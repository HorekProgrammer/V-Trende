import json
import math
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHART_URL = "https://music.apple.com/us/playlist/top-100-russia/pl.728bd30a9247487c80a483f4168a9dcd"
CHART_SIZE = 100


class _ServerDataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.inside = dict(attrs).get("id") == "serialized-server-data"

    def handle_data(self, data):
        if self.inside:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside = False


def parse_chart_html(html: str) -> list[dict]:
    parser = _ServerDataParser()
    parser.feed(html)
    if not parser.chunks:
        raise RuntimeError("Apple Music: данные страницы не найдены.")

    try:
        server_data = json.loads("".join(parser.chunks))
        sections = server_data["data"][0]["data"]["sections"]
        track_sections = [section for section in sections if section.get("itemKind") == "trackLockup"]
        if len(track_sections) != 1:
            raise ValueError
        items = track_sections[0]["items"]
        if not isinstance(items, list) or len(items) != CHART_SIZE:
            raise ValueError

        result = []
        for position, item in enumerate(items, start=1):
            title = item["title"]
            artist_links = item["subtitleLinks"]
            artists = [link["title"] for link in artist_links]
            if (not isinstance(title, str) or not title.strip()
                    or not isinstance(artist_links, list) or not artists
                    or any(not isinstance(artist, str) or not artist.strip() for artist in artists)):
                raise ValueError
            result.append({"position": position, "title": title, "artists": artists})
        return result
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError(
            "Apple Music: некорректный или неполный топ-100; возможно, формат сайта изменился."
        ) from None


def get_apple_music_chart(limit: int | None = None, *, timeout: float = 30) -> list[dict]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit должен быть положительным целым числом или None.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")

    request = Request(CHART_URL, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8")
    except HTTPError as error:
        status = error.code
        error.close()
        raise RuntimeError(f"Apple Music: HTTP {status}.") from None
    except (URLError, OSError):
        raise RuntimeError("Apple Music: ошибка сети или таймаут.") from None
    except UnicodeError:
        raise RuntimeError("Apple Music: некорректная кодировка страницы.") from None
    return parse_chart_html(html)[:limit]
