"""Тестовые данные: несколько недель правдоподобных чартов для проверки запросов.

    python -m database.seed                 # 12 недель, заканчивая текущей
    python -m database.seed --weeks 20 --random-seed 7
    python -m database.seed --force         # дописать, даже если в базе уже есть сборы

Все названия явно вымышленные («Тестовый трек 012»). Данные проходят тот же путь,
что и настоящие: результат «парсера» → build_payload → load_payload, поэтому
заодно проверяется и формат пакетов, и загрузчик.

Что моделируется:
  * у объекта есть базовая популярность, тренд роста или угасания и неделя появления;
  * один объект попадает в несколько чартов своей категории с разными позициями;
  * игры бывают только в Steam, только в Epic или в обоих магазинах;
  * изредка сбор чарта проваливается (status = failed);
  * для объектов топов есть частота запросов Wordstat.
"""

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta

from parser.common import CHARTS, build_failure_payload, build_payload, week_start

from .db import DatabaseConfigError, connect
from .load_outbox import load_payload, refresh_rankings

FAILURE_PROBABILITY = 0.03


@dataclass
class FakeObject:
    number: int
    category: str
    base: float          # базовая популярность
    growth: float        # изменение популярности за неделю (лог-шкала)
    first_week: int      # с какой по счёту недели объект существует
    stores: set = field(default_factory=set)  # для игр: steam / epic

    def popularity(self, week_index: int, rng: random.Random) -> float | None:
        age = week_index - self.first_week
        if age < 0:
            return None
        # Новинки быстро набирают популярность, потом действует тренд.
        launch = 1 - math.exp(-(age + 1) / 1.5)
        # Рост или угасание длится не дольше полугода, иначе на длинной истории
        # популярность уходила бы в бесконечность или в ноль.
        return self.base * launch * math.exp(self.growth * min(age, 26) + rng.gauss(0, 0.15))


def _pool(rng: random.Random, category: str, size: int, weeks: int) -> list[FakeObject]:
    objects = []
    for number in range(1, size + 1):
        obj = FakeObject(
            number=number,
            category=category,
            base=rng.lognormvariate(0, 1),
            growth=rng.gauss(0, 0.06),
            # Примерно треть объектов появляется по ходу периода.
            first_week=0 if rng.random() < 0.65 else rng.randrange(0, weeks),
        )
        if category == "games":
            roll = rng.random()
            obj.stores = {"steam"} if roll < 0.6 else {"epic"} if roll < 0.8 else {"steam", "epic"}
        objects.append(obj)
    return objects


def _item(chart_key: str, obj: FakeObject, position: int) -> dict:
    """Запись в формате настоящего парсера этого чарта."""
    n = obj.number
    if obj.category == "music":
        artists = [f"Тестовый исполнитель {n % 60 + 1:02d}"]
        if n % 7 == 0:
            artists.append(f"Тестовый исполнитель {(n * 3) % 60 + 1:02d}")
        return {"position": position, "title": f"Тестовый трек {n:03d}", "artists": artists}
    if obj.category == "games":
        title = f"Тестовая игра {n:03d}"
        if chart_key.startswith("steam"):
            return {"position": position, "title": title, "steam_app_id": 900_000 + n, "tags": []}
        return {"position": position, "title": title, "epic_offer_id": f"test-offer-{n:03d}",
                "epic_namespace": "test", "epic_slug": f"test-game-{n:03d}"}
    if obj.category == "movies":
        return {"position": position, "title": f"Тестовый фильм {n:03d}",
                "kinopoisk_id": 9_000_000 + n, "year": 2026}
    return {"position": position, "channel": f"Тестовый стример {n:03d}", "slug": f"test_streamer_{n:03d}"}


