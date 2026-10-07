import base64
import json
import unittest
from unittest.mock import MagicMock, call, patch
from urllib.error import HTTPError, URLError

from parser.twitch import (
    get_russian_twitch_ranking,
    parse_ranking_html,
    parse_weekly_stats_html,
)
from parser.twitch.twitch_parser import RANKING_URL, _channel_bootstrap


def page(start=1, count=50):
    rows = []
    for position in range(start, start + count):
        rows.append(f"""
        <tr>
          <td>#{position}</td><td><img></td>
          <td><a href="/channel_{position}">Канал {position}</a></td>
          <td>{position * 10}</td><td>{position + 0.5}<br><small>hours</small></td>
          <td>{position * 100}</td><td>{position * 1000}</td><td>{position + 20}</td>
          <td>+{position * 2}</td><td>{position * 3000}</td><td>{position * 4000}</td>
        </tr>
        """)
    return '<table id="channels"><tbody>' + "".join(rows) + "</tbody></table>"


def ecs(payloads):
    values = list(payloads.values()) + [list(payloads)]
    encoded = []
    for value in values:
        data = json.dumps(value, separators=(",", ":")).encode()
        encoded.append(base64.b64encode(data).decode().rstrip("=").replace("W", "#"))
    return f'<meta id="ecs" content="{"!".join(encoded)}">'


def weekly_html(**overrides):
    current = {
        "duration": 3597,
        "avg_viewers": 35991,
        "max_viewers": 85828,
        "man_hours": 2157656,
        "followers": 19230,
        "followers_hour": 320.767,
    }
    current.update(overrides)
    return ecs({"performance": {"week": {"curr": current}}})


def response(html):
    context = MagicMock()
    context.__enter__.return_value.read.return_value = html.encode()
    return context


