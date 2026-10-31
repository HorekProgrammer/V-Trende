"""Сбор частоты запросов Wordstat для всех объектов чартов недели.

    python -m parser.wordstat_batch                     # показать результат, ничего не сохраняя
    python -m parser.wordstat_batch --save              # сохранить (бэкенд или data/outbox/)
    python -m parser.wordstat_batch --week 2026-10-19 --max 20

Запускается после загрузки чартов недели в базу: список уникальных объектов
берётся напрямую из успешно сохранённых позиций, поэтому пересчёт рейтинга для
этого не нужен. Объекты, для которых значение за неделю уже есть, пропускаются,
поэтому прерванный запуск можно просто повторить.

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
NETWORK_RETRIES = 3
RETRY_DELAY_SECONDS = 3

_PENDING_TRENDS = """
WITH current_trends AS (
    SELECT DISTINCT trend_id
    FROM v_chart_entries
    WHERE week_start = %s
)
SELECT t.category, t.title, t.subtitle, t.match_key, t.search_query
FROM current_trends w
JOIN trends t ON t.id = w.trend_id
LEFT JOIN trend_search_stats s ON s.trend_id = t.id AND s.week_start = %s
WHERE s.trend_id IS NULL
  AND t.category <> 'games'
ORDER BY t.category, t.title, t.id
"""


def pending_trends(conn, week: date) -> list[dict]:
    rows = conn.execute(_PENDING_TRENDS, (week, week)).fetchall()
    return [
        {
            "category": category,
            "match_key": match_key,
            "query": (search_query or "").strip() or default_search_query(category, title, subtitle),
        }
        for category, title, subtitle, match_key, search_query in rows
    ]


def collect(
    trends: list[dict],
    *,
    fetch=get_wordstat_count,
    delay: float = DELAY_SECONDS,
    network_retries: int = NETWORK_RETRIES,
    retry_delay: float = RETRY_DELAY_SECONDS,
    log=print,
) -> tuple[list[dict], str | None]:
    """Возвращает (значения, причина остановки или None)."""
    entries = []
    for index, trend in enumerate(trends):
        if index and delay:
            sleep(delay)
        for attempt in range(network_retries + 1):
            try:
                count = fetch(trend["query"])
                break
            except ValueError as error:
                if "отклонил" in str(error):
                    # Wordstat не принял именно эту фразу: пропускаем объект.
                    log(f"[пропуск] {trend['query']!r}: {error}")
                    count = None
                    break
                return entries, str(error)
            except RuntimeError as error:
                transient = "ошибка сети или таймаут" in str(error).lower()
                if not transient or attempt == network_retries:
                    return entries, str(error)
                log(
                    f"[повтор {attempt + 1}/{network_retries}] "
                    f"{trend['query']!r}: {error}"
                )
                if retry_delay:
                    sleep(retry_delay)
        if count is None:
            continue
        entries.append({**trend, "search_count": count})
    return entries, None


def build_payload(week: date, entries: list[dict], *, publish: bool = True) -> dict:
    payload = {
        "type": "search_stats",
        "week_start": week.isoformat(),
        "collected_at": datetime.now(MOSCOW_TZ).isoformat(timespec="seconds"),
        "entries": entries,
    }
    if not publish:
        payload["publish"] = False
    return payload


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Собрать Wordstat для всех объектов чартов недели")
    cli.add_argument("--week", type=date.fromisoformat, help="Понедельник недели; по умолчанию текущая")
    cli.add_argument("--max", type=int, help="Не больше N запросов (для проверки)")
    cli.add_argument("--save", action="store_true", help="Сохранить результат")
    cli.add_argument("--defer-publish", action="store_true",
                     help="Сохранить Wordstat без публикации нового рейтинга")
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
        log(f"За неделю {week} собирать нечего: чартов нет или Wordstat уже собран.")
        if args.save:
            # Пустой пакет завершает конвейер и пересчитывает рейтинг даже тогда,
            # когда все значения Wordstat уже были собраны предыдущим запуском.
            try:
                log(save_payload(build_payload(week, [], publish=not args.defer_publish)))
            except SaveError as error:
                log(f"Ошибка финального пересчёта: {error}")
                return 1
        return 0

    log(f"Запросов к Wordstat: {len(trends)} (≈{len(trends) * DELAY_SECONDS / 60:.0f} мин)")
    entries, stopped = collect(trends, log=log)
    if stopped:
        log(f"Сбор остановлен: {stopped}")

    payload = build_payload(week, entries, publish=not args.defer_publish)
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
