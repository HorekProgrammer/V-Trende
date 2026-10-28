"""Публикация заранее собранного недельного рейтинга.

Используется планировщиком по понедельникам в 00:00 МСК:
    python -m parser.publish_rankings
"""

import sys

from parser.common import SaveError, publish_rankings


def main() -> int:
    try:
        message = publish_rankings()
    except SaveError as error:
        print(f"Ошибка публикации: {error}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
