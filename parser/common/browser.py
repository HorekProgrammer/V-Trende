"""Загрузка страницы в настоящем браузере с постоянным профилем.

Нужна сайтам, которые не отдают данные простому запросу, но пускают обычный
браузер (например, проверка доступа Servicepipe у Звука). Профиль хранится
в data/browser/<имя>_profile/ (папка data/ не попадает в git): cookies, полученные
после проверки, сохраняются и используются при следующих запусках.

Защита не обходится и не подделывается: страница открывается обычным Chromium,
который выполняет проверку так же, как браузер пользователя.
"""

from pathlib import Path

BROWSER_DIR = Path(__file__).resolve().parents[2] / "data" / "browser"


class BrowserFetchError(RuntimeError):
    pass


# Страница готова, когда документ дочитан до конца и нужный элемент на месте.
# Для <script type="application/json"> дополнительно проверяется, что данные
# целые: после проверки доступа сайт перезагружает страницу, и сразу после появления
# элемента его содержимое ещё догружается — так получался обрезанный JSON.
_READY_JS = """
selector => {
    if (document.readyState === 'loading') return false;
    const element = document.querySelector(selector);
    if (!element) return false;
    if (element.tagName === 'SCRIPT' && element.type === 'application/json') {
        try { JSON.parse(element.textContent); } catch (error) { return false; }
    }
    return true;
}
"""


def _wait_until_ready(page, selector: str, timeout: float, playwright_error) -> None:
    from time import monotonic
    deadline = monotonic() + timeout
    while True:
        remaining_ms = max((deadline - monotonic()) * 1000, 1)
        try:
            page.wait_for_function(_READY_JS, arg=selector, timeout=remaining_ms, polling=250)
            return
        except playwright_error as error:
            # Страница перезагрузилась во время ожидания (например, после проверки
            # доступа) — ждём уже на новой странице.
            if "context was destroyed" in str(error) and monotonic() < deadline:
                continue
            raise


def fetch_html(profile: str, url: str, *, wait_selector: str, timeout: float,
               headless: bool = True) -> str:
    """Открывает url, ждёт полной загрузки и элемента wait_selector, возвращает HTML."""
    try:
        from playwright.sync_api import Error, TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError:
        raise BrowserFetchError(
            "нужен Playwright: pip install -r requirements.txt и python -m playwright install chromium"
        ) from None

    profile_dir = BROWSER_DIR / f"{profile}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            # channel="chromium" — полный Chromium, как в парсерах Кинопоиска:
            # облегчённый headless shell у Playwright ставится не всегда.
            context = playwright.chromium.launch_persistent_context(
                str(profile_dir), headless=headless, channel="chromium", locale="ru-RU",
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                _wait_until_ready(page, wait_selector, timeout, Error)
                return page.content()
            finally:
                context.close()
    except PlaywrightTimeoutError:
        raise BrowserFetchError(f"страница не загрузилась за {int(timeout)} с") from None
    except Error as error:
        message = str(error).splitlines()[0] if str(error) else type(error).__name__
        raise BrowserFetchError(message) from None
