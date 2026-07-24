from __future__ import annotations

from app.config import Settings
from app.features.reminder_intake.agent import (
    ClaudeCliReminderParserAgent,
    FakeReminderParserAgent,
    ReminderParserAgent,
)


def build_reminder_parser_agent(settings: Settings) -> ReminderParserAgent:
    if settings.parser_provider in ("", "fake", "local"):
        return FakeReminderParserAgent()
    if settings.parser_provider == "claude_cli":
        return ClaudeCliReminderParserAgent(
            claude_bin=settings.claude_bin,
            oauth_token=settings.claude_code_oauth_token,
            model=settings.claude_model,
            timeout_seconds=settings.claude_timeout_seconds,
            allow_paid_api=settings.allow_paid_api,
        )
    raise RuntimeError(f"Unsupported PARSER_PROVIDER: {settings.parser_provider}")

