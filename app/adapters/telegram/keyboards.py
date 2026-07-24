from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.features.events.models import NotificationJobView


DONE_PREFIX = "done:"
SNOOZE_PREFIX = "snooze:"
CANCEL_EVENT_PREFIX = "cancel_event:"
CONFIRM_REMINDER_PREFIX = "confirm_reminder:"
DISCARD_REMINDER_PREFIX = "discard_reminder:"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["📆 Сегодня", "🗓 Неделя"], ["📋 Ближайшие", "🗂 Месяц"], ["❔ Помощь"]],
        resize_keyboard=True,
    )


def confirmation_keyboard(pending_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Сохранить", callback_data=f"{CONFIRM_REMINDER_PREFIX}{pending_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{DISCARD_REMINDER_PREFIX}{pending_id}")],
        ]
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
