"""Тесты на настоящей PostgreSQL: миграции, загрузчик, представления.

Запускаются, только если задан TEST_DATABASE_URL, например:
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vtrende_test

ВНИМАНИЕ: перед каждым тестом схема public этой базы удаляется целиком.
Никогда не указывайте здесь рабочую базу.
"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from database.db import settings
from parser.common import build_failure_payload, build_payload

TEST_URL = (settings().get("TEST_DATABASE_URL") or "").strip()

W1 = date(2026, 10, 5)
W2 = date(2026, 10, 12)
W3 = date(2026, 10, 19)


def tracks(*specs):
    """specs: (позиция, номер трека) → записи музыкального парсера."""
    return [{"position": p, "title": f"Трек {n}", "artists": [f"Артист {n}"]} for p, n in specs]


def steam(*specs):
    return [{"position": p, "title": f"Игра {n}", "steam_app_id": 1000 + n, "tags": []} for p, n in specs]


@unittest.skipUnless(TEST_URL, "TEST_DATABASE_URL не задан: тесты на PostgreSQL пропущены")
class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        from database.db import connect
        from database.migrate import migrate
        self.conn = connect(TEST_URL)
        self.conn.execute("DROP SCHEMA public CASCADE")
        self.conn.execute("CREATE SCHEMA public")
        migrate(self.conn)

    def tearDown(self):
        self.conn.close()

    def load(self, payload):
        from database.load_outbox import load_payload
        with self.conn.transaction():
            return load_payload(self.conn, payload)

    def refresh(self):
        from database.load_outbox import refresh_rankings
        refresh_rankings(self.conn)

    def scalar(self, sql, params=None):
        return self.conn.execute(sql, params).fetchone()[0]

    def rows(self, sql, params=None):
        return self.conn.execute(sql, params).fetchall()


class MigrationTests(DatabaseTestCase):
    def test_second_run_applies_nothing(self):
        from database.migrate import migrate, status
        self.assertEqual(migrate(self.conn), [])
        self.assertTrue(all(applied for _, _, applied in status(self.conn)))

    def test_changed_applied_migration_is_detected(self):
        from database.migrate import MIGRATIONS_DIR, MigrationError, migrate
        with tempfile.TemporaryDirectory() as tmp:
            for path in MIGRATIONS_DIR.glob("*.sql"):
                text = path.read_text(encoding="utf-8")
                if path.name.startswith("002"):
                    text += "\n-- изменено"
                (Path(tmp) / path.name).write_text(text, encoding="utf-8")
            with self.assertRaises(MigrationError):
                migrate(self.conn, directory=Path(tmp))

    def test_new_migration_is_applied_and_failed_one_is_rolled_back(self):
        from database.migrate import MIGRATIONS_DIR, MigrationError, migrate
        with tempfile.TemporaryDirectory() as tmp:
            migration_paths = list(MIGRATIONS_DIR.glob("*.sql"))
            for path in migration_paths:
                (Path(tmp) / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            last_version = max(int(path.name.split("_", 1)[0]) for path in migration_paths)
            extra_version = f"{last_version + 1:03d}"
            broken_version = f"{last_version + 2:03d}"
            (Path(tmp) / f"{extra_version}_extra.sql").write_text(
                "CREATE TABLE extra (id INT);", encoding="utf-8"
            )
            self.assertEqual(migrate(self.conn, directory=Path(tmp)), [extra_version])
            (Path(tmp) / f"{broken_version}_broken.sql").write_text(
                "CREATE TABLE half_done (id INT); SELECT * FROM no_such_table;", encoding="utf-8")
            with self.assertRaises(MigrationError):
                migrate(self.conn, directory=Path(tmp))
        self.assertIsNone(self.scalar("SELECT to_regclass('half_done')"))
        self.assertFalse(self.scalar(
            "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = %s)",
            (broken_version,),
        ))

    def test_baseline_for_database_created_from_schema_sql(self):
        from database.migrate import MIGRATIONS_DIR, migrate
        self.conn.execute("DROP SCHEMA public CASCADE")
        self.conn.execute("CREATE SCHEMA public")
        # База, созданная вручную старым schema.sql (= миграция 001).
        self.conn.execute((MIGRATIONS_DIR / "001_init.sql").read_text(encoding="utf-8"))
        self.assertEqual(migrate(self.conn, baseline="001"), ["002", "003", "004", "005", "006"])

    def test_genres_are_seeded_and_category_is_enforced(self):
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM genres"), 20)
        self.load(build_payload("zvuk", tracks((1, 1)), week=W1))
        rock = self.scalar("SELECT id FROM genres WHERE category = 'music' AND name = 'Рок'")
        rpg = self.scalar("SELECT id FROM genres WHERE category = 'games' AND name = 'RPG'")
        self.conn.execute("UPDATE trends SET genre_id = %s", (rock,))
        with self.assertRaises(Exception):
            self.conn.execute("UPDATE trends SET genre_id = %s", (rpg,))


class LoaderTests(DatabaseTestCase):
    def test_chart_is_loaded_and_reload_does_not_duplicate(self):
        payload = build_payload("zvuk", tracks((1, 1), (2, 2), (3, 3)), week=W1)
        self.load(payload)
        self.load(payload)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trends"), 3)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM chart_runs"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trend_history"), 3)
        self.assertEqual(self.scalar("SELECT status FROM chart_runs"), "success")

    def test_reload_with_new_positions_replaces_them(self):
        self.load(build_payload("zvuk", tracks((1, 1), (2, 2)), week=W1))
        self.load(build_payload("zvuk", tracks((1, 2), (2, 1), (3, 3)), week=W1))
        positions = dict(self.rows(
            "SELECT t.title, h.position FROM trend_history h JOIN trends t ON t.id = h.trend_id"))
        self.assertEqual(positions, {"Трек 2": 1, "Трек 1": 2, "Трек 3": 3})

    def test_same_track_in_two_services_is_one_trend(self):
        self.load(build_payload("zvuk", tracks((1, 1)), week=W1))
        self.load(build_payload("vk", [{"position": 4, "title": "ТРЕК 1 (feat. X)", "artists": ["Артист 1", "X"]}],
                                week=W1))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trends"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trend_history"), 2)
        self.assertEqual(self.scalar("SELECT subtitle FROM trends"), "Артист 1")

    def test_external_id_links_steam_charts_and_title_links_epic(self):
        self.load(build_payload("steam", steam((1, 1)), week=W1))
        self.load(build_payload("steam_players", steam((7, 1)), week=W1))
        self.load(build_payload("epic_popular", [{"position": 2, "title": "Игра 1", "epic_offer_id": "e1",
                                                  "epic_namespace": "n", "epic_slug": "igra-1"}], week=W1))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trends"), 1)
        self.assertEqual(
            sorted(self.rows("SELECT source, external_id FROM trend_source_items")),
            [("epic", "e1"), ("steam", "1001")],
        )

    def test_renamed_object_is_found_by_external_id(self):
        self.load(build_payload("steam", steam((1, 1)), week=W1))
        renamed = [{"position": 1, "title": "Игра 1: Remastered", "steam_app_id": 1001, "tags": []}]
        self.load(build_payload("steam", renamed, week=W2))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trends"), 1)

    def test_two_entries_of_one_object_keep_best_position(self):
        payload = build_payload("steam", steam((1, 1)), week=W1)
        twin = dict(payload["entries"][0], position=5, match_key="другой ключ")
        payload["entries"].append(twin)
        message = self.load(payload)
        self.assertIn("пропущено повторов: 1", message)
        self.assertEqual(self.rows("SELECT position FROM trend_history"), [(1,)])

    def test_failed_run_does_not_replace_success(self):
        self.load(build_payload("vk", tracks((1, 1)), week=W1))
        message = self.load(build_failure_payload("vk", "cookies", week=W1))
        self.assertIn("уже собрана", message)
        self.assertEqual(self.scalar("SELECT status FROM chart_runs"), "success")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trend_history"), 1)

    def test_failure_then_success(self):
        self.load(build_failure_payload("vk", "cookies", week=W1))
        self.assertEqual(self.rows("SELECT status, error FROM chart_runs"), [("failed", "cookies")])
        self.load(build_payload("vk", tracks((1, 1)), week=W1))
        self.assertEqual(self.rows("SELECT status, error FROM chart_runs"), [("success", None)])

    def test_genre_from_payload_is_set_once(self):
        payload = build_payload("zvuk", tracks((1, 1)), week=W1)
        payload["entries"][0]["genre"] = "Рок"
        self.load(payload)
        payload["entries"][0]["genre"] = "Поп"
        self.load(payload)
        self.assertEqual(self.scalar(
            "SELECT g.name FROM trends t JOIN genres g ON g.id = t.genre_id"), "Рок")

    def test_invalid_payload_is_rolled_back_entirely(self):
        from database.load_outbox import PayloadError
        bad_genre = build_payload("zvuk", tracks((1, 1), (2, 2)), week=W1)
        bad_genre["entries"][1]["genre"] = "Шансон"
        bad_week = build_payload("zvuk", tracks((1, 1)), week=W1)
        bad_week["week_start"] = "2026-10-07"
        bad_position = build_payload("zvuk", tracks((1, 1)), week=W1)
        bad_position["entries"][0]["position"] = 101
        for payload in (bad_genre, bad_week, bad_position, {"type": "unknown"}):
            with self.subTest(payload=str(payload)[:60]), self.assertRaises(PayloadError):
                self.load(payload)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM trends"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM chart_runs"), 0)

    def test_search_stats(self):
        self.load(build_payload("zvuk", tracks((1, 1)), week=W1))
        key = self.scalar("SELECT match_key FROM trends")
        stats = {"type": "search_stats", "week_start": W1.isoformat(), "entries": [
            {"category": "music", "match_key": key, "query": "артист 1 трек 1", "search_count": 500},
            {"category": "music", "match_key": "нет такого", "query": "x", "search_count": 1},
        ]}
        self.assertIn("объектов нет в базе: 1", self.load(stats))
        stats["entries"][0]["search_count"] = 700
        self.load(stats)
        self.assertEqual(self.rows("SELECT search_count FROM trend_search_stats"), [(700,)])

    def test_twitch_weekly_metrics_are_saved(self):
        channel = {
            "position": 1, "channel": "Streamer", "slug": "streamer",
            "total_followers": 100_000, "hours_streamed": 40.5,
            "average_viewers": 2_000, "peak_viewers": 5_000,
            "hours_watched": 81_000, "followers_gained": 500,
            "followers_per_hour": 12.346,
        }
        self.load(build_payload("twitch", [channel], week=W1))
        self.assertEqual(
            self.rows("SELECT hours_watched, average_viewers, followers_gained FROM twitch_weekly_stats"),
            [(81_000, 2_000, 500)],
        )

    def test_load_outbox_moves_good_files_and_keeps_bad(self):
        from database.load_outbox import load_outbox
        with tempfile.TemporaryDirectory() as tmp:
            outbox = Path(tmp)
            (outbox / "a.json").write_text(json.dumps(build_payload("zvuk", tracks((1, 1)), week=W1),
                                                      ensure_ascii=False), encoding="utf-8")
            (outbox / "b.json").write_text("{не json", encoding="utf-8")
            loaded, failed = load_outbox(self.conn, outbox, log=lambda message: None)
            self.assertEqual([p.name for p in loaded], ["a.json"])
            self.assertEqual([p.name for p in failed], ["b.json"])
            self.assertTrue((outbox / "loaded" / "a.json").exists())
            self.assertTrue((outbox / "b.json").exists())
        # Рейтинг пересчитан автоматически.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM v_category_top_latest"), 1)


class RankingTests(DatabaseTestCase):
    """Музыка: min_charts = 2, поэтому объект из одного чарта в общий топ не попадает."""

    def setUp(self):
        super().setUp()
        # Неделя 1: трек 1 — 1-е и 3-е места, трек 2 — 2-е и 1-е, трек 3 только в одном чарте.
        self.load(build_payload("zvuk", tracks((1, 1), (2, 2), (3, 3)), week=W1))
        self.load(build_payload("vk", tracks((1, 2), (3, 1)), week=W1))
        # Неделя 2: трек 1 вырос до первого места везде, появился трек 4.
        self.load(build_payload("zvuk", tracks((1, 1), (2, 4), (3, 2)), week=W2))
        self.load(build_payload("vk", tracks((1, 1), (2, 4), (5, 2)), week=W2))
        self.load(build_failure_payload("shazam", "сбой", week=W2))
        self.refresh()

    def top(self, week):
        return self.rows(
            "SELECT title, rank, avg_position, chart_count, charts_collected, prev_rank, rank_change, "
            "peak_rank, weeks_in_top, is_new FROM v_category_top WHERE category = 'music' "
            "AND week_start = %s ORDER BY rank", (week,))

    def test_average_position_and_min_charts(self):
        week1 = self.top(W1)
        self.assertEqual([(r[0], r[1], float(r[2]), r[3]) for r in week1],
                         [("Трек 2", 1, 1.5, 2), ("Трек 1", 2, 2.0, 2)])

    def test_dynamics_and_failed_chart_is_not_counted(self):
        week2 = {r[0]: r for r in self.top(W2)}
        self.assertEqual(list(week2), ["Трек 1", "Трек 4", "Трек 2"])
        track1 = week2["Трек 1"]
        self.assertEqual(track1[4], 2)                       # провал Shazam не учитывается
        self.assertEqual((track1[5], track1[6]), (2, 1))     # было 2-е место, рост на 1
        self.assertEqual((track1[7], track1[8]), (1, 2))     # пик 1, две недели в топе
        self.assertTrue(week2["Трек 4"][9])                  # новинка
        self.assertIsNone(week2["Трек 4"][5])
        self.assertEqual(week2["Трек 2"][6], -2)             # падение с 1-го на 3-е

    def test_latest_main_feed_and_history(self):
        latest = self.rows("SELECT DISTINCT week_start FROM v_category_top_latest")
        self.assertEqual(latest, [(W2,)])
        key = self.scalar("SELECT match_key FROM trends WHERE title = 'Трек 2'")
        self.load({"type": "search_stats", "week_start": W2.isoformat(), "entries": [
            {"category": "music", "match_key": key, "query": "q", "search_count": 10_000}]})
        self.refresh()
        feed = self.rows("SELECT feed_rank, title, search_count FROM v_main_feed ORDER BY feed_rank")
        self.assertEqual(feed[0][1], "Трек 1")  # Wordstat весит 15% и не перекрывает лидерство в чартах
        trend = self.scalar("SELECT id FROM trends WHERE title = 'Трек 2'")
        history = self.rows("SELECT week_start, category_rank, search_count FROM v_trend_history "
                            "WHERE trend_id = %s ORDER BY week_start", (trend,))
        self.assertEqual(history, [(W1, 1, None), (W2, 3, 10_000)])

    def test_chart_top_prev_position(self):
        rows = self.rows("SELECT title, position, prev_position FROM v_chart_top "
                         "WHERE source = 'zvuk' AND week_start = %s ORDER BY position", (W2,))
        self.assertEqual(rows, [("Трек 1", 1, 1), ("Трек 4", 2, None), ("Трек 2", 3, 2)])

    def test_week_gap_breaks_prev_rank(self):
        self.load(build_payload("zvuk", tracks((1, 1)), week=W3 + timedelta(weeks=1)))
        self.load(build_payload("vk", tracks((1, 1)), week=W3 + timedelta(weeks=1)))
        self.refresh()
        row = self.rows("SELECT prev_rank, weeks_in_top FROM v_category_top_latest WHERE title = 'Трек 1'")
        self.assertEqual(row, [(None, 3)])

    def test_prepared_week_is_hidden_until_refresh(self):
        future = W3
        self.load(build_payload("zvuk", tracks((1, 1)), week=future))
        self.load(build_payload("vk", tracks((1, 1)), week=future))
        self.assertEqual(
            self.rows("SELECT DISTINCT week_start FROM v_category_top_latest"),
            [(W2,)],
        )
        self.refresh()
        self.assertEqual(
            self.rows("SELECT DISTINCT week_start FROM v_category_top_latest"),
            [(future,)],
        )


class SeedTests(DatabaseTestCase):
    def test_seed_fills_every_category_within_limits(self):
        from database.seed import seed
        seed(self.conn, weeks=4, random_seed=3, last_week=W3)
        rows = dict(self.rows("SELECT category, MAX(rank) FROM v_category_top_latest GROUP BY category"))
        self.assertEqual(set(rows), {"music", "games", "movies", "streamers"})
        limits = dict(self.rows("SELECT category, top_limit FROM category_settings"))
        for category, max_rank in rows.items():
            self.assertLessEqual(max_rank, limits[category])
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM trend_search_stats"), 0)

    def test_wordstat_batch_picks_all_chart_trends_without_stats(self):
        from database.seed import seed
        from parser.wordstat_batch import pending_trends
        seed(self.conn, weeks=1, random_seed=3, last_week=W3)
        self.conn.execute("DELETE FROM trend_search_stats")
        pending = pending_trends(self.conn, W3)
        self.assertEqual(len(pending), self.scalar(
            "SELECT COUNT(DISTINCT trend_id) FROM v_chart_entries WHERE week_start = %s", (W3,)))
        self.conn.execute("UPDATE trends SET search_query = 'своя фраза' WHERE match_key = %s",
                          (pending[0]["match_key"],))
        self.assertEqual(pending_trends(self.conn, W3)[0]["query"], "своя фраза")


if __name__ == "__main__":
    unittest.main()
