import unittest
from datetime import date

from backend.repository import card


class BackendMappingTests(unittest.TestCase):
    def test_database_record_is_mapped_to_frontend_card(self):
        result = card({
            "trend_id": 42,
            "category": "music",
            "week_start": date(2026, 10, 19),
            "rank": 1,
            "prev_rank": 3,
            "peak_rank": 1,
            "weeks_in_top": 5,
            "title": "Песня",
            "subtitle": None,
            "genre": "Поп",
            "is_new": False,
            "search_count": 1200,
        })

        self.assertEqual(result["key"], "42")
        self.assertEqual(result["sphere"], "music")
        self.assertEqual(result["categoryLabel"], "Музыка")
        self.assertEqual(result["weekStart"], "2026-10-19")
        self.assertEqual(result["prevRank"], 3)
        self.assertEqual(result["subtitle"], "")
        self.assertEqual(result["searchCount"], 1200)


class BackendRouteTests(unittest.TestCase):
    def test_expected_routes_are_registered(self):
        from backend.app import app

        routes = {(route.path, method) for route in app.routes for method in route.methods or []}
        self.assertIn(("/api/v1/health", "GET"), routes)
        self.assertIn(("/api/v1/feed", "GET"), routes)
        self.assertIn(("/api/v1/categories", "GET"), routes)
        self.assertIn(("/api/v1/categories/{category}/trends", "GET"), routes)
        self.assertIn(("/api/v1/trends/{trend_id}", "GET"), routes)
        self.assertIn(("/api/v1/trends/{trend_id}/history", "GET"), routes)


if __name__ == "__main__":
    unittest.main()
