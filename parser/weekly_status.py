"""Read-only status report for the latest scheduled weekly collection."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from database.db import DatabaseConfigError, connect
from parser.common.charts import CHARTS
from parser.scheduler import LOG_DIR


START_RE = re.compile(r"^\[(?P<time>[^]]+)] prepare: запуск$")
FINISH_RE = re.compile(r"^\[(?P<time>[^]]+)] prepare: код (?P<code>\d+)$")
ERROR_RE = re.compile(r"^\[(?P<name>[^]]+)] ОШИБКА: (?P<message>.+)$")


@dataclass(frozen=True)
class PrepareRun:
    started_at: datetime
    finished_at: datetime | None
    code: int | None
    errors: tuple[tuple[str, str], ...]

    @property
    def week(self) -> date:
        day = self.started_at.date()
        return day + timedelta(days=7 - day.weekday())


def parse_latest_prepare(text: str) -> PrepareRun | None:
    lines = text.splitlines()
    starts = [(index, START_RE.match(line)) for index, line in enumerate(lines)]
    starts = [(index, match) for index, match in starts if match]
    if not starts:
        return None
    index, match = starts[-1]
    started_at = datetime.fromisoformat(match.group("time"))
    finished_at = None
    code = None
    errors: list[tuple[str, str]] = []
    for line in lines[index + 1:]:
        if START_RE.match(line):
            break
        finish = FINISH_RE.match(line)
        if finish:
            finished_at = datetime.fromisoformat(finish.group("time"))
            code = int(finish.group("code"))
            break
        error = ERROR_RE.match(line)
        if error:
            errors.append((error.group("name"), error.group("message")))
    return PrepareRun(started_at, finished_at, code, tuple(errors))


def latest_prepare(log_dir: Path = LOG_DIR) -> PrepareRun | None:
    for path in sorted(log_dir.glob("scheduler-*.log"), reverse=True):
        try:
            run = parse_latest_prepare(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if run is not None:
            return run
    return None


def chart_states(week: date) -> dict[str, tuple[str, str | None]]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.source, c.name, r.status, r.error
               FROM chart_runs r
               JOIN charts c ON c.id = r.chart_id
               WHERE r.week_start = %s""",
            (week,),
        ).fetchall()
    by_chart = {(source, name): (status, error) for source, name, status, error in rows}
    return {
        key: by_chart.get((chart.source, chart.name), ("missing", None))
        for key, chart in CHARTS.items()
    }


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Статус последнего планового сбора В-Тренде")
    cli.add_argument("--week", type=date.fromisoformat, help="целевая неделя YYYY-MM-DD")
    args = cli.parse_args(argv)

    run = latest_prepare()
    if run is None and args.week is None:
        print("Статус: НЕТ ДАННЫХ — в журнале ещё нет планового запуска.")
        return 1
    week = args.week or run.week
    if week.weekday() != 0:
        cli.error("--week должен указывать на понедельник")

    if run is not None:
        print(f"Последний запуск: {run.started_at:%d.%m.%Y %H:%M:%S %Z}")
        print(f"Целевая неделя: {week.isoformat()}")
        if run.code is None:
            print("Статус процесса: ЕЩЁ РАБОТАЕТ")
        else:
            result = "УСПЕШНО" if run.code == 0 else "С ОШИБКОЙ"
            print(f"Статус процесса: {result} (код {run.code})")
            print(f"Завершён: {run.finished_at:%d.%m.%Y %H:%M:%S %Z}")

    try:
        states = chart_states(week)
    except DatabaseConfigError as error:
        print(f"База данных: НЕДОСТУПНА — {error}")
        return 1

    successful = [key for key, (status, _) in states.items() if status == "success"]
    failed = [(key, error) for key, (status, error) in states.items() if status == "failed"]
    pending = [key for key, (status, _) in states.items() if status in {"missing", "running"}]
    print(f"Чарты: {len(successful)}/{len(states)} успешно")
    if failed:
        print("Ошибки чартов:")
        for key, error in failed:
            print(f"  - {key}: {error or 'причина не записана'}")
    if pending:
        print("Ещё не готовы: " + ", ".join(pending))
    if run is not None:
        logged_only = [(name, message) for name, message in run.errors if name not in states]
        if logged_only:
            print("Ошибки дополнительных этапов:")
            for name, message in logged_only:
                print(f"  - {name}: {message}")

    if run is not None and run.code is None:
        print("Итог: сбор ещё выполняется; запустите проверку позже.")
        return 2
    if failed or pending or (run is not None and run.code != 0):
        print("Итог: сбор требует внимания.")
        return 1
    print("Итог: все парсеры завершились успешно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
