"""HTTP-маршруты регистрации: коды ответов, cookie сессии, формат ошибок.

База подменяется заглушкой, как в tests/test_backend.py; логику с настоящей
PostgreSQL проверяет tests/test_auth.py.
"""

import inspect
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import auth

USER = {"id": 7, "email": "mark@mail.ru", "created_at": datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)}
PUBLIC_USER = {"id": 7, "email": "mark@mail.ru", "createdAt": "2026-11-07T12:00:00+00:00"}


class FakeConnection:
    pass


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        from backend.app import app, database

        self.app = app
        self.app.dependency_overrides[database] = lambda: FakeConnection()
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def register(self, **body):
        return self.client.post("/api/v1/auth/register", json=body)

    def test_routes_are_registered(self):
        routes = {(route.path, method) for route in self.app.routes for method in route.methods or []}
        self.assertIn(("/api/v1/auth/register", "POST"), routes)
        self.assertIn(("/api/v1/auth/me", "GET"), routes)

    def test_cookie_parameter_matches_cookie_name(self):
        # FastAPI берёт имя cookie из имени параметра функции me().
        from backend.app import me
        self.assertIn(auth.SESSION_COOKIE, inspect.signature(me).parameters)

    @patch("backend.app.auth.register", return_value=(USER, "token-123"))
    def test_successful_registration_sets_session_cookie(self, register):
        response = self.register(email=" Mark@Mail.ru ", password="password1")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"user": PUBLIC_USER})
        register.assert_called_once()
        self.assertEqual(register.call_args.args[1:], (" Mark@Mail.ru ", "password1"))
        cookie = response.headers["set-cookie"]
        self.assertIn(f"{auth.SESSION_COOKIE}=token-123", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertNotIn("Secure", cookie)
        self.assertNotIn("password", response.text)

    @patch("backend.app.settings", return_value={"SESSION_COOKIE_SECURE": "true"})
    @patch("backend.app.auth.register", return_value=(USER, "token-123"))
    def test_secure_cookie_in_production(self, _register, _settings):
        response = self.register(email="mark@mail.ru", password="password1")
        self.assertIn("Secure", response.headers["set-cookie"])

    @patch("backend.app.auth.register")
    def test_invalid_fields_return_422_with_field_errors(self, register):
        response = self.register(email="bad", password="short")

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["fields"], {"email": "Некорректный email", "password": "Минимум 8 символов"})
        self.assertIn("message", detail)
        register.assert_not_called()
        self.assertNotIn("set-cookie", response.headers)

    @patch("backend.app.auth.register", side_effect=auth.EmailTaken)
    def test_taken_email_returns_409_on_email_field(self, _register):
        response = self.register(email="mark@mail.ru", password="password1")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["fields"],
            {"email": "Пользователь с таким email уже зарегистрирован"},
        )
        self.assertNotIn("set-cookie", response.headers)

    def test_missing_fields_are_rejected(self):
        self.assertEqual(self.client.post("/api/v1/auth/register", json={}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/auth/register", json={"email": 1, "password": 2}).status_code, 422)

    @patch("backend.app.auth.session_user", return_value=USER)
    def test_me_with_session(self, session_user):
        self.client.cookies.set(auth.SESSION_COOKIE, "token-123")
        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user": PUBLIC_USER})
        self.assertEqual(session_user.call_args.args[1], "token-123")

    @patch("backend.app.auth.session_user", return_value=None)
    def test_me_without_session_is_401(self, _session_user):
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)


if __name__ == "__main__":
    unittest.main()
