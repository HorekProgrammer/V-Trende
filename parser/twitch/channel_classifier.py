import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "twitch" / "channel_types.json"
SEARCH_URL = "https://api.deepseek.com/v1/tools/search"
FETCH_URL = "https://api.deepseek.com/v1/tools/fetch"
CHAT_URL = "https://api.deepseek.com/chat/completions"
CLASSIFIER_VERSION = 3
ALLOWED_TYPES = {"person", "studio", "unknown"}
ALLOWED_OWNER_KINDS = {"individual", "organization", "unknown"}
DEFAULT_BATCH_SIZE = 10
DEFAULT_PERSON_CONFIDENCE = 0.75
RETRIES = 3


def _settings() -> dict:
    return {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}


def _integer_setting(settings: dict, name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(settings.get(name) or default)
    except (TypeError, ValueError):
        raise RuntimeError(f"{name} must be an integer.") from None
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _float_setting(settings: dict, name: str, default: float) -> float:
    try:
        value = float(settings.get(name) or default)
    except (TypeError, ValueError):
        raise RuntimeError(f"{name} must be a number.") from None
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise RuntimeError(f"{name} must be between 0 and 1.")
    return value


def classification_batch_size() -> int:
    return _integer_setting(_settings(), "TWITCH_CLASSIFICATION_BATCH_SIZE", DEFAULT_BATCH_SIZE, 1, 25)


def minimum_person_confidence() -> float:
    return _float_setting(_settings(), "TWITCH_PERSON_CONFIDENCE", DEFAULT_PERSON_CONFIDENCE)


def is_person(classification: dict) -> bool:
    return (
        classification.get("type") == "person"
        and classification.get("confidence", 0) >= minimum_person_confidence()
    )


def _cache_file(settings: dict) -> Path:
    configured = settings.get("TWITCH_CLASSIFICATION_CACHE_FILE")
    return Path(configured) if configured else DEFAULT_CACHE_FILE


def _load_cache(path: Path) -> dict[str, dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        channels = value["channels"]
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        return {}
    return channels if isinstance(channels, dict) else {}


def _save_cache(path: Path, channels: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"version": 1, "channels": channels}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _is_known(value: dict, now: datetime) -> bool:
    if not isinstance(value, dict) or value.get("type") not in ALLOWED_TYPES:
        return False
    try:
        confidence = float(value["confidence"])
    except (KeyError, TypeError, ValueError):
        return False
    if not 0 <= confidence <= 1:
        return False
    if value.get("type") != "unknown":
        return True
    try:
        checked_at = datetime.fromisoformat(value["checked_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False
    return checked_at.tzinfo is not None and now - checked_at <= timedelta(days=1)


def _post_json(url: str, payload: dict, api_key: str, timeout: float) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(RETRIES + 1):
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After") if error.headers else None
            error.close()
            if status not in {429, 500, 502, 503, 504} or attempt == RETRIES:
                raise RuntimeError(f"DeepSeek API: HTTP {status}.") from None
            try:
                delay = max(float(retry_after), 1) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            sleep(delay)
        except (URLError, OSError, TimeoutError):
            if attempt == RETRIES:
                raise RuntimeError("DeepSeek API: network error or timeout.") from None
            sleep(2 ** attempt)
        except (UnicodeError, json.JSONDecodeError):
            raise RuntimeError("DeepSeek API returned an invalid JSON response.") from None
    raise RuntimeError("DeepSeek API: retry limit exceeded.")


def _search_channel(channel: dict, api_key: str, timeout: float) -> list[dict]:
    slug = channel["_slug"]
    response = _post_json(
        SEARCH_URL,
        {
            "query": f'"{slug}" Twitch стример студия организация киберспорт',
            "count": 8,
            "need_content": False,
        },
        api_key,
        timeout,
    )
    results = response.get("results")
    if not isinstance(results, list):
        raise RuntimeError(f"DeepSeek Search returned invalid results for {slug}.")
    return [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("snippet"),
            "summary": item.get("summary"),
            "authority": item.get("authority"),
        }
        for item in results[:8]
        if isinstance(item, dict)
    ]


def fetch_page_markdown(url: str, *, timeout: float = 30) -> str:
    settings = _settings()
    api_key = settings.get("DEEPSEEK_API")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API is required for the TwitchTracker fallback.")
    response = _post_json(FETCH_URL, {"url": url}, str(api_key), timeout)
    content = response.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"DeepSeek Fetch returned no content for {url}.")
    return content


def _validate_classification(item: dict, expected_slugs: set[str], checked_at: str) -> tuple[str, dict]:
    if not isinstance(item, dict):
        raise RuntimeError("DeepSeek returned an invalid channel classification.")
    slug = str(item.get("slug", "")).lower()
    channel_type = item.get("type")
    owner_kind = item.get("owner_kind")
    reason = item.get("reason")
    try:
        confidence = float(item.get("confidence"))
    except (TypeError, ValueError):
        confidence = -1
    if (
        slug not in expected_slugs
        or channel_type not in ALLOWED_TYPES
        or owner_kind not in ALLOWED_OWNER_KINDS
    ):
        raise RuntimeError("DeepSeek returned an unexpected channel classification.")
    expected_type = {
        "individual": "person",
        "organization": "studio",
        "unknown": "unknown",
    }[owner_kind]
    if channel_type != expected_type:
        raise RuntimeError(f"DeepSeek returned an inconsistent classification for {slug}.")
    if not 0 <= confidence <= 1 or not isinstance(reason, str) or not reason.strip():
        raise RuntimeError(f"DeepSeek returned an incomplete classification for {slug}.")
    urls = item.get("evidence_urls", [])
    if not isinstance(urls, list):
        urls = []
    urls = [url for url in urls[:3] if isinstance(url, str) and url.startswith(("http://", "https://"))]
    return slug, {
        "classifier_version": CLASSIFIER_VERSION,
        "type": channel_type,
        "owner_kind": owner_kind,
        "confidence": confidence,
        "reason": reason.strip(),
        "evidence_urls": urls,
        "checked_at": checked_at,
    }


def _classify_batch(channels: list[dict], api_key: str, model: str, timeout: float, checked_at: str) -> dict[str, dict]:
    supplied = []
    for channel in channels:
        supplied.append({
            "channel": channel["channel"],
            "slug": channel["_slug"],
            "twitch_url": f'https://www.twitch.tv/{channel["_slug"]}',
            "search_results": _search_channel(channel, api_key, timeout),
        })

    prompt = f"""Classify every Twitch channel using the supplied current web search results.
Types:
- person: the account belongs to and represents one specific individual streamer or commentator;
- studio: the account belongs to and represents an organization, studio, team, league, tournament operator or brand;
- unknown: reliable evidence is insufficient.
First determine owner_kind: individual, organization, or unknown. Derive type strictly from it: individual=person, organization=studio, unknown=unknown. The content format is secondary: a personal commentator remains person even when they cast esports matches with guests, own a team, organize tournaments, or host official matches. Do not infer ownership from the channel name alone.
Return JSON only: {{"results":[{{"slug":"...","owner_kind":"individual|organization|unknown","type":"person|studio|unknown","confidence":0.0,"reason":"one short sentence","evidence_urls":["up to 3 URLs"]}}]}}.
Data: {json.dumps(supplied, ensure_ascii=False, separators=(',', ':'))}"""
    response = _post_json(
        CHAT_URL,
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You carefully classify Twitch channels. Return strict JSON and never invent evidence.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 3500,
        },
        api_key,
        timeout,
    )
    try:
        content = response["choices"][0]["message"]["content"]
        items = json.loads(content)["results"]
    except (IndexError, KeyError, TypeError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek returned an invalid classification response.") from None
    if not isinstance(items, list):
        raise RuntimeError("DeepSeek returned an invalid classification list.")

    expected = {channel["_slug"].lower() for channel in channels}
    result = dict(_validate_classification(item, expected, checked_at) for item in items)
    if set(result) != expected:
        missing = ", ".join(sorted(expected - set(result)))
        raise RuntimeError(f"DeepSeek did not classify all channels: {missing}.")
    return result


def classify_channels(
    channels: list[dict],
    *,
    timeout: float = 30,
    cache_path: Path | None = None,
) -> dict[str, dict]:
    if not channels:
        return {}
    settings = _settings()
    path = cache_path or _cache_file(settings)
    cache = _load_cache(path)
    now = datetime.now(timezone.utc)

    result = {}
    pending = []
    seen = set()
    for channel in channels:
        slug = channel["_slug"].lower()
        if slug in seen:
            continue
        seen.add(slug)
        cached = cache.get(slug)
        if _is_known(cached, now):
            result[slug] = cached
        else:
            pending.append(channel)

    if not pending:
        return result

    api_key = settings.get("DEEPSEEK_API")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API is required to classify Twitch channels.")
    model = settings.get("DEEPSEEK_MODEL") or "deepseek-flash"
    checked_at = now.isoformat().replace("+00:00", "Z")
    batch_size = classification_batch_size()
    for start in range(0, len(pending), batch_size):
        classified = _classify_batch(
            pending[start:start + batch_size], str(api_key), str(model), timeout, checked_at
        )
        cache.update(classified)
        result.update(classified)
        _save_cache(path, cache)
    return result
