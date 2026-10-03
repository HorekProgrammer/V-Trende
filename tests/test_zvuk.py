import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from parser.zvuk import get_zvuk_chart, parse_chart_html
from parser.zvuk.zvuk_parser import CHART_URL


def tracks():
    return [{"title": f"Песня {i} & <3", "artists": [{"name": "Первый"}, {"name": "Второй"}]} for i in range(100)]


def page(items):
    data = {"props": {"pageProps": {"hydrationData": {"trackList": {"tracks": items}}}}}
    return '<html><script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script></html>'


class ZvukTests(unittest.TestCase):
    def test_fields_order_and_multiple_artists(self):
        result = parse_chart_html(page(tracks()))
        self.assertEqual(len(result), 100)
        self.assertEqual(result[0], {"position": 1, "title": "Песня 0 & <3", "artists": ["Первый", "Второй"]})
        self.assertEqual([r["position"] for r in result], list(range(1, 101)))
        self.assertTrue(all(set(r) == {"position", "title", "artists"} for r in result))

    def test_missing_or_invalid_json(self):
        for html in ('<html>Servicepipe</html>', '<script id="__NEXT_DATA__">bad</script>', '<script id="__NEXT_DATA__">{}</script>'):
            with self.subTest(html=html), self.assertRaises(RuntimeError):
                parse_chart_html(html)

    def test_incomplete_chart(self):
        for items in ([], tracks()[:99], tracks() + tracks()[:1], {}):
            with self.assertRaises(RuntimeError):
                parse_chart_html(page(items))

    def test_invalid_track(self):
        for field, value in (("title", ""), ("title", None), ("artists", []), ("artists", None), ("artists", [{"name": ""}])):
            items = tracks()
            items[10][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                parse_chart_html(page(items))

    @patch("parser.zvuk.zvuk_parser.urlopen")
    def test_fetch_without_cookies_and_limit(self, opened):
        opened.return_value.__enter__.return_value.read.return_value = page(tracks()).encode()
        self.assertEqual(len(get_zvuk_chart(5)), 5)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, CHART_URL)
        self.assertIsNone(request.get_header("Cookie"))
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(opened.call_args.kwargs["timeout"], 30)

    @patch("parser.zvuk.zvuk_parser.urlopen")
    def test_invalid_arguments(self, opened):
        for limit in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                get_zvuk_chart(limit)
        for timeout in (0, -1, float("nan"), float("inf"), "30"):
            with self.assertRaises(ValueError):
                get_zvuk_chart(timeout=timeout)
        opened.assert_not_called()

    @patch("parser.zvuk.zvuk_parser.urlopen")
    def test_network_and_http_errors(self, opened):
        for error in (HTTPError(CHART_URL, 403, "denied", {}, None), URLError("offline"), TimeoutError()):
            opened.side_effect = error
            with self.assertRaises(RuntimeError):
                get_zvuk_chart()


if __name__ == "__main__":
    unittest.main()
