import argparse
import json

from .epic_most_played_parser import (
    get_epic_most_played_chart,
)
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Epic Games Most Played chart"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    add_save_argument(parser)
    args = parser.parse_args()

    limit = resolve_limit("epic_most_played", args.limit, args.save)

    try:
        chart = get_epic_most_played_chart(
            limit=limit
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
        save_or_exit(parser, "epic_most_played", chart)


if __name__ == "__main__":
    main()