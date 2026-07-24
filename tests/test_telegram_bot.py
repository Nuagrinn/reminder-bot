from __future__ import annotations

import logging
from unittest import TestCase

from app.telegram_bot import configure_logging


class TelegramBotLoggingTest(TestCase):
    def test_http_client_logs_are_not_info(self) -> None:
        configure_logging()

        self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)

