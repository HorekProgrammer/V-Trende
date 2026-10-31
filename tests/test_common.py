import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from parser import run_all
from parser.common import (
    CATEGORY_LIMITS,
    CHARTS,
    SaveError,
    build_payload,
    match_key,
    normalize_text,
    resolve_limit,
    save_chart,
    week_start,
)
from parser.common.upload import MOSCOW_TZ
from parser.twitch import get_russian_twitch_positions, parse_ranking_positions_html
from tests.test_twitch import page as twitch_page
from tests.test_twitch import response as twitch_response
from tests.test_zvuk import page as zvuk_page
from tests.test_zvuk import tracks as zvuk_tracks

MONDAY = date(2026, 10, 19)


def music(position, title="Песня", artists=("Артист",)):
    return {"position": position, "title": title, "artists": list(artists)}


def music_chart(count):
    return [music(i, f"Песня {i}") for i in range(1, count + 1)]


def env(**values):
    base = {"BACKEND_URL": "", "INTERNAL_API_TOKEN": ""}
    base.update(values)
    return patch("parser.common.upload._settings", return_value=base)


class NormalizeTests(unittest.TestCase):
    def test_case_yo_punctuation_and_spaces(self):
        self.assertEqual(normalize_text("  Ёлка — ПЕСНЯ!!  "), "елка песня")

    def test_feat_markers_are_removed(self):
        self.assertEqual(normalize_text("Song (feat. Someone)"), "song")
        self.assertEqual(normalize_text("Song feat. Someone"), "song")
        self.assertEqual(normalize_text("Song [Explicit]"), "song")

    def test_remix_stays_a_different_track(self):
        self.assertNotEqual(match_key("Song (Remix)", ["A"]), match_key("Song", ["A"]))

    def test_same_track_from_different_services_gets_same_key(self):
        shazam = match_key("Песня", ["HUGEL, Imael Angel & Ultra Naté"])
        zvuk = match_key("песня (feat. Imael Angel)", ["HUGEL", "Imael Angel"])
        self.assertEqual(shazam, zvuk)
        self.assertEqual(shazam, "hugel|песня")

    def test_title_only_for_non_music(self):
        self.assertEqual(match_key("Counter-Strike 2™"), "counter strike 2")

    def test_empty_values_are_rejected(self):
        with self.assertRaises(ValueError):
            match_key("!!!")
        with self.assertRaises(ValueError):
            match_key("Песня", [])


class WeekStartTests(unittest.TestCase):
    def test_monday_in_moscow_time(self):
        # Воскресенье 22:30 UTC — уже понедельник в Москве.
        moment = datetime(2026, 10, 25, 22, 30, tzinfo=timezone.utc)
        self.assertEqual(week_start(moment), date(2026, 10, 26))
        self.assertEqual(week_start(datetime(2026, 10, 21, 12, tzinfo=MOSCOW_TZ)), MONDAY)

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ValueError):
            week_start(datetime(2026, 10, 21))


class LimitTests(unittest.TestCase):
    def test_category_limits(self):
        self.assertEqual(CATEGORY_LIMITS, {"music": 100, "games": 100, "movies": 50, "streamers": 150})

    def test_every_chart_respects_category_limit(self):
        expected = {
            "yandex_music": 100, "zvuk": 100, "shazam": 100, "vk": 100, "apple_music": 100, "kion": 100,
            "steam": 100, "steam_players": 100, "epic_most_played": 100, "epic_popular": 50,
            "kinopoisk": 50, "kinopoisk_boxoffice": 50, "twitch": 150,
        }
        self.assertEqual({key: chart.limit for key, chart in CHARTS.items()}, expected)

    def test_resolve_limit(self):
        self.assertIsNone(resolve_limit("shazam", None, save=False))
        self.assertEqual(resolve_limit("shazam", 150, save=False), 150)
        self.assertEqual(resolve_limit("shazam", None, save=True), 100)
        self.assertEqual(resolve_limit("shazam", 150, save=True), 100)
        self.assertEqual(resolve_limit("twitch", 10, save=True), 10)


