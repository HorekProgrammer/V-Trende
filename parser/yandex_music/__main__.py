import argparse
import json

from . import get_yandex_music_chart
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    cli = argparse.ArgumentParser(description="Получить чарт Яндекс Музыки без авторизации")
    cli.add_argument("--limit", type=int, default=None, help="Число треков; по умолчанию весь чарт")
    add_save_argument(cli)
    args = cli.parse_args()
    limit = resolve_limit("yandex_music", args.limit, args.save)

    try:
        tracks = get_yandex_music_chart(limit)
    except (ValueError, RuntimeError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))

    if args.save:
        save_or_exit(cli, "yandex_music", tracks)


if __name__ == "__main__":
    main()
