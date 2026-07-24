from __future__ import annotations

import json

from app.features.reminder_intake.agent import ReminderParseRequest


def build_system_prompt(request: ReminderParseRequest) -> str:
    return (
        "Ты парсер личных напоминаний для Telegram-бота.\n"
        "Пользователь пишет или говорит по-русски короткие команды: что сделать, "
        "когда, и иногда когда напомнить. Верни только JSON по schema.\n\n"
        f"NOW_LOCAL: {request.now.isoformat(timespec='seconds')}\n"
        f"TIMEZONE: {request.timezone}\n"
        f"DEFAULT_DAY_REMINDER_TIME: {request.default_day_reminder_time}\n"
        f"DEFAULT_TIMED_EVENT_OFFSET_MINUTES: {request.default_timed_event_offset_minutes}\n"
        f"DEFAULT_BIRTHDAY_OFFSETS_MINUTES: {request.default_birthday_offsets_minutes}\n\n"
        "Правила:\n"
        "- относительные даты считай от NOW_LOCAL;\n"
        "- если дата/время не названы, верни status='needs_clarification';\n"
        "- если дата есть, но времени нет, верни all_day=true и precision='date';\n"
        "- дефолтные уведомления не придумывай: если пользователь не назвал offset, "
        "notification_offsets оставь пустым;\n"
        "- для дней рождения используй event_type='birthday' и yearly recurrence;\n"
        "- для 'каждый вторник' используй weekly recurrence и weekday 'TU';\n"
        "- для 'каждого 25 числа' используй monthly recurrence и month_days=[25];\n"
        "- title пиши без слов 'надо', 'нужно', 'напомни';\n"
        "- если несколько событий, верни несколько items;\n"
        "- не веди диалог вне JSON.\n"
    )


def build_user_prompt(request: ReminderParseRequest) -> str:
    payload = {
        "raw_text": request.raw_text,
        "source_kind": request.source_kind,
    }
    return (
        "Разбери пользовательскую команду и верни JSON.\n\n"
        f"REQUEST_JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )

