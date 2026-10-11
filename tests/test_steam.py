import json
import unittest
from unittest.mock import patch

from parser.steam.steam_parser import (
    CHART_SIZE,
    _date_to_timestamp,
    _extract_latest_weekly_date,
    _fetch_app_name,
    _fetch_chart,
    _parse_chart,
    get_steam_chart,
)


def _make_payload(missing_title_rank=None, size=CHART_SIZE):
    ranks = []

    for position in range(1, size + 1):
        app_id = 100000 + position

        item = {
            "appid": app_id,
            "name": f"Game {position}",
        }

        if position == missing_title_rank:
            item.pop("name")

        ranks.append(
            {
                "rank": position,
                "appid": app_id,
                "item": item,
                "last_week_rank": position + 3,
                "consecutive_weeks": position,
            }
        )

    return {
        "response": {
            "start_date": 1790640000,
            "ranks": ranks,
            "next_page_start": 100,
        }
    }


class SteamParserTests(unittest.TestCase):
    def test_latest_weekly_date_is_extracted(self):
        html = """
        <a href="/charts/topsellers/DE/2026-9-15"></a>
        <a href="/charts/topsellers/DE/2026-9-29"></a>
        <a href="/charts/topsellers/DE/2026-9-22"></a>
        """

        self.assertEqual(
            _extract_latest_weekly_date(html),
            "2026-9-29",
        )

    def test_date_is_converted_to_timestamp(self):
        self.assertEqual(
            _date_to_timestamp("2026-9-29"),
            1790640000,
        )

    def test_parse_chart(self):
        chart = _parse_chart(
            _make_payload(),
            timeout=30,
        )

        self.assertEqual(len(chart), CHART_SIZE)

        self.assertEqual(
            chart[0],
            {
                "position": 1,
                "title": "Game 1",
                "steam_app_id": 100001,
                "rank_last_week": 4,
                "consecutive_weeks": 1,
            },
        )

        self.assertEqual(
            chart[-1]["position"],
            100,
        )

    def test_incomplete_chart_is_rejected(self):
        with self.assertRaises(RuntimeError):
            _parse_chart(
                _make_payload(size=99),
                timeout=30,
            )

    def test_duplicate_app_id_is_rejected(self):
        payload = _make_payload()

        ranks = payload["response"]["ranks"]
        ranks[1]["appid"] = ranks[0]["appid"]

        with self.assertRaises(RuntimeError):
            _parse_chart(
                payload,
                timeout=30,
            )

    @patch(
        "parser.steam.steam_parser._fetch_app_name"
    )
    def test_missing_title_uses_fallback(self, fetch_app_name):
        fetch_app_name.return_value = "Fallback Game"

        chart = _parse_chart(
            _make_payload(missing_title_rank=9),
            timeout=30,
        )

        self.assertEqual(
            chart[8]["title"],
            "Fallback Game",
        )

        fetch_app_name.assert_called_once_with(
            100009,
            30,
        )

    @patch(
        "parser.steam.steam_parser._fetch_text"
    )
    def test_fetch_app_name(self, fetch_text):
        fetch_text.return_value = json.dumps(
            {
                "1282100": {
                    "success": True,
                    "data": {
                        "steam_appid": 1282100,
                        "name": "REMNANT II®",
                    },
                }
            }
        )

        self.assertEqual(
            _fetch_app_name(1282100, 30),
            "REMNANT II®",
        )

    @patch(
        "parser.steam.steam_parser._fetch_weekly_chart_payload"
    )
    @patch(
        "parser.steam.steam_parser._fetch_text"
    )
    def test_fetch_chart_uses_latest_week(self, fetch_text, fetch_payload):
        fetch_text.return_value = """
        <a href="/charts/topsellers/DE/2026-9-29"></a>
        """

        fetch_payload.return_value = _make_payload()

        chart = _fetch_chart(
            limit=10,
            timeout=30,
        )

        self.assertEqual(len(chart), 10)

        fetch_payload.assert_called_once_with(
            1790640000,
            30,
        )

    @patch(
        "parser.steam.steam_parser._fetch_chart"
    )
    def test_limit_is_passed_to_fetcher(self, fetch_chart):
        fetch_chart.return_value = []

        get_steam_chart(limit=5)

        fetch_chart.assert_called_once_with(
            5,
            30,
        )

    @patch(
        "parser.steam.steam_parser._fetch_chart"
    )
    def test_invalid_arguments_do_not_fetch(self, fetch_chart):
        invalid_limits = [
            0,
            -1,
            True,
            1.5,
            "10",
        ]

        for value in invalid_limits:
            with self.subTest(limit=value):
                with self.assertRaises(ValueError):
                    get_steam_chart(
                        limit=value
                    )

        invalid_timeouts = [
            0,
            -1,
            True,
            float("inf"),
            float("nan"),
            "30",
        ]

        for value in invalid_timeouts:
            with self.subTest(timeout=value):
                with self.assertRaises(ValueError):
                    get_steam_chart(
                        timeout=value
                    )

        fetch_chart.assert_not_called()

    def test_missing_previous_rank_is_allowed(self):
        payload = _make_payload()

        payload["response"]["ranks"][3].pop(
            "last_week_rank"
        )

        chart = _parse_chart(
            payload,
            timeout=30,
        )

        self.assertIsNone(
            chart[3]["rank_last_week"]
        )


if __name__ == "__main__":
    unittest.main()