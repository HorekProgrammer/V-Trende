import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from fastapi.testclient import TestClient

from backend.app import app, database
from backend.seo import (
    PUBLIC_PATHS,
    SITE_URL,
    SITEMAP_NAMESPACE,
    category_html,
    sitemap_xml,
    spa_html,
    trend_html,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = '<!doctype html><html><head><title>В Чарте</title></head><body><div id="root"></div><script src="/assets/app.js"></script></body></html>'
FEED = {
    "weekStart": "2026-11-16",
    "global": [
        {
            "key": "7",
            "rank": 1,
            "title": "Настоящий лидер",
            "subtitle": "Автор & соавтор",
        }
    ],
    "top3": [
        {
            "category": {"id": "music", "label": "Музыка"},
            "items": [
                {
                    "key": "8",
                    "rank": 2,
                    "title": "Второй трек",
                    "subtitle": "Исполнитель",
                }
            ],
        }
    ],
}


class SeoDocumentTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[database] = lambda: object()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_robots_allows_public_pages_and_points_to_sitemap(self):
        content = (PROJECT_ROOT / "frontend" / "public" / "robots.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("User-agent: *", content)
        self.assertIn("Allow: /", content)
        self.assertIn("Disallow: /api/", content)
        self.assertIn(f"Sitemap: {SITE_URL}/sitemap.xml", content)

    def test_sitemap_contains_only_public_absolute_urls(self):
        root = ElementTree.fromstring(sitemap_xml([7, 42]))
        locations = [
            node.text
            for node in root.findall(f"{{{SITEMAP_NAMESPACE}}}url/{{{SITEMAP_NAMESPACE}}}loc")
        ]
        self.assertEqual(
            locations,
            [
                *(f"{SITE_URL}{path}" for path in PUBLIC_PATHS),
                f"{SITE_URL}/trend/7",
                f"{SITE_URL}/trend/42",
            ],
        )
        self.assertTrue(all(url.startswith("https://vcharte.com/") for url in locations))
        self.assertFalse(
            any(
                "/api/" in url or "/auth" in url or "/login" in url
                for url in locations
            )
        )
        self.assertNotIn(b"lastmod", sitemap_xml([7]))

    @patch("backend.app.repository.sitemap_trend_ids", return_value=[11, 12])
    def test_sitemap_endpoint_has_xml_content_type(self, trend_ids):
        response = TestClient(app).get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/xml")
        self.assertIn("https://vcharte.com/trend/11", response.text)
        trend_ids.assert_called_once()

    def test_home_prerender_contains_real_ranking_and_safe_initial_data(self):
        rendered = spa_html(INDEX_HTML, FEED)
        self.assertIn("<h1>Всё, что сейчас обсуждают", rendered)
        self.assertIn("Настоящий лидер", rendered)
        self.assertIn('href="/trend/7"', rendered)
        self.assertIn('<li class="seo-ranking-card">', rendered)
        self.assertIn('<a class="seo-ranking-link" href="/trend/7">', rendered)
        self.assertIn("Автор &amp; соавтор", rendered)
        self.assertIn("window.__VCHARTE_INITIAL_DATA__", rendered)
        self.assertIn('<meta name="description"', rendered)
        self.assertNotIn("data-state--error", rendered)
        self.assertNotIn("Не удалось загрузить данные", rendered)

        hostile = {**FEED, "global": [{**FEED["global"][0], "title": "</script>"}]}
        self.assertNotIn("</script></strong>", spa_html(INDEX_HTML, hostile))

    @patch("backend.app.load_frontend_index", return_value=INDEX_HTML)
    @patch("backend.app.repository.feed", return_value=FEED)
    def test_home_web_route_returns_prerendered_html(self, feed, load_index):
        response = TestClient(app).get("/web/home")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/html"))
        self.assertIn("Настоящий лидер", response.text)
        self.assertIn("<h1>", response.text)
        self.assertIn('<a class="seo-ranking-link" href="/trend/7">', response.text)
        self.assertNotIn("data-state--error", response.text)
        feed.assert_called_once()
        load_index.assert_called_once()

    def test_category_html_contains_ranking_links_and_unique_metadata(self):
        ranking = {"weekStart": "2026-11-16", "items": FEED["global"]}
        rendered = category_html(INDEX_HTML, "games", "Игры", ranking)
        self.assertIn("<h1>Игры</h1>", rendered)
        self.assertIn("Настоящий лидер", rendered)
        self.assertIn('href="/trend/7"', rendered)
        self.assertIn("Популярные игры — рейтинг недели | В ЧАРТЕ", rendered)
        self.assertIn(
            '<link rel="canonical" href="https://vcharte.com/category/games">',
            rendered,
        )
        self.assertIn('property="og:title"', rendered)
        self.assertNotIn("data-state--error", rendered)

    def test_trend_html_contains_facts_history_links_and_metadata(self):
        item = {
            **FEED["global"][0],
            "sphere": "games",
            "categoryLabel": "Игры",
            "peak": 1,
            "weeks": 4,
            "cover": "/media/covers/example.jpg",
            "history": [{"weekStart": "2026-11-16", "rank": 1}],
        }
        rendered = trend_html(INDEX_HTML, item)
        self.assertIn("<h1>Настоящий лидер</h1>", rendered)
        self.assertIn("Настоящий лидер — Автор &amp; соавтор — популярность", rendered)
        self.assertIn("Текущая позиция</dt><dd>#1", rendered)
        self.assertIn("Лучшее место</dt><dd>#1", rendered)
        self.assertIn("Недель в рейтинге</dt><dd>4", rendered)
        self.assertIn("История позиций", rendered)
        self.assertIn('href="/category/games"', rendered)
        self.assertIn(
            '<link rel="canonical" href="https://vcharte.com/trend/7">', rendered
        )
        self.assertIn('content="https://vcharte.com/media/covers/example.jpg"', rendered)

    @patch("backend.app.load_frontend_index", return_value=INDEX_HTML)
    @patch("backend.app.repository.category_trends", return_value={"weekStart": "2026-11-16", "items": []})
    def test_web_routes_reject_unknown_category_and_trend(self, category_trends, load_index):
        client = TestClient(app)
        self.assertEqual(client.get("/web/category/music").status_code, 200)
        self.assertEqual(client.get("/web/category/unknown").status_code, 404)
        item = {
            **FEED["global"][0],
            "sphere": "games",
            "categoryLabel": "Игры",
            "peak": 1,
            "weeks": 4,
            "cover": None,
            "history": [],
        }
        with patch("backend.app.repository.trend", return_value=item):
            self.assertEqual(client.get("/web/trend/7").status_code, 200)
        with patch("backend.app.repository.trend", return_value=None):
            self.assertEqual(client.get("/web/trend/999999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
