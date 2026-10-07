import base64
import json
import math
import re
from html import unescape
from html.parser import HTMLParser
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

RANKING_URL = "https://twitchtracker.com/channels/ranking/russian/personality"
PROFILE_URL = "https://twitchtracker.com/{channel}"
PAGE_SIZE = 50
MAX_CHANNELS = 150
PERIOD_DAYS = 7
CHANNEL_DELAY_SECONDS = 1.0
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_DELAY_SECONDS = 30

_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class _RankingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_body = False
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "channels":
            self.in_table = True
        elif self.in_table and tag == "tbody":
            self.in_body = True
        elif self.in_body and tag == "tr":
            self.row = []
        elif self.row is not None and tag == "td":
            self.cell = {"text": [], "href": None}
        elif self.cell is not None and tag == "a" and self.cell["href"] is None:
            self.cell["href"] = attributes.get("href")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None and self.row is not None:
            self.cell["text"] = " ".join("".join(self.cell["text"]).split())
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
        elif tag == "tbody" and self.in_body:
            self.in_body = False
        elif tag == "table" and self.in_table:
            self.in_table = False


def _integer(value: str) -> int:
    if not re.fullmatch(r"\+?[\d\s,]+", value):
        raise ValueError
    return int(value.lstrip("+").replace(" ", "").replace(",", ""))


def _parse_ranking_entries(html: str, *, expected_start: int | None = None) -> list[dict]:
    parser = _RankingParser()
    parser.feed(html)
    result = []
    try:
        for cells in parser.rows:
            if not cells or not re.fullmatch(r"#\d+", cells[0]["text"]):
                continue
            if len(cells) != 11:
                raise ValueError
            position = _integer(cells[0]["text"].removeprefix("#"))
            channel = cells[2]["text"]
            href = cells[2]["href"]
            slug_match = re.fullmatch(r"/([A-Za-z0-9_]+)", href or "")
            if not channel or slug_match is None:
                raise ValueError
            result.append({
                "position": position,
                "channel": channel,
                "total_followers": _integer(cells[9]["text"]),
                "_slug": slug_match.group(1),
            })
    except (TypeError, ValueError):
        raise RuntimeError(
            "TwitchTracker: некорректная строка рейтинга; возможно, формат сайта изменился."
        ) from None

    if not result:
        raise RuntimeError("TwitchTracker: таблица рейтинга не найдена.")
    start = expected_start if expected_start is not None else result[0]["position"]
    positions = [entry["position"] for entry in result]
    if positions != list(range(start, start + len(result))):
        raise RuntimeError("TwitchTracker: позиции рейтинга идут не по порядку.")
    return result


def parse_ranking_html(html: str, *, expected_start: int | None = None) -> list[dict]:
    return [
        {"channel": entry["channel"], "total_followers": entry["total_followers"]}
        for entry in _parse_ranking_entries(html, expected_start=expected_start)
    ]


def _page_url(page: int) -> str:
    return RANKING_URL if page == 1 else f"{RANKING_URL}?{urlencode({'page': page})}"


def _read(request: Request, timeout: float, context: str) -> str:
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After") if error.headers else None
            error.close()
            if status == 429 and attempt < RATE_LIMIT_RETRIES:
                try:
                    delay = max(float(retry_after), 1) if retry_after is not None else 0
                except ValueError:
                    delay = 0
                sleep(delay or RATE_LIMIT_DELAY_SECONDS * (2 ** attempt))
                continue
            raise RuntimeError(f"TwitchTracker: HTTP {status} ({context}).") from None
        except (URLError, OSError):
            raise RuntimeError(f"TwitchTracker: ошибка сети или таймаут ({context}).") from None
        except UnicodeError:
            raise RuntimeError(f"TwitchTracker: некорректная кодировка страницы ({context}).") from None
    raise RuntimeError(f"TwitchTracker: превышено число повторов ({context}).")


def _fetch_ranking_page(page: int, timeout: float) -> list[dict]:
    request = Request(_page_url(page), headers=_HEADERS)
    html = _read(request, timeout, f"страница рейтинга {page}")
    return _parse_ranking_entries(html, expected_start=(page - 1) * PAGE_SIZE + 1)


