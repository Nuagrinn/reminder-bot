from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from assistant_toolkit.speech import SpeechToTextError
from assistant_toolkit.telegram import split_message

from app.adapters.telegram.formatters import (
    format_done,
    format_due_notification,
    format_event_deleted,
    format_intake_result,
    format_occurrence_list,
    format_snoozed,
    format_start,
)
from app.adapters.telegram.keyboards import (
    CANCEL_EVENT_PREFIX,
    DONE_PREFIX,
    SNOOZE_PREFIX,
    due_keyboard,
    main_keyboard,
)
from app.config import Settings, load_settings
from app.core.time import local_now
from app.features.reminder_intake.agent import ReminderParseRequest
from app.services import AppServices


log = logging.getLogger(__name__)


def _services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return context.application.bot_data["services"]


def _owner_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    return int(context.application.bot_data["owner_id"])


async def _reject_non_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    owner_id = _owner_id(context)
    if not update.effective_user or update.effective_user.id != owner_id:
        if update.message:
            await update.message.reply_text("Это личный бот.")
        elif update.callback_query:
            await update.callback_query.answer("Это личный бот.", show_alert=True)
        return True
    return False


async def _answer_long(update: Update, text: str, **kwargs) -> None:
    if update.message:
        for chunk in split_message(text):
            await update.message.reply_text(chunk, **kwargs)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(text, **kwargs)


