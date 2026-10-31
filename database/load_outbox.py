"""Загрузка пакетов парсеров из data/outbox/ в PostgreSQL.

    python -m database.load_outbox            # загрузить все пакеты
    python -m database.load_outbox --keep     # не переносить загруженные файлы
    python -m database.load_outbox --dir путь # другая папка с пакетами

Каждый файл загружается в отдельной транзакции: либо целиком, либо никак.
Загруженные файлы переносятся в data/outbox/loaded/, файлы с ошибкой остаются
на месте. Повторная загрузка того же пакета ничего не дублирует. После загрузки
пересчитывается материализованный рейтинг mv_category_rank.

Типы пакетов:
  * чарт (type = "chart")              — позиции за неделю (parser/common/upload.py);
  * неудачный сбор (status = "failed") — чарт за неделю собрать не удалось;
  * Wordstat (type = "search_stats") — частота запросов (parser/wordstat_batch.py);
  * Whatstat (type = "game_audience_stats") — средняя Twitch-аудитория игр за 7 дней.
"""

import argparse
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

from .db import PROJECT_ROOT, DatabaseConfigError, connect

OUTBOX_DIR = PROJECT_ROOT / "data" / "outbox"
CATEGORIES = {"music", "games", "movies", "streamers"}
MAX_POSITION = 150


class PayloadError(ValueError):
    """Пакет некорректен; в базу из него ничего не записано."""


# ---------- проверка пакета ----------

def _text(container: dict, key: str, *, required: bool = True, max_length: int = 1000) -> str | None:
    value = container.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise PayloadError(f"Поле {key!r}: ожидается непустая строка до {max_length} символов.")
    return value.strip()


def _week(payload: dict) -> date:
    try:
        week = date.fromisoformat(payload["week_start"])
    except (KeyError, TypeError, ValueError):
        raise PayloadError("Поле 'week_start': ожидается дата YYYY-MM-DD.") from None
    if week.weekday() != 0:
        raise PayloadError("Поле 'week_start' должно быть понедельником.")
    return week


def _collected_at(payload: dict) -> datetime | None:
    value = payload.get("collected_at")
    if value is None:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise PayloadError("Поле 'collected_at': ожидается дата и время ISO 8601.") from None
    if moment.tzinfo is None:
        raise PayloadError("Поле 'collected_at' должно содержать часовой пояс.")
    return moment


def _category(container: dict) -> str:
    category = container.get("category")
    if category not in CATEGORIES:
        raise PayloadError(f"Неизвестная категория: {category!r}.")
    return category


def _entries(payload: dict) -> list:
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise PayloadError("Поле 'entries': ожидается список.")
    if not all(isinstance(entry, dict) for entry in entries):
        raise PayloadError("Каждая запись в 'entries' должна быть объектом.")
    return entries


def _nonnegative_number(entry: dict, key: str, *, integer: bool = False) -> int | float:
    value = entry.get(key, 0)
    valid_type = type(value) is int if integer else type(value) in (int, float)
    if not valid_type or value < 0:
        kind = "целым" if integer else "числом"
        raise PayloadError(f"Поле {key!r} должно быть неотрицательным {kind}: {value!r}.")
    return value


def _cover_url(entry: dict) -> str | None:
    url = _text(entry, "cover_url", required=False, max_length=2000)
    if url is not None and not url.startswith("https://"):
        raise PayloadError(f"Поле 'cover_url' должно быть https-ссылкой: {url!r}.")
    return url


def _year(entry: dict) -> int | None:
    year = entry.get("year")
    if year is None:
        return None
    if type(year) is not int or not 1900 <= year <= 2100:
        raise PayloadError(f"Поле 'year' должно быть годом от 1900 до 2100: {year!r}.")
    return year


def _chart_entry(entry: dict, source: str) -> dict:
    position = entry.get("position")
    if type(position) is not int or not 1 <= position <= MAX_POSITION:
        raise PayloadError(f"Позиция должна быть целым числом от 1 до {MAX_POSITION}: {position!r}.")
    result = {
        "position": position,
        "title": _text(entry, "title"),
        "subtitle": _text(entry, "subtitle", required=False),
        "genre": _text(entry, "genre", required=False, max_length=100),
        "external_id": _text(entry, "external_id", required=False, max_length=200),
        "url": _text(entry, "url", required=False, max_length=2000),
        "cover_url": _cover_url(entry),
        "year": _year(entry),
        "match_key": _text(entry, "match_key"),
    }
    if source == "twitch":
        result["twitch_metrics"] = {
            "total_followers": _nonnegative_number(entry, "total_followers", integer=True),
            "hours_streamed": _nonnegative_number(entry, "hours_streamed"),
            "average_viewers": _nonnegative_number(entry, "average_viewers", integer=True),
            "peak_viewers": _nonnegative_number(entry, "peak_viewers", integer=True),
            "hours_watched": _nonnegative_number(entry, "hours_watched", integer=True),
            "followers_gained": _nonnegative_number(entry, "followers_gained", integer=True),
            "followers_per_hour": _nonnegative_number(entry, "followers_per_hour"),
        }
    return result


