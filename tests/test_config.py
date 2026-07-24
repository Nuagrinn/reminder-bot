from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from app.config import load_settings


class LoadSettingsTest(TestCase):
    def test_telegram_owner_id_is_preferred(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_OWNER_ID": "12345",
                "TG_USER_ID": "99999",
            },
        ):
            settings = load_settings()

        self.assertEqual(settings.tg_user_id, 12345)

    def test_daily_agenda_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_OWNER_ID": "12345",
                "DAILY_AGENDA_ENABLED": "true",
                "DAILY_AGENDA_TIME": "07:30",
                "DAILY_AGENDA_LIMIT": "25",
            },
        ):
            settings = load_settings()

        self.assertTrue(settings.daily_agenda_enabled)
        self.assertEqual(settings.daily_agenda_hhmm, (7, 30))
        self.assertEqual(settings.daily_agenda_limit, 25)

    def test_claude_budget_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_OWNER_ID": "12345",
                "CLAUDE_MODEL": "",
                "CLAUDE_MAX_BUDGET_USD": "0.07",
                "CLAUDE_SYSTEM_PROMPT_MODE": "replace",
            },
        ):
            settings = load_settings()

        self.assertEqual(settings.claude_model, "claude-haiku-4-5-20251001")
        self.assertEqual(settings.claude_max_budget_usd, 0.07)
        self.assertEqual(settings.claude_system_prompt_mode, "replace")
