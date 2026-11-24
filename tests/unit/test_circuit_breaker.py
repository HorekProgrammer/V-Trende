import tempfile
import unittest
from pathlib import Path

from parser.common.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    JsonStateStore,
)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.breaker = CircuitBreaker(
            "provider", failure_threshold=2, recovery_timeout=30, clock=self.clock
        )

    @staticmethod
    def fail():
        raise ConnectionError("down")

    def test_opens_after_failure_threshold_and_rejects_calls(self):
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                self.breaker.call(self.fail)

        self.assertEqual(self.breaker.snapshot.state, CircuitState.OPEN)
        with self.assertRaises(CircuitOpenError) as error:
            self.breaker.call(lambda: "must not run")
        self.assertEqual(error.exception.retry_after, 30)

    def test_success_resets_consecutive_failure_count(self):
        with self.assertRaises(ConnectionError):
            self.breaker.call(self.fail)
        self.assertEqual(self.breaker.call(lambda: "ok"), "ok")
        self.assertEqual(self.breaker.snapshot.failure_count, 0)
        self.assertEqual(self.breaker.snapshot.state, CircuitState.CLOSED)

    def test_half_open_probe_closes_recovered_circuit(self):
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                self.breaker.call(self.fail)
        self.clock.advance(30)

        self.assertEqual(self.breaker.call(lambda: "recovered"), "recovered")
        self.assertEqual(self.breaker.snapshot.state, CircuitState.CLOSED)

    def test_failed_half_open_probe_reopens_circuit(self):
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                self.breaker.call(self.fail)
        self.clock.advance(30)
        with self.assertRaises(ConnectionError):
            self.breaker.call(self.fail)
        self.clock.advance(29)

        with self.assertRaises(CircuitOpenError):
            self.breaker.call(lambda: None)

    def test_state_is_restored_in_a_new_process_instance(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JsonStateStore(Path(temporary) / "breakers.json")
            first = CircuitBreaker(
                "provider", failure_threshold=1, recovery_timeout=30,
                clock=self.clock, store=store,
            )
            with self.assertRaises(ConnectionError):
                first.call(self.fail)

            restored = CircuitBreaker(
                "provider", failure_threshold=1, recovery_timeout=30,
                clock=self.clock, store=store,
            )
            with self.assertRaises(CircuitOpenError):
                restored.call(lambda: None)


if __name__ == "__main__":
    unittest.main()
