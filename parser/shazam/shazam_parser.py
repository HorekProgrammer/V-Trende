import math
from html.parser import HTMLParser

CHART_URL = "https://www.shazam.com/ru-ru/charts/top-200/russia"
CHART_SIZE = 200


class _ChartParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._rows = []
        self._list_items = []
        self._rank_span_depth = None

    @property
    def rows(self):
        return self._rows

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "li":
            self._list_items.append({"position_text": [], "titles": [], "artists": []})
            return
        if not self._list_items:
            return

        row = self._list_items[-1]
        if tag == "span" and "SongItem_rankingNumber" in attributes.get("class", ""):
            self._rank_span_depth = len(self._list_items)
        elif tag == "a":
            test_id = attributes.get("data-test-id")
            label = attributes.get("aria-label")
            if test_id == "charts_userevent_list_songTitle" and label:
                row["titles"].append(label)
            elif test_id == "charts_userevent_list_artistName" and label:
                row["artists"].append(label)

    def handle_data(self, data):
        if self._list_items and self._rank_span_depth == len(self._list_items):
            self._list_items[-1]["position_text"].append(data)

    def handle_endtag(self, tag):
        if tag == "span" and self._rank_span_depth == len(self._list_items):
            self._rank_span_depth = None
        elif tag == "li" and self._list_items:
            row = self._list_items.pop()
            if row["titles"] or row["artists"] or row["position_text"]:
                self._rows.append(row)


def parse_chart_html(html: str) -> list[dict]:
    parser = _ChartParser()
    parser.feed(html)
    result = []
    try:
        for row in parser.rows:
            titles = list(dict.fromkeys(row["titles"]))
            artists = list(dict.fromkeys(row["artists"]))
            position = int("".join(row["position_text"]).strip())
            if (len(titles) != 1 or not titles[0].strip() or not artists
                    or any(not artist.strip() for artist in artists)):
                raise ValueError
            result.append({
                "position": position,
                "title": titles[0],
                "artists": artists,
            })
    except (TypeError, ValueError):
        raise RuntimeError("Shazam: некорректная строка чарта; возможно, формат сайта изменился.") from None

    positions = [track["position"] for track in result]
    if len(result) != CHART_SIZE or positions != list(range(1, CHART_SIZE + 1)):
        raise RuntimeError("Shazam: чарт отсутствует или загружен не полностью.")
    return result


def _validate_tracks(tracks: list[dict]) -> list[dict]:
    try:
        result = []
        for track in tracks:
            position = track["position"]
            title = track["title"]
            artists = track["artists"]
            if (type(position) is not int or not isinstance(title, str) or not title.strip()
                    or not isinstance(artists, list) or not artists
                    or any(not isinstance(artist, str) or not artist.strip() for artist in artists)):
                raise ValueError
            result.append({"position": position, "title": title, "artists": artists})
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Shazam: некорректная строка чарта; возможно, формат сайта изменился.") from None
    if (len(result) != CHART_SIZE
            or [track["position"] for track in result] != list(range(1, CHART_SIZE + 1))):
        raise RuntimeError("Shazam: чарт отсутствует или загружен не полностью.")
    return result


def _fetch_chart(timeout: float) -> list[dict]:
    try:
        from playwright.sync_api import Error, TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError:
        raise RuntimeError(
            "Shazam: установите Playwright командой 'pip install playwright' и браузер "
            "командой 'playwright install chromium'."
        ) from None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale="ru-RU")
                response = page.goto(CHART_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
                if response is None or not response.ok:
                    status = response.status if response is not None else "нет ответа"
                    raise RuntimeError(f"Shazam: HTTP {status}.")
                page.wait_for_selector(
                    '[data-test-id="charts_userevent_list_songTitle"]',
                    timeout=timeout * 1000,
                )
                tracks = page.locator('li:has([data-test-id="charts_userevent_list_songTitle"])').evaluate_all("""
                    rows => rows.map(row => ({
                        position: Number(row.querySelector('[class*="SongItem_rankingNumber"]')?.textContent.trim()),
                        title: row.querySelector('[data-test-id="charts_userevent_list_songTitle"]')?.getAttribute('aria-label'),
                        artists: [...new Set([...row.querySelectorAll('[data-test-id="charts_userevent_list_artistName"]')]
                            .map(element => element.getAttribute('aria-label')).filter(Boolean))],
                    }))
                """)
                return _validate_tracks(tracks)
            finally:
                browser.close()
    except RuntimeError:
        raise
    except PlaywrightTimeoutError:
        raise RuntimeError("Shazam: превышено время ожидания загрузки чарта.") from None
    except Error:
        raise RuntimeError("Shazam: ошибка запуска браузера или загрузки страницы.") from None


def get_shazam_chart(limit: int | None = None, *, timeout: float = 30) -> list[dict]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit должен быть положительным целым числом или None.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")
    return _fetch_chart(timeout)[:limit]
