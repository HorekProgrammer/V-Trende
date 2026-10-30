import base64
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from .channel_classifier import (
    classify_channels,
    fetch_page_markdown,
    is_person,
)

RANKING_URL = "https://twitchtracker.com/channels/ranking/russian"
PROFILE_URL = "https://twitchtracker.com/{channel}"
PAGE_SIZE = 50
MAX_CHANNELS = 150
HARDCODED_CHANNELS = (
    {"channel": "evelone2004", "slug": "evelone2004"},
)
PERIOD_DAYS = 7
CHANNEL_DELAY_SECONDS = 1.0
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_DELAY_SECONDS = 30
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "twitch"
MOSCOW_TZ = timezone(timedelta(hours=3))

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


def parse_ranking_positions_html(html: str, *, expected_start: int | None = None) -> list[dict]:
    """Позиции каналов в рейтинге без статистики: для сохранения в базу."""
    return [
        {"position": entry["position"], "channel": entry["channel"], "slug": entry["_slug"]}
        for entry in _parse_ranking_entries(html, expected_start=expected_start)
    ]


def parse_ranking_markdown(markdown: str, *, expected_start: int | None = None) -> list[dict]:
    result = []
    for match in re.finditer(r"(?m)^#(\d+)\s*\|\s*([A-Za-z0-9_]+)\s*\|", markdown):
        result.append({
            "position": int(match.group(1)),
            "channel": match.group(2),
            "total_followers": 0,
            "_slug": match.group(2).lower(),
        })
    if not result:
        raise RuntimeError("DeepSeek Fetch: TwitchTracker ranking table was not found.")
    start = expected_start if expected_start is not None else result[0]["position"]
    positions = [entry["position"] for entry in result]
    if positions != list(range(start, start + len(result))):
        raise RuntimeError("DeepSeek Fetch: TwitchTracker ranking positions are not sequential.")
    return result


def _page_url(page: int) -> str:
    return RANKING_URL if page == 1 else f"{RANKING_URL}?{urlencode({'page': page})}"


def _read(request: Request, timeout: float, context: str) -> str:
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            proxy = (os.getenv("TWITCHTRACKER_PROXY") or "").strip()
            if proxy and urlparse(request.full_url).hostname == "twitchtracker.com":
                response_context = build_opener(
                    ProxyHandler({"http": proxy, "https": proxy})
                ).open(request, timeout=timeout)
            else:
                response_context = urlopen(request, timeout=timeout)
            with response_context as response:
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
    expected_start = (page - 1) * PAGE_SIZE + 1
    try:
        html = _read(request, timeout, f"страница рейтинга {page}")
    except RuntimeError as error:
        if "HTTP 403" not in str(error) and not os.getenv("TWITCHTRACKER_PROXY"):
            raise
        markdown = fetch_page_markdown(request.full_url, timeout=timeout)
        return parse_ranking_markdown(markdown, expected_start=expected_start)
    return _parse_ranking_entries(html, expected_start=expected_start)


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


def _markdown_number(markdown: str, label: str) -> int | float:
    match = re.search(
        rf"(?m)^(?:#\d+\s+)?([+-]?[\d,.]+(?:[KMB])?)\s*\n\n{re.escape(label)}\s*$",
        markdown,
    )
    if match is None:
        raise ValueError
    raw = match.group(1).replace(",", "")
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(raw[-1:], 1)
    if multiplier != 1:
        raw = raw[:-1]
    value = float(raw) * multiplier
    return int(value) if value.is_integer() else value


def parse_weekly_stats_markdown(markdown: str) -> dict:
    try:
        return {
            "hours_streamed": float(_markdown_number(markdown, "Hours streamed")),
            "average_viewers": int(_markdown_number(markdown, "Average viewers")),
            "peak_viewers": int(_markdown_number(markdown, "Peak viewers")),
            "hours_watched": int(_markdown_number(markdown, "Hours watched")),
            "followers_gained": int(_markdown_number(markdown, "Followers gained")),
            "followers_per_hour": float(_markdown_number(markdown, "Followers / hour")),
            "total_followers": int(_markdown_number(markdown, "Total followers")),
        }
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError(
            "DeepSeek Fetch: weekly TwitchTracker channel statistics were not found."
        ) from None


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
    try:
        profile_html = _read(profile_request, timeout, f"канал {slug}")
    except RuntimeError as error:
        if "HTTP 403" not in str(error) and not os.getenv("TWITCHTRACKER_PROXY"):
            raise
        markdown = fetch_page_markdown(profile_url, timeout=timeout)
        return parse_weekly_stats_markdown(markdown)
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


