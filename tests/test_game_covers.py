import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from parser import game_covers
from parser.game_covers import NetworkError, candidate_slugs, fill_game_covers, find_cover, matches, parse_page

SQUARE = "https://images.stopgame.ru/games/logos/7175/c280x280/6LBExfvx0rSclICcuajC0A/rust-square_1.jpg"
HERO = "https://images.stopgame.ru/games/logos/7175/c1280x412/SEWAy-7-E33-zyqBHdkEMg/rust-hero.jpg"


def page(title, *, steam=None, square=SQUARE):
    parts = [f'<h1 class="title">{title} <span>игра</span></h1>', f'<img src="{HERO}">']
    if square:
        parts.append(f'<img src="{square}">')
    if steam:
        parts.append(f'<a href="https://store.steampowered.com/app/{steam}/">Steam</a>')
    return "".join(parts)


class SlugTests(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(candidate_slugs("Rust"), ["rust"])
        self.assertIn("helldivers_2", candidate_slugs("HELLDIVERS™ 2"))
        self.assertIn("warhammer_40_000_space_marine_ii", candidate_slugs("Warhammer 40,000: Space Marine 2"))
        self.assertIn("sims_4", candidate_slugs("The Sims™ 4"))
        self.assertIn("repo", candidate_slugs("R.E.P.O."))
        self.assertIn("witcher_3_wild_hunt", candidate_slugs("The Witcher 3: Wild Hunt — Remastered"))
        self.assertIn("ea_sports_fc_26", candidate_slugs("EA SPORTS FC™ 26 Standard Edition"))
        self.assertIn("sid_meier_s_civilization_vi", candidate_slugs("Sid Meier’s Civilization® VI"))


class PageTests(unittest.TestCase):
    def test_square_cover_not_hero(self):
        info = parse_page(page("RUST", steam="252490"))
        self.assertEqual(info["cover_url"], SQUARE)
        self.assertEqual(info["steam_ids"], {"252490"})
        self.assertEqual(info["title"], "RUST")

    def test_match_rules(self):
        rust = {"title": "Rust", "steam_id": "252490"}
        self.assertTrue(matches(rust, parse_page(page("RUST", steam="252490"))))
        self.assertFalse(matches(rust, parse_page(page("RUST", steam="999"))))
        self.assertTrue(matches(rust, parse_page(page("Rust"))))
        self.assertFalse(matches(rust, parse_page(page("RUST", steam="252490", square=None))))
        self.assertFalse(matches({"title": "Crosshair V2", "steam_id": None}, parse_page(page("Crosshair X"))))
        self.assertFalse(matches({"title": "HITMAN World of Assassination", "steam_id": None},
                                 parse_page(page("Hitman III"))))
        self.assertTrue(matches({"title": "Cyberpunk 2077: Ultimate Edition", "steam_id": None},
                                parse_page(page("Cyberpunk 2077"))))

    @patch.object(game_covers, "_fetch")
    def test_tries_next_slug(self, fetch):
        fetch.side_effect = lambda url: None if url.endswith("space_marine_2") else page(
            "Warhammer 40,000: Space Marine II", steam="2183900")
        game = {"title": "Warhammer 40,000: Space Marine 2", "steam_id": "2183900"}
        self.assertEqual(find_cover(game), SQUARE)


class FakeConn:
    def __init__(self, games):
        self.games, self.updates = games, []

    def execute(self, sql, params):
        if sql.lstrip().startswith("UPDATE"):
            self.updates.append(params)
            return None
        rows = [(g["id"], g["title"], g.get("steam_id")) for g in self.games]

        class Result:
            def fetchall(self):
                return rows

        return Result()


class FillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name) / "covers.json"

    def run_fill(self, conn, covers, **kwargs):
        with patch.object(game_covers, "find_cover", side_effect=covers):
            return fill_game_covers(conn, cache_path=self.cache, log=lambda *a: None, **kwargs)

    def test_found_saved_missing_cached(self):
        conn = FakeConn([{"id": 1, "title": "Rust"}, {"id": 2, "title": "FiveM"}])
        stats = self.run_fill(conn, [SQUARE, None])
        self.assertEqual(conn.updates, [(SQUARE, "stopgame", 1)])
        self.assertEqual((stats["found"], stats["missing"]), (1, 1))
        self.assertIn("2", json.loads(self.cache.read_text(encoding="utf-8")))

    def test_recent_miss_skipped_old_rechecked(self):
        now = datetime.now(timezone.utc)
        self.cache.write_text(json.dumps({
            "1": {"checked_at": now.isoformat()},
            "2": {"checked_at": (now - timedelta(days=31)).isoformat()},
        }), encoding="utf-8")
        conn = FakeConn([{"id": 1, "title": "A"}, {"id": 2, "title": "B"}])
        stats = self.run_fill(conn, [SQUARE])
        self.assertEqual(stats["checked"], 1)
        self.assertEqual(conn.updates, [(SQUARE, "stopgame", 2)])

    def test_network_errors_are_not_cached_and_stop_run(self):
        conn = FakeConn([{"id": i, "title": f"G{i}"} for i in range(5)])
        stats = self.run_fill(conn, [NetworkError("HTTP 429")] * 5)
        self.assertEqual(stats["errors"], game_covers.MAX_NETWORK_ERRORS)
        self.assertEqual(conn.updates, [])
        self.assertFalse(self.cache.exists())


class FetchTests(unittest.TestCase):
    @patch.object(game_covers.time, "sleep")
    @patch.object(game_covers, "urlopen")
    def test_404_means_no_page(self, opened, _sleep):
        from urllib.error import HTTPError
        opened.side_effect = HTTPError("u", 404, "Not Found", {}, None)
        self.assertIsNone(game_covers._fetch("https://stopgame.ru/game/x"))

    @patch.object(game_covers.time, "sleep")
    @patch.object(game_covers, "urlopen")
    def test_429_twice_is_network_error(self, opened, _sleep):
        from urllib.error import HTTPError
        opened.side_effect = HTTPError("u", 429, "Too Many", {}, None)
        with self.assertRaises(NetworkError):
            game_covers._fetch("https://stopgame.ru/game/x")
        self.assertEqual(opened.call_count, 2)


if __name__ == "__main__":
    unittest.main()
