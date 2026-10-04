import math
import re

CHART_URL = "https://www.kinopoisk.ru/lists/movies/popular-films/"
CHART_SIZE = 1000
PAGE_SIZE = 50

_FILM_URL_RE = re.compile(r"^/film/(\d+)/?$")
_YEAR_RE = re.compile(r"(?:^|\D)((?:19|20)\d{2})(?!\d)")
_RATING_RE = re.compile(r"Рейтинг Кинопоиска\s+(\d+(?:[.,]\d+)?)")


def _parse_page(items: list[dict], page_number: int) -> list[dict]:
    if not isinstance(items, list) or len(items) != PAGE_SIZE:
        raise RuntimeError(
            "Кинопоиск: чарт отсутствует или загружен не полностью."
        )

    result = []
    seen_ids = set()

    try:
        for index, item in enumerate(items):
            href = item["href"]
            title = item["title"]
            text = item["text"]

            if (
                not isinstance(href, str)
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(text, str)
            ):
                raise ValueError

            id_match = _FILM_URL_RE.fullmatch(href)
            if id_match is None:
                raise ValueError

            kinopoisk_id = int(id_match.group(1))

            if kinopoisk_id in seen_ids:
                raise ValueError

            seen_ids.add(kinopoisk_id)

            year_match = _YEAR_RE.search(text)
            if year_match is None:
                raise ValueError

            year = int(year_match.group(1))

            rating_match = _RATING_RE.search(text)
            rating = (
                float(rating_match.group(1).replace(",", "."))
                if rating_match
                else None
            )

            if rating is not None and not 0 <= rating <= 10:
                raise ValueError

            position = (page_number - 1) * PAGE_SIZE + index + 1

            result.append({
                "position": position,
                "title": title.strip(),
                "kinopoisk_id": kinopoisk_id,
                "year": year,
                "rating": rating,
            })

    except (KeyError, TypeError, ValueError):
        raise RuntimeError(
            "Кинопоиск: некорректная карточка фильма; "
            "возможно, формат сайта изменился."
        ) from None

    return result


def _fetch_chart(limit: int | None, timeout: float) -> list[dict]:
    try:
        from playwright.sync_api import (
            Error,
            TimeoutError as PlaywrightTimeoutError,
            sync_playwright,
        )
    except ImportError:
        raise RuntimeError(
            "Кинопоиск: установите Playwright командой "
            "'pip install playwright' и Chromium командой "
            "'python -m playwright install chromium --no-shell'."
        ) from None

    target_size = CHART_SIZE if limit is None else min(limit, CHART_SIZE)
    pages_count = math.ceil(target_size / PAGE_SIZE)

    result = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                channel="chromium",
            )

            try:
                context = browser.new_context(
                    locale="ru-RU",
                    viewport={"width": 1400, "height": 900},
                )
                page = context.new_page()

                for page_number in range(1, pages_count + 1):
                    url = (
                        CHART_URL
                        if page_number == 1
                        else f"{CHART_URL}?page={page_number}"
                    )

                    response = page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=timeout * 1000,
                    )

                    if response is None or not response.ok:
                        status = response.status if response is not None else "нет ответа"
                        raise RuntimeError(f"Кинопоиск: HTTP {status}.")

                    page.wait_for_function(
                        """
                        () => {
                            const hrefs = [...document.querySelectorAll(
                                'main a[href^="/film/"] img[alt]'
                            )]
                                .map(image =>
                                    image.closest('a[href^="/film/"]')
                                        ?.getAttribute('href')
                                )
                                .filter(href =>
                                    href && /^\\/film\\/\\d+\\/?$/.test(href)
                                );

                            return new Set(hrefs).size >= 50;
                        }
                        """,
                        timeout=timeout * 1000,
                    )

                    items = page.evaluate(
                        """
                        () => {
                            const result = [];
                            const seen = new Set();

                            const images = document.querySelectorAll(
                                'main a[href^="/film/"] img[alt]'
                            );

                            for (const image of images) {
                                const link = image.closest(
                                    'a[href^="/film/"]'
                                );

                                if (!link) {
                                    continue;
                                }

                                const href = link.getAttribute('href');

                                if (
                                    !href ||
                                    !/^\\/film\\/\\d+\\/?$/.test(href) ||
                                    seen.has(href)
                                ) {
                                    continue;
                                }

                                seen.add(href);

                                let node = link.parentElement;
                                let text = "";

                                for (
                                    let depth = 0;
                                    depth < 5 && node;
                                    depth++, node = node.parentElement
                                ) {
                                    const candidate =
                                        (node.innerText || "").trim();

                                    if (
                                        candidate.includes(image.alt) &&
                                        /(?:19|20)\\d{2}/.test(candidate)
                                    ) {
                                        text = candidate;
                                        break;
                                    }
                                }

                                result.push({
                                    href,
                                    title: image.alt,
                                    text,
                                });
                            }

                            return result;
                        }
                        """
                    )

                    result.extend(_parse_page(items, page_number))

            finally:
                browser.close()

    except RuntimeError:
        raise
    except PlaywrightTimeoutError:
        raise RuntimeError(
            "Кинопоиск: превышено время ожидания загрузки чарта."
        ) from None
    except Error:
        raise RuntimeError(
            "Кинопоиск: ошибка запуска браузера или загрузки страницы."
        ) from None

    return result[:target_size]


def get_kinopoisk_chart(
    limit: int | None = None,
    *,
    timeout: float = 30,
) -> list[dict]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError(
            "limit должен быть положительным целым числом или None."
        )

    if (
        type(timeout) not in (int, float)
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError(
            "timeout должен быть положительным конечным числом."
        )

    return _fetch_chart(limit, timeout)