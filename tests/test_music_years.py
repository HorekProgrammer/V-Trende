import json
import unittest
from datetime import date
from unittest.mock import patch

from database.load_outbox import PayloadError, _chart_entry
from parser.apple_music import itunes_years
from parser.apple_music.apple_music_parser import _apple_id
from parser.common import build_payload
from parser.common.covers import zvuk_track_cover
from parser.common.years import yandex_track_year

MONDAY = date(2026, 10, 26)


def itunes_response(results):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"resultCount": len(results), "results": results}).encode()

    return Response()


class YandexYearTests(unittest.TestCase):
    def test_album_year_and_release_date(self):
        self.assertEqual(yandex_track_year({"albums": [{"id": 1, "year": 2026}]}), 2026)
        self.assertEqual(yandex_track_year({"albums": [{"releaseDate": "2024-07-24T00:00:00+03:00"}]}), 2024)
        self.assertEqual(yandex_track_year({"albums": [{"year": None}, {"year": 2019}]}), 2019)

    def test_missing_year(self):
        for track in (None, {}, {"albums": None}, {"albums": ["junk"]}, {"albums": [{"year": "2026"}]}):
            with self.subTest(track=track):
                self.assertIsNone(yandex_track_year(track))


class AppleYearTests(unittest.TestCase):
    def test_apple_id_from_chart_item(self):
        item = {"contentDescriptor": {"kind": "song", "identifiers": {"storeAdamID": "6820477982"}}}
        self.assertEqual(_apple_id(item), "6820477982")
        self.assertIsNone(_apple_id({"contentDescriptor": {"identifiers": {"storeAdamID": "pl.abc"}}}))
        self.assertIsNone(_apple_id({}))

    @patch.object(itunes_years, "urlopen")
    def test_fill_years_in_batches(self, opened):
        tracks = [{"apple_id": str(i), "year": None} for i in range(1, 201)]
        opened.side_effect = [
            itunes_response([{"wrapperType": "track", "trackId": 1, "releaseDate": "2025-01-10T12:00:00Z"},
                             {"wrapperType": "collection", "collectionId": 2, "releaseDate": "2001-01-01T00:00:00Z"}]),
            itunes_response([{"wrapperType": "track", "trackId": 200, "releaseDate": "1999-05-01T07:00:00Z"}]),
        ]
        self.assertEqual(itunes_years.fill_years(tracks), 2)
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(tracks[0]["year"], 2025)
        self.assertIsNone(tracks[1]["year"])
        self.assertEqual(tracks[199]["year"], 1999)

    @patch.object(itunes_years, "urlopen", side_effect=OSError("network down"))
    def test_itunes_failure_is_not_fatal(self, _opened):
        tracks = [{"apple_id": "1", "year": None}]
        self.assertEqual(itunes_years.fill_years(tracks), 0)
        self.assertIsNone(tracks[0]["year"])

    @patch.object(itunes_years, "urlopen")
    def test_no_request_without_ids(self, opened):
        itunes_years.fill_years([{"apple_id": None, "year": None}, {"apple_id": "5", "year": 2020}])
        opened.assert_not_called()


class ZvukCoverTests(unittest.TestCase):
    def test_cover_src_from_real_track(self):
        track = {
            "id": "180359844", "title": "Ты не бойся ночи",
            "release": {"id": "50386921", "title": "Ты не бойся ночи"},
            "coverSrc": "https://cdn-image.zvuk.com/pic?hash=22b4&id=50386921&size={size}&type=release",
            "publicationDate": None,
        }
        self.assertEqual(zvuk_track_cover(track),
                         "https://cdn-image.zvuk.com/pic?hash=22b4&id=50386921&size=400x400&type=release")


class YearPayloadTests(unittest.TestCase):
    def test_music_year_goes_to_payload_not_subtitle(self):
        track = {"position": 1, "title": "ДИНАСТИЯ", "artists": ["VILLIAN", "madk1d"], "year": 2026}
        entry = build_payload("yandex_music", [track], week=MONDAY)["entries"][0]
        self.assertEqual(entry["year"], 2026)
        self.assertEqual(entry["subtitle"], "VILLIAN, madk1d")

    def test_invalid_year_is_dropped(self):
        track = {"position": 1, "title": "Песня", "artists": ["Артист"], "year": 3000}
        self.assertIsNone(build_payload("vk", [track], week=MONDAY)["entries"][0]["year"])

    def test_loader_validates_year(self):
        base = {"position": 1, "title": "Песня", "match_key": "артист|песня"}
        self.assertIsNone(_chart_entry(base, "vk")["year"])
        self.assertEqual(_chart_entry({**base, "year": 2026}, "vk")["year"], 2026)
        for bad in (1800, 2200, "2026", 2026.0):
            with self.subTest(bad=bad), self.assertRaises(PayloadError):
                _chart_entry({**base, "year": bad}, "vk")


if __name__ == "__main__":
    unittest.main()
