import unittest

from parser.weekly_status import parse_latest_prepare


class WeeklyStatusTests(unittest.TestCase):
    def test_latest_running_prepare_is_detected(self):
        run = parse_latest_prepare(
            "[2026-11-08T22:00:00+03:00] prepare: запуск\n"
            "[2026-11-08T23:00:00+03:00] prepare: код 0\n"
            "[2026-11-15T22:00:05+03:00] prepare: запуск\n"
            "[vk] OK: сохранено\n"
        )
        self.assertIsNone(run.code)
        self.assertEqual(run.week.isoformat(), "2026-11-16")

    def test_errors_and_completion_are_reported(self):
        run = parse_latest_prepare(
            "[2026-11-15T22:00:05+03:00] prepare: запуск\n"
            "[twitch] ОШИБКА: формат изменился\n"
            "[2026-11-15T22:27:00+03:00] prepare: код 1\n"
        )
        self.assertEqual(run.code, 1)
        self.assertEqual(run.errors, (("twitch", "формат изменился"),))
        self.assertIsNotNone(run.finished_at)


if __name__ == "__main__":
    unittest.main()
