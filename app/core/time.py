from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def app_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def local_now(timezone: str) -> datetime:
    return datetime.now(app_timezone(timezone)).replace(tzinfo=None, microsecond=0)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_time(value: str | None, *, default: tuple[int, int]) -> time:
    if value:
        raw_hour, raw_minute = value.split(":", 1)
        return time(hour=int(raw_hour), minute=int(raw_minute))
    return time(hour=default[0], minute=default[1])


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat(timespec="seconds")

