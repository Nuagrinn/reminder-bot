from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest import TestCase

from app.adapters.telegram.formatters import (
    format_action_cancelled,
    format_daily_agenda,
    format_daily_agenda_settings,
    format_daily_agenda_toggled,
    format_due_notification,
    format_occurrence_detail,
    format_occurrence_list,
    format_occurrence_list_view,
    format_parse_confirmation,
    format_reschedule_menu,
    format_rescheduled,
)
from app.adapters.telegram.keyboards import (
    CLARIFY_CANCEL_PREFIX,
    CLARIFY_PREFIX,
    CONFIRM_REMINDER_PREFIX,
    DAILY_AGENDA_TOGGLE_PREFIX,
    DELETE_MENU_PREFIX,
    DELETE_OCCURRENCE_PREFIX,
    DELETE_SERIES_FROM_PREFIX,
    DETAIL_CANCEL_PREFIX,
    DONE_PREFIX,
    HIDE_MESSAGE_PREFIX,
    HIDE_NOTIFICATION_PREFIX,
    LIST_PAGE_PREFIX,
    OCCURRENCE_DETAIL_PREFIX,
    RESCHEDULE_CUSTOM_PREFIX,
    RESCHEDULE_MENU_PREFIX,
    RESCHEDULE_QUICK_PREFIX,
    RESCHEDULE_SCOPE_PREFIX,
    SNOOZE_PREFIX,
    clarification_keyboard,
    confirmation_keyboard,
    daily_agenda_settings_keyboard,
    delete_scope_keyboard,
    due_keyboard,
    main_keyboard,
    occurrence_detail_keyboard,
    occurrence_list_keyboard,
    reschedule_options_keyboard,
    reschedule_scope_keyboard,
)
from app.adapters.telegram.occurrence_list_view import OccurrenceListView
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
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, f"{HIDE_MESSAGE_PREFIX}confirmation")

    def test_clarification_keyboard_uses_option_indexes(self) -> None:
        keyboard = clarification_keyboard("pending_123", ["сегодня", "завтра", "через час"])

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{CLARIFY_PREFIX}pending_123:0")
        self.assertEqual(keyboard.inline_keyboard[0][1].callback_data, f"{CLARIFY_PREFIX}pending_123:1")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, f"{CLARIFY_PREFIX}pending_123:2")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, f"{CLARIFY_CANCEL_PREFIX}pending_123")
        self.assertEqual(keyboard.inline_keyboard[3][0].callback_data, f"{HIDE_MESSAGE_PREFIX}clarification")

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
        self.assertEqual(keyboard.inline_keyboard[4][0].callback_data, f"{HIDE_NOTIFICATION_PREFIX}job_1")

    def test_delete_scope_keyboard_has_recurring_choices(self) -> None:
        keyboard = delete_scope_keyboard(occurrence_id="occ_1", event_id="evt_1")
        callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]

        self.assertIn(f"{DELETE_OCCURRENCE_PREFIX}occ_1", callbacks)
        self.assertIn(f"{DELETE_SERIES_FROM_PREFIX}occ_1", callbacks)
        self.assertIn(f"{HIDE_MESSAGE_PREFIX}delete", callbacks)

    def test_main_keyboard_has_week_and_month(self) -> None:
        labels = [button.text for row in main_keyboard().keyboard for button in row]

        self.assertIn("🗓 Неделя", labels)
        self.assertIn("🗂 Месяц", labels)
        self.assertIn("🎂 Ежегодные", labels)
        self.assertIn("🌅 Утро", labels)

    def test_daily_agenda_settings_keyboard_toggles_state(self) -> None:
        enabled_keyboard = daily_agenda_settings_keyboard(enabled=True)
        disabled_keyboard = daily_agenda_settings_keyboard(enabled=False)

        self.assertEqual(enabled_keyboard.inline_keyboard[0][0].callback_data, f"{DAILY_AGENDA_TOGGLE_PREFIX}off")
        self.assertEqual(disabled_keyboard.inline_keyboard[0][0].callback_data, f"{DAILY_AGENDA_TOGGLE_PREFIX}on")
        self.assertEqual(enabled_keyboard.inline_keyboard[1][0].callback_data, f"{HIDE_MESSAGE_PREFIX}daily_agenda")

    def test_occurrence_list_keyboard_uses_numbered_detail_buttons(self) -> None:
        item = occurrence()

        keyboard = occurrence_list_keyboard(list_view([item]))

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{OCCURRENCE_DETAIL_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[0][0].text, "1")
        self.assertEqual(keyboard.inline_keyboard[-1][0].callback_data, f"{HIDE_MESSAGE_PREFIX}list")

    def test_all_day_occurrence_list_hides_internal_nine_am_anchor(self) -> None:
        item = all_day_occurrence()

        text = format_occurrence_list([item], title="Сегодня", empty_text="Пусто")
        keyboard = occurrence_list_keyboard(list_view([item], anchor_date=date(2026, 7, 24)))

        self.assertIn("<b>1.</b> Закинуть наличку на карту", text)
        self.assertNotIn("<code>день</code>", text)
        self.assertNotIn("09:00", text)
        self.assertEqual(keyboard.inline_keyboard[0][0].text, "1")

    def test_broad_time_word_is_shown_instead_of_internal_clock_anchor(self) -> None:
        item = OccurrenceView(
            occurrence_id="occ_3",
            event_id="evt_3",
            title="Прибить дощечку на кухне",
            description="",
            event_type="task",
            occurs_at=datetime(2026, 7, 25, 9, 0),
            occurrence_date="2026-07-25",
            occurrence_status="scheduled",
            event_status="active",
            next_notify_at=None,
            all_day=True,
            source_text="Завтра утром прибить дощечку на кухне.",
        )

        text = format_occurrence_list([item], title="Сегодня", empty_text="Пусто")
        detail = format_occurrence_detail(item)
        keyboard = occurrence_list_keyboard(list_view([item], anchor_date=date(2026, 7, 25)))

        self.assertIn("<code>утро</code>", text)
        self.assertNotIn("09:00", text)
        self.assertIn("25.07.2026, утром", detail)
        self.assertEqual(keyboard.inline_keyboard[0][0].text, "1")

    def test_compact_week_list_shows_short_header_and_weekday_group(self) -> None:
        anchor = date(2026, 7, 26)
        item = occurrence_at("occ_4", "Приделать дощечку на кухне", datetime(2026, 7, 26, 9, 0), all_day=True)
        view = list_view([item], kind="week", title="Неделя", anchor_date=anchor, days=7)

        text = format_occurrence_list_view(view)

        self.assertIn("<b>Неделя · 26.07-01.08</b>", text)
        self.assertIn("<b>Вс 26.07 · сегодня</b>", text)
        self.assertNotIn("26.07.2026", text)

    def test_today_list_keeps_weekday_in_header_without_duplicate_date_group(self) -> None:
        anchor = date(2026, 7, 26)
        item = occurrence_at("occ_5", "Помыть машину", datetime(2026, 7, 26, 9, 0), all_day=True)
        view = list_view([item], kind="today", title="Сегодня", anchor_date=anchor, days=1)

        text = format_occurrence_list_view(view)

        self.assertIn("<b>Сегодня · Вс 26.07</b>", text)
        self.assertNotIn("<b>Вс 26.07 · сегодня</b>", text)
        self.assertIn("<b>1.</b> Помыть машину", text)

    def test_annual_list_forces_year_in_date_group(self) -> None:
        anchor = date(2026, 7, 26)
        item = occurrence_at("occ_6", "День рождения Виталика", datetime(2027, 5, 11, 9, 0), all_day=True)
        view = list_view([item], kind="annual", title="Ежегодные", anchor_date=anchor, force_year=True)

        text = format_occurrence_list_view(view)

        self.assertIn("<b>11.05.2027 · Вт</b>", text)
        self.assertIn("День рождения Виталика", text)

    def test_occurrence_list_keyboard_uses_numeric_rows_and_pagination(self) -> None:
        anchor = date(2026, 7, 26)
        items = [
            occurrence_at(f"occ_page_{index}", f"Событие {index}", datetime(2026, 7, 26, 9, index), all_day=True)
            for index in range(1, 13)
        ]
        view = list_view(items, kind="week", title="Неделя", anchor_date=anchor, days=7)

        text = format_occurrence_list_view(view)
        keyboard = occurrence_list_keyboard(view)

        self.assertIn("Показано: <b>1-10</b> из <b>12</b>", text)
        first_page_numbers = [button.text for row in keyboard.inline_keyboard[:2] for button in row]
        self.assertEqual(first_page_numbers, [str(index) for index in range(1, 11)])
        pager = keyboard.inline_keyboard[2]
        self.assertEqual([button.text for button in pager], ["←", "1/2", "→"])
        self.assertEqual(pager[2].callback_data, f"{LIST_PAGE_PREFIX}week:20260726:1")

    def test_occurrence_list_second_page_uses_visible_row_numbers(self) -> None:
        anchor = date(2026, 7, 26)
        items = [
            occurrence_at(f"occ_page_{index}", f"Событие {index}", datetime(2026, 7, 26, 9, index), all_day=True)
            for index in range(1, 13)
        ]
        view = list_view(items, kind="week", title="Неделя", anchor_date=anchor, days=7, page=1)

        text = format_occurrence_list_view(view)
        keyboard = occurrence_list_keyboard(view)

        self.assertIn("Показано: <b>11-12</b> из <b>12</b>", text)
        self.assertIn("<b>1.</b> Событие 11", text)
        self.assertEqual([button.text for button in keyboard.inline_keyboard[0]], ["1", "2"])
        self.assertEqual(keyboard.inline_keyboard[1][1].text, "2/2")

    def test_occurrence_detail_keyboard_has_done_and_delete(self) -> None:
        keyboard = occurrence_detail_keyboard("occ_1")

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{DONE_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, f"{RESCHEDULE_MENU_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, f"{DELETE_MENU_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[3][0].callback_data, f"{DETAIL_CANCEL_PREFIX}occ_1")
        self.assertEqual(keyboard.inline_keyboard[4][0].callback_data, f"{HIDE_MESSAGE_PREFIX}detail")

    def test_reschedule_keyboards_have_scope_and_quick_actions(self) -> None:
        scope_keyboard = reschedule_scope_keyboard(occurrence_id="occ_1")
        options_keyboard = reschedule_options_keyboard(occurrence_id="occ_1", scope="series")

        self.assertEqual(scope_keyboard.inline_keyboard[0][0].callback_data, f"{RESCHEDULE_SCOPE_PREFIX}occ_1:occ")
        self.assertEqual(options_keyboard.inline_keyboard[0][0].callback_data, f"{RESCHEDULE_QUICK_PREFIX}occ_1:series:plus_1h")
        self.assertEqual(options_keyboard.inline_keyboard[3][0].callback_data, f"{RESCHEDULE_CUSTOM_PREFIX}occ_1:series")
        self.assertEqual(scope_keyboard.inline_keyboard[-1][0].callback_data, f"{HIDE_MESSAGE_PREFIX}reschedule_scope")
        self.assertEqual(options_keyboard.inline_keyboard[-1][0].callback_data, f"{HIDE_MESSAGE_PREFIX}reschedule_options")

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

    def test_daily_agenda_empty_state_is_clear(self) -> None:
        text = format_daily_agenda([])

        self.assertIn("На сегодня событий нет", text)

    def test_daily_agenda_settings_texts_show_status(self) -> None:
        settings_text = format_daily_agenda_settings(enabled=True, time_label="07:00")
        toggled_text = format_daily_agenda_toggled(enabled=False, time_label="07:00")

        self.assertIn("включены", settings_text)
        self.assertIn("07:00", settings_text)
        self.assertIn("выключены", toggled_text)


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


def occurrence_at(
    occurrence_id: str,
    title: str,
    occurs_at: datetime,
    *,
    all_day: bool = False,
    source_text: str = "",
) -> OccurrenceView:
    return OccurrenceView(
        occurrence_id=occurrence_id,
        event_id=f"evt_{occurrence_id}",
        title=title,
        description="",
        event_type="task",
        occurs_at=occurs_at,
        occurrence_date=occurs_at.date().isoformat(),
        occurrence_status="scheduled",
        event_status="active",
        next_notify_at=None,
        all_day=all_day,
        source_text=source_text,
    )


def list_view(
    items: list[OccurrenceView],
    *,
    kind: str = "today",
    title: str = "Сегодня",
    anchor_date: date = date(2026, 7, 26),
    days: int | None = None,
    page: int = 0,
    force_year: bool = False,
) -> OccurrenceListView:
    return OccurrenceListView(
        kind=kind,
        title=title,
        empty_text="Пусто",
        anchor_date=anchor_date,
        items=items,
        range_start=anchor_date if days else None,
        range_end=anchor_date + timedelta(days=days) if days else None,
        page=page,
        force_year=force_year,
    )
