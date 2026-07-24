from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


WEEKDAYS_RU = {
    "понедельник": 0,
    "понедельникa": 0,
    "понедельника": 0,
    "пн": 0,
    "вторник": 1,
    "вторника": 1,
    "вт": 1,
    "среду": 2,
    "среда": 2,
    "среды": 2,
    "ср": 2,
    "четверг": 3,
    "четверга": 3,
    "чт": 3,
    "пятницу": 4,
    "пятница": 4,
    "пятницы": 4,
    "пт": 4,
    "субботу": 5,
    "суббота": 5,
    "субботы": 5,
    "сб": 5,
    "воскресенье": 6,
    "воскресенья": 6,
    "вс": 6,
}

MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


@dataclass(frozen=True)
class RescheduleTarget:
    occurs_at: datetime
    all_day: bool


class RescheduleParseError(ValueError):
    pass


def parse_reschedule_target(
    text: str,
    *,
    now: datetime,
    current_occurs_at: datetime,
    default_day_hhmm: tuple[int, int],
    evening_hhmm: tuple[int, int],
) -> RescheduleTarget:
    raw = text.strip()
    low = raw.lower()
    if not low:
        raise RescheduleParseError("Напиши новую дату или время.")

    explicit_time = _extract_time(low, default_day_hhmm=default_day_hhmm, evening_hhmm=evening_hhmm)
    relative = _relative_target(low, now=now, explicit_time=explicit_time, default_day_hhmm=default_day_hhmm)
    if relative:
        return _ensure_future(relative, now=now)

    target_date = _extract_date(low, now=now)
    if target_date and explicit_time:
        return _ensure_future(RescheduleTarget(_combine(target_date, explicit_time), all_day=False), now=now)
    if target_date:
        return _ensure_future(RescheduleTarget(_all_day_at(target_date, default_day_hhmm), all_day=True), now=now)

    if explicit_time:
        candidate = _combine(current_occurs_at.date(), explicit_time)
        if candidate <= now:
            candidate = _combine(now.date(), explicit_time)
            if candidate <= now:
                candidate += timedelta(days=1)
        return RescheduleTarget(candidate.replace(second=0, microsecond=0), all_day=False)

    raise RescheduleParseError("Не понял новую дату или время. Например: завтра, в 18:30, через 2 часа.")


def quick_reschedule_target(
    action: str,
    *,
    now: datetime,
    current_occurs_at: datetime,
    current_all_day: bool,
    default_day_hhmm: tuple[int, int],
    evening_hhmm: tuple[int, int],
    relative_to_current: bool = False,
) -> RescheduleTarget:
    now_minute = now.replace(second=0, microsecond=0)
    if action == "plus_1h":
        base = current_occurs_at if relative_to_current else now_minute
        return RescheduleTarget(base.replace(second=0, microsecond=0) + timedelta(hours=1), all_day=False)
    if action == "plus_3h":
        base = current_occurs_at if relative_to_current else now_minute
        return RescheduleTarget(base.replace(second=0, microsecond=0) + timedelta(hours=3), all_day=False)
    if action == "evening":
        evening = _combine(now.date(), time(hour=evening_hhmm[0], minute=evening_hhmm[1]))
        if evening <= now_minute:
            evening += timedelta(days=1)
        return RescheduleTarget(evening, all_day=False)
    if action == "tomorrow":
        target_date = now.date() + timedelta(days=1)
        if current_all_day:
            return RescheduleTarget(_all_day_at(target_date, default_day_hhmm), all_day=True)
        return RescheduleTarget(_combine(target_date, current_occurs_at.time()), all_day=False)
    if action == "next_week":
        shifted = current_occurs_at.replace(second=0, microsecond=0) + timedelta(days=7)
        return RescheduleTarget(shifted, all_day=current_all_day)
    raise RescheduleParseError("Не понял быстрый вариант переноса.")


