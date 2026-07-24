from __future__ import annotations

from datetime import datetime
from unittest import TestCase

from app.adapters.telegram.formatters import format_daily_agenda, format_parse_confirmation
from app.adapters.telegram.keyboards import (
    CONFIRM_REMINDER_PREFIX,
    DELETE_MENU_PREFIX,
    DELETE_OCCURRENCE_PREFIX,
    DELETE_SERIES_FROM_PREFIX,
    SNOOZE_PREFIX,
    confirmation_keyboard,
    delete_scope_keyboard,
    due_keyboard,
    main_keyboard,
)
from app.features.events.service import EventDefaults
from app.features.notifications.policy import annotate_notification_preview
from app.features.events.models import NotificationJobView, OccurrenceView
from app.features.reminder_intake.agent import FakeReminderParserAgent
from tests.test_fake_parser import request


class TelegramFormattersTest(TestCase):
    def test_confirmation_text_contains_parsed_reminder(self) -> None:
        parse_result = FakeReminderParserAgent().parse(request("надо завтра пополнить карту наличкой"))
        annotate_notification_preview(
            parse_result.payload,
            now=datetime(2026, 7, 24, 12, 0),
            defaults=EventDefaults(timezone="Europe/Moscow"),
        )

        text = format_parse_confirmation(parse_result)

        self.assertIn("Проверь напоминание", text)
        self.assertIn("Пополнить карту наличкой", text)
        self.assertIn("25.07.2026", text)
        self.assertIn("вечером за день", text)

    def test_confirmation_text_contains_daily_interval(self) -> None:
        parse_result = FakeReminderParserAgent().parse(request("каждые два дня проверять почту"))

        text = format_parse_confirmation(parse_result)

        self.assertIn("каждые 2 дня", text)

    def test_confirmation_keyboard_uses_pending_id(self) -> None:
        keyboard = confirmation_keyboard("pending_123")

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{CONFIRM_REMINDER_PREFIX}pending_123")

    def test_due_keyboard_opens_delete_scope_menu(self) -> None:
        job = NotificationJobView(
            job_id="job_1",
            event_id="evt_1",
            occurrence_id="occ_1",
            notification_rule_id="rule_1",
            title="Проверять почту",
            description="",
            event_type="habit",
            occurs_at=datetime(2026, 7, 25, 9, 0),
            notify_at=datetime(2026, 7, 25, 9, 0),
            job_status="pending",
        )
        keyboard = due_keyboard(job)

        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, f"{SNOOZE_PREFIX}job_1:60")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, f"{DELETE_MENU_PREFIX}occ_1")

    def test_delete_scope_keyboard_has_recurring_choices(self) -> None:
        keyboard = delete_scope_keyboard(occurrence_id="occ_1", event_id="evt_1")
        callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]

        self.assertIn(f"{DELETE_OCCURRENCE_PREFIX}occ_1", callbacks)
        self.assertIn(f"{DELETE_SERIES_FROM_PREFIX}occ_1", callbacks)

    def test_main_keyboard_has_week_and_month(self) -> None:
        labels = [button.text for row in main_keyboard().keyboard for button in row]

        self.assertIn("🗓 Неделя", labels)
        self.assertIn("🗂 Месяц", labels)

    def test_daily_agenda_uses_today_list(self) -> None:
        item = OccurrenceView(
            occurrence_id="occ_1",
            event_id="evt_1",
            title="Проверять почту",
            description="",
            event_type="habit",
            occurs_at=datetime(2026, 7, 25, 9, 0),
            occurrence_date="2026-07-25",
            occurrence_status="scheduled",
            event_status="active",
            next_notify_at=datetime(2026, 7, 25, 9, 0),
        )

        text = format_daily_agenda([item])

        self.assertIn("План на сегодня", text)
        self.assertIn("Проверять почту", text)
