"""Fill missing genres for weekly movie charts: Kinopoisk film page, Wikidata, then DeepSeek."""

import argparse
import json
import math
import re
import time
import unicodedata
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database.db import connect
from parser.twitch.channel_classifier import CHAT_URL, SEARCH_URL, _post_json, _settings

FILM_URL = "https://www.kinopoisk.ru/film/{}/"
KINOPOISK_PAUSE_MS = 700
KINOPOISK_MAX_MISSES = 3
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
KINOPOISK_PROPERTY = "P2603"
GENRE_PROPERTY = "P136"
MIN_CONFIDENCE = 0.80
GENRES = ("Фантастика", "Боевик", "Триллер", "Комедия", "Драма", "Другое")

RULES = (
    ("Фантастика", ("science fiction", "sci fi", "fantasy", "superhero", "cyberpunk", "space opera",
                    "фантаст", "фэнтези", "супергеро")),
    ("Боевик", ("action", "war film", "martial arts", "spy", "disaster", "боевик", "военн")),
    ("Триллер", ("thriller", "horror", "crime", "mystery", "detective", "neo noir", "film noir",
                 "триллер", "ужас", "криминал", "детектив")),
    ("Комедия", ("comedy", "parody", "satire", "комед", "пароди")),
    ("Драма", ("drama", "biographical", "romance", "romantic", "historical", "melodrama",
               "драма", "биограф", "мелодрам", "истори")),
)


FIND_GENRES_JS = """
() => {
    const found = [];
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
            const data = JSON.parse(script.textContent);
            for (const item of Array.isArray(data) ? data : [data]) {
                const genre = item && item.genre;
                if (Array.isArray(genre)) found.push(...genre);
                else if (typeof genre === 'string') found.push(genre);
            }
        } catch (error) {}
    }
    if (!found.length) {
        const label = [...document.querySelectorAll('div, span, dt, td')]
            .find(element => element.children.length === 0 && element.textContent.trim() === 'Жанр');
        for (const row of [label && label.parentElement, label && label.parentElement && label.parentElement.parentElement]) {
            if (!row || found.length) continue;
            for (const link of row.querySelectorAll('a')) found.push(link.textContent);
        }
    }
    return found.map(value => String(value).trim()).filter(value => value && value !== 'слова').slice(0, 10);
}
"""


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return " ".join(re.findall(r"[\w]+", value, flags=re.UNICODE))


def classify_labels(labels: list[str]) -> str | None:
    values = [_norm(label) for label in labels if isinstance(label, str) and label.strip()]
    if not values:
        return None
    joined = " | ".join(values)
    for genre, tokens in RULES:
        if any(token in joined for token in tokens):
            return genre
    return "Другое"


def accept_deepseek_genre(answer: dict) -> str | None:
    if not isinstance(answer, dict) or answer.get("genre") not in GENRES:
        return None
    confidence = answer.get("confidence")
    if type(confidence) not in (int, float) or not math.isfinite(confidence):
        return None
    return answer["genre"] if confidence >= MIN_CONFIDENCE else None


def _wikidata(params: dict, timeout: float) -> dict:
    url = f"{WIKIDATA_URL}?{urlencode({'format': 'json', **params})}"
    request = Request(url, headers={"User-Agent": "V-Trende/1.0 (movie metadata)"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read())
            time.sleep(0.3)
            return payload
        except HTTPError as error:
            error.close()
            if error.code != 429 or attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    return {}


def wikidata_labels(kinopoisk_id: str, *, timeout: float = 30) -> list[str]:
    if not kinopoisk_id or not str(kinopoisk_id).isdigit():
        return []
    try:
        search = _wikidata({"action": "query", "list": "search", "srlimit": 1,
                            "srsearch": f"haswbstatement:{KINOPOISK_PROPERTY}={kinopoisk_id}"}, timeout)
        hits = search.get("query", {}).get("search", [])
        if not hits:
            return []
        entity_id = hits[0]["title"]
        entity = _wikidata({"action": "wbgetentities", "ids": entity_id, "props": "claims"}, timeout)
        claims = entity["entities"][entity_id].get("claims", {}).get(GENRE_PROPERTY, [])
        ids = [claim["mainsnak"]["datavalue"]["value"]["id"] for claim in claims
               if claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")]
        if not ids:
            return []
        labels = _wikidata({"action": "wbgetentities", "ids": "|".join(ids[:20]),
                            "props": "labels", "languages": "en|ru"}, timeout)
        result = []
        for item in ids[:20]:
            item_labels = labels["entities"][item].get("labels", {})
            for language in ("en", "ru"):
                value = item_labels.get(language, {}).get("value")
                if value:
                    result.append(value)
        return result
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, IndexError):
        return []


def kinopoisk_genres(movies: list[dict], *, timeout: float = 40) -> dict[int, list[str]]:
    films = [movie for movie in movies if str(movie.get("kinopoisk_id") or "").isdigit()]
    if not films:
        return {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}
    result, misses = {}, 0
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="chromium")
            try:
                page = browser.new_context(locale="ru-RU", viewport={"width": 1400, "height": 900}).new_page()
                for movie in films:
                    if misses >= KINOPOISK_MAX_MISSES:
                        break
                    try:
                        page.goto(FILM_URL.format(movie["kinopoisk_id"]), wait_until="domcontentloaded",
                                  timeout=timeout * 1000)
                        try:
                            page.wait_for_selector('script[type="application/ld+json"]', timeout=5000)
                        except Exception:  # noqa: BLE001
                            pass
                        labels = page.evaluate(FIND_GENRES_JS)
                    except Exception:  # noqa: BLE001
                        labels = []
                    if isinstance(labels, list) and labels:
                        result[movie["id"]] = [str(label) for label in labels]
                        misses = 0
                    else:
                        misses += 1
                    page.wait_for_timeout(KINOPOISK_PAUSE_MS)
            finally:
                browser.close()
    except Exception:  # noqa: BLE001
        return result
    return result


