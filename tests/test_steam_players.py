import json
import unittest
from unittest.mock import patch

from parser.steam_players.steam_players_parser import (
    CHART_SIZE,
    _extract_tags,
    _fetch_chart,
    _fetch_payload,
    _fetch_tag_names,
    _parse_chart,
    get_steam_players_chart,
)


def _make_tag_names():
    return {
        19: "Action",
        1663: "FPS",
        1774: "Shooter",
        3859: "Multiplayer",
    }


def _make_payload():
    ranks = []

    for position in range(
        1,
        CHART_SIZE + 1,
    ):
        ranks.append(
            {
                "rank": position,
                "appid": 100000 + position,
                "item": {
                    "name": f"Game {position}",
                    "tags": [
                        {
                            "tagid": 1663,
                            "weight": 1000,
                        },
                        {
                            "tagid": 1774,
                            "weight": 900,
                        },
                    ],
                },
                "concurrent_in_game": (
                    1_000_000 - position
                ),
                "peak_in_game": (
                    1_100_000 - position
                ),
            }
        )

    return {
        "response": {
            "last_update": 1234567890,
            "ranks": ranks,
        }
    }


class SteamPlayersTests(unittest.TestCase):
    def test_parses_full_chart(self):
        chart = _parse_chart(
            _make_payload(),
            _make_tag_names(),
        )

        self.assertEqual(
            len(chart),
            CHART_SIZE,
        )

        self.assertEqual(
            chart[0],
            {
                "position": 1,
                "title": "Game 1",
                "steam_app_id": 100001,
                "current_players": 999999,
                "peak_today": 1099999,
                "tags": [
                    "FPS",
                    "Shooter",
                ],
                "cover_url": (
                    "https://shared.akamai.steamstatic.com/store_item_assets/"
                    "steam/apps/100001/header.jpg"
                ),
            },
        )

        self.assertEqual(
            chart[-1]["position"],
            100,
        )

    def test_extracts_tags(self):
        item = {
            "tags": [
                {
                    "tagid": 1663,
                    "weight": 1000,
                },
                {
                    "tagid": 19,
                    "weight": 900,
                },
            ]
        }

        tags = _extract_tags(
            item,
            _make_tag_names(),
        )

        self.assertEqual(
            tags,
            [
                "FPS",
                "Action",
            ],
        )

    def test_unknown_tags_are_ignored(self):
        item = {
            "tags": [
                {
                    "tagid": 999999,
                    "weight": 1000,
                }
            ]
        }

        tags = _extract_tags(
            item,
            _make_tag_names(),
        )

        self.assertEqual(
            tags,
            [],
        )

    def test_missing_tags_are_allowed(self):
        item = {
            "name": "Restricted Game",
        }

        tags = _extract_tags(
            item,
            _make_tag_names(),
        )

        self.assertEqual(
            tags,
            [],
        )

    def test_country_restricted_game_is_allowed(self):
        payload = _make_payload()

        payload["response"]["ranks"][3]["item"] = {
            "success": 15,
            "visible": False,
            "unvailable_for_country_restriction": True,
            "name": "Restricted Game",
        }

        chart = _parse_chart(
            payload,
            _make_tag_names(),
        )

        self.assertEqual(
            chart[3]["title"],
            "Restricted Game",
        )

        self.assertEqual(
            chart[3]["tags"],
            [],
        )

    def test_rejects_incomplete_chart(self):
        payload = _make_payload()

        payload["response"]["ranks"].pop()

        with self.assertRaises(RuntimeError):
            _parse_chart(
                payload,
                _make_tag_names(),
            )

    def test_rejects_duplicate_app_id(self):
        payload = _make_payload()

        ranks = payload["response"]["ranks"]

        ranks[1]["appid"] = ranks[0]["appid"]

        with self.assertRaises(RuntimeError):
            _parse_chart(
                payload,
                _make_tag_names(),
            )

    def test_rejects_invalid_player_count(self):
        payload = _make_payload()

        payload[
            "response"
        ]["ranks"][0][
            "concurrent_in_game"
        ] = -1

        with self.assertRaises(RuntimeError):
            _parse_chart(
                payload,
                _make_tag_names(),
            )

    def test_rejects_unsorted_player_counts(self):
        payload = _make_payload()

        ranks = payload["response"]["ranks"]

        ranks[0]["concurrent_in_game"] = 10
        ranks[1]["concurrent_in_game"] = 20

        with self.assertRaises(RuntimeError):
            _parse_chart(
                payload,
                _make_tag_names(),
            )

    @patch(
        "parser.steam_players."
        "steam_players_parser._fetch_text"
    )
    def test_fetch_payload(
        self,
        fetch_text,
    ):
        fetch_text.return_value = json.dumps(
            _make_payload()
        )

        payload = _fetch_payload(
            timeout=30,
        )

        self.assertEqual(
            len(
                payload["response"]["ranks"]
            ),
            CHART_SIZE,
        )

        fetch_text.assert_called_once()

    @patch(
        "parser.steam_players."
        "steam_players_parser._fetch_text"
    )
    def test_fetch_tag_names(
        self,
        fetch_text,
    ):
        fetch_text.return_value = json.dumps(
            [
                {
                    "tagid": 1663,
                    "name": "FPS",
                },
                {
                    "tagid": 1774,
                    "name": "Shooter",
                },
            ]
        )

        tag_names = _fetch_tag_names(
            timeout=30,
        )

        self.assertEqual(
            tag_names,
            {
                1663: "FPS",
                1774: "Shooter",
            },
        )

        fetch_text.assert_called_once()

    @patch(
        "parser.steam_players."
        "steam_players_parser._fetch_tag_names"
    )
    @patch(
        "parser.steam_players."
        "steam_players_parser._fetch_payload"
    )
    def test_fetch_chart_applies_limit(
        self,
        fetch_payload,
        fetch_tag_names,
    ):
        fetch_payload.return_value = (
            _make_payload()
        )

        fetch_tag_names.return_value = (
            _make_tag_names()
        )

        chart = _fetch_chart(
            limit=5,
            timeout=30,
        )

        self.assertEqual(
            len(chart),
            5,
        )

        self.assertEqual(
            chart[0]["position"],
            1,
        )

        self.assertEqual(
            chart[-1]["position"],
            5,
        )

    @patch(
        "parser.steam_players."
        "steam_players_parser._fetch_chart"
    )
    def test_limit_is_passed_to_fetcher(
        self,
        fetch_chart,
    ):
        fetch_chart.return_value = []

        get_steam_players_chart(
            limit=10,
        )

        fetch_chart.assert_called_once_with(
            limit=10,
            timeout=30,
        )

    @patch(
        "parser.steam_players."
        "steam_players_parser._fetch_chart"
    )
    def test_invalid_arguments_do_not_fetch(
        self,
        fetch_chart,
    ):
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
                    get_steam_players_chart(
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
                    get_steam_players_chart(
                        timeout=value
                    )

        fetch_chart.assert_not_called()


if __name__ == "__main__":
    unittest.main()