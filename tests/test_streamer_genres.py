import json
import unittest
from unittest.mock import MagicMock, patch

from parser import streamer_genres


class StreamerGenreTests(unittest.TestCase):
    def test_deepseek_threshold(self):
        self.assertIsNone(streamer_genres.accept_deepseek_genre({"genre": "IRL", "confidence": 0.79}))
        self.assertEqual(streamer_genres.accept_deepseek_genre({"genre": "IRL", "confidence": 0.8}), "IRL")
        self.assertIsNone(streamer_genres.accept_deepseek_genre({"genre": "Спорт", "confidence": 1.0}))

    @patch.object(streamer_genres, "_post_json")
    def test_deepseek_batch(self, post_json):
        answer = {"results": [{"id": 1, "genre": "Игры", "confidence": 0.95},
                              {"id": 2, "genre": "Just Chatting", "confidence": 0.6},
                              {"id": "3", "genre": "Музыка", "confidence": 0.9}]}
        post_json.side_effect = [{"results": []}] * 3 + [
            {"choices": [{"message": {"content": json.dumps(answer)}}]}]
        channels = [{"id": i, "title": f"Канал {i}", "slug": f"channel{i}"} for i in (1, 2, 3)]
        self.assertEqual(streamer_genres._deepseek_batch(channels, "key", "model", 5), {1: "Игры"})

    @patch.object(streamer_genres, "_post_json")
    def test_broken_answer(self, post_json):
        post_json.side_effect = [{"results": []}, {"choices": [{"message": {"content": "не json"}}]}]
        with self.assertRaises(RuntimeError):
            streamer_genres._deepseek_batch([{"id": 1, "title": "A", "slug": "a"}], "key", "model", 5)

    @patch.object(streamer_genres.time, "sleep")
    @patch.object(streamer_genres, "twitchtracker_categories", return_value=[])
    @patch.object(streamer_genres, "_settings", return_value={})
    @patch.object(streamer_genres, "connect")
    def test_requires_api_key(self, connect, _settings, _tracker, _sleep):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [(1, "Канал", "channel")]
        connect.return_value.__enter__.return_value = conn
        from datetime import date
        with self.assertRaises(RuntimeError):
            streamer_genres.fill_streamer_genres(date(2026, 11, 9), log=lambda *_: None)


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

    def test_genre_by_total_time(self):
        genre = streamer_genres.genre_from_categories
        self.assertEqual(genre([("Dota 2", 100), ("Just Chatting", 90)]), "Игры")
        self.assertEqual(genre([("Dota 2", 50), ("CS2", 50), ("Just Chatting", 90)]), "Игры")
        self.assertEqual(genre([("Just Chatting", 100), ("Dota 2", 40), ("CS2", 40)]), "Just Chatting")
        self.assertEqual(genre([("Music", 100), ("Just Chatting", 20)]), "Музыка")
        self.assertEqual(genre([("Art", 10), ("Makers & Crafting", 10), ("IRL", 15)]), "Творчество")
        self.assertEqual(genre([("Travel & Outdoors", 30), ("Food & Drink", 30), ("Just Chatting", 50)]), "IRL")
        self.assertIsNone(genre([]))

    @patch.object(streamer_genres, "_read", side_effect=RuntimeError("TwitchTracker: HTTP 403"))
    def test_tracker_errors_fall_back(self, _read):
        self.assertEqual(streamer_genres.twitchtracker_categories("nix"), [])

    @patch.object(streamer_genres, "_save_genres")
    @patch.object(streamer_genres.time, "sleep")
    @patch.object(streamer_genres, "_deepseek_batch", return_value={2: "IRL"})
    @patch.object(streamer_genres, "_settings", return_value={"DEEPSEEK_API": "key"})
    @patch.object(streamer_genres, "twitchtracker_categories")
    @patch.object(streamer_genres, "connect")
    def test_tracker_first_then_deepseek(self, connect, tracker, _settings, deepseek, _sleep, save):
        from datetime import date
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [(1, "NIX", "nix"), (2, "Кто-то", "someone")]
        connect.return_value.__enter__.return_value = conn
        tracker.side_effect = lambda slug, timeout: [("Dota 2", 100)] if slug == "nix" else []
        self.assertEqual(streamer_genres.fill_streamer_genres(date(2026, 11, 2), log=lambda *_: None), (2, 0))
        self.assertEqual(save.call_args_list[0].args[0], {1: "Игры"})
        self.assertEqual(deepseek.call_args.args[0], [{"id": 2, "title": "Кто-то", "slug": "someone"}])

    @patch.object(streamer_genres, "_save_genres")
    @patch.object(streamer_genres.time, "sleep")
    @patch.object(streamer_genres, "_deepseek_batch", return_value={1: "IRL", 2: "Just Chatting"})
    @patch.object(streamer_genres, "_settings", return_value={"DEEPSEEK_API": "key"})
    @patch.object(streamer_genres, "twitchtracker_categories", return_value=[("Just Chatting", 100)])
    @patch.object(streamer_genres, "connect")
    def test_just_chatting_is_refined_to_irl(self, connect, _tracker, _settings, deepseek, _sleep, save):
        from datetime import date
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [(1, "Гуляка", "walker"), (2, "Болтун", "talker")]
        connect.return_value.__enter__.return_value = conn
        log = []
        self.assertEqual(streamer_genres.fill_streamer_genres(date(2026, 11, 2), log=log.append), (2, 0))
        save.assert_called_once_with({1: "IRL", 2: "Just Chatting"})
        self.assertEqual(deepseek.call_args.args[4], ("Just Chatting", "IRL"))
        self.assertTrue(any("уточнено как IRL" in line for line in log))

    @patch.object(streamer_genres, "_save_genres")
    @patch.object(streamer_genres.time, "sleep")
    @patch.object(streamer_genres, "_settings", return_value={})
    @patch.object(streamer_genres, "twitchtracker_categories", return_value=[("Just Chatting", 100)])
    @patch.object(streamer_genres, "connect")
    def test_without_api_key_just_chatting_stays(self, connect, _tracker, _settings, _sleep, save):
        from datetime import date
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [(1, "Болтун", "talker")]
        connect.return_value.__enter__.return_value = conn
        self.assertEqual(streamer_genres.fill_streamer_genres(date(2026, 11, 2), log=lambda *_: None), (1, 0))
        save.assert_called_once_with({1: "Just Chatting"})

    def test_watch_parties_are_not_games(self):
        self.assertEqual(streamer_genres.genre_from_categories([("Watch Parties", 100), ("Dota 2", 50)]),
                         "Just Chatting")
        self.assertEqual(streamer_genres.main_category([("Dota 2", 5), ("Just Chatting", 9)]), "Just Chatting")


if __name__ == "__main__":
    unittest.main()
