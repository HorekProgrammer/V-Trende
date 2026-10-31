"""Тесты конвейера данных, не требующие PostgreSQL."""

import io
import json
import random
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from database import seed
from database.migrate import MigrationError, discover
from parser import run_all, wordstat_batch
from parser.common import CHARTS, build_failure_payload, default_search_query, save_chart_failure

MONDAY = date(2026, 10, 19)


def env(**values):
    base = {"BACKEND_URL": "", "INTERNAL_API_TOKEN": ""}
    base.update(values)
    return patch("parser.common.upload._settings", return_value=base)


class MigrationFilesTests(unittest.TestCase):
    def test_project_migrations_are_ordered_and_named(self):
        migrations = discover()
        self.assertEqual([m.version for m in migrations], ["001", "002", "003", "004", "005", "006", "007", "008"])
        self.assertTrue(all(m.sql.strip() for m in migrations))

    def test_bad_name_and_duplicate_number_are_rejected(self):
        for names in (["1_init.sql"], ["001_init.sql", "001_other.sql"], ["001_Init.sql"]):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as tmp:
                for name in names:
                    (Path(tmp) / name).write_text("SELECT 1;", encoding="utf-8")
                with self.assertRaises(MigrationError):
                    discover(Path(tmp))

    def test_checksum_ignores_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "001_a.sql").write_bytes(b"SELECT 1;\n")
            (Path(tmp) / "002_b.sql").write_bytes(b"SELECT 1;\r\n")
            first, second = discover(Path(tmp))
        self.assertEqual(first.checksum, second.checksum)


class SearchQueryTests(unittest.TestCase):
    def test_default_queries(self):
        self.assertEqual(default_search_query("music", "Песня (feat. B)", "Артист, B"), "артист песня")
        self.assertEqual(default_search_query("movies", "Мастер и Маргарита", "2024"),
                         "мастер и маргарита фильм")
        self.assertEqual(default_search_query("games", "Counter-Strike 2™"), "counter strike 2")
        self.assertEqual(default_search_query("streamers", "Buster"), "buster")

    def test_wordstat_operators_are_removed(self):
        self.assertEqual(default_search_query("games", '!Игра "+бонус" -[демо]'), "игра бонус демо")

    def test_empty_query_is_rejected(self):
        with self.assertRaises(ValueError):
            default_search_query("games", "!!!")


class FailurePayloadTests(unittest.TestCase):
    def test_failure_payload(self):
        payload = build_failure_payload("vk", RuntimeError("cookies expired"), week=MONDAY)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["source"], "vk")
        self.assertEqual(payload["week_start"], "2026-10-19")
        self.assertEqual(payload["error"], "cookies expired")
        self.assertNotIn("entries", payload)

    def test_failure_file_does_not_overwrite_success_file(self):
        from parser.common import save_chart
        tracks = [{"position": 1, "title": "Песня", "artists": ["Артист"]}]
        with tempfile.TemporaryDirectory() as tmp, env():
            save_chart("vk", tracks, week=MONDAY, outbox_dir=Path(tmp))
            save_chart_failure("vk", "сбой", week=MONDAY, outbox_dir=Path(tmp))
            names = sorted(p.name for p in Path(tmp).iterdir())
        self.assertEqual(len(names), 2)
        self.assertTrue(names[1].endswith("_failed.json"))

    @patch("parser.common.upload.urlopen")
    def test_search_stats_go_to_their_endpoint(self, opened):
        from parser.common import save_payload
        opened.return_value.__enter__.return_value.status = 200
        with env(BACKEND_URL="http://api", INTERNAL_API_TOKEN="t"):
            save_payload({"type": "search_stats", "week_start": "2026-10-19", "entries": []})
        self.assertEqual(opened.call_args.args[0].full_url, "http://api/api/v1/internal/update-search-stats")


