"""Загрузка через настоящий браузер (parser/common/browser.py).

Нужен установленный Chromium (python -m playwright install chromium);
без него тесты пропускаются — например, в GitHub Actions.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from parser.common import browser
from parser.common.browser import BrowserFetchError, fetch_html
from parser.zvuk import parse_chart_html
from tests.test_zvuk import tracks

FULL = json.dumps({"props": {"pageProps": {"hydrationData": {"trackList": {"tracks": tracks()}}}}})


def _browser_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            playwright.chromium.launch(channel="chromium").close()
        return True
    except Exception:  # noqa: BLE001 — нет Playwright или Chromium
        return False


@unittest.skipUnless(_browser_available(), "Chromium не установлен: тесты с браузером пропущены")
class RealBrowserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        patcher = patch.object(browser, "BROWSER_DIR", self.dir / "profiles")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def fetch(self, html, timeout=10):
        page = self.dir / "page.html"
        page.write_text(html, encoding="utf-8")
        return fetch_html("test", page.as_uri(), wait_selector="script#__NEXT_DATA__", timeout=timeout)

    def test_waits_until_chart_data_is_complete(self):
        # Регрессия: после проверки доступа Звука данные догружались, а страница
        # читалась сразу при появлении элемента — JSON оказывался обрезанным.
        partial = FULL[: len(FULL) // 2].replace("</", "<\\/")
        html = (
            f"<html><body><script id='__NEXT_DATA__' type='application/json'>{partial}</script>"
            f"<script>setTimeout(() => {{ document.getElementById('__NEXT_DATA__').textContent = "
            f"{json.dumps(FULL)}; }}, 800)</script></body></html>"
        )
        self.assertEqual(len(parse_chart_html(self.fetch(html))), 100)

    def test_follows_redirect_after_access_check(self):
        target = self.dir / "chart.html"
        target.write_text(f"<html><body><script id='__NEXT_DATA__' type='application/json'>{FULL}"
                          "</script></body></html>", encoding="utf-8")
        html = f"<html><body>Проверка…<script>setTimeout(() => location.href = {json.dumps(target.as_uri())}, 400)" \
               "</script></body></html>"
        self.assertEqual(len(parse_chart_html(self.fetch(html))), 100)

    def test_missing_data_times_out(self):
        with self.assertRaisesRegex(BrowserFetchError, "не загрузилась"):
            self.fetch("<html><body>капча</body></html>", timeout=1)


if __name__ == "__main__":
    unittest.main()
