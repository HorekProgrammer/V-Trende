import argparse
import json

from . import get_vk_chart
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    cli = argparse.ArgumentParser(description="Получить топ-100 VK Музыки")
    cli.add_argument("--limit", type=int, help="Количество треков; по умолчанию весь топ")
    add_save_argument(cli)
    args = cli.parse_args()
    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")
    limit = resolve_limit("vk", args.limit, args.save)

    try:
        tracks = get_vk_chart(limit)
    except (ValueError, RuntimeError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))

    if args.save:
        save_or_exit(cli, "vk", tracks)


if __name__ == "__main__":
    main()