class BoxOfficeAdapterTests(unittest.TestCase):
    def test_row_with_missing_numbers_is_saved_without_metrics(self):
        from parser.common import build_payload
        from parser.kinopoisk_boxoffice.kinopoisk_boxoffice_parser import _parse_row
        cells = ["1", "Фильм", "Прокатчик [1 095]", "-", "—", "-", "—", "-"]
        row = _parse_row(position=1, cells=cells, title="Фильм", href="/film/42/")
        entry = build_payload("kinopoisk_boxoffice", [row], week=MONDAY)["entries"][0]
        self.assertEqual(entry["external_id"], "42")
        self.assertEqual(entry["url"], "https://www.kinopoisk.ru/film/42/")
        self.assertNotIn("viewers", entry)
        self.assertNotIn("weeks_in_release", entry)


class TwitchAdapterTests(unittest.TestCase):
    def test_weekly_metrics_are_kept_in_payload(self):
        from parser.common import build_payload

        channel = {
            "position": 1,
            "channel": "Streamer",
            "slug": "streamer",
            "total_followers": 100_000,
            "hours_streamed": 40.5,
            "average_viewers": 2_000,
            "peak_viewers": 5_000,
            "hours_watched": 81_000,
            "followers_gained": 500,
            "followers_per_hour": 12.346,
        }
        entry = build_payload("twitch", [channel], week=MONDAY)["entries"][0]

        self.assertEqual(entry["external_id"], "streamer")
        self.assertEqual(entry["hours_watched"], 81_000)
        self.assertEqual(entry["average_viewers"], 2_000)
        self.assertEqual(entry["followers_gained"], 500)
        self.assertEqual(entry["followers_per_hour"], 12.346)

    def test_negative_follower_growth_is_normalized_to_zero(self):
        from parser.common import build_payload

        channel = {
            "position": 1,
            "channel": "Streamer",
            "slug": "streamer",
            "total_followers": 100,
            "hours_streamed": 5.0,
            "average_viewers": 10,
            "peak_viewers": 20,
            "hours_watched": 50,
            "followers_gained": -3,
            "followers_per_hour": -0.6,
        }
        entry = build_payload("twitch", [channel], week=MONDAY)["entries"][0]
        self.assertEqual(entry["followers_gained"], 0)
        self.assertEqual(entry["followers_per_hour"], 0)


class RunAllFailureTests(unittest.TestCase):
    def test_failed_chart_is_recorded_with_save(self):
        bad = MagicMock(side_effect=RuntimeError("сайт недоступен"))
        chart = CHARTS["vk"].__class__(**{**CHARTS["vk"].__dict__, "fetch": bad})
        with patch.dict(run_all.CHARTS, {"vk": chart}, clear=True), \
                patch("parser.run_all.missing_chart_keys", return_value=(["vk"], [])), \
                patch("parser.run_all.save_chart_failure", return_value="ok") as recorded, \
                patch("parser.run_all.run_wordstat", return_value=0) as wordstat, \
                redirect_stderr(io.StringIO()) as err:
            code = run_all.main(["--save"])
        self.assertEqual(code, 1)
        recorded.assert_called_once()
        wordstat.assert_called_once()
        self.assertIn("сбой записан", err.getvalue())

    def test_failure_is_not_recorded_without_save(self):
        bad = MagicMock(side_effect=RuntimeError("сайт недоступен"))
        chart = CHARTS["vk"].__class__(**{**CHARTS["vk"].__dict__, "fetch": bad})
        with patch.dict(run_all.CHARTS, {"vk": chart}, clear=True), \
                patch("parser.run_all.save_chart_failure") as recorded, redirect_stderr(io.StringIO()):
            run_all.main([])
        recorded.assert_not_called()

    def test_wordstat_failure_makes_pipeline_fail(self):
        chart = CHARTS["vk"].__class__(
            **{**CHARTS["vk"].__dict__, "fetch": MagicMock(return_value=[])}
        )
        with patch.dict(run_all.CHARTS, {"vk": chart}, clear=True), \
                patch("parser.run_all.missing_chart_keys", return_value=(["vk"], [])), \
                patch("parser.run_all.save_chart", return_value="ok"), \
                patch("parser.run_all.run_wordstat", return_value=1), \
                redirect_stderr(io.StringIO()):
            self.assertEqual(run_all.main(["--save"]), 1)

    def test_next_week_is_prepared_without_early_publish(self):
        current_week = date(2026, 10, 26)
        with patch.dict(run_all.CHARTS, {}, clear=True), \
                patch("parser.run_all.week_start", return_value=current_week), \
                patch("parser.run_all.missing_chart_keys", return_value=([], [])) as missing, \
                patch("parser.run_all.run_wordstat", return_value=0) as wordstat, \
                redirect_stderr(io.StringIO()):
            self.assertEqual(
                run_all.main(["--save", "--next-week", "--defer-publish"]),
                0,
            )

        target = date(2026, 11, 2)
        missing.assert_called_once_with([], target)
        wordstat.assert_called_once_with(target, publish=False)


