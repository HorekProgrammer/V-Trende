"""Еженедельный сбор всех чартов.

    python -m parser.run_all            # собрать и показать сводку, ничего не сохраняя
    python -m parser.run_all --save     # собрать недостающие, Whatstat/Wordstat и рейтинг
    python -m parser.run_all --save --force  # пересобрать все чарты этой недели
    python -m parser.run_all --save --next-week --defer-publish  # воскресная подготовка
    python -m parser.run_all --only steam twitch --save
    python -m parser.run_all --save --skip-wordstat

Падение одного парсера не останавливает остальные; с --save сбой сохраняется
отдельным пакетом, и в базе запуск получает статус failed. Если хотя бы один чарт
не собран или не сохранён, процесс завершается с кодом 1.

При --save успешно собранные за текущую неделю чарты пропускаются. После
недостающих парсеров запускаются Whatstat для игр и Wordstat для остальных
категорий; финальная загрузка атомарно публикует рейтинг для backend и frontend.
"""

import argparse
import sys
from datetime import date, timedelta

from database.db import DatabaseConfigError, connect
from parser.common import CHARTS, SaveError, save_chart, save_chart_failure, week_start


def missing_chart_keys(keys: list[str], week: date | None = None) -> tuple[list[str], list[str]]:
    """Возвращает (нужно собрать, уже успешно собрано) за выбранную неделю."""
    week = week or week_start()
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.source, c.name
               FROM chart_runs r
               JOIN charts c ON c.id = r.chart_id
               WHERE r.week_start = %s AND r.status = 'success'""",
            (week,),
        ).fetchall()
        twitch_metrics_ready = conn.execute(
            "SELECT EXISTS (SELECT 1 FROM twitch_weekly_stats WHERE week_start = %s)",
            (week,),
        ).fetchone()[0]
    completed = set(rows)
    skipped = [
        key for key in keys
        if (CHARTS[key].source, CHARTS[key].name) in completed
        and (key != "twitch" or twitch_metrics_ready)
    ]
    return [key for key in keys if key not in skipped], skipped


def run_wordstat(week: date | None = None, *, publish: bool = True) -> int:
    from parser import wordstat_batch
    args = ["--save"]
    if week is not None:
        args.extend(["--week", week.isoformat()])
    if not publish:
        args.append("--defer-publish")
    return wordstat_batch.main(args)


def run_whatstat(week: date | None = None) -> int:
    from parser import whatstat_batch
    args = ["--save", "--pages", "10"]
    if week is not None:
        args.extend(["--week", week.isoformat()])
    return whatstat_batch.main(args)


def run_chart(key: str, save: bool, week: date | None = None) -> tuple[bool, str]:
    chart = CHARTS[key]
    try:
        items = chart.fetch(chart.limit)
    except Exception as error:  # noqa: BLE001 — сбой одного источника не должен останавливать остальные
        message = f"сбор не удался: {error}"
        if save:
            # Записываем сбой: иначе рейтинг примет его за выпадение объектов из чарта.
            try:
                save_chart_failure(chart, error, week=week)
                message += " (сбой записан)"
            except SaveError as save_error:
                message += f" (сбой не записан: {save_error})"
        return False, message
    if not save:
        return True, f"собрано {len(items)} позиций (не сохранено, нужен --save)"
    try:
        return True, save_chart(chart, items, week=week)
    except SaveError as error:
        return False, f"сохранение не удалось: {error}"


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Собрать все чарты за неделю")
    cli.add_argument("--save", action="store_true", help="Сохранить результаты")
    cli.add_argument("--only", nargs="+", choices=sorted(CHARTS), metavar="CHART",
                     help=f"Только указанные чарты: {', '.join(CHARTS)}")
    cli.add_argument("--skip-wordstat", action="store_true",
                     help="Не запускать Whatstat и Wordstat после сохранения чартов")
    cli.add_argument("--force", action="store_true",
                     help="Пересобрать уже сохранённые чарты текущей недели")
    week_group = cli.add_mutually_exclusive_group()
    week_group.add_argument("--week", type=date.fromisoformat, metavar="YYYY-MM-DD",
                            help="Неделя, к которой относятся данные (понедельник)")
    week_group.add_argument("--next-week", action="store_true",
                            help="Сохранить данные как замер следующего понедельника")
    cli.add_argument("--defer-publish", action="store_true",
                     help="Собрать Wordstat, но не обновлять рейтинг до отдельной публикации")
    args = cli.parse_args(argv)

    target_week = week_start() + timedelta(weeks=1) if args.next_week else (args.week or week_start())
    if target_week.weekday() != 0:
        cli.error("--week должен быть понедельником")
    if args.defer_publish and not args.save:
        cli.error("--defer-publish используется только вместе с --save")

    keys = args.only or list(CHARTS)
    skipped = []
    if args.save and not args.force:
        try:
            keys, skipped = missing_chart_keys(keys, target_week)
        except DatabaseConfigError as error:
            print(f"Ошибка проверки данных: {error}", file=sys.stderr)
            return 1
        except Exception as error:  # noqa: BLE001 — понятная ошибка до долгого запуска парсеров
            print(f"Ошибка проверки данных за текущую неделю: {error}", file=sys.stderr)
            return 1
        if skipped:
            print(f"Уже собрано, пропущено: {', '.join(skipped)}", file=sys.stderr)
    failed = []
    for key in keys:
        print(f"[{key}] запуск…", file=sys.stderr, flush=True)
        ok, message = run_chart(key, args.save, target_week)
        print(f"[{key}] {'OK' if ok else 'ОШИБКА'}: {message}", file=sys.stderr, flush=True)
        if not ok:
            failed.append(key)

    print(f"\nИтого: собрано {len(keys) - len(failed)} из {len(keys)}, пропущено {len(skipped)}.", file=sys.stderr)
    if failed:
        print(f"С ошибкой: {', '.join(failed)}", file=sys.stderr)

    whatstat_failed = False
    wordstat_failed = False
    if args.save and not args.skip_wordstat:
        print("\n[whatstat] запуск…", file=sys.stderr, flush=True)
        whatstat_failed = run_whatstat(target_week) != 0
        print(f"[whatstat] {'ОШИБКА' if whatstat_failed else 'OK'}", file=sys.stderr, flush=True)
        if not whatstat_failed:
            print("\n[wordstat] запуск…", file=sys.stderr, flush=True)
            wordstat_failed = run_wordstat(target_week, publish=not args.defer_publish) != 0
            print(f"[wordstat] {'ОШИБКА' if wordstat_failed else 'OK'}", file=sys.stderr, flush=True)

    return 1 if failed or whatstat_failed or wordstat_failed else 0


if __name__ == "__main__":
    sys.exit(main())
