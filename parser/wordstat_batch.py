"""Сбор частоты запросов Wordstat для объектов топов недели.

    python -m parser.wordstat_batch                     # показать результат, ничего не сохраняя
    python -m parser.wordstat_batch --save              # сохранить (бэкенд или data/outbox/)
    python -m parser.wordstat_batch --week 2026-10-19 --max 20

Запускается после загрузки чартов недели в базу: список объектов берётся из
mv_category_rank (не больше 300 — топы всех категорий). Объекты, для которых
значение за неделю уже есть, пропускаются, поэтому прерванный запуск можно
просто повторить.

Если Wordstat перестал отвечать (истекла сессия, CAPTCHA, ограничение запросов),
сбор останавливается, но уже полученные значения сохраняются; код выхода — 1.
"""

import argparse
import json
import sys
from datetime import date, datetime
from time import sleep

from database.db import DatabaseConfigError, connect
from parser.common import SaveError, default_search_query, save_payload, week_start
from parser.common.upload import MOSCOW_TZ
from parser.wordstat import get_wordstat_count

DELAY_SECONDS = 1.5

_PENDING_TRENDS = """
SELECT t.category, t.title, t.subtitle, t.match_key, t.search_query
FROM mv_category_rank w
JOIN trends t ON t.id = w.trend_id
LEFT JOIN trend_search_stats s ON s.trend_id = t.id AND s.week_start = w.week_start
WHERE w.week_start = %s AND s.trend_id IS NULL
ORDER BY w.category, w.rank
"""


def pending_trends(conn, week: date) -> list[dict]:
    rows = conn.execute(_PENDING_TRENDS, (week,)).fetchall()
    return [
        {
            "category": category,
            "match_key": match_key,
            "query": (search_query or "").strip() or default_search_query(category, title, subtitle),
        }
        for category, title, subtitle, match_key, search_query in rows
    ]


def collect(trends: list[dict], *, fetch=get_wordstat_count, delay: float = DELAY_SECONDS,
            log=print) -> tuple[list[dict], str | None]:
    """Возвращает (значения, причина остановки или None)."""
    entries = []
    for index, trend in enumerate(trends):
        if index and delay:
            sleep(delay)
        try:
            count = fetch(trend["query"])
        except ValueError as error:
            if "отклонил" in str(error):
                # Wordstat не принял именно эту фразу: пропускаем объект.
                log(f"[пропуск] {trend['query']!r}: {error}")
                continue
            return entries, str(error)
        except RuntimeError as error:
            return entries, str(error)
        entries.append({**trend, "search_count": count})
    return entries, None


def build_payload(week: date, entries: list[dict]) -> dict:
    return {
        "type": "search_stats",
        "week_start": week.isoformat(),
        "collected_at": datetime.now(MOSCOW_TZ).isoformat(timespec="seconds"),
        "entries": entries,
    }


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Собрать Wordstat для объектов топов недели")
    cli.add_argument("--week", type=date.fromisoformat, help="Понедельник недели; по умолчанию текущая")
    cli.add_argument("--max", type=int, help="Не больше N запросов (для проверки)")
    cli.add_argument("--save", action="store_true", help="Сохранить результат")
    args = cli.parse_args(argv)
    week = args.week or week_start()
    if week.weekday() != 0:
        cli.error("--week должен быть понедельником")

    def log(message):
        print(message, file=sys.stderr, flush=True)

    try:
        with connect() as conn:
            trends = pending_trends(conn, week)
    except DatabaseConfigError as error:
        log(f"Ошибка: {error}")
        return 1
    if args.max is not None:
        trends = trends[:max(args.max, 0)]
    if not trends:
        log(f"За неделю {week} собирать нечего: топов нет или Wordstat уже собран.")
        return 0

    log(f"Запросов к Wordstat: {len(trends)} (≈{len(trends) * DELAY_SECONDS / 60:.0f} мин)")
    entries, stopped = collect(trends, log=log)
    if stopped:
        log(f"Сбор остановлен: {stopped}")

    payload = build_payload(week, entries)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.save and entries:
        try:
            log(save_payload(payload))
        except SaveError as error:
            log(f"Ошибка сохранения: {error}")
            return 1
    log(f"Получено значений: {len(entries)} из {len(trends)}.")
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
