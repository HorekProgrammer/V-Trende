import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from parser.yandex_music import get_yandex_music_chart
from parser.yandex_music.yandex_music_parser import CHART_URL, parse_chart_html


def track(number):
    return {"id": str(100 + number), "title": "Песня <3 & музыка", "durationMs": 123456,
            "artists": [{"name": "Артист A"}, {"name": "Артист B"}],
            "chart": {"position": number}}


def page(operations):
    return "<html><script>window.__PAGE_STATE_PATCHES__['pages/chart'].push(" + json.dumps(operations) + ");</script></html>"


def data():
    return [{"op": "replace", "path": "/tracksSubPage/loadingState", "value": "PENDING"},
            *[{"op": "add", "path": f"/tracksSubPage/items/{i}", "value": track(i + 1)} for i in range(2)],
            {"op": "replace", "path": "/tracksSubPage/loadingState", "value": "RESOLVE"}]


class MusicTests(unittest.TestCase):
    def test_normalization(self):
        tracks = parse_chart_html(page(data()))
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0], {"title": "Песня <3 & музыка",
                         "artists": ["Артист A", "Артист B"], "position": 1})
        self.assertTrue(all(set(t) == {"title", "artists", "position"} for t in tracks))

    def test_removed_fields_are_not_required(self):
        operations = data()
        for operation in operations:
            if operation["op"] == "add":
                operation["value"].pop("id")
                operation["value"].pop("durationMs")
        self.assertEqual(parse_chart_html(page(operations)), parse_chart_html(page(data())))

    def test_multiple_scripts_and_extra_properties(self):
        operations = data()
        html = page(operations[:2]) + page(operations[2:]) + page([
            {"op": "replace", "path": "/tracksSubPage/items/0/trackType", "value": "music"}])
        self.assertEqual(len(parse_chart_html(html)), 2)

    def test_partial_or_blocked_page_is_error(self):
        for html in ("<html>Log in</html>", page(data()[:-1]), page([])):
            with self.subTest(html=html), self.assertRaises(RuntimeError):
                parse_chart_html(html)

    def test_bad_schema_and_duplicate_positions(self):
        for field, value in (("artists", None), ("title", ""), ("chart", {})):
            operations = data()
            operations[1]["value"][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                parse_chart_html(page(operations))
        operations = data()
        operations[2]["value"]["chart"]["position"] = 1
        with self.assertRaises(RuntimeError):
            parse_chart_html(page(operations))

    def test_position_gap_and_invalid_json(self):
        operations = data()
        operations[2]["value"]["chart"]["position"] = 3
        with self.assertRaises(RuntimeError):
            parse_chart_html(page(operations))
        with self.assertRaises(RuntimeError):
            parse_chart_html("<script>window.__PAGE_STATE_PATCHES__['pages/chart'].push(bad);</script>")

    @patch("parser.yandex_music.yandex_music_parser.urlopen")
    def test_fetch_without_auth_and_limit(self, opened):
        opened.return_value.__enter__.return_value.read.return_value = page(data()).encode()
        self.assertEqual(len(get_yandex_music_chart(1)), 1)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, CHART_URL)
        self.assertIsNone(request.get_header("Cookie"))
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(opened.call_args.kwargs["timeout"], 30)

    @patch("parser.yandex_music.yandex_music_parser.urlopen")
    def test_invalid_arguments_do_not_call_network(self, opened):
        for limit in (0, -1, True, "10"):
            with self.assertRaises(ValueError):
                get_yandex_music_chart(limit)
        for timeout in (0, float("nan"), "30"):
            with self.assertRaises(ValueError):
                get_yandex_music_chart(timeout=timeout)
        opened.assert_not_called()

    @patch("parser.yandex_music.yandex_music_parser.urlopen")
    def test_network_errors(self, opened):
        for error in (HTTPError(CHART_URL, 429, "limit", {}, None), URLError("offline"), TimeoutError()):
            opened.side_effect = error
            with self.assertRaises(RuntimeError):
                get_yandex_music_chart()


if __name__ == "__main__":
    unittest.main()
