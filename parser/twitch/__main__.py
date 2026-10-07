import argparse
import json
from pathlib import Path

from . import get_russian_twitch_ranking, parse_ranking_html


def main():
    cli = argparse.ArgumentParser(description="Получить недельную статистику русскоязычных Twitch-стримеров")
    cli.add_argument("--limit", type=int, default=150, help="Количество каналов от 1 до 150")
    cli.add_argument(
        "--html",
        type=Path,
        help="Прочитать только каналы и подписчиков из сохранённой страницы рейтинга",
    )
    args = cli.parse_args()
    try:
        if args.html:
            channels = parse_ranking_html(args.html.read_text(encoding="utf-8"))[:args.limit]
        else:
            channels = get_russian_twitch_ranking(args.limit)
    except (ValueError, RuntimeError, OSError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(channels, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
