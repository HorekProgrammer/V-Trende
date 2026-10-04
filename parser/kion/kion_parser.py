import json
import math
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHART_URL = "https://music.mts.ru/chart"
CHART_API_URL = "https://api.music.yandex.net/users/324504548/playlists/1480"
CHART_SIZE = 100


class _NextDataParser(HTMLParser):
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


def _parse_playlist(playlist: dict) -> list[dict]:
    try:
        tracks = playlist["tracks"]
        if (playlist.get("title") != "Настоящий чарт"
                or playlist.get("trackCount") != CHART_SIZE
                or not isinstance(tracks, list) or len(tracks) != CHART_SIZE):
            raise ValueError

        result = []
        for position, item in enumerate(tracks, start=1):
            track = item.get("track", item)
            title = track["title"]
            raw_artists = track["artists"]
            artists = [artist["name"] for artist in raw_artists]
            if (not isinstance(title, str) or not title.strip()
                    or not isinstance(raw_artists, list) or not artists
                    or any(not isinstance(artist, str) or not artist.strip() for artist in artists)):
                raise ValueError
            result.append({"position": position, "title": title, "artists": artists})
        return result
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError(
            "КИОН Музыка: некорректный или неполный топ-100; возможно, формат сайта изменился."
        ) from None


def parse_chart_html(html: str) -> list[dict]:
    parser = _NextDataParser()
    parser.feed(html)
    if not parser.chunks:
        raise RuntimeError("КИОН Музыка: данные чарта не найдены.")
    try:
        data = json.loads("".join(parser.chunks))
        return _parse_playlist(data["props"]["pageProps"]["playlist"])
    except (json.JSONDecodeError, KeyError, TypeError):
        raise RuntimeError("КИОН Музыка: некорректные данные страницы чарта.") from None


def _parse_api_response(body: bytes) -> list[dict]:
    try:
        data = json.loads(body.decode("utf-8"))
        return _parse_playlist(data["result"])
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        raise RuntimeError("КИОН Музыка: некорректный ответ API.") from None


def _fetch_chart(timeout: float) -> list[dict]:
    request = Request(CHART_API_URL, headers={
        "Accept": "application/json",
        "User-Agent": "V-Trende/1.0",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            return _parse_api_response(response.read())
    except HTTPError as error:
        status = error.code
        error.close()
        raise RuntimeError(f"КИОН Музыка: HTTP {status}.") from None
    except (URLError, OSError):
        raise RuntimeError("КИОН Музыка: ошибка сети или таймаут.") from None


def get_kion_chart(limit: int | None = None, *, timeout: float = 30) -> list[dict]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit должен быть положительным целым числом или None.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")

    return _fetch_chart(timeout)[:limit]
