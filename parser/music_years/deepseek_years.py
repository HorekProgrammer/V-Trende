import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from parser.common.normalize import match_key
from parser.common.years import valid_year
from parser.twitch.channel_classifier import CHAT_URL, SEARCH_URL, _post_json, _settings

CACHE_FILE = Path(__file__).resolve().parents[2] / "data" / "cache" / "music" / "years.json"
BATCH_SIZE = 10
SEARCH_COUNT = 6
RECHECK_UNKNOWN_DAYS = 7

_VERSION_WORDS = (
    r"mix|mixed|edit|remix|version|nightcore|speed|sped|slow|slowed|club|radio|extended|live|"
    r"acoustic|prod\.?|feat\.?|ft\.?|remaster|remastered|instrumental|версия|ремикс|рэп"
)
_VERSION_RE = re.compile(rf"\s*[(\[][^)\]]*\b(?:{_VERSION_WORDS})(?!\w)[^)\]]*[)\]]", re.IGNORECASE)


def base_title(title: str) -> str:
    cleaned = _VERSION_RE.sub("", title).strip(" -–—")
    return cleaned or title


def base_key(title: str, artists: str) -> str | None:
    try:
        return match_key(base_title(title), [artists] if artists else None)
    except ValueError:
        return None


def _load_cache(path: Path) -> dict[str, dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        tracks = value["tracks"]
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        return {}
    return tracks if isinstance(tracks, dict) else {}


def _save_cache(path: Path, tracks: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"version": 1, "tracks": tracks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _cached_year(value, now: datetime) -> tuple[bool, int | None]:
    if not isinstance(value, dict):
        return False, None
    year = valid_year(value.get("year"))
    if year:
        return True, year
    try:
        checked_at = datetime.fromisoformat(str(value["checked_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False, None
    if checked_at.tzinfo is None or now - checked_at > timedelta(days=RECHECK_UNKNOWN_DAYS):
        return False, None
    return True, None


def _search(track: dict, api_key: str, timeout: float) -> list[dict]:
    response = _post_json(
        SEARCH_URL,
        {
            "query": f'{track["artists"]} {track["title"]} песня год выхода',
            "count": SEARCH_COUNT,
            "need_content": False,
        },
        api_key,
        timeout,
    )
    results = response.get("results")
    if not isinstance(results, list):
        return []
    return [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("snippet"),
            "summary": item.get("summary"),
        }
        for item in results[:SEARCH_COUNT]
        if isinstance(item, dict) and isinstance(item.get("url"), str)
    ]


def _validated_year(item, urls: set[str], today: date) -> int | None:
    if not isinstance(item, dict):
        return None
    year = valid_year(item.get("year"))
    if not year or year > today.year:
        return None
    if item.get("evidence_url") not in urls:
        return None
    return year


def _ask_batch(tracks: list[dict], api_key: str, model: str, timeout: float, today: date) -> dict[str, dict]:
    supplied, urls_by_key = [], {}
    for track in tracks:
        results = _search(track, api_key, timeout)
        urls_by_key[track["key"]] = {r["url"] for r in results}
        supplied.append({
            "key": track["key"],
            "title": track["title"],
            "artists": track["artists"],
            "search_results": results,
        })

    prompt = f"""For every track, find the year the song was first released, using ONLY the supplied search results.
Rules:
- Use the release year of the original song by these artists, not of another song with the same title.
- If the search results do not state the release year clearly, return null. Never guess.
- evidence_url must be one of the supplied search result URLs that states the year.
Return JSON only: {{"results":[{{"key":"...","year":2024,"evidence_url":"..."}}]}}, with "year": null and "evidence_url": null when unknown.
Data: {json.dumps(supplied, ensure_ascii=False, separators=(',', ':'))}"""
    response = _post_json(
        CHAT_URL,
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You extract facts from supplied search results. Return strict JSON and never invent data.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 2000,
        },
        api_key,
        timeout,
    )
    try:
        items = json.loads(response["choices"][0]["message"]["content"])["results"]
    except (IndexError, KeyError, TypeError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek вернул некорректный ответ о годах треков.") from None
    answers = {item.get("key"): item for item in items if isinstance(item, dict)} if isinstance(items, list) else {}

    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {}
    for track in tracks:
        answer = answers.get(track["key"])
        year = _validated_year(answer, urls_by_key[track["key"]], today)
        result[track["key"]] = {
            "year": year,
            "evidence_url": answer.get("evidence_url") if year else None,
            "checked_at": checked_at,
        }
    return result


def find_years(
    tracks: list[dict],
    *,
    known: dict[str, int] | None = None,
    recheck: bool = False,
    timeout: float = 30,
    cache_path: Path | None = None,
) -> dict[str, int]:
    path = cache_path or CACHE_FILE
    cache = _load_cache(path)
    now = datetime.now(timezone.utc)
    known = known or {}

    groups: dict[str, list[dict]] = {}
    for track in tracks:
        groups.setdefault(base_key(track["title"], track["artists"]) or track["key"], []).append(track)

    years_by_group, pending = {}, []
    for group, members in groups.items():
        if known.get(group):
            years_by_group[group] = known[group]
            continue
        cached, year = _cached_year(cache.get(group), now)
        if not year:
            for member in members:
                member_cached, member_year = _cached_year(cache.get(member["key"]), now)
                if member_year:
                    cached, year = True, member_year
                    break
                cached = cached or member_cached
        if year:
            years_by_group[group] = year
        elif not cached or recheck:
            first = members[0]
            pending.append({"key": group, "title": base_title(first["title"]), "artists": first["artists"]})

    if pending:
        settings = _settings()
        api_key = settings.get("DEEPSEEK_API")
        if not api_key:
            raise RuntimeError("Для поиска года нужен DEEPSEEK_API в .env.")
        model = str(settings.get("DEEPSEEK_MODEL") or "deepseek-flash")
        for start in range(0, len(pending), BATCH_SIZE):
            answers = _ask_batch(pending[start:start + BATCH_SIZE], str(api_key), model, timeout, now.date())
            cache.update(answers)
            _save_cache(path, cache)
            years_by_group.update({key: value["year"] for key, value in answers.items() if value["year"]})

    return {
        member["key"]: years_by_group[group]
        for group, members in groups.items()
        if group in years_by_group
        for member in members
    }
