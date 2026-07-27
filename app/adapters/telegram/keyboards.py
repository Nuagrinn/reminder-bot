from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.adapters.telegram.occurrence_list_view import OccurrenceListView
from app.features.events.context import context_action_url
from app.features.events.context import context_button_label
from app.features.events.context import normalize_event_contexts
from app.features.events.models import NotificationJobView, OccurrenceView


DONE_PREFIX = "done:"
OCCURRENCE_DETAIL_PREFIX = "occ_detail:"
LIST_PAGE_PREFIX = "list_page:"
SNOOZE_PREFIX = "snooze:"
HIDE_NOTIFICATION_PREFIX = "hide_notification:"
HIDE_MESSAGE_PREFIX = "hide_message:"
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


def confirmation_keyboard(pending_id: str, contexts=None) -> InlineKeyboardMarkup:
    rows = _context_rows(contexts)
    rows.extend(
        [
            [InlineKeyboardButton("Сохранить", callback_data=f"{CONFIRM_REMINDER_PREFIX}{pending_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{DISCARD_REMINDER_PREFIX}{pending_id}")],
            _hide_row("confirmation"),
        ]
    )
    return InlineKeyboardMarkup(
        rows
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
    rows.append(_hide_row("clarification"))
    return InlineKeyboardMarkup(rows)


def due_keyboard(job: NotificationJobView) -> InlineKeyboardMarkup:
    rows = _context_rows(job.contexts)
    rows.extend(
        [
            [InlineKeyboardButton("Готово", callback_data=f"{DONE_PREFIX}{job.occurrence_id}")],
            [
                InlineKeyboardButton("Напомнить +1ч", callback_data=f"{SNOOZE_PREFIX}{job.job_id}:60"),
                InlineKeyboardButton("На завтра", callback_data=f"{RESCHEDULE_QUICK_PREFIX}{job.occurrence_id}:occ:tomorrow"),
            ],
            [InlineKeyboardButton("Перенести", callback_data=f"{RESCHEDULE_MENU_PREFIX}{job.occurrence_id}")],
            [InlineKeyboardButton("Удалить", callback_data=f"{DELETE_MENU_PREFIX}{job.occurrence_id}")],
            [InlineKeyboardButton("Скрыть", callback_data=f"{HIDE_NOTIFICATION_PREFIX}{job.job_id}")],
        ]
    )
    return InlineKeyboardMarkup(
        rows
    )


def occurrence_list_keyboard(view: OccurrenceListView) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for index, item in enumerate(view.page_items, start=1):
        row.append(
            InlineKeyboardButton(
                str(index),
                callback_data=f"{OCCURRENCE_DETAIL_PREFIX}{item.occurrence_id}",
            )
        )
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if view.total_pages > 1:
        rows.append(_occurrence_list_pagination_row(view))
    rows.append(_hide_row("list"))
    return InlineKeyboardMarkup(rows)


def occurrence_detail_keyboard(item: OccurrenceView | str) -> InlineKeyboardMarkup:
    occurrence_id = item.occurrence_id if isinstance(item, OccurrenceView) else item
    rows = _context_rows(item.contexts if isinstance(item, OccurrenceView) else ())
    rows.extend(
        [
            [InlineKeyboardButton("Готово", callback_data=f"{DONE_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Перенести", callback_data=f"{RESCHEDULE_MENU_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Удалить", callback_data=f"{DELETE_MENU_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{DETAIL_CANCEL_PREFIX}{occurrence_id}")],
            _hide_row("detail"),
        ]
    )
    return InlineKeyboardMarkup(
        rows
    )


def delete_scope_keyboard(*, occurrence_id: str, event_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Только этот раз", callback_data=f"{DELETE_OCCURRENCE_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("С этого раза и дальше", callback_data=f"{DELETE_SERIES_FROM_PREFIX}{occurrence_id}")],
            [InlineKeyboardButton("Всю серию", callback_data=f"{CANCEL_EVENT_PREFIX}{event_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"{DELETE_CANCEL_PREFIX}{occurrence_id}")],
            _hide_row("delete"),
        ]
    )


def reschedule_scope_keyboard(*, occurrence_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Только этот раз", callback_data=f"{RESCHEDULE_SCOPE_PREFIX}{occurrence_id}:occ")],
            [InlineKeyboardButton("С этого раза и дальше", callback_data=f"{RESCHEDULE_SCOPE_PREFIX}{occurrence_id}:series")],
            [InlineKeyboardButton("Отмена", callback_data=f"{RESCHEDULE_CANCEL_PREFIX}{occurrence_id}")],
            _hide_row("reschedule_scope"),
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
            _hide_row("reschedule_options"),
        ]
    )


def daily_agenda_settings_keyboard(*, enabled: bool) -> InlineKeyboardMarkup:
    label = "Выключить" if enabled else "Включить"
    next_value = "off" if enabled else "on"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=f"{DAILY_AGENDA_TOGGLE_PREFIX}{next_value}")],
            _hide_row("daily_agenda"),
        ]
    )


def _hide_row(scope: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("Скрыть", callback_data=f"{HIDE_MESSAGE_PREFIX}{scope}")]


def _context_rows(contexts) -> list[list[InlineKeyboardButton]]:
    items = _coerce_contexts(contexts)
    rows: list[list[InlineKeyboardButton]] = []
    for item in items[:4]:
        url = context_action_url(item)
        if not url:
            continue
        rows.append([InlineKeyboardButton(context_button_label(item), url=url)])
    return rows


def _coerce_contexts(contexts) -> list:
    if not contexts:
        return []
    if isinstance(contexts, tuple):
        return list(contexts)
    if isinstance(contexts, list):
        if contexts and not isinstance(contexts[0], dict):
            return list(contexts)
        return normalize_event_contexts(contexts)
    return normalize_event_contexts(contexts)


def _occurrence_list_pagination_row(view: OccurrenceListView) -> list[InlineKeyboardButton]:
    current_page = view.current_page
    previous_page = max(0, current_page - 1)
    next_page = min(view.total_pages - 1, current_page + 1)
    return [
        InlineKeyboardButton("←", callback_data=_occurrence_page_callback(view, previous_page)),
        InlineKeyboardButton(
            f"{current_page + 1}/{view.total_pages}",
            callback_data=_occurrence_page_callback(view, current_page),
        ),
        InlineKeyboardButton("→", callback_data=_occurrence_page_callback(view, next_page)),
    ]


def _occurrence_page_callback(view: OccurrenceListView, page: int) -> str:
    return f"{LIST_PAGE_PREFIX}{view.kind}:{view.anchor_date:%Y%m%d}:{page}"


def _clarification_button_label(option: str) -> str:
    label = option.strip() or "Уточнить"
    label = f"{label[0].upper()}{label[1:]}" if label else "Уточнить"
    if len(label) > 34:
        label = f"{label[:31]}..."
    return label
