import argparse
import json

from . import get_yandex_music_chart


def main():
    cli = argparse.ArgumentParser(description="Получить чарт Яндекс Музыки без авторизации")
    cli.add_argument("--limit", type=int, default=None, help="Число треков; по умолчанию весь чарт")
    args = cli.parse_args()
    try:
        tracks = get_yandex_music_chart(args.limit)
    except (ValueError, RuntimeError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
