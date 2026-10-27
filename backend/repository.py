"""Queries and response mapping for the public API."""

from collections import defaultdict

CATEGORY_LABELS = {
    "music": "Музыка",
    "movies": "Фильмы",
    "games": "Игры",
    "streamers": "Стримеры",
}

CARD_COLUMNS = """
    week_start, category, rank, trend_id, title, subtitle, genre,
    prev_rank, peak_rank, weeks_in_top, first_seen_week, is_new, search_count
"""


def _rows(cursor) -> list[dict]:
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _row(cursor) -> dict | None:
    columns = [column.name for column in cursor.description]
    value = cursor.fetchone()
    return dict(zip(columns, value)) if value is not None else None


def card(record: dict) -> dict:
    return {
        "key": str(record["trend_id"]),
        "sphere": record["category"],
        "categoryLabel": CATEGORY_LABELS[record["category"]],
        "weekStart": record["week_start"].isoformat(),
        "rank": record["rank"],
        "prevRank": record["prev_rank"],
        "peak": record["peak_rank"],
        "weeks": record["weeks_in_top"],
        "title": record["title"],
        "subtitle": record["subtitle"] or "",
        "genre": record["genre"],
        "isNew": record["is_new"],
        "searchCount": record["search_count"],
    }


def categories(conn) -> list[dict]:
    rows = _rows(conn.execute(
        "SELECT category, name FROM genres ORDER BY category, id"
    ))
    genres = defaultdict(list)
    for row in rows:
        genres[row["category"]].append(row["name"])
    return [
        {"id": key, "label": label, "genres": genres[key]}
        for key, label in CATEGORY_LABELS.items()
    ]


def feed(conn) -> dict:
    global_items = _rows(conn.execute(
        f"SELECT {CARD_COLUMNS} FROM v_main_feed ORDER BY feed_rank LIMIT 10"
    ))
    new_items = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM v_category_top_latest
            WHERE is_new
            ORDER BY search_count DESC NULLS LAST, rank
            LIMIT 8"""
    ))
    legendary = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM v_category_top_latest
            ORDER BY weeks_in_top DESC, rank
            LIMIT 8"""
    ))
    top = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM v_category_top_latest
            WHERE rank <= 3
            ORDER BY category, rank"""
    ))
    grouped = defaultdict(list)
    for row in top:
        grouped[row["category"]].append(card(row))
    return {
        "global": [card(row) for row in global_items],
        "new": [card(row) for row in new_items],
        "legendary": [card(row) for row in legendary],
        "top3": [
            {
                "category": {"id": key, "label": label},
                "items": grouped[key],
            }
            for key, label in CATEGORY_LABELS.items()
        ],
    }


def main_trends(conn, limit: int, offset: int) -> dict:
    rows = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM v_main_feed
            ORDER BY feed_rank LIMIT %s OFFSET %s""",
        (limit, offset),
    ))
    return {"items": [card(row) for row in rows], "limit": limit, "offset": offset}


def category_trends(
    conn,
    category: str,
    sort: str,
    genres: list[str],
    limit: int = 100,
    offset: int = 0,
) -> dict:
    order = {
        "popular": "rank",
        "new": "first_seen_week DESC, rank",
        "rising": "rank_change DESC NULLS LAST, rank",
    }[sort]
    params: list[object] = [category]
    genre_filter = ""
    if genres:
        genre_filter = " AND genre = ANY(%s)"
        params.append(genres)
    rows = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM v_category_top_latest
            WHERE category = %s{genre_filter}
            ORDER BY {order} LIMIT %s OFFSET %s""",
        [*params, limit, offset],
    ))
    week = rows[0]["week_start"].isoformat() if rows else None
    return {
        "weekStart": week,
        "items": [card(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


def trend(conn, trend_id: int) -> dict | None:
    record = _row(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM v_category_top
            WHERE trend_id = %s
            ORDER BY week_start DESC
            LIMIT 1""",
        (trend_id,),
    ))
    if record is None:
        return None
    result = card(record)
    result["history"] = trend_history(conn, trend_id) or []
    return result


def trend_history(conn, trend_id: int) -> list[dict] | None:
    exists = conn.execute("SELECT 1 FROM trends WHERE id = %s", (trend_id,)).fetchone()
    if exists is None:
        return None
    history = _rows(conn.execute(
        """SELECT week_start, category_rank, search_count
           FROM v_trend_history
           WHERE trend_id = %s
           ORDER BY week_start""",
        (trend_id,),
    ))
    return [
        {
            "weekStart": point["week_start"].isoformat(),
            "rank": point["category_rank"],
            "searchCount": point["search_count"],
        }
        for point in history
    ]
