"""Вход в VK для парсера чарта: cookies собираются автоматически.

    python -m parser.vk.login
    python -m parser.vk.login --user-id 123456   # если ID не определится сам

Открывается отдельное окно браузера с vk.ru. Войдите в аккаунт как обычно
(пароль, код из SMS — всё вводится в окне, программа их не видит и не хранит).
Как только вход выполнен, окно закроется само, а парсер получит:
  * cookies remixsid и remixnsid,
  * User-Agent этого браузера,
  * ID пользователя.

Они сохраняются в data/browser/vk_session.json; профиль браузера — в
data/browser/vk_profile/ (папка data/ не попадает в git). Пока VK не завершит
сессию, повторный вход не нужен; если парсер напишет, что сессия истекла, —
запустите эту команду снова: обычно вход подхватится из профиля без пароля.

Значения VK_* в .env, если заданы, важнее сохранённой сессии.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from time import monotonic, sleep

from .vk_parser import SESSION_FILE

PROFILE_DIR = SESSION_FILE.parent / "vk_profile"
START_URL = "https://vk.ru/audio"
COOKIE_URL = "https://vk.ru"
POLL_SECONDS = 2
# Сколько ждать определения ID после появления cookies, прежде чем спросить вручную.
USER_ID_GRACE_SECONDS = 20

_USER_ID_JS = "() => { const id = window.vk && Number(window.vk.id); return id > 0 ? id : null; }"


class LoginError(RuntimeError):
    pass


def session_from_browser(cookies: list[dict], user_agent: str, user_id: int) -> dict:
    """Собирает значения для парсера из cookies браузера."""
    values = {cookie.get("name"): cookie.get("value") for cookie in cookies}
    missing = [name for name in ("remixsid", "remixnsid") if not values.get(name)]
    if missing:
        raise LoginError(f"В браузере нет cookies {', '.join(missing)}: вход не завершён.")
    if not user_agent or type(user_id) is not int or user_id <= 0:
        raise LoginError("Не удалось определить User-Agent или ID пользователя.")
    return {
        "VK_USER_ID": str(user_id),
        "VK_REMIXSID": values["remixsid"],
        "VK_REMIXNSID": values["remixnsid"],
        "VK_USER_AGENT": user_agent,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def save_session(session: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = SESSION_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(SESSION_FILE)


def _ask_user_id() -> int:
    print(
        "\nНе удалось определить ваш ID автоматически.\n"
        "Откройте в окне браузера свою страницу: число из адреса vk.ru/id123456 — это ID\n"
        "(или «Настройки» → «Аккаунт» → «Адрес страницы»).",
        file=sys.stderr,
    )
    value = input("Введите ID: ").strip()
    if not value.isdigit() or int(value) <= 0:
        raise LoginError("ID должен быть положительным числом.")
    return int(value)


def _evaluate(page, script):
    """Выполняет JS на странице; во время перехода между страницами возвращает None."""
    from playwright.sync_api import Error
    try:
        return page.evaluate(script)
    except Error:
        return None


def login(timeout: float, user_id: int | None = None, log=print) -> dict:
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        raise LoginError(
            "Нужен Playwright: pip install -r requirements.txt и python -m playwright install chromium"
        ) from None

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(PROFILE_DIR), headless=False, locale="ru-RU",
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(START_URL, wait_until="domcontentloaded")
                log("Войдите в VK в открывшемся окне — после входа оно закроется само.")
                deadline = monotonic() + timeout
                cookies_seen_at = None
                while monotonic() < deadline:
                    if not context.pages:
                        raise LoginError("Окно браузера закрыто до завершения входа.")
                    # Вход может открыть новую вкладку: следим за последней.
                    page = context.pages[-1]
                    cookies = context.cookies(COOKIE_URL)
                    names = {cookie["name"] for cookie in cookies if cookie.get("value")}
                    if {"remixsid", "remixnsid"} <= names:
                        cookies_seen_at = cookies_seen_at or monotonic()
                        detected = user_id or _evaluate(page, _USER_ID_JS)
                        if not detected and monotonic() - cookies_seen_at > USER_ID_GRACE_SECONDS:
                            detected = _ask_user_id()
                        user_agent = _evaluate(page, "() => navigator.userAgent")
                        if detected and user_agent:
                            return session_from_browser(cookies, user_agent, int(detected))
                    sleep(POLL_SECONDS)
                raise LoginError(f"Вход не выполнен за {int(timeout)} с. Запустите команду снова.")
            finally:
                context.close()
    except Error as error:
        message = str(error).splitlines()[0] if str(error) else type(error).__name__
        raise LoginError(f"Окно браузера закрыто или не открылось: {message}") from None


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Войти в VK и сохранить сессию для парсера чарта")
    cli.add_argument("--timeout", type=float, default=300, help="Сколько секунд ждать входа (по умолчанию 300)")
    cli.add_argument("--user-id", type=int, help="ID пользователя VK, если он не определится сам")
    args = cli.parse_args(argv)
    if args.timeout <= 0:
        cli.error("--timeout должен быть положительным")
    if args.user_id is not None and args.user_id <= 0:
        cli.error("--user-id должен быть положительным")

    def log(message):
        print(message, file=sys.stderr, flush=True)

    try:
        session = login(args.timeout, args.user_id, log=log)
        save_session(session)
    except (LoginError, OSError) as error:
        log(f"Ошибка: {error}")
        return 1
    log(f"Готово: сессия VK (ID {session['VK_USER_ID']}) сохранена. "
        "Проверьте: python -m parser.vk --limit 5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
