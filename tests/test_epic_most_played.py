import unittest
from unittest.mock import patch

from parser.epic_most_played.epic_most_played_parser import (
    CHART_SIZE,
    _extract_slug,
    _parse_chart,
    get_epic_most_played_chart,
)


def _make_payload():
    offers = []

    for position in range(1, CHART_SIZE + 1):
        offers.append(
            {
                "title": f"Game {position}",
                "id": f"id-{position}",
                "namespace": f"namespace-{position}",
                "catalogNs": {
                    "mappings": [
                        {
                            "pageSlug": f"game-{position}",
                        }
                    ]
                },
            }
        )

    return {
        "data": {
            "Storefront": {
                "collectionLayout": {
                    "collectionOffers": offers,
                }
            }
        }
    }


class EpicMostPlayedTests(unittest.TestCase):
    def test_parses_chart(self):
        chart = _parse_chart(
            _make_payload()
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
                "epic_offer_id": "id-1",
                "epic_namespace": "namespace-1",
                "epic_slug": "game-1",
                "cover_url": None,
                "year": None,
            },
        )

        self.assertEqual(
            chart[-1]["position"],
            100,
        )

    def test_extracts_slug(self):
        offer = {
            "catalogNs": {
                "mappings": [
                    {
                        "pageSlug": "fortnite",
                    }
                ]
            }
        }

        self.assertEqual(
            _extract_slug(offer),
            "fortnite",
        )

    def test_missing_slug_is_allowed(self):
        self.assertIsNone(
            _extract_slug({})
        )

    def test_rejects_incomplete_chart(self):
        payload = _make_payload()

        payload["data"]["Storefront"][
            "collectionLayout"
        ]["collectionOffers"].pop()

        with self.assertRaises(RuntimeError):
            _parse_chart(payload)

    def test_rejects_duplicate_offers(self):
        payload = _make_payload()

        offers = payload["data"]["Storefront"][
            "collectionLayout"
        ]["collectionOffers"]

        offers[1]["id"] = offers[0]["id"]

        with self.assertRaises(RuntimeError):
            _parse_chart(payload)

    @patch(
        "parser.epic_most_played."
        "epic_most_played_parser._fetch_payload"
    )
    def test_limit(self, fetch_payload):
        fetch_payload.return_value = _make_payload()

        chart = get_epic_most_played_chart(
            limit=5
        )

        self.assertEqual(
            len(chart),
            5,
        )

        self.assertEqual(
            chart[-1]["position"],
            5,
        )

    @patch(
        "parser.epic_most_played."
        "epic_most_played_parser._fetch_payload"
    )
    def test_invalid_limit(self, fetch_payload):
        for value in [0, -1, True, 1.5]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    get_epic_most_played_chart(
                        limit=value
                    )

        fetch_payload.assert_not_called()


if __name__ == "__main__":
    unittest.main()