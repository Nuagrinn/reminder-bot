from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from assistant_toolkit.speech import SpeechToTextError, build_speech_to_text

from app.config import load_settings
from app.core.db import build_database
from app.core.time import local_now
from app.features.reminder_intake.agent import ReminderParseRequest
from app.services import AppServices


def _request(settings, text: str, source_kind: str, now: datetime) -> ReminderParseRequest:
    return ReminderParseRequest(
        raw_text=text,
        source_kind=source_kind,
        now=now,
        timezone=settings.timezone,
        default_day_reminder_time=settings.default_day_reminder_time,
        default_timed_event_offset_minutes=settings.default_timed_event_offset_minutes,
        default_birthday_offsets_minutes=settings.default_birthday_offsets_minutes,
    )


def cmd_migrate(args) -> None:
    settings = load_settings()
    db = build_database(settings.db_path)
    result = db.migrate()
    print(json.dumps({"applied": result.applied, "skipped": result.skipped}, ensure_ascii=False))


def cmd_parse_preview(args) -> None:
    settings = load_settings()
    services = AppServices(settings)
    now = local_now(settings.timezone)
    result = services.intake.parse(_request(settings, args.text, "text", now))
    print(json.dumps(result.payload, ensure_ascii=False, indent=2))


def cmd_add(args) -> None:
    settings = load_settings()
    services = AppServices(settings)
    now = local_now(settings.timezone)
    result = services.intake.ingest(_request(settings, args.text, "text", now))
    print(json.dumps({"event_ids": result.event_ids, "payload": result.parse_result.payload}, ensure_ascii=False, indent=2))


def cmd_today(args) -> None:
    settings = load_settings()
    services = AppServices(settings)
    now = local_now(settings.timezone)
    start_at = datetime.combine(now.date(), datetime.min.time())
    end_at = start_at + timedelta(days=1)
    for item in services.events.list_occurrences(start_at=start_at, end_at=end_at, limit=args.limit):
        print(f"{item.occurs_at:%Y-%m-%d %H:%M}\t{item.title}\t{item.event_id}")


def cmd_upcoming(args) -> None:
    settings = load_settings()
    services = AppServices(settings)
    now = local_now(settings.timezone)
    services.events.materialize_all(now=now)
    for item in services.events.upcoming(now=now, limit=args.limit):
        notify = item.next_notify_at.strftime("%Y-%m-%d %H:%M") if item.next_notify_at else "-"
        print(f"{item.occurs_at:%Y-%m-%d %H:%M}\t{notify}\t{item.title}\t{item.event_id}")


def cmd_due(args) -> None:
    settings = load_settings()
    services = AppServices(settings)
    now = local_now(settings.timezone)
    for item in services.events.due_jobs(now=now, limit=args.limit):
        print(f"{item.notify_at:%Y-%m-%d %H:%M}\t{item.title}\t{item.job_id}")


def _tool_exists(value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    if path.is_absolute() or any(sep in value for sep in ("/", "\\")):
        return path.exists()
    return shutil.which(value) is not None


def cmd_stt_check(args) -> None:
    settings = load_settings()
    if args.provider:
        settings = replace(settings, stt_provider=args.provider)

    print(f"STT provider: {settings.stt_provider}")
    print(f"- ffmpeg: {'OK' if _tool_exists(settings.ffmpeg_bin) else 'not found'} ({settings.ffmpeg_bin})")
    if settings.stt_provider == "whisper_cpp":
        print(
            "- whisper.cpp bin: "
            f"{'OK' if _tool_exists(settings.stt_whisper_cpp_bin) else 'not found'} "
            f"({settings.stt_whisper_cpp_bin})"
        )
        print(
            "- whisper.cpp model: "
            f"{'OK' if settings.stt_whisper_cpp_model.exists() else 'not found'} "
            f"({settings.stt_whisper_cpp_model})"
        )
    elif settings.stt_provider == "whisper_cli":
        print(
            "- whisper CLI: "
            f"{'OK' if _tool_exists(settings.stt_whisper_bin) else 'not found'} "
            f"({settings.stt_whisper_bin})"
        )
        print(f"- whisper model: {settings.stt_whisper_model or 'default'}")
    elif settings.stt_provider == "openai":
        print(f"- OPENAI_API_KEY: {'OK' if settings.openai_api_key else 'missing'}")


def cmd_stt_preview(args) -> None:
    if args.provider:
        os.environ["STT_PROVIDER"] = args.provider
    settings = load_settings()
    audio_path = Path(args.audio)
    try:
        transcript = build_speech_to_text(settings).transcribe(audio_path)
    except SpeechToTextError as exc:
        raise SystemExit(f"STT failed: {exc}") from exc
    print(transcript)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reminder-bot-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser("migrate")
    migrate.set_defaults(func=cmd_migrate)

    preview = sub.add_parser("parse-preview")
    preview.add_argument("text")
    preview.set_defaults(func=cmd_parse_preview)

    add = sub.add_parser("add")
    add.add_argument("text")
    add.set_defaults(func=cmd_add)

    today = sub.add_parser("today")
    today.add_argument("--limit", type=int, default=50)
    today.set_defaults(func=cmd_today)

    upcoming = sub.add_parser("upcoming")
    upcoming.add_argument("--limit", type=int, default=20)
    upcoming.set_defaults(func=cmd_upcoming)

    due = sub.add_parser("due")
    due.add_argument("--limit", type=int, default=20)
    due.set_defaults(func=cmd_due)

    stt_check = sub.add_parser("stt-check")
    stt_check.add_argument(
        "--provider",
        choices=["disabled", "whisper_cpp", "whisper_cli", "openai"],
        help="Override STT_PROVIDER for this check",
    )
    stt_check.set_defaults(func=cmd_stt_check)

    stt_preview = sub.add_parser("stt-preview")
    stt_preview.add_argument("audio")
    stt_preview.add_argument(
        "--provider",
        choices=["disabled", "whisper_cpp", "whisper_cli", "openai"],
        help="Override STT_PROVIDER for this run",
    )
    stt_preview.set_defaults(func=cmd_stt_preview)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
