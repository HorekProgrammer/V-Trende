"""Collect Whatstat's seven-day Twitch audience and match it to charted games."""

import argparse
import sys
from datetime import date, datetime

from database.db import DatabaseConfigError, connect
from parser.common import SaveError, normalize_text, save_payload, week_start
from parser.common.upload import MOSCOW_TZ
from parser.whatstat_categories import get_whatstat_categories


ALIASES = {
    "counter strike": "counter strike 2",
    "gta v": "grand theft auto v",
    "playerunknown s battlegrounds": "pubg battlegrounds",
}


def game_keys(conn, week: date) -> dict[str, str]:
    rows = conn.execute(
        """SELECT DISTINCT t.match_key, t.title
           FROM v_chart_entries e
           JOIN trends t ON t.id = e.trend_id
           WHERE e.category = 'games' AND e.week_start = %s""",
        (week,),
    ).fetchall()
    return {match_key: title for match_key, title in rows}


def match_categories(categories: list[dict], games: dict[str, str]) -> tuple[list[dict], list[dict]]:
    by_normalized_title = {normalize_text(title): key for key, title in games.items()}
    matched, unmatched = [], []
    seen_keys = set()
    for category in categories:
        source_key = normalize_text(category["title"])
        target_key = ALIASES.get(source_key, source_key)
        match_key = by_normalized_title.get(target_key)
        if match_key is None or match_key in seen_keys:
            unmatched.append(category)
            continue
        seen_keys.add(match_key)
        matched.append({
            "match_key": match_key,
            "source_title": category["title"],
            "source_category_id": category["category_id"],
            "source_url": category["url"],
            "position": category["position"],
            "average_viewers": category["average_viewers"],
        })
    return matched, unmatched


def build_payload(week: date, entries: list[dict], *, publish: bool = False) -> dict:
    payload = {
        "type": "game_audience_stats",
        "week_start": week.isoformat(),
        "collected_at": datetime.now(MOSCOW_TZ).isoformat(timespec="seconds"),
        "entries": entries,
        "publish": publish,
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Собрать аудиторию игровых категорий Whatstat")
    cli.add_argument("--week", type=date.fromisoformat)
    cli.add_argument("--pages", type=int, default=10)
    cli.add_argument("--save", action="store_true")
    cli.add_argument("--publish", action="store_true")
    args = cli.parse_args(argv)
    week = args.week or week_start()
    if week.weekday() != 0:
        cli.error("--week должен быть понедельником")
    try:
        with connect() as conn:
            games = game_keys(conn, week)
        categories = get_whatstat_categories(pages=args.pages)
        matched, unmatched = match_categories(categories, games)
        if not matched:
            raise RuntimeError("ни одна категория Whatstat не сопоставилась с играми недели")
        print(
            f"Whatstat: получено {len(categories)}, сопоставлено {len(matched)}, "
            f"без совпадения {len(unmatched)}",
            file=sys.stderr,
        )
        if args.save:
            print(save_payload(build_payload(week, matched, publish=args.publish)), file=sys.stderr)
        return 0
    except (DatabaseConfigError, RuntimeError, SaveError, ValueError) as error:
        print(f"Whatstat: ошибка: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
