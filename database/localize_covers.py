"""Move cover URLs already stored in PostgreSQL into local media storage."""

import argparse
import sys

from .db import DatabaseConfigError, connect
from .image_store import ImageDownloadError, is_local_cover, localize_image


def localize_existing_covers(conn, *, limit: int | None = None, timeout: float = 25,
                             log=print) -> dict[str, int]:
    sql = """SELECT id, title, cover_url FROM trends
             WHERE cover_url IS NOT NULL AND cover_url LIKE 'https://%%'
             ORDER BY id"""
    params: tuple = ()
    if limit is not None:
        sql += " LIMIT %s"
        params = (limit,)
    rows = conn.execute(sql, params).fetchall()
    stats = {"checked": 0, "saved": 0, "failed": 0}
    for trend_id, title, source_url in rows:
        stats["checked"] += 1
        try:
            local_url = localize_image(source_url, timeout=timeout)
        except ImageDownloadError as error:
            stats["failed"] += 1
            log(f"{title}: download failed ({error})")
            continue
        if not is_local_cover(local_url):
            stats["failed"] += 1
            continue
        cursor = conn.execute(
            "UPDATE trends SET cover_url = %s WHERE id = %s AND cover_url = %s",
            (local_url, trend_id, source_url),
        )
        stats["saved"] += cursor.rowcount
    return stats


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Download external covers to local media storage")
    cli.add_argument("--limit", type=int, help="Process no more than N database rows")
    cli.add_argument("--timeout", type=float, default=25, help="Download timeout per image")
    args = cli.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        cli.error("--limit must be positive")
    try:
        with connect() as conn:
            stats = localize_existing_covers(conn, limit=args.limit, timeout=args.timeout)
    except DatabaseConfigError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print("Covers: checked {checked}, saved {saved}, failed {failed}".format(**stats))
    return 0 if stats["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
