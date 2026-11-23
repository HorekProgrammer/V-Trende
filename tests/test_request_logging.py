import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app


class RequestLoggingTests(unittest.TestCase):
    def test_deployment_disables_unsanitized_uvicorn_access_log(self):
        dockerfile = (
            Path(__file__).resolve().parents[1] / "deploy" / "Dockerfile.api"
        ).read_text(encoding="utf-8")
        self.assertIn("--no-access-log", dockerfile)

    def test_logs_method_path_status_and_duration_without_sensitive_data(self):
        secret = "do-not-log-this-value"
        with patch("backend.request_logging.LOGGER.info") as info:
            response = TestClient(app).get(
                f"/api/v1/health?token={secret}",
                headers={"Authorization": f"Bearer {secret}", "Cookie": f"session={secret}"},
            )

        self.assertEqual(response.status_code, 200)
        info.assert_called_once()
        template, method, path, status_code, duration_ms = info.call_args.args
        self.assertEqual(
            template,
            "http_request method=%s path=%s status=%d duration_ms=%.2f",
        )
        self.assertEqual((method, path, status_code), ("GET", "/api/v1/health", 200))
        self.assertGreaterEqual(duration_ms, 0)
        self.assertNotIn(secret, " ".join(map(str, info.call_args.args)))


if __name__ == "__main__":
    unittest.main()
