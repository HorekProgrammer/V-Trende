import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from parser.vk import get_vk_chart, parse_chart_responses
from parser.vk.vk_parser import CHART_URL


def track(number):
    item = [0] * 32
    item[3] = f"Трек {number} &amp; Remix"
    item[4] = "Первый, Второй &amp; Co"
    return item


def response(start, count, has_more, next_offset=""):
    playlist = {
        "title": "Чарт VK\u00a0Музыки",
        "list": [track(i) for i in range(start, start + count)],
        "hasMore": has_more,
        "nextOffset": next_offset,
        "blockId": "chart-section",
    }
    return json.dumps({"payload": [0, ["", {"playlist": playlist}]]}, ensure_ascii=False).encode("cp1251")


FIRST = response(1, 18, True, "next")
REMAINING = response(19, 82, False)


class VkTests(unittest.TestCase):
    def test_parses_complete_chart(self):
        result = parse_chart_responses(FIRST, REMAINING)
        self.assertEqual(len(result), 100)
        self.assertEqual(result[0], {
            "position": 1,
            "title": "Трек 1 & Remix",
            "artists": ["Первый", "Второй & Co"],
        })
        self.assertEqual(result[-1]["position"], 100)

    def test_rejects_invalid_or_incomplete_response(self):
        cases = [
            (b"not json", REMAINING),
            (response(1, 17, True, "next"), REMAINING),
            (FIRST, response(19, 81, False)),
            (FIRST, response(19, 82, True)),
        ]
        for first, remaining in cases:
            with self.subTest(), self.assertRaises(RuntimeError):
                parse_chart_responses(first, remaining)

    def test_rejects_invalid_track(self):
        body = json.loads(FIRST.decode("cp1251"))
        body["payload"][1][1]["playlist"]["list"][0][3] = ""
        broken = json.dumps(body, ensure_ascii=False).encode("cp1251")
        with self.assertRaises(RuntimeError):
            parse_chart_responses(broken, REMAINING)

    @patch("parser.vk.vk_parser._settings")
    @patch("parser.vk.vk_parser.urlopen")
    def test_requests_use_only_required_cookies(self, opened, settings):
        settings.return_value = {
            "VK_REMIXSID": "session-value",
            "VK_REMIXNSID": "network-session-value",
            "VK_USER_ID": "123",
            "VK_USER_AGENT": "Mozilla/5.0 Test",
        }
        opened.return_value.__enter__.return_value.read.side_effect = [FIRST, REMAINING]
        self.assertEqual(len(get_vk_chart(5)), 5)
        self.assertEqual(opened.call_count, 2)
        first_request = opened.call_args_list[0].args[0]
        self.assertEqual(first_request.get_header("Cookie"), "remixsid=session-value; remixnsid=network-session-value")
        self.assertNotIn("httoken", first_request.get_header("Cookie"))

    @patch("parser.vk.vk_parser._settings")
    @patch("parser.vk.vk_parser.urlopen")
    def test_invalid_configuration_and_arguments(self, opened, settings):
        settings.return_value = {}
        for limit in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                get_vk_chart(limit)
        for timeout in (0, -1, float("nan"), float("inf"), "30"):
            with self.assertRaises(ValueError):
                get_vk_chart(timeout=timeout)
        with self.assertRaises(ValueError):
            get_vk_chart()
        opened.assert_not_called()

    @patch("parser.vk.vk_parser._settings")
    @patch("parser.vk.vk_parser.urlopen")
    def test_network_errors(self, opened, settings):
        settings.return_value = {
            "VK_REMIXSID": "a",
            "VK_REMIXNSID": "b",
            "VK_USER_ID": "123",
            "VK_USER_AGENT": "Mozilla/5.0 Test",
        }
        for error in (HTTPError(CHART_URL, 403, "denied", {}, None), URLError("offline"), TimeoutError()):
            opened.side_effect = error
            with self.assertRaises(RuntimeError):
                get_vk_chart()


if __name__ == "__main__":
    unittest.main()
