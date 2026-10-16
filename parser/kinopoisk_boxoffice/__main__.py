import argparse
import json

from .kinopoisk_boxoffice_parser import (
    get_kinopoisk_boxoffice,
)


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

    args = parser.parse_args()

    try:
        chart = get_kinopoisk_boxoffice(
            limit=args.limit,
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


if __name__ == "__main__":
    main()