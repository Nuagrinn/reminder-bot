from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.features.events.models import NotificationJobView


DONE_PREFIX = "done:"
SNOOZE_PREFIX = "snooze:"
CANCEL_EVENT_PREFIX = "cancel_event:"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["📆 Сегодня", "📋 Ближайшие"], ["❔ Помощь"]],
        resize_keyboard=True,
    )


def due_keyboard(job: NotificationJobView) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Готово", callback_data=f"{DONE_PREFIX}{job.occurrence_id}")],
            [
                InlineKeyboardButton("Через 1 час", callback_data=f"{SNOOZE_PREFIX}{job.job_id}:60"),
                InlineKeyboardButton("Завтра", callback_data=f"{SNOOZE_PREFIX}{job.job_id}:1440"),
            ],
            [InlineKeyboardButton("Удалить", callback_data=f"{CANCEL_EVENT_PREFIX}{job.event_id}")],
        ]
    )

