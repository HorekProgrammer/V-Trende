"""Реестр чартов: источник, категория, лимит и перевод результата парсера в общий формат.

Лимиты по категориям (README, «Анализ нагрузок»): 100 треков, 100 игр,
50 фильмов, 50 стримеров. Каждый чарт категории обрезается до этого лимита,
поэтому позиции разных чартов одной категории сопоставимы.
"""

from dataclasses import dataclass
from typing import Callable

from .circuit_breaker import protected_call
from .normalize import match_key

CATEGORY_LIMITS = {
    "music": 100,
    "games": 100,
    "movies": 50,
    "streamers": 50,
}

@dataclass(frozen=True)
class Chart:
    key: str
    source: str
    name: str
    category: str
    # Сколько позиций источник отдаёт максимум; None — заранее неизвестно.
    size: int | None
    fetch: Callable[[int], list[dict]]
    to_entry: Callable[[dict], dict]

    @property
    def limit(self) -> int:
        category_limit = CATEGORY_LIMITS[self.category]
        return category_limit if self.size is None else min(category_limit, self.size)


def _entry(item: dict, *, title: str, key: str, subtitle=None,
           external_id=None, url=None) -> dict:
    return {
        "position": item["position"],
        "title": title,
        "subtitle": subtitle,
        # Жанры будет проставлять нейросеть; парсеры их не определяют.
        # Поле оставлено в формате, чтобы позже передавать жанр тем же пакетом.
        "genre": None,
        "external_id": None if external_id is None else str(external_id),
        "url": url,
        "match_key": key,
    }


def music_entry(item: dict) -> dict:
    # Музыкальные парсеры не отдают ID трека: объект опознаётся по match_key.
    return _entry(
        item,
        title=item["title"],
        subtitle=", ".join(item["artists"]),
        key=match_key(item["title"], item["artists"]),
    )


def steam_entry(item: dict) -> dict:
    app_id = item["steam_app_id"]
    return _entry(
        item,
        title=item["title"],
        key=match_key(item["title"]),
        external_id=app_id,
        url=f"https://store.steampowered.com/app/{app_id}/",
    )


def epic_entry(item: dict) -> dict:
    slug = item.get("epic_slug")
    return _entry(
        item,
        title=item["title"],
        key=match_key(item["title"]),
        external_id=item["epic_offer_id"],
        url=f"https://store.epicgames.com/ru/p/{slug}" if slug else None,
    )


def kinopoisk_entry(item: dict) -> dict:
    film_id = item["kinopoisk_id"]
    year = item.get("year")
    return _entry(
        item,
        title=item["title"],
        key=match_key(item["title"]),
        subtitle=str(year) if year else None,
        external_id=film_id,
        url=f"https://www.kinopoisk.ru/film/{film_id}/",
    )


def twitch_entry(item: dict) -> dict:
    slug = item["slug"].lower()
    entry = _entry(
        item,
        title=item["channel"],
        key=match_key(slug),
        external_id=slug,
        url=f"https://www.twitch.tv/{slug}",
    )
    entry.update({
        "total_followers": item.get("total_followers", 0),
        "hours_streamed": item.get("hours_streamed", 0),
        "average_viewers": item.get("average_viewers", 0),
        "peak_viewers": item.get("peak_viewers", 0),
        "hours_watched": item.get("hours_watched", 0),
        "followers_gained": item.get("followers_gained", 0),
        "followers_per_hour": item.get("followers_per_hour", 0),
    })
    return entry


# Импорт парсеров внутри функций: модуль можно импортировать без Playwright
# и без настроек VK/Wordstat, а ошибка одного парсера не ломает остальные.
def _yandex_music(limit):
    from parser.yandex_music import get_yandex_music_chart
    return protected_call("yandex_music", get_yandex_music_chart, limit)


def _zvuk(limit):
    from parser.zvuk import get_zvuk_chart
    return protected_call("zvuk", get_zvuk_chart, limit, browser_fallback=True)


def _shazam(limit):
    from parser.shazam import get_shazam_chart
    return protected_call("shazam", get_shazam_chart, limit)


def _vk(limit):
    from parser.vk import get_vk_chart
    return protected_call("vk", get_vk_chart, limit)


def _apple_music(limit):
    from parser.apple_music import get_apple_music_chart
    return protected_call("apple_music", get_apple_music_chart, limit)


def _kion(limit):
    from parser.kion import get_kion_chart
    return protected_call("kion", get_kion_chart, limit)


def _steam(limit):
    from parser.steam import get_steam_chart
    return protected_call("steam", get_steam_chart, limit=limit)


def _steam_players(limit):
    from parser.steam_players import get_steam_players_chart
    return protected_call("steam", get_steam_players_chart, limit=limit)


def _epic_most_played(limit):
    from parser.epic_most_played import get_epic_most_played_chart
    return protected_call("epic", get_epic_most_played_chart, limit=limit)


def _epic_popular(limit):
    from parser.epic_popular import get_epic_popular_chart
    return protected_call("epic", get_epic_popular_chart, limit=limit)


def _kinopoisk(limit):
    from parser.kinopoisk import get_kinopoisk_chart
    return protected_call("kinopoisk", get_kinopoisk_chart, limit)


def _kinopoisk_boxoffice(limit):
    from parser.kinopoisk_boxoffice import get_kinopoisk_boxoffice
    return protected_call("kinopoisk", get_kinopoisk_boxoffice, limit=limit)


def _twitch(limit):
    from parser.twitch import get_cached_russian_twitch_ranking
    return protected_call("twitch", get_cached_russian_twitch_ranking, limit)


CHARTS = {chart.key: chart for chart in (
    Chart("yandex_music", "yandex_music", "Чарт", "music", 100, _yandex_music, music_entry),
    Chart("zvuk", "zvuk", "Топ-100", "music", 100, _zvuk, music_entry),
    Chart("shazam", "shazam", "Топ-200 Россия", "music", 200, _shazam, music_entry),
    Chart("vk", "vk", "Чарт VK Музыки", "music", 100, _vk, music_entry),
    Chart("apple_music", "apple_music", "Топ-100 Россия", "music", 100, _apple_music, music_entry),
    Chart("kion", "kion", "Настоящий чарт", "music", 100, _kion, music_entry),
    Chart("steam", "steam", "Top Sellers", "games", 100, _steam, steam_entry),
    Chart("steam_players", "steam", "Most Played", "games", 100, _steam_players, steam_entry),
    Chart("epic_most_played", "epic", "Most Played", "games", 100, _epic_most_played, epic_entry),
    Chart("epic_popular", "epic", "Most Popular", "games", 50, _epic_popular, epic_entry),
    Chart("kinopoisk", "kinopoisk", "Популярные фильмы", "movies", 1000, _kinopoisk, kinopoisk_entry),
    Chart("kinopoisk_boxoffice", "kinopoisk", "Кассовые сборы выходных", "movies", None,
          _kinopoisk_boxoffice, kinopoisk_entry),
    Chart("twitch", "twitch", "Русскоязычные стримеры", "streamers", 150, _twitch, twitch_entry),
)}
