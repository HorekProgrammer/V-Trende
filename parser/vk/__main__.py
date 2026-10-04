import argparse
import json

from . import get_vk_chart


def main():
    cli = argparse.ArgumentParser(description="Получить топ-100 VK Музыки")
    cli.add_argument("--limit", type=int, help="Количество треков; по умолчанию весь топ")
    args = cli.parse_args()
    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")
    try:
        tracks = get_vk_chart(args.limit)
    except (ValueError, RuntimeError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
