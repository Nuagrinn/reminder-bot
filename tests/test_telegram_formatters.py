from __future__ import annotations

from unittest import TestCase

from app.adapters.telegram.formatters import format_parse_confirmation
from app.adapters.telegram.keyboards import CONFIRM_REMINDER_PREFIX, confirmation_keyboard, main_keyboard
from app.features.reminder_intake.agent import FakeReminderParserAgent
from tests.test_fake_parser import request


class TelegramFormattersTest(TestCase):
    def test_confirmation_text_contains_parsed_reminder(self) -> None:
        parse_result = FakeReminderParserAgent().parse(request("надо завтра пополнить карту наличкой"))

        text = format_parse_confirmation(parse_result)

        self.assertIn("Проверь напоминание", text)
        self.assertIn("Пополнить карту наличкой", text)
        self.assertIn("25.07.2026", text)

    def test_confirmation_keyboard_uses_pending_id(self) -> None:
        keyboard = confirmation_keyboard("pending_123")

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, f"{CONFIRM_REMINDER_PREFIX}pending_123")

    def test_main_keyboard_has_week_and_month(self) -> None:
        labels = [button.text for row in main_keyboard().keyboard for button in row]

        self.assertIn("🗓 Неделя", labels)
        self.assertIn("🗂 Месяц", labels)

