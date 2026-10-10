import unittest
from unittest.mock import patch

from parser.kinopoisk import get_kinopoisk_chart
from parser.kinopoisk.kinopoisk_parser import PAGE_SIZE, _parse_page


def chart_page(page_number=1, size=50):
    start = (page_number - 1) * PAGE_SIZE + 1

    return [
        {
            "href": f"/film/{1000000 + position}/",
            "title": f"Фильм {position}",
            "text": (
                f"{position}\n"
                f"Фильм {position}\n"
                f"Original Title\n"
                f", 2026, 1 ч 30 мин\n"
                f"Россия • драма\n"
                f"Рейтинг Кинопоиска 7.5\n"
                f"7.5\n"
                f"10 000 оценок"
            ),
        }
        for position in range(start, start + size)
    ]


class KinopoiskTests(unittest.TestCase):
    def test_parses_first_page(self):
        result = _parse_page(chart_page(), 1)

        self.assertEqual(len(result), 50)

        self.assertEqual(result[0], {
            "position": 1,
            "title": "Фильм 1",
            "kinopoisk_id": 1000001,
            "year": 2026,
            "rating": 7.5,
        })

        self.assertEqual(result[-1]["position"], 50)

    def test_second_page_positions_start_from_51(self):
        result = _parse_page(chart_page(page_number=2), 2)

        self.assertEqual(result[0]["position"], 51)
        self.assertEqual(result[-1]["position"], 100)

    def test_allows_missing_rating(self):
        items = chart_page()
        items[4]["text"] = (
            "5\n"
            "Фильм 5\n"
            "2026, 1 ч 30 мин\n"
            "Россия • приключения\n"
            "—\n"
            "Буду смотреть"
        )

        result = _parse_page(items, 1)

        self.assertIsNone(result[4]["rating"])

    def test_rejects_incomplete_page(self):
        with self.assertRaises(RuntimeError):
            _parse_page(chart_page(size=49), 1)

    def test_rejects_invalid_movie(self):
        cases = []

        missing_title = chart_page()
        missing_title[5]["title"] = ""
        cases.append(missing_title)

        invalid_href = chart_page()
        invalid_href[5]["href"] = "/series/123/"
        cases.append(invalid_href)

        missing_year = chart_page()
        missing_year[5]["text"] = "Фильм без года"
        cases.append(missing_year)

        duplicate_id = chart_page()
        duplicate_id[5]["href"] = duplicate_id[4]["href"]
        cases.append(duplicate_id)

        for items in cases:
            with self.subTest(), self.assertRaises(RuntimeError):
                _parse_page(items, 1)

    @patch("parser.kinopoisk.kinopoisk_parser._fetch_chart")
    def test_fetch_and_limit(self, fetch):
        fetch.return_value = [{
            "position": 1,
            "title": "Фильм",
            "kinopoisk_id": 123,
            "year": 2026,
            "rating": 7.5,
        }]

        result = get_kinopoisk_chart(5, timeout=12)

        self.assertEqual(result, fetch.return_value)
        fetch.assert_called_once_with(5, 12)

    @patch("parser.kinopoisk.kinopoisk_parser._fetch_chart")
    def test_invalid_arguments(self, fetch):
        for limit in (0, -1, True, "5"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                get_kinopoisk_chart(limit)

        for timeout in (0, -1, float("nan"), float("inf"), "30"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                get_kinopoisk_chart(timeout=timeout)

        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()