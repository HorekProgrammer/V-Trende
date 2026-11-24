import unittest
from unittest.mock import patch

from parser import game_genres
from parser.game_genres import accept_deepseek_genre, classify_tags


class GameGenreTests(unittest.TestCase):
    def test_priority(self):
        self.assertEqual(classify_tags(["Action", "FPS", "RPG"]), "Шутеры")
        self.assertEqual(classify_tags(["Action", "RPG"]), "RPG")
        self.assertEqual(classify_tags(["Action", "RPG", "MOBA"]), "Стратегии")
        self.assertEqual(classify_tags(["Action", "Strategy"]), "Стратегии")
        self.assertEqual(classify_tags(["Action", "Indie"]), "Экшен")
        self.assertEqual(classify_tags(["Indie", "Casual"]), "Инди")
        self.assertEqual(classify_tags(["Sports", "Simulation"]), "Другое")
        self.assertIsNone(classify_tags([]))

    def test_deepseek_threshold(self):
        self.assertIsNone(accept_deepseek_genre({"genre": "Экшен", "confidence": 0.799}))
        self.assertEqual(accept_deepseek_genre({"genre": "Экшен", "confidence": 0.8}), "Экшен")
        self.assertIsNone(accept_deepseek_genre({"genre": "Хоррор", "confidence": 1.0}))

    def test_lower_weighted_tag_does_not_override_top_five(self):
        tags = ["Horror", "Multiplayer", "Survival Horror", "Online Co-Op", "Third Person", "Strategy"]
        self.assertEqual(classify_tags(tags[:5]), "Экшен")

    @patch.object(game_genres, "_get")
    def test_steam_page_tags_are_preferred(self, get):
        get.return_value = b'<a class="app_tag"> FPS </a><a class="app_tag">Shooter</a>'
        self.assertEqual(game_genres.steam_tags("730"), ["FPS", "Shooter"])
        self.assertEqual(classify_tags(game_genres.steam_tags("730")), "Шутеры")


if __name__ == "__main__":
    unittest.main()
