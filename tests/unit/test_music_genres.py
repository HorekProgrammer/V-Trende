import unittest
from unittest.mock import patch

from parser import music_genres


class MusicGenreTests(unittest.TestCase):
    def test_normalizes_itunes_genres(self):
        self.assertEqual(music_genres.normalize_apple_genre("Hip-Hop/Rap"), "Рэп / Хип-хоп")
        self.assertEqual(music_genres.normalize_apple_genre("Dance"), "Электроника")
        self.assertEqual(music_genres.normalize_apple_genre("Indie Pop"), "Инди")
        self.assertIsNone(music_genres.normalize_apple_genre("Soundtrack"))

    def test_deepseek_threshold_is_inclusive(self):
        self.assertIsNone(music_genres.accept_deepseek_genre({"genre": "Поп", "confidence": 0.7999}))
        self.assertEqual(music_genres.accept_deepseek_genre({"genre": "Поп", "confidence": 0.80}), "Поп")
        self.assertIsNone(music_genres.accept_deepseek_genre({"genre": "Джаз", "confidence": 1.0}))

    @patch.object(music_genres, "_get_json")
    def test_itunes_requires_track_and_artist_match(self, get_json):
        get_json.return_value = {"results": [
            {"trackName": "ДИНАСТИЯ", "artistName": "VILLIAN", "primaryGenreName": "Hip-Hop/Rap"},
            {"trackName": "ДИНАСТИЯ", "artistName": "Другой", "primaryGenreName": "Pop"},
        ]}
        genre, confidence = music_genres.itunes_genre({"title": "ДИНАСТИЯ", "subtitle": "VILLIAN, madk1d"})
        self.assertEqual(genre, "Рэп / Хип-хоп")
        self.assertGreaterEqual(confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