class TwitchTests(unittest.TestCase):
    def test_parses_ranking_channel_and_total_followers(self):
        result = parse_ranking_html(page())
        self.assertEqual(len(result), 50)
        self.assertEqual(result[0], {"channel": "Канал 1", "total_followers": 3000})
        self.assertNotIn("position", result[0])

    def test_rejects_missing_invalid_and_nonsequential_rows(self):
        cases = [
            "<html></html>",
            page(count=49).replace("#2", "#3", 1),
            page().replace("<td>3000</td>", "<td>bad</td>", 1),
            page().replace('href="/channel_1"', 'href="https://example.com/channel_1"', 1),
        ]
        for html in cases:
            with self.subTest(size=len(html)), self.assertRaises(RuntimeError):
                parse_ranking_html(html)

    def test_parses_weekly_statistics(self):
        self.assertEqual(parse_weekly_stats_html(weekly_html()), {
            "hours_streamed": 60.0,
            "average_viewers": 35991,
            "peak_viewers": 85828,
            "hours_watched": 2157656,
            "followers_gained": 19230,
            "followers_per_hour": 320.767,
        })

    def test_channel_without_streams_has_zero_weekly_statistics(self):
        empty_week = weekly_html(
            duration=None,
            avg_viewers=None,
            max_viewers=None,
            man_hours=None,
            followers=None,
            followers_hour=None,
        )
        self.assertEqual(parse_weekly_stats_html(empty_week), {
            "hours_streamed": 0.0,
            "average_viewers": 0,
            "peak_viewers": 0,
            "hours_watched": 0,
            "followers_gained": 0,
            "followers_per_hour": 0.0,
        })

    def test_rejects_invalid_weekly_statistics(self):
        cases = [
            "<html></html>",
            ecs({"performance": {}}),
            weekly_html(duration="3597"),
            weekly_html(duration=None),
        ]
        for html in cases:
            with self.subTest(html=html[:30]), self.assertRaises(RuntimeError):
                parse_weekly_stats_html(html)

    def test_extracts_channel_id_and_signed_fragments_url(self):
        url = "https://twitchtracker.com/strogo/fragments?expires=1&signature=abc"
        html = "<script>window.channel = { id: 233741947, name: 'strogo' }</script>" + ecs({
            "related": [], "fragments": url
        })
        self.assertEqual(_channel_bootstrap(html, "StRoGo"), (233741947, url))

    @patch("parser.twitch.twitch_parser._fetch_channel_stats")
    @patch("parser.twitch.twitch_parser.sleep")
    @patch("parser.twitch.twitch_parser.urlopen")
    def test_fetches_three_pages_and_each_channel_in_original_order(
        self, open_url, pause, fetch_stats
    ):
        open_url.side_effect = [response(page()), response(page(51)), response(page(101))]
        fetch_stats.side_effect = lambda slug, timeout: {
            "hours_streamed": int(slug.split("_")[1]),
            "average_viewers": 2,
            "peak_viewers": 3,
            "hours_watched": 4,
            "followers_gained": 5,
            "followers_per_hour": 6.0,
        }
        result = get_russian_twitch_ranking(125, timeout=12)
        self.assertEqual(len(result), 125)
        self.assertEqual(result[0]["channel"], "Канал 1")
        self.assertEqual(result[-1]["channel"], "Канал 125")
        self.assertEqual(result[-1]["hours_streamed"], 125)
        self.assertNotIn("position", result[-1])
        requests = [item.args[0] for item in open_url.call_args_list]
        self.assertEqual([request.full_url for request in requests], [
            RANKING_URL,
            f"{RANKING_URL}?page=2",
            f"{RANKING_URL}?page=3",
        ])
        self.assertTrue(all(request.get_header("Cookie") is None for request in requests))
        self.assertCountEqual(
            fetch_stats.call_args_list,
            [call(f"channel_{number}", 12) for number in range(1, 126)],
        )
        self.assertEqual(pause.call_count, 124)
        pause.assert_called_with(1.0)

    @patch("parser.twitch.twitch_parser._fetch_channel_stats")
    @patch("parser.twitch.twitch_parser.sleep")
    @patch("parser.twitch.twitch_parser.urlopen")
    def test_retries_rate_limit_response(self, open_url, pause, fetch_stats):
        open_url.side_effect = [
            HTTPError(RANKING_URL, 429, "rate limited", {}, None),
            response(page()),
        ]
        fetch_stats.return_value = {
            "hours_streamed": 1.0,
            "average_viewers": 2,
            "peak_viewers": 3,
            "hours_watched": 4,
            "followers_gained": 5,
            "followers_per_hour": 6.0,
        }

        self.assertEqual(len(get_russian_twitch_ranking(1)), 1)
        pause.assert_called_once_with(30)

    @patch("parser.twitch.twitch_parser.urlopen")
    def test_fetches_profile_and_fragments_without_cookies(self, open_url):
        url = "https://twitchtracker.com/strogo/fragments?expires=1&signature=abc"
        profile = "<script>window.channel={id:233741947}</script>" + ecs({"fragments": url})
        open_url.side_effect = [response(profile), response(weekly_html())]
        from parser.twitch.twitch_parser import _fetch_channel_stats

        result = _fetch_channel_stats("strogo", 9)
        self.assertEqual(result["average_viewers"], 35991)
        profile_request, fragments_request = [item.args[0] for item in open_url.call_args_list]
        self.assertEqual(profile_request.full_url, "https://twitchtracker.com/strogo")
        self.assertEqual(fragments_request.full_url, url)
        self.assertEqual(fragments_request.method, "POST")
        self.assertEqual(fragments_request.data, b"id=233741947")
        self.assertIsNone(profile_request.get_header("Cookie"))
        self.assertIsNone(fragments_request.get_header("Cookie"))

    @patch("parser.twitch.twitch_parser.urlopen")
    def test_rejects_incomplete_page(self, open_url):
        open_url.return_value = response(page(count=49))
        with self.assertRaisesRegex(RuntimeError, "не полностью"):
            get_russian_twitch_ranking()

    @patch("parser.twitch.twitch_parser.urlopen")
    def test_invalid_arguments_do_not_call_network(self, open_url):
        for limit in (0, 151, True, "10"):
            with self.assertRaises(ValueError):
                get_russian_twitch_ranking(limit)
        for timeout in (0, -1, float("nan"), float("inf"), "30"):
            with self.assertRaises(ValueError):
                get_russian_twitch_ranking(timeout=timeout)
        open_url.assert_not_called()

    @patch("parser.twitch.twitch_parser.urlopen")
    def test_network_errors(self, open_url):
        errors = (
            HTTPError(RANKING_URL, 403, "denied", {}, None),
            URLError("offline"),
            TimeoutError(),
        )
        for error in errors:
            open_url.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(RuntimeError):
                get_russian_twitch_ranking(1)


if __name__ == "__main__":
    unittest.main()
