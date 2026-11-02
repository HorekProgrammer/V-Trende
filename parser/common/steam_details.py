import json
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .covers import clean_image_url, steam_fallback_cover_url

APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"
REGION = "us"
MAX_REQUESTS = 40
PAUSE_SECONDS = 0.5


def header_image_from_details(payload, app_id) -> str | None:
    if not isinstance(payload, dict):
        return None
    entry = payload.get(str(app_id))
    if not isinstance(entry, dict) or entry.get("success") is not True:
        return None
    data = entry.get("data")
    if not isinstance(data, dict):
        return None
    url = clean_image_url(data.get("header_image"))
    return url if url and "steamstatic.com" in url else None


def _fetch_details(app_id, timeout) -> dict | None:
    query = urlencode({"appids": app_id, "cc": REGION, "l": "english"})
    request = Request(f"{APP_DETAILS_URL}?{query}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        error.close()
        return None
    except (URLError, OSError, ValueError):
        return None


def fill_missing_covers(items: list[dict], *, timeout: float = 30) -> int:
    found = requests = 0
    for item in items:
        if item.get("cover_url") or not item.get("steam_app_id"):
            continue
        app_id = item["steam_app_id"]
        cover = None
        if requests < MAX_REQUESTS:
            if requests:
                sleep(PAUSE_SECONDS)
            requests += 1
            cover = header_image_from_details(_fetch_details(app_id, timeout), app_id)
        if cover:
            found += 1
        item["cover_url"] = cover or steam_fallback_cover_url(app_id)
    return found
