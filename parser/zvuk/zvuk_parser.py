import json
import math
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
            result.append({"position": position, "title": title, "artists": artists})
        return result
    except (ValueError, TypeError, KeyError):
        raise RuntimeError("Звук: некорректные данные или неполный топ-100; возможно, формат сайта изменился.") from None


def get_zvuk_chart(limit: int | None = None, *, timeout: float = 30) -> list[dict]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit должен быть положительным целым числом или None.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")
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
        raise RuntimeError(f"Звук: HTTP {status}.") from None
    except (URLError, OSError):
        raise RuntimeError("Звук: ошибка сети или таймаут.") from None
    except UnicodeError:
        raise RuntimeError("Звук: некорректная кодировка страницы.") from None
    return parse_chart_html(html)[:limit]