# ---------- запись ----------

def _upsert_chart(conn, source: str, name: str, category: str) -> int:
    return conn.execute(
        """
        INSERT INTO charts (source, name, category) VALUES (%s, %s, %s)
        ON CONFLICT (source, name) DO UPDATE SET category = EXCLUDED.category
        RETURNING id
        """,
        (source, name, category),
    ).fetchone()[0]


def _genre_id(conn, category: str, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM genres WHERE category = %s AND name = %s", (category, name)
    ).fetchone()
    if row is None:
        raise PayloadError(f"Жанра {name!r} нет в справочнике категории {category}.")
    return row[0]


def _resolve_trend(conn, source: str, category: str, entry: dict) -> int:
    """Находит объект: ID на платформе → ссылка → match_key; иначе создаёт новый."""
    row = None
    if entry["external_id"] is not None:
        row = conn.execute(
            "SELECT trend_id FROM trend_source_items WHERE source = %s AND external_id = %s",
            (source, entry["external_id"]),
        ).fetchone()
    elif entry["url"] is not None:
        row = conn.execute(
            "SELECT trend_id FROM trend_source_items "
            "WHERE source = %s AND url = %s AND external_id IS NULL",
            (source, entry["url"]),
        ).fetchone()

    if row is not None:
        trend_id = row[0]
        if entry["subtitle"] is not None:
            conn.execute(
                "UPDATE trends SET subtitle = %s WHERE id = %s AND subtitle IS NULL",
                (entry["subtitle"], trend_id),
            )
    else:
        trend_id = conn.execute(
            """
            INSERT INTO trends (category, title, subtitle, match_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (category, match_key)
            DO UPDATE SET subtitle = COALESCE(trends.subtitle, EXCLUDED.subtitle)
            RETURNING id
            """,
            (category, entry["title"], entry["subtitle"], entry["match_key"]),
        ).fetchone()[0]

    if entry["external_id"] is not None or entry["url"] is not None:
        # ON CONFLICT без цели срабатывает и на частичные уникальные индексы.
        conn.execute(
            """
            INSERT INTO trend_source_items (trend_id, source, external_id, url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (trend_id, source, entry["external_id"], entry["url"]),
        )

    if entry["year"] is not None:
        conn.execute(
            "UPDATE trends SET year = %s WHERE id = %s AND year IS NULL",
            (entry["year"], trend_id),
        )

    if entry["cover_url"] is not None:
        conn.execute(
            """UPDATE trends SET cover_url = %s, cover_source = %s
               WHERE id = %s AND (cover_url IS NULL OR cover_source = %s)""",
            (entry["cover_url"], source, trend_id, source),
        )

    if entry["genre"] is not None:
        # Жанр, уже назначенный объекту, не перезаписывается.
        conn.execute(
            "UPDATE trends SET genre_id = %s WHERE id = %s AND genre_id IS NULL",
            (_genre_id(conn, category, entry["genre"]), trend_id),
        )
    return trend_id


def load_chart(conn, payload: dict) -> str:
    source = _text(payload, "source", max_length=100)
    name = _text(payload, "chart", max_length=200)
    category = _category(payload)
    week = _week(payload)
    collected_at = _collected_at(payload)
    entries = sorted((_chart_entry(e, source) for e in _entries(payload)), key=lambda e: e["position"])
    if not entries:
        raise PayloadError("В пакете чарта нет позиций.")
    positions = [e["position"] for e in entries]
    if len(set(positions)) != len(positions):
        raise PayloadError("Позиции в пакете повторяются.")

    chart_id = _upsert_chart(conn, source, name, category)
    run_id = conn.execute(
        """
        INSERT INTO chart_runs (chart_id, week_start, status, started_at, finished_at)
        VALUES (%s, %s, 'success', COALESCE(%s, NOW()), NOW())
        ON CONFLICT (chart_id, week_start) DO UPDATE
            SET status = 'success',
                started_at = EXCLUDED.started_at,
                finished_at = NOW(),
                error = NULL
        RETURNING id
        """,
        (chart_id, week, collected_at),
    ).fetchone()[0]
    # Повторная загрузка за ту же неделю заменяет позиции запуска целиком.
    conn.execute("DELETE FROM trend_history WHERE run_id = %s", (run_id,))
    if source == "twitch":
        conn.execute(
            """DELETE FROM twitch_weekly_stats
               WHERE week_start = %s
                 AND trend_id IN (
                     SELECT trend_id FROM trend_source_items WHERE source = 'twitch'
                 )""",
            (week,),
        )

    seen, skipped = set(), 0
    for entry in entries:
        trend_id = _resolve_trend(conn, source, category, entry)
        if trend_id in seen:
            # Два элемента чарта оказались одним объектом: остаётся лучшая позиция.
            skipped += 1
            continue
        seen.add(trend_id)
        conn.execute(
            "INSERT INTO trend_history (run_id, trend_id, position) VALUES (%s, %s, %s)",
            (run_id, trend_id, entry["position"]),
        )
        if source == "twitch":
            metrics = entry["twitch_metrics"]
            conn.execute(
                """
                INSERT INTO twitch_weekly_stats (
                    trend_id, week_start, total_followers, hours_streamed,
                    average_viewers, peak_viewers, hours_watched,
                    followers_gained, followers_per_hour, collected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
                ON CONFLICT (trend_id, week_start) DO UPDATE SET
                    total_followers = EXCLUDED.total_followers,
                    hours_streamed = EXCLUDED.hours_streamed,
                    average_viewers = EXCLUDED.average_viewers,
                    peak_viewers = EXCLUDED.peak_viewers,
                    hours_watched = EXCLUDED.hours_watched,
                    followers_gained = EXCLUDED.followers_gained,
                    followers_per_hour = EXCLUDED.followers_per_hour,
                    collected_at = EXCLUDED.collected_at
                """,
                (
                    trend_id, week, metrics["total_followers"], metrics["hours_streamed"],
                    metrics["average_viewers"], metrics["peak_viewers"],
                    metrics["hours_watched"], metrics["followers_gained"],
                    metrics["followers_per_hour"], collected_at,
                ),
            )
    note = f", пропущено повторов: {skipped}" if skipped else ""
    return f"{source} / {name} за {week}: {len(seen)} позиций{note}"


def load_failed_run(conn, payload: dict) -> str:
    source = _text(payload, "source", max_length=100)
    name = _text(payload, "chart", max_length=200)
    category = _category(payload)
    week = _week(payload)
    collected_at = _collected_at(payload)
    error = _text(payload, "error", required=False, max_length=10_000) or "неизвестная ошибка"

    chart_id = _upsert_chart(conn, source, name, category)
    # Успешный сбор той же недели не затирается неудачным перезапуском.
    row = conn.execute(
        """
        INSERT INTO chart_runs (chart_id, week_start, status, started_at, finished_at, error)
        VALUES (%s, %s, 'failed', COALESCE(%s, NOW()), NOW(), %s)
        ON CONFLICT (chart_id, week_start) DO UPDATE
            SET status = 'failed',
                started_at = EXCLUDED.started_at,
                finished_at = NOW(),
                error = EXCLUDED.error
            WHERE chart_runs.status <> 'success'
        RETURNING id
        """,
        (chart_id, week, collected_at, error),
    ).fetchone()
    if row is None:
        return f"{source} / {name} за {week}: сбой не записан, неделя уже собрана успешно"
    return f"{source} / {name} за {week}: записан неудачный сбор"


def load_search_stats(conn, payload: dict) -> str:
    week = _week(payload)
    collected_at = _collected_at(payload)
    saved = missing = 0
    for raw in _entries(payload):
        category = _category(raw)
        match_key = _text(raw, "match_key")
        query = _text(raw, "query", max_length=400)
        count = raw.get("search_count")
        if type(count) is not int or count < 0:
            raise PayloadError(f"search_count должен быть неотрицательным целым: {count!r}.")
        row = conn.execute(
            "SELECT id FROM trends WHERE category = %s AND match_key = %s", (category, match_key)
        ).fetchone()
        if row is None:
            missing += 1
            continue
        conn.execute(
            """
            INSERT INTO trend_search_stats (trend_id, week_start, query, search_count, collected_at)
            VALUES (%s, %s, %s, %s, COALESCE(%s, NOW()))
            ON CONFLICT (trend_id, week_start) DO UPDATE
                SET query = EXCLUDED.query,
                    search_count = EXCLUDED.search_count,
                    collected_at = EXCLUDED.collected_at
            """,
            (row[0], week, query, count, collected_at),
        )
        saved += 1
    note = f", объектов нет в базе: {missing}" if missing else ""
    return f"Wordstat за {week}: {saved} значений{note}"


def load_game_audience_stats(conn, payload: dict) -> str:
    week = _week(payload)
    collected_at = _collected_at(payload)
    saved = missing = 0
    entries = _entries(payload)
    if not entries:
        raise PayloadError("В пакете Whatstat нет игровых категорий.")
    for raw in entries:
        match_key = _text(raw, "match_key")
        source_title = _text(raw, "source_title", max_length=300)
        source_category_id = _text(raw, "source_category_id", max_length=100)
        source_url = _text(raw, "source_url", max_length=2000)
        position = raw.get("position")
        average_viewers = raw.get("average_viewers")
        if type(position) is not int or position <= 0:
            raise PayloadError(f"position должен быть положительным целым: {position!r}.")
        if type(average_viewers) is not int or average_viewers < 0:
            raise PayloadError(
                f"average_viewers должен быть неотрицательным целым: {average_viewers!r}."
            )
        row = conn.execute(
            "SELECT id FROM trends WHERE category = 'games' AND match_key = %s",
            (match_key,),
        ).fetchone()
        if row is None:
            missing += 1
            continue
        conn.execute(
            """
            INSERT INTO game_audience_stats (
                trend_id, week_start, source_title, source_category_id,
                source_url, position, average_viewers, collected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
            ON CONFLICT (trend_id, week_start) DO UPDATE SET
                source_title = EXCLUDED.source_title,
                source_category_id = EXCLUDED.source_category_id,
                source_url = EXCLUDED.source_url,
                position = EXCLUDED.position,
                average_viewers = EXCLUDED.average_viewers,
                collected_at = EXCLUDED.collected_at
            """,
            (
                row[0], week, source_title, source_category_id, source_url,
                position, average_viewers, collected_at,
            ),
        )
        saved += 1
    if not saved:
        raise PayloadError("Ни одна категория Whatstat не найдена среди игр в базе.")
    note = f", объектов нет в базе: {missing}" if missing else ""
    return f"Whatstat за {week}: {saved} игровых категорий{note}"


def load_payload(conn, payload: dict) -> str:
    """Записывает один пакет. Вызывать внутри транзакции (см. load_file)."""
    if not isinstance(payload, dict):
        raise PayloadError("Пакет должен быть JSON-объектом.")
    kind = payload.get("type", "chart")
    if kind == "search_stats":
        return load_search_stats(conn, payload)
    if kind == "game_audience_stats":
        return load_game_audience_stats(conn, payload)
    if kind != "chart":
        raise PayloadError(f"Неизвестный тип пакета: {kind!r}.")
    if payload.get("status") == "failed":
        return load_failed_run(conn, payload)
    return load_chart(conn, payload)


def refresh_rankings(conn) -> None:
    """Пересчитывает материализованный рейтинг после загрузки чартов.

    CONCURRENTLY: сайт продолжает читать старую версию, пока строится новая.
    Нельзя вызывать внутри транзакции.
    """
    conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_category_rank")


def load_file(conn, path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PayloadError(f"Не удалось прочитать JSON: {error}") from None
    with conn.transaction():
        return load_payload(conn, payload)


def load_outbox(conn, directory: Path = OUTBOX_DIR, *, keep: bool = False,
                log=print) -> tuple[list[Path], list[Path]]:
    """Загружает все *.json из папки и обновляет рейтинг. Возвращает (загруженные, с ошибкой)."""
    loaded, failed = [], []
    # Сначала старые недели: история складывается в хронологическом порядке.
    for path in sorted(directory.glob("*.json")):
        try:
            message = load_file(conn, path)
        except Exception as error:  # noqa: BLE001 — ошибка одного файла не останавливает остальные
            failed.append(path)
            log(f"[ОШИБКА] {path.name}: {error}")
            continue
        loaded.append(path)
        log(f"[OK] {path.name}: {message}")
        if not keep:
            target_dir = directory / "loaded"
            target_dir.mkdir(exist_ok=True)
            shutil.move(str(path), target_dir / path.name)
    if loaded:
        refresh_rankings(conn)
        log("Рейтинг категорий пересчитан.")
    return loaded, failed


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Загрузить пакеты парсеров в PostgreSQL")
    cli.add_argument("--dir", type=Path, default=OUTBOX_DIR, help="Папка с пакетами")
    cli.add_argument("--keep", action="store_true", help="Не переносить загруженные файлы")
    args = cli.parse_args(argv)
    if not args.dir.is_dir():
        print(f"Папки {args.dir} нет: загружать нечего.", file=sys.stderr)
        return 0
    try:
        with connect() as conn:
            loaded, failed = load_outbox(conn, args.dir, keep=args.keep,
                                         log=lambda message: print(message, file=sys.stderr))
    except DatabaseConfigError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    print(f"\nЗагружено: {len(loaded)}, с ошибкой: {len(failed)}.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
