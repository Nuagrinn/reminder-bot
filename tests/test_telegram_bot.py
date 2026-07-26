from __future__ import annotations

import logging
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from app.adapters.telegram.keyboards import HIDE_MESSAGE_PREFIX, HIDE_NOTIFICATION_PREFIX
from app.telegram_bot import (
    _deliver_text,
    _format_version_update_text,
    configure_logging,
    hide_message_callback,
    hide_notification_callback,
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
    def __init__(self, *, owner_id: int):
        self.application = FakeApplication(owner_id=owner_id)


class FakeApplication:
    def __init__(self, *, owner_id: int):
        self.bot_data = {"owner_id": owner_id}


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
