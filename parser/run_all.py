"""Еженедельный сбор всех чартов.

    python -m parser.run_all            # собрать и показать сводку, ничего не сохраняя
    python -m parser.run_all --save     # собрать и сохранить (бэкенд или data/outbox/)
    python -m parser.run_all --only steam twitch --save

Падение одного парсера не останавливает остальные; с --save сбой сохраняется
отдельным пакетом, и в базе запуск получает статус failed. Если хотя бы один чарт
не собран или не сохранён, процесс завершается с кодом 1.

Еженедельный порядок:
    python -m parser.run_all --save        # 1. собрать чарты
    python -m database.load_outbox         # 2. загрузить их в базу
    python -m parser.wordstat_batch --save # 3. Wordstat для объектов топов недели
    python -m database.load_outbox         # 4. загрузить Wordstat
"""

import argparse
import sys

from parser.common import CHARTS, SaveError, save_chart, save_chart_failure


def run_chart(key: str, save: bool) -> tuple[bool, str]:
    chart = CHARTS[key]
    try:
        items = chart.fetch(chart.limit)
    except Exception as error:  # noqa: BLE001 — сбой одного источника не должен останавливать остальные
        message = f"сбор не удался: {error}"
        if save:
            # Записываем сбой: иначе рейтинг примет его за выпадение объектов из чарта.
            try:
                save_chart_failure(chart, error)
                message += " (сбой записан)"
            except SaveError as save_error:
                message += f" (сбой не записан: {save_error})"
        return False, message
    if not save:
        return True, f"собрано {len(items)} позиций (не сохранено, нужен --save)"
    try:
        return True, save_chart(chart, items)
    except SaveError as error:
        return False, f"сохранение не удалось: {error}"


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Собрать все чарты за неделю")
    cli.add_argument("--save", action="store_true", help="Сохранить результаты")
    cli.add_argument("--only", nargs="+", choices=sorted(CHARTS), metavar="CHART",
                     help=f"Только указанные чарты: {', '.join(CHARTS)}")
    args = cli.parse_args(argv)

    keys = args.only or list(CHARTS)
    failed = []
    for key in keys:
        print(f"[{key}] запуск…", file=sys.stderr, flush=True)
        ok, message = run_chart(key, args.save)
        print(f"[{key}] {'OK' if ok else 'ОШИБКА'}: {message}", file=sys.stderr, flush=True)
        if not ok:
            failed.append(key)

    print(f"\nИтого: успешно {len(keys) - len(failed)} из {len(keys)}.", file=sys.stderr)
    if failed:
        print(f"С ошибкой: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
