import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.repository import card


class BackendMappingTests(unittest.TestCase):
    def test_database_record_is_mapped_to_frontend_card(self):
        result = card({
            "trend_id": 42,
            "category": "music",
            "week_start": date(2026, 10, 19),
            "rank": 1,
            "score": 92.5,
            "source_score": 95,
            "wordstat_score": 78.3,
            "prev_rank": 3,
            "peak_rank": 1,
            "weeks_in_top": 5,
            "title": "Песня",
            "subtitle": None,
            "genre": "Поп",
            "is_new": False,
            "search_count": 1200,
            "cover_url": "https://avatars.yandex.net/cover.jpg",
            "year": 2026,
        })

        self.assertEqual(result["key"], "42")
        self.assertEqual(result["sphere"], "music")
        self.assertEqual(result["categoryLabel"], "Музыка")
        self.assertEqual(result["weekStart"], "2026-10-19")
        self.assertEqual(result["prevRank"], 3)
        self.assertEqual(result["score"], 92.5)
        self.assertEqual(result["subtitle"], "")
        self.assertEqual(result["searchCount"], 1200)
        self.assertEqual(result["cover"], "https://avatars.yandex.net/cover.jpg")
        self.assertEqual(result["year"], 2026)


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
        self.assertIn(("/api/v1/internal/update-trends", "POST"), routes)
        self.assertIn(("/api/v1/internal/update-search-stats", "POST"), routes)
        self.assertIn(("/api/v1/internal/publish-rankings", "POST"), routes)


class FakeTransaction:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def transaction(self):
        return FakeTransaction()


class ParserIngestionTests(unittest.TestCase):
    def setUp(self):
        from backend.app import app, database

        self.app = app
        self.database = database
        self.app.dependency_overrides[database] = lambda: FakeConnection()
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    @patch("backend.app.settings", return_value={"INTERNAL_API_TOKEN": "secret"})
    def test_rejects_missing_or_invalid_token(self, _settings):
        payload = {"type": "chart"}
        self.assertEqual(
            self.client.post("/api/v1/internal/update-trends", json=payload).status_code,
            401,
        )
        response = self.client.post(
            "/api/v1/internal/update-trends",
            json=payload,
            headers={"Authorization": "Bearer wrong"},
        )
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.load_payload", return_value="chart saved")
    @patch("backend.app.settings", return_value={"INTERNAL_API_TOKEN": "secret"})
    def test_saves_chart_without_refreshing_rankings(self, _settings, loader):
        payload = {"type": "chart", "entries": []}
        with patch("database.load_outbox.refresh_rankings") as refresh:
            response = self.client.post(
                "/api/v1/internal/update-trends",
                json=payload,
                headers={"Authorization": "Bearer secret"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "chart saved"})
        loader.assert_called_once()
        refresh.assert_not_called()

    @patch("backend.app.load_payload", return_value="stats saved")
    @patch("backend.app.refresh_rankings")
    @patch("backend.app.settings", return_value={"INTERNAL_API_TOKEN": "secret"})
    def test_saves_search_stats_and_publishes_rankings(self, _settings, refresh, loader):
        payload = {"type": "search_stats", "entries": []}
        response = self.client.post(
            "/api/v1/internal/update-search-stats",
            json=payload,
            headers={"Authorization": "Bearer secret"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "stats saved", "rankingsRefreshed": True})
        loader.assert_called_once()
        refresh.assert_called_once()

    @patch("backend.app.load_payload", return_value="stats prepared")
    @patch("backend.app.refresh_rankings")
    @patch("backend.app.settings", return_value={"INTERNAL_API_TOKEN": "secret"})
    def test_deferred_search_stats_do_not_publish(self, _settings, refresh, loader):
        response = self.client.post(
            "/api/v1/internal/update-search-stats",
            json={"type": "search_stats", "entries": [], "publish": False},
            headers={"Authorization": "Bearer secret"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["rankingsRefreshed"])
        loader.assert_called_once()
        refresh.assert_not_called()

    @patch("backend.app.refresh_rankings")
    @patch("backend.app.settings", return_value={"INTERNAL_API_TOKEN": "secret"})
    def test_publish_endpoint_refreshes_prepared_rating(self, _settings, refresh):
        response = self.client.post(
            "/api/v1/internal/publish-rankings",
            headers={"Authorization": "Bearer secret"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["rankingsRefreshed"])
        refresh.assert_called_once()

    @patch("backend.app.settings", return_value={"INTERNAL_API_TOKEN": "secret"})
    def test_rejects_payload_for_the_other_endpoint(self, _settings):
        response = self.client.post(
            "/api/v1/internal/update-trends",
            json={"type": "search_stats"},
            headers={"Authorization": "Bearer secret"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
