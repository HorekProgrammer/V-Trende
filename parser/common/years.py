from datetime import date, datetime, timezone

MIN_YEAR = 1900
MAX_YEARS_AHEAD = 2


def valid_year(year) -> int | None:
    if type(year) is not int:
        return None
    if not MIN_YEAR <= year <= date.today().year + MAX_YEARS_AHEAD:
        return None
    return year


def _timestamp_year(value) -> int | None:
    if type(value) is not int or value <= 0:
        return None
    try:
        return valid_year(datetime.fromtimestamp(value, tz=timezone.utc).year)
    except (OverflowError, OSError, ValueError):
        return None


def steam_release_year(item) -> int | None:
    if not isinstance(item, dict):
        return None
    release = item.get("release")
    if not isinstance(release, dict) or release.get("is_coming_soon") is True:
        return None
    for key in ("original_release_date", "steam_release_date"):
        year = _timestamp_year(release.get(key))
        if year:
            return year
    return None


def iso_release_year(value) -> int | None:
    if not isinstance(value, str) or len(value) < 4 or not value[:4].isdigit():
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if moment.astimezone(timezone.utc).date() > date.today():
        return None
    return valid_year(moment.year)


def yandex_track_year(track) -> int | None:
    if not isinstance(track, dict):
        return None
    albums = track.get("albums")
    if not isinstance(albums, list):
        return None
    for album in albums:
        if isinstance(album, dict):
            year = valid_year(album.get("year")) or iso_release_year(album.get("releaseDate"))
            if year:
                return year
    return None
