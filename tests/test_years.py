import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from parser.common import build_payload
from parser.common.years import iso_release_year, steam_release_year, valid_year
from parser.epic_popular.epic_popular_parser import _parse_chart as parse_epic_chart
from parser.steam.steam_parser import _parse_chart as parse_steam_chart
from parser.steam_players.steam_players_parser import _parse_chart as parse_players_chart

MONDAY = date(2026, 10, 26)


def timestamp(year, month=6, day=1):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


class YearHelpersTests(unittest.TestCase):
    def test_steam_original_date_is_preferred(self):
        item = {"release": {"steam_release_date": timestamp(2020), "original_release_date": timestamp(2015)}}
        self.assertEqual(steam_release_year(item), 2015)
        self.assertEqual(steam_release_year({"release": {"steam_release_date": timestamp(2023)}}), 2023)

    def test_steam_without_release(self):
        for item in (None, {}, {"release": None}, {"release": {"steam_release_date": 0}},
                     {"release": {"steam_release_date": timestamp(2027), "is_coming_soon": True}}):
            with self.subTest(item=item):
                self.assertIsNone(steam_release_year(item))

    def test_iso_dates(self):
        self.assertEqual(iso_release_year("2019-08-20T15:00:00.000Z"), 2019)
        self.assertEqual(iso_release_year("2024-02-01"), 2024)
        self.assertEqual(iso_release_year("1964-05-01"), 1964)
        for value in (None, "", "TBA", "2099-01-01T00:00:00.000Z", "1850-01-01"):
            with self.subTest(value=value):
                self.assertIsNone(iso_release_year(value))

    def test_valid_year_bounds(self):
        self.assertEqual(valid_year(2000), 2000)
        self.assertEqual(valid_year(1964), 1964)
        self.assertIsNone(valid_year(1899))
        self.assertIsNone(valid_year(date.today().year + 3))
        self.assertIsNone(valid_year("2020"))


class GameParsersYearTests(unittest.TestCase):
    def test_steam_top_sellers(self):
        ranks = [{
            "rank": position, "appid": 1000 + position, "consecutive_weeks": 1,
            "item": {"name": f"Game {position}",
                     "release": {"steam_release_date": timestamp(2018 + position % 5)}},
        } for position in range(1, 101)]
        chart = parse_steam_chart({"response": {"ranks": ranks}}, timeout=30)
        self.assertEqual(chart[0]["year"], 2019)

    def test_steam_most_played(self):
        ranks = [{
            "rank": position, "appid": 2000 + position,
            "concurrent_in_game": 1_000_000 - position, "peak_in_game": 1_100_000 - position,
            "item": {"name": f"Game {position}", "release": {"steam_release_date": timestamp(2012)}},
        } for position in range(1, 101)]
        chart = parse_players_chart({"response": {"ranks": ranks}}, {1: "Action"})
        self.assertEqual(chart[0]["year"], 2012)

    def test_epic(self):
        offers = [{"title": f"Game {position}", "id": f"id-{position}", "namespace": "ns",
                   "releaseDate": "2021-03-04T15:00:00.000Z" if position == 1 else None}
                  for position in range(1, 51)]
        chart = parse_epic_chart({"data": {"Storefront": {"collectionLayout": {"collectionOffers": offers}}}})
        self.assertEqual(chart[0]["year"], 2021)
        self.assertIsNone(chart[1]["year"])

    def test_year_becomes_subtitle(self):
        steam = build_payload("steam", [{"position": 1, "title": "Dota 2", "steam_app_id": 570, "year": 2013}],
                              week=MONDAY)["entries"][0]
        epic = build_payload("epic_popular", [{"position": 1, "title": "Fortnite", "epic_offer_id": "x",
                                                "year": None}], week=MONDAY)["entries"][0]
        self.assertEqual(steam["subtitle"], "2013")
        self.assertIsNone(epic["subtitle"])


if __name__ == "__main__":
    unittest.main()