def _eligible(chart_key: str, obj: FakeObject, rng: random.Random) -> bool:
    if obj.category == "games":
        store = "steam" if chart_key.startswith("steam") else "epic"
        return store in obj.stores
    if chart_key == "kinopoisk_boxoffice":
        # В прокате только недавние фильмы.
        return rng.random() < 0.5
    # Каждый музыкальный сервис видит не весь каталог.
    return rng.random() < 0.85


def generate(weeks: list[date], rng: random.Random) -> list[dict]:
    """Пакеты чартов и Wordstat за указанные недели, в хронологическом порядке."""
    pools = {
        "music": _pool(rng, "music", 260, len(weeks)),
        "games": _pool(rng, "games", 260, len(weeks)),
        "movies": _pool(rng, "movies", 120, len(weeks)),
        "streamers": _pool(rng, "streamers", 120, len(weeks)),
    }
    payloads = []
    for index, week in enumerate(weeks):
        popularity = {}
        for category, objects in pools.items():
            for obj in objects:
                value = obj.popularity(index, rng)
                if value is not None:
                    popularity[(category, obj.number)] = value

        for key, chart in CHARTS.items():
            if rng.random() < FAILURE_PROBABILITY:
                payloads.append(build_failure_payload(chart, "тестовый сбой источника", week=week))
                continue
            candidates = []
            for obj in pools[chart.category]:
                value = popularity.get((chart.category, obj.number))
                if value is not None and _eligible(key, obj, rng):
                    # У каждого сервиса своя аудитория: добавляем шум.
                    candidates.append((value * rng.lognormvariate(0, 0.35), obj))
            candidates.sort(key=lambda pair: pair[0], reverse=True)
            items = [_item(key, obj, position) for position, (_, obj) in
                     enumerate(candidates[:chart.limit], start=1)]
            if items:
                payloads.append(build_payload(chart, items, week=week))

        stats = []
        for category, objects in pools.items():
            for obj in objects:
                value = popularity.get((category, obj.number))
                if value is None:
                    continue
                # match_key берётся из пакета, как у настоящего wordstat_batch.
                sample = build_payload(_any_chart(category), [_item(_any_chart(category), obj, 1)], week=week)
                entry = sample["entries"][0]
                stats.append({
                    "category": category,
                    "match_key": entry["match_key"],
                    "query": entry["title"].lower(),
                    "search_count": int(value * 20_000 * rng.lognormvariate(0, 0.2)),
                })
        payloads.append({"type": "search_stats", "week_start": week.isoformat(), "entries": stats})
    return payloads


def _any_chart(category: str) -> str:
    return {"music": "zvuk", "games": "steam", "movies": "kinopoisk", "streamers": "twitch"}[category]


def seed(conn, *, weeks: int = 12, random_seed: int = 42, last_week: date | None = None) -> int:
    last_week = last_week or week_start()
    week_list = [last_week - timedelta(weeks=offset) for offset in range(weeks - 1, -1, -1)]
    payloads = generate(week_list, random.Random(random_seed))
    for payload in payloads:
        with conn.transaction():
            load_payload(conn, payload)
    refresh_rankings(conn)
    return len(payloads)


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Заполнить базу тестовыми данными")
    cli.add_argument("--weeks", type=int, default=12, help="Сколько недель сгенерировать")
    cli.add_argument("--random-seed", type=int, default=42, help="Зерно генератора")
    cli.add_argument("--force", action="store_true", help="Дописать, даже если в базе есть сборы")
    args = cli.parse_args(argv)
    if args.weeks < 1:
        cli.error("--weeks должен быть положительным")
    try:
        with connect() as conn:
            if not args.force and conn.execute("SELECT EXISTS (SELECT 1 FROM chart_runs)").fetchone()[0]:
                print("В базе уже есть сборы. Тестовые данные смешаются с ними; "
                      "для записи всё равно используйте --force.", file=sys.stderr)
                return 1
            count = seed(conn, weeks=args.weeks, random_seed=args.random_seed)
    except DatabaseConfigError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    print(f"Загружено пакетов: {count} ({args.weeks} недель).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
