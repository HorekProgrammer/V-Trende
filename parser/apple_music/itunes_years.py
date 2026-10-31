import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from parser.common.years import iso_release_year

LOOKUP_URL = "https://itunes.apple.com/lookup"
STOREFRONT = "us"
BATCH_SIZE = 150


def _lookup(ids: list[str], timeout: float) -> dict[str, int]:
    query = urlencode({"id": ",".join(ids), "country": STOREFRONT, "entity": "song"})
    request = Request(f"{LOOKUP_URL}?{query}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        error.close()
        return {}
    except (URLError, OSError, ValueError):
        return {}
    years = {}
    for result in data.get("results", []) if isinstance(data, dict) else []:
        if not isinstance(result, dict) or result.get("wrapperType") != "track":
            continue
        year = iso_release_year(result.get("releaseDate"))
        if year and result.get("trackId") is not None:
            years[str(result["trackId"])] = year
    return years


def fill_years(tracks: list[dict], *, timeout: float = 30) -> int:
    ids = [str(t["apple_id"]) for t in tracks if t.get("apple_id") and not t.get("year")]
    years = {}
    for start in range(0, len(ids), BATCH_SIZE):
        years.update(_lookup(ids[start:start + BATCH_SIZE], timeout))
    found = 0
    for track in tracks:
        year = years.get(str(track.get("apple_id")))
        if year and not track.get("year"):
            track["year"] = year
            found += 1
    return found
