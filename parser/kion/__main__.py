import argparse
import json
from pathlib import Path

from . import get_kion_chart, parse_chart_html


def main():
    cli = argparse.ArgumentParser(description="Получить топ-100 КИОН Музыки")
    cli.add_argument("--limit", type=int, help="Количество треков; по умолчанию весь топ")
    cli.add_argument("--html", type=Path, help="Прочитать сохранённый HTML вместо запроса к сайту")
    args = cli.parse_args()
    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")
    try:
        if args.html:
            tracks = parse_chart_html(args.html.read_text(encoding="utf-8"))[:args.limit]
        else:
            tracks = get_kion_chart(args.limit)
    except (ValueError, RuntimeError, OSError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
