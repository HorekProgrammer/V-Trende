"""Queries and response mapping for the public API."""

from collections import defaultdict

CATEGORY_LABELS = {
    "music": "Музыка",
    "movies": "Фильмы",
    "games": "Игры",
    "streamers": "Стримеры",
}

CARD_COLUMNS = """
    week_start, category, rank, score, source_score, wordstat_score,
    trend_id, title, subtitle, genre,
    prev_rank, peak_rank, weeks_in_top, first_seen_week, is_new, search_count,
    cover_url
"""


def _rows(cursor) -> list[dict]:
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _row(cursor) -> dict | None:
    columns = [column.name for column in cursor.description]
    value = cursor.fetchone()
    return dict(zip(columns, value)) if value is not None else None


def weeks(conn) -> list[str]:
    """Недели, за которые опубликован рейтинг, от новой к старой."""
    rows = conn.execute(
        "SELECT DISTINCT week_start FROM mv_category_rank ORDER BY week_start DESC"
    ).fetchall()
    return [row[0].isoformat() for row in rows]


def week_exists(conn, week) -> bool:
    return conn.execute(
        "SELECT 1 FROM mv_category_rank WHERE week_start = %s LIMIT 1", (week,)
    ).fetchone() is not None


def _top_source(week) -> tuple[str, list]:
    """Откуда брать топ категорий: последняя неделя или выбранная."""
    if week is None:
        return "v_category_top_latest", []
    return "(SELECT * FROM v_category_top WHERE week_start = %s) AS top_week", [week]


def _feed_source(week) -> tuple[str, list]:
    """Главная лента: для выбранной недели порядок считается так же, как в v_main_feed."""
    if week is None:
        return "v_main_feed", []
    return (
        """(SELECT t.*,
                   (row_number() OVER (
                       ORDER BY t.score DESC, t.search_count DESC NULLS LAST,
                                t.rank, t.category, t.trend_id
                   ))::integer AS feed_rank
            FROM v_category_top t
            WHERE t.week_start = %s) AS feed_week""",
        [week],
    )


def card(record: dict) -> dict:
    return {
        "key": str(record["trend_id"]),
        "sphere": record["category"],
        "categoryLabel": CATEGORY_LABELS[record["category"]],
        "weekStart": record["week_start"].isoformat(),
        "rank": record["rank"],
        "score": float(record["score"]),
        "sourceScore": float(record["source_score"]),
        "wordstatScore": float(record["wordstat_score"]),
        "prevRank": record["prev_rank"],
        "peak": record["peak_rank"],
        "weeks": record["weeks_in_top"],
        "title": record["title"],
        "subtitle": record["subtitle"] or "",
        "genre": record["genre"],
        "isNew": record["is_new"],
        "searchCount": record["search_count"],
        "cover": record["cover_url"],
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


def feed(conn, week=None) -> dict:
    top_source, top_params = _top_source(week)
    feed_source, feed_params = _feed_source(week)
    global_items = _rows(conn.execute(
        f"SELECT {CARD_COLUMNS} FROM {feed_source} ORDER BY feed_rank LIMIT 10",
        feed_params,
    ))
    new_items = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM {top_source}
            WHERE is_new
            ORDER BY search_count DESC NULLS LAST, rank
            LIMIT 8""",
        top_params,
    ))
    legendary = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM {top_source}
            ORDER BY weeks_in_top DESC, rank
            LIMIT 8""",
        top_params,
    ))
    top = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM {top_source}
            WHERE rank <= 3
            ORDER BY category, rank""",
        top_params,
    ))
    grouped = defaultdict(list)
    for row in top:
        grouped[row["category"]].append(card(row))
    chosen_week = None
    for rows in (global_items, top, new_items, legendary):
        if rows:
            chosen_week = rows[0]["week_start"].isoformat()
            break
    return {
        "weekStart": chosen_week,
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


def main_trends(conn, limit: int, offset: int, week=None) -> dict:
    feed_source, feed_params = _feed_source(week)
    rows = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM {feed_source}
            ORDER BY feed_rank LIMIT %s OFFSET %s""",
        [*feed_params, limit, offset],
    ))
    return {"items": [card(row) for row in rows], "limit": limit, "offset": offset}


def category_trends(
    conn,
    category: str,
    sort: str,
    genres: list[str],
    limit: int = 100,
    offset: int = 0,
    week=None,
) -> dict:
    order = {
        "popular": "rank",
        "new": "weeks_in_top, rank",
        "rising": "rank_change DESC NULLS LAST, rank",
    }[sort]
    top_source, top_params = _top_source(week)
    params: list[object] = [*top_params, category]
    genre_filter = ""
    if genres:
        genre_filter = " AND genre = ANY(%s)"
        params.append(genres)
    rows = _rows(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM {top_source}
            WHERE category = %s{genre_filter}
            ORDER BY {order} LIMIT %s OFFSET %s""",
        [*params, limit, offset],
    ))
    chosen_week = rows[0]["week_start"].isoformat() if rows else (str(week) if week else None)
    return {
        "weekStart": chosen_week,
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
        """SELECT week_start, category_rank, score, source_score, wordstat_score, search_count
           FROM v_trend_history
           WHERE trend_id = %s
           ORDER BY week_start""",
        (trend_id,),
    ))
    return [
        {
            "weekStart": point["week_start"].isoformat(),
            "rank": point["category_rank"],
            "score": None if point["score"] is None else float(point["score"]),
            "sourceScore": None if point["source_score"] is None else float(point["source_score"]),
            "wordstatScore": None if point["wordstat_score"] is None else float(point["wordstat_score"]),
            "searchCount": point["search_count"],
        }
        for point in history
    ]