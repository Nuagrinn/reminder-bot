from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.features.events.models import NotificationJobView
from app.features.events.models import OccurrenceView


DONE_PREFIX = "done:"
OCCURRENCE_DETAIL_PREFIX = "occ_detail:"
SNOOZE_PREFIX = "snooze:"
HIDE_NOTIFICATION_PREFIX = "hide_notification:"
CANCEL_EVENT_PREFIX = "cancel_event:"
DELETE_MENU_PREFIX = "delete_menu:"
DELETE_OCCURRENCE_PREFIX = "delete_occurrence:"
DELETE_SERIES_FROM_PREFIX = "delete_series_from:"
DELETE_CANCEL_PREFIX = "delete_cancel:"
RESCHEDULE_MENU_PREFIX = "reschedule_menu:"
RESCHEDULE_SCOPE_PREFIX = "reschedule_scope:"
RESCHEDULE_QUICK_PREFIX = "reschedule_quick:"
RESCHEDULE_CUSTOM_PREFIX = "reschedule_custom:"
RESCHEDULE_CANCEL_PREFIX = "reschedule_cancel:"
DAILY_AGENDA_TOGGLE_PREFIX = "daily_agenda_toggle:"
CONFIRM_REMINDER_PREFIX = "confirm_reminder:"
DISCARD_REMINDER_PREFIX = "discard_reminder:"
CLARIFY_PREFIX = "clarify:"
CLARIFY_CANCEL_PREFIX = "clarify_cancel:"
DETAIL_CANCEL_PREFIX = "detail_cancel:"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["📆 Сегодня", "🗓 Неделя"],
            ["📋 Ближайшие", "🗂 Месяц"],
            ["🎂 Ежегодные", "🌅 Утро"],
            ["❔ Помощь"],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def confirmation_keyboard(pending_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Сохранить", callback_data=f"{CONFIRM_REMINDER_PREFIX}{pending_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{DISCARD_REMINDER_PREFIX}{pending_id}")],
        ]
    )


def clarification_keyboard(pending_id: str, options: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    option_row: list[InlineKeyboardButton] = []
    for index, option in enumerate(options[:4]):
        option_row.append(
            InlineKeyboardButton(
                _clarification_button_label(option),
                callback_data=f"{CLARIFY_PREFIX}{pending_id}:{index}",
            )
        )
        if len(option_row) == 2:
            rows.append(option_row)
            option_row = []
    if option_row:
        rows.append(option_row)
    rows.append([InlineKeyboardButton("Отмена", callback_data=f"{CLARIFY_CANCEL_PREFIX}{pending_id}")])
    return InlineKeyboardMarkup(rows)


def due_keyboard(job: NotificationJobView) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Готово", callback_data=f"{DONE_PREFIX}{job.occurrence_id}")],
            [
                InlineKeyboardButton("Через 1 час", callback_data=f"{SNOOZE_PREFIX}{job.job_id}:60"),
                InlineKeyboardButton("Завтра", callback_data=f"{SNOOZE_PREFIX}{job.job_id}:1440"),
            ],
            [InlineKeyboardButton("Перенести", callback_data=f"{RESCHEDULE_MENU_PREFIX}{job.occurrence_id}")],
            [InlineKeyboardButton("Удалить", callback_data=f"{DELETE_MENU_PREFIX}{job.occurrence_id}")],
            [InlineKeyboardButton("Скрыть", callback_data=f"{HIDE_NOTIFICATION_PREFIX}{job.job_id}")],
        ]
    )


def occurrence_list_keyboard(items: list[OccurrenceView]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, item in enumerate(items[:100], start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    _occurrence_button_label(index, item),
                    callback_data=f"{OCCURRENCE_DETAIL_PREFIX}{item.occurrence_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def occurrence_detail_keyboard(occurrence_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Готово", callback_data=f"{DONE_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Перенести", callback_data=f"{RESCHEDULE_MENU_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Удалить", callback_data=f"{DELETE_MENU_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{DETAIL_CANCEL_PREFIX}{occurrence_id}")],
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


def reschedule_scope_keyboard(*, occurrence_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Только этот раз", callback_data=f"{RESCHEDULE_SCOPE_PREFIX}{occurrence_id}:occ")],
            [InlineKeyboardButton("С этого раза и дальше", callback_data=f"{RESCHEDULE_SCOPE_PREFIX}{occurrence_id}:series")],
            [InlineKeyboardButton("Отмена", callback_data=f"{RESCHEDULE_CANCEL_PREFIX}{occurrence_id}")],
        ]
    )


def reschedule_options_keyboard(*, occurrence_id: str, scope: str) -> InlineKeyboardMarkup:
    prefix = f"{occurrence_id}:{scope}:"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("+1 час", callback_data=f"{RESCHEDULE_QUICK_PREFIX}{prefix}plus_1h"),
                InlineKeyboardButton("+3 часа", callback_data=f"{RESCHEDULE_QUICK_PREFIX}{prefix}plus_3h"),
            ],
            [
                InlineKeyboardButton("Вечером", callback_data=f"{RESCHEDULE_QUICK_PREFIX}{prefix}evening"),
                InlineKeyboardButton("Завтра", callback_data=f"{RESCHEDULE_QUICK_PREFIX}{prefix}tomorrow"),
            ],
            [InlineKeyboardButton("Через неделю", callback_data=f"{RESCHEDULE_QUICK_PREFIX}{prefix}next_week")],
            [InlineKeyboardButton("Выбрать дату/время", callback_data=f"{RESCHEDULE_CUSTOM_PREFIX}{occurrence_id}:{scope}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{RESCHEDULE_CANCEL_PREFIX}{occurrence_id}")],
        ]
    )


def daily_agenda_settings_keyboard(*, enabled: bool) -> InlineKeyboardMarkup:
    label = "Выключить" if enabled else "Включить"
    next_value = "off" if enabled else "on"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"{DAILY_AGENDA_TOGGLE_PREFIX}{next_value}")]]
    )


def _occurrence_button_label(index: int, item: OccurrenceView) -> str:
    title = item.title
    if len(title) > 34:
        title = f"{title[:31]}..."
    time_label = "день" if item.all_day else item.occurs_at.strftime("%H:%M")
    return f"{index}. {time_label} · {title}"


def _clarification_button_label(option: str) -> str:
    label = option.strip() or "Уточнить"
    label = f"{label[0].upper()}{label[1:]}" if label else "Уточнить"
    if len(label) > 34:
        label = f"{label[:31]}..."
    return label
