from __future__ import annotations

import logging
from unittest import IsolatedAsyncioTestCase, TestCase

from app.telegram_bot import _deliver_text, configure_logging


class TelegramBotLoggingTest(TestCase):
    def test_http_client_logs_are_not_info(self) -> None:
        configure_logging()

        self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)


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


class FakeUpdate:
    def __init__(self, *, message=None):
        self.message = message
        self.callback_query = None


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
