import argparse
import json
from pathlib import Path

from . import get_apple_music_chart, parse_chart_html
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    cli = argparse.ArgumentParser(description="Получить топ-100 Apple Music по России")
    cli.add_argument("--limit", type=int, help="Количество треков; по умолчанию весь топ")
    cli.add_argument("--html", type=Path, help="Прочитать сохранённый HTML вместо запроса к сайту")
    add_save_argument(cli)
    args = cli.parse_args()
    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")
    limit = resolve_limit("apple_music", args.limit, args.save)

    try:
        if args.html:
            tracks = parse_chart_html(args.html.read_text(encoding="utf-8"))[:limit]
        else:
            tracks = get_apple_music_chart(limit)
    except (ValueError, RuntimeError, OSError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))

    if args.save:
        save_or_exit(cli, "apple_music", tracks)


if __name__ == "__main__":
    main()