def _relative_target(
    low: str,
    *,
    now: datetime,
    explicit_time: time | None,
    default_day_hhmm: tuple[int, int],
) -> RescheduleTarget | None:
    match = re.search(
        r"\bчерез\s+(\d+|один|одну|два|две|три|четыре|пять|пару)\s+"
        r"(минуту|минут|минуты|час|часа|часов|день|дня|дней|неделю|недели|недель)\b",
        low,
    )
    if not match:
        return None
    amount = _amount(match.group(1))
    unit = match.group(2)
    if unit.startswith("минут"):
        return RescheduleTarget(now.replace(second=0, microsecond=0) + timedelta(minutes=amount), all_day=False)
    if unit.startswith("час"):
        return RescheduleTarget(now.replace(second=0, microsecond=0) + timedelta(hours=amount), all_day=False)
    if unit.startswith("недел"):
        target_date = now.date() + timedelta(days=amount * 7)
    else:
        target_date = now.date() + timedelta(days=amount)
    if explicit_time:
        return RescheduleTarget(_combine(target_date, explicit_time), all_day=False)
    return RescheduleTarget(_all_day_at(target_date, default_day_hhmm), all_day=True)


def _extract_date(low: str, *, now: datetime) -> date | None:
    if "послезавтра" in low:
        return now.date() + timedelta(days=2)
    if "завтра" in low:
        return now.date() + timedelta(days=1)
    if "сегодня" in low:
        return now.date()

    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", low)
    if iso_match:
        return _date_from_parts(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

    dotted = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", low)
    if dotted:
        day = int(dotted.group(1))
        month = int(dotted.group(2))
        year = _normalize_year(dotted.group(3), now=now)
        candidate = _date_from_parts(year, month, day)
        if dotted.group(3) is None and candidate < now.date():
            candidate = _date_from_parts(year + 1, month, day)
        return candidate

    month_match = re.search(r"\b(\d{1,2})\s+([а-яё]+)\b", low)
    if month_match and month_match.group(2) in MONTHS_RU:
        day = int(month_match.group(1))
        month = MONTHS_RU[month_match.group(2)]
        candidate = _date_from_parts(now.year, month, day)
        if candidate < now.date():
            candidate = _date_from_parts(now.year + 1, month, day)
        return candidate

    for word, weekday in WEEKDAYS_RU.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            return _next_weekday(now.date(), weekday, force_next="след" in low)
    return None


def _extract_time(
    low: str,
    *,
    default_day_hhmm: tuple[int, int],
    evening_hhmm: tuple[int, int],
) -> time | None:
    if re.search(r"\bутром\b", low):
        return time(hour=default_day_hhmm[0], minute=default_day_hhmm[1])
    if re.search(r"\bвечером\b|\bк вечеру\b", low):
        return time(hour=evening_hhmm[0], minute=evening_hhmm[1])
    if re.search(r"\bднем\b|\bднём\b", low):
        return time(hour=13, minute=0)

    match = re.search(r"(?:\bв\s*)?(\d{1,2})[:.](\d{2})\b", low)
    if match:
        return _time_from_parts(int(match.group(1)), int(match.group(2)))
    match = re.search(r"\bв\s+(\d{1,2})\b", low)
    if match:
        return _time_from_parts(int(match.group(1)), 0)
    if re.fullmatch(r"\s*\d{1,2}\s*", low):
        return _time_from_parts(int(low), 0)
    return None


def _ensure_future(target: RescheduleTarget, *, now: datetime) -> RescheduleTarget:
    if target.all_day:
        if target.occurs_at.date() < now.date():
            raise RescheduleParseError("Эта дата уже прошла.")
        return target
    if target.occurs_at <= now:
        raise RescheduleParseError("Это время уже прошло.")
    return target


def _next_weekday(start: date, weekday: int, *, force_next: bool) -> date:
    days = (weekday - start.weekday()) % 7
    if force_next and days == 0:
        days = 7
    return start + timedelta(days=days)


def _all_day_at(value: date, default_day_hhmm: tuple[int, int]) -> datetime:
    return _combine(value, time(hour=default_day_hhmm[0], minute=default_day_hhmm[1]))


def _combine(value: date, value_time: time) -> datetime:
    return datetime.combine(value, value_time).replace(second=0, microsecond=0)


def _date_from_parts(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise RescheduleParseError("Не похоже на корректную дату.") from exc


def _time_from_parts(hour: int, minute: int) -> time:
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise RescheduleParseError("Не похоже на корректное время.")
    return time(hour=hour, minute=minute)


def _normalize_year(value: str | None, *, now: datetime) -> int:
    if not value:
        return now.year
    year = int(value)
    if year < 100:
        return 2000 + year
    return year


def _amount(value: str) -> int:
    if value in {"один", "одну"}:
        return 1
    if value in {"два", "две", "пару"}:
        return 2
    if value == "три":
        return 3
    if value == "четыре":
        return 4
    if value == "пять":
        return 5
    return int(value)
