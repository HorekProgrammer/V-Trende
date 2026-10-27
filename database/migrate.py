"""Миграции схемы базы данных.

    python -m database.migrate                 # применить все новые миграции
    python -m database.migrate --status        # показать, что применено
    python -m database.migrate --target 003    # применить миграции до 003 включительно
    python -m database.migrate --baseline 001  # база уже создана из schema.sql:
                                               # отметить 001 применённой, не выполняя её

Миграции — файлы database/migrations/NNN_описание.sql. Каждая выполняется один раз,
в своей транзакции, и записывается в таблицу schema_migrations вместе с контрольной
суммой. Применённую миграцию менять нельзя: любое изменение схемы — новый файл.
"""

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .db import DatabaseConfigError, connect

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_FILE_RE = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")
# Произвольный постоянный ключ: не даёт двум процессам мигрировать одновременно.
_LOCK_KEY = 7_274_310

_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        # Переводы строк нормализуются: файл из Windows и Linux даёт одну сумму.
        return hashlib.sha256(self.sql.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILE_RE.match(path.name)
        if match is None:
            raise MigrationError(f"Имя миграции не по шаблону NNN_описание.sql: {path.name}")
        migrations.append(Migration(match.group(1), match.group(2), path.read_text(encoding="utf-8")))
    versions = [m.version for m in migrations]
    if len(set(versions)) != len(versions):
        raise MigrationError("Два файла миграций с одним номером.")
    return migrations


def applied_migrations(conn) -> dict[str, str]:
    conn.execute(_BOOTSTRAP)
    return dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())


def _check_history(migrations: list[Migration], applied: dict[str, str]) -> None:
    known = {m.version: m for m in migrations}
    for version, checksum in sorted(applied.items()):
        if version not in known:
            raise MigrationError(f"Миграция {version} применена к базе, но её файла нет.")
        if known[version].checksum != checksum:
            raise MigrationError(
                f"Файл миграции {version}_{known[version].name}.sql изменён после применения. "
                "Верните его и оформите изменение новой миграцией."
            )


def migrate(conn, *, directory: Path = MIGRATIONS_DIR, target: str | None = None,
            baseline: str | None = None) -> list[str]:
    """Применяет новые миграции; возвращает номера применённых."""
    migrations = discover(directory)
    for value in (target, baseline):
        if value is not None and value not in {m.version for m in migrations}:
            raise MigrationError(f"Нет миграции с номером {value}.")

    conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
    try:
        applied = applied_migrations(conn)
        _check_history(migrations, applied)

        if baseline is not None:
            with conn.transaction():
                for m in migrations:
                    if m.version <= baseline and m.version not in applied:
                        conn.execute(
                            "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                            (m.version, m.name, m.checksum),
                        )
                        applied[m.version] = m.checksum

        done = []
        for m in migrations:
            if m.version in applied or (target is not None and m.version > target):
                continue
            try:
                with conn.transaction():
                    conn.execute(m.sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                        (m.version, m.name, m.checksum),
                    )
            except Exception as error:
                raise MigrationError(f"Миграция {m.version}_{m.name} не применена: {error}") from None
            done.append(m.version)
        return done
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))


def status(conn, directory: Path = MIGRATIONS_DIR) -> list[tuple[str, str, bool]]:
    applied = applied_migrations(conn)
    return [(m.version, m.name, m.version in applied) for m in discover(directory)]


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Миграции базы данных «В-Тренде»")
    cli.add_argument("--status", action="store_true", help="Показать состояние миграций")
    cli.add_argument("--target", help="Применить миграции до этого номера включительно")
    cli.add_argument("--baseline", help="Отметить миграции до этого номера применёнными без выполнения")
    args = cli.parse_args(argv)
    try:
        with connect() as conn:
            if args.status:
                for version, name, is_applied in status(conn):
                    print(f"{'[x]' if is_applied else '[ ]'} {version}_{name}")
                return 0
            done = migrate(conn, target=args.target, baseline=args.baseline)
    except (DatabaseConfigError, MigrationError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    print(f"Применены миграции: {', '.join(done)}" if done else "Новых миграций нет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
