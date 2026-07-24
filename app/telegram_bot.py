from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

from telegram import Message, Update
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
    format_daily_agenda,
    format_delete_cancelled,
    format_delete_scope_question,
    format_due_notification,
    format_event_deleted,
    format_intake_result,
    format_occurrence_detail,
    format_occurrence_list,
    format_occurrence_deleted,
    format_parse_confirmation,
    format_series_deleted,
    format_series_stopped,
    format_snoozed,
    format_start,
)
from app.adapters.telegram.keyboards import (
    CANCEL_EVENT_PREFIX,
    CLARIFY_CANCEL_PREFIX,
    CLARIFY_PREFIX,
    CONFIRM_REMINDER_PREFIX,
    DELETE_CANCEL_PREFIX,
    DELETE_MENU_PREFIX,
    DELETE_OCCURRENCE_PREFIX,
    DELETE_SERIES_FROM_PREFIX,
    DISCARD_REMINDER_PREFIX,
    DONE_PREFIX,
    OCCURRENCE_DETAIL_PREFIX,
    SNOOZE_PREFIX,
    clarification_keyboard,
    confirmation_keyboard,
    delete_scope_keyboard,
    due_keyboard,
    main_keyboard,
    occurrence_detail_keyboard,
    occurrence_list_keyboard,
)
from app.config import Settings, load_settings
from app.core.ids import new_id
from app.core.time import local_now
from app.features.reminder_intake.agent import ReminderParseRequest, ReminderParseResult
from app.features.reminder_intake.clarification import clarification_options_from_payload
from app.services import AppServices


log = logging.getLogger(__name__)
PENDING_TTL_MINUTES = 30


@dataclass(frozen=True)
class PendingReminder:
    request: ReminderParseRequest
    parse_result: ReminderParseResult
    created_at: datetime


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    for logger_name in ("httpx", "httpcore", "telegram", "telegram.ext"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _services(context: ContextTypes.DEFAULT_TYPE) -> AppServices:
    return context.application.bot_data["services"]


def _owner_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    return int(context.application.bot_data["owner_id"])


def _pending_reminders(context: ContextTypes.DEFAULT_TYPE) -> dict[str, PendingReminder]:
    store = context.application.bot_data.setdefault("pending_reminders", {})
    return store


def _cleanup_pending(context: ContextTypes.DEFAULT_TYPE, *, now: datetime) -> None:
    store = _pending_reminders(context)
    expired_at = now - timedelta(minutes=PENDING_TTL_MINUTES)
    for pending_id, pending in list(store.items()):
        if pending.created_at < expired_at:
            store.pop(pending_id, None)


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


async def _safe_reply_text(message: Message, text: str, **kwargs) -> Message | None:
    try:
        return await message.reply_text(text, **kwargs)
    except Exception:
        log.warning("Failed to send Telegram status message", exc_info=True)
        return None


async def _safe_edit_message(message: Message | None, text: str, **kwargs) -> None:
    if not message:
        return
    try:
        await message.edit_text(text, **kwargs)
    except Exception:
        log.warning("Failed to edit Telegram status message", exc_info=True)


async def _safe_delete_message(message: Message | None) -> None:
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        log.warning("Failed to delete Telegram status message", exc_info=True)


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
    await _show_range(update, context, title="Сегодня", days=1, empty_text="На сегодня напоминаний нет.")


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    await _show_range(update, context, title="Неделя", days=7, empty_text="На неделю напоминаний нет.")


async def month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    await _show_range(update, context, title="Месяц", days=31, empty_text="На месяц напоминаний нет.", limit=100)


async def _show_range(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    title: str,
    days: int,
    empty_text: str,
    limit: int = 50,
) -> None:
    services = _services(context)
    now = local_now(services.settings.timezone)
    items = await _occurrences_for_range(services, now=now, days=days, limit=limit)
    await _answer_long(
        update,
        format_occurrence_list(items, title=title, empty_text=empty_text),
        parse_mode=ParseMode.HTML,
        reply_markup=occurrence_list_keyboard(items) if items else main_keyboard(),
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
        reply_markup=occurrence_list_keyboard(items) if items else main_keyboard(),
    )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    text = " ".join(context.args).strip()
    if not text:
        await _answer_long(update, "Напиши текст после /add или просто отправь сообщение.", reply_markup=main_keyboard())
        return
    await _preview_from_text(update, context, text, source_kind="text")


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    text = (update.message.text or "").strip() if update.message else ""
    if not text:
        return
    if text in ("📆 Сегодня", "Сегодня"):
        await today(update, context)
        return
    if text in ("🗓 Неделя", "Неделя"):
        await week(update, context)
        return
    if text in ("🗂 Месяц", "Месяц"):
        await month(update, context)
        return
    if text in ("📋 Ближайшие", "Ближайшие"):
        await upcoming(update, context)
        return
    if text in ("❔ Помощь", "Помощь"):
        await start(update, context)
        return
    await _preview_from_text(update, context, text, source_kind="text")


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    if not update.message or not update.message.voice:
        return
    services = _services(context)
    voice = update.message.voice
    started = perf_counter()
    log.info("Voice message received file_id=%s duration=%s", _safe_file_id(voice.file_id), voice.duration)
    wait_message = await _safe_reply_text(update.message, "Распознаю голосовое...")
    audio_path = _voice_audio_path(services, voice.file_id)
    try:
        log.info("Voice download started file_id=%s", _safe_file_id(voice.file_id))
        tg_file = await context.bot.get_file(voice.file_id)
        await tg_file.download_to_drive(str(audio_path))
        log.info("Voice transcription started path=%s", audio_path.name)
        transcript = await asyncio.to_thread(services.speech.transcribe, audio_path)
    except SpeechToTextError as exc:
        await _safe_voice_failure(update, wait_message, f"Не смог распознать голосовое.\n\n{exc}")
        return
    except Exception:
        log.exception("Voice processing failed")
        await _safe_voice_failure(update, wait_message, "Не смог обработать голосовое. Попробуй текстом.")
        return
    log.info("Voice transcribed elapsed=%.2fs transcript=%r", perf_counter() - started, _short_log_text(transcript))
    await _safe_edit_message(wait_message, f"Распознал: {_short_log_text(transcript, 700)}\n\nРазбираю...")
    try:
        await _preview_from_text(update, context, transcript, source_kind="voice")
    except Exception:
        log.exception("Voice preview failed after transcription")
        await _safe_edit_message(wait_message, "Распознал голосовое, но не смог отправить результат в Telegram.")
        return
    await _safe_delete_message(wait_message)
    log.info("Voice processed elapsed=%.2fs", perf_counter() - started)


async def _safe_voice_failure(update: Update, wait_message: Message | None, text: str) -> None:
    if wait_message:
        await _safe_edit_message(wait_message, text)
    elif update.message:
        await _safe_reply_text(update.message, text)


def _voice_audio_path(services: AppServices, file_id: str) -> Path:
    services.settings.voice_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() else "-" for ch in file_id)[:16] or "voice"
    stamp = local_now(services.settings.timezone).strftime("%Y%m%d-%H%M%S")
    return services.settings.voice_dir / f"{stamp}-{safe}.oga"