class BuildPayloadTests(unittest.TestCase):
    def test_music_payload_is_cut_to_100(self):
        payload = build_payload("shazam", music_chart(200), week=MONDAY)
        self.assertEqual(payload["source"], "shazam")
        self.assertEqual(payload["category"], "music")
        self.assertEqual(payload["week_start"], "2026-10-19")
        self.assertEqual(len(payload["entries"]), 100)
        self.assertEqual(payload["entries"][0], {
            "position": 1, "title": "Песня 1", "subtitle": "Артист", "genre": None,
            "external_id": None, "url": None, "cover_url": None, "match_key": "артист|песня 1",
        })

    def test_movies_are_cut_to_50_and_streamers_to_150(self):
        movies = [{"position": i, "title": f"Фильм {i}", "kinopoisk_id": i, "year": 2026} for i in range(1, 1001)]
        streamers = [{"position": i, "channel": f"Канал {i}", "slug": f"Chan_{i}"} for i in range(1, 151)]
        self.assertEqual(len(build_payload("kinopoisk", movies, week=MONDAY)["entries"]), 50)
        twitch = build_payload("twitch", streamers, week=MONDAY)["entries"]
        self.assertEqual(len(twitch), 150)
        self.assertEqual(twitch[0]["external_id"], "chan_1")
        self.assertEqual(twitch[0]["url"], "https://www.twitch.tv/chan_1")

    def test_platform_metrics_and_tags_are_not_sent(self):
        # Жанры будет проставлять нейросеть: теги Steam в жанр не превращаются.
        item = {"position": 1, "title": "Dota 2", "steam_app_id": 570, "current_players": 700000,
                "peak_today": 800000, "tags": ["Free to Play", "Strategy", "Action"]}
        entry = build_payload("steam_players", [item], week=MONDAY)["entries"][0]
        self.assertEqual(entry, {
            "position": 1, "title": "Dota 2", "subtitle": None, "genre": None,
            "external_id": "570", "url": "https://store.steampowered.com/app/570/", "cover_url": None,
            "match_key": "dota 2",
        })

    def test_kinopoisk_and_epic_entries(self):
        film = build_payload("kinopoisk_boxoffice", [{"position": 1, "title": "Фильм", "kinopoisk_id": 42,
                                                      "box_office": 100}], week=MONDAY)
        self.assertEqual(film["source"], "kinopoisk")
        self.assertEqual(film["entries"][0]["url"], "https://www.kinopoisk.ru/film/42/")
        game = build_payload("epic_popular", [{"position": 1, "title": "Fortnite", "epic_offer_id": "abc",
                                               "epic_namespace": "ns", "epic_slug": None}], week=MONDAY)
        self.assertEqual(game["entries"][0]["external_id"], "abc")
        self.assertIsNone(game["entries"][0]["url"])

    def test_duplicate_object_keeps_best_position(self):
        items = [music(1, "Song"), music(2, "Song (feat. B)"), music(3, "Other")]
        entries = build_payload("zvuk", items, week=MONDAY)["entries"]
        self.assertEqual([e["position"] for e in entries], [1, 3])

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(ValueError):
            build_payload("zvuk", [], week=MONDAY)
        with self.assertRaises(ValueError):
            build_payload("zvuk", [music(1, "A"), music(1, "B")], week=MONDAY)
        with self.assertRaises(ValueError):
            build_payload("zvuk", [{"position": 1, "title": "Без исполнителя"}], week=MONDAY)
        with self.assertRaises(ValueError):
            build_payload("zvuk", music_chart(3), week=date(2026, 10, 21))


