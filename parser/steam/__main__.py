import argparse
import json

from .steam_parser import get_steam_chart
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    parser = argparse.ArgumentParser(
        description="Fetch the Steam RU weekly Top Sellers chart"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of chart entries to return",
    )

    add_save_argument(parser)
    args = parser.parse_args()

    limit = resolve_limit("steam", args.limit, args.save)

    try:
        chart = get_steam_chart(limit=limit)
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")

    print(
        json.dumps(
            chart,
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.save:
        save_or_exit(parser, "steam", chart)


if __name__ == "__main__":
    main()