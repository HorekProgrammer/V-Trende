import argparse

from . import get_wordstat_count


def main() -> None:
    cli = argparse.ArgumentParser(description="Частотность фразы в России через веб-сессию Wordstat")
    cli.add_argument("phrase", help="Слово или фраза для Wordstat")
    args = cli.parse_args()
    try:
        count = get_wordstat_count(args.phrase)
    except (ValueError, RuntimeError) as error:
        cli.exit(1, f"Ошибка: {error}\n")
    print(count)


if __name__ == "__main__":
    main()