def _safe_file_id(file_id: str) -> str:
    if len(file_id) <= 10:
        return file_id
    return f"{file_id[:6]}...{file_id[-4:]}"


async def _preview_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, *, source_kind: str) -> None:
    services = _services(context)
    now = local_now(services.settings.timezone)
    _cleanup_pending(context, now=now)
    request = _parse_request(services.settings, text, source_kind, now)
    try:
        parse_result = await asyncio.to_thread(services.intake.parse, request)
    except Exception as exc:
        log.exception("Reminder intake failed")
        await _answer_long(update, f"Не смог разобрать напоминание.\n\n{exc}", reply_markup=main_keyboard())
        return

    pending_id = new_id("pending_")
    _pending_reminders(context)[pending_id] = PendingReminder(
        request=request,
        parse_result=parse_result,
        created_at=now,
    )
    keyboard = _pending_inline_keyboard(pending_id, parse_result)
    await _answer_long(
        update,
        format_parse_confirmation(parse_result),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard or main_keyboard(),
    )


def _can_confirm(parse_result: ReminderParseResult) -> bool:
    payload = parse_result.payload
    return payload.get("intent") == "create" and payload.get("status") == "ok" and bool(payload.get("items"))


def _needs_clarification(parse_result: ReminderParseResult) -> bool:
    return parse_result.payload.get("status") == "needs_clarification"


def _pending_inline_keyboard(pending_id: str, parse_result: ReminderParseResult):
    if _can_confirm(parse_result):
        return confirmation_keyboard(pending_id)
    if _needs_clarification(parse_result):
        return clarification_keyboard(pending_id, _clarification_options(parse_result))
    return None


def _clarification_options(parse_result: ReminderParseResult) -> list[str]:
    return clarification_options_from_payload(parse_result.payload)


def _apply_clarification(raw_text: str, option: str) -> str:
    raw_text = raw_text.strip()
    option = option.strip()
    if not raw_text:
        return option
    if not option:
        return raw_text
    return f"{raw_text} {option}"


def _short_log_text(value: str, limit: int = 160) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


