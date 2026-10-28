import argparse
import json
from pathlib import Path

from . import (
    get_russian_twitch_positions,
    get_russian_twitch_ranking,
    parse_ranking_html,
    parse_ranking_positions_html,
)
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    cli = argparse.ArgumentParser(description="Получить недельную статистику русскоязычных Twitch-стримеров")
    cli.add_argument("--limit", type=int, help="Количество каналов от 1 до 150; по умолчанию 150")
    cli.add_argument(
        "--html",
        type=Path,
        help="Прочитать только каналы и подписчиков из сохранённой страницы рейтинга",
    )
    add_save_argument(cli)
    args = cli.parse_args()
    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")
    if args.save and args.html:
        cli.error("--html нельзя использовать с --save: в HTML рейтинга нет недельной статистики")

    try:
        if args.save:
            limit = resolve_limit("twitch", args.limit, save=True)
            channels = get_russian_twitch_ranking(limit)
        else:
            limit = args.limit if args.limit is not None else 150
            if args.html:
                channels = parse_ranking_html(args.html.read_text(encoding="utf-8"))[:limit]
            else:
                channels = get_russian_twitch_ranking(limit)
    except (ValueError, RuntimeError, OSError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(channels, ensure_ascii=False, indent=2))

    if args.save:
        save_or_exit(cli, "twitch", channels)


if __name__ == "__main__":
    main()
