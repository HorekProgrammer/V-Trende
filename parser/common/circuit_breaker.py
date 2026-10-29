"""Circuit breaker for external chart providers.

The breaker is intentionally dependency-free.  Its state can be persisted to a
JSON file, so scheduled parser runs do not forget that a provider is failing
when the Python process exits.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeVar


T = TypeVar("T")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_FILE = PROJECT_ROOT / "data" / "circuit_breakers.json"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the provider circuit is open."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = max(0.0, retry_after)
        super().__init__(
            f"Circuit breaker '{name}' is open; retry in {self.retry_after:.0f} s"
        )


@dataclass(frozen=True)
class CircuitSnapshot:
    state: CircuitState
    failure_count: int
    opened_at: float | None


class JsonStateStore:
    """Small atomic JSON store used by scheduled parser processes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def load(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._read()
            value = data.get(name)
            return value if isinstance(value, dict) else None

    def save(self, name: str, snapshot: CircuitSnapshot) -> None:
        with self._lock:
            data = self._read()
            if snapshot.state is CircuitState.CLOSED and snapshot.failure_count == 0:
                data.pop(name, None)
            else:
                data[name] = {
                    "state": snapshot.state.value,
                    "failure_count": snapshot.failure_count,
                    "opened_at": snapshot.opened_at,
                }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(self.path)

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return value if isinstance(value, dict) else {}


class CircuitBreaker:
    """Thread-safe CLOSED/OPEN/HALF_OPEN circuit breaker."""

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 3,
        recovery_timeout: float = 300,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
        clock: Callable[[], float] = time.time,
        store: JsonStateStore | None = None,
    ):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout cannot be negative")
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        self._clock = clock
        self._store = store
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._probe_in_progress = False
        self._restore()

    @property
    def snapshot(self) -> CircuitSnapshot:
        with self._lock:
            return self._snapshot_unlocked()

    def call(self, function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        self._before_call()
        try:
            result = function(*args, **kwargs)
        except self.expected_exceptions:
            self._record_failure()
            raise
        except BaseException:
            self._cancel_probe()
            raise
        self._record_success()
        return result

    def _before_call(self) -> None:
        with self._lock:
            now = self._clock()
            if self._state is CircuitState.OPEN:
                opened_at = now if self._opened_at is None else self._opened_at
                elapsed = now - opened_at
                if elapsed < self.recovery_timeout:
                    raise CircuitOpenError(self.name, self.recovery_timeout - elapsed)
                self._state = CircuitState.HALF_OPEN
                self._probe_in_progress = True
                self._persist_unlocked()
            elif self._state is CircuitState.HALF_OPEN:
                if self._probe_in_progress:
                    raise CircuitOpenError(self.name, self.recovery_timeout)
                self._probe_in_progress = True

    def _record_success(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = None
            self._probe_in_progress = False
            self._persist_unlocked()

    def _record_failure(self) -> None:
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
            else:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = self._clock()
            self._probe_in_progress = False
            self._persist_unlocked()

    def _cancel_probe(self) -> None:
        with self._lock:
            self._probe_in_progress = False

    def _snapshot_unlocked(self) -> CircuitSnapshot:
        return CircuitSnapshot(self._state, self._failure_count, self._opened_at)

    def _persist_unlocked(self) -> None:
        if self._store is not None:
            self._store.save(self.name, self._snapshot_unlocked())

    def _restore(self) -> None:
        if self._store is None:
            return
        value = self._store.load(self.name)
        if not value:
            return
        try:
            state = CircuitState(value["state"])
            failures = max(0, int(value.get("failure_count", 0)))
            opened_at = value.get("opened_at")
            opened_at = None if opened_at is None else float(opened_at)
        except (KeyError, TypeError, ValueError):
            return
        self._state = state
        self._failure_count = failures
        self._opened_at = opened_at
        # A probe cannot survive a process restart; treat it as an open circuit.
        if state is CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN


_registry: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _non_negative_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= 0 else default


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Return one persistent breaker per external provider."""
    with _registry_lock:
        if name not in _registry:
            state_path = os.getenv("CIRCUIT_BREAKER_STATE_FILE", str(DEFAULT_STATE_FILE))
            _registry[name] = CircuitBreaker(
                name,
                failure_threshold=_positive_int("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 3),
                recovery_timeout=_non_negative_float("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 300),
                store=JsonStateStore(state_path),
            )
        return _registry[name]


def protected_call(name: str, function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    return get_circuit_breaker(name).call(function, *args, **kwargs)
