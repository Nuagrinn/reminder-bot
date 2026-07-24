from __future__ import annotations

from datetime import datetime

from assistant_toolkit.telegram import h

from app.features.events.models import NotificationJobView, OccurrenceView
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
        "Команды: /today, /upcoming, /add"
    )


def format_intake_result(result: IntakeResult, occurrences: list[OccurrenceView]) -> str:
    payload = result.parse_result.payload
    if payload.get("status") == "needs_clarification":
        clarification = payload.get("clarification") or {}
        question = str(clarification.get("question") or "Нужно уточнение.")
        options = clarification.get("options") or []
        lines = ["<b>Нужно уточнить</b>", "", h(question)]
        if options:
            lines.extend(["", "<b>Варианты</b>"])
            lines.extend(f"- {_h_option(item)}" for item in options)
        return "\n".join(lines)

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


def _h_option(value: object) -> str:
    return h(value)

