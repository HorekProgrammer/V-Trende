"""Регистрация и сессии: проверка данных, хэширование паролей, работа с базой.

Тесты с базой запускаются, только если задан TEST_DATABASE_URL
(схема public этой базы удаляется перед каждым тестом).
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend import auth
from database.db import settings

TEST_URL = (settings().get("TEST_DATABASE_URL") or "").strip()


class ValidationTests(unittest.TestCase):
    def test_valid_data(self):
        self.assertEqual(auth.validate_registration("  Mark@Mail.RU ", "password1"), {})

    def test_email_errors_match_frontend_messages(self):
        self.assertEqual(auth.validate_registration("", "password1"), {"email": "Введите email"})
        for bad in ("mark", "mark@mail", "ma rk@mail.ru", "a@b.c" + "x" * 260):
            with self.subTest(email=bad):
                self.assertEqual(auth.validate_registration(bad, "password1"), {"email": "Некорректный email"})

    def test_password_errors(self):
        self.assertEqual(auth.validate_registration("a@b.ru", ""), {"password": "Введите пароль"})
        self.assertEqual(auth.validate_registration("a@b.ru", "1234567"), {"password": "Минимум 8 символов"})
        self.assertEqual(auth.validate_registration("a@b.ru", "x" * 129), {"password": "Максимум 128 символов"})
        self.assertEqual(auth.validate_registration("a@b.ru", "x" * 128), {})

    def test_both_fields_reported_at_once(self):
        self.assertEqual(set(auth.validate_registration("bad", "short")), {"email", "password"})

    def test_email_is_normalized(self):
        self.assertEqual(auth.normalize_email("  Mark@Mail.RU "), "mark@mail.ru")


class PasswordHashTests(unittest.TestCase):
    def test_hash_is_salted_and_verifiable(self):
        first = auth.hash_password("пароль-123")
        second = auth.hash_password("пароль-123")
        self.assertNotEqual(first, second)              # своя соль у каждого хэша
        self.assertNotIn("пароль-123", first)
        self.assertTrue(first.startswith("scrypt$16384$8$1$"))
        self.assertTrue(auth.verify_password("пароль-123", first))
        self.assertFalse(auth.verify_password("пароль-124", first))

    def test_broken_hash_is_rejected_not_crashed(self):
        for stored in ("", "plain", "md5$1$2$3$4$5", "scrypt$x$8$1$AAAA$AAAA"):
            with self.subTest(stored=stored):
                self.assertFalse(auth.verify_password("password1", stored))

    def test_public_user_hides_hash(self):
        user = auth.public_user({"id": 1, "email": "a@b.ru", "password_hash": "secret",
                                 "created_at": datetime(2026, 11, 7, tzinfo=timezone.utc)})
        self.assertEqual(user, {"id": 1, "email": "a@b.ru", "createdAt": "2026-11-07T00:00:00+00:00"})


@unittest.skipUnless(TEST_URL, "TEST_DATABASE_URL не задан: тесты на PostgreSQL пропущены")
class AuthDatabaseTests(unittest.TestCase):
    def setUp(self):
        from database.db import connect
        from database.migrate import migrate
        self.conn = connect(TEST_URL)
        self.conn.execute("DROP SCHEMA public CASCADE")
        self.conn.execute("CREATE SCHEMA public")
        migrate(self.conn)

    def tearDown(self):
        self.conn.close()

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_register_creates_user_and_session(self):
        user, token = auth.register(self.conn, " Mark@Mail.RU ", "password1")
        self.assertEqual(user["email"], "mark@mail.ru")
        stored_hash = self.conn.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertTrue(auth.verify_password("password1", stored_hash))
        self.assertEqual(self.count("user_sessions"), 1)
        # В базе только хэш токена, не сам токен.
        self.assertNotEqual(self.conn.execute("SELECT token_hash FROM user_sessions").fetchone()[0], token)
        self.assertEqual(auth.session_user(self.conn, token)["id"], user["id"])

    def test_duplicate_email_ignores_case_and_spaces(self):
        auth.register(self.conn, "mark@mail.ru", "password1")
        with self.assertRaises(auth.EmailTaken):
            auth.register(self.conn, "  MARK@mail.RU", "password2")
        self.assertEqual(self.count("users"), 1)
        self.assertEqual(self.count("user_sessions"), 1)   # сессия неудачной попытки откатилась

    def test_failed_session_rolls_back_user(self):
        with patch.object(auth, "create_session", side_effect=RuntimeError("сбой")):
            with self.assertRaises(RuntimeError):
                auth.register(self.conn, "a@b.ru", "password1")
        self.assertEqual(self.count("users"), 0)

    def test_unknown_or_expired_session(self):
        user, _ = auth.register(self.conn, "a@b.ru", "password1")
        self.assertIsNone(auth.session_user(self.conn, None))
        self.assertIsNone(auth.session_user(self.conn, "неизвестный-токен"))
        self.assertIsNone(auth.session_user(self.conn, "x" * 500))
        old = datetime.now(timezone.utc) - auth.SESSION_TTL - timedelta(minutes=1)
        expired = auth.create_session(self.conn, user["id"], now=old)
        self.assertIsNone(auth.session_user(self.conn, expired))

    def test_deleting_user_deletes_sessions(self):
        user, token = auth.register(self.conn, "a@b.ru", "password1")
        self.conn.execute("DELETE FROM users WHERE id = %s", (user["id"],))
        self.assertEqual(self.count("user_sessions"), 0)
        self.assertIsNone(auth.session_user(self.conn, token))

    def test_database_rejects_blank_email(self):
        with self.assertRaises(Exception):
            self.conn.execute("INSERT INTO users (email, password_hash) VALUES ('  ', 'x')")


if __name__ == "__main__":
    unittest.main()
