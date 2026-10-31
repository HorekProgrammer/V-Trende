import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from parser.music_years import deepseek_years
from parser.music_years.__main__ import save_years
from parser.music_years.deepseek_years import base_key, base_title, find_years

URL_A = "https://ru.wikipedia.org/wiki/Track_A"
URL_B = "https://genius.com/track-b"
THIS_YEAR = date.today().year


def track(key, title=None, artists="Артист"):
    return {"key": key, "title": title or f"Песня {key}", "artists": artists}


class FakeDeepSeek:
    def __init__(self, answers, search_urls=(URL_A, URL_B)):
        self.answers, self.search_urls = answers, search_urls
        self.searches, self.chats = 0, 0

    def __call__(self, url, payload, api_key, timeout):
        if url == deepseek_years.SEARCH_URL:
            self.searches += 1
            return {"results": [{"title": "t", "url": u, "snippet": "s"} for u in self.search_urls]}
        self.chats += 1
        return {"choices": [{"message": {"content": json.dumps({"results": self.answers})}}]}


class FindYearsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "years.json"
        settings = patch.object(deepseek_years, "_settings", return_value={"DEEPSEEK_API": "key"})
        settings.start()
        self.addCleanup(settings.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def run_with(self, fake, tracks):
        with patch.object(deepseek_years, "_post_json", side_effect=fake):
            return find_years(tracks, cache_path=self.cache)

    def test_only_years_backed_by_search_results_are_accepted(self):
        k = {name: base_key(f"Песня {name}", "Артист") for name in "abcdef"}
        fake = FakeDeepSeek([
            {"key": k["a"], "year": 2019, "evidence_url": URL_A},
            {"key": k["b"], "year": 2020, "evidence_url": "https://made-up.example/page"},
            {"key": k["c"], "year": THIS_YEAR + 1, "evidence_url": URL_B},
            {"key": k["d"], "year": None, "evidence_url": None},
            {"key": k["e"], "year": "2018", "evidence_url": URL_A},
        ])
        years = self.run_with(fake, [track(k) for k in "abcdef"])
        self.assertEqual(years, {"a": 2019})
        self.assertEqual(fake.searches, 6)
        self.assertEqual(fake.chats, 1)

    def test_cache_skips_known_and_rechecks_unknown_after_a_week(self):
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        fresh = datetime.now(timezone.utc).isoformat()
        self.cache.write_text(json.dumps({"version": 1, "tracks": {
            "found": {"year": 2015, "checked_at": old},
            "unknown_fresh": {"year": None, "checked_at": fresh},
            "unknown_old": {"year": None, "checked_at": old},
        }}), encoding="utf-8")
        fake = FakeDeepSeek([{"key": base_key("Песня unknown_old", "Артист"), "year": 2021, "evidence_url": URL_A}])
        years = self.run_with(fake, [track("found"), track("unknown_fresh"), track("unknown_old")])
        self.assertEqual(years, {"found": 2015, "unknown_old": 2021})
        self.assertEqual(fake.searches, 1)
        saved = json.loads(self.cache.read_text(encoding="utf-8"))["tracks"]
        group = base_key("Песня unknown_old", "Артист")
        self.assertEqual(saved[group]["year"], 2021)
        self.assertEqual(saved[group]["evidence_url"], URL_A)

    def test_batches_of_ten(self):
        fake = FakeDeepSeek([])
        self.run_with(fake, [track(str(i)) for i in range(23)])
        self.assertEqual(fake.chats, 3)

    def test_no_request_when_everything_is_cached(self):
        self.cache.write_text(json.dumps({"version": 1, "tracks": {
            "a": {"year": 2010, "checked_at": "2020-01-01T00:00:00Z"}}}), encoding="utf-8")
        fake = FakeDeepSeek([])
        self.assertEqual(self.run_with(fake, [track("a")]), {"a": 2010})
        self.assertEqual(fake.searches + fake.chats, 0)

    def test_missing_api_key(self):
        with patch.object(deepseek_years, "_settings", return_value={}), self.assertRaises(RuntimeError):
            find_years([track("a")], cache_path=self.cache)

    def test_broken_model_answer(self):
        def broken(url, payload, api_key, timeout):
            if url == deepseek_years.SEARCH_URL:
                return {"results": []}
            return {"choices": [{"message": {"content": "not json"}}]}
        with patch.object(deepseek_years, "_post_json", side_effect=broken), self.assertRaises(RuntimeError):
            find_years([track("a")], cache_path=self.cache)


class VersionTests(unittest.TestCase):
    def test_version_markers_are_removed(self):
        cases = {
            "Hold The Horizon (Extended Mix)": "Hold The Horizon",
            "One Desire (Mondotek Radio Edit)": "One Desire",
            "Ты не бойся ночи (Nightcore)": "Ты не бойся ночи",
            "Пьяный (Speed Up)": "Пьяный",
            "Танцуй пока молодой (рэп версия)": "Танцуй пока молодой",
            "Beni Al (Ta Ki Seni Görene Kadar) [Afro House Remix]": "Beni Al (Ta Ki Seni Görene Kadar)",
            "pepsi p (prod. STAKILLAZ)": "pepsi p",
            "Slow Down (Can't Stop Thinking)": "Slow Down (Can't Stop Thinking)",
            "Хочешь, я тебе спою (Я подарю тебе стихи)": "Хочешь, я тебе спою (Я подарю тебе стихи)",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(base_title(title), expected)


class VersionGroupingTests(FindYearsTests):
    def test_versions_share_one_request(self):
        group = base_key("Hold The Horizon", "ZOYA")
        fake = FakeDeepSeek([{"key": group, "year": 2026, "evidence_url": URL_A}])
        tracks = [track("plain", "Hold The Horizon", "ZOYA"), track("ext", "Hold The Horizon (Extended Mix)", "ZOYA")]
        self.assertEqual(self.run_with(fake, tracks), {"plain": 2026, "ext": 2026})
        self.assertEqual(fake.searches, 1)

    def test_year_of_known_original_is_reused(self):
        fake = FakeDeepSeek([])
        known = {base_key("Hold The Horizon", "ZOYA"): 2026}
        with patch.object(deepseek_years, "_post_json", side_effect=fake):
            years = find_years([track("ext", "Hold The Horizon (Extended Mix)", "ZOYA")],
                               known=known, cache_path=self.cache)
        self.assertEqual(years, {"ext": 2026})
        self.assertEqual(fake.searches + fake.chats, 0)

    def test_recheck_asks_again_for_cached_unknown(self):
        group = base_key("Песня x", "Артист")
        self.cache.write_text(json.dumps({"version": 1, "tracks": {
            group: {"year": None, "checked_at": datetime.now(timezone.utc).isoformat()}}}), encoding="utf-8")
        fake = FakeDeepSeek([{"key": group, "year": 1990, "evidence_url": URL_B}])
        self.assertEqual(self.run_with(fake, [track("x")]), {})
        with patch.object(deepseek_years, "_post_json", side_effect=fake):
            years = find_years([track("x")], recheck=True, cache_path=self.cache)
        self.assertEqual(years, {"x": 1990})


class SaveYearsTests(unittest.TestCase):
    def test_updates_only_found_years(self):
        executed = []

        class Cursor:
            rowcount = 1

        class Conn:
            def execute(self, sql, params):
                executed.append(params)
                return Cursor()

        tracks = [{"id": 1, "key": "a"}, {"id": 2, "key": "b"}]
        self.assertEqual(save_years(Conn(), tracks, {"a": 2019}), 1)
        self.assertEqual(executed, [(2019, 1)])


if __name__ == "__main__":
    unittest.main()
