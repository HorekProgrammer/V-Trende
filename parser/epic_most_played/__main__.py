import argparse
import json

from .epic_most_played_parser import (
    get_epic_most_played_chart,
)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Epic Games Most Played chart"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    try:
        chart = get_epic_most_played_chart(
            limit=args.limit
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