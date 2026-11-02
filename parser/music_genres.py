"""Fill missing genres for a weekly music top: iTunes, then DeepSeek."""

import argparse
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

ITUNES_URL = "https://itunes.apple.com/search"
MIN_CONFIDENCE = 0.80
GENRES = ("Поп", "Рэп / Хип-хоп", "Рок", "Электроника", "Инди")
APPLE_GENRES = {
    "pop": "Поп", "russian pop": "Поп", "pop in russian": "Поп", "r&b/soul": "Поп",
    "r&b и соул": "Поп", "hip-hop/rap": "Рэп / Хип-хоп", "hip-hop": "Рэп / Хип-хоп",
    "хип-хоп": "Рэп / Хип-хоп", "russian hip-hop": "Рэп / Хип-хоп", "rock": "Рок",
    "рок": "Рок", "alternative": "Рок", "electronic": "Электроника",
    "электроника": "Электроника", "dance": "Электроника", "танцевальная": "Электроника",
    "house": "Электроника", "хаус": "Электроника", "techno": "Электроника",
    "техно": "Электроника", "ambient": "Электроника", "эмбиент": "Электроника",
    "indie pop": "Инди", "инди-поп": "Инди", "indie": "Инди", "инди": "Инди",
}


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return " ".join(re.findall(r"[\w]+", value, flags=re.UNICODE))


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _norm(left), _norm(right)).ratio()


def _artist_similarity(expected: str, actual: str) -> float:
    parts = [p.strip() for p in re.split(r"[,;&]|\bfeat\.?\b|\bft\.?\b", expected, flags=re.I) if p.strip()]
    return max((_similarity(part, actual) for part in parts), default=0.0)


def normalize_apple_genre(value: str) -> str | None:
    key = value.casefold().replace("\xa0", " ").strip()
    if key in APPLE_GENRES:
        return APPLE_GENRES[key]
    if "hip-hop" in key or "hip hop" in key or "рэп" in key:
        return "Рэп / Хип-хоп"
    if any(word in key for word in ("electronic", "dance", "house", "techno", "электрон")):
        return "Электроника"
    if "indie" in key or "инди" in key:
        return "Инди"
    if "rock" in key or "рок" in key:
        return "Рок"
    if "pop" in key or "поп" in key:
        return "Поп"
    return None


def _get_json(url: str, timeout: float) -> dict:
    request = Request(url, headers={"User-Agent": "V-Trende/1.0", "Accept": "application/json"})
    for attempt in range(5):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as error:
            error.close()
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def itunes_genre(track: dict, *, timeout: float = 30) -> tuple[str, float] | None:
    query = urlencode({"term": f'{track["subtitle"]} {track["title"]}', "country": "RU",
                       "media": "music", "entity": "song", "limit": 25})
    try:
        payload = _get_json(f"{ITUNES_URL}?{query}", timeout)
    except (HTTPError, URLError, OSError, ValueError):
        return None
    best = None
    for item in payload.get("results", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        title_score = _similarity(track["title"], str(item.get("trackName") or ""))
        artist_score = _artist_similarity(track["subtitle"], str(item.get("artistName") or ""))
        score = title_score * 0.7 + artist_score * 0.3
        genre = normalize_apple_genre(str(item.get("primaryGenreName") or ""))
        if genre and title_score >= 0.78 and artist_score >= 0.58 and (best is None or score > best[1]):
            best = (genre, score)
    return best


def accept_deepseek_genre(answer: dict) -> str | None:
    if not isinstance(answer, dict) or answer.get("genre") not in GENRES:
        return None
    confidence = answer.get("confidence")
    if type(confidence) not in (int, float) or not math.isfinite(confidence):
        return None
    return answer["genre"] if confidence >= MIN_CONFIDENCE else None


def _deepseek_batch(tracks: list[dict], api_key: str, model: str, timeout: float) -> dict[int, str]:
    supplied = []
    for track in tracks:
        search = _post_json(SEARCH_URL, {
            "query": f'{track["subtitle"]} {track["title"]} трек жанр', "count": 5,
            "need_content": False,
        }, api_key, timeout)
        supplied.append({
            "id": track["id"], "title": track["title"], "artist": track["subtitle"],
            "search_results": [{k: item.get(k) for k in ("title", "url", "snippet", "summary")}
                               for item in search.get("results", []) if isinstance(item, dict)],
        })
    prompt = f"""Classify every track into exactly one genre from {json.dumps(GENRES, ensure_ascii=False)}.
Use the specific track and search results. Return strict JSON only:
{{"results":[{{"id":123,"genre":"Поп","confidence":0.90}}]}}.
Confidence is from 0 to 1. Return every id. Data: {json.dumps(supplied, ensure_ascii=False)}"""
    response = _post_json(CHAT_URL, {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a careful music metadata editor. Return strict JSON."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"},
        "max_tokens": 1800,
    }, api_key, timeout)
    try:
        answers = json.loads(response["choices"][0]["message"]["content"])["results"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek вернул некорректный ответ о жанрах.") from None
    result = {}
    for answer in answers if isinstance(answers, list) else []:
        genre = accept_deepseek_genre(answer)
        if genre and type(answer.get("id")) is int:
            result[answer["id"]] = genre
    return result


def fill_music_genres(week: date, *, timeout: float = 40) -> tuple[int, int]:
    """Return (saved, unknown); rows with an existing genre are never requested."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT t.id, t.title, COALESCE(t.subtitle, '') AS subtitle
               FROM mv_category_rank r JOIN trends t ON t.id = r.trend_id
               WHERE r.week_start = %s AND r.category = 'music' AND r.rank <= 100
                 AND t.genre_id IS NULL ORDER BY r.rank""", (week,)).fetchall()
        tracks = [{"id": row[0], "title": row[1], "subtitle": row[2]} for row in rows]
    if not tracks:
        return 0, 0
    genres, pending = {}, []
    for track in tracks:
        match = itunes_genre(track, timeout=timeout)
        if match:
            genres[track["id"]] = match[0]
        else:
            pending.append(track)
        time.sleep(0.35)
    if pending:
        settings = _settings()
        api_key = str(settings.get("DEEPSEEK_API") or "")
        if not api_key:
            raise RuntimeError("Для определения жанров нужен DEEPSEEK_API в .env.")
        model = str(settings.get("DEEPSEEK_MODEL") or "deepseek-flash")
        for start in range(0, len(pending), 10):
            genres.update(_deepseek_batch(pending[start:start + 10], api_key, model, timeout))
    with connect() as conn:
        for trend_id, genre in genres.items():
            conn.execute("""UPDATE trends t SET genre_id = g.id FROM genres g
                            WHERE t.id = %s AND t.genre_id IS NULL
                              AND g.category = 'music' AND g.name = %s""", (trend_id, genre))
        conn.commit()
    return len(genres), len(tracks) - len(genres)


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Заполнить отсутствующие жанры музыкального топа")
    cli.add_argument("--week", required=True, type=date.fromisoformat)
    args = cli.parse_args(argv)
    saved, unknown = fill_music_genres(args.week)
    print(f"Жанры: сохранено {saved}, осталось без жанра {unknown}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
