"""Refresh weekly streamer genres exclusively from TwitchTracker categories."""

import argparse
import html
import re
import time
from datetime import date
from urllib.parse import quote, urlencode
from urllib.request import Request

from database.db import connect
from parser.twitch.twitch_parser import PROFILE_URL, RANKING_URL, _HEADERS, _channel_bootstrap, _read

GENRES = ("Игры", "Just Chatting")
TRACKER_PAUSE_SECONDS = 1.0

JUST_CHATTING_CATEGORIES = {
    "just chatting", "talk shows & podcasts", "asmr", "politics", "special events",
    "watch parties", "co-working & studying", "always on",
}

# Separate Twitch sections are neither games nor Just Chatting and are ignored.
# Any other category is a game title.
IGNORED_CATEGORIES = {
    "music", "djs", "art", "makers & crafting", "software and game development",
    "science & technology", "beauty & body art", "writing & reading", "irl",
    "travel & outdoors", "food & drink", "sports", "fitness & health",
    "animals, aquariums, and zoos", "pools, hot tubs, and beaches", "i'm only sleeping",
}

_GAMES_BLOCK_RE = re.compile(r'id="channel-games"([\s\S]*?)(?:</section>|$)')
_CATEGORY_RE = re.compile(
    r'<a class="entity" href="/[^"/]+/games/\d+">\s*<div title="([^"]*)"[\s\S]*?class="to-time">(\d+)<'
)


def categories_from_fragments(page: str) -> list[tuple[str, int]]:
    block = _GAMES_BLOCK_RE.search(page or "")
    if block is None:
        return []
    return [(html.unescape(title).strip(), int(minutes)) for title, minutes in _CATEGORY_RE.findall(block.group(1))]


def genres_from_categories(categories: list[tuple[str, int]]) -> list[str]:
    """Return every supported genre present, ordered by streamed minutes."""
    totals = {genre: 0 for genre in GENRES}
    for title, minutes in categories:
        if not title or minutes <= 0:
            continue
        normalized = title.casefold()
        if normalized in JUST_CHATTING_CATEGORIES:
            totals["Just Chatting"] += minutes
        elif normalized not in IGNORED_CATEGORIES:
            totals["Игры"] += minutes
    return sorted((genre for genre, minutes in totals.items() if minutes > 0), key=totals.get, reverse=True)


def twitchtracker_categories(slug: str, *, timeout: float = 30) -> list[tuple[str, int]] | None:
    """Return categories, or None when TwitchTracker could not be reached."""
    profile_url = PROFILE_URL.format(channel=quote(slug))
    try:
        profile = _read(Request(profile_url, headers={**_HEADERS, "Referer": RANKING_URL}),
                        timeout, f"канал {slug}")
        channel_id, fragments_url = _channel_bootstrap(profile, slug)
        request = Request(fragments_url, data=urlencode({"id": channel_id}).encode("ascii"), method="POST",
                          headers={**_HEADERS, "Referer": profile_url, "X-Requested-With": "XMLHttpRequest"})
        return categories_from_fragments(_read(request, timeout, f"статистика канала {slug}"))
    except RuntimeError:
        return None


def _save_genres(genres: dict[int, list[str]]) -> None:
    """Replace genres for successfully checked channels, including empty results."""
    if not genres:
        return
    with connect() as conn:
        for trend_id, names in genres.items():
            names = [name for name in dict.fromkeys(names) if name in GENRES]
            conn.execute("DELETE FROM trend_genres WHERE trend_id = %s", (trend_id,))
            conn.execute(
                "UPDATE trends SET genre_id = NULL, genres_resolved_at = NOW() WHERE id = %s",
                (trend_id,),
            )
            if not names:
                continue
            conn.execute("""UPDATE trends t SET genre_id = g.id FROM genres g
                            WHERE t.id = %s AND g.category = 'streamers' AND g.name = %s""",
                         (trend_id, names[0]))
            for position, name in enumerate(names[1:], 2):
                conn.execute("""INSERT INTO trend_genres (trend_id, genre_id, category, position)
                                SELECT %s, id, 'streamers', %s FROM genres
                                WHERE category = 'streamers' AND name = %s""",
                             (trend_id, position, name))
        conn.commit()


def fill_streamer_genres(week: date, *, timeout: float = 40, log=print) -> tuple[int, int]:
    """Refresh all weekly streamer genres; return (classified, unavailable/empty)."""
    with connect() as conn:
        rows = conn.execute("""SELECT t.id, t.title,
                   COALESCE(MAX(s.external_id) FILTER (WHERE s.source = 'twitch'), t.match_key) AS slug
               FROM mv_category_rank r JOIN trends t ON t.id = r.trend_id
               LEFT JOIN trend_source_items s ON s.trend_id = t.id
               WHERE r.week_start = %s AND r.category = 'streamers'
               GROUP BY r.rank, t.id, t.title, t.match_key ORDER BY r.rank""", (week,)).fetchall()
        channels = [{"id": row[0], "title": row[1], "slug": row[2]} for row in rows]

    refreshed = {}
    classified = 0
    for channel in channels:
        categories = twitchtracker_categories(channel["slug"], timeout=timeout)
        if categories is None:
            log(f"  {channel['title']}: TwitchTracker недоступен, прежние жанры сохранены")
        else:
            genres = genres_from_categories(categories)
            refreshed[channel["id"]] = genres
            if genres:
                classified += 1
                log(f"  {channel['title']}: {', '.join(genres)}")
            else:
                log(f"  {channel['title']}: нет категорий Игры или Just Chatting")
        time.sleep(TRACKER_PAUSE_SECONDS)

    _save_genres(refreshed)
    return classified, len(channels) - classified


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Обновить жанры стримеров по TwitchTracker")
    cli.add_argument("--week", required=True, type=date.fromisoformat)
    args = cli.parse_args(argv)
    saved, unknown = fill_streamer_genres(args.week)
    print(f"Жанры стримеров: определено {saved}, без поддерживаемого жанра {unknown}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
