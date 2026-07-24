from __future__ import annotations

import unittest
from datetime import datetime

from app.features.reminder_intake.agent import FakeReminderParserAgent, ReminderParseRequest


def request(text: str) -> ReminderParseRequest:
    return ReminderParseRequest(
        raw_text=text,
        source_kind="text",
        now=datetime(2026, 7, 24, 12, 0),
        timezone="Europe/Moscow",
        default_day_reminder_time="09:00",
        default_timed_event_offset_minutes=120,
        default_birthday_offsets_minutes=[1440, 0],
    )


class FakeParserTests(unittest.TestCase):
    def test_parses_tomorrow_task(self) -> None:
        result = FakeReminderParserAgent().parse(request("надо завтра пополнить карту наличкой"))
        item = result.payload["items"][0]

        self.assertEqual(result.payload["status"], "ok")
        self.assertEqual(item["title"], "Пополнить карту наличкой")
        self.assertEqual(item["schedule"]["date"], "2026-07-25")
        self.assertTrue(item["schedule"]["all_day"])

    def test_parses_weekly_task(self) -> None:
        result = FakeReminderParserAgent().parse(request("каждый вторник обновлять отчет по калориям"))
        item = result.payload["items"][0]

        self.assertEqual(item["event_type"], "habit")
        self.assertEqual(item["schedule"]["kind"], "recurring")
        self.assertEqual(item["schedule"]["recurrence"]["frequency"], "weekly")
        self.assertEqual(item["schedule"]["recurrence"]["weekdays"], ["TU"])

    def test_parses_birthday(self) -> None:
        result = FakeReminderParserAgent().parse(request("12 августа день рождения Маши"))
        item = result.payload["items"][0]

        self.assertEqual(item["event_type"], "birthday")
        self.assertEqual(item["schedule"]["recurrence"]["frequency"], "yearly")
        self.assertEqual(item["schedule"]["recurrence"]["months"], [8])
        self.assertEqual(item["schedule"]["recurrence"]["month_days"], [12])

    def test_needs_clarification_without_date(self) -> None:
        result = FakeReminderParserAgent().parse(request("пополнить карту"))

        self.assertEqual(result.payload["status"], "needs_clarification")
        self.assertEqual(result.payload["items"], [])


if __name__ == "__main__":
    unittest.main()