class SaveChartTests(unittest.TestCase):
    def test_without_backend_url_writes_outbox(self):
        with tempfile.TemporaryDirectory() as tmp, env():
            message = save_chart("zvuk", music_chart(3), week=MONDAY, outbox_dir=Path(tmp))
            files = list(Path(tmp).iterdir())
            self.assertEqual(len(files), 1)
            self.assertIn(str(files[0]), message)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(len(payload["entries"]), 3)

    def test_rerun_overwrites_same_outbox_file(self):
        with tempfile.TemporaryDirectory() as tmp, env():
            save_chart("zvuk", music_chart(3), week=MONDAY, outbox_dir=Path(tmp))
            save_chart("zvuk", music_chart(2), week=MONDAY, outbox_dir=Path(tmp))
            files = list(Path(tmp).iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(len(json.loads(files[0].read_text(encoding="utf-8"))["entries"]), 2)

    @patch("parser.common.upload.urlopen")
    def test_posts_to_backend(self, opened):
        opened.return_value.__enter__.return_value.status = 200
        with env(BACKEND_URL="http://localhost:8000/", INTERNAL_API_TOKEN="secret"):
            message = save_chart("vk", music_chart(2), week=MONDAY, timeout=5)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8000/api/v1/internal/update-trends")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(json.loads(request.data)["chart"], "Чарт VK Музыки")
        self.assertEqual(opened.call_args.kwargs["timeout"], 5)
        self.assertIn("2 позиций", message)

    def test_backend_errors_raise_save_error(self):
        errors = [HTTPError("u", 500, "err", None, None), URLError("down")]
        for error in errors:
            with self.subTest(error=error), env(BACKEND_URL="http://x", INTERNAL_API_TOKEN="t"), \
                    patch("parser.common.upload.urlopen", side_effect=error):
                with self.assertRaises(SaveError):
                    save_chart("vk", music_chart(1), week=MONDAY)

    def test_missing_token_or_bad_data_raise_save_error(self):
        with env(BACKEND_URL="http://x"):
            with self.assertRaises(SaveError):
                save_chart("vk", music_chart(1), week=MONDAY)
        with env():
            with self.assertRaises(SaveError):
                save_chart("vk", [], week=MONDAY)


class TwitchPositionsTests(unittest.TestCase):
    def test_positions_from_html(self):
        result = parse_ranking_positions_html(twitch_page())
        self.assertEqual(result[0], {
            "position": 1, "channel": "Канал 1", "slug": "channel_1",
            "cover_url": "https://static-cdn.jtvnw.net/jtv_user_pictures/ch1-profile_image-300x300.png",
        })
        self.assertEqual(len(result), 50)

    @patch("parser.twitch.twitch_parser.classify_channels")
    @patch("parser.twitch.twitch_parser.urlopen")
    def test_positions_do_not_request_channel_stats(self, opened, classify):
        opened.return_value = twitch_response(twitch_page())
        classify.side_effect = lambda channels, **_kwargs: {
            channel["_slug"].lower(): {"type": "person", "confidence": 1.0}
            for channel in channels
        }
        result = get_russian_twitch_positions(50)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual([entry["position"] for entry in result], list(range(1, 51)))


class CommandLineTests(unittest.TestCase):
    def run_main(self, module, argv):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["prog", *argv]), redirect_stdout(out), redirect_stderr(err):
            try:
                module.main()
                code = 0
            except SystemExit as exit_:
                code = exit_.code or 0
        return code, out.getvalue(), err.getvalue()

    def test_zvuk_save_from_html(self):
        from parser.zvuk import __main__ as zvuk_main
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "zvuk.html"
            html.write_text(zvuk_page(zvuk_tracks()), encoding="utf-8")
            with patch("parser.common.upload.save_chart", return_value="ok") as saved:
                code, out, err = self.run_main(zvuk_main, ["--html", str(html), "--save"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 100)
        self.assertEqual(saved.call_args.args[0], "zvuk")
        self.assertIn("zvuk: ok", err)

    def test_save_error_exits_with_code_1(self):
        from parser.zvuk import __main__ as zvuk_main
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "zvuk.html"
            html.write_text(zvuk_page(zvuk_tracks()), encoding="utf-8")
            with patch("parser.common.upload.save_chart", side_effect=SaveError("бэкенд недоступен")):
                code, _, err = self.run_main(zvuk_main, ["--html", str(html), "--save"])
        self.assertEqual(code, 1)
        self.assertIn("бэкенд недоступен", err)

    def test_without_save_nothing_is_saved(self):
        from parser.zvuk import __main__ as zvuk_main
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "zvuk.html"
            html.write_text(zvuk_page(zvuk_tracks()), encoding="utf-8")
            with patch("parser.common.upload.save_chart") as saved:
                code, out, _ = self.run_main(zvuk_main, ["--html", str(html), "--limit", "5"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 5)
        saved.assert_not_called()


class EntryPointsTests(unittest.TestCase):
    def test_every_chart_has_cli_with_save_flag(self):
        import importlib
        for key in CHARTS:
            with self.subTest(chart=key):
                module = importlib.import_module(f"parser.{key}.__main__")
                out = io.StringIO()
                with patch("sys.argv", ["prog", "--help"]), redirect_stdout(out), \
                        self.assertRaises(SystemExit):
                    module.main()
                self.assertIn("--save", out.getvalue())


class RunAllTests(unittest.TestCase):
    def test_one_failure_does_not_stop_others(self):
        good = MagicMock(return_value=music_chart(3))
        bad = MagicMock(side_effect=RuntimeError("сайт недоступен"))
        charts = {
            "zvuk": CHARTS["zvuk"].__class__(**{**CHARTS["zvuk"].__dict__, "fetch": good}),
            "vk": CHARTS["vk"].__class__(**{**CHARTS["vk"].__dict__, "fetch": bad}),
        }
        err = io.StringIO()
        with patch.dict(run_all.CHARTS, charts, clear=True), \
                patch("parser.run_all.save_chart", return_value="ok") as saved, \
                patch("parser.run_all.save_chart_failure", return_value="ok"), \
                patch("parser.run_all.missing_chart_keys", return_value=(list(charts), [])), \
                patch("parser.run_all.run_wordstat", return_value=0), redirect_stderr(err):
            code = run_all.main(["--save"])
        self.assertEqual(code, 1)
        good.assert_called_once_with(100)
        saved.assert_called_once()
        self.assertIn("собрано 1 из 2", err.getvalue())
        self.assertIn("vk", err.getvalue())


if __name__ == "__main__":
    unittest.main()
