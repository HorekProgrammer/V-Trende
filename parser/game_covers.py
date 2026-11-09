import argparse
import html
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from database.db import connect

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = PROJECT_ROOT / "data" / "stopgame_covers.json"
SOURCE = "stopgame"
GAME_URL = "https://stopgame.ru/game/{}"
PAUSE_SECONDS = 1.5
RETRY_AFTER_SECONDS = 15
RECHECK_AFTER = timedelta(days=30)
MAX_NETWORK_ERRORS = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

ROMAN = {"2": "ii", "3": "iii", "4": "iv", "5": "v", "6": "vi", "7": "vii", "8": "viii", "9": "ix", "10": "x"}
EDITION_RE = re.compile(
    r"\s+(?:enhanced|legacy|remastered|rebirth|free access|"
    r"(?:standard|ultimate|definitive|deluxe|gold) edition)\s*$",
    re.I,
)
SQUARE_RE = re.compile(
    r"https://images\.stopgame\.ru/games/logos/\d+/c\d+x\d+/[^\"'\s)]+?-square[^\"'\s)/]*?\.(?:jpe?g|png|webp)"
)
STEAM_RE = re.compile(r"store\.steampowered\.com/app/(\d+)")
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

GAMES_SQL = """
SELECT t.id, t.title,
       (SELECT s.external_id FROM trend_source_items s
        WHERE s.trend_id = t.id AND s.source = 'steam' AND s.external_id IS NOT NULL
        ORDER BY s.id LIMIT 1) AS steam_id
FROM trends t
WHERE t.category = 'games'
  AND COALESCE(t.cover_source, '') NOT IN (%s, 'manual')
ORDER BY t.id
"""


class NetworkError(Exception):
    pass


def slugify(title: str) -> str:
    text = unicodedata.normalize("NFKC", re.sub(r"[™®©℠]", "", title)).lower()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def candidate_slugs(title: str) -> list[str]:
    clean = re.sub(r"[™®©℠]", "", title).strip()
    variants = [clean]
    for separator in (":", " - ", " – ", " — "):
        if separator in clean:
            variants.append(clean.split(separator)[0])
    variants += [EDITION_RE.sub("", v) for v in list(variants)]
    variants += [re.sub(r"['’]", "", v) for v in list(variants)]
    variants += [re.sub(r"\.(?=\w)", "", v) for v in list(variants)]
    variants += [re.sub(r"^the\s+", "", v, flags=re.I) for v in list(variants)]
    variants += [re.sub(r"\b(10|[2-9])\b", lambda m: ROMAN[m.group(1)], v) for v in list(variants)]
    slugs = []
    for variant in variants:
        slug = slugify(variant)
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def parse_page(page: str) -> dict:
    square = SQUARE_RE.search(page)
    h1 = H1_RE.search(page)
    title = html.unescape(TAG_RE.sub("", h1.group(1))).strip() if h1 else None
    return {
        "cover_url": square.group(0) if square else None,
        "steam_ids": set(STEAM_RE.findall(page)),
        "title": title.removesuffix(" игра").strip() if title else None,
    }


def matches(game: dict, page: dict) -> bool:
    if not page["cover_url"]:
        return False
    steam_id = game.get("steam_id")
    if steam_id and page["steam_ids"]:
        return steam_id in page["steam_ids"]
    return bool(page["title"]) and slugify(page["title"]) in candidate_slugs(game["title"])


def _fetch(url: str) -> str | None:
    for attempt in range(2):
        time.sleep(PAUSE_SECONDS)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"})
        try:
            with urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", "replace")
        except HTTPError as error:
            error.close()
            if error.code == 404:
                return None
            if error.code in (429, 503) and attempt == 0:
                time.sleep(RETRY_AFTER_SECONDS)
                continue
            raise NetworkError(f"HTTP {error.code}") from None
        except (URLError, OSError) as error:
            if attempt == 0:
                continue
            raise NetworkError(str(error)) from None
    raise NetworkError("нет ответа")


def find_cover(game: dict) -> str | None:
    for slug in candidate_slugs(game["title"]):
        page = _fetch(GAME_URL.format(slug))
        if page is None:
            continue
        info = parse_page(page)
        if matches(game, info):
            return info["cover_url"]
    return None


def _load_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def _recently_missed(entry, now: datetime) -> bool:
    try:
        checked = datetime.fromisoformat(entry["checked_at"])
    except (TypeError, KeyError, ValueError):
        return False
    return now - checked < RECHECK_AFTER


def fill_game_covers(conn, *, limit: int | None = None, recheck: bool = False,
                     cache_path: Path = CACHE_PATH, log=print) -> dict:
    now = datetime.now(timezone.utc)
    cache = _load_cache(cache_path)
    columns = ("id", "title", "steam_id")
    games = [dict(zip(columns, row)) for row in conn.execute(GAMES_SQL, (SOURCE,)).fetchall()]
    if not recheck:
        games = [g for g in games if not _recently_missed(cache.get(str(g["id"])), now)]
    if limit is not None:
        games = games[:limit]

    stats = {"checked": 0, "found": 0, "missing": 0, "errors": 0}
    errors_in_row = 0
    for game in games:
        try:
            cover = find_cover(game)
        except NetworkError as error:
            stats["errors"] += 1
            errors_in_row += 1
            log(f"  {game['title']}: ошибка сети ({error})")
            if errors_in_row >= MAX_NETWORK_ERRORS:
                log("  StopGame не отвечает, остальные игры проверим в следующий раз")
                break
            continue
        errors_in_row = 0
        stats["checked"] += 1
        if cover:
            conn.execute(
                "UPDATE trends SET cover_url = %s, cover_source = %s WHERE id = %s",
                (cover, SOURCE, game["id"]),
            )
            cache.pop(str(game["id"]), None)
            stats["found"] += 1
            log(f"  {game['title']}: обложка найдена")
        else:
            cache[str(game["id"])] = {"title": game["title"], "checked_at": now.isoformat()}
            stats["missing"] += 1
            log(f"  {game['title']}: нет на StopGame")
        _save_cache(cache_path, cache)
    return stats


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Квадратные обложки игр со StopGame")
    cli.add_argument("--limit", type=int, help="Проверить не больше N игр")
    cli.add_argument("--recheck", action="store_true",
                     help="Заново проверить игры, которых недавно не нашлось")
    args = cli.parse_args(argv)
    with connect() as conn:
        stats = fill_game_covers(conn, limit=args.limit, recheck=args.recheck)
    print(
        f"Проверено {stats['checked']}, найдено {stats['found']}, "
        f"нет на StopGame {stats['missing']}, ошибок сети {stats['errors']}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
