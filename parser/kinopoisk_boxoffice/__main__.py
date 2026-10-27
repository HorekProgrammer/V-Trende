import argparse
import json

from .kinopoisk_boxoffice_parser import (
    get_kinopoisk_boxoffice,
)
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch the Kinopoisk Russia + CIS "
            "weekend box office chart by viewers"
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of chart entries to return",
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the Chromium browser window",
    )

    add_save_argument(parser)
    args = parser.parse_args()

    limit = resolve_limit("kinopoisk_boxoffice", args.limit, args.save)

    try:
        chart = get_kinopoisk_boxoffice(
            limit=limit,
            headless=not args.headed,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(
            1,
            f"error: {exc}\n",
        )

    print(
        json.dumps(
            chart,
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.save:
        save_or_exit(parser, "kinopoisk_boxoffice", chart)


if __name__ == "__main__":
    main()