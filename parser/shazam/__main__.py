import argparse
import json
from pathlib import Path

from . import get_shazam_chart, parse_chart_html
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    cli = argparse.ArgumentParser(description="Получить топ-200 Shazam по России")
    cli.add_argument("--limit", type=int, help="Количество треков; по умолчанию весь топ")
    cli.add_argument("--html", type=Path, help="Прочитать сохранённый HTML вместо запуска браузера")
    add_save_argument(cli)
    args = cli.parse_args()
    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")
    limit = resolve_limit("shazam", args.limit, args.save)

    try:
        if args.html:
            tracks = parse_chart_html(args.html.read_text(encoding="utf-8"))[:limit]
        else:
            tracks = get_shazam_chart(limit)
    except (ValueError, RuntimeError, OSError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))

    if args.save:
        save_or_exit(cli, "shazam", tracks)


if __name__ == "__main__":
    main()
