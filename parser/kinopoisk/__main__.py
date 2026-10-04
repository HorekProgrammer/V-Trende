import argparse
import json

from . import get_kinopoisk_chart


def main():
    cli = argparse.ArgumentParser(
        description="Получить рейтинг популярных фильмов Кинопоиска"
    )
    cli.add_argument(
        "--limit",
        type=int,
        help="Количество фильмов; по умолчанию весь топ-1000",
    )

    args = cli.parse_args()

    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")

    try:
        movies = get_kinopoisk_chart(args.limit)
    except (ValueError, RuntimeError) as error:
        cli.exit(1, f"Ошибка: {error}\n")

    print(json.dumps(movies, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()