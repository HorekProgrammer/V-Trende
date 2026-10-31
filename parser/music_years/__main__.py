import argparse
import sys

from database.db import DatabaseConfigError, connect

from .deepseek_years import base_key, find_years

_PENDING_TOP = """
SELECT DISTINCT t.id, t.title, t.subtitle, t.match_key
FROM v_category_top_latest v
JOIN trends t ON t.id = v.trend_id
WHERE v.category = 'music'
  AND t.year IS NULL
ORDER BY t.title, t.id
"""

_KNOWN_YEARS = """
SELECT title, subtitle, year
FROM trends
WHERE category = 'music' AND year IS NOT NULL
"""

_PENDING_ALL = """
SELECT DISTINCT t.id, t.title, t.subtitle, t.match_key
FROM v_chart_entries e
JOIN trends t ON t.id = e.trend_id
WHERE e.category = 'music'
  AND e.week_start = (SELECT MAX(week_start) FROM v_chart_entries WHERE category = 'music')
  AND t.year IS NULL
ORDER BY t.title, t.id
"""


def pending_tracks(conn, *, all_charts: bool = False) -> list[dict]:
    query = _PENDING_ALL if all_charts else _PENDING_TOP
    return [
        {"id": trend_id, "key": match_key, "title": title, "artists": subtitle or ""}
        for trend_id, title, subtitle, match_key in conn.execute(query).fetchall()
    ]


def known_years(conn) -> dict[str, int]:
    result = {}
    for title, subtitle, year in conn.execute(_KNOWN_YEARS).fetchall():
        key = base_key(title, subtitle or "")
        if key and key not in result:
            result[key] = year
    return result


def save_years(conn, tracks: list[dict], years: dict[str, int]) -> int:
    saved = 0
    for track in tracks:
        year = years.get(track["key"])
        if year:
            cursor = conn.execute(
                "UPDATE trends SET year = %s WHERE id = %s AND year IS NULL",
                (year, track["id"]),
            )
            saved += cursor.rowcount
    return saved


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Найти год у треков недели без года (DeepSeek с поиском)")
    cli.add_argument("--save", action="store_true", help="Записать найденные годы в базу")
    cli.add_argument("--max", type=int, help="Обработать не больше N треков")
    cli.add_argument("--all-charts", action="store_true",
                     help="Все треки музыкальных чартов недели, а не только топ на сайте")
    cli.add_argument("--recheck", action="store_true",
                     help="Заново искать треки, для которых год ещё не нашёлся")
    args = cli.parse_args(argv)

    try:
        with connect() as conn:
            tracks = pending_tracks(conn, all_charts=args.all_charts)
            if args.max is not None:
                tracks = tracks[:max(args.max, 0)]
            print(f"Треков без года: {len(tracks)}", file=sys.stderr)
            if not tracks:
                return 0
            years = find_years(tracks, known=known_years(conn), recheck=args.recheck)
            for track in tracks:
                year = years.get(track["key"])
                print(f"  {track['artists']} — {track['title']}: {year or 'не найден'}", file=sys.stderr)
            if args.save:
                saved = save_years(conn, tracks, years)
                print(f"Записано в базу: {saved}", file=sys.stderr)
            else:
                print("Ничего не записано (нужен --save)", file=sys.stderr)
    except (DatabaseConfigError, RuntimeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
