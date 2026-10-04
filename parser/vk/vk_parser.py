import html
import json
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values

CHART_URL = "https://vk.ru/al_audio.php"
CHART_SIZE = 100
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _settings() -> dict:
    return {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}


def _validate_cookie(value: str, name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"Укажите {name} в .env или окружении.")
    if any(ord(char) < 33 or ord(char) > 126 or char in ';,"\\' for char in value):
        raise ValueError(f"{name} содержит недопустимые символы.")
    return value


def _playlist(response_body: bytes) -> dict:
    try:
        payload = json.loads(response_body.decode("cp1251"))
        playlist = payload["payload"][1][1]["playlist"]
        if (not isinstance(playlist, dict)
                or playlist.get("title", "").replace("\xa0", " ") != "Чарт VK Музыки"
                or not isinstance(playlist.get("list"), list)):
            raise ValueError
        return playlist
    except (UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError(
            "VK Музыка не вернула чарт. Проверьте VK_REMIXSID, VK_REMIXNSID и VK_USER_ID."
        ) from None


def parse_chart_responses(first_response: bytes, remaining_response: bytes) -> list[dict]:
    first = _playlist(first_response)
    remaining = _playlist(remaining_response)
    raw_tracks = first["list"] + remaining["list"]
    result = []
    try:
        for position, track in enumerate(raw_tracks, start=1):
            title = html.unescape(track[3]).strip()
            performer_text = html.unescape(track[4]).strip()
            artists = [artist.strip() for artist in performer_text.split(",") if artist.strip()]
            if len(track) < 5 or not title or not artists:
                raise ValueError
            result.append({"position": position, "title": title, "artists": artists})
    except (IndexError, TypeError, ValueError):
        raise RuntimeError("VK Музыка: некорректная строка чарта; возможно, формат сайта изменился.") from None

    if (len(result) != CHART_SIZE or first.get("hasMore") is not True
            or remaining.get("hasMore") is not False):
        raise RuntimeError("VK Музыка: чарт загружен не полностью.")
    return result


def _request(data: dict, cookie: str, user_agent: str, timeout: float) -> bytes:
    request = Request(
        CHART_URL,
        data=urlencode(data).encode(),
        headers={
            "User-Agent": user_agent,
            "Cookie": cookie,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Origin": "https://vk.ru",
            "Referer": "https://vk.ru/audio",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as error:
        status = error.code
        error.close()
        raise RuntimeError(f"VK Музыка: HTTP {status}.") from None
    except (URLError, OSError):
        raise RuntimeError("VK Музыка: ошибка сети или таймаут.") from None


def get_vk_chart(limit: int | None = None, *, timeout: float = 30) -> list[dict]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit должен быть положительным целым числом или None.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout должен быть положительным конечным числом.")

    settings = _settings()
    remixsid = _validate_cookie(settings.get("VK_REMIXSID") or "", "VK_REMIXSID")
    remixnsid = _validate_cookie(settings.get("VK_REMIXNSID") or "", "VK_REMIXNSID")
    user_agent = (settings.get("VK_USER_AGENT") or "").strip()
    if not user_agent or "\r" in user_agent or "\n" in user_agent:
        raise ValueError("Укажите VK_USER_AGENT из того же запроса в .env или окружении.")
    try:
        user_id = int(settings.get("VK_USER_ID") or "")
        if user_id <= 0:
            raise ValueError
    except ValueError:
        raise ValueError("Укажите положительный VK_USER_ID в .env или окружении.") from None

    cookie = f"remixsid={remixsid}; remixnsid={remixnsid}"
    first_body = _request({
        "al": 1,
        "act": "section",
        "claim": 0,
        "is_layer": 0,
        "owner_id": user_id,
        "section": "explore",
    }, cookie, user_agent, timeout)
    first = _playlist(first_body)
    if first.get("hasMore") is not True or not first.get("nextOffset") or not first.get("blockId"):
        raise RuntimeError("VK Музыка: отсутствуют параметры загрузки продолжения чарта.")
    remaining_body = _request({
        "al": 1,
        "act": "load_catalog_section",
        "section_id": first["blockId"],
        "start_from": first["nextOffset"],
    }, cookie, user_agent, timeout)
    return parse_chart_responses(first_body, remaining_body)[:limit]
