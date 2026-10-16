import argparse
import json

from .steam_players_parser import (
    get_steam_players_chart,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch the Steam Most Played chart "
            "by current player count"
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of chart entries to return",
    )

    args = parser.parse_args()

    try:
        chart = get_steam_players_chart(
            limit=args.limit,
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