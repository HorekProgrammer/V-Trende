import json
import unittest
from unittest.mock import patch

from parser.common import steam_details
from parser.common.steam_details import fill_missing_covers, header_image_from_details

HEADER = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/553850/abc123/header.jpg?t=1"
FALLBACK = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/553850/header.jpg"


def details(app_id, header=HEADER, success=True):
    return {str(app_id): {"success": success, "data": {"header_image": header}}}


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class HeaderImageTests(unittest.TestCase):
    def test_header_image(self):
        self.assertEqual(header_image_from_details(details(553850), 553850), HEADER)

    def test_missing_or_foreign_image(self):
        for payload in (None, {}, details(553850, success=False), details(553850, header=None),
                        details(553850, header="https://evil.example/x.jpg"), {"553850": {"success": True, "data": []}}):
            with self.subTest(payload=payload):
                self.assertIsNone(header_image_from_details(payload, 553850))


class FillMissingCoversTests(unittest.TestCase):
    @patch.object(steam_details, "sleep")
    @patch.object(steam_details, "urlopen")
    def test_only_items_without_cover_are_requested(self, opened, _sleep):
        opened.return_value = Response(details(553850))
        items = [{"steam_app_id": 730, "cover_url": "https://x/cs2.jpg"}, {"steam_app_id": 553850, "cover_url": None}]
        self.assertEqual(fill_missing_covers(items), 1)
        self.assertEqual(items[1]["cover_url"], HEADER)
        self.assertEqual(items[0]["cover_url"], "https://x/cs2.jpg")
        self.assertEqual(opened.call_count, 1)
        url = opened.call_args.args[0].full_url
        self.assertIn("appids=553850", url)
        self.assertIn("cc=us", url)

    @patch.object(steam_details, "sleep")
    @patch.object(steam_details, "urlopen", side_effect=OSError("network down"))
    def test_network_error_falls_back_to_standard_header(self, _opened, _sleep):
        items = [{"steam_app_id": 553850, "cover_url": None}]
        self.assertEqual(fill_missing_covers(items), 0)
        self.assertEqual(items[0]["cover_url"], FALLBACK)

    @patch.object(steam_details, "sleep")
    @patch.object(steam_details, "urlopen")
    def test_request_limit(self, opened, _sleep):
        opened.return_value = Response({})
        items = [{"steam_app_id": i, "cover_url": None} for i in range(1, 100)]
        fill_missing_covers(items)
        self.assertEqual(opened.call_count, steam_details.MAX_REQUESTS)
        self.assertTrue(all(item["cover_url"] for item in items))


if __name__ == "__main__":
    unittest.main()
