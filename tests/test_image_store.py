import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import image_store


JPEG = b"\xff\xd8\xff" + b"image-data"


class Response:
    def __init__(self, data=JPEG, url="https://images.example/cover"):
        self.data = data
        self.url = url
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, _limit):
        return self.data


class ImageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.cover_dir = patch.object(image_store, "COVER_DIR", self.directory)
        self.cover_dir.start()
        self.addCleanup(self.cover_dir.stop)

    @patch.object(image_store, "urlopen", return_value=Response())
    def test_downloads_once_and_returns_local_url(self, opened):
        first = image_store.localize_image("https://images.example/cover")
        second = image_store.localize_image("https://images.example/cover")
        self.assertTrue(first.startswith("/media/covers/"))
        self.assertEqual(first, second)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(list(self.directory.iterdir())[0].read_bytes(), JPEG)

    @patch.object(image_store, "urlopen", return_value=Response(b"not-an-image"))
    def test_rejects_non_image_response(self, _opened):
        with self.assertRaises(image_store.ImageDownloadError):
            image_store.localize_image("https://images.example/file")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_rejects_insecure_and_preserves_local_urls(self):
        with self.assertRaises(image_store.ImageDownloadError):
            image_store.localize_image("http://images.example/cover.jpg")
        local = "/media/covers/already.jpg"
        self.assertEqual(image_store.localize_image(local), local)

    @patch.object(image_store, "localize_image")
    def test_payload_uses_local_urls_and_omits_failed_images(self, localize):
        localize.side_effect = ["/media/covers/one.jpg", image_store.ImageDownloadError("down")]
        payload = {"entries": [
            {"cover_url": "https://images.example/one"},
            {"cover_url": "https://images.example/two"},
            {"cover_url": None},
        ]}
        self.assertEqual(image_store.localize_payload_covers(payload), (1, 1))
        self.assertEqual(payload["entries"][0]["cover_url"], "/media/covers/one.jpg")
        self.assertIsNone(payload["entries"][1]["cover_url"])
