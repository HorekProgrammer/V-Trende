import json
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from parser.common.covers import twitch_avatar_url

CHANNEL_URL = "https://www.twitch.tv/{slug}"
CACHE_FILE = Path(__file__).resolve().parents[2] / "data" / "cache" / "twitch" / "avatars.json"
MAX_PAGE_BYTES = 2_000_000
MAX_MISSES_IN_ROW = 5
PAUSE_SECONDS = 0.3

_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class _MetaImages(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        attributes = dict(attrs)
        key = attributes.get("property") or attributes.get("name")
        if key in ("og:image", "twitter:image") and attributes.get("content"):
            self.images.append(attributes["content"])


def avatar_from_channel_html(html: str) -> str | None:
    parser = _MetaImages()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001
        return None
    for image in parser.images:
        url = twitch_avatar_url(image)
        if url and "static-cdn.jtvnw.net/jtv_user_pictures/" in url:
            return url
    return None


def fetch_avatar(slug: str, timeout: float) -> str | None:
    request = Request(CHANNEL_URL.format(slug=quote(slug)), headers=_HEADERS)
    try:
        with urlopen(request, timeout=min(timeout, 15)) as response:
            html = response.read(MAX_PAGE_BYTES).decode("utf-8", errors="replace")
    except HTTPError as error:
        error.close()
        return None
    except (URLError, OSError, ValueError):
        return None
    return avatar_from_channel_html(html)


def _load_cache(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {slug: url for slug, url in value.items() if isinstance(url, str) and twitch_avatar_url(url)}


def _save_cache(path: Path, cache: dict[str, str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def fill_missing_avatars(channels: list[dict], *, timeout: float = 30,
                         cache_path: Path | None = None) -> int:
    cache_path = cache_path or CACHE_FILE
    cache = _load_cache(cache_path)
    found = misses = 0
    changed = False
    for channel in channels:
        slug = str(channel.get("slug") or "").lower()
        if not slug:
            continue
        if channel.get("cover_url"):
            if cache.get(slug) != channel["cover_url"]:
                cache[slug] = channel["cover_url"]
                changed = True
            continue
        if slug in cache:
            channel["cover_url"] = cache[slug]
            found += 1
            continue
        if misses >= MAX_MISSES_IN_ROW:
            continue
        if found or misses:
            sleep(PAUSE_SECONDS)
        avatar = fetch_avatar(slug, timeout)
        if avatar:
            channel["cover_url"] = cache[slug] = avatar
            found += 1
            misses = 0
            changed = True
        else:
            misses += 1
    if changed:
        _save_cache(cache_path, cache)
    return found