class WordstatBatchTests(unittest.TestCase):
    TRENDS = [{"category": "games", "match_key": f"g{i}", "query": f"игра {i}"} for i in range(4)]

    def test_rejected_phrase_is_skipped(self):
        def fetch(query):
            if query == "игра 1":
                raise ValueError("Wordstat отклонил поисковую фразу.")
            return 100
        entries, stopped = wordstat_batch.collect(self.TRENDS, fetch=fetch, delay=0, log=lambda m: None)
        self.assertIsNone(stopped)
        self.assertEqual([e["match_key"] for e in entries], ["g0", "g2", "g3"])
        self.assertEqual(entries[0]["search_count"], 100)

    def test_session_problem_stops_and_keeps_collected(self):
        def fetch(query):
            if query == "игра 2":
                raise RuntimeError("Wordstat Web: HTTP 403.")
            return 5
        entries, stopped = wordstat_batch.collect(self.TRENDS, fetch=fetch, delay=0, log=lambda m: None)
        self.assertIn("403", stopped)
        self.assertEqual(len(entries), 2)

    def test_payload_shape(self):
        payload = wordstat_batch.build_payload(MONDAY, [{**self.TRENDS[0], "search_count": 1}])
        self.assertEqual(payload["type"], "search_stats")
        self.assertEqual(payload["week_start"], "2026-10-19")
        json.dumps(payload)

    def test_deferred_payload_does_not_request_publication(self):
        payload = wordstat_batch.build_payload(MONDAY, [], publish=False)
        self.assertIs(payload["publish"], False)

    def test_transient_network_error_is_retried(self):
        calls = 0

        def fetch(_query):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("Wordstat Web: ошибка сети или таймаут.")
            return 42

        entries, stopped = wordstat_batch.collect(
            self.TRENDS[:1], fetch=fetch, delay=0, retry_delay=0, log=lambda m: None
        )
        self.assertIsNone(stopped)
        self.assertEqual(calls, 3)
        self.assertEqual(entries[0]["search_count"], 42)


class SeedGeneratorTests(unittest.TestCase):
    def test_generated_payloads_respect_limits_and_format(self):
        weeks = [date(2026, 9, 28), date(2026, 10, 5), date(2026, 10, 12)]
        payloads = seed.generate(weeks, random.Random(1))
        charts = [p for p in payloads if p["type"] == "chart" and p.get("status") != "failed"]
        stats = [p for p in payloads if p["type"] == "search_stats"]
        self.assertEqual(len(stats), 3)
        self.assertGreater(len(charts), 30)
        for payload in charts:
            limit = next(c.limit for c in CHARTS.values()
                         if c.source == payload["source"] and c.name == payload["chart"])
            self.assertLessEqual(len(payload["entries"]), limit)
            self.assertTrue(all(e["title"].startswith("Тест") for e in payload["entries"]))

    def test_same_seed_gives_same_data(self):
        weeks = [date(2026, 10, 12)]
        first = seed.generate(weeks, random.Random(5))
        second = seed.generate(weeks, random.Random(5))
        strip = lambda ps: [{k: v for k, v in p.items() if k != "collected_at"} for p in ps]  # noqa: E731
        self.assertEqual(strip(first), strip(second))


if __name__ == "__main__":
    unittest.main()
