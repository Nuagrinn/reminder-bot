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

    def test_compact_relative_delay_repairs_missing_start_at(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "замариновать курицу",
                "date": "2026-07-24",
                "temporal_profile": "moment_reminder",
            },
            request("через три часа замариновать курицу"),
        )
        item = payload["items"][0]

        self.assertEqual(item["temporal_profile"], "moment_reminder")
        self.assertFalse(item["schedule"]["all_day"])
        self.assertEqual(item["schedule"]["start_at"], "2026-07-24T15:00:00")
        self.assertEqual(item["schedule"]["date"], "2026-07-24")
        self.assertEqual(item["schedule"]["time"], "15:00")

    def test_native_relative_delay_repairs_date_only_moment_reminder(self) -> None:
        payload = normalize_claude_payload(
            {
                "schema_version": "reminder-parser-v3",
                "intent": "create",
                "status": "ok",
                "raw_text": "Через три часа замариновать курицу.",
                "items": [
                    {
                        "title": "Замариновать курицу",
                        "description": "",
                        "event_type": "task",
                        "temporal_profile": "moment_reminder",
                        "priority": "normal",
                        "schedule": {
                            "kind": "once",
                            "timezone": "Europe/Moscow",
                            "all_day": True,
                            "start_at": None,
                            "date": "2026-07-24",
                            "time": None,
                            "precision": "date",
                            "recurrence": {
                                "frequency": "none",
                                "interval": 1,
                                "weekdays": [],
                                "month_days": [],
                                "months": [],
                                "until": None,
                                "count": None,
                                "rrule": "",
                            },
                        },
                        "notification_offsets": [],
                        "confidence": 0.95,
                        "assumptions": ["start_at = 2026-07-24T15:00:00"],
                    }
                ],
                "clarification": {"question": "", "options": []},
            },
            request("Через три часа замариновать курицу."),
        )
        item = payload["items"][0]

        self.assertEqual(item["temporal_profile"], "moment_reminder")
        self.assertFalse(item["schedule"]["all_day"])
        self.assertEqual(item["schedule"]["start_at"], "2026-07-24T15:00:00")
        self.assertEqual(item["schedule"]["date"], "2026-07-24")
        self.assertEqual(item["schedule"]["time"], "15:00")

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

    def test_compact_payload_keeps_russian_title_when_claude_translates(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "Order creatine and protein",
                "date": "2026-07-25",
            },
            request("Сегодня вечером надо заказать креатин и протеин."),
        )

        self.assertEqual(payload["items"][0]["title"], "Заказать креатин и протеин")

    def test_compact_payload_extracts_context_link_from_raw_text(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "собес/скрининг, ссылка в телемост",
                "datetime": "2026-07-25T14:00:00",
                "date": "2026-07-25",
                "time": "14:00",
            },
            request("Завтра в 14:00 собес/скрининг, ссылка в телемост: https://telemost.yandex.ru/j/123"),
        )
        item = payload["items"][0]

        self.assertEqual(item["title"], "Собес/скрининг")
        self.assertEqual(item["context"][0]["label"], "Телемост")
        self.assertEqual(item["context"][0]["value"], "https://telemost.yandex.ru/j/123")

    def test_native_payload_extracts_context_when_claude_omits_it(self) -> None:
        payload = normalize_claude_payload(
            {
                "schema_version": "reminder-parser-v3",
                "intent": "create",
                "status": "ok",
                "raw_text": "Завтра в 14:00 собес/скрининг https://meet.google.com/abc-defg-hij",
                "items": [
                    {
                        "title": "собес/скрининг",
                        "description": "",
                        "event_type": "calendar_event",
                        "temporal_profile": "exact_time",
                        "priority": "normal",
                        "schedule": {
                            "kind": "once",
                            "timezone": "Europe/Moscow",
                            "all_day": False,
                            "start_at": "2026-07-25T14:00:00",
                            "date": "2026-07-25",
                            "time": "14:00",
                            "precision": "datetime",
                            "recurrence": {
                                "frequency": "none",
                                "interval": 1,
                                "weekdays": [],
                                "month_days": [],
                                "months": [],
                                "until": None,
                                "count": None,
                                "rrule": "",
                            },
                        },
                        "notification_offsets": [],
                        "confidence": 0.9,
                        "assumptions": [],
                    }
                ],
                "clarification": {"question": "", "options": []},
            },
            request("Завтра в 14:00 собес/скрининг https://meet.google.com/abc-defg-hij"),
        )

        self.assertEqual(payload["items"][0]["context"][0]["label"], "Google Meet")

    def test_native_payload_keeps_russian_title_when_claude_translates(self) -> None:
        payload = normalize_claude_payload(
            {
                "schema_version": "reminder-parser-v3",
                "intent": "create",
                "status": "ok",
                "raw_text": "Сегодня вечером надо заказать креатин и протеин.",
                "items": [
                    {
                        "title": "Order creatine and protein",
                        "description": "",
                        "event_type": "task",
                        "temporal_profile": "day_task",
                        "priority": "normal",
                        "schedule": {
                            "kind": "once",
                            "timezone": "Europe/Moscow",
                            "all_day": True,
                            "start_at": None,
                            "date": "2026-07-25",
                            "time": None,
                            "precision": "date",
                            "recurrence": {
                                "frequency": "none",
                                "interval": 1,
                                "weekdays": [],
                                "month_days": [],
                                "months": [],
                                "until": None,
                                "count": None,
                                "rrule": "",
                            },
                        },
                        "notification_offsets": [],
                        "confidence": 0.8,
                        "assumptions": [],
                    }
                ],
                "clarification": {"question": "", "options": []},
            },
            request("Сегодня вечером надо заказать креатин и протеин."),
        )

        self.assertEqual(payload["items"][0]["title"], "Заказать креатин и протеин")

    def test_compact_payload_drops_inferred_clock_when_user_said_morning(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "прибить дощечку на кухне",
                "datetime": "2026-07-25T09:00:00",
                "date": "2026-07-25",
                "time": "09:00",
                "temporal_profile": "exact_time",
            },
            request("Завтра утром прибить дощечку на кухне."),
        )
        item = payload["items"][0]

        self.assertEqual(item["temporal_profile"], "day_task")
        self.assertTrue(item["schedule"]["all_day"])
        self.assertIsNone(item["schedule"]["start_at"])
        self.assertIsNone(item["schedule"]["time"])

    def test_native_payload_drops_inferred_clock_when_user_did_not_say_exact_time(self) -> None:
        payload = normalize_claude_payload(
            {
                "schema_version": "reminder-parser-v3",
                "intent": "create",
                "status": "ok",
                "raw_text": "Завтра утром прибить дощечку на кухне.",
                "items": [
                    {
                        "title": "прибить дощечку на кухне",
                        "description": "",
                        "event_type": "task",
                        "temporal_profile": "exact_time",
                        "priority": "normal",
                        "schedule": {
                            "kind": "once",
                            "timezone": "Europe/Moscow",
                            "all_day": False,
                            "start_at": "2026-07-25T09:00:00",
                            "date": "2026-07-25",
                            "time": "09:00",
                            "precision": "datetime",
                            "recurrence": {
                                "frequency": "none",
                                "interval": 1,
                                "weekdays": [],
                                "month_days": [],
                                "months": [],
                                "until": None,
                                "count": None,
                                "rrule": "",
                            },
                        },
                        "notification_offsets": [],
                        "confidence": 0.8,
                        "assumptions": [],
                    }
                ],
                "clarification": {"question": "", "options": []},
            },
            request("Завтра утром прибить дощечку на кухне."),
        )
        item = payload["items"][0]

        self.assertEqual(item["temporal_profile"], "day_task")
        self.assertTrue(item["schedule"]["all_day"])
        self.assertIsNone(item["schedule"]["start_at"])
        self.assertIsNone(item["schedule"]["time"])

    def test_explicit_clock_time_stays_exact(self) -> None:
        payload = normalize_claude_payload(
            {
                "title": "прибить дощечку на кухне",
                "datetime": "2026-07-25T09:00:00",
                "date": "2026-07-25",
                "time": "09:00",
                "temporal_profile": "exact_time",
            },
            request("Завтра в 9 прибить дощечку на кухне."),
        )
        item = payload["items"][0]

        self.assertEqual(item["temporal_profile"], "exact_time")
        self.assertFalse(item["schedule"]["all_day"])
        self.assertEqual(item["schedule"]["start_at"], "2026-07-25T09:00:00")
        self.assertEqual(item["schedule"]["time"], "09:00")
