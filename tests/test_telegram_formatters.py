from __future__ import annotations

from datetime import datetime
from unittest import TestCase

from app.adapters.telegram.formatters import (
    format_action_cancelled,
    format_daily_agenda,
    format_due_notification,
    format_occurrence_detail,
    format_occurrence_list,
    format_parse_confirmation,
    format_reschedule_menu,
    format_rescheduled,
)
from app.adapters.telegram.keyboards import (
    CLARIFY_CANCEL_PREFIX,
    CLARIFY_PREFIX,
    CONFIRM_REMINDER_PREFIX,
    DELETE_MENU_PREFIX,
    DELETE_OCCURRENCE_PREFIX,
    DELETE_SERIES_FROM_PREFIX,
    DETAIL_CANCEL_PREFIX,
    DONE_PREFIX,
    OCCURRENCE_DETAIL_PREFIX,
    RESCHEDULE_CUSTOM_PREFIX,
    RESCHEDULE_MENU_PREFIX,
    RESCHEDULE_QUICK_PREFIX,
    RESCHEDULE_SCOPE_PREFIX,
    SNOOZE_PREFIX,
    clarification_keyboard,
    confirmation_keyboard,
    delete_scope_keyboard,
    due_keyboard,
    main_keyboard,
    occurrence_detail_keyboard,
    occurrence_list_keyboard,
    reschedule_options_keyboard,
    reschedule_scope_keyboard,
)
from app.features.events.service import EventDefaults
from app.features.notifications.policy import annotate_notification_preview
from app.features.events.models import NotificationJobView, OccurrenceView
from app.features.reminder_intake.agent import FakeReminderParserAgent, ReminderParseResult
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
        self.assertNotIn("Заметка:", text)

    def test_confirmation_text_contains_daily_interval(self) -> None:
        parse_result = FakeReminderParserAgent().parse(request("каждые два дня проверять почту"))

        text = format_parse_confirmation(parse_result)

        self.assertIn("каждые 2 дня", text)

    def test_confirmation_keyboard_uses_pending_id(self) -> None:
        keyboard = confirmation_keyboard("pending_123")

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{CONFIRM_REMINDER_PREFIX}pending_123")

    def test_clarification_keyboard_uses_option_indexes(self) -> None:
        keyboard = clarification_keyboard("pending_123", ["сегодня", "завтра", "через час"])

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{CLARIFY_PREFIX}pending_123:0")
        self.assertEqual(keyboard.inline_keyboard[0][1].callback_data, f"{CLARIFY_PREFIX}pending_123:1")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, f"{CLARIFY_PREFIX}pending_123:2")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, f"{CLARIFY_CANCEL_PREFIX}pending_123")

    def test_clarification_text_hides_machine_reason(self) -> None:
        parse_result = ReminderParseResult(
            payload={
                "status": "needs_clarification",
                "clarification": {"question": "no_time_specified", "options": []},
            },
            provider="test",
            model="test",
        )

        text = format_parse_confirmation(parse_result)

        self.assertIn("Когда напомнить?", text)
        self.assertIn("сегодня", text)
        self.assertNotIn("no_time_specified", text)

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
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, f"{RESCHEDULE_MENU_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[3][0].callback_data, f"{DELETE_MENU_PREFIX}occ_1")

    def test_delete_scope_keyboard_has_recurring_choices(self) -> None:
        keyboard = delete_scope_keyboard(occurrence_id="occ_1", event_id="evt_1")
        callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]

        self.assertIn(f"{DELETE_OCCURRENCE_PREFIX}occ_1", callbacks)
        self.assertIn(f"{DELETE_SERIES_FROM_PREFIX}occ_1", callbacks)

    def test_main_keyboard_has_week_and_month(self) -> None:
        labels = [button.text for row in main_keyboard().keyboard for button in row]

        self.assertIn("🗓 Неделя", labels)
        self.assertIn("🗂 Месяц", labels)

    def test_occurrence_list_keyboard_uses_numbered_detail_buttons(self) -> None:
        item = occurrence()

        keyboard = occurrence_list_keyboard([item])

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{OCCURRENCE_DETAIL_PREFIX}occ_1")
        self.assertIn("1.", keyboard.inline_keyboard[0][0].text)

    def test_all_day_occurrence_list_hides_internal_nine_am_anchor(self) -> None:
        item = all_day_occurrence()

        text = format_occurrence_list([item], title="Сегодня", empty_text="Пусто")
        keyboard = occurrence_list_keyboard([item])

        self.assertIn("<code>день</code>", text)
        self.assertNotIn("09:00", text)
        self.assertIn("1. день", keyboard.inline_keyboard[0][0].text)

    def test_occurrence_detail_keyboard_has_done_and_delete(self) -> None:
        keyboard = occurrence_detail_keyboard("occ_1")

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{DONE_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, f"{RESCHEDULE_MENU_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, f"{DELETE_MENU_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[3][0].callback_data, f"{DETAIL_CANCEL_PREFIX}occ_1")

    def test_reschedule_keyboards_have_scope_and_quick_actions(self) -> None:
        scope_keyboard = reschedule_scope_keyboard(occurrence_id="occ_1")
        options_keyboard = reschedule_options_keyboard(occurrence_id="occ_1", scope="series")

        self.assertEqual(scope_keyboard.inline_keyboard[0][0].callback_data, f"{RESCHEDULE_SCOPE_PREFIX}occ_1:occ")
        self.assertEqual(options_keyboard.inline_keyboard[0][0].callback_data, f"{RESCHEDULE_QUICK_PREFIX}occ_1:series:plus_1h")
        self.assertEqual(options_keyboard.inline_keyboard[3][0].callback_data, f"{RESCHEDULE_CUSTOM_PREFIX}occ_1:series")

    def test_reschedule_texts_show_current_and_new_time(self) -> None:
        menu = format_reschedule_menu(occurrence(), scope="occ")
        done = format_rescheduled(occurrence())

        self.assertIn("Перенести напоминание", menu)
        self.assertIn("25.07.2026 09:00", menu)
        self.assertIn("Перенесено", done)
        self.assertIn("25.07.2026 09:00", done)

    def test_action_cancel_text_is_neutral(self) -> None:
        self.assertEqual(format_action_cancelled(), "Ок, ничего не меняю.")

    def test_occurrence_detail_text_contains_actions_context(self) -> None:
        text = format_occurrence_detail(occurrence())

        self.assertIn("Напоминание", text)
        self.assertIn("Проверять почту", text)
        self.assertIn("25.07.2026 09:00", text)

    def test_all_day_occurrence_detail_hides_internal_time(self) -> None:
        text = format_occurrence_detail(all_day_occurrence())

        self.assertIn("24.07.2026", text)
        self.assertNotIn("09:00", text)

    def test_all_day_due_notification_hides_internal_time(self) -> None:
        text = format_due_notification(
            NotificationJobView(
                job_id="job_1",
                event_id="evt_1",
                occurrence_id="occ_1",
                notification_rule_id="rule_1",
                title="Закинуть наличку на карту",
                description="",
                event_type="task",
                occurs_at=datetime(2026, 7, 24, 9, 0),
                notify_at=datetime(2026, 7, 24, 18, 19),
                job_status="pending",
                all_day=True,
            )
        )

        self.assertIn("24.07.2026", text)
        self.assertNotIn("09:00", text)

    def test_daily_agenda_uses_today_list(self) -> None:
        item = occurrence()

        text = format_daily_agenda([item])

        self.assertIn("План на сегодня", text)
        self.assertIn("Проверять почту", text)


def occurrence() -> OccurrenceView:
    return OccurrenceView(
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


def all_day_occurrence() -> OccurrenceView:
    return OccurrenceView(
        occurrence_id="occ_2",
        event_id="evt_2",
        title="Закинуть наличку на карту",
        description="",
        event_type="task",
        occurs_at=datetime(2026, 7, 24, 9, 0),
        occurrence_date="2026-07-24",
        occurrence_status="scheduled",
        event_status="active",
        next_notify_at=datetime(2026, 7, 24, 18, 19),
        all_day=True,
    )
