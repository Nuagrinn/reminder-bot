from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from assistant_toolkit.config import (
    load_env_file,
    parse_bool,
    parse_hhmm,
    parse_int,
    resolve_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    db_path: Path
    telegram_bot_token: str
    tg_user_id: int | None
    reminder_tick_seconds: int
    timezone: str
    default_day_reminder_time: str
    default_timed_event_offset_minutes: int
    default_birthday_offsets_minutes: list[int]
    materialize_days: int
    daily_agenda_enabled: bool
    daily_agenda_time: str
    daily_agenda_limit: int
    parser_provider: str
    claude_bin: str
    claude_code_oauth_token: str
    claude_model: str
    claude_timeout_seconds: int
    claude_max_budget_usd: float
    claude_system_prompt_mode: str
    allow_paid_api: bool
    stt_provider: str
    voice_dir: Path
    openai_api_key: str
    stt_openai_model: str
    stt_language: str
    stt_prompt: str
    stt_timeout_seconds: int
    stt_whisper_bin: str
    stt_whisper_model: str
    stt_whisper_cpp_bin: str
    stt_whisper_cpp_model: Path
    ffmpeg_bin: str

    @property
    def default_day_reminder_hhmm(self) -> tuple[int, int]:
        return parse_hhmm(self.default_day_reminder_time, default=(9, 0))

    @property
    def daily_agenda_hhmm(self) -> tuple[int, int]:
        return parse_hhmm(self.daily_agenda_time, default=(7, 0))


def load_settings() -> Settings:
    env_file = load_env_file(PROJECT_ROOT / ".env")

    def get(name: str, default: str = "") -> str:
        return os.getenv(name) or env_file.get(name, default)

    raw_user_id = get("TELEGRAM_OWNER_ID") or get("TG_USER_ID")
    tg_user_id = int(raw_user_id) if raw_user_id.isdigit() else None
    raw_offsets = get("DEFAULT_BIRTHDAY_OFFSETS_MINUTES", "1440,0")
    birthday_offsets = [
        parse_int(part, default=0, min_value=0)
        for part in raw_offsets.split(",")
        if part.strip()
    ] or [1440, 0]

    return Settings(
        db_path=resolve_path(get("DB_PATH"), default=PROJECT_ROOT / "data" / "reminder.sqlite3", base_dir=PROJECT_ROOT),
        telegram_bot_token=get("TELEGRAM_BOT_TOKEN").strip(),
        tg_user_id=tg_user_id,
        reminder_tick_seconds=parse_int(get("REMINDER_TICK_SECONDS", "60"), default=60, min_value=10),
        timezone=get("TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow",
        default_day_reminder_time=get("DEFAULT_DAY_REMINDER_TIME", "09:00").strip() or "09:00",
        default_timed_event_offset_minutes=parse_int(
            get("DEFAULT_TIMED_EVENT_OFFSET_MINUTES", "120"),
            default=120,
            min_value=0,
        ),
        default_birthday_offsets_minutes=birthday_offsets,
        materialize_days=parse_int(get("MATERIALIZE_DAYS", "180"), default=180, min_value=7),
        daily_agenda_enabled=parse_bool(get("DAILY_AGENDA_ENABLED", "true")),
        daily_agenda_time=get("DAILY_AGENDA_TIME", "07:00").strip() or "07:00",
        daily_agenda_limit=parse_int(get("DAILY_AGENDA_LIMIT", "50"), default=50, min_value=1),
        parser_provider=get("PARSER_PROVIDER", "fake").strip().lower() or "fake",
        claude_bin=get("CLAUDE_BIN", "claude").strip() or "claude",
        claude_code_oauth_token=get("CLAUDE_CODE_OAUTH_TOKEN").strip(),
        claude_model=get("CLAUDE_MODEL").strip() or "claude-haiku-4-5-20251001",
        claude_timeout_seconds=parse_int(get("CLAUDE_TIMEOUT_SECONDS", "120"), default=120, min_value=30),
        claude_max_budget_usd=_parse_float(get("CLAUDE_MAX_BUDGET_USD", "0.12"), default=0.12, min_value=0),
        claude_system_prompt_mode=get("CLAUDE_SYSTEM_PROMPT_MODE", "replace").strip().lower() or "replace",
        allow_paid_api=parse_bool(get("ALLOW_PAID_API", "false")),
        stt_provider=get("STT_PROVIDER", "disabled").strip().lower() or "disabled",
        voice_dir=resolve_path(get("VOICE_DIR"), default=PROJECT_ROOT / "data" / "voice", base_dir=PROJECT_ROOT),
        openai_api_key=get("OPENAI_API_KEY").strip(),
        stt_openai_model=get("STT_OPENAI_MODEL", "gpt-4o-transcribe").strip() or "gpt-4o-transcribe",
        stt_language=get("STT_LANGUAGE", "ru").strip() or "ru",
        stt_prompt=get("STT_PROMPT").strip(),
        stt_timeout_seconds=parse_int(get("STT_TIMEOUT_SECONDS", "180"), default=180, min_value=10),
        stt_whisper_bin=get("STT_WHISPER_BIN", "whisper").strip() or "whisper",
        stt_whisper_model=get("STT_WHISPER_MODEL", "small").strip(),
        stt_whisper_cpp_bin=get("STT_WHISPER_CPP_BIN", "whisper-cli").strip() or "whisper-cli",
        stt_whisper_cpp_model=resolve_path(
            get("STT_WHISPER_CPP_MODEL"),
            default=PROJECT_ROOT / "tools" / "whisper.cpp" / "models" / "ggml-base.bin",
            base_dir=PROJECT_ROOT,
        ),
        ffmpeg_bin=get("FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg",
    )


def _parse_float(value: str, *, default: float, min_value: float) -> float:
    try:
        return max(min_value, float(value))
    except (TypeError, ValueError):
        return default
