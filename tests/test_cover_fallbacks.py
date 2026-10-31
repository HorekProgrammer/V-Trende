import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from parser.kinopoisk.posters import fill_missing_details, film_year, poster_url
from parser.twitch import avatars
from parser.twitch.avatars import avatar_from_channel_html, fill_missing_avatars
from parser.twitch.twitch_parser import parse_ranking_markdown, parse_ranking_positions_html

POSTER = "https://avatars.mds.yandex.net/get-kinopoisk-image/1/abc/orig"
AVATAR = "https://static-cdn.jtvnw.net/jtv_user_pictures/abc-profile_image-300x300.png"


class FakePage:
    def __init__(self, posters, fail=(), headings=None):
        self.posters, self.fail, self.visited = posters, set(fail), []
        self.headings = headings or {}
        self.current = None

    def goto(self, url, **kwargs):
        self.visited.append(url)
        if url in self.fail:
            raise TimeoutError("timeout")
        self.current = url

    def wait_for_selector(self, selector, timeout=None):
        if self.current not in self.posters:
            raise TimeoutError("no poster")

    def evaluate(self, script):
        poster = self.posters.get(self.current)
        heading = self.headings.get(self.current)
        if poster is None and heading is None:
            return None
        return {"srcset": "", "src": poster or "", "heading": heading or "", "title": ""}

    def wait_for_timeout(self, ms):
        pass


def film_url(film_id):
    return f"https://www.kinopoisk.ru/film/{film_id}/"


class KinopoiskPosterTests(unittest.TestCase):
    def test_only_real_posters_are_accepted(self):
        self.assertEqual(poster_url({"src": POSTER}), POSTER)
        self.assertEqual(
            poster_url({"srcset": "//avatars.mds.yandex.net/get-kinopoisk-image/1/a/300x450 1x, "
                                  "//avatars.mds.yandex.net/get-kinopoisk-image/1/a/600x900 2x",
                        "src": "//avatars.mds.yandex.net/get-kinopoisk-image/1/a/300x450"}),
            "https://avatars.mds.yandex.net/get-kinopoisk-image/1/a/600x900",
        )
        self.assertIsNone(poster_url({"src": "https://yastatic.net/s3/kinopoisk-frontend/logo.png"}))
        self.assertIsNone(poster_url({"src": "https://evil.example/get-kinopoisk-image/1/a/300x450"}))
        self.assertIsNone(poster_url({"src": "https://avatars.mds.yandex.net/get-bunker/1/a/orig"}))

    def test_cdn_host_is_replaced_with_canonical(self):
        cdn = "//cdnrrviubnyuntopbez5.svc.cdn.yandex.net/get-kinopoisk-image/10953618/e0ca91d6"
        found = {"srcset": f"{cdn}/300x450 1x, {cdn}/600x900 2x", "src": f"{cdn}/300x450"}
        self.assertEqual(
            poster_url(found),
            "https://avatars.mds.yandex.net/get-kinopoisk-image/10953618/e0ca91d6/600x900",
        )
        self.assertIsNone(poster_url(None))

    def test_open_graph_card_is_not_used(self):
        page = FakePage({})
        films = [{"kinopoisk_id": 1, "cover_url": None, "year": 2026}]
        fill_missing_details(page, films, 30)
        self.assertIsNone(films[0]["cover_url"])

    def test_fills_only_missing(self):
        films = [{"kinopoisk_id": 1, "cover_url": "https://x/already.jpg", "year": 2026},
                 {"kinopoisk_id": 2, "cover_url": None, "year": 2026},
                 {"kinopoisk_id": 3, "year": 2025}]
        page = FakePage({film_url(2): POSTER, film_url(3): POSTER + "3"})
        self.assertEqual(fill_missing_details(page, films, 30), 2)
        self.assertEqual([f["cover_url"] for f in films], ["https://x/already.jpg", POSTER, POSTER + "3"])
        self.assertEqual(page.visited, [film_url(2), film_url(3)])

    def test_stops_after_several_misses(self):
        films = [{"kinopoisk_id": i, "cover_url": None} for i in range(1, 11)]
        page = FakePage({}, fail={film_url(1)})
        self.assertEqual(fill_missing_details(page, films, 30), 0)
        self.assertEqual(len(page.visited), 3)
        self.assertTrue(all(f["cover_url"] is None for f in films))


