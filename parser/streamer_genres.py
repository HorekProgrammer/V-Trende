"""Fill missing genres for the weekly streamers top: TwitchTracker categories, then DeepSeek."""

import argparse
import html
import json
import math
import re
import time
from datetime import date
from urllib.parse import quote, urlencode
from urllib.request import Request

from database.db import connect
from parser.twitch.channel_classifier import CHAT_URL, SEARCH_URL, _post_json, _settings
from parser.twitch.twitch_parser import PROFILE_URL, RANKING_URL, _HEADERS, _channel_bootstrap, _read

MIN_CONFIDENCE = 0.80
GENRES = ("Игры", "Just Chatting", "Музыка", "IRL", "Творчество")
BATCH_SIZE = 10
TRACKER_PAUSE_SECONDS = 1.0

CATEGORY_GENRES = {
    "just chatting": "Just Chatting",
    "talk shows & podcasts": "Just Chatting",
    "asmr": "Just Chatting",
    "politics": "Just Chatting",
    "special events": "Just Chatting",
    "watch parties": "Just Chatting",
    "co-working & studying": "Just Chatting",
    "always on": "Just Chatting",
    "music": "Музыка",
    "djs": "Музыка",
    "art": "Творчество",
    "makers & crafting": "Творчество",
    "software and game development": "Творчество",
    "science & technology": "Творчество",
    "beauty & body art": "Творчество",
    "writing & reading": "Творчество",
    "irl": "IRL",
    "travel & outdoors": "IRL",
    "food & drink": "IRL",
    "sports": "IRL",
    "fitness & health": "IRL",
    "animals, aquariums, and zoos": "IRL",
    "pools, hot tubs, and beaches": "IRL",
    "i'm only sleeping": "IRL",
}
_GAMES_BLOCK_RE = re.compile(r'id="channel-games"([\s\S]*?)(?:</section>|$)')
_CATEGORY_RE = re.compile(
    r'<a class="entity" href="/[^"/]+/games/\d+">\s*<div title="([^"]*)"[\s\S]*?class="to-time">(\d+)<'
)

CHATTING_REFINEMENT = ("Just Chatting", "IRL")

GUIDE = """Genres:
- "Игры": most streams are playing video games.
- "Just Chatting": talking with chat, watching and reacting to videos, talk shows, podcasts.
- "Музыка": music performances, singing, DJ sets, music production.
- "IRL": streams outside the studio: walks, travel, cooking, sports, real-life events.
- "Творчество": drawing, art, crafts, programming and other making things on stream.
Pick the genre of what the channel streams most often."""

REFINEMENT_NOTE = """All these channels stream mostly in the Twitch category "Just Chatting".
Answer "IRL" only if most of their streams happen outside: walks, travel, trips, events.
Studio talk, reactions and watching videos stay "Just Chatting"."""


def categories_from_fragments(page: str) -> list[tuple[str, int]]:
    block = _GAMES_BLOCK_RE.search(page or "")
    if block is None:
        return []
    return [(html.unescape(title).strip(), int(minutes)) for title, minutes in _CATEGORY_RE.findall(block.group(1))]


def main_category(categories: list[tuple[str, int]]) -> str | None:
    best = max(categories, key=lambda item: item[1], default=None)
    return best[0] if best else None


def genre_from_categories(categories: list[tuple[str, int]]) -> str | None:
    totals = {}
    for title, minutes in categories:
        if not title or minutes <= 0:
            continue
        genre = CATEGORY_GENRES.get(title.casefold(), "Игры")
        totals[genre] = totals.get(genre, 0) + minutes
    if not totals:
        return None
    return max(totals, key=totals.get)


def twitchtracker_categories(slug: str, *, timeout: float = 30) -> list[tuple[str, int]]:
    profile_url = PROFILE_URL.format(channel=quote(slug))
    try:
        profile = _read(Request(profile_url, headers={**_HEADERS, "Referer": RANKING_URL}),
                        timeout, f"канал {slug}")
        channel_id, fragments_url = _channel_bootstrap(profile, slug)
        request = Request(fragments_url, data=urlencode({"id": channel_id}).encode("ascii"), method="POST",
                          headers={**_HEADERS, "Referer": profile_url, "X-Requested-With": "XMLHttpRequest"})
        return categories_from_fragments(_read(request, timeout, f"статистика канала {slug}"))
    except RuntimeError:
        return []


def accept_deepseek_genre(answer: dict, allowed: tuple[str, ...] = GENRES) -> str | None:
    if not isinstance(answer, dict) or answer.get("genre") not in allowed:
        return None
    confidence = answer.get("confidence")
    if type(confidence) not in (int, float) or not math.isfinite(confidence):
        return None
    return answer["genre"] if confidence >= MIN_CONFIDENCE else None


