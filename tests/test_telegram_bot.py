from __future__ import annotations

import logging
from datetime import datetime
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from app.adapters.telegram.keyboards import CLARIFY_PREFIX, HIDE_MESSAGE_PREFIX, HIDE_NOTIFICATION_PREFIX
from app.adapters.telegram.keyboards import LIST_PAGE_PREFIX, OCCURRENCE_DETAIL_PREFIX
from app.features.events.models import OccurrenceView
from app.features.reminder_intake.agent import ReminderParseRequest, ReminderParseResult
from app.telegram_bot import (
    _build_occurrence_list_view,
    _deliver_text,
    _format_version_update_text,
    configure_logging,
    PendingReminder,
    clarify_callback,
    hide_message_callback,
    hide_notification_callback,
    list_page_callback,
    occurrence_detail_callback,
)


class TelegramBotLoggingTest(TestCase):
    def test_http_client_logs_are_not_info(self) -> None:
        configure_logging()

        self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)

    def test_version_update_text_contains_commit_context(self) -> None:
        with (
            patch("app.telegram_bot._current_version", return_value="abc123"),
            patch("app.telegram_bot._current_version_subject", return_value="Add feature"),
            patch("app.telegram_bot._current_version_date", return_value="2026-07-24 18:30:00 +0300"),
        ):
            text = _format_version_update_text()

        self.assertIn("Reminder Bot обновлен", text)
        self.assertIn("abc123", text)
        self.assertIn("Add feature", text)


class TelegramDeliveryTest(IsolatedAsyncioTestCase):
    async def test_deliver_text_edits_status_message(self) -> None:
        status_message = FakeEditMessage()

        delivered_via_edit = await _deliver_text(
            FakeUpdate(),
            "Проверь напоминание",
            edit_message=status_message,
            parse_mode="HTML",
        )

        self.assertTrue(delivered_via_edit)
        self.assertEqual(status_message.edits[0][0], "Проверь напоминание")
        self.assertEqual(status_message.edits[0][1]["parse_mode"], "HTML")

    async def test_deliver_text_falls_back_to_reply_after_edit_failure(self) -> None:
        reply_message = FakeReplyMessage()

        with self.assertLogs("app.telegram_bot", level="INFO"):
            delivered_via_edit = await _deliver_text(
                FakeUpdate(message=reply_message),
                "Проверь напоминание",
                edit_message=FailingEditMessage(),
            )

        self.assertFalse(delivered_via_edit)
        self.assertEqual(reply_message.replies[0][0], "Проверь напоминание")

    async def test_hide_notification_callback_deletes_message(self) -> None:
        message = FakeDeletableMessage()
        query = FakeCallbackQuery(data=f"{HIDE_NOTIFICATION_PREFIX}job_1", message=message)
        update = FakeCallbackUpdate(query=query, user_id=123)
        context = FakeContext(owner_id=123)

        await hide_notification_callback(update, context)

        self.assertTrue(message.deleted)
        self.assertEqual(query.answers, [("Скрыто", {})])

    async def test_hide_message_callback_deletes_message(self) -> None:
        message = FakeDeletableMessage()
        query = FakeCallbackQuery(data=f"{HIDE_MESSAGE_PREFIX}list", message=message)
        update = FakeCallbackUpdate(query=query, user_id=123)
        context = FakeContext(owner_id=123)

        await hide_message_callback(update, context)

        self.assertTrue(message.deleted)
        self.assertEqual(query.answers, [("Скрыто", {})])

    async def test_occurrence_detail_stale_click_shows_refresh_hint(self) -> None:
        message = FakeDeletableMessage()
        query = FakeCallbackQuery(data=f"{OCCURRENCE_DETAIL_PREFIX}missing", message=message)
        update = FakeCallbackUpdate(query=query, user_id=123)
        context = FakeContext(owner_id=123, services=FakeServices(items=[]))

        await occurrence_detail_callback(update, context)

        self.assertEqual(query.answers, [("Не нашел это напоминание. Обнови список.", {"show_alert": True})])
        self.assertEqual(message.edits, [])

    async def test_list_page_callback_edits_same_card(self) -> None:
        items = [
            fake_occurrence(f"occ_{index}", f"Событие {index}", datetime(2026, 7, 26, 9, index))
            for index in range(1, 13)
        ]
        message = FakeDeletableMessage()
        query = FakeCallbackQuery(data=f"{LIST_PAGE_PREFIX}week:20260726:1", message=message)
        update = FakeCallbackUpdate(query=query, user_id=123)
        context = FakeContext(owner_id=123, services=FakeServices(items=items))

        await list_page_callback(update, context)

        self.assertEqual(query.answers, [("", {})])
        edit_text, kwargs = message.edits[0]
        self.assertIn("Показано: <b>11-12</b> из <b>12</b>", edit_text)
        self.assertEqual([button.text for button in kwargs["reply_markup"].inline_keyboard[0]], ["1", "2"])

    async def test_occurrence_list_builder_supports_all_entry_kinds(self) -> None:
        now = datetime(2026, 7, 26, 12, 0)
        services = FakeServices(
            items=[fake_occurrence("occ_1", "Сегодня", datetime(2026, 7, 26, 9, 0))],
            annual_items=[fake_occurrence("occ_2", "День рождения", datetime(2027, 5, 11, 9, 0))],
        )

        views = [
            await _build_occurrence_list_view(services, kind=kind, now=now)
            for kind in ("today", "week", "month", "upcoming", "agenda", "annual")
        ]

        self.assertEqual([view.kind for view in views], ["today", "week", "month", "upcoming", "agenda", "annual"])
        self.assertTrue(all(view.page_size == 10 for view in views))

    async def test_clarification_callback_acknowledges_before_slow_parse(self) -> None:
        message = FakeDeletableMessage()
        query = FakeCallbackQuery(data=f"{CLARIFY_PREFIX}pending_1:0", message=message)
        update = FakeCallbackUpdate(query=query, user_id=123)
        services = FakeServices(items=[])
        services.intake = FakeClarificationIntake(query)
        context = FakeContext(owner_id=123, services=services)
        now = datetime(2026, 7, 26, 23, 0)
        request = ReminderParseRequest(
            raw_text="Купить кофе",
            source_kind="voice",
            now=now,
            timezone="Europe/Moscow",
            default_day_reminder_time="09:00",
            default_timed_event_offset_minutes=120,
            default_birthday_offsets_minutes=[1440, 0],
        )
        context.application.bot_data["pending_reminders"] = {
            "pending_1": PendingReminder(
                request=request,
                parse_result=ReminderParseResult(
                    payload={
                        "intent": "create",
                        "status": "needs_clarification",
                        "clarification": {"question": "Когда напомнить?", "options": ["Сегодня"]},
                    },
                    provider="test",
                    model="test",
                ),
                created_at=now,
            )
        }

        await clarify_callback(update, context)

        self.assertEqual(query.answers[0], ("Уточняю...", {}))
        self.assertEqual(message.edits[0][0], "Уточняю напоминание...")
        self.assertIn("Проверь напоминание", message.edits[-1][0])