class KinopoiskYearTests(unittest.TestCase):
    def test_year_from_heading_and_title(self):
        self.assertEqual(film_year({"heading": "Чудо-Юдо (2026)", "title": ""}), 2026)
        self.assertEqual(film_year({"heading": "Игра престолов (сериал 2011 – 2019)"}), 2011)
        self.assertEqual(
            film_year({"heading": "Без года", "title": "Морозко фильм, 1964, дата выхода трейлеры"}), 1964)
        self.assertIsNone(film_year({"heading": "1+1", "title": "Кинопоиск"}))
        self.assertIsNone(film_year(None))

    def test_box_office_film_gets_year_and_poster(self):
        films = [{"kinopoisk_id": 7, "year": None, "cover_url": None},
                 {"kinopoisk_id": 8, "year": 2024, "cover_url": POSTER}]
        page = FakePage({film_url(7): POSTER}, headings={film_url(7): "Чудо-Юдо (2026)"})
        self.assertEqual(fill_missing_details(page, films, 30), 1)
        self.assertEqual((films[0]["year"], films[0]["cover_url"]), (2026, POSTER))
        self.assertEqual(page.visited, [film_url(7)])

    def test_year_reaches_subtitle(self):
        from parser.common import build_payload
        from datetime import date
        film = {"position": 1, "title": "Чудо-Юдо", "kinopoisk_id": 7, "year": 2026, "cover_url": POSTER}
        entry = build_payload("kinopoisk_boxoffice", [film], week=date(2026, 10, 26))["entries"][0]
        self.assertEqual(entry["subtitle"], "2026")


class TwitchAvatarSourcesTests(unittest.TestCase):
    def test_lazy_image_attribute(self):
        from tests.test_twitch import page
        html = page().replace(
            '<img src="https://static-cdn.jtvnw.net/jtv_user_pictures/ch1-profile_image-70x70.png">',
            '<img src="data:image/gif;base64,R0lGOD" '
            'data-src="https://static-cdn.jtvnw.net/jtv_user_pictures/lazy-profile_image-70x70.png">',
        )
        result = parse_ranking_positions_html(html)
        self.assertEqual(result[0]["cover_url"],
                         "https://static-cdn.jtvnw.net/jtv_user_pictures/lazy-profile_image-300x300.png")

    def test_markdown_row_with_and_without_avatar(self):
        markdown = (
            "#1 | streamer_one | ![](https://static-cdn.jtvnw.net/jtv_user_pictures/s1-profile_image-70x70.png) | 100\n"
            "#2 | streamer_two | 200\n"
        )
        result = parse_ranking_markdown(markdown)
        self.assertEqual([r["_slug"] for r in result], ["streamer_one", "streamer_two"])
        self.assertEqual(result[0]["_cover"],
                         "https://static-cdn.jtvnw.net/jtv_user_pictures/s1-profile_image-300x300.png")
        self.assertIsNone(result[1]["_cover"])

    def test_avatar_from_channel_page(self):
        html = f'''<html><head>
            <meta property="og:image" content="https://static.twitchcdn.net/assets/favicon-32.png">
            <meta content="{AVATAR}" name="twitter:image">
        </head></html>'''
        self.assertEqual(avatar_from_channel_html(html), AVATAR)
        self.assertIsNone(avatar_from_channel_html("<html><meta property='og:image' "
                                                   "content='https://static.twitchcdn.net/logo.png'></html>"))
        self.assertIsNone(avatar_from_channel_html(""))


class FillMissingAvatarsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "avatars.json"

    def tearDown(self):
        self.tmp.cleanup()

    @patch.object(avatars, "sleep")
    @patch.object(avatars, "fetch_avatar")
    def test_fetches_only_missing_and_caches(self, fetch, _sleep):
        fetch.side_effect = lambda slug, timeout: AVATAR.replace("abc", slug)
        channels = [{"slug": "has", "cover_url": "https://static-cdn.jtvnw.net/jtv_user_pictures/has-profile_image-300x300.png"},
                    {"slug": "Missing", "cover_url": None}]
        self.assertEqual(fill_missing_avatars(channels, cache_path=self.cache), 1)
        fetch.assert_called_once_with("missing", 30)
        self.assertIn("missing-profile_image", channels[1]["cover_url"])
        cached = json.loads(self.cache.read_text(encoding="utf-8"))
        self.assertEqual(set(cached), {"has", "missing"})

        fetch.reset_mock()
        again = [{"slug": "missing", "cover_url": None}]
        fill_missing_avatars(again, cache_path=self.cache)
        fetch.assert_not_called()
        self.assertEqual(again[0]["cover_url"], channels[1]["cover_url"])

    @patch.object(avatars, "sleep")
    @patch.object(avatars, "fetch_avatar", return_value=None)
    def test_gives_up_when_twitch_does_not_answer(self, fetch, _sleep):
        channels = [{"slug": f"ch{i}", "cover_url": None} for i in range(20)]
        self.assertEqual(fill_missing_avatars(channels, cache_path=self.cache), 0)
        self.assertEqual(fetch.call_count, avatars.MAX_MISSES_IN_ROW)
        self.assertTrue(all(c["cover_url"] is None for c in channels))

    @patch.object(avatars, "urlopen", side_effect=OSError("network down"))
    def test_network_error_is_not_fatal(self, _urlopen):
        self.assertIsNone(avatars.fetch_avatar("someone", 30))


if __name__ == "__main__":
    unittest.main()
