import json
from pathlib import Path
import os

from dotenv import dotenv_values
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
TABLE_URL = "https://wordstat.yandex.ru/wordstat/api/getTable"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_wordstat_count(phrase: str) -> int:
    if not isinstance(phrase, str) or not 1 <= len(phrase.strip()) <= 400:
        raise ValueError("Фраза должна содержать от 1 до 400 символов.")
    settings = {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}
    session_id = (settings.get("WORDSTAT_SESSION_ID") or "").strip()
    if not session_id:
        raise ValueError("Укажите WORDSTAT_SESSION_ID в .env или окружении.")
    if any(ord(char) < 33 or ord(char) > 126 or char in ';,\"\\' for char in session_id):
        raise ValueError("WORDSTAT_SESSION_ID содержит недопустимые символы.")
    headers = {
        "Cookie": f"Session_id={session_id}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Origin": "https://wordstat.yandex.ru",
        "Referer": "https://wordstat.yandex.ru/",
    }
    body = {
        "searchValue": phrase.strip(),
        "currentDevice": "desktop,phone,tablet",
        "dbname": "rus",
        "filters": {"region": "225", "tableType": "popular"},
    }
    request = Request(TABLE_URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers=headers, method="POST")
    try:
        with build_opener(_NoRedirect).open(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        status = error.code
        error.close()
        raise RuntimeError(
            f"Wordstat Web: HTTP {status}. Откройте Wordstat в браузере, "
            "проверьте вход и обновите WORDSTAT_SESSION_ID в .env; при ограничении запросов повторите позже."
        ) from None
    except (URLError, OSError):
        raise RuntimeError("Wordstat Web: ошибка сети или таймаут.") from None
    except (ValueError, UnicodeError):
        raise RuntimeError("Wordstat вернул не JSON. Проверьте вход/CAPTCHA в браузере и обновите WORDSTAT_SESSION_ID в .env.") from None

    if not isinstance(payload, dict) or not isinstance(payload.get("table"), dict):
        raise RuntimeError("Wordstat не вернул таблицу: проверьте сессию или изменение формата ответа.")
    if payload["table"].get("isQueryInvalid") is True:
        raise ValueError("Wordstat отклонил поисковую фразу.")
    count = payload.get("totalValue")
    if type(count) is not int or count < 0:
        raise RuntimeError("Wordstat не вернул корректный totalValue.")
    return count
