"""Звук: загрузка через браузер при проверке доступа; Shazam: причина ошибки."""

import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from parser.shazam import get_shazam_chart
from parser.zvuk import get_zvuk_chart
from parser.zvuk.zvuk_parser import CHART_URL
from tests.test_zvuk import page, tracks

CHART_HTML = page(tracks())
CHALLENGE_HTML = "<html><body>Servicepipe: проверка браузера</body></html>"


def http_response(html):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = html.encode()
    return response


@patch("parser.zvuk.zvuk_parser._fetch_with_browser", return_value=CHART_HTML)
@patch("parser.zvuk.zvuk_parser.urlopen")
class ZvukBrowserFallbackTests(unittest.TestCase):
    def test_plain_request_is_enough_without_browser(self, opened, browser):
        opened.return_value = http_response(CHART_HTML)
        self.assertEqual(len(get_zvuk_chart(5, browser_fallback=True)), 5)
        browser.assert_not_called()

    def test_challenge_page_opens_browser(self, opened, browser):
        opened.return_value = http_response(CHALLENGE_HTML)
        self.assertEqual(len(get_zvuk_chart(browser_fallback=True)), 100)
        browser.assert_called_once_with(30)

    def test_blocked_status_opens_browser(self, opened, browser):
        opened.side_effect = HTTPError(CHART_URL, 403, "Forbidden", {}, None)
        self.assertEqual(len(get_zvuk_chart(3, browser_fallback=True)), 3)
        browser.assert_called_once()

    def test_without_fallback_behaviour_is_unchanged(self, opened, browser):
        opened.return_value = http_response(CHALLENGE_HTML)
        with self.assertRaisesRegex(RuntimeError, "Servicepipe"):
            get_zvuk_chart()
        opened.side_effect = HTTPError(CHART_URL, 403, "Forbidden", {}, None)
        with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
            get_zvuk_chart()
        browser.assert_not_called()

    def test_other_http_errors_do_not_open_browser(self, opened, browser):
        opened.side_effect = HTTPError(CHART_URL, 404, "Not Found", {}, None)
        with self.assertRaisesRegex(RuntimeError, "HTTP 404"):
            get_zvuk_chart(browser_fallback=True)
        browser.assert_not_called()

    def test_headed_goes_straight_to_visible_browser(self, opened, browser):
        self.assertEqual(len(get_zvuk_chart(headed=True)), 100)
        opened.assert_not_called()
        browser.assert_called_once_with(30)


class ZvukDumpHtmlTests(unittest.TestCase):
    def test_page_is_saved_even_if_it_cannot_be_parsed(self):
        import io
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from pathlib import Path
        from parser.zvuk import __main__ as zvuk_main
        broken = page(tracks()[:40])  # браузер получил не тот формат страницы
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "zvuk_debug.html"
            with patch("parser.zvuk.__main__.fetch_chart_html", return_value=broken), \
                    patch("sys.argv", ["prog", "--headed", "--dump-html", str(target)]), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err, \
                    self.assertRaises(SystemExit) as exit_:
                zvuk_main.main()
            self.assertEqual(exit_.exception.code, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), broken)
            self.assertIn("сохранена", err.getvalue())


class ShazamErrorDetailTests(unittest.TestCase):
    def test_real_cause_is_shown(self):
        from playwright.sync_api import Error
        manager = MagicMock()
        manager.__enter__.side_effect = Error("net::ERR_CONNECTION_RESET at https://www.shazam.com/\nCall log: ...")
        with patch("playwright.sync_api.sync_playwright", return_value=manager):
            with self.assertRaisesRegex(RuntimeError, "ERR_CONNECTION_RESET") as raised:
                get_shazam_chart()
        self.assertNotIn("Call log", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
