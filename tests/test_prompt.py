from __future__ import annotations

from unittest import TestCase

from app.features.reminder_intake.prompt import build_system_prompt
from app.features.reminder_intake.prompt import build_user_prompt
from app.features.reminder_intake.schema import PROMPT_VERSION
from tests.test_fake_parser import request


class PromptTest(TestCase):
    def test_prompt_contains_claude_recurrence_rules(self) -> None:
        prompt = build_system_prompt(request("каждые два дня проверять почту"))

        self.assertEqual(PROMPT_VERSION, "reminder-parser-v2")
        self.assertTrue(prompt.isascii())
        self.assertIn("daily recurrence interval=2", prompt)
        self.assertIn("weekly recurrence interval=2", prompt)
        self.assertIn("do not use custom_rrule", prompt)
        self.assertIn("YYYY-MM-DDTHH:MM:00", prompt)

    def test_user_prompt_escapes_non_ascii_for_windows_cli(self) -> None:
        prompt = build_user_prompt(request("25 июля в 15:30 оплатить счет"))

        self.assertTrue(prompt.isascii())
        self.assertIn("\\u0438\\u044e\\u043b\\u044f", prompt)
        self.assertNotIn("июля", prompt)
