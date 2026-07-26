from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil

from app.features.events.models import OccurrenceView


DEFAULT_LIST_PAGE_SIZE = 10
WEEKDAY_LABELS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


@dataclass(frozen=True)
class OccurrenceListView:
    kind: str
    title: str
    empty_text: str
    anchor_date: date
    items: list[OccurrenceView]
    range_start: date | None = None
    range_end: date | None = None
    page: int = 0
    page_size: int = DEFAULT_LIST_PAGE_SIZE
    force_year: bool = False

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def effective_page_size(self) -> int:
        return max(1, self.page_size)

    @property
    def total_pages(self) -> int:
        if not self.items:
            return 1
        return max(1, ceil(len(self.items) / self.effective_page_size))

    @property
    def current_page(self) -> int:
        return min(max(0, self.page), self.total_pages - 1)

    @property
    def page_items(self) -> list[OccurrenceView]:
        if not self.items:
            return []
        start = self.current_page * self.effective_page_size
        end = start + self.effective_page_size
        return self.items[start:end]

    @property
    def page_start_number(self) -> int:
        if not self.items:
            return 0
        return self.current_page * self.effective_page_size + 1

    @property
    def page_end_number(self) -> int:
        if not self.items:
            return 0
        return min(self.page_start_number + len(self.page_items) - 1, self.total_count)

    @property
    def crosses_year(self) -> bool:
        if not self.range_start or not self.range_end:
            return False
        return self.range_start.year != _inclusive_range_end(self.range_start, self.range_end).year

    @property
    def show_year(self) -> bool:
        return (
            self.force_year
            or self.crosses_year
            or any(item.occurs_at.date().year != self.anchor_date.year for item in self.items)
        )

    @property
    def suppress_single_day_group(self) -> bool:
        return self.kind in {"today", "agenda"} and _all_items_on_anchor_date(self)


def occurrence_list_header(view: OccurrenceListView) -> str:
    if view.kind in {"today", "agenda"}:
        return f"{view.title} · {_header_day_label(view.anchor_date, show_year=view.crosses_year)}"
    if view.kind in {"week", "month"} and view.range_start and view.range_end:
        return f"{view.title} · {_date_range_label(view.range_start, view.range_end)}"
    if view.kind == "upcoming" and view.range_start:
        return f"{view.title} · с {_compact_date(view.range_start, show_year=view.crosses_year)}"
    return view.title


def occurrence_group_label(value: date, view: OccurrenceListView) -> str:
    if view.show_year:
        label = f"{value:%d.%m.%Y} · {weekday_label(value)}"
    else:
        label = f"{weekday_label(value)} {value:%d.%m}"

    relative = relative_day_label(value, anchor_date=view.anchor_date)
    if relative:
        label = f"{label} · {relative}"
    return label


def weekday_label(value: date) -> str:
    return WEEKDAY_LABELS[value.weekday()]


def relative_day_label(value: date, *, anchor_date: date) -> str:
    delta = (value - anchor_date).days
    if delta == 0:
        return "сегодня"
    if delta == 1:
        return "завтра"
    if delta == -1:
        return "вчера"
    return ""


def _date_range_label(start: date, end: date) -> str:
    inclusive_end = _inclusive_range_end(start, end)
    show_year = start.year != inclusive_end.year
    return f"{_compact_date(start, show_year=show_year)}-{_compact_date(inclusive_end, show_year=show_year)}"


def _header_day_label(value: date, *, show_year: bool) -> str:
    if show_year:
        return f"{value:%d.%m.%Y} · {weekday_label(value)}"
    return f"{weekday_label(value)} {value:%d.%m}"


def _compact_date(value: date, *, show_year: bool) -> str:
    return value.strftime("%d.%m.%Y") if show_year else value.strftime("%d.%m")


def _inclusive_range_end(start: date, end: date) -> date:
    if end <= start:
        return start
    return end - timedelta(days=1)


def _all_items_on_anchor_date(view: OccurrenceListView) -> bool:
    if not view.items:
        return True
    return all(item.occurs_at.date() == view.anchor_date for item in view.page_items)
