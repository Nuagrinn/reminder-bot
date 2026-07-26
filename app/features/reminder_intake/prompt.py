from __future__ import annotations

import json

from app.features.reminder_intake.agent import ReminderParseRequest


def build_system_prompt(request: ReminderParseRequest) -> str:
    return (
        "You are a strict parser for a personal Telegram reminder bot.\n"
        "The user writes short Russian text or voice transcripts. Parse: title, "
        "date/time, temporal profile, recurrence, and optional notification offset. Return only "
        "JSON matching the provided schema.\n\n"
        "Windows transport note: REQUEST_JSON is ASCII-safe JSON and Russian "
        "letters may be encoded as JSON unicode escapes. Decode those escapes as "
        "normal JSON before interpreting raw_text.\n\n"
        f"NOW_LOCAL: {request.now.isoformat(timespec='seconds')}\n"
        f"TIMEZONE: {request.timezone}\n"
        f"DEFAULT_DAY_REMINDER_TIME: {request.default_day_reminder_time}\n"
        f"DEFAULT_TIMED_EVENT_OFFSET_MINUTES: {request.default_timed_event_offset_minutes}\n"
        f"DEFAULT_BIRTHDAY_OFFSETS_MINUTES: {request.default_birthday_offsets_minutes}\n\n"
        "Rules:\n"
        "- resolve relative dates from NOW_LOCAL;\n"
        "- temporal_profile is the primary classification for notification policy;\n"
        "- event_type is secondary compatibility metadata; keep it broad: task, "
        "calendar_event, deadline, birthday, anniversary, or habit;\n"
        "- use temporal_profile='moment_reminder' when the command means remind "
        "at the target moment itself, especially relative delays like 'in 2 hours';\n"
        "- use temporal_profile='exact_time' for a real event/task scheduled at "
        "a concrete date and time;\n"
        "- use temporal_profile='day_task' for a task attached to a date but "
        "without exact time;\n"
        "- use temporal_profile='deadline' for 'by/until/due before' phrasing;\n"
        "- use temporal_profile='time_window' for a start/end window; put the "
        "window start in start_at and mention the end in description if needed;\n"
        "- use temporal_profile='recurring_exact_time' when recurrence has time;\n"
        "- use temporal_profile='recurring_day_task' when recurrence has no time;\n"
        "- use temporal_profile='annual_date' for yearly dates like birthdays;\n"
        "- use temporal_profile='floating' only when no date/time can be found;\n"
        "- return all dates and start_at in local TIMEZONE without timezone suffix;\n"
        "- for exact datetime use start_at as YYYY-MM-DDTHH:MM:00;\n"
        "- if no date/time is stated, return status='needs_clarification';\n"
        "- if date is stated but time is not, use all_day=true and precision='date';\n"
        "- if date and time are stated, use all_day=false and precision='datetime';\n"
        "- if a month/day date has already passed this year, choose the nearest future date;\n"
        "- do not invent default notifications: if the user did not state an offset, "
        "leave notification_offsets=[];\n"
        "- explicit offsets like 'za 2 chasa', 'za den', 'za 30 minut' must become "
        "minutes_before with source='explicit';\n"
        "- birthdays use event_type='birthday', temporal_profile='annual_date' "
        "and yearly recurrence;\n"
        "- Russian phrases meaning 'every other day' or 'every two days' "
        "(unicode examples: \\u0434\\u0435\\u043d\\u044c \\u0447\\u0435\\u0440\\u0435\\u0437 "
        "\\u0434\\u0435\\u043d\\u044c, \\u043a\\u0430\\u0436\\u0434\\u044b\\u0435 \\u0434\\u0432\\u0430 "
        "\\u0434\\u043d\\u044f) use daily recurrence interval=2;\n"
        "- Russian phrase meaning 'every day' uses daily recurrence interval=1;\n"
        "- Russian phrase meaning 'once every two weeks' uses weekly recurrence interval=2;\n"
        "- Russian phrase meaning 'every Tuesday' uses weekly recurrence weekday 'TU';\n"
        "- Russian phrase meaning 'every 25th day of month' uses monthly recurrence month_days=[25];\n"
        "- do not use custom_rrule: if the recurrence cannot be represented as "
        "daily/weekly/monthly/yearly, return needs_clarification;\n"
        "- preserve the language and script of raw_text in title and description; "
        "if raw_text is Russian/Cyrillic, title must be Russian/Cyrillic; "
        "do not translate titles to English;\n"
        "- title must omit helper words such as 'nado', 'nuzhno', 'napomni';\n"
        "- title must omit date, time, recurrence words, and notification offset words;\n"
        "- if several events are present, return several items;\n"
        "- do not write any prose outside JSON.\n\n"
        "Examples:\n"
        "- '25 July at 15:30 pay bill' -> once, date='2026-07-25', "
        "time='15:30', start_at='2026-07-25T15:30:00', temporal_profile='exact_time'.\n"
        "- 'tomorrow top up card' -> once, date=tomorrow, time=null, "
        "all_day=true, temporal_profile='day_task', notification_offsets=[].\n"
        "- 'in 2 hours check oven' -> once with exact start_at and "
        "temporal_profile='moment_reminder'.\n"
        "- 'every two days check mail' -> recurring daily interval=2 and "
        "temporal_profile='recurring_day_task'.\n"
        "- 'every Tuesday at 9 update report' -> recurring weekly weekday TU, "
        "time='09:00', temporal_profile='recurring_exact_time'.\n"
        "- Russian '\\u0441\\u0435\\u0433\\u043e\\u0434\\u043d\\u044f "
        "\\u0432\\u0435\\u0447\\u0435\\u0440\\u043e\\u043c "
        "\\u043d\\u0430\\u0434\\u043e "
        "\\u0437\\u0430\\u043a\\u0430\\u0437\\u0430\\u0442\\u044c "
        "\\u043a\\u0440\\u0435\\u0430\\u0442\\u0438\\u043d' -> "
        "title='\\u0417\\u0430\\u043a\\u0430\\u0437\\u0430\\u0442\\u044c "
        "\\u043a\\u0440\\u0435\\u0430\\u0442\\u0438\\u043d', not English.\n"
    )


def build_user_prompt(request: ReminderParseRequest) -> str:
    payload = {
        "raw_text": request.raw_text,
        "source_kind": request.source_kind,
    }
    return (
        "Parse the user command and return JSON matching the schema.\n\n"
        f"REQUEST_JSON:\n{json.dumps(payload, ensure_ascii=True)}"
    )
