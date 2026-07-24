from __future__ import annotations

from datetime import datetime
from typing import Any

from assistant_toolkit.telegram import h

from app.features.events.models import NotificationJobView, OccurrenceView
from app.features.reminder_intake.agent import ReminderParseResult
from app.features.reminder_intake.service import IntakeResult


def format_start() -> str:
    return (
        "<b>Reminder Bot</b>\n\n"
        "Напиши или отправь голосом, что и когда напомнить.\n\n"
        "Примеры:\n"
        "- <code>надо завтра пополнить карту наличкой</code>\n"
        "- <code>через 2 часа проверить духовку</code>\n"
        "- <code>каждый вторник обновить отчет по калориям</code>\n"
        "- <code>12 августа день рождения Маши</code>\n\n"
        "Команды: /today, /week, /month, /upcoming, /add"
    )


def format_parse_confirmation(parse_result: ReminderParseResult) -> str:
    payload = parse_result.payload
    if payload.get("status") == "needs_clarification":
        return _format_clarification(payload)

    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    if payload.get("status") != "ok" or not items:
        return "Не смог уверенно собрать напоминание. Попробуй написать дату точнее."

    lines = ["<b>Проверь напоминание</b>", ""]
    for index, item in enumerate(items[:5], start=1):
        prefix = f"{index}. " if len(items) > 1 else ""
        lines.append(f"{prefix}<b>{h(_item_title(item))}</b>")
        lines.append(f"Когда: <code>{h(_schedule_label(item))}</code>")
        repeat = _recurrence_label(item)
        if repeat:
            lines.append(f"Повтор: <code>{h(repeat)}</code>")
        lines.append(f"Напомню: <code>{h(_notification_label(item))}</code>")
        if assumptions := item.get("assumptions"):
            if isinstance(assumptions, list) and assumptions:
                lines.append(f"Заметка: {h(str(assumptions[0]))}")
        lines.append("")
    return "\n".join(lines).strip()


def format_intake_result(result: IntakeResult, occurrences: list[OccurrenceView]) -> str:
    payload = result.parse_result.payload
    if payload.get("status") == "needs_clarification":
        return _format_clarification(payload)

    if not result.event_ids:
        return "Не смог создать напоминание. Попробуй написать дату точнее."

    lines = ["<b>Запланировал</b>", ""]
    for occurrence in occurrences[:10]:
        lines.append(f"• <b>{h(occurrence.title)}</b>")
        lines.append(f"  Событие: <code>{_date_time_label(occurrence.occurs_at)}</code>")
        if occurrence.next_notify_at:
            lines.append(f"  Напомню: <code>{_date_time_label(occurrence.next_notify_at)}</code>")
        lines.append("")
    return "\n".join(lines).strip()


def format_occurrence_list(items: list[OccurrenceView], *, title: str, empty_text: str) -> str:
    if not items:
        return empty_text
    lines = [f"<b>{h(title)}</b>", f"Всего: <b>{len(items)}</b>", ""]
    current_date = ""
    for item in items:
        day = item.occurs_at.strftime("%d.%m.%Y")
        if day != current_date:
            current_date = day
            lines.append(f"<b>{day}</b>")
        time_label = item.occurs_at.strftime("%H:%M")
        lines.append(f"<code>{time_label}</code> · {h(item.title)}")
    return "\n".join(lines)


def format_due_notification(job: NotificationJobView) -> str:
    return (
        "<b>Напоминание</b>\n\n"
        f"<b>{h(job.title)}</b>\n"
        f"План: <code>{_date_time_label(job.occurs_at)}</code>"
    )


def format_event_deleted() -> str:
    return "Напоминание удалено."


def format_done() -> str:
    return "Готово, отметил."


def format_snoozed(minutes: int) -> str:
    if minutes % 1440 == 0:
        return "Хорошо, напомню завтра."
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"Хорошо, напомню через {hours} ч."
    return f"Хорошо, напомню через {minutes} мин."


def _date_time_label(value: datetime) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


def _format_clarification(payload: dict[str, Any]) -> str:
    clarification = payload.get("clarification") or {}
    question = str(clarification.get("question") or "Нужно уточнение.")
    options = clarification.get("options") or []
    lines = ["<b>Нужно уточнить</b>", "", h(question)]
    if options:
        lines.extend(["", "<b>Варианты</b>"])
        lines.extend(f"- {_h_option(item)}" for item in options)
    return "\n".join(lines)


def _item_title(item: dict[str, Any]) -> str:
    return str(item.get("title") or "Напоминание")


def _schedule_label(item: dict[str, Any]) -> str:
    schedule = item.get("schedule") if isinstance(item.get("schedule"), dict) else {}
    start_at = str(schedule.get("start_at") or "")
    if start_at:
        try:
            return _date_time_label(datetime.fromisoformat(start_at))
        except ValueError:
            pass

    date = str(schedule.get("date") or "")
    time = str(schedule.get("time") or "")
    if date:
        label = _date_label(date)
        if time:
            label = f"{label} {time}"
        return label
    if time:
        return time
    return "по дате из текста"


def _recurrence_label(item: dict[str, Any]) -> str:
    schedule = item.get("schedule") if isinstance(item.get("schedule"), dict) else {}
    recurrence = schedule.get("recurrence") if isinstance(schedule.get("recurrence"), dict) else {}
    frequency = str(recurrence.get("frequency") or "none")
    if frequency == "none":
        return ""
    interval = int(recurrence.get("interval") or 1)
    every = "" if interval == 1 else f"каждые {interval} "
    if frequency == "daily":
        return f"{every}день"
    if frequency == "weekly":
        weekdays = recurrence.get("weekdays") or []
        days = ", ".join(_weekday_label(str(day)) for day in weekdays) if weekdays else "неделю"
        return f"{every}неделю: {days}"
    if frequency == "monthly":
        month_days = recurrence.get("month_days") or []
        if month_days:
            return f"{every}месяц: {', '.join(str(day) for day in month_days)} числа"
        return f"{every}месяц"
    if frequency == "yearly":
        months = recurrence.get("months") or []
        month_days = recurrence.get("month_days") or []
        if months and month_days:
            return f"каждый год: {month_days[0]:02d}.{months[0]:02d}"
        return "каждый год"
    return frequency


def _notification_label(item: dict[str, Any]) -> str:
    offsets = item.get("notification_offsets") or []
    if not offsets:
        return "по умолчанию"
    labels = []
    for offset in offsets:
        if not isinstance(offset, dict):
            continue
        minutes = int(offset.get("minutes_before") or 0)
        if minutes == 0:
            labels.append("в момент события")
        elif minutes % 1440 == 0:
            labels.append(f"за {minutes // 1440} дн.")
        elif minutes % 60 == 0:
            labels.append(f"за {minutes // 60} ч.")
        else:
            labels.append(f"за {minutes} мин.")
    return ", ".join(labels) if labels else "по умолчанию"


def _date_label(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


def _weekday_label(value: str) -> str:
    return {
        "MO": "пн",
        "TU": "вт",
        "WE": "ср",
        "TH": "чт",
        "FR": "пт",
        "SA": "сб",
        "SU": "вс",
    }.get(value, value)


def _h_option(value: object) -> str:
    return h(value)