class FakeUpdate:
    def __init__(self, *, message=None):
        self.message = message
        self.callback_query = None


class FakeCallbackUpdate:
    def __init__(self, *, query, user_id: int):
        self.message = None
        self.callback_query = query
        self.effective_user = FakeUser(user_id)


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeContext:
    def __init__(self, *, owner_id: int, services=None):
        self.application = FakeApplication(owner_id=owner_id, services=services)
        self.user_data = {}


class FakeApplication:
    def __init__(self, *, owner_id: int, services=None):
        self.bot_data = {"owner_id": owner_id}
        if services is not None:
            self.bot_data["services"] = services


class FakeCallbackQuery:
    def __init__(self, *, data: str, message):
        self.data = data
        self.message = message
        self.answers = []

    async def answer(self, text: str = "", **kwargs) -> None:
        self.answers.append((text, kwargs))

    async def edit_message_text(self, text: str, **kwargs) -> None:
        self.message.edits.append((text, kwargs))


class FakeDeletableMessage:
    def __init__(self) -> None:
        self.deleted = False
        self.edits = []

    async def delete(self) -> None:
        self.deleted = True


class FakeEditMessage:
    def __init__(self) -> None:
        self.edits = []

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edits.append((text, kwargs))


class FailingEditMessage:
    async def edit_text(self, text: str, **kwargs) -> None:
        raise RuntimeError("edit failed")


class FakeReplyMessage:
    def __init__(self) -> None:
        self.replies = []

    async def reply_text(self, text: str, **kwargs) -> None:
        self.replies.append((text, kwargs))


class FakeServices:
    def __init__(self, *, items: list[OccurrenceView], annual_items: list[OccurrenceView] | None = None):
        self.settings = FakeSettings()
        self.events = FakeEvents(items=items, annual_items=annual_items or [])


class FakeSettings:
    timezone = "Europe/Moscow"
    daily_agenda_limit = 50
    default_day_reminder_time = "09:00"
    default_timed_event_offset_minutes = 120
    default_birthday_offsets_minutes = [1440, 0]


class FakeDefaults:
    materialize_days = 180


class FakeEvents:
    def __init__(self, *, items: list[OccurrenceView], annual_items: list[OccurrenceView]):
        self.items = items
        self.annual_items = annual_items
        self.defaults = FakeDefaults()

    def materialize_all(self, *, now: datetime) -> int:
        return len(self.items)

    def list_occurrences(self, *, start_at: datetime, end_at: datetime, limit: int = 50) -> list[OccurrenceView]:
        items = [item for item in self.items if start_at <= item.occurs_at <= end_at]
        return sorted(items, key=lambda item: item.occurs_at)[:limit]

    def annual_occurrences(self, *, now: datetime, limit: int = 100) -> list[OccurrenceView]:
        return self.annual_items[:limit]

    def get_occurrence(self, occurrence_id: str) -> OccurrenceView:
        for item in self.items:
            if item.occurrence_id == occurrence_id:
                return item
        raise ValueError(f"Occurrence not found: {occurrence_id}")


class FakeClarificationIntake:
    def __init__(self, query: FakeCallbackQuery):
        self.query = query

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        assert self.query.answers == [("Уточняю...", {})]
        assert self.query.message.edits[0][0] == "Уточняю напоминание..."
        assert request.raw_text == "Купить кофе Сегодня"
        return ReminderParseResult(
            payload={
                "intent": "create",
                "status": "ok",
                "items": [
                    {
                        "title": "Купить кофе",
                        "schedule": {"date": "2026-07-26"},
                        "notification_offsets": [],
                    }
                ],
            },
            provider="test",
            model="test",
        )


def fake_occurrence(occurrence_id: str, title: str, occurs_at: datetime) -> OccurrenceView:
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
        all_day=True,
    )
