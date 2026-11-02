"""Fill missing primary genres for a weekly games top without overwriting known values."""

import argparse
import html
import json
import math
import re
import time
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database.db import connect
from parser.twitch.channel_classifier import CHAT_URL, SEARCH_URL, _post_json, _settings

STEAM_DETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAM_SEARCH_URL = "https://store.steampowered.com/search/suggest"
STEAM_APP_URL = "https://store.steampowered.com/app"
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
MIN_CONFIDENCE = 0.80
GENRES = ("Экшен", "RPG", "Стратегии", "Шутеры", "Инди", "Другое")

SHOOTER = ("shooter", "fps", "third-person shooter", "first-person shooter", "shoot 'em up")
MOBA = ("moba", "multiplayer online battle arena")
RPG = ("rpg", "role-playing", "role playing", "roguelike", "dungeon crawl", "souls-like", "soulslike")
STRATEGY = ("strategy", "strateg", "tower defense", "4x",
            "auto battler", "real-time tactics", "turn-based tactics", "card game")
ACTION = ("action", "fighting", "platform", "battle royale", "survival", "beat 'em up", "hack and slash")


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    value = value.replace("™", "").replace("®", "").replace("�", "")
    return " ".join(re.findall(r"[\w]+", value, flags=re.UNICODE))


def _search_title(value: str) -> str:
    value = value.replace("™", "").replace("®", "").replace("�", "")
    value = re.sub(r"\s*[-:]?\s*(standard|ultimate|deluxe) edition\s*$", "", value, flags=re.I)
    value = re.sub(r"\s*-\s*free access\s*$", "", value, flags=re.I)
    return value.strip()


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _norm(left), _norm(right)).ratio()


def classify_tags(tags: list[str]) -> str | None:
    values = [_norm(tag) for tag in tags if isinstance(tag, str) and tag.strip()]
    joined = " | ".join(values)
    if any(token in joined for token in SHOOTER):
        return "Шутеры"
    if any(token in joined for token in MOBA):
        return "Стратегии"
    if any(token in joined for token in RPG):
        return "RPG"
    if any(token in joined for token in STRATEGY):
        return "Стратегии"
    if any(token in joined for token in ACTION):
        return "Экшен"
    if any("indie" in value or "инди" in value for value in values):
        return "Инди"
    return "Другое" if values else None


def accept_deepseek_genre(answer: dict) -> str | None:
    if not isinstance(answer, dict) or answer.get("genre") not in GENRES:
        return None
    confidence = answer.get("confidence")
    if type(confidence) not in (int, float) or not math.isfinite(confidence):
        return None
    return answer["genre"] if confidence >= MIN_CONFIDENCE else None


def _get(url: str, timeout: float, *, pause: float = 0.0) -> bytes:
    request = Request(url, headers={
        "User-Agent": "V-Trende/1.0 (game metadata)",
        "Cookie": "birthtime=0; lastagecheckage=1-January-1970; mature_content=1",
    })
    for attempt in range(6):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
            if pause:
                time.sleep(pause)
            return body
        except HTTPError as error:
            error.close()
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(3 * (attempt + 1))
    return b""


def steam_tags(app_id: str, *, timeout: float = 30) -> list[str]:
    try:
        page = _get(f"{STEAM_APP_URL}/{app_id}/?cc=us&l=english", timeout).decode("utf-8", "replace")
        tags = [html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
                for value in re.findall(r'<a[^>]*class="app_tag"[^>]*>([\s\S]*?)</a>', page)]
        tags = [tag for tag in tags if tag]
        if tags:
            return tags
    except (HTTPError, URLError, OSError):
        pass
    query = urlencode({"appids": app_id, "cc": "us", "l": "english"})
    try:
        payload = json.loads(_get(f"{STEAM_DETAILS_URL}?{query}", timeout))
    except (HTTPError, URLError, OSError, ValueError):
        return []
    item = payload.get(str(app_id), {})
    data = item.get("data") if item.get("success") else None
    if not isinstance(data, dict):
        return []
    return [item["description"] for item in data.get("genres", [])
            if isinstance(item, dict) and isinstance(item.get("description"), str)]


def search_steam_app(title: str, *, timeout: float = 30) -> str | None:
    query = urlencode({"term": _search_title(title), "f": "games", "cc": "US", "l": "english", "v": 1})
    try:
        body = _get(f"{STEAM_SEARCH_URL}?{query}", timeout).decode("utf-8", "replace")
    except (HTTPError, URLError, OSError):
        return None
    matches = []
    for block in re.findall(r'<a[^>]+data-ds-appid="\d+"[\s\S]*?</a>', body):
        app = re.search(r'data-ds-appid="(\d+)"', block)
        name = re.search(r'class="match_name">([\s\S]*?)</div>', block)
        if app and name:
            candidate = html.unescape(re.sub(r"<[^>]+>", "", name.group(1))).strip()
            matches.append((_similarity(_search_title(title), candidate), app.group(1)))
    best = max(matches, default=None)
    return best[1] if best and best[0] >= 0.88 else None


def _wikidata(params: dict, timeout: float) -> dict:
    url = f"{WIKIDATA_URL}?{urlencode({'format': 'json', **params})}"
    return json.loads(_get(url, timeout, pause=0.5))


