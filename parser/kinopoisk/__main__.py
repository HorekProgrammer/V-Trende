import argparse
import json

from . import get_kinopoisk_chart
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    cli = argparse.ArgumentParser(
        description="Получить рейтинг популярных фильмов Кинопоиска"
    )
    cli.add_argument(
        "--limit",
        type=int,
        help="Количество фильмов; по умолчанию весь топ-1000",
    )

    add_save_argument(cli)
    args = cli.parse_args()

    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")

    limit = resolve_limit("kinopoisk", args.limit, args.save)

    try:
        movies = get_kinopoisk_chart(limit)
    except (ValueError, RuntimeError) as error:
        cli.exit(1, f"Ошибка: {error}\n")

    print(json.dumps(movies, ensure_ascii=False, indent=2))

    if args.save:
        save_or_exit(cli, "kinopoisk", movies)


if __name__ == "__main__":
    main()