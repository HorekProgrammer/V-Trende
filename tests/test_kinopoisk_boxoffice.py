import unittest
from unittest.mock import patch

from parser.kinopoisk_boxoffice.kinopoisk_boxoffice_parser import (
    _extract_kinopoisk_id,
    _extract_weeks,
    _optional_first_number,
    _parse_row,
    get_kinopoisk_boxoffice,
)


class KinopoiskBoxOfficeTests(unittest.TestCase):
    def test_parses_first_chart_row(self):
        cells = [
            "1.",
            "Битва моторов",
            "Централ Партнершип [1]",
            "285 986 706, ~ 142 353",
            "289 744 710, ~ 144 223",
            "527 646",
            "530 843",
            "2 009",
        ]

        result = _parse_row(
            position=1,
            cells=cells,
            title="Битва моторов",
            href="/film/5505674/",
        )

        self.assertEqual(
            result,
            {
                "position": 1,
                "title": "Битва моторов",
                "kinopoisk_id": 5505674,
                "weeks_in_release": 1,
                "box_office": 285986706,
                "total_box_office": 289744710,
                "viewers": 527646,
                "total_viewers": 530843,
                "copies": 2009,
            },
        )

    def test_ignores_change_percentages(self):
        cells = [
            "2. -1",
            "Приключения мамонтёнка",
            "NMG Kinoprokat [2]",
            "74 714 381 ↓24%, ~ 33 961",
            "200 467 604, ~ 91 122",
            "189 407 ↓22%",
            "508 739",
            "2 200 +3",
        ]

        result = _parse_row(
            position=2,
            cells=cells,
            title="Приключения мамонтёнка",
            href="/film/11826673/",
        )

        self.assertEqual(result["position"], 2)
        self.assertEqual(result["weeks_in_release"], 2)
        self.assertEqual(result["box_office"], 74714381)
        self.assertEqual(result["viewers"], 189407)
        self.assertEqual(result["copies"], 2200)

    def test_allows_missing_number(self):
        self.assertIsNone(
            _optional_first_number(
                "-",
                "weekend viewers",
            )
        )

        self.assertIsNone(
            _optional_first_number(
                "—",
                "weekend viewers",
            )
        )

    def test_extracts_large_weeks_count(self):
        self.assertEqual(
            _extract_weeks(
                "Samokat [1 095]"
            ),
            1095,
        )

    def test_extracts_weeks(self):
        self.assertEqual(
            _extract_weeks(
                "West / Kino.Art.Pro [4]"
            ),
            4,
        )

    def test_extracts_film_id(self):
        self.assertEqual(
            _extract_kinopoisk_id(
                "/film/420224/"
            ),
            420224,
        )

    def test_rejects_invalid_row(self):
        with self.assertRaises(RuntimeError):
            _parse_row(
                position=1,
                cells=["1.", "Movie"],
                title="Movie",
                href="/film/123/",
            )

    @patch(
        "parser.kinopoisk_boxoffice."
        "kinopoisk_boxoffice_parser._fetch_chart"
    )
    def test_limit_is_passed_to_fetcher(
        self,
        fetch_chart,
    ):
        fetch_chart.return_value = []

        get_kinopoisk_boxoffice(
            limit=10,
        )

        fetch_chart.assert_called_once_with(
            limit=10,
            timeout=60,
            headless=True,
        )

    @patch(
        "parser.kinopoisk_boxoffice."
        "kinopoisk_boxoffice_parser._fetch_chart"
    )
    def test_invalid_arguments_do_not_fetch(
        self,
        fetch_chart,
    ):
        for value in [
            0,
            -1,
            True,
            1.5,
            "10",
        ]:
            with self.subTest(limit=value):
                with self.assertRaises(ValueError):
                    get_kinopoisk_boxoffice(
                        limit=value
                    )

        for value in [
            0,
            -1,
            True,
            float("inf"),
            float("nan"),
            "60",
        ]:
            with self.subTest(timeout=value):
                with self.assertRaises(ValueError):
                    get_kinopoisk_boxoffice(
                        timeout=value
                    )

        for value in [
            0,
            1,
            None,
            "yes",
        ]:
            with self.subTest(headless=value):
                with self.assertRaises(ValueError):
                    get_kinopoisk_boxoffice(
                        headless=value
                    )

        fetch_chart.assert_not_called()


if __name__ == "__main__":
    unittest.main()