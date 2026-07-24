from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.features.events.models import NotificationJobView


DONE_PREFIX = "done:"
SNOOZE_PREFIX = "snooze:"
CANCEL_EVENT_PREFIX = "cancel_event:"
DELETE_MENU_PREFIX = "delete_menu:"
DELETE_OCCURRENCE_PREFIX = "delete_occurrence:"
DELETE_SERIES_FROM_PREFIX = "delete_series_from:"
DELETE_CANCEL_PREFIX = "delete_cancel:"
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
            [InlineKeyboardButton("Удалить", callback_data=f"{DELETE_MENU_PREFIX}{job.occurrence_id}")],
        ]
    )


def delete_scope_keyboard(*, occurrence_id: str, event_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Только этот раз", callback_data=f"{DELETE_OCCURRENCE_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("С этого раза и дальше", callback_data=f"{DELETE_SERIES_FROM_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Всю серию", callback_data=f"{CANCEL_EVENT_PREFIX}{event_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{DELETE_CANCEL_PREFIX}{occurrence_id}")],
        ]
    )