def _deepseek_batch(channels: list[dict], api_key: str, model: str, timeout: float,
                    allowed: tuple[str, ...] = GENRES) -> dict[int, str]:
    supplied = []
    for channel in channels:
        search = _post_json(SEARCH_URL, {"query": f'{channel["title"]} {channel["slug"]} twitch стример',
                                         "count": 5, "need_content": False}, api_key, timeout)
        supplied.append({
            "id": channel["id"], "channel": channel["title"], "twitch": channel["slug"],
            "search_results": [{k: item.get(k) for k in ("title", "url", "snippet", "summary")}
                               for item in search.get("results", []) if isinstance(item, dict)],
        })
    prompt = f"""Classify each Russian-speaking Twitch channel into exactly one genre from {json.dumps(allowed, ensure_ascii=False)}.
{GUIDE}
{REFINEMENT_NOTE if allowed == CHATTING_REFINEMENT else ""}
Return strict JSON only: {{"results":[{{"id":123,"genre":"Игры","confidence":0.90}}]}}.
Confidence is from 0 to 1. Return every id. Data: {json.dumps(supplied, ensure_ascii=False)}"""
    response = _post_json(CHAT_URL, {"model": model, "messages": [
        {"role": "system", "content": "You are a careful streaming metadata editor. Return strict JSON."},
        {"role": "user", "content": prompt}], "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"}, "max_tokens": 1200}, api_key, timeout)
    try:
        answers = json.loads(response["choices"][0]["message"]["content"])["results"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek вернул некорректный ответ о жанрах стримеров.") from None
    result = {}
    for answer in answers if isinstance(answers, list) else []:
        genre = accept_deepseek_genre(answer, allowed)
        if genre and type(answer.get("id")) is int:
            result[answer["id"]] = genre
    return result


def _save_genres(genres: dict[int, str]) -> None:
    if not genres:
        return
    with connect() as conn:
        for trend_id, genre in genres.items():
            conn.execute("""UPDATE trends t SET genre_id = g.id FROM genres g
                            WHERE t.id = %s AND t.genre_id IS NULL
                              AND g.category = 'streamers' AND g.name = %s""", (trend_id, genre))
        conn.commit()


def _api_settings() -> tuple[str, str]:
    settings = _settings()
    return str(settings.get("DEEPSEEK_API") or ""), str(settings.get("DEEPSEEK_MODEL") or "deepseek-flash")


def _ask_deepseek(channels: list[dict], api_key: str, model: str, timeout: float,
                  allowed: tuple[str, ...] = GENRES) -> dict[int, str]:
    result = {}
    for start in range(0, len(channels), BATCH_SIZE):
        result.update(_deepseek_batch(channels[start:start + BATCH_SIZE], api_key, model, timeout, allowed))
    return result


def fill_streamer_genres(week: date, *, timeout: float = 40, log=print) -> tuple[int, int]:
    """Return (saved, unknown); rows with an existing genre are never requested."""
    with connect() as conn:
        rows = conn.execute("""SELECT t.id, t.title,
                   COALESCE(MAX(s.external_id) FILTER (WHERE s.source = 'twitch'), t.match_key) AS slug
               FROM mv_category_rank r JOIN trends t ON t.id = r.trend_id
               LEFT JOIN trend_source_items s ON s.trend_id = t.id
               WHERE r.week_start = %s AND r.category = 'streamers' AND t.genre_id IS NULL
               GROUP BY r.rank, t.id, t.title, t.match_key ORDER BY r.rank""", (week,)).fetchall()
        channels = [{"id": row[0], "title": row[1], "slug": row[2]} for row in rows]
    if not channels:
        return 0, 0
    genres, chatting, pending = {}, [], []
    for channel in channels:
        categories = twitchtracker_categories(channel["slug"], timeout=timeout)
        genre = genre_from_categories(categories)
        if genre:
            log(f"  {channel['title']}: {genre} (больше всего: {main_category(categories)})")
            genres[channel["id"]] = genre
            if genre == "Just Chatting":
                chatting.append(channel)
        else:
            log(f"  {channel['title']}: нет данных TwitchTracker")
            pending.append(channel)
        time.sleep(TRACKER_PAUSE_SECONDS)

    api_key, model = _api_settings()
    if chatting and api_key:
        titles = {channel["id"]: channel["title"] for channel in chatting}
        refined = _ask_deepseek(chatting, api_key, model, timeout, CHATTING_REFINEMENT)
        for trend_id, genre in refined.items():
            if genre == "IRL":
                genres[trend_id] = "IRL"
                log(f"  {titles[trend_id]}: уточнено как IRL")
    _save_genres(genres)
    saved = len(genres)
    if pending:
        if not api_key:
            raise RuntimeError("Для определения жанров стримеров нужен DEEPSEEK_API в .env.")
        ai_genres = _ask_deepseek(pending, api_key, model, timeout)
        _save_genres(ai_genres)
        saved += len(ai_genres)
    return saved, len(channels) - saved


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Заполнить отсутствующие жанры стримеров")
    cli.add_argument("--week", required=True, type=date.fromisoformat)
    args = cli.parse_args(argv)
    saved, unknown = fill_streamer_genres(args.week)
    print(f"Жанры стримеров: сохранено {saved}, осталось без жанра {unknown}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
