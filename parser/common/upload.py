"""Сборка пакета данных чарта и отправка его в бэкенд.

Пакет чарта отправляется POST-запросом на {BACKEND_URL}/api/v1/internal/update-trends,
пакет Wordstat — на {BACKEND_URL}/api/v1/internal/update-search-stats,
пакет игровой аудитории — на {BACKEND_URL}/api/v1/internal/update-game-audience-stats,
с заголовком Authorization: Bearer {INTERNAL_API_TOKEN}. Пока BACKEND_URL не задан,
пакет сохраняется в data/outbox/; оттуда его загружает python -m database.load_outbox.
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values

from .charts import CHARTS, Chart

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
OUTBOX_DIR = PROJECT_ROOT / "data" / "outbox"
ENDPOINT_PATH = "/api/v1/internal/update-trends"
SEARCH_STATS_ENDPOINT_PATH = "/api/v1/internal/update-search-stats"
GAME_AUDIENCE_ENDPOINT_PATH = "/api/v1/internal/update-game-audience-stats"
PUBLISH_RANKINGS_ENDPOINT_PATH = "/api/v1/internal/publish-rankings"
# Москва живёт в UTC+3 без перехода на летнее время; фиксированный сдвиг
# не требует пакета tzdata на Windows.
MOSCOW_TZ = timezone(timedelta(hours=3), "MSK")


class SaveError(RuntimeError):
    """Данные не удалось сохранить: обновление нельзя считать успешным."""


def _settings() -> dict:
    return {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}


def week_start(moment: datetime | None = None) -> date:
    """Понедельник недели замера по московскому времени."""
    moment = moment or datetime.now(MOSCOW_TZ)
    if moment.tzinfo is None:
        raise ValueError("moment должен содержать часовой пояс.")
    day = moment.astimezone(MOSCOW_TZ).date()
    return day - timedelta(days=day.weekday())


def build_payload(chart: Chart | str, items: list[dict], *, week: date | None = None) -> dict:
    """Переводит результат парсера в общий формат и обрезает его до лимита категории."""
    if isinstance(chart, str):
        chart = CHARTS[chart]
    week = week or week_start()
    if week.weekday() != 0:
        raise ValueError("week должен быть понедельником.")

    try:
        entries = [chart.to_entry(item) for item in items if item["position"] <= chart.limit]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{chart.key}: некорректная запись парсера ({error}).") from None

    entries.sort(key=lambda entry: entry["position"])
    positions = [entry["position"] for entry in entries]
    if not entries:
        raise ValueError(f"{chart.key}: нет ни одной позиции для сохранения.")
    if any(type(p) is not int or p < 1 for p in positions) or len(set(positions)) != len(positions):
        raise ValueError(f"{chart.key}: позиции должны быть уникальными положительными числами.")
    # Один объект — одна позиция в замере (UNIQUE (run_id, trend_id)).
    # Если после нормализации объект встретился дважды, остаётся лучшая позиция.
    unique_entries, seen = [], set()
    for entry in entries:
        if entry["match_key"] not in seen:
            seen.add(entry["match_key"])
            unique_entries.append(entry)
    entries = unique_entries

    return {
        "type": "chart",
        "source": chart.source,
        "chart": chart.name,
        "category": chart.category,
        "week_start": week.isoformat(),
        "collected_at": _now(),
        "entries": entries,
    }


def build_failure_payload(chart: Chart | str, error: object, *, week: date | None = None) -> dict:
    """Пакет о неудачном сборе: в базе запуск получит статус failed."""
    if isinstance(chart, str):
        chart = CHARTS[chart]
    return {
        "type": "chart",
        "status": "failed",
        "source": chart.source,
        "chart": chart.name,
        "category": chart.category,
        "week_start": (week or week_start()).isoformat(),
        "collected_at": _now(),
        "error": (str(error) or type(error).__name__)[:1000],
    }


def _now() -> str:
    return datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")


def _endpoint(payload: dict) -> str:
    kind = payload.get("type")
    if kind == "search_stats":
        return SEARCH_STATS_ENDPOINT_PATH
    if kind == "game_audience_stats":
        return GAME_AUDIENCE_ENDPOINT_PATH
    return ENDPOINT_PATH


def _post_to(payload: dict, endpoint: str, backend_url: str, token: str, timeout: float) -> str:
    request = Request(
        backend_url.rstrip("/") + endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
        error.close()
        raise SaveError(f"бэкенд ответил HTTP {status}.") from None
    except (URLError, OSError):
        raise SaveError("бэкенд недоступен (ошибка сети или таймаут).") from None
    if not 200 <= status < 300:
        raise SaveError(f"бэкенд ответил HTTP {status}.")
    if "entries" in payload:
        return f"отправлено в бэкенд: {len(payload['entries'])} позиций"
    return "отправлено в бэкенд"


def _post(payload: dict, backend_url: str, token: str, timeout: float) -> str:
    return _post_to(payload, _endpoint(payload), backend_url, token, timeout)


def _file_stem(payload: dict) -> str:
    if payload.get("type") == "search_stats":
        parts = [payload["week_start"], "wordstat"]
    elif payload.get("type") == "game_audience_stats":
        parts = [payload["week_start"], "whatstat-games"]
    else:
        parts = [payload["week_start"], payload["source"], payload["chart"]]
        if payload.get("status") == "failed":
            # Отдельное имя: сбой не затирает ещё не загруженный успешный пакет.
            parts.append("failed")
    return re.sub(r"[^\w-]+", "_", "_".join(parts))


def _write_outbox(payload: dict, outbox_dir: Path) -> str:
    path = outbox_dir / f"{_file_stem(payload)}.json"
    try:
        outbox_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as error:
        raise SaveError(f"не удалось записать {path}: {error}") from None
    return f"BACKEND_URL не задан, пакет сохранён в {path}"


def save_payload(payload: dict, *, timeout: float = 30, outbox_dir: Path | None = None) -> str:
    """Отправляет готовый пакет в бэкенд или, без BACKEND_URL, пишет в data/outbox/."""
    settings = _settings()
    backend_url = (settings.get("BACKEND_URL") or "").strip()
    if not backend_url:
        return _write_outbox(payload, outbox_dir or OUTBOX_DIR)
    token = (settings.get("INTERNAL_API_TOKEN") or "").strip()
    if not token:
        raise SaveError("укажите INTERNAL_API_TOKEN в .env или окружении.")
    return _post(payload, backend_url, token, timeout)


def publish_rankings(*, timeout: float = 120) -> str:
    """Публикует заранее собранную неделю одним пересчётом рейтингов."""
    settings = _settings()
    backend_url = (settings.get("BACKEND_URL") or "").strip()
    if not backend_url:
        raise SaveError("для публикации рейтинга укажите BACKEND_URL в .env или окружении.")
    token = (settings.get("INTERNAL_API_TOKEN") or "").strip()
    if not token:
        raise SaveError("укажите INTERNAL_API_TOKEN в .env или окружении.")
    _post_to({}, PUBLISH_RANKINGS_ENDPOINT_PATH, backend_url, token, timeout)
    return "рейтинг опубликован"


def save_chart(chart: Chart | str, items: list[dict], *, week: date | None = None,
               timeout: float = 30, outbox_dir: Path | None = None) -> str:
    """Сохраняет чарт: отправляет в бэкенд или, без BACKEND_URL, пишет в data/outbox/.

    Возвращает описание результата; при неудаче бросает SaveError.
    """
    try:
        payload = build_payload(chart, items, week=week)
    except ValueError as error:
        raise SaveError(str(error)) from None
    return save_payload(payload, timeout=timeout, outbox_dir=outbox_dir)


def save_chart_failure(chart: Chart | str, error: object, *, week: date | None = None,
                       timeout: float = 30, outbox_dir: Path | None = None) -> str:
    """Сохраняет факт неудачного сбора, чтобы рейтинг не принял сбой за выпадение из чарта."""
    payload = build_failure_payload(chart, error, week=week)
    return save_payload(payload, timeout=timeout, outbox_dir=outbox_dir)


def resolve_limit(chart_key: str, requested: int | None, save: bool) -> int | None:
    """Лимит для запуска из командной строки: при --save не больше лимита категории."""
    if not save:
        return requested
    limit = CHARTS[chart_key].limit
    return limit if requested is None else min(requested, limit)


def add_save_argument(cli) -> None:
    cli.add_argument(
        "--save",
        action="store_true",
        help="Сохранить позиции: отправить в бэкенд (BACKEND_URL) или в data/outbox/",
    )


def save_or_exit(cli, chart_key: str, items: list[dict]) -> None:
    """Сохраняет чарт из командной строки; при ошибке завершает процесс с кодом 1.

    Сообщение пишется в stderr, чтобы stdout оставался корректным JSON.
    """
    try:
        message = save_chart(chart_key, items)
    except SaveError as error:
        cli.exit(1, f"Ошибка сохранения ({chart_key}): {error}\n")
    print(f"{chart_key}: {message}", file=sys.stderr)
