import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from parser.wordstat.wordstat_parser import TABLE_URL, get_wordstat_count, _NoRedirect


class WebTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / ".env"
        self.path.write_text("WORDSTAT_SESSION_ID='fake-session'\n", encoding="utf-8-sig")
        environment = patch.dict("os.environ", {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        location = patch("parser.wordstat.wordstat_parser.ENV_FILE", self.path)
        location.start()
        self.addCleanup(location.stop)
        transport = patch("parser.wordstat.wordstat_parser.build_opener")
        self.build = transport.start()
        self.addCleanup(transport.stop)
        self.response = self.build.return_value.open.return_value.__enter__.return_value

    def test_count_and_filters(self):
        self.response.read.return_value = b'{"table":{"isQueryInvalid":false},"totalValue":42}'
        self.assertEqual(get_wordstat_count("new phrase"), 42)
        request = self.build.return_value.open.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, TABLE_URL)
        self.assertEqual(body["filters"], {"region": "225", "tableType": "popular"})
        self.assertEqual(body["searchValue"], "new phrase")
        self.assertNotIn("page", body)
        self.assertEqual(request.get_header("Cookie"), "Session_id=fake-session")
        self.assertEqual(body["dbname"], "rus")
        self.assertEqual(body["currentDevice"], "desktop,phone,tablet")

    def test_environment_overrides_file(self):
        self.response.read.return_value = b'{"table":{},"totalValue":42}'
        with patch.dict("os.environ", {"WORDSTAT_SESSION_ID": "env-session"}):
            get_wordstat_count("test")
        request = self.build.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("Cookie"), "Session_id=env-session")

    def test_invalid_session_never_sent(self):
        for value in ("", "bad\nheader", "one; other=two", "bad cookie", '"bad"'):
            with patch.dict("os.environ", {"WORDSTAT_SESSION_ID": value}):
                with self.assertRaises(ValueError):
                    get_wordstat_count("test")
        self.path.unlink()
        with self.assertRaises(ValueError):
            get_wordstat_count("test")
        self.build.assert_not_called()

    def test_response_validation(self):
        for data in (b'<html>login</html>', b'{}', b'{"table":{},"totalValue":true}',
                     b'{"table":{},"totalValue":-1}'):
            self.response.read.return_value = data
            with self.assertRaises(RuntimeError):
                get_wordstat_count("test")
        self.response.read.return_value = b'{"table":{},"totalValue":0}'
        self.assertEqual(get_wordstat_count("test"), 0)

    def test_no_redirect(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_invalid_phrase(self):
        for phrase in (None, " ", "x" * 401):
            with self.assertRaises(ValueError):
                get_wordstat_count(phrase)
        self.build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
