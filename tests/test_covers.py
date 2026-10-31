import re
import unittest
from datetime import date
from unittest.mock import patch

from database.load_outbox import PayloadError, _chart_entry
from parser.common import build_payload
from parser.common.covers import (
    apple_artwork_url,
    clean_image_url,
    epic_cover_url,
    largest_from_srcset,
    steam_cover_url,
    twitch_avatar_url,
    vk_track_cover,
    yandex_cover_url,
    yandex_track_cover,
    zvuk_track_cover,
)
from parser.epic_popular import epic_popular_parser
from parser.steam.steam_parser import _parse_chart as parse_steam_chart

MONDAY = date(2026, 10, 19)
STEAM = "https://shared.akamai.steamstatic.com/store_item_assets/"


class CleanImageUrlTests(unittest.TestCase):
    def test_accepts_and_normalizes(self):
        self.assertEqual(clean_image_url(" https://a.ru/x.jpg "), "https://a.ru/x.jpg")
        self.assertEqual(clean_image_url("//a.ru/x.jpg"), "https://a.ru/x.jpg")
        self.assertEqual(clean_image_url("http://a.ru/x.jpg"), "https://a.ru/x.jpg")

    def test_rejects_bad_values(self):
        for value in (None, "", 42, "data:image/gif;base64,AAA", "/images/x.jpg",
                      "javascript:alert(1)", "https://a.ru/x y.jpg", "https://a.ru/" + "x" * 2000):
            with self.subTest(value=value):
                self.assertIsNone(clean_image_url(value))

    def test_largest_from_srcset(self):
        self.assertEqual(largest_from_srcset("a.jpg 1x, b.jpg 2x"), "b.jpg")
        self.assertEqual(largest_from_srcset("a.jpg 136w, b.jpg 68w"), "a.jpg")
        self.assertEqual(largest_from_srcset("a.jpg"), "a.jpg")
        self.assertIsNone(largest_from_srcset(""))
        self.assertIsNone(largest_from_srcset(None))


class SteamCoverTests(unittest.TestCase):
    ASSETS = {
        "asset_url_format": "steam/apps/730/${FILENAME}?t=1749053861",
        "header": "header.jpg",
        "library_capsule": "abc123/library_600x900.jpg",
    }

    def test_vertical_capsule_is_preferred(self):
        self.assertEqual(
            steam_cover_url(730, self.ASSETS),
            STEAM + "steam/apps/730/abc123/library_600x900.jpg?t=1749053861",
        )

    def test_header_when_no_capsule(self):
        assets = {k: v for k, v in self.ASSETS.items() if k != "library_capsule"}
        self.assertEqual(steam_cover_url(730, assets),
                         STEAM + "steam/apps/730/header.jpg?t=1749053861")

    def test_fallback_without_assets(self):
        self.assertEqual(steam_cover_url(730), STEAM + "steam/apps/730/header.jpg")
        self.assertEqual(steam_cover_url(730, {"header": "header.jpg"}),
                         STEAM + "steam/apps/730/header.jpg")
        self.assertIsNone(steam_cover_url(0))

    def test_top_sellers_reads_assets_from_api(self):
        ranks = [{
            "rank": position, "appid": 1000 + position, "consecutive_weeks": 1,
            "item": {"name": f"Game {position}", "assets": {
                "asset_url_format": f"steam/apps/{1000 + position}/${{FILENAME}}",
                "library_capsule": "library_600x900.jpg",
            }},
        } for position in range(1, 101)]
        chart = parse_steam_chart({"response": {"ranks": ranks}}, timeout=30)
        self.assertEqual(chart[0]["cover_url"], STEAM + "steam/apps/1001/library_600x900.jpg")


