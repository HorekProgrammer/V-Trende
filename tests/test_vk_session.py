"""Сессия VK из браузера: команда входа и использование сессии парсером."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from parser.vk import get_vk_chart
from parser.vk import login as vk_login
from parser.vk import vk_parser
from tests.test_vk import FIRST, REMAINING

SESSION = {
    "VK_USER_ID": "777",
    "VK_REMIXSID": "browser-sid",
    "VK_REMIXNSID": "browser-nsid",
    "VK_USER_AGENT": "Mozilla/5.0 Browser",
    "saved_at": "2026-10-25T10:00:00+00:00",
}


class SessionFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "vk_session.json"
        patcher = patch.object(vk_parser, "SESSION_FILE", self.file)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_chart(self, env):
        with patch("parser.vk.vk_parser._settings", return_value=env), \
                patch("parser.vk.vk_parser.urlopen") as opened:
            opened.return_value.__enter__.return_value.read.side_effect = [FIRST, REMAINING]
            result = get_vk_chart(3)
        return result, opened.call_args_list[0].args[0]

    def test_saved_session_is_used_when_env_is_empty(self):
        self.file.write_text(json.dumps(SESSION), encoding="utf-8")
        result, request = self.run_chart({"VK_REMIXSID": "", "VK_USER_ID": None})
        self.assertEqual(len(result), 3)
        self.assertEqual(request.get_header("Cookie"), "remixsid=browser-sid; remixnsid=browser-nsid")
        self.assertEqual(request.get_header("User-agent"), "Mozilla/5.0 Browser")
        self.assertIn("owner_id=777", request.data.decode())

    def test_env_values_override_saved_session(self):
        self.file.write_text(json.dumps(SESSION), encoding="utf-8")
        _, request = self.run_chart({"VK_REMIXSID": "env-sid"})
        self.assertEqual(request.get_header("Cookie"), "remixsid=env-sid; remixnsid=browser-nsid")

    def test_without_session_and_env_hint_to_login(self):
        with patch("parser.vk.vk_parser._settings", return_value={}), \
                patch("parser.vk.vk_parser.urlopen") as opened:
            with self.assertRaisesRegex(ValueError, "parser.vk.login"):
                get_vk_chart()
        opened.assert_not_called()

    def test_corrupted_session_file(self):
        self.file.write_text("{не json", encoding="utf-8")
        with patch("parser.vk.vk_parser._settings", return_value={}):
            with self.assertRaisesRegex(ValueError, "повреждён"):
                get_vk_chart()

    def test_save_session_round_trip(self):
        with patch.object(vk_login, "SESSION_FILE", self.file):
            vk_login.save_session(SESSION)
        self.assertEqual(vk_parser._saved_session()["VK_REMIXSID"], "browser-sid")
        self.assertNotIn("saved_at", vk_parser._saved_session())


class SessionFromBrowserTests(unittest.TestCase):
    COOKIES = [{"name": "remixsid", "value": "s"}, {"name": "remixnsid", "value": "n"},
               {"name": "remixlang", "value": "0"}]

    def test_builds_session(self):
        session = vk_login.session_from_browser(self.COOKIES, "UA", 42)
        self.assertEqual({k: session[k] for k in ("VK_USER_ID", "VK_REMIXSID", "VK_REMIXNSID", "VK_USER_AGENT")},
                         {"VK_USER_ID": "42", "VK_REMIXSID": "s", "VK_REMIXNSID": "n", "VK_USER_AGENT": "UA"})

    def test_rejects_incomplete_login(self):
        for cookies, user_id in ((self.COOKIES[:1], 42), (self.COOKIES, 0)):
            with self.subTest(), self.assertRaises(vk_login.LoginError):
                vk_login.session_from_browser(cookies, "UA", user_id)


class FakePage:
    def __init__(self, user_ids):
        self.user_ids = list(user_ids)

    def goto(self, *args, **kwargs):
        pass

    def evaluate(self, script):
        if "userAgent" in script:
            return "Mozilla/5.0 Playwright"
        return self.user_ids.pop(0) if len(self.user_ids) > 1 else self.user_ids[0]


class LoginFlowTests(unittest.TestCase):
    def run_login(self, cookie_rounds, user_ids, *, user_id=None, timeout=60):
        page = FakePage(user_ids)
        context = MagicMock()
        context.pages = [page]
        rounds = list(cookie_rounds)
        context.cookies.side_effect = lambda url: rounds.pop(0) if len(rounds) > 1 else rounds[0]
        playwright = MagicMock()
        playwright.chromium.launch_persistent_context.return_value = context
        manager = MagicMock()
        manager.__enter__.return_value = playwright
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(vk_login, "PROFILE_DIR", Path(tmp) / "profile"), \
                patch("playwright.sync_api.sync_playwright", return_value=manager), \
                patch.object(vk_login, "sleep"):
            session = vk_login.login(timeout, user_id, log=lambda message: None)
        options = playwright.chromium.launch_persistent_context.call_args
        self.assertFalse(options.kwargs["headless"])
        context.close.assert_called_once()
        return session

    def test_waits_until_user_logs_in(self):
        logged_out = [{"name": "remixlang", "value": "0"}]
        logged_in = SessionFromBrowserTests.COOKIES
        session = self.run_login([logged_out, logged_out, logged_in], [None, 12345])
        self.assertEqual(session["VK_USER_ID"], "12345")
        self.assertEqual(session["VK_USER_AGENT"], "Mozilla/5.0 Playwright")

    def test_explicit_user_id(self):
        session = self.run_login([SessionFromBrowserTests.COOKIES], [None], user_id=99)
        self.assertEqual(session["VK_USER_ID"], "99")

    def test_closed_window(self):
        context = MagicMock()
        context.pages = []
        playwright = MagicMock()
        playwright.chromium.launch_persistent_context.return_value = context
        manager = MagicMock()
        manager.__enter__.return_value = playwright
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(vk_login, "PROFILE_DIR", Path(tmp) / "profile"), \
                patch("playwright.sync_api.sync_playwright", return_value=manager):
            with self.assertRaisesRegex(vk_login.LoginError, "закрыто"):
                vk_login.login(60, log=lambda message: None)


if __name__ == "__main__":
    unittest.main()
