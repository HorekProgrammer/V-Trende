import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from parser.twitch.channel_classifier import classify_channels
from parser.twitch.twitch_parser import _fetch_personal_candidates


def channel(position: int) -> dict:
    return {
        "position": position,
        "channel": f"Channel {position}",
        "total_followers": position * 100,
        "_slug": f"channel_{position}",
    }


class TwitchClassifierTests(unittest.TestCase):
    @patch("parser.twitch.channel_classifier._settings")
    @patch("parser.twitch.channel_classifier._post_json")
    def test_classifies_channel_and_reuses_persistent_cache(self, post_json, settings):
        settings.return_value = {
            "DEEPSEEK_API": "secret",
            "DEEPSEEK_MODEL": "deepseek-flash",
            "TWITCH_CLASSIFICATION_BATCH_SIZE": "10",
        }
        post_json.side_effect = [
            {
                "results": [{
                    "title": "Channel profile",
                    "url": "https://example.com/channel",
                    "snippet": "Personal streamer",
                    "summary": "A personal channel",
                    "authority": 2,
                }]
            },
            {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "results": [{
                                "slug": "channel_1",
                                "owner_kind": "individual",
                                "type": "person",
                                "confidence": 0.94,
                                "reason": "Personal channel.",
                                "evidence_urls": ["https://example.com/channel"],
                            }]
                        })
                    }
                }]
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "types.json"
            first = classify_channels([channel(1)], cache_path=cache)
            post_json.reset_mock()
            second = classify_channels([channel(1)], cache_path=cache)

        self.assertEqual(first["channel_1"]["type"], "person")
        self.assertEqual(second["channel_1"]["confidence"], 0.94)
        post_json.assert_not_called()

    @patch("parser.twitch.channel_classifier._settings")
    def test_requires_api_key_when_channel_is_not_cached(self, settings):
        settings.return_value = {
            "TWITCH_CLASSIFICATION_BATCH_SIZE": "10",
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "DEEPSEEK_API"):
                classify_channels([channel(1)], cache_path=Path(tmp) / "types.json")

    @patch("parser.twitch.channel_classifier._settings", return_value={})
    def test_reuses_studio_classification_without_expiration_or_api_key(self, _settings):
        stored = {
            "type": "studio",
            "owner_kind": "organization",
            "confidence": 0.91,
            "reason": "Official tournament channel.",
            "evidence_urls": [],
            "checked_at": "2020-01-01T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "types.json"
            cache.write_text(
                json.dumps({"version": 1, "channels": {"channel_1": stored}}),
                encoding="utf-8",
            )
            result = classify_channels([channel(1)], cache_path=cache)

        self.assertEqual(result["channel_1"]["type"], "studio")

    @patch("parser.twitch.twitch_parser.classify_channels")
    @patch("parser.twitch.twitch_parser._fetch_candidates")
    def test_filters_studios_from_complete_candidate_set(self, fetch_candidates, classify):
        fetch_candidates.return_value = [channel(position) for position in range(1, 4)]

        def result(channels, **_kwargs):
            return {
                item["_slug"]: {
                    "type": "studio" if item["position"] == 1 else "person",
                    "confidence": 0.95,
                }
                for item in channels
            }

        classify.side_effect = result
        ranking = _fetch_personal_candidates(3, 30)

        self.assertEqual([item["_slug"] for item in ranking], ["channel_2", "channel_3"])
        fetch_candidates.assert_called_once_with(3, 30)


if __name__ == "__main__":
    unittest.main()