class EpicCoverTests(unittest.TestCase):
    def test_prefers_tall_image(self):
        images = [
            {"type": "OfferImageWide", "url": "https://cdn1.epicgames.com/wide.jpg"},
            {"type": "OfferImageTall", "url": "https://cdn1.epicgames.com/tall.jpg"},
            {"type": "Thumbnail", "url": "https://cdn1.epicgames.com/thumb.jpg"},
        ]
        self.assertEqual(epic_cover_url(images), "https://cdn1.epicgames.com/tall.jpg")

    def test_falls_back_to_wide_and_ignores_garbage(self):
        images = [{"type": "OfferImageTall", "url": "not a url"}, "junk",
                  {"type": "OfferImageWide", "url": "https://cdn1.epicgames.com/wide.jpg"}]
        self.assertEqual(epic_cover_url(images), "https://cdn1.epicgames.com/wide.jpg")
        self.assertIsNone(epic_cover_url([{"type": "VaultClosed", "url": "https://x.ru/a.jpg"}]))
        self.assertIsNone(epic_cover_url(None))

    def test_query_without_images_is_retried(self):
        good = {"data": {"Storefront": {"collectionLayout": {"collectionOffers": []}}}}
        rejected = {"errors": [{"message": "Cannot query field keyImages"}], "data": None}
        with patch.object(epic_popular_parser, "_request",
                          side_effect=[rejected, rejected, good]) as request:
            self.assertEqual(epic_popular_parser._fetch_payload(30), good)
        queries = [call.args[0] for call in request.call_args_list]
        self.assertEqual(queries, [epic_popular_parser.QUERY_WITH_DETAILS,
                                   epic_popular_parser.QUERY_WITH_IMAGES,
                                   epic_popular_parser.QUERY])
        self.assertNotIn("keyImages", epic_popular_parser.QUERY)
        self.assertNotIn("releaseDate", epic_popular_parser.QUERY_WITH_IMAGES)

    def test_release_date_rejected_keeps_images(self):
        good = {"data": {"Storefront": {"collectionLayout": {"collectionOffers": []}}}}
        rejected = {"errors": [{"message": "Cannot query field releaseDate"}], "data": None}
        with patch.object(epic_popular_parser, "_request", side_effect=[rejected, good]) as request:
            self.assertEqual(epic_popular_parser._fetch_payload(30), good)
        self.assertEqual(request.call_args_list[-1].args[0], epic_popular_parser.QUERY_WITH_IMAGES)

    def test_http_error_on_image_query_is_retried(self):
        good = {"data": {"Storefront": {"collectionLayout": {"collectionOffers": []}}}}
        with patch.object(epic_popular_parser, "_request",
                          side_effect=[RuntimeError("HTTP 400"), RuntimeError("HTTP 400"), good]):
            self.assertEqual(epic_popular_parser._fetch_payload(30), good)

    def test_image_query_used_when_it_works(self):
        good = {"data": {"Storefront": {"collectionLayout": {"collectionOffers": []}}}}
        with patch.object(epic_popular_parser, "_request", return_value=good) as request:
            epic_popular_parser._fetch_payload(30)
        request.assert_called_once_with(epic_popular_parser.QUERY_WITH_DETAILS, 30)


class PayloadCoverTests(unittest.TestCase):
    def test_cover_goes_into_payload_and_bad_cover_is_dropped(self):
        films = [
            {"position": 1, "title": "Фильм", "kinopoisk_id": 1, "year": 2026,
             "cover_url": "//avatars.mds.yandex.net/get-kinopoisk-image/1/1/136x204"},
            {"position": 2, "title": "Без постера", "kinopoisk_id": 2, "year": 2026,
             "cover_url": "data:image/gif;base64,AAA"},
        ]
        entries = build_payload("kinopoisk", films, week=MONDAY)["entries"]
        self.assertEqual(entries[0]["cover_url"],
                         "https://avatars.mds.yandex.net/get-kinopoisk-image/1/1/136x204")
        self.assertIsNone(entries[1]["cover_url"])

    def test_loader_accepts_only_https(self):
        base = {"position": 1, "title": "Игра", "match_key": "игра"}
        self.assertIsNone(_chart_entry(base, "steam")["cover_url"])
        self.assertEqual(
            _chart_entry({**base, "cover_url": "https://x.ru/a.jpg"}, "steam")["cover_url"],
            "https://x.ru/a.jpg",
        )
        for bad in ("http://x.ru/a.jpg", "javascript:alert(1)", 5):
            with self.subTest(bad=bad), self.assertRaises(PayloadError):
                _chart_entry({**base, "cover_url": bad}, "steam")