def _validate_arguments(limit, timeout) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_CHANNELS:
        raise ValueError(f"limit должен быть целым числом от 1 до {MAX_CHANNELS}.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")


def _fetch_ranking(limit: int, timeout: float) -> list[dict]:
    ranking = []
    for page in range(1, math.ceil(limit / PAGE_SIZE) + 1):
        entries = _fetch_ranking_page(page, timeout)
        if len(entries) != PAGE_SIZE:
            raise RuntimeError("TwitchTracker: страница рейтинга загружена не полностью.")
        ranking.extend(entries)
    return ranking[:limit]


def _fetch_candidates(limit: int, timeout: float) -> list[dict]:
    result = _fetch_ranking(limit, timeout)
    if limit != MAX_CHANNELS:
        return result
    known = {entry["_slug"].lower() for entry in result}
    for channel in HARDCODED_CHANNELS:
        slug = channel["slug"].lower()
        if slug in known:
            continue
        result.append({
            "position": len(result) + 1,
            "channel": channel["channel"],
            "total_followers": 0,
            "_slug": slug,
        })
        known.add(slug)
    return result


def _fetch_personal_candidates(limit: int, timeout: float) -> list[dict]:
    candidates = _fetch_candidates(limit, timeout)
    classifications = classify_channels(candidates, timeout=timeout)
    result = []
    for entry in candidates:
        classification = classifications.get(entry["_slug"].lower())
        if classification is None:
            raise RuntimeError(f'DeepSeek did not return a classification for {entry["_slug"]}.')
        if is_person(classification):
            result.append(entry)
    return result


def get_russian_twitch_positions(limit: int = MAX_CHANNELS, *, timeout: float = 30) -> list[dict]:
    """Только позиции каналов в рейтинге — без запросов статистики каждого канала."""
    _validate_arguments(limit, timeout)
    return [
        {"position": entry["position"], "channel": entry["channel"], "slug": entry["_slug"]}
        for entry in _fetch_personal_candidates(limit, timeout)
    ]


def _weekly_cache_path() -> Path:
    today = datetime.now(MOSCOW_TZ).date()
    week = today - timedelta(days=today.weekday())
    return CACHE_DIR / f"{week.isoformat()}.json"


def _load_stats_cache(path: Path) -> dict[str, dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _save_stats_cache(path: Path, cache: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def get_russian_twitch_ranking(
    limit: int = MAX_CHANNELS,
    *,
    timeout: float = 30,
    cache_path: Path | None = None,
) -> list[dict]:
    _validate_arguments(limit, timeout)
    ranking = _fetch_personal_candidates(limit, timeout)
    cache = _load_stats_cache(cache_path) if cache_path is not None else {}

    result = []
    for index, entry in enumerate(ranking):
        slug = entry["_slug"]
        stats = cache.get(slug)
        required = {
            "hours_streamed", "average_viewers", "peak_viewers", "hours_watched",
            "followers_gained", "followers_per_hour",
        }
        if not isinstance(stats, dict) or not required.issubset(stats):
            stats = None
        if stats is None and index:
            sleep(CHANNEL_DELAY_SECONDS)
        if stats is None:
            stats = _fetch_channel_stats(slug, timeout)
            if cache_path is not None:
                cache[slug] = stats
                _save_stats_cache(cache_path, cache)
        result.append({
            "position": len(result) + 1,
            "channel": entry["channel"],
            "slug": slug,
            "total_followers": entry["total_followers"],
            **stats,
        })
    return result


def get_cached_russian_twitch_ranking(limit: int = MAX_CHANNELS, *, timeout: float = 30) -> list[dict]:
    """Полный недельный рейтинг с поканальным возобновлением после сетевого сбоя."""
    return get_russian_twitch_ranking(limit, timeout=timeout, cache_path=_weekly_cache_path())
