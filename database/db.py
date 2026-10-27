"""Подключение к PostgreSQL.

Адрес базы берётся из переменной DATABASE_URL (.env или окружение), например:
    DATABASE_URL=postgresql://postgres:password@localhost:5432/vtrende
"""

import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


class DatabaseConfigError(RuntimeError):
    """Не задан адрес базы или не установлен драйвер."""


def settings() -> dict:
    return {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}


def database_url(variable: str = "DATABASE_URL") -> str:
    url = (settings().get(variable) or "").strip()
    if not url:
        raise DatabaseConfigError(f"Укажите {variable} в .env или окружении.")
    return url


def connect(url: str | None = None):
    """Соединение в режиме autocommit: атомарность задаётся блоками conn.transaction()."""
    try:
        import psycopg
    except ImportError:
        raise DatabaseConfigError(
            "Не установлен драйвер PostgreSQL: pip install -r requirements.txt"
        ) from None
    try:
        return psycopg.connect(url or database_url(), autocommit=True)
    except psycopg.Error as error:
        raise DatabaseConfigError(f"Не удалось подключиться к базе: {error}") from None
