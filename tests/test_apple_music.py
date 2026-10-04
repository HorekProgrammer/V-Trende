import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from parser.apple_music import get_apple_music_chart, parse_chart_html
from parser.apple_music.apple_music_parser import CHART_URL


def tracks(count=100):
    return [
        {
            "title": f"Трек {position}",
            "subtitleLinks": [{"title": "Первый"}, {"title": "Второй"}],
        }
        for position in range(1, count + 1)
    ]


def page(items, *, extra_sections=None):
    sections = list(extra_sections or [])
    sections.append({"itemKind": "trackLockup", "items": items})
    data = {"data": [{"data": {"sections": sections}}]}
    return (
        '<html><script id="serialized-server-data" type="application/json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script></html>"
    )


class AppleMusicTests(unittest.TestCase):
    def test_parses_all_tracks_and_multiple_artists(self):
        result = parse_chart_html(page(tracks()))
        self.assertEqual(len(result), 100)
        self.assertEqual(result[0], {
            "position": 1,
            "title": "Трек 1",
            "artists": ["Первый", "Второй"],
        })
        self.assertEqual(result[-1]["position"], 100)

    def test_ignores_unrelated_sections(self):
        result = parse_chart_html(page(tracks(), extra_sections=[{"itemKind": "header", "items": []}]))
        self.assertEqual(len(result), 100)

    def test_rejects_missing_invalid_or_incomplete_data(self):
        cases = [
            "<html></html>",
            '<script id="serialized-server-data">bad</script>',
            '<script id="serialized-server-data">{}</script>',
            page(tracks(99)),
            page(tracks(), extra_sections=[{"itemKind": "trackLockup", "items": tracks()}]),
        ]
        for html in cases:
            with self.subTest(size=len(html)), self.assertRaises(RuntimeError):
                parse_chart_html(html)

    def test_rejects_invalid_track(self):
        for field, value in (("title", ""), ("title", None), ("subtitleLinks", []), ("subtitleLinks", None)):
            items = tracks()
            items[10][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                parse_chart_html(page(items))

    @patch("parser.apple_music.apple_music_parser.urlopen")
    def test_fetch_without_auth_and_limit(self, opened):
        opened.return_value.__enter__.return_value.read.return_value = page(tracks()).encode()
        self.assertEqual(len(get_apple_music_chart(5, timeout=12)), 5)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, CHART_URL)
        self.assertIsNone(request.get_header("Cookie"))
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(opened.call_args.kwargs["timeout"], 12)

    @patch("parser.apple_music.apple_music_parser.urlopen")
    def test_invalid_arguments(self, opened):
        for limit in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                get_apple_music_chart(limit)
        for timeout in (0, -1, float("nan"), float("inf"), "30"):
            with self.assertRaises(ValueError):
                get_apple_music_chart(timeout=timeout)
        opened.assert_not_called()

    @patch("parser.apple_music.apple_music_parser.urlopen")
    def test_network_errors(self, opened):
        for error in (HTTPError(CHART_URL, 403, "denied", {}, None), URLError("offline"), TimeoutError()):
            opened.side_effect = error
            with self.assertRaises(RuntimeError):
                get_apple_music_chart()


if __name__ == "__main__":
    unittest.main()
