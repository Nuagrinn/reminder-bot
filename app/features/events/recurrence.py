from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time, timedelta


WEEKDAY_INDEX = {
    "MO": 0,
    "TU": 1,
    "WE": 2,
    "TH": 3,
    "FR": 4,
    "SA": 5,
    "SU": 6,
}


def occurrence_datetimes(
    *,
    recurrence: dict,
    start_date: date | None,
    event_time: time,
    now: datetime,
    horizon_days: int,
) -> list[datetime]:
    frequency = str(recurrence.get("frequency") or "none")
    interval = max(1, int(recurrence.get("interval") or 1))
    horizon_date = now.date() + timedelta(days=horizon_days)

    if frequency == "none":
        if not start_date:
            return []
        return [datetime.combine(start_date, event_time)]

    dates = _recurring_dates(
        frequency=frequency,
        recurrence=recurrence,
        start_date=start_date,
        from_date=now.date(),
        until_date=horizon_date,
        interval=interval,
    )
    return [datetime.combine(item, event_time) for item in dates]


def _recurring_dates(
    *,
    frequency: str,
    recurrence: dict,
    start_date: date | None,
    from_date: date,
    until_date: date,
    interval: int,
) -> Iterator[date]:
    if frequency == "daily":
        cursor = max(start_date or from_date, from_date)
        while cursor <= until_date:
            yield cursor
            cursor += timedelta(days=interval)
        return

    if frequency == "weekly":
        weekdays = [
            WEEKDAY_INDEX[item]
            for item in recurrence.get("weekdays", [])
            if item in WEEKDAY_INDEX
        ] or [(start_date or from_date).weekday()]
        cursor = from_date
        while cursor <= until_date:
            if cursor.weekday() in weekdays and (not start_date or cursor >= start_date):
                yield cursor
            cursor += timedelta(days=1)
        return

    if frequency == "monthly":
        month_days = [int(item) for item in recurrence.get("month_days", []) if 1 <= int(item) <= 31]
        if not month_days and start_date:
            month_days = [start_date.day]
        yield from _monthly_dates(
            month_days=month_days or [from_date.day],
            from_date=from_date,
            until_date=until_date,
            start_date=start_date,
            interval=interval,
        )
        return

    if frequency == "yearly":
        months = [int(item) for item in recurrence.get("months", []) if 1 <= int(item) <= 12]
        month_days = [int(item) for item in recurrence.get("month_days", []) if 1 <= int(item) <= 31]
        if start_date:
            months = months or [start_date.month]
            month_days = month_days or [start_date.day]
        yield from _yearly_dates(
            months=months or [from_date.month],
            month_days=month_days or [from_date.day],
            from_date=from_date,
            until_date=until_date,
            start_date=start_date,
            interval=interval,
        )


def _monthly_dates(
    *,
    month_days: list[int],
    from_date: date,
    until_date: date,
    start_date: date | None,
    interval: int,
) -> Iterator[date]:
    year = from_date.year
    month = from_date.month
    step = 0
    while date(year, month, 1) <= until_date.replace(day=1):
        if step % interval == 0:
            for day in sorted(month_days):
                try:
                    candidate = date(year, month, day)
                except ValueError:
                    continue
                if from_date <= candidate <= until_date and (not start_date or candidate >= start_date):
                    yield candidate
        year, month = _next_month(year, month)
        step += 1


def _yearly_dates(
    *,
    months: list[int],
    month_days: list[int],
    from_date: date,
    until_date: date,
    start_date: date | None,
    interval: int,
) -> Iterator[date]:
    for year in range(from_date.year, until_date.year + 1):
        if (year - from_date.year) % interval != 0:
            continue
        for month in sorted(months):
            for day in sorted(month_days):
                try:
                    candidate = date(year, month, day)
                except ValueError:
                    continue
                if from_date <= candidate <= until_date and (not start_date or candidate >= start_date):
                    yield candidate


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1