def wikidata_tags(title: str, *, timeout: float = 30) -> list[str]:
    cleaned = _search_title(title)
    try:
        search = _wikidata({"action": "wbsearchentities", "search": cleaned,
                            "language": "en", "limit": 8}, timeout)
        candidates = []
        for item in search.get("search", []):
            description = str(item.get("description") or "").casefold()
            if "video game" not in description and "game" not in description:
                continue
            score = _similarity(cleaned, str(item.get("label") or ""))
            if score >= 0.76:
                candidates.append((score, item["id"]))
        if not candidates:
            return []
        entity_id = max(candidates)[1]
        entity = _wikidata({"action": "wbgetentities", "ids": entity_id, "props": "claims"}, timeout)
        claims = entity["entities"][entity_id].get("claims", {}).get("P136", [])
        ids = [claim["mainsnak"]["datavalue"]["value"]["id"] for claim in claims
               if claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")]
        if not ids:
            return []
        labels = _wikidata({"action": "wbgetentities", "ids": "|".join(ids),
                            "props": "labels", "languages": "en"}, timeout)
        return [labels["entities"][item].get("labels", {}).get("en", {}).get("value", "") for item in ids]
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError):
        return []


def _deepseek_batch(games: list[dict], api_key: str, model: str, timeout: float) -> dict[int, str]:
    supplied = []
    for game in games:
        search = _post_json(SEARCH_URL, {"query": f'{game["title"]} игра жанр', "count": 5,
                                         "need_content": False}, api_key, timeout)
        supplied.append({"id": game["id"], "title": game["title"], "search_results": search.get("results", [])})
    prompt = f"""Classify each video game into exactly one primary genre from {json.dumps(GENRES, ensure_ascii=False)}.
Priority: shooter > RPG > strategy/MOBA > action/battle royale/survival > indie > other.
Return strict JSON only: {{"results":[{{"id":123,"genre":"Экшен","confidence":0.90}}]}}.
Confidence is from 0 to 1. Return every id. Data: {json.dumps(supplied, ensure_ascii=False)}"""
    response = _post_json(CHAT_URL, {"model": model, "messages": [
        {"role": "system", "content": "You are a careful video game metadata editor. Return strict JSON."},
        {"role": "user", "content": prompt}], "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"}, "max_tokens": 1200}, api_key, timeout)
    try:
        answers = json.loads(response["choices"][0]["message"]["content"])["results"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek вернул некорректный ответ о жанрах игр.") from None
    result = {}
    for answer in answers if isinstance(answers, list) else []:
        genre = accept_deepseek_genre(answer)
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
                              AND g.category = 'games' AND g.name = %s""", (trend_id, genre))
        conn.commit()


def fill_game_genres(week: date, *, timeout: float = 40) -> tuple[int, int]:
    with connect() as conn:
        rows = conn.execute("""SELECT t.id, t.title,
                   MAX(s.external_id) FILTER (WHERE s.source = 'steam') AS steam_app_id
               FROM mv_category_rank r JOIN trends t ON t.id = r.trend_id
               LEFT JOIN trend_source_items s ON s.trend_id = t.id
               WHERE r.week_start = %s AND r.category = 'games' AND r.rank <= 100
                 AND t.genre_id IS NULL
               GROUP BY r.rank, t.id, t.title ORDER BY r.rank""", (week,)).fetchall()
        games = [{"id": row[0], "title": row[1], "steam_app_id": row[2]} for row in rows]
    if not games:
        return 0, 0
    genres, pending = {}, []
    for game in games:
        app_id = game["steam_app_id"] or search_steam_app(game["title"], timeout=timeout)
        tags = steam_tags(str(app_id), timeout=timeout) if app_id else []
        # Steam orders tags by weight; the top five are the most representative.
        # the clearest description of a game. Lower tags must not override them.
        genre = classify_tags(tags[:5])
        if not genre:
            genre = classify_tags(wikidata_tags(game["title"], timeout=timeout))
        if genre:
            genres[game["id"]] = genre
        else:
            pending.append(game)
        time.sleep(0.25)
    # Persist deterministic public-source results before the optional AI fallback.
    # A DeepSeek outage must not discard Steam/Wikidata work.
    _save_genres(genres)
    saved = len(genres)
    if pending:
        settings = _settings()
        api_key = str(settings.get("DEEPSEEK_API") or "")
        if not api_key:
            raise RuntimeError("Для определения жанров игр нужен DEEPSEEK_API в .env.")
        model = str(settings.get("DEEPSEEK_MODEL") or "deepseek-flash")
        ai_genres = {}
        for start in range(0, len(pending), 10):
            ai_genres.update(_deepseek_batch(pending[start:start + 10], api_key, model, timeout))
        _save_genres(ai_genres)
        saved += len(ai_genres)
    return saved, len(games) - saved


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Заполнить отсутствующие жанры игрового топа")
    cli.add_argument("--week", required=True, type=date.fromisoformat)
    args = cli.parse_args(argv)
    saved, unknown = fill_game_genres(args.week)
    print(f"Жанры игр: сохранено {saved}, осталось без жанра {unknown}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
