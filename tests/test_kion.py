import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from parser.kion import get_kion_chart, parse_chart_html
from parser.kion.kion_parser import CHART_API_URL


def tracks(count=100):
    return [
        {
            "title": f"Трек {position}",
            "artists": [{"name": "Первый"}, {"name": "Второй"}],
        }
        for position in range(1, count + 1)
    ]


def page(items, track_count=None, title="Настоящий чарт"):
    playlist = {
        "title": title,
        "trackCount": len(items) if track_count is None else track_count,
        "tracks": items,
    }
    data = {"props": {"pageProps": {"playlist": playlist}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + "</script>"


class KionTests(unittest.TestCase):
    def test_parses_complete_chart(self):
        result = parse_chart_html(page(tracks()))
        self.assertEqual(len(result), 100)
        self.assertEqual(result[0], {
            "position": 1,
            "title": "Трек 1",
            "artists": ["Первый", "Второй"],
        })
        self.assertEqual(result[-1]["position"], 100)

    def test_rejects_missing_invalid_or_incomplete_data(self):
        cases = [
            "<html></html>",
            '<script id="__NEXT_DATA__">bad</script>',
            '<script id="__NEXT_DATA__">{}</script>',
            page(tracks(99)),
            page(tracks(), track_count=99),
            page(tracks(), title="Другой плейлист"),
        ]
        for html in cases:
            with self.subTest(size=len(html)), self.assertRaises(RuntimeError):
                parse_chart_html(html)

    def test_rejects_invalid_track(self):
        for field, value in (("title", ""), ("title", None), ("artists", []), ("artists", None)):
            items = tracks()
            items[5][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                parse_chart_html(page(items))

    @patch("parser.kion.kion_parser.urlopen")
    def test_fetch_without_auth_and_limit(self, open_url):
        api_tracks = [{"track": track} for track in tracks()]
        payload = {"result": {
            "title": "Настоящий чарт",
            "trackCount": 100,
            "tracks": api_tracks,
        }}
        response = open_url.return_value.__enter__.return_value
        response.read.return_value = json.dumps(payload).encode()
        self.assertEqual(len(get_kion_chart(5, timeout=12)), 5)
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, CHART_API_URL)
        self.assertIsNone(request.get_header("Cookie"))
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(open_url.call_args.kwargs["timeout"], 12)

    @patch("parser.kion.kion_parser.urlopen")
    def test_invalid_arguments(self, open_url):
        for limit in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                get_kion_chart(limit)
        for timeout in (0, -1, float("nan"), float("inf"), "30"):
            with self.assertRaises(ValueError):
                get_kion_chart(timeout=timeout)
        open_url.assert_not_called()

    @patch("parser.kion.kion_parser.urlopen")
    def test_network_errors(self, open_url):
        errors = (
            HTTPError(CHART_API_URL, 403, "denied", {}, None),
            URLError("offline"),
            TimeoutError(),
        )
        for error in errors:
            open_url.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(RuntimeError):
                get_kion_chart()


if __name__ == "__main__":
    unittest.main()
