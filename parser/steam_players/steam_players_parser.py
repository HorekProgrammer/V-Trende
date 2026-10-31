import json
import math
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from parser.common.covers import steam_cover_url
from parser.common.years import steam_release_year


MOST_PLAYED_API_URL = (
    "https://api.steampowered.com/"
    "ISteamChartsService/GetGamesByConcurrentPlayers/v1/"
)

TAG_NAMES_URL = (
    "https://store.steampowered.com/"
    "tagdata/populartags/english"
)

CHART_SIZE = 100
TAG_COUNT = 10


def _fetch_text(url, timeout):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://store.steampowered.com",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            return response.read().decode("utf-8")
    except (
        URLError,
        TimeoutError,
        OSError,
    ) as exc:
        raise RuntimeError(
            "Steam request failed"
        ) from exc


def _fetch_payload(timeout):
    payload = {
        "context": {
            "language": "english",
            "country_code": "RU",
        },
        "data_request": {
            "include_basic_info": True,
            "include_assets": True,
            "include_release": True,
            "include_tag_count": TAG_COUNT,
        },
    }

    query = urlencode(
        {
            "input_json": json.dumps(payload),
        }
    )

    raw = _fetch_text(
        f"{MOST_PLAYED_API_URL}?{query}",
        timeout,
    )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Steam Most Played returned invalid JSON"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "Steam Most Played returned invalid data"
        )

    return data


def _fetch_tag_names(timeout):
    raw = _fetch_text(
        TAG_NAMES_URL,
        timeout,
    )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Steam tag dictionary returned invalid JSON"
        ) from exc

    if not isinstance(payload, list):
        raise RuntimeError(
            "Steam tag dictionary returned invalid data"
        )

    result = {}

    for entry in payload:
        if not isinstance(entry, dict):
            continue

        tag_id = entry.get("tagid")
        name = entry.get("name")

        if (
            isinstance(tag_id, int)
            and not isinstance(tag_id, bool)
            and tag_id > 0
            and isinstance(name, str)
            and name.strip()
        ):
            result[tag_id] = name.strip()

    if not result:
        raise RuntimeError(
            "Steam tag dictionary is empty"
        )

    return result


def _extract_tags(item, tag_names):
    raw_tags = item.get("tags")

    if not isinstance(raw_tags, list):
        return []

    result = []

    for entry in raw_tags:
        if not isinstance(entry, dict):
            continue

        tag_id = entry.get("tagid")

        if (
            not isinstance(tag_id, int)
            or isinstance(tag_id, bool)
            or tag_id <= 0
        ):
            continue

        name = tag_names.get(tag_id)

        if name is not None:
            result.append(name)

    return result


def _parse_chart(payload, tag_names):
    if not isinstance(payload, dict):
        raise RuntimeError(
            "Steam Most Played payload is invalid"
        )

    if not isinstance(tag_names, dict):
        raise RuntimeError(
            "Steam tag dictionary is invalid"
        )

    response = payload.get("response")

    if not isinstance(response, dict):
        raise RuntimeError(
            "Steam Most Played response is missing"
        )

    ranks = response.get("ranks")

    if not isinstance(ranks, list):
        raise RuntimeError(
            "Steam Most Played ranks are missing"
        )

    if len(ranks) != CHART_SIZE:
        raise RuntimeError(
            "Steam Most Played chart is incomplete: "
            f"expected {CHART_SIZE} items, got {len(ranks)}"
        )

    result = []

    seen_positions = set()
    seen_app_ids = set()

    for entry in ranks:
        if not isinstance(entry, dict):
            raise RuntimeError(
                "Steam Most Played contains an invalid item"
            )

        position = entry.get("rank")
        app_id = entry.get("appid")
        current_players = entry.get(
            "concurrent_in_game"
        )
        peak_today = entry.get(
            "peak_in_game"
        )

        item = entry.get("item")

        if (
            not isinstance(position, int)
            or isinstance(position, bool)
            or position < 1
            or position > CHART_SIZE
        ):
            raise RuntimeError(
                "Steam Most Played contains "
                "an invalid position"
            )

        if position in seen_positions:
            raise RuntimeError(
                "Steam Most Played contains "
                "duplicate positions"
            )

        if (
            not isinstance(app_id, int)
            or isinstance(app_id, bool)
            or app_id <= 0
        ):
            raise RuntimeError(
                f"Steam Most Played item #{position} "
                "has an invalid app id"
            )

        if app_id in seen_app_ids:
            raise RuntimeError(
                "Steam Most Played contains "
                "duplicate app ids"
            )

        if not isinstance(item, dict):
            raise RuntimeError(
                f"Steam Most Played item #{position} "
                "has invalid game data"
            )

        title = item.get("name")

        if (
            not isinstance(title, str)
            or not title.strip()
        ):
            raise RuntimeError(
                f"Steam Most Played item #{position} "
                "has no title"
            )

        if (
            not isinstance(current_players, int)
            or isinstance(current_players, bool)
            or current_players < 0
        ):
            raise RuntimeError(
                f"Steam Most Played item #{position} "
                "has an invalid current player count"
            )

        if (
            not isinstance(peak_today, int)
            or isinstance(peak_today, bool)
            or peak_today < 0
        ):
            raise RuntimeError(
                f"Steam Most Played item #{position} "
                "has an invalid daily peak"
            )

        tags = _extract_tags(
            item,
            tag_names,
        )

        seen_positions.add(position)
        seen_app_ids.add(app_id)

        result.append(
            {
                "position": position,
                "title": title.strip(),
                "steam_app_id": app_id,
                "current_players": current_players,
                "peak_today": peak_today,
                "tags": tags,
                "cover_url": steam_cover_url(app_id, item.get("assets")),
                "year": steam_release_year(item),
            }
        )

    result.sort(
        key=lambda item: item["position"]
    )

    positions = [
        item["position"]
        for item in result
    ]

    expected_positions = list(
        range(1, CHART_SIZE + 1)
    )

    if positions != expected_positions:
        raise RuntimeError(
            "Steam Most Played positions are incomplete"
        )

    player_counts = [
        item["current_players"]
        for item in result
    ]

    if player_counts != sorted(
        player_counts,
        reverse=True,
    ):
        raise RuntimeError(
            "Steam Most Played chart is not "
            "sorted by current players"
        )

    return result


def _fetch_chart(limit, timeout):
    payload = _fetch_payload(
        timeout=timeout,
    )

    tag_names = _fetch_tag_names(
        timeout=timeout,
    )

    chart = _parse_chart(
        payload,
        tag_names,
    )

    if limit is not None:
        return chart[:limit]

    return chart


def get_steam_players_chart(
    limit=None,
    timeout=30,
):
    if limit is not None:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
        ):
            raise ValueError(
                "limit must be a positive integer or None"
            )

    if (
        isinstance(timeout, bool)
        or not isinstance(
            timeout,
            (int, float),
        )
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError(
            "timeout must be a positive finite number"
        )

    return _fetch_chart(
        limit=limit,
        timeout=timeout,
    )