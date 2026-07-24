from __future__ import annotations

from unittest import TestCase

from app.features.reminder_intake.agent import normalize_claude_payload
from tests.test_fake_parser import request


class ClaudeNormalizationTest(TestCase):
    def test_compact_datetime_payload_becomes_native_schema(self) -> None:
        payload = normalize_claude_payload(
            {
                "intent": "create_reminder",
                "title": "оплатить счет",
                "datetime": "2026-07-25T15:30:00",
                "date": "2026-07-25",
                "time": "15:30",
                "confidence": 1.0,
            },
            request("25 июля в 15:30 оплатить счет"),
        )
        item = payload["items"][0]

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(item["title"], "Оплатить счет")
        self.assertEqual(item["temporal_profile"], "exact_time")
        self.assertEqual(item["schedule"]["kind"], "once")
        self.assertEqual(item["schedule"]["date"], "2026-07-25")
        self.assertEqual(item["schedule"]["time"], "15:30")
        self.assertEqual(item["schedule"]["start_at"], "2026-07-25T15:30:00")

    def test_nested_daily_interval_payload_becomes_recurring_habit(self) -> None:
        payload = normalize_claude_payload(
            {
                "reminder": {
                    "title": "проверять почту",
                    "time": "09:00",
                    "recurrence": {"frequency": "daily", "interval": 2},
                    "reminder_offset_minutes": 30,
                }
            },
            request("каждые два дня проверять почту в 9 за 30 минут"),
        )
        item = payload["items"][0]

        self.assertEqual(item["event_type"], "habit")
        self.assertEqual(item["temporal_profile"], "recurring_exact_time")
        self.assertEqual(item["schedule"]["kind"], "recurring")
        self.assertEqual(item["schedule"]["date"], "2026-07-25")
        self.assertEqual(item["schedule"]["recurrence"]["frequency"], "daily")
        self.assertEqual(item["schedule"]["recurrence"]["interval"], 2)
        self.assertEqual(item["notification_offsets"], [{"minutes_before": 30, "source": "explicit"}])

    def test_compact_clarification_payload_stays_clarification(self) -> None:
        payload = normalize_claude_payload(
            {"status": "needs_clarification", "message": "Когда напомнить?"},
            request("пополнить карту"),
        )

        self.assertEqual(payload["status"], "needs_clarification")
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["clarification"]["question"], "Когда напомнить?")

    def test_machine_clarification_reason_gets_human_question_and_options(self) -> None:
        payload = normalize_claude_payload(
            {"status": "needs_clarification", "reason": "no_time_specified"},
            request("пополнить карту"),
        )

        self.assertEqual(payload["status"], "needs_clarification")
        self.assertEqual(payload["clarification"]["question"], "Когда напомнить?")
        self.assertEqual(payload["clarification"]["options"], ["сегодня", "завтра", "через час"])

    def test_native_machine_clarification_gets_human_question_and_options(self) -> None:
        payload = normalize_claude_payload(
            {
                "schema_version": "reminder-parser-v3",
                "intent": "create",
                "status": "needs_clarification",
                "raw_text": "пополнить карту",
                "items": [],
                "clarification": {"question": "no_time_specified", "options": []},
            },
            request("пополнить карту"),
        )

        self.assertEqual(payload["clarification"]["question"], "Когда напомнить?")
        self.assertEqual(payload["clarification"]["options"], ["сегодня", "завтра", "через час"])

    def test_compact_birthday_payload_gets_yearly_recurrence(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "день рождения Маши",
                "date": "2026-08-12",
                "event_type": "birthday",
            },
            request("12 августа день рождения Маши"),
        )
        item = payload["items"][0]

        self.assertEqual(item["event_type"], "birthday")
        self.assertEqual(item["temporal_profile"], "annual_date")
        self.assertEqual(item["schedule"]["kind"], "recurring")
        self.assertEqual(item["schedule"]["recurrence"]["frequency"], "yearly")
        self.assertEqual(item["schedule"]["recurrence"]["months"], [8])
        self.assertEqual(item["schedule"]["recurrence"]["month_days"], [12])

    def test_relative_delay_without_profile_becomes_moment_reminder(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "проверить духовку",
                "datetime": "2026-07-24T14:00:00",
                "date": "2026-07-24",
                "time": "14:00",
            },
            request("через 2 часа проверить духовку"),
        )
        item = payload["items"][0]

        self.assertEqual(item["temporal_profile"], "moment_reminder")

    def test_compact_midnight_without_explicit_time_becomes_day_task(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "закинуть наличку на карту",
                "datetime": "2026-07-24T00:00:00",
                "date": "2026-07-24",
                "time": "00:00",
                "temporal_profile": "exact_time",
            },
            request("закинуть наличку на карту сегодня"),
        )
        item = payload["items"][0]

        self.assertEqual(item["temporal_profile"], "day_task")
        self.assertTrue(item["schedule"]["all_day"])
        self.assertIsNone(item["schedule"]["start_at"])
        self.assertIsNone(item["schedule"]["time"])
