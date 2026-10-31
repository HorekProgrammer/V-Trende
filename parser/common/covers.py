import re

MAX_URL_LENGTH = 2000

STEAM_ASSETS_BASE = "https://shared.akamai.steamstatic.com/store_item_assets/"
STEAM_ASSET_PREFERENCE = ("library_capsule", "header", "main_capsule")
STEAM_FALLBACK_FILE = "header.jpg"


def clean_image_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://") or len(url) > MAX_URL_LENGTH or any(c.isspace() for c in url):
        return None
    return url


def largest_from_srcset(srcset) -> str | None:
    if not isinstance(srcset, str):
        return None
    best_url, best_size = None, -1.0
    for candidate in srcset.split(","):
        parts = candidate.split()
        if not parts:
            continue
        size = 1.0
        if len(parts) > 1 and parts[1][:-1]:
            try:
                size = float(parts[1][:-1])
            except ValueError:
                continue
        if size > best_size:
            best_url, best_size = parts[0], size
    return best_url


def steam_cover_url(app_id: int, assets=None) -> str | None:
    if isinstance(assets, dict):
        template = assets.get("asset_url_format")
        if isinstance(template, str) and "${FILENAME}" in template:
            for key in STEAM_ASSET_PREFERENCE:
                filename = assets.get(key)
                if isinstance(filename, str) and filename.strip():
                    url = clean_image_url(
                        STEAM_ASSETS_BASE + template.replace("${FILENAME}", filename.strip())
                    )
                    if url:
                        return url
    if type(app_id) is not int or app_id <= 0:
        return None
    return f"{STEAM_ASSETS_BASE}steam/apps/{app_id}/{STEAM_FALLBACK_FILE}"


EPIC_IMAGE_PREFERENCE = (
    "OfferImageTall",
    "DieselStoreFrontTall",
    "Thumbnail",
    "OfferImageWide",
    "DieselStoreFrontWide",
)


def epic_cover_url(key_images) -> str | None:
    if not isinstance(key_images, list):
        return None
    by_type = {}
    for image in key_images:
        if isinstance(image, dict) and isinstance(image.get("type"), str):
            url = clean_image_url(image.get("url"))
            if url:
                by_type.setdefault(image["type"], url)
    for image_type in EPIC_IMAGE_PREFERENCE:
        if image_type in by_type:
            return by_type[image_type]
    return None


COVER_SIZE = 400


def yandex_cover_url(uri) -> str | None:
    if not isinstance(uri, str) or not uri.strip():
        return None
    uri = uri.strip().replace("%%", f"{COVER_SIZE}x{COVER_SIZE}")
    if "://" not in uri and not uri.startswith("//"):
        uri = "https://" + uri
    return clean_image_url(uri)


def yandex_track_cover(track) -> str | None:
    if not isinstance(track, dict):
        return None
    candidates = [track.get("coverUri"), track.get("ogImage")]
    albums = track.get("albums")
    if isinstance(albums, list):
        for album in albums:
            if isinstance(album, dict):
                candidates.append(album.get("coverUri"))
    for candidate in candidates:
        url = yandex_cover_url(candidate)
        if url:
            return url
    return None


def apple_artwork_url(artwork) -> str | None:
    if not isinstance(artwork, dict):
        return None
    data = artwork.get("dictionary", artwork)
    template = data.get("url") if isinstance(data, dict) else None
    if not isinstance(template, str):
        return None
    url = (template.replace("{w}", str(COVER_SIZE)).replace("{h}", str(COVER_SIZE))
           .replace("{c}", "bb").replace("{f}", "jpg"))
    if "{" in url:
        return None
    return clean_image_url(url)


def zvuk_track_cover(track) -> str | None:
    if not isinstance(track, dict):
        return None
    cover = track.get("coverSrc")
    if isinstance(cover, str):
        url = clean_image_url(cover.replace("{size}", f"{COVER_SIZE}x{COVER_SIZE}"))
        if url and "{" not in url:
            return url
    release = track.get("release")
    for holder in (track, release if isinstance(release, dict) else None):
        if holder is None:
            continue
        image = holder.get("image")
        src = image.get("src") if isinstance(image, dict) else image
        if isinstance(src, str):
            url = clean_image_url(src.replace("{size}", f"{COVER_SIZE}x{COVER_SIZE}"))
            if url and "{" not in url:
                return url
    return None


def vk_track_cover(track) -> str | None:
    if not isinstance(track, list) or len(track) <= 14 or not isinstance(track[14], str):
        return None
    urls = [part for part in track[14].split(",") if part.strip()]
    return clean_image_url(urls[-1]) if urls else None


def twitch_avatar_url(src) -> str | None:
    url = clean_image_url(src)
    if url and "static-cdn.jtvnw.net" in url:
        url = re.sub(r"-profile_image-\d+x\d+\.", "-profile_image-300x300.", url)
    return url
