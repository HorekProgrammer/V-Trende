import json
from html.parser import HTMLParser
import math
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHART_URL = "https://music.yandex.ru/chart"
_PATCH = re.compile(
    r"window\.__PAGE_STATE_PATCHES__\s*\[\s*['\"]pages/chart['\"]\s*\]\.push\s*\(\s*"
)
_ITEM = re.compile(r"/tracksSubPage/items/(\d+)$")


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None


def _normalize(track: dict) -> dict:
    try:
        title = track["title"]
        position = track["chart"]["position"]
        artists = [artist["name"] for artist in track["artists"]]
        if (not isinstance(title, str) or not title.strip()
                or type(position) is not int or position < 1
                or not artists or any(not isinstance(a, str) or not a.strip() for a in artists)):
            raise ValueError
        return {
            "title": title,
            "artists": artists,
            "position": position,
        }
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Яндекс Музыка: изменилась структура данных трека.") from None


def parse_chart_html(html: str) -> list[dict]:
    parser = _Scripts()
    parser.feed(html)
    items = {}
    state = None
    try:
        for script in parser.scripts:
            for match in _PATCH.finditer(script):
                operations, _ = json.JSONDecoder().raw_decode(script[match.end():])
                if not isinstance(operations, list):
                    raise ValueError
                for operation in operations:
                    path = operation["path"]
                    if path == "/tracksSubPage/loadingState":
                        state = operation["value"]
                    item = _ITEM.fullmatch(path)
                    if item:
                        if operation["op"] not in ("add", "replace"):
                            raise ValueError
                        items[int(item.group(1))] = _normalize(operation["value"])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Яндекс Музыка: некорректные JSON-данные чарта.") from None
    if state != "RESOLVE" or not items:
        raise RuntimeError(
            "Чарт не найден или загружен не полностью. Возможны ограничение региона, "
            "страница проверки доступа или изменение формата сайта."
        )
    tracks = sorted(items.values(), key=lambda track: track["position"])
    if (sorted(items) != list(range(len(items)))
            or [t["position"] for t in tracks] != list(range(1, len(tracks) + 1))):
        raise RuntimeError("Яндекс Музыка: неполный чарт или дубликаты позиций.")
    return tracks


def get_yandex_music_chart(limit: int | None = None, *, timeout: float = 30) -> list[dict]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit должен быть положительным целым числом или None.")
    if (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("timeout должен быть положительным конечным числом.")
    request = Request(CHART_URL, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8")
    except HTTPError as error:
        status = error.code
        error.close()
        raise RuntimeError(f"Яндекс Музыка: HTTP {status}.") from None
    except (URLError, OSError):
        raise RuntimeError("Яндекс Музыка: ошибка сети или таймаут.") from None
    except UnicodeError:
        raise RuntimeError("Яндекс Музыка: некорректная кодировка страницы.") from None
    return parse_chart_html(html)[:limit]
