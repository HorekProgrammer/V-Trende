"""Safe request timing logs for runtime observability."""

from __future__ import annotations

import logging
import sys
from time import perf_counter

from fastapi import FastAPI, Request


LOGGER = logging.getLogger("vcharte.requests")
if not LOGGER.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False


def install_request_logging(app: FastAPI) -> None:
    """Log method, path, response status and duration without request data."""

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (perf_counter() - started) * 1000
            # Deliberately omit query strings, headers, cookies and bodies: they
            # can contain tokens, passwords and other sensitive information.
            LOGGER.info(
                "http_request method=%s path=%s status=%d duration_ms=%.2f",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