def _deepseek_batch(movies: list[dict], api_key: str, model: str, timeout: float) -> dict[int, str]:
    supplied = []
    for movie in movies:
        year = f" {movie['year']}" if movie.get("year") else ""
        search = _post_json(SEARCH_URL, {"query": f'{movie["title"]}{year} фильм жанр', "count": 5,
                                         "need_content": False}, api_key, timeout)
        supplied.append({
            "id": movie["id"], "title": movie["title"], "year": movie.get("year"),
            "search_results": [{k: item.get(k) for k in ("title", "url", "snippet", "summary")}
                               for item in search.get("results", []) if isinstance(item, dict)],
        })
    prompt = f"""Classify each movie into exactly one primary genre from {json.dumps(GENRES, ensure_ascii=False)}.
Priority: science fiction/fantasy/superhero > action/war > thriller/horror/crime > comedy > drama.
Use "Другое" for animation, documentaries, family films and musicals that fit nothing else.
Return strict JSON only: {{"results":[{{"id":123,"genre":"Драма","confidence":0.90}}]}}.
Confidence is from 0 to 1. Return every id. Data: {json.dumps(supplied, ensure_ascii=False)}"""
    response = _post_json(CHAT_URL, {"model": model, "messages": [
        {"role": "system", "content": "You are a careful film metadata editor. Return strict JSON."},
        {"role": "user", "content": prompt}], "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"}, "max_tokens": 1200}, api_key, timeout)
    try:
        answers = json.loads(response["choices"][0]["message"]["content"])["results"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek вернул некорректный ответ о жанрах фильмов.") from None
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
                              AND g.category = 'movies' AND g.name = %s""", (trend_id, genre))
        conn.commit()


def fill_movie_genres(week: date, *, timeout: float = 40) -> tuple[int, int]:
    """Return (saved, unknown); rows with an existing genre are never requested."""
    with connect() as conn:
        rows = conn.execute("""SELECT t.id, t.title, t.subtitle,
                   MAX(s.external_id) FILTER (WHERE s.source = 'kinopoisk') AS kinopoisk_id
               FROM mv_category_rank r JOIN trends t ON t.id = r.trend_id
               LEFT JOIN trend_source_items s ON s.trend_id = t.id
               WHERE r.week_start = %s AND r.category = 'movies' AND t.genre_id IS NULL
               GROUP BY r.rank, t.id, t.title, t.subtitle ORDER BY r.rank""", (week,)).fetchall()
        movies = [{"id": row[0], "title": row[1],
                   "year": row[2] if row[2] and str(row[2]).isdigit() else None,
                   "kinopoisk_id": row[3]} for row in rows]
    if not movies:
        return 0, 0
    genres, pending = {}, []
    from_kinopoisk = kinopoisk_genres(movies, timeout=timeout)
    for movie in movies:
        genre = classify_labels(from_kinopoisk.get(movie["id"], []))
        if not genre:
            genre = classify_labels(wikidata_labels(movie["kinopoisk_id"], timeout=timeout))
        if genre:
            genres[movie["id"]] = genre
        else:
            pending.append(movie)
    _save_genres(genres)
    saved = len(genres)
    if pending:
        settings = _settings()
        api_key = str(settings.get("DEEPSEEK_API") or "")
        if not api_key:
            raise RuntimeError("Для определения жанров фильмов нужен DEEPSEEK_API в .env.")
        model = str(settings.get("DEEPSEEK_MODEL") or "deepseek-flash")
        ai_genres = {}
        for start in range(0, len(pending), 10):
            ai_genres.update(_deepseek_batch(pending[start:start + 10], api_key, model, timeout))
        _save_genres(ai_genres)
        saved += len(ai_genres)
    return saved, len(movies) - saved


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Заполнить отсутствующие жанры фильмов")
    cli.add_argument("--week", required=True, type=date.fromisoformat)
    args = cli.parse_args(argv)
    saved, unknown = fill_movie_genres(args.week)
    print(f"Жанры фильмов: сохранено {saved}, осталось без жанра {unknown}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
