import json
import unittest
from unittest.mock import patch

from parser import movie_genres


class MovieGenreTests(unittest.TestCase):
    def test_priority(self):
        self.assertEqual(movie_genres.classify_labels(["drama film", "science fiction film"]), "Фантастика")
        self.assertEqual(movie_genres.classify_labels(["action film", "thriller film"]), "Боевик")
        self.assertEqual(movie_genres.classify_labels(["horror film", "comedy film"]), "Ужасы")
        self.assertEqual(movie_genres.classify_labels(["comedy-drama"]), "Комедия")
        self.assertEqual(movie_genres.classify_labels(["biographical film"]), "Драма")
        self.assertEqual(movie_genres.classify_labels(["фильм ужасов"]), "Ужасы")
        self.assertEqual(movie_genres.classify_labels(["animated film", "family film"]), "Другое")
        self.assertIsNone(movie_genres.classify_labels([]))

    def test_returns_up_to_three_ordered_genres(self):
        self.assertEqual(
            movie_genres.classify_genres(["фантастика", "боевик", "триллер", "драма"]),
            ["Фантастика", "Боевик", "Триллер"],
        )

    def test_deepseek_threshold(self):
        self.assertIsNone(movie_genres.accept_deepseek_genre({"genre": "Драма", "confidence": 0.79}))
        self.assertEqual(movie_genres.accept_deepseek_genre({"genre": "Драма", "confidence": 0.8}), "Драма")
        self.assertIsNone(movie_genres.accept_deepseek_genre({"genre": "Вестерн", "confidence": 1.0}))
        self.assertIsNone(movie_genres.accept_deepseek_genre({"genre": "Драма", "confidence": "0.9"}))

    @patch.object(movie_genres, "_wikidata")
    def test_wikidata_by_kinopoisk_id(self, wikidata):
        wikidata.side_effect = [
            {"query": {"search": [{"title": "Q1"}]}},
            {"entities": {"Q1": {"claims": {"P136": [
                {"mainsnak": {"datavalue": {"value": {"id": "Q2"}}}},
                {"mainsnak": {"datavalue": {"value": {"id": "Q3"}}}},
            ]}}}},
            {"entities": {"Q2": {"labels": {"en": {"value": "drama film"}}},
                          "Q3": {"labels": {"ru": {"value": "комедия"}}}}},
        ]
        labels = movie_genres.wikidata_labels("301")
        self.assertEqual(labels, ["drama film", "комедия"])
        self.assertEqual(movie_genres.classify_labels(labels), "Комедия")
        self.assertIn("haswbstatement:P2603=301", wikidata.call_args_list[0].args[0]["srsearch"])

    @patch.object(movie_genres, "_wikidata")
    def test_wikidata_skips_bad_id_and_missing_film(self, wikidata):
        self.assertEqual(movie_genres.wikidata_labels(None), [])
        self.assertEqual(movie_genres.wikidata_labels("abc"), [])
        wikidata.assert_not_called()
        wikidata.return_value = {"query": {"search": []}}
        self.assertEqual(movie_genres.wikidata_labels("301"), [])

    @patch.object(movie_genres, "_post_json")
    def test_deepseek_batch(self, post_json):
        answer = {"results": [{"id": 1, "genre": "Боевик", "confidence": 0.9},
                              {"id": 2, "genre": "Драма", "confidence": 0.5}]}
        post_json.side_effect = [
            {"results": [{"title": "t", "url": "u", "snippet": "s"}]},
            {"results": []},
            {"choices": [{"message": {"content": json.dumps(answer)}}]},
        ]
        movies = [{"id": 1, "title": "Мстители", "year": "2012"}, {"id": 2, "title": "Фильм", "year": None}]
        self.assertEqual(movie_genres._deepseek_batch(movies, "key", "model", 5), {1: "Боевик"})


class KinopoiskPageTests(unittest.TestCase):
    def evaluate(self, html):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("нет Playwright")
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_content(html)
                    return page.evaluate(movie_genres.FIND_GENRES_JS)
                finally:
                    browser.close()
        except Exception as error:  # noqa: BLE001
            self.skipTest(f"Chromium недоступен: {error}")

    def test_json_ld_genres(self):
        html = """<script type="application/ld+json">{"@type":"Movie","name":"Фильм",
                  "genre":["драма","мелодрама"]}</script><a href="/lists/movies/genre--comedy/">комедия</a>"""
        self.assertEqual(self.evaluate(html), ["драма", "мелодрама"])

    def test_genre_row_fallback(self):
        html = """<nav><a href="/lists/movies/genre--horror/">ужасы</a></nav>
                  <div><div>Год производства</div><div><a>2025</a></div></div>
                  <div><div>Жанр</div><div><a>фантастика</a>, <a>боевик</a>, <a>слова</a></div></div>"""
        self.assertEqual(self.evaluate(html), ["фантастика", "боевик"])

    def test_russian_labels(self):
        self.assertEqual(movie_genres.classify_labels(["мультфильм", "комедия"]), "Комедия")
        self.assertEqual(movie_genres.classify_labels(["мультфильм", "семейный"]), "Другое")
        self.assertEqual(movie_genres.classify_labels(["драма", "криминал"]), "Триллер")


class FillTests(unittest.TestCase):
    @patch.object(movie_genres, "_save_genres")
    @patch.object(movie_genres, "wikidata_labels")
    @patch.object(movie_genres, "kinopoisk_genres")
    @patch.object(movie_genres, "connect")
    def test_kinopoisk_then_wikidata(self, connect, kinopoisk, wikidata, save):
        from datetime import date
        from unittest.mock import MagicMock
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [(1, "A", "2025", "11"), (2, "B", None, "22")]
        connect.return_value.__enter__.return_value = conn
        kinopoisk.return_value = {1: ["боевик"]}
        wikidata.side_effect = lambda film_id, timeout: ["comedy film"] if film_id == "22" else []
        self.assertEqual(movie_genres.fill_movie_genres(date(2026, 11, 2)), (2, 0))
        save.assert_called_once_with({1: ["Боевик"], 2: ["Комедия"]})
        wikidata.assert_called_once()


if __name__ == "__main__":
    unittest.main()