def _decode_ecs(html: str) -> dict:
    match = re.search(r'<meta\s+id=["\']ecs["\']\s+content=["\']([^"\']+)', html)
    if match is None:
        raise ValueError
    encoded = unescape(match.group(1)).split("!")
    if len(encoded) < 2:
        raise ValueError

    decoded = []
    for part in encoded:
        part = part.replace("#", "W")
        part += "=" * (-len(part) % 4)
        decoded.append(json.loads(base64.b64decode(part, validate=True).decode("utf-8")))
    keys = decoded.pop()
    if not isinstance(keys, list) or len(keys) != len(decoded):
        raise ValueError
    return dict(zip(keys, decoded))


def _number(value) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError
    if not math.isfinite(value):
        raise ValueError
    return value


def _whole_number(value) -> int:
    value = _number(value)
    if not float(value).is_integer():
        raise ValueError
    return int(value)


def parse_weekly_stats_html(html: str) -> dict:
    try:
        current = _decode_ecs(html)["performance"]["week"]["curr"]
        metric_names = (
            "duration",
            "avg_viewers",
            "max_viewers",
            "man_hours",
            "followers",
            "followers_hour",
        )
        if all(current[name] is None for name in metric_names):
            return {
                "hours_streamed": 0.0,
                "average_viewers": 0,
                "peak_viewers": 0,
                "hours_watched": 0,
                "followers_gained": 0,
                "followers_per_hour": 0.0,
            }
        values = {
            "hours_streamed": round(_number(current["duration"]) / 60, 1),
            "average_viewers": _whole_number(current["avg_viewers"]),
            "peak_viewers": _whole_number(current["max_viewers"]),
            "hours_watched": _whole_number(current["man_hours"]),
            "followers_gained": _whole_number(current["followers"]),
            "followers_per_hour": _number(current["followers_hour"]),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeError):
        raise RuntimeError(
            "TwitchTracker: недельная статистика не найдена; возможно, формат сайта изменился."
        ) from None
    return values


def _channel_bootstrap(html: str, slug: str) -> tuple[int, str]:
    channel_id_match = re.search(r"window\.channel\s*=\s*\{.*?\bid\s*:\s*(\d+)", html, re.DOTALL)
    try:
        channel_id = int(channel_id_match.group(1))
        fragments_url = _decode_ecs(html)["fragments"]
        parsed = urlparse(fragments_url)
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeError):
        raise RuntimeError(f"TwitchTracker: данные канала {slug} не найдены.") from None

    expected_path = f"/{slug.lower()}/fragments"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "twitchtracker.com"
        or parsed.path.lower() != expected_path
        or not parsed.query
    ):
        raise RuntimeError(f"TwitchTracker: некорректный адрес статистики канала {slug}.")
    return channel_id, fragments_url


def _fetch_channel_stats(slug: str, timeout: float) -> dict:
    profile_url = PROFILE_URL.format(channel=quote(slug))
    profile_request = Request(profile_url, headers={**_HEADERS, "Referer": RANKING_URL})
    profile_html = _read(profile_request, timeout, f"канал {slug}")
    channel_id, fragments_url = _channel_bootstrap(profile_html, slug)

    body = urlencode({"id": channel_id}).encode("ascii")
    fragments_request = Request(
        fragments_url,
        data=body,
        headers={
            **_HEADERS,
            "Referer": profile_url,
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    fragments_html = _read(fragments_request, timeout, f"статистика канала {slug}")
    try:
        return parse_weekly_stats_html(fragments_html)
    except RuntimeError as error:
        raise RuntimeError(f"{error} Канал: {slug}.") from None


def get_russian_twitch_ranking(limit: int = MAX_CHANNELS, *, timeout: float = 30) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= MAX_CHANNELS:
        raise ValueError(f"limit должен быть целым числом от 1 до {MAX_CHANNELS}.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")

    ranking = []
    for page in range(1, math.ceil(limit / PAGE_SIZE) + 1):
        entries = _fetch_ranking_page(page, timeout)
        if len(entries) != PAGE_SIZE:
            raise RuntimeError("TwitchTracker: страница рейтинга загружена не полностью.")
        ranking.extend(entries)
    ranking = ranking[:limit]

    result = []
    for index, entry in enumerate(ranking):
        if index:
            sleep(CHANNEL_DELAY_SECONDS)
        stats = _fetch_channel_stats(entry["_slug"], timeout)
        result.append({
            "channel": entry["channel"],
            "total_followers": entry["total_followers"],
            **stats,
        })
    return result
