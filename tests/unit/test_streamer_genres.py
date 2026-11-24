import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from parser import streamer_genres


FRAGMENTS = """<section id="most-streamed-games-wrapper"><div id="channel-games">
<a class="entity" href="/nix/games/29595"><div title="Dota 2" data-toggle="tooltip"><img src="x"></div>
<div class="body"><div title="time"><span class="to-time">290185</span></div></div></a>
<a class="entity" href="/nix/games/509658"><div title="Just Chatting" data-toggle="tooltip"><img src="x"></div>
<div class="body"><div title="time"><span class="to-time">32286</span></div></div></a>
<a class="entity" href="/nix/games/498592"><div title="I&#039;m Only Sleeping" data-toggle="tooltip"><img src="x"></div>
<div class="body"><div title="time"><span class="to-time">3335</span></div></div></a>
</div></section><section><a class="entity" href="/nix/games/1"><div title="Music"></div>
<span class="to-time">999999</span></a></section>"""


class TwitchTrackerTests(unittest.TestCase):
    def test_parse_most_streamed_categories(self):
        self.assertEqual(streamer_genres.categories_from_fragments(FRAGMENTS), [
            ("Dota 2", 290185), ("Just Chatting", 32286), ("I'm Only Sleeping", 3335)])
        self.assertEqual(streamer_genres.categories_from_fragments("<html></html>"), [])

    def test_both_supported_genres_are_kept_and_ordered_by_time(self):
        genres = streamer_genres.genres_from_categories
        self.assertEqual(genres([("Dota 2", 100), ("Just Chatting", 90)]), ["Игры", "Just Chatting"])
        self.assertEqual(genres([("Dota 2", 40), ("Just Chatting", 100)]), ["Just Chatting", "Игры"])
        self.assertEqual(genres([("CS2", 50), ("Dota 2", 50)]), ["Игры"])

    def test_unrelated_sections_are_ignored(self):
        genres = streamer_genres.genres_from_categories
        self.assertEqual(genres([("Music", 100), ("IRL", 50), ("Art", 20)]), [])
        self.assertEqual(genres([("Music", 100), ("Just Chatting", 20)]), ["Just Chatting"])
        self.assertEqual(genres([]), [])

    def test_chatting_family_is_not_treated_as_games(self):
        self.assertEqual(
            streamer_genres.genres_from_categories([("Watch Parties", 100), ("Dota 2", 50)]),
            ["Just Chatting", "Игры"],
        )

    @patch.object(streamer_genres, "_read", side_effect=RuntimeError("TwitchTracker: HTTP 403"))
    def test_tracker_errors_are_distinguished_from_empty_categories(self, _read):
        self.assertIsNone(streamer_genres.twitchtracker_categories("nix"))

    @patch.object(streamer_genres, "_save_genres")
    @patch.object(streamer_genres.time, "sleep")
    @patch.object(streamer_genres, "twitchtracker_categories")
    @patch.object(streamer_genres, "connect")
    def test_every_week_refreshes_existing_genres_without_deepseek(self, connect, tracker, _sleep, save):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            (1, "NIX", "nix"), (2, "Talker", "talker"), (3, "DJ", "dj")]
        connect.return_value.__enter__.return_value = conn
        tracker.side_effect = [
            [("Dota 2", 100), ("Just Chatting", 20)],
            [("Just Chatting", 100)],
            [("Music", 100)],
        ]

        self.assertEqual(streamer_genres.fill_streamer_genres(date(2026, 11, 9), log=lambda *_: None), (2, 1))
        save.assert_called_once_with({1: ["Игры", "Just Chatting"], 2: ["Just Chatting"], 3: []})
        self.assertNotIn("genre_id IS NULL", conn.execute.call_args.args[0])

    @patch.object(streamer_genres, "_save_genres")
    @patch.object(streamer_genres.time, "sleep")
    @patch.object(streamer_genres, "twitchtracker_categories", return_value=None)
    @patch.object(streamer_genres, "connect")
    def test_network_failure_preserves_previous_genres(self, connect, _tracker, _sleep, save):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [(1, "NIX", "nix")]
        connect.return_value.__enter__.return_value = conn
        self.assertEqual(streamer_genres.fill_streamer_genres(date(2026, 11, 9), log=lambda *_: None), (0, 1))
        save.assert_called_once_with({})


if __name__ == "__main__":
    unittest.main()
