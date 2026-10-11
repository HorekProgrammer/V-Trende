import json
import math
import re
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CHARTS_OVERVIEW_URL = "https://store.steampowered.com/charts/"
TOP_SELLERS_API_URL = (
    "https://api.steampowered.com/"
    "IStoreTopSellersService/GetWeeklyTopSellers/v1/"
)
APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

REGION = "RU"
CHART_SIZE = 100

_WEEKLY_DATE_RE = re.compile(
    r"/charts/topsellers/[A-Z]{2}/(\d{4}-\d{1,2}-\d{1,2})",
    re.IGNORECASE,
)


def _fetch_text(url, timeout, origin=None):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }

    if origin is not None:
        headers["Origin"] = origin

    request = Request(
        url,
        headers=headers,
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode(
                "utf-8",
                errors="replace",
            )
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Failed to fetch Steam data: {exc}"
        ) from exc


def _extract_latest_weekly_date(html):
    dates = _WEEKLY_DATE_RE.findall(html)

    if not dates:
        raise RuntimeError(
            "Steam latest weekly chart date was not found"
        )

    def date_key(value):
        year, month, day = map(int, value.split("-"))
        return year, month, day

    return max(set(dates), key=date_key)


def _date_to_timestamp(value):
    try:
        year, month, day = map(int, value.split("-"))

        date = datetime(
            year,
            month,
            day,
            tzinfo=timezone.utc,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid Steam weekly chart date: {value}"
        ) from exc

    return int(date.timestamp())


def _fetch_app_name(app_id, timeout):
    query = urlencode(
        {
            "appids": app_id,
            "cc": REGION,
            "l": "english",
        }
    )

    raw = _fetch_text(
        f"{APP_DETAILS_URL}?{query}",
        timeout,
    )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Steam app details returned invalid JSON for app {app_id}"
        ) from exc

    entry = payload.get(str(app_id))

    if not isinstance(entry, dict) or entry.get("success") is not True:
        raise RuntimeError(
            f"Steam app details are unavailable for app {app_id}"
        )

    data = entry.get("data")

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Steam app details are missing for app {app_id}"
        )

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        raise RuntimeError(
            f"Steam app name is missing for app {app_id}"
        )

    return name.strip()


def _fetch_weekly_chart_payload(start_date, timeout):
    payload = {
        "country_code": REGION,
        "context": {
            "language": "english",
            "country_code": REGION,
        },
        "data_request": {
            "include_assets": True,
            "include_release": True,
            "include_basic_info": True,
        },
        "start_date": start_date,
        "page_start": 0,
        "page_count": CHART_SIZE,
    }

    query = urlencode(
        {
            "input_json": json.dumps(payload),
        }
    )

    raw = _fetch_text(
        f"{TOP_SELLERS_API_URL}?{query}",
        timeout,
        origin="https://store.steampowered.com",
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Steam weekly chart API returned invalid JSON"
        ) from exc


def _parse_chart(payload, timeout):
    if not isinstance(payload, dict):
        raise RuntimeError(
            "Steam weekly chart response is invalid"
        )

    response = payload.get("response")

    if not isinstance(response, dict):
        raise RuntimeError(
            "Steam weekly chart response is missing"
        )

    ranks = response.get("ranks")

    if not isinstance(ranks, list):
        raise RuntimeError(
            "Steam weekly chart ranks are missing"
        )

    if len(ranks) != CHART_SIZE:
        raise RuntimeError(
            f"Steam chart is incomplete: expected "
            f"{CHART_SIZE} items, got {len(ranks)}"
        )

    result = []
    seen_positions = set()
    seen_app_ids = set()

    for entry in ranks:
        if not isinstance(entry, dict):
            raise RuntimeError(
                "Steam chart contains an invalid item"
            )

        position = entry.get("rank")
        app_id = entry.get("appid")

        if (
            not isinstance(position, int)
            or isinstance(position, bool)
            or position < 1
            or position > CHART_SIZE
        ):
            raise RuntimeError(
                "Steam chart contains an invalid position"
            )

        if position in seen_positions:
            raise RuntimeError(
                "Steam chart contains duplicate positions"
            )

        if (
            not isinstance(app_id, int)
            or isinstance(app_id, bool)
            or app_id <= 0
        ):
            raise RuntimeError(
                f"Steam chart item #{position} "
                "has an invalid app id"
            )

        if app_id in seen_app_ids:
            raise RuntimeError(
                "Steam chart contains duplicate app ids"
            )

        last_week_rank = entry.get("last_week_rank")
        consecutive_weeks = entry.get("consecutive_weeks")

        if last_week_rank is not None:
            if (
                not isinstance(last_week_rank, int)
                or isinstance(last_week_rank, bool)
                or last_week_rank < 1
            ):
                raise RuntimeError(
                    f"Steam chart item #{position} "
                    "has an invalid previous rank"
                )

        if (
            not isinstance(consecutive_weeks, int)
            or isinstance(consecutive_weeks, bool)
            or consecutive_weeks < 1
        ):
            raise RuntimeError(
                f"Steam chart item #{position} "
                "has an invalid weeks count"
            )

        item = entry.get("item")
        title = None

        if isinstance(item, dict):
            name = item.get("name")

            if isinstance(name, str) and name.strip():
                title = name.strip()

        if title is None:
            title = _fetch_app_name(
                app_id,
                timeout,
            )

        seen_positions.add(position)
        seen_app_ids.add(app_id)

        result.append(
            {
                "position": position,
                "title": title,
                "steam_app_id": app_id,
                "rank_last_week": last_week_rank,
                "consecutive_weeks": consecutive_weeks,
            }
        )

    result.sort(key=lambda item: item["position"])

    expected_positions = list(
        range(1, CHART_SIZE + 1)
    )
    actual_positions = [
        item["position"]
        for item in result
    ]

    if actual_positions != expected_positions:
        raise RuntimeError(
            "Steam chart positions are incomplete"
        )

    return result


def _fetch_chart(limit, timeout):
    target_size = (
        CHART_SIZE
        if limit is None
        else min(limit, CHART_SIZE)
    )

    overview_html = _fetch_text(
        CHARTS_OVERVIEW_URL,
        timeout,
    )

    latest_date = _extract_latest_weekly_date(
        overview_html
    )

    start_date = _date_to_timestamp(
        latest_date
    )

    payload = _fetch_weekly_chart_payload(
        start_date,
        timeout,
    )

    chart = _parse_chart(
        payload,
        timeout,
    )

    return chart[:target_size]


def get_steam_chart(limit=None, timeout=30):
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
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError(
            "timeout must be a positive finite number"
        )

    return _fetch_chart(limit, timeout)