import argparse
import sys
import json
from pathlib import Path

from . import parse_chart_html
from .zvuk_parser import fetch_chart_html
from parser.common import add_save_argument, resolve_limit, save_or_exit


def main():
    cli = argparse.ArgumentParser(description="Получить топ-100 Звука")
    cli.add_argument("--limit", type=int, help="Количество треков; по умолчанию весь топ")
    cli.add_argument("--html", type=Path, help="Прочитать сохранённый HTML вместо запроса к сайту")
    cli.add_argument(
        "--headed",
        action="store_true",
        help="Сразу открыть окно браузера, без попытки простого запроса",
    )
    cli.add_argument(
        "--dump-html",
        type=Path,
        help="Сохранить полученную страницу в файл (для диагностики), даже если разобрать её не удалось",
    )
    add_save_argument(cli)
    args = cli.parse_args()
    if args.limit is not None and args.limit < 1:
        cli.error("--limit должен быть положительным")
    limit = resolve_limit("zvuk", args.limit, args.save)

    try:
        if args.html:
            tracks = parse_chart_html(args.html.read_text(encoding="utf-8-sig"))[:limit]
        else:
            html = fetch_chart_html(browser_fallback=True, headed=args.headed)
            if args.dump_html:
                args.dump_html.write_text(html, encoding="utf-8")
                print(f"Страница сохранена в {args.dump_html}", file=sys.stderr)
            tracks = parse_chart_html(html)[:limit]
    except (ValueError, RuntimeError, OSError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(json.dumps(tracks, ensure_ascii=False, indent=2))

    if args.save:
        save_or_exit(cli, "zvuk", tracks)


if __name__ == "__main__":
    main()
