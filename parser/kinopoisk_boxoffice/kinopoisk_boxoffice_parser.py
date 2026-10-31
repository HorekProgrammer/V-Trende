import math
import re
from urllib.parse import urljoin

from parser.common.covers import clean_image_url, largest_from_srcset
from parser.kinopoisk.posters import fill_missing_posters

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


BASE_URL = "https://www.kinopoisk.ru/box/"

_FILM_ID_RE = re.compile(r"/film/(\d+)/")
_FIRST_NUMBER_RE = re.compile(r"\d[\d\s\u00a0]*")
_WEEKS_RE = re.compile(r"\[([\d\s\u00a0]+)\]\s*$")


def _normalize_space(value):
    return " ".join(
        value.replace("\u00a0", " ").split()
    )


def _first_number(value, field_name):
    value = _normalize_space(value)

    match = _FIRST_NUMBER_RE.search(value)

    if not match:
        raise RuntimeError(
            f"Kinopoisk box office row has invalid "
            f"{field_name}: {value!r}"
        )

    return int(
        match.group(0).replace(" ", "")
    )


def _optional_first_number(value, field_name):
    value = _normalize_space(value)

    if value in {"", "-", "—"}:
        return None

    return _first_number(
        value,
        field_name,
    )


def _extract_weeks(value):
    value = _normalize_space(value)

    match = _WEEKS_RE.search(value)

    if not match:
        raise RuntimeError(
            "Kinopoisk box office row has invalid "
            f"weeks count: {value!r}"
        )

    weeks = int(
        match.group(1).replace(" ", "")
    )

    if weeks <= 0:
        raise RuntimeError(
            "Kinopoisk box office row has invalid "
            f"weeks count: {value!r}"
        )

    return weeks


def _extract_kinopoisk_id(href):
    if not isinstance(href, str):
        raise RuntimeError(
            "Kinopoisk box office row "
            "has invalid film link"
        )

    match = _FILM_ID_RE.search(href)

    if not match:
        raise RuntimeError(
            "Kinopoisk box office row "
            "has invalid film link"
        )

    return int(match.group(1))


def _parse_row(
    position,
    cells,
    title,
    href,
    cover_url=None,
):
    if len(cells) != 8:
        raise RuntimeError(
            "Kinopoisk box office row "
            "must contain 8 cells"
        )

    title = _normalize_space(title)

    if not title:
        raise RuntimeError(
            "Kinopoisk box office row "
            "has an empty title"
        )

    return {
        "position": position,
        "title": title,
        "kinopoisk_id": _extract_kinopoisk_id(href),
        "weeks_in_release": _extract_weeks(cells[2]),
        "box_office": _optional_first_number(
            cells[3],
            "weekend box office",
        ),
        "total_box_office": _optional_first_number(
            cells[4],
            "total box office",
        ),
        "viewers": _optional_first_number(
            cells[5],
            "weekend viewers",
        ),
        "total_viewers": _optional_first_number(
            cells[6],
            "total viewers",
        ),
        "copies": _optional_first_number(
            cells[7],
            "copies",
        ),
        "cover_url": clean_image_url(cover_url),
    }


def _parse_chart(page):
    rows = page.locator(
        'tr:has(a[href*="/film/"])'
    )

    result = []

    for index in range(rows.count()):
        row = rows.nth(index)
        cells_locator = row.locator("td")

        if cells_locator.count() != 8:
            continue

        film_link = row.locator(
            'a[href*="/film/"]'
        ).first

        href = film_link.get_attribute("href")
        title = film_link.inner_text()

        cells = [
            cells_locator.nth(i).inner_text()
            for i in range(8)
        ]

        cover_url = None
        images = row.locator("img")
        if images.count() > 0:
            image = images.first
            cover_url = (
                largest_from_srcset(image.get_attribute("srcset"))
                or image.get_attribute("src")
            )

        result.append(
            _parse_row(
                position=len(result) + 1,
                cells=cells,
                title=title,
                href=href,
                cover_url=cover_url,
            )
        )

    if not result:
        raise RuntimeError(
            "Kinopoisk box office chart was not found"
        )

    viewer_counts = [
        item["viewers"]
        for item in result
        if item["viewers"] is not None
    ]

    if viewer_counts != sorted(
        viewer_counts,
        reverse=True,
    ):
        raise RuntimeError(
            "Kinopoisk box office chart "
            "is not sorted by viewers"
        )

    ids = [
        item["kinopoisk_id"]
        for item in result
    ]

    if len(ids) != len(set(ids)):
        raise RuntimeError(
            "Kinopoisk box office contains "
            "duplicate film ids"
        )

    return result


def _goto(page, url, timeout):
    try:
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=int(timeout * 1000),
        )
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            f"Kinopoisk request timed out: {url}"
        ) from exc

    if (
        response is not None
        and response.status >= 400
    ):
        raise RuntimeError(
            f"Kinopoisk returned HTTP {response.status}"
        )

    page.wait_for_timeout(2000)


def _fetch_chart(
    limit,
    timeout,
    headless,
):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            channel="chromium",
        )

        try:
            page = browser.new_page(
                locale="ru-RU",
                viewport={
                    "width": 1400,
                    "height": 900,
                },
            )

            _goto(
                page,
                BASE_URL,
                timeout,
            )

            viewer_links = page.locator(
                'a[href*="/box/"][href*="/sort/view/"]'
            )

            if viewer_links.count() == 0:
                raise RuntimeError(
                    "Kinopoisk viewer-sort link "
                    "was not found"
                )

            viewer_href = (
                viewer_links
                .first
                .get_attribute("href")
            )

            if not viewer_href:
                raise RuntimeError(
                    "Kinopoisk viewer-sort link "
                    "is invalid"
                )

            viewer_url = urljoin(
                page.url,
                viewer_href,
            )

            if "/sort/view/" not in viewer_url:
                raise RuntimeError(
                    "Kinopoisk viewer-sort URL "
                    "is invalid"
                )

            show_all_url = (
                viewer_url.rstrip("/")
                + "/view/all/"
            )

            _goto(
                page,
                show_all_url,
                timeout,
            )

            if "kinopoisk.ru/box/" not in page.url:
                raise RuntimeError(
                    "Kinopoisk redirected away "
                    "from the box office page"
                )

            chart = _parse_chart(page)
            if limit is not None:
                chart = chart[:limit]

            fill_missing_posters(page, chart, timeout)

        finally:
            browser.close()

    return chart


def get_kinopoisk_boxoffice(
    limit=None,
    timeout=60,
    headless=True,
):
    if limit is not None and (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit <= 0
    ):
        raise ValueError(
            "limit must be a positive integer or None"
        )

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError(
            "timeout must be a positive finite number"
        )

    if not isinstance(headless, bool):
        raise ValueError(
            "headless must be a boolean"
        )

    return _fetch_chart(
        limit=limit,
        timeout=timeout,
        headless=headless,
    )