class MusicAndTwitchCoverTests(unittest.TestCase):
    def test_yandex(self):
        self.assertEqual(yandex_cover_url("avatars.yandex.net/get-music-content/1/a/%%"),
                         "https://avatars.yandex.net/get-music-content/1/a/400x400")
        track = {"albums": [{"coverUri": "avatars.yandex.net/get-music-content/2/b/%%"}]}
        self.assertEqual(yandex_track_cover(track),
                         "https://avatars.yandex.net/get-music-content/2/b/400x400")
        for value in (None, "", {"coverUri": None}, {"albums": "junk"}):
            with self.subTest(value=value):
                self.assertIsNone(yandex_track_cover(value))

    def test_apple(self):
        artwork = {"dictionary": {"url": "https://is1-ssl.mzstatic.com/x/{w}x{h}{c}.{f}"}}
        self.assertEqual(apple_artwork_url(artwork), "https://is1-ssl.mzstatic.com/x/400x400bb.jpg")
        self.assertIsNone(apple_artwork_url({"dictionary": {"url": "https://a/{w}x{h}{q}.jpg"}}))
        self.assertIsNone(apple_artwork_url(None))

    def test_zvuk(self):
        release = {"release": {"image": {"src": "https://cdn-image.zvuk.com/pic?id=1&size={size}"}}}
        self.assertEqual(zvuk_track_cover(release), "https://cdn-image.zvuk.com/pic?id=1&size=400x400")
        self.assertIsNone(zvuk_track_cover({"image": {"src": "https://a/{other}"}}))
        self.assertIsNone(zvuk_track_cover({"image": None}))

    def test_vk(self):
        track = [0] * 15
        track[14] = "https://sun9.userapi.com/small.jpg,https://sun9.userapi.com/big.jpg"
        self.assertEqual(vk_track_cover(track), "https://sun9.userapi.com/big.jpg")
        track[14] = ""
        self.assertIsNone(vk_track_cover(track))
        self.assertIsNone(vk_track_cover([0] * 5))

    def test_twitch(self):
        self.assertEqual(
            twitch_avatar_url("https://static-cdn.jtvnw.net/jtv_user_pictures/a-profile_image-70x70.png"),
            "https://static-cdn.jtvnw.net/jtv_user_pictures/a-profile_image-300x300.png",
        )
        self.assertIsNone(twitch_avatar_url(None))


class ChartsWithoutCoversTests(unittest.TestCase):
    def test_music_parsers_without_images(self):
        from parser.kion import parse_chart_html as kion
        from parser.shazam import parse_chart_html as shazam
        from parser.zvuk import parse_chart_html as zvuk
        from tests import test_kion, test_shazam, test_zvuk

        kion_tracks = test_kion.tracks()
        for track in kion_tracks:
            del track["coverUri"]
        zvuk_tracks = test_zvuk.tracks()
        for track in zvuk_tracks:
            del track["image"]
        shazam_page = re.sub(r"<img[^>]*>", "", test_shazam.chart_page())

        for name, result in (("kion", kion(test_kion.page(kion_tracks))),
                             ("zvuk", zvuk(test_zvuk.page(zvuk_tracks))),
                             ("shazam", shazam(shazam_page))):
            with self.subTest(parser=name):
                self.assertGreaterEqual(len(result), 100)
                self.assertTrue(all(track["cover_url"] is None for track in result))

    def test_twitch_without_avatar(self):
        from parser.twitch import parse_ranking_positions_html
        from tests.test_twitch import page

        html = re.sub(r"<img[^>]*>", "<img>", page())
        result = parse_ranking_positions_html(html)
        self.assertEqual(len(result), 50)
        self.assertIsNone(result[0]["cover_url"])

    def test_twitch_cover_reaches_payload(self):
        from parser.twitch import parse_ranking_positions_html
        from tests.test_twitch import page

        channels = parse_ranking_positions_html(page())
        entry = build_payload("twitch", channels, week=MONDAY)["entries"][0]
        self.assertEqual(entry["cover_url"],
                         "https://static-cdn.jtvnw.net/jtv_user_pictures/ch1-profile_image-300x300.png")


if __name__ == "__main__":
    unittest.main()