async def _occurrences_for_range(
    services: AppServices,
    *,
    now: datetime,
    days: int,
    limit: int,
):
    start_at = datetime.combine(now.date(), datetime.min.time())
    end_at = start_at + timedelta(days=days)
    await asyncio.to_thread(services.events.materialize_all, now=now)
    return await asyncio.to_thread(
        services.events.list_occurrences,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
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


async def send_daily_agenda(context: ContextTypes.DEFAULT_TYPE) -> None:
    services = _services(context)
    owner_id = _owner_id(context)
    now = local_now(services.settings.timezone)
    items = await _occurrences_for_range(
        services,
        now=now,
        days=1,
        limit=services.settings.daily_agenda_limit,
    )
    try:
        await context.bot.send_message(
            chat_id=owner_id,
            text=format_daily_agenda(items),
            parse_mode=ParseMode.HTML,
            reply_markup=occurrence_list_keyboard(items) if items else main_keyboard(),
        )
    except Exception:
        log.exception("Failed to send daily agenda")


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


async def occurrence_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    occurrence_id = (query.data or "").removeprefix(OCCURRENCE_DETAIL_PREFIX)
    services = _services(context)
    try:
        occurrence = await asyncio.to_thread(services.events.get_occurrence, occurrence_id)
    except Exception:
        log.exception("Occurrence detail failed")
        await query.answer("Не нашел напоминание", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        format_occurrence_detail(occurrence),
        parse_mode=ParseMode.HTML,
        reply_markup=occurrence_detail_keyboard(occurrence.occurrence_id),
    )


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
    await query.edit_message_text(format_series_deleted())


async def delete_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    occurrence_id = (query.data or "").removeprefix(DELETE_MENU_PREFIX)
    services = _services(context)
    now = local_now(services.settings.timezone)
    try:
        event = await asyncio.to_thread(services.events.get_event_for_occurrence, occurrence_id)
    except Exception:
        log.exception("Delete menu failed")
        await query.answer("Не нашел событие", show_alert=True)
        return
    if not services.events.is_recurring(event):
        await asyncio.to_thread(services.events.cancel_event, event.id, now=now)
        await query.answer("Удалено")
        await query.edit_message_text(format_event_deleted())
        return
    await query.answer("Выбери вариант")
    await query.edit_message_text(
        format_delete_scope_question(event.title),
        parse_mode=ParseMode.HTML,
        reply_markup=delete_scope_keyboard(occurrence_id=occurrence_id, event_id=event.id),
    )


async def delete_occurrence_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    occurrence_id = (query.data or "").removeprefix(DELETE_OCCURRENCE_PREFIX)
    services = _services(context)
    now = local_now(services.settings.timezone)
    await asyncio.to_thread(services.events.cancel_occurrence, occurrence_id, now=now)
    await query.answer("Пропущено")
    await query.edit_message_text(format_occurrence_deleted())


async def delete_series_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    occurrence_id = (query.data or "").removeprefix(DELETE_SERIES_FROM_PREFIX)
    services = _services(context)
    now = local_now(services.settings.timezone)
    await asyncio.to_thread(services.events.cancel_series_from_occurrence, occurrence_id, now=now)
    await query.answer("Остановлено")
    await query.edit_message_text(format_series_stopped())


async def delete_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    await query.answer("Отмена")
    await query.edit_message_text(format_delete_cancelled())


async def confirm_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    pending_id = (query.data or "").removeprefix(CONFIRM_REMINDER_PREFIX)
    services = _services(context)
    now = local_now(services.settings.timezone)
    _cleanup_pending(context, now=now)
    pending = _pending_reminders(context).pop(pending_id, None)
    if not pending:
        await query.answer("Черновик устарел", show_alert=True)
        await query.edit_message_text("Черновик напоминания устарел. Отправь команду еще раз.")
        return

    try:
        result = await asyncio.to_thread(
            services.intake.create_from_parse_result,
            pending.request,
            pending.parse_result,
        )
    except Exception as exc:
        log.exception("Reminder confirmation failed")
        await query.answer("Не сохранил", show_alert=True)
        await query.edit_message_text(f"Не смог сохранить напоминание.\n\n{exc}")
        return

    occurrences = await asyncio.to_thread(services.events.upcoming, now=now, limit=20)
    own_occurrences = [item for item in occurrences if item.event_id in set(result.event_ids)]
    await query.answer("Сохранено")
    await query.edit_message_text(
        format_intake_result(result, own_occurrences),
        parse_mode=ParseMode.HTML,
    )


async def discard_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    pending_id = (query.data or "").removeprefix(DISCARD_REMINDER_PREFIX)
    _pending_reminders(context).pop(pending_id, None)
    await query.answer("Отменено")
    await query.edit_message_text("Ок, не сохраняю.")


async def clarify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    payload = (query.data or "").removeprefix(CLARIFY_PREFIX)
    try:
        pending_id, raw_option_index = payload.rsplit(":", 1)
        option_index = int(raw_option_index)
    except ValueError:
        log.warning("Malformed clarification callback payload=%r", payload)
        await query.answer("Не понял вариант", show_alert=True)
        return

    services = _services(context)
    now = local_now(services.settings.timezone)
    _cleanup_pending(context, now=now)
    pending = _pending_reminders(context).get(pending_id)
    if not pending:
        log.info("Clarification callback expired pending_id=%s", pending_id)
        await query.answer("Черновик устарел", show_alert=True)
        await query.edit_message_text("Черновик напоминания устарел. Отправь команду еще раз.")
        return

    options = _clarification_options(pending.parse_result)
    if option_index < 0 or option_index >= len(options):
        log.warning(
            "Clarification option not found pending_id=%s option_index=%s options=%s",
            pending_id,
            option_index,
            options,
        )
        await query.answer("Вариант устарел", show_alert=True)
        return

    option = options[option_index]
    resolved_text = _apply_clarification(pending.request.raw_text, option)
    request = _parse_request(services.settings, resolved_text, pending.request.source_kind, now)
    log.info(
        "Reminder clarification selected pending_id=%s option=%r original=%r resolved=%r",
        pending_id,
        option,
        _short_log_text(pending.request.raw_text),
        _short_log_text(resolved_text),
    )
    try:
        parse_result = await asyncio.to_thread(services.intake.parse, request)
    except Exception as exc:
        log.exception("Reminder clarification parse failed pending_id=%s", pending_id)
        await query.answer("Не разобрал", show_alert=True)
        await query.edit_message_text(f"Не смог разобрать уточнение.\n\n{exc}")
        return

    _pending_reminders(context)[pending_id] = PendingReminder(
        request=request,
        parse_result=parse_result,
        created_at=now,
    )
    await query.answer("Уточнил")
    await query.edit_message_text(
        format_parse_confirmation(parse_result),
        parse_mode=ParseMode.HTML,
        reply_markup=_pending_inline_keyboard(pending_id, parse_result),
    )


async def clarify_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_non_owner(update, context):
        return
    query = update.callback_query
    pending_id = (query.data or "").removeprefix(CLARIFY_CANCEL_PREFIX)
    _pending_reminders(context).pop(pending_id, None)
    log.info("Reminder clarification cancelled pending_id=%s", pending_id)
    await query.answer("Отменено")
    await query.edit_message_text("Ок, не сохраняю.")


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
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("upcoming", upcoming))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CallbackQueryHandler(confirm_reminder_callback, pattern=f"^{CONFIRM_REMINDER_PREFIX}"))
    app.add_handler(CallbackQueryHandler(discard_reminder_callback, pattern=f"^{DISCARD_REMINDER_PREFIX}"))
    app.add_handler(CallbackQueryHandler(clarify_callback, pattern=f"^{CLARIFY_PREFIX}"))
    app.add_handler(CallbackQueryHandler(clarify_cancel_callback, pattern=f"^{CLARIFY_CANCEL_PREFIX}"))
    app.add_handler(CallbackQueryHandler(occurrence_detail_callback, pattern=f"^{OCCURRENCE_DETAIL_PREFIX}"))
    app.add_handler(CallbackQueryHandler(done_callback, pattern=f"^{DONE_PREFIX}"))
    app.add_handler(CallbackQueryHandler(snooze_callback, pattern=f"^{SNOOZE_PREFIX}"))
    app.add_handler(CallbackQueryHandler(delete_menu_callback, pattern=f"^{DELETE_MENU_PREFIX}"))
    app.add_handler(CallbackQueryHandler(delete_occurrence_callback, pattern=f"^{DELETE_OCCURRENCE_PREFIX}"))
    app.add_handler(CallbackQueryHandler(delete_series_from_callback, pattern=f"^{DELETE_SERIES_FROM_PREFIX}"))
    app.add_handler(CallbackQueryHandler(delete_cancel_callback, pattern=f"^{DELETE_CANCEL_PREFIX}"))
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
        if settings.daily_agenda_enabled:
            hour, minute = settings.daily_agenda_hhmm
            app.job_queue.run_daily(
                send_daily_agenda,
                time=time(hour=hour, minute=minute, tzinfo=ZoneInfo(settings.timezone)),
                name="daily-agenda",
            )
    return app


def run_bot() -> None:
    configure_logging()
    settings = load_settings()
    services = AppServices(settings)
    app = build_application(settings, services)
    log.info("Starting reminder bot polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=5)


def main() -> None:
    run_bot()


if __name__ == "__main__":
    main()
