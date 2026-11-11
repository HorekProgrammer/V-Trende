"""Download external cover images into the shared local media directory."""

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .db import PROJECT_ROOT

COVER_DIR = Path(os.environ.get("COVER_STORAGE_DIR") or PROJECT_ROOT / "data" / "covers")
PUBLIC_PREFIX = "/media/covers/"
MAX_IMAGE_BYTES = 12 * 1024 * 1024


class ImageDownloadError(RuntimeError):
    """An external image could not be safely saved."""


def _image_extension(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis"}:
        return ".avif"
    return None


def is_local_cover(url: str | None) -> bool:
    return isinstance(url, str) and url.startswith(PUBLIC_PREFIX)


def localize_image(url: str | None, *, timeout: float = 25) -> str | None:
    """Return a local media URL, downloading an HTTPS image once when necessary."""
    if not url or is_local_cover(url):
        return url
    if urlparse(url).scheme != "https":
        raise ImageDownloadError("cover URL must use HTTPS")

    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    cached = next(COVER_DIR.glob(f"{key}.*"), None)
    if cached is not None and cached.is_file():
        return PUBLIC_PREFIX + cached.name

    request = Request(url, headers={
        "User-Agent": "V-Trende/1.0 (+https://github.com/HorekProgrammer/V-Trende)",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif;q=0.8,*/*;q=0.1",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            if urlparse(final_url).scheme != "https":
                raise ImageDownloadError("image redirected outside HTTPS")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_IMAGE_BYTES:
                raise ImageDownloadError("image is too large")
            data = response.read(MAX_IMAGE_BYTES + 1)
    except (HTTPError, URLError, OSError, ValueError) as error:
        raise ImageDownloadError(str(error)) from None

    if len(data) > MAX_IMAGE_BYTES:
        raise ImageDownloadError("image is too large")
    extension = _image_extension(data)
    if extension is None:
        raise ImageDownloadError("response is not a supported raster image")

    destination = COVER_DIR / f"{key}{extension}"
    handle, temporary = tempfile.mkstemp(prefix=f".{key}-", dir=COVER_DIR)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return PUBLIC_PREFIX + destination.name


def localize_payload_covers(payload: dict, *, timeout: float = 25) -> tuple[int, int]:
    """Replace external chart cover URLs with local URLs; failed downloads are omitted."""
    saved = failed = 0
    for entry in payload.get("entries") or []:
        url = entry.get("cover_url")
        if not url or is_local_cover(url):
            continue
        try:
            entry["cover_url"] = localize_image(url, timeout=timeout)
            saved += 1
        except ImageDownloadError:
            entry["cover_url"] = None
            failed += 1
    return saved, failed
