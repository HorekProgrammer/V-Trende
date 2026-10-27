import argparse
import json

from .steam_players_parser import (
    get_steam_players_chart,
)
from parser.common import add_save_argument, resolve_limit, save_or_exit


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

    add_save_argument(parser)
    args = parser.parse_args()

    limit = resolve_limit("steam_players", args.limit, args.save)

    try:
        chart = get_steam_players_chart(
            limit=limit,
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
        save_or_exit(parser, "steam_players", chart)


if __name__ == "__main__":
    main()