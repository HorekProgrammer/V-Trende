import json
import math
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from parser.common.covers import zvuk_track_cover

CHART_URL = "https://zvuk.com/top100"


class _NextData(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.inside = dict(attrs).get("id") == "__NEXT_DATA__"

    def handle_data(self, data):
        if self.inside:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside = False


def parse_chart_html(html: str) -> list[dict]:
    parser = _NextData()
    parser.feed(html)
    if not parser.chunks:
        raise RuntimeError(
            "Звук: данные чарта отсутствуют. Возможно, сайт вернул проверку доступа "
            "Servicepipe. Можно передать сохранённый HTML через --html."
        )
    try:
        data = json.loads("".join(parser.chunks))
        tracks = data["props"]["pageProps"]["hydrationData"]["trackList"]["tracks"]
        if not isinstance(tracks, list) or len(tracks) != 100:
            raise ValueError
        result = []
        for position, track in enumerate(tracks, start=1):
            title = track["title"]
            raw_artists = track["artists"]
            if not isinstance(raw_artists, list):
                raise ValueError
            artists = [artist["name"] for artist in raw_artists]
            if (not isinstance(title, str) or not title.strip() or not artists
                    or any(not isinstance(name, str) or not name.strip() for name in artists)):
                raise ValueError
            result.append({"position": position, "title": title, "artists": artists,
                           "cover_url": zvuk_track_cover(track)})
        return result
    except (ValueError, TypeError, KeyError):
        raise RuntimeError("Звук: некорректные данные или неполный топ-100; возможно, формат сайта изменился.") from None


# Ответы, которыми защита сайта отказывает простому запросу.
_BLOCKED_STATUSES = {401, 403, 429, 503}
# Минимальное время ожидания в окне браузера: проверка доступа и загрузка чарта.
BROWSER_TIMEOUT = 120


def _fetch_with_browser(timeout: float) -> str:
    """Открывает чарт в обычном (видимом) окне браузера с постоянным профилем.

    Невидимый (headless) режим проверка доступа Звука не пропускает, а обычное окно
    проходит её само, без действий пользователя: окно появляется на несколько секунд
    и закрывается, как только данные чарта загрузились.
    """
    from parser.common.browser import BrowserFetchError, fetch_html
    try:
        return fetch_html("zvuk", CHART_URL, wait_selector="script#__NEXT_DATA__",
                          timeout=max(timeout, BROWSER_TIMEOUT), headless=False)
    except BrowserFetchError as error:
        raise RuntimeError(f"Звук: чарт не загрузился в окне браузера: {error}.") from None


def fetch_chart_html(*, timeout: float = 30, browser_fallback: bool = False,
                     headed: bool = False) -> str:
    """HTML страницы чарта: простым запросом, а при проверке доступа — через браузер."""
    if headed:
        return _fetch_with_browser(timeout)

    request = Request(CHART_URL, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8-sig")
    except HTTPError as error:
        status = error.code
        error.close()
        if browser_fallback and status in _BLOCKED_STATUSES:
            return _fetch_with_browser(timeout)
        raise RuntimeError(f"Звук: HTTP {status}.") from None
    except (URLError, OSError):
        raise RuntimeError("Звук: ошибка сети или таймаут.") from None
    except UnicodeError:
        raise RuntimeError("Звук: некорректная кодировка страницы.") from None
    if browser_fallback and 'id="__NEXT_DATA__"' not in html:
        # Вместо чарта пришла страница проверки доступа — открываем окно браузера.
        return _fetch_with_browser(timeout)
    return html


def get_zvuk_chart(limit: int | None = None, *, timeout: float = 30,
                   browser_fallback: bool = False, headed: bool = False) -> list[dict]:
    """Топ-100 Звука.

    browser_fallback — если сайт не отдал данные простому запросу (проверка доступа),
    открыть страницу в обычном окне браузера (parser/common/browser.py); окно
    закрывается само. Нужен компьютер с рабочим столом (Windows, macOS, Linux с экраном).
    headed — сразу открыть окно браузера, без попытки простого запроса.
    """
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit должен быть положительным целым числом или None.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")
    html = fetch_chart_html(timeout=timeout, browser_fallback=browser_fallback, headed=headed)
    return parse_chart_html(html)[:limit]
