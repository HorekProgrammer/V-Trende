import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from urllib.error import HTTPError, URLError

from parser.twitch import (
    get_russian_twitch_ranking,
    parse_ranking_html,
    parse_weekly_stats_html,
)
from parser.twitch.twitch_parser import (
    RANKING_URL,
    _channel_bootstrap,
    _fetch_candidates,
    _fetch_ranking_page,
    parse_ranking_markdown,
    parse_weekly_stats_markdown,
)


def page(start=1, count=50):
    rows = []
    for position in range(start, start + count):
        rows.append(f"""
        <tr>
          <td>#{position}</td><td><img src="https://static-cdn.jtvnw.net/jtv_user_pictures/ch{position}-profile_image-70x70.png"></td>
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


def weekly_markdown():
    return """68.1

Hours streamed

36,889

Average viewers

93,943

Peak viewers

2.51M

Hours watched

-166

Followers gained

-65.96

Followers / hour

#183 2,304,573

Total followers
"""


def response(html):
    context = MagicMock()
    context.__enter__.return_value.read.return_value = html.encode()
    return context


def classify_as_people(channels, **_kwargs):
    return {
        channel["_slug"].lower(): {
            "type": "person",
            "confidence": 1.0,
            "reason": "test",
            "evidence_urls": [],
            "checked_at": "2026-01-01T00:00:00Z",
        }
        for channel in channels
    }


class TwitchTests(unittest.TestCase):
    @patch("parser.twitch.twitch_parser._fetch_ranking")
    def test_adds_evelone_to_full_candidate_collection(self, fetch_ranking):
        fetch_ranking.return_value = [
            {"position": 1, "channel": "One", "total_followers": 10, "_slug": "one"}
        ]
        result = _fetch_candidates(150, 30)
        self.assertEqual(result[-1]["_slug"], "evelone2004")
        self.assertEqual(result[-1]["position"], 2)

    def test_parses_ranking_channel_and_total_followers(self):
        result = parse_ranking_html(page())
        self.assertEqual(len(result), 50)
        self.assertEqual(result[0], {"channel": "Канал 1", "total_followers": 3000})
        self.assertNotIn("position", result[0])

    def test_parses_ranking_from_deepseek_markdown(self):
        markdown = "\n".join(
            f"#{position} | Channel_{position} | {position * 100} | 10 hours |"
            for position in range(1, 51)
        )
        result = parse_ranking_markdown(markdown, expected_start=1)
        self.assertEqual(len(result), 50)
        self.assertEqual(result[0]["_slug"], "channel_1")
        self.assertEqual(result[-1]["position"], 50)

    @patch("parser.twitch.twitch_parser.urlopen")
    @patch("parser.twitch.twitch_parser.build_opener")
    def test_uses_configured_proxy_for_twitchtracker(self, build, direct_open):
        build.return_value.open.return_value = response(page())
        with patch.dict(os.environ, {"TWITCHTRACKER_PROXY": "http://user:pass@proxy:8000"}):
            result = _fetch_ranking_page(1, 30)

        self.assertEqual(len(result), 50)
        build.return_value.open.assert_called_once()
        direct_open.assert_not_called()

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

    def test_parses_weekly_statistics_from_deepseek_markdown(self):
        self.assertEqual(parse_weekly_stats_markdown(weekly_markdown()), {
            "hours_streamed": 68.1,
            "average_viewers": 36889,
            "peak_viewers": 93943,
            "hours_watched": 2_510_000,
            "followers_gained": -166,
            "followers_per_hour": -65.96,
            "total_followers": 2_304_573,
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
    @patch("parser.twitch.twitch_parser.classify_channels", side_effect=classify_as_people)
    @patch("parser.twitch.twitch_parser.sleep")
    @patch("parser.twitch.twitch_parser.urlopen")
    def test_fetches_three_pages_and_each_channel_in_original_order(
        self, open_url, pause, _classify, fetch_stats
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
        self.assertEqual(result[-1]["position"], 125)
        self.assertEqual(result[-1]["slug"], "channel_125")
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

    @patch("parser.twitch.twitch_parser._fetch_personal_candidates")
    @patch("parser.twitch.twitch_parser._fetch_channel_stats")
    @patch("parser.twitch.twitch_parser.sleep")
    def test_cached_collection_resumes_after_channel_failure(self, _pause, fetch_stats, ranking):
        ranking.return_value = [
            {"position": 1, "channel": "One", "total_followers": 10, "_slug": "one"},
            {"position": 2, "channel": "Two", "total_followers": 20, "_slug": "two"},
        ]
        one = {
            "hours_streamed": 1.0, "average_viewers": 2, "peak_viewers": 3,
            "hours_watched": 4, "followers_gained": 5, "followers_per_hour": 6.0,
        }
        two = {**one, "hours_watched": 40}
        fetch_stats.side_effect = [one, RuntimeError("HTTP 429")]

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "week.json"
            with self.assertRaisesRegex(RuntimeError, "429"):
                get_russian_twitch_ranking(2, cache_path=cache)

            fetch_stats.reset_mock(side_effect=True)
            fetch_stats.return_value = two
            result = get_russian_twitch_ranking(2, cache_path=cache)

        fetch_stats.assert_called_once_with("two", 30)
        self.assertEqual(result[0]["hours_watched"], 4)
        self.assertEqual(result[1]["hours_watched"], 40)

    @patch("parser.twitch.twitch_parser._fetch_personal_candidates")
    @patch("parser.twitch.twitch_parser._fetch_channel_stats")
    @patch("parser.twitch.twitch_parser.sleep")
    def test_keeps_inactive_channels_for_wordstat_scoring(self, _pause, fetch_stats, candidates):
        candidates.return_value = [
            {"position": 1, "channel": "Inactive", "total_followers": 10, "_slug": "inactive"},
            {"position": 2, "channel": "Active", "total_followers": 20, "_slug": "active"},
        ]
        base = {
            "average_viewers": 2, "peak_viewers": 3, "hours_watched": 4,
            "followers_gained": 5, "followers_per_hour": 6.0,
        }
        fetch_stats.side_effect = [
            {**base, "hours_streamed": 0.0},
            {**base, "hours_streamed": 2.0},
        ]

        result = get_russian_twitch_ranking(2)

        self.assertEqual(len(result), 2)
        self.assertEqual([item["slug"] for item in result], ["inactive", "active"])
        self.assertEqual([item["position"] for item in result], [1, 2])
        self.assertEqual(result[0]["hours_streamed"], 0.0)

    @patch("parser.twitch.twitch_parser._fetch_channel_stats")
    @patch("parser.twitch.twitch_parser.classify_channels", side_effect=classify_as_people)
    @patch("parser.twitch.twitch_parser.sleep")
    @patch("parser.twitch.twitch_parser.urlopen")
    def test_retries_rate_limit_response(self, open_url, pause, _classify, fetch_stats):
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

    @patch("parser.twitch.twitch_parser.fetch_page_markdown", return_value=weekly_markdown())
    @patch("parser.twitch.twitch_parser.urlopen")
    def test_uses_deepseek_fetch_when_profile_is_blocked(self, open_url, fetch_markdown):
        open_url.side_effect = HTTPError("https://twitchtracker.com/strogo", 403, "denied", {}, None)
        from parser.twitch.twitch_parser import _fetch_channel_stats

        result = _fetch_channel_stats("strogo", 9)

        self.assertEqual(result["total_followers"], 2_304_573)
        fetch_markdown.assert_called_once_with("https://twitchtracker.com/strogo", timeout=9)

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

    @patch("parser.twitch.twitch_parser.fetch_page_markdown", side_effect=RuntimeError("fallback failed"))
    @patch("parser.twitch.twitch_parser.urlopen")
    def test_network_errors(self, open_url, _fetch_markdown):
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
