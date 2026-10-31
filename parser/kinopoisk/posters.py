from urllib.parse import urlsplit

from parser.common.covers import clean_image_url, largest_from_srcset

FILM_URL = "https://www.kinopoisk.ru/film/{film_id}/"
POSTER_PATH = "/get-kinopoisk-image/"
CANONICAL_HOST = "https://avatars.mds.yandex.net"
POSTER_SELECTOR = 'img[class*="film-poster"]'
MAX_MISSES_IN_ROW = 3
PAUSE_MS = 700

FIND_POSTER_JS = """
() => {
    const images = [...document.querySelectorAll('img')].filter(image =>
        /get-kinopoisk-image/.test(
            (image.currentSrc || image.getAttribute('src') || '') + ' ' + (image.getAttribute('srcset') || '')
        )
    );
    const byClass = images.find(image => /film-poster/i.test(image.className || ''));
    const portrait = images.find(image =>
        image.naturalWidth >= 100 && image.naturalHeight > image.naturalWidth * 1.2
    );
    const poster = byClass || portrait;
    if (!poster) {
        return null;
    }
    return {
        srcset: poster.getAttribute('srcset') || '',
        src: poster.currentSrc || poster.getAttribute('src') || '',
    };
}
"""


def kinopoisk_image_url(value) -> str | None:
    url = clean_image_url(value)
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not (host == "yandex.net" or host.endswith(".yandex.net")):
        return None
    if not parts.path.startswith(POSTER_PATH):
        return None
    return CANONICAL_HOST + parts.path


def poster_url(found) -> str | None:
    if not isinstance(found, dict):
        return None
    for candidate in (largest_from_srcset(found.get("srcset")), found.get("src")):
        url = kinopoisk_image_url(candidate)
        if url:
            return url
    return None


def fill_missing_posters(page, films: list[dict], timeout: float) -> int:
    found = misses = 0
    for film in films:
        if film.get("cover_url"):
            continue
        if misses >= MAX_MISSES_IN_ROW:
            break
        try:
            page.goto(
                FILM_URL.format(film_id=film["kinopoisk_id"]),
                wait_until="domcontentloaded",
                timeout=timeout * 1000,
            )
            try:
                page.wait_for_selector(POSTER_SELECTOR, timeout=5000)
            except Exception:  # noqa: BLE001
                pass
            result = page.evaluate(FIND_POSTER_JS)
        except Exception:  # noqa: BLE001
            result = None
        poster = poster_url(result)
        if poster:
            film["cover_url"] = poster
            found += 1
            misses = 0
        else:
            misses += 1
        page.wait_for_timeout(PAUSE_MS)
    return found