def _parse_request(settings: Settings, raw_text: str, source_kind: str, now: datetime) -> ReminderParseRequest:
    return ReminderParseRequest(
        raw_text=raw_text,
        source_kind=source_kind,
        now=now,
        timezone=settings.timezone,
        default_day_reminder_time=settings.default_day_reminder_time,
        default_timed_event_offset_minutes=settings.default_timed_event_offset_minutes,
        default_birthday_offsets_minutes=settings.default_birthday_offsets_minutes,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    await _answer_long(update, format_start(), parse_mode=ParseMode.HTML, reply_markup=main_keyboard())


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    services = _services(context)
    now = local_now(services.settings.timezone)
    start_at = datetime.combine(now.date(), datetime.min.time())
    end_at = start_at + timedelta(days=1)
    items = await asyncio.to_thread(
        services.events.list_occurrences,
        start_at=start_at,
        end_at=end_at,
        limit=50,
    )
    await _answer_long(
        update,
        format_occurrence_list(items, title="Сегодня", empty_text="На сегодня напоминаний нет."),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    services = _services(context)
    now = local_now(services.settings.timezone)
    await asyncio.to_thread(services.events.materialize_all, now=now)
    items = await asyncio.to_thread(services.events.upcoming, now=now, limit=20)
    await _answer_long(
        update,
        format_occurrence_list(items, title="Ближайшие", empty_text="Ближайших напоминаний нет."),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    text = " ".join(context.args).strip()
    if not text:
        await _answer_long(update, "Напиши текст после /add или просто отправь сообщение.", reply_markup=main_keyboard())
        return
    await _create_from_text(update, context, text, source_kind="text")


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    text = (update.message.text or "").strip() if update.message else ""
    if not text:
        return
    if text in ("📆 Сегодня", "Сегодня"):
        await today(update, context)
        return
    if text in ("📋 Ближайшие", "Ближайшие"):
        await upcoming(update, context)
        return
    if text in ("❔ Помощь", "Помощь"):
        await start(update, context)
        return
    await _create_from_text(update, context, text, source_kind="text")


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    if not update.message or not update.message.voice:
        return
    services = _services(context)
    voice = update.message.voice
    started = perf_counter()
    wait_message = await update.message.reply_text("Распознаю голосовое...")
    audio_path = _voice_audio_path(services, voice.file_id)
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        await tg_file.download_to_drive(str(audio_path))
        transcript = await asyncio.to_thread(services.speech.transcribe, audio_path)
    except SpeechToTextError as exc:
        await wait_message.edit_text(f"Не смог распознать голосовое.\n\n{exc}")
        return
    except Exception:
        log.exception("Voice processing failed")
        await wait_message.edit_text("Не смог обработать голосовое. Попробуй текстом.")
        return
    await wait_message.edit_text(f"Распознал: {transcript}\n\nПланирую...")
    await _create_from_text(update, context, transcript, source_kind="voice")
    log.info("Voice processed elapsed=%.2fs", perf_counter() - started)


def _voice_audio_path(services: AppServices, file_id: str) -> Path:
    services.settings.voice_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() else "-" for ch in file_id)[:16] or "voice"
    stamp = local_now(services.settings.timezone).strftime("%Y%m%d-%H%M%S")
    return services.settings.voice_dir / f"{stamp}-{safe}.oga"


async def _create_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, *, source_kind: str) -> None:
    services = _services(context)
    now = local_now(services.settings.timezone)
    request = _parse_request(services.settings, text, source_kind, now)
    try:
        result = await asyncio.to_thread(services.intake.ingest, request)
    except Exception as exc:
        log.exception("Reminder intake failed")
        await _answer_long(update, f"Не смог разобрать напоминание.\n\n{exc}", reply_markup=main_keyboard())
        return
    occurrences = await asyncio.to_thread(services.events.upcoming, now=now, limit=20)
    own_occurrences = [item for item in occurrences if item.event_id in set(result.event_ids)]
    await _answer_long(
        update,
        format_intake_result(result, own_occurrences),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def notify_due(context: ContextTypes.DEFAULT_TYPE) -> None:
    services = _services(context)
    owner_id = _owner_id(context)
    now = local_now(services.settings.timezone)
    await asyncio.to_thread(services.events.materialize_all, now=now)
    jobs = await asyncio.to_thread(services.events.due_jobs, now=now, limit=20)
    for job in jobs:
        try:
            message = await context.bot.send_message(
                chat_id=owner_id,
                text=format_due_notification(job),
                parse_mode=ParseMode.HTML,
                reply_markup=due_keyboard(job),
            )
        except Exception as exc:
            log.exception("Failed to send notification job_id=%s", job.job_id)
            await asyncio.to_thread(services.events.mark_job_failed, job.job_id, reason=str(exc), now=now)
            continue
        await asyncio.to_thread(
            services.events.mark_job_sent,
            job.job_id,
            message_id=message.message_id,
            now=now,
        )


async def done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    occurrence_id = (query.data or "").removeprefix(DONE_PREFIX)
    services = _services(context)
    now = local_now(services.settings.timezone)
    await asyncio.to_thread(services.events.complete_occurrence, occurrence_id, now=now)
    await query.answer("Готово")
    await query.edit_message_text(format_done())


async def snooze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    payload = (query.data or "").removeprefix(SNOOZE_PREFIX)
    job_id, raw_minutes = payload.split(":", 1)
    minutes = int(raw_minutes)
    services = _services(context)
    now = local_now(services.settings.timezone)
    await asyncio.to_thread(services.events.snooze_job, job_id, minutes=minutes, now=now)
    await query.answer("Перенесено")
    await query.edit_message_text(format_snoozed(minutes))


async def cancel_event_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    event_id = (query.data or "").removeprefix(CANCEL_EVENT_PREFIX)
    services = _services(context)
    now = local_now(services.settings.timezone)
    await asyncio.to_thread(services.events.cancel_event, event_id, now=now)
    await query.answer("Удалено")
    await query.edit_message_text(format_event_deleted())


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    await _answer_long(update, "Пока понимаю текст и голосовые напоминания.", reply_markup=main_keyboard())


def build_application(settings: Settings, services: AppServices) -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if settings.tg_user_id is None:
        raise RuntimeError("TELEGRAM_OWNER_ID is required")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["services"] = services
    app.bot_data["owner_id"] = settings.tg_user_id

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("upcoming", upcoming))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CallbackQueryHandler(done_callback, pattern=f"^{DONE_PREFIX}"))
    app.add_handler(CallbackQueryHandler(snooze_callback, pattern=f"^{SNOOZE_PREFIX}"))
    app.add_handler(CallbackQueryHandler(cancel_event_callback, pattern=f"^{CANCEL_EVENT_PREFIX}"))
    app.add_handler(MessageHandler(filters.VOICE, voice_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_handler(MessageHandler(filters.ALL, fallback))

    if app.job_queue is None:
        log.warning("JobQueue unavailable. Install python-telegram-bot[job-queue].")
    else:
        app.job_queue.run_repeating(
            notify_due,
            interval=settings.reminder_tick_seconds,
            first=10,
            name="due-reminders",
        )
    return app


def run_bot() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    settings = load_settings()
    services = AppServices(settings)
    app = build_application(settings, services)
    log.info("Starting reminder bot polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    run_bot()


if __name__ == "__main__":
    main()
