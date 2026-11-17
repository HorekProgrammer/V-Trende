"""Queries and response mapping for the public API."""

from collections import defaultdict

CATEGORY_LABELS = {
    "music": "Музыка",
    "movies": "Фильмы",
    "games": "Игры",
    "streamers": "Стримеры",
}

SOURCE_LABELS = {
    "yandex_music": "Яндекс Музыка",
    "vk": "VK Музыка",
    "zvuk": "Звук",
    "apple_music": "Apple Music",
    "shazam": "Shazam",
    "kion": "KION Музыка",
    "steam": "Steam",
    "epic": "Epic Games",
    "kinopoisk": "Кинопоиск",
}

CARD_COLUMNS = """
    week_start, category, rank, score, source_score, wordstat_score,
    trend_id, title, subtitle, genre, trend_genre_names(trend_id) AS genres,
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
        "genres": list(record.get("genres") or ([record["genre"]] if record["genre"] else [])),
        "isNew": record["is_new"],
        "isBack": not record["is_new"] and record["prev_rank"] is None,
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


def sitemap_trend_ids(conn) -> list[int]:
    """Trend pages that exist in at least one published weekly ranking."""
    return [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT trend_id FROM mv_category_rank ORDER BY trend_id"
        ).fetchall()
    ]


def published_trend_exists(conn, trend_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM v_category_top WHERE trend_id = %s LIMIT 1",
        (trend_id,),
    ).fetchone() is not None


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
        genre_filter = " AND trend_genre_names(trend_id) && %s"
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


def trend(conn, trend_id: int, week=None) -> dict | None:
    latest_record = _row(conn.execute(
        f"""SELECT {CARD_COLUMNS} FROM v_category_top
            WHERE trend_id = %s
            ORDER BY week_start DESC
            LIMIT 1""",
        (trend_id,),
    ))
    if latest_record is None:
        return None
    history = trend_history(conn, trend_id) or []

    if week is None:
        record = latest_record
    else:
        selected_week = week.isoformat()
        point_index = next(
            (index for index, point in enumerate(history) if point["weekStart"] == selected_week),
            None,
        )
        if point_index is None:
            return None
        point = history[point_index]
        record = _row(conn.execute(
            f"""SELECT {CARD_COLUMNS} FROM v_category_top
                WHERE trend_id = %s AND week_start = %s
                LIMIT 1""",
            (trend_id, week),
        ))
        if record is None:
            return None

    result = card(record)
    result["scoreBreakdown"] = score_breakdown(conn, record)
    result["history"] = history
    return result


def score_breakdown(conn, record: dict) -> dict:
    """Return the exact normalized inputs used for the selected weekly score."""
    category = record["category"]
    week_start = record["week_start"]
    trend_id = record["trend_id"]
    extra_score = round(float(record["wordstat_score"]), 2)

    if category == "games":
        extra_row = _row(conn.execute(
            """WITH ranked AS (
                   SELECT trend_id,
                          RANK() OVER (ORDER BY average_viewers DESC) AS position
                   FROM game_audience_stats
                   WHERE week_start = %s
               )
               SELECT position FROM ranked WHERE trend_id = %s""",
            (week_start, trend_id),
        ))
        auxiliary = {
            "label": "Whatstat",
            "position": extra_row["position"] if extra_row else None,
            "value": extra_score,
        }
    else:
        extra_row = _row(conn.execute(
            """WITH ranked AS (
                   SELECT s.trend_id,
                          RANK() OVER (ORDER BY s.search_count DESC) AS position
                   FROM trend_search_stats s
                   JOIN trends t ON t.id = s.trend_id
                   WHERE s.week_start = %s AND t.category = %s
               )
               SELECT position FROM ranked WHERE trend_id = %s""",
            (week_start, category, trend_id),
        ))
        auxiliary = {
            "label": "Wordstat",
            "position": extra_row["position"] if extra_row else None,
            "value": extra_score,
        }

    if category == "streamers":
        row = _row(conn.execute(
            """WITH weekly AS (
                   SELECT s.*,
                          PERCENT_RANK() OVER (ORDER BY hours_watched) AS hours_watched_score,
                          PERCENT_RANK() OVER (ORDER BY average_viewers) AS average_viewers_score,
                          PERCENT_RANK() OVER (ORDER BY peak_viewers) AS peak_viewers_score,
                          PERCENT_RANK() OVER (ORDER BY followers_gained) AS followers_gained_score,
                          PERCENT_RANK() OVER (ORDER BY followers_per_hour) AS followers_per_hour_score,
                          PERCENT_RANK() OVER (ORDER BY hours_streamed) AS hours_streamed_score,
                          PERCENT_RANK() OVER (ORDER BY total_followers) AS total_followers_score,
                          RANK() OVER (ORDER BY hours_watched DESC) AS hours_watched_rank,
                          RANK() OVER (ORDER BY average_viewers DESC) AS average_viewers_rank,
                          RANK() OVER (ORDER BY peak_viewers DESC) AS peak_viewers_rank,
                          RANK() OVER (ORDER BY followers_gained DESC) AS followers_gained_rank,
                          RANK() OVER (ORDER BY followers_per_hour DESC) AS followers_per_hour_rank,
                          RANK() OVER (ORDER BY hours_streamed DESC) AS hours_streamed_rank,
                          RANK() OVER (ORDER BY total_followers DESC) AS total_followers_rank
                   FROM twitch_weekly_stats s
                   WHERE week_start = %s
               )
               SELECT * FROM weekly WHERE trend_id = %s""",
            (week_start, trend_id),
        ))
        metrics = (
            ("Часы просмотра", "hours_watched_score", "hours_watched_rank", 0.30),
            ("Средние зрители", "average_viewers_score", "average_viewers_rank", 0.20),
            ("Новые подписчики", "followers_gained_score", "followers_gained_rank", 0.20),
            ("Пиковые зрители", "peak_viewers_score", "peak_viewers_rank", 0.10),
            ("Подписчики за час", "followers_per_hour_score", "followers_per_hour_rank", 0.10),
            ("Часы в эфире", "hours_streamed_score", "hours_streamed_rank", 0.05),
            ("Всего подписчиков", "total_followers_score", "total_followers_rank", 0.05),
        )
        return {
            "kind": "streamers",
            "auxiliary": auxiliary,
            "components": [
                {
                    "label": label,
                    "position": row[rank_column],
                    "value": round(float(row[score_column]) * 100, 2),
                    "weight": weight,
                }
                for label, score_column, rank_column, weight in metrics
            ] if row else [],
        }

    rows = _rows(conn.execute(
        """WITH positions AS (
               SELECT e.*,
                      MAX(e.position) OVER (PARTITION BY e.chart_id, e.week_start) AS chart_size,
                      COALESCE(w.weight, 1.0) AS chart_weight
               FROM v_chart_entries e
               LEFT JOIN chart_weights w ON w.source = e.source AND w.name = e.chart_name
               WHERE e.week_start = %s
           )
           SELECT source, chart_name, position, chart_weight,
                  CASE WHEN chart_size <= 1 THEN 100.0
                       ELSE (1.0 - (position - 1)::NUMERIC / (chart_size - 1)) * 100
                  END AS normalized_score
           FROM positions
           WHERE trend_id = %s
           ORDER BY chart_weight DESC, source, chart_name""",
        (week_start, trend_id),
    ))
    return {
        "kind": category,
        "auxiliary": auxiliary,
        "components": [
            {
                "label": (
                    SOURCE_LABELS.get(row["source"], row["source"])
                    if category == "music"
                    else f"{SOURCE_LABELS.get(row['source'], row['source'])} — {row['chart_name']}"
                ),
                "position": row["position"],
                "value": round(float(row["normalized_score"]), 2),
                "weight": float(row["chart_weight"]),
            }
            for row in rows
        ],
    }


def trend_history(conn, trend_id: int) -> list[dict] | None:
    exists = conn.execute("SELECT 1 FROM trends WHERE id = %s", (trend_id,)).fetchone()
    if exists is None:
        return None
    history = _rows(conn.execute(
        """WITH target AS (
               SELECT id, category FROM trends WHERE id = %s
           ), history AS (
               SELECT h.* FROM v_trend_history h
               JOIN target t ON t.id = h.trend_id
           ), weeks AS (
               SELECT DISTINCT r.week_start
               FROM mv_category_rank r
               JOIN target t ON t.category = r.category
               WHERE r.week_start >= (
                   SELECT MIN(week_start) FROM history WHERE category_rank IS NOT NULL
               )
           )
           SELECT w.week_start, h.category_rank, h.score, h.source_score,
                  h.wordstat_score, h.search_count
           FROM weeks w
           LEFT JOIN history h ON h.week_start = w.week_start
           ORDER BY w.week_start""",
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
