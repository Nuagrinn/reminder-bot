from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from assistant_toolkit.llm import StructuredClaudeRunner

from app.features.events.context import normalize_event_contexts
from app.features.events.context import strip_context_from_title
from app.features.notifications.policy import VALID_TEMPORAL_PROFILES, derive_temporal_profile
from app.features.reminder_intake.clarification import normalize_clarification
from app.features.reminder_intake.clarification import normalize_payload_clarification
from app.features.reminder_intake.schema import PROMPT_VERSION, REMINDER_JSON_SCHEMA


WEEKDAYS_RU = {
    "понедельник": "MO",
    "понедельникам": "MO",
    "вторник": "TU",
    "вторникам": "TU",
    "среду": "WE",
    "средам": "WE",
    "четверг": "TH",
    "четвергам": "TH",
    "пятницу": "FR",
    "пятницам": "FR",
    "субботу": "SA",
    "субботам": "SA",
    "воскресенье": "SU",
    "воскресеньям": "SU",
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
class ReminderParseRequest:
    raw_text: str
    source_kind: str
    now: datetime
    timezone: str
    default_day_reminder_time: str
    default_timed_event_offset_minutes: int
    default_birthday_offsets_minutes: list[int]


@dataclass(frozen=True)
class ReminderParseResult:
    payload: dict[str, Any]
    provider: str
    model: str
    prompt_version: str = PROMPT_VERSION
    stdout: str = ""


class ReminderParserError(RuntimeError):
    pass


class ReminderParserAgent(Protocol):
    provider: str
    model: str
    prompt_version: str

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        ...


class FakeReminderParserAgent:
    provider = "fake"
    model = "fake"
    prompt_version = "fake-reminder-parser-v1"

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        payload = fake_parse_payload(request)
        return ReminderParseResult(
            payload=payload,
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
        )


class ClaudeCliReminderParserAgent:
    provider = "claude_cli"
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        *,
        claude_bin: str,
        oauth_token: str,
        model: str,
        timeout_seconds: int,
        max_budget_usd: float,
        system_prompt_mode: str,
        allow_paid_api: bool,
    ):
        self.model = model
        self.runner = StructuredClaudeRunner(
            claude_bin=claude_bin,
            oauth_token=oauth_token,
            model=model,
            timeout_seconds=timeout_seconds,
            max_budget_usd=max_budget_usd,
            system_prompt_mode=system_prompt_mode,
            allow_paid_api=allow_paid_api,
        )

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        from app.features.reminder_intake.prompt import build_system_prompt, build_user_prompt

        try:
            result = self.runner.run(
                system_prompt=build_system_prompt(request),
                user_prompt=build_user_prompt(request),
                json_schema=REMINDER_JSON_SCHEMA,
                expected_keys=(),
            )
        except Exception as exc:
            raise ReminderParserError(str(exc)) from exc
        payload = normalize_claude_payload(result.payload, request)
        return ReminderParseResult(
            payload=payload,
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            stdout=result.stdout,
        )


def fake_parse_payload(request: ReminderParseRequest) -> dict[str, Any]:
    text = request.raw_text.strip()
    low = text.lower()
    if not text:
        return _clarification(text, "Что нужно напомнить?", [])

    if low in {"ближайшие", "покажи ближайшие"}:
        return _base(text, intent="list", status="ok", items=[])

    schedule = None
    event_type = "task"
    recurrence = _recurrence_none()
    all_day = True
    title_source = text
    temporal_profile = "floating"

    daily_interval = _daily_interval(low)
    if daily_interval:
        time_text = _extract_time(low)
        first_date = _recurring_start_date(request=request, time_text=time_text)
        all_day = time_text is None
        schedule = {
            "kind": "recurring",
            "timezone": request.timezone,
            "all_day": all_day,
            "start_at": f"{first_date.isoformat()}T{time_text}:00" if time_text else None,
            "date": first_date.isoformat(),
            "time": time_text,
            "precision": "datetime" if time_text else "date",
            "recurrence": {
                **_recurrence_none(),
                "frequency": "daily",
                "interval": daily_interval,
            },
        }
        event_type = "habit"
        temporal_profile = "recurring_exact_time" if time_text else "recurring_day_task"
        title_source = _strip_recurrence_words(text)

    if schedule is None and "кажд" in low:
        for word, weekday in WEEKDAYS_RU.items():
            if word in low:
                time_text = _extract_time(low)
                schedule = {
                    "kind": "recurring",
                    "timezone": request.timezone,
                    "all_day": time_text is None,
                    "start_at": None,
                    "date": None,
                    "time": time_text,
                    "precision": "datetime" if time_text else "date",
                    "recurrence": {**_recurrence_none(), "frequency": "weekly", "weekdays": [weekday]},
                }
                event_type = "habit"
                temporal_profile = "recurring_exact_time" if time_text else "recurring_day_task"
                title_source = _remove_patterns(low, [r"кажд\w+\s+\w+"])
                break

    birthday_match = re.search(r"(\d{1,2})\s+([а-яё]+).*день\s+рожд", low)
    if birthday_match:
        day = int(birthday_match.group(1))
        month = MONTHS_RU.get(birthday_match.group(2), request.now.month)
        first_date = _next_date(day=day, month=month, now=request.now)
        schedule = {
            "kind": "recurring",
            "timezone": request.timezone,
            "all_day": True,
            "start_at": None,
            "date": first_date.date().isoformat(),
            "time": None,
            "precision": "date",
            "recurrence": {
                **_recurrence_none(),
                "frequency": "yearly",
                "months": [month],
                "month_days": [day],
            },
        }
        event_type = "birthday"
        temporal_profile = "annual_date"
        title_source = _birthday_title(text)

    if schedule is None:
        target = _one_off_datetime(low, request.now)
        if target:
            all_day = target["time"] is None
            schedule = {
                "kind": "once",
                "timezone": request.timezone,
                "all_day": all_day,
                "start_at": target["start_at"],
                "date": target["date"],
                "time": target["time"],
                "precision": "datetime" if target["time"] else "date",
                "recurrence": recurrence,
            }
            temporal_profile = str(target.get("temporal_profile") or ("exact_time" if target["time"] else "day_task"))
            title_source = _strip_time_words(text)

    if schedule is None:
        return _clarification(text, "Когда напомнить?", ["сегодня", "завтра", "через час"])

    item = {
        "client_ref": "item_1",
        "title": _title(title_source),
        "description": "",
        "context": normalize_event_contexts(None, raw_text=text, include_extracted=True),
        "event_type": event_type,
        "temporal_profile": temporal_profile,
        "priority": "normal",
        "schedule": schedule,
        "notification_offsets": _explicit_offsets(low),
        "confidence": 0.75,
        "assumptions": ["Fake parser: локальная эвристика без LLM."],
    }
    return _base(text, items=[item])


def _one_off_datetime(low: str, now: datetime) -> dict[str, Any] | None:
    time_text = _extract_time(low)
    if "послезавтра" in low:
        target_date = now.date() + timedelta(days=2)
    elif "завтра" in low:
        target_date = now.date() + timedelta(days=1)
    elif "сегодня" in low:
        target_date = now.date()
    else:
        target = _relative_delay_target(low, now=now)
        if target:
            return {
                "start_at": target.isoformat(timespec="seconds"),
                "date": target.date().isoformat(),
                "time": target.strftime("%H:%M"),
                "temporal_profile": "moment_reminder",
            }
        date_match = re.search(r"(\d{1,2})\s+([а-яё]+)", low)
        if not date_match:
            return None
        day = int(date_match.group(1))
        month = MONTHS_RU.get(date_match.group(2))
        if not month:
            return None
        target_date = _next_date(day=day, month=month, now=now).date()
    if time_text:
        return {
            "start_at": f"{target_date.isoformat()}T{time_text}:00",
            "date": target_date.isoformat(),
            "time": time_text,
            "temporal_profile": "exact_time",
        }
    return {"start_at": None, "date": target_date.isoformat(), "time": None, "temporal_profile": "day_task"}


def _relative_delay_target(raw_text: str, *, now: datetime) -> datetime | None:
    low = raw_text.lower()
    rel = re.search(
        r"через\s+(\d+|один|одну|два|две|три|четыре|пять|пару)\s+"
        r"(минут|минуту|минуты|час|часа|часов|день|дня|дней)",
        low,
    )
    if not rel:
        return None
    amount = _amount(rel.group(1))
    unit = rel.group(2)
    if unit.startswith("час"):
        return now.replace(microsecond=0) + timedelta(hours=amount)
    if unit.startswith("д"):
        return now.replace(microsecond=0) + timedelta(days=amount)
    return now.replace(microsecond=0) + timedelta(minutes=amount)


def normalize_claude_payload(payload: dict[str, Any], request: ReminderParseRequest) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _clarification(request.raw_text, "Не удалось разобрать ответ парсера.", [])
    if _is_native_payload(payload):
        native_payload = normalize_payload_clarification(payload)
        native_payload = _normalize_native_payload_schedules(native_payload, request)
        native_payload = _normalize_native_payload_contexts(native_payload, request)
        return _normalize_native_payload_titles(native_payload, request)

    compact = payload.get("reminder") if isinstance(payload.get("reminder"), dict) else payload
    raw_text = _clean(compact.get("raw_text")) or _clean(payload.get("raw_text")) or request.raw_text
    if _compact_is_error(payload) or _compact_is_error(compact):
        question = str(
            compact.get("message")
            or compact.get("reason")
            or compact.get("clarification_question")
            or payload.get("message")
            or payload.get("reason")
            or payload.get("clarification_question")
            or "Нужно уточнение."
        )
        return _clarification(raw_text, question, [])

    intent = _clean(payload.get("intent") or compact.get("intent") or payload.get("action") or compact.get("action") or "create").lower()
    if intent in {"add", "create_reminder", "create_event", "create_task", "reminder"}:
        intent = "create"
    if intent != "create":
        return _base(raw_text, intent="unknown", status="unsupported", items=[])

    start_at = _clean(compact.get("start_at")) or _clean(compact.get("datetime"))
    event_date = _clean(compact.get("date"))
    event_time = _clean(compact.get("time"))
    if start_at:
        try:
            parsed = datetime.fromisoformat(start_at)
        except ValueError:
            parsed = None
        if parsed:
            parsed = parsed.replace(tzinfo=None, microsecond=0)
            start_at = parsed.isoformat(timespec="seconds")
            event_date = event_date or parsed.date().isoformat()
            event_time = event_time or parsed.strftime("%H:%M")

    raw_event_type = _clean(compact.get("event_type"))
    recurrence = _compact_recurrence(compact.get("recurrence") or compact.get("repeat") or compact.get("frequency"))
    if recurrence.get("frequency") == "none" and raw_event_type in {"birthday", "anniversary"} and event_date:
        birthday_date = _parse_iso_date(event_date)
        if birthday_date:
            recurrence = {
                **_recurrence_none(),
                "frequency": "yearly",
                "months": [birthday_date.month],
                "month_days": [birthday_date.day],
            }
    is_recurring = recurrence.get("frequency") != "none"
    event_type = raw_event_type or ("habit" if is_recurring else "task")
    if is_recurring and not event_date:
        event_date = _recurring_start_date(request=request, time_text=event_time or None).isoformat()
    if not is_recurring and not event_date and not start_at:
        return _clarification(raw_text, "Когда напомнить?", ["сегодня", "завтра", "через час"])

    title_source = _clean(compact.get("title") or compact.get("text") or payload.get("title") or payload.get("text")) or raw_text
    title = _title_preserving_raw_language(title_source, raw_text=raw_text)
    date_only_midnight = _date_only_midnight(raw_text=raw_text, event_time=event_time, start_at=start_at)
    inferred_clock = _inferred_clock_without_explicit_time(raw_text=raw_text, event_time=event_time, start_at=start_at)
    if date_only_midnight or inferred_clock:
        start_at = ""
        event_time = ""
    relative_delay_target = _relative_delay_target(raw_text, now=request.now)
    if relative_delay_target and not (start_at and event_time):
        start_at = relative_delay_target.isoformat(timespec="seconds")
        event_date = relative_delay_target.date().isoformat()
        event_time = relative_delay_target.strftime("%H:%M")
    all_day = not bool(event_time or start_at)
    raw_temporal_profile = (
        "day_task"
        if date_only_midnight or inferred_clock
        else _clean(
            compact.get("temporal_profile")
            or compact.get("profile")
            or compact.get("schedule_profile")
            or compact.get("temporal_type")
        ).lower()
    )
    item = {
        "client_ref": "item_1",
        "title": title,
        "description": _clean(compact.get("description")),
        "context": normalize_event_contexts(
            compact.get("context")
            or compact.get("contexts")
            or {
                "links": compact.get("links") or compact.get("link") or compact.get("url") or compact.get("urls"),
                "locations": compact.get("locations")
                or compact.get("location")
                or compact.get("address")
                or compact.get("venue"),
                "notes": compact.get("notes") or compact.get("note"),
            },
            raw_text=raw_text,
            include_extracted=True,
        ),
        "event_type": event_type if event_type in {"task", "calendar_event", "deadline", "birthday", "anniversary", "habit"} else ("habit" if is_recurring else "task"),
        "temporal_profile": raw_temporal_profile if raw_temporal_profile in VALID_TEMPORAL_PROFILES else "",
        "priority": _priority(compact.get("priority")),
        "schedule": {
            "kind": "recurring" if is_recurring else "once",
            "timezone": _clean(compact.get("timezone")) or request.timezone,
            "all_day": all_day,
            "start_at": start_at or None,
            "date": event_date or None,
            "time": event_time or None,
            "precision": "datetime" if not all_day else "date",
            "recurrence": recurrence,
        },
        "notification_offsets": _compact_offsets(compact),
        "confidence": _coerce_float(compact.get("confidence") or payload.get("confidence"), default=0.7),
        "assumptions": ["Claude compact output normalized by reminder-bot."],
    }
    if not item["temporal_profile"]:
        item["temporal_profile"] = "moment_reminder" if _looks_like_moment_reminder(raw_text) else derive_temporal_profile(item)
    return _base(raw_text, items=[item])


def _is_native_payload(payload: dict[str, Any]) -> bool:
    return all(key in payload for key in ("intent", "status", "items", "clarification"))


def _normalize_native_payload_titles(payload: dict[str, Any], request: ReminderParseRequest) -> dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list):
        return payload
    raw_text = _clean(payload.get("raw_text")) or request.raw_text
    single_item = len([item for item in items if isinstance(item, dict)]) == 1
    for item in items:
        if not isinstance(item, dict):
            continue
        title_source = _clean(item.get("title")) or raw_text
        if single_item:
            item["title"] = _title_preserving_raw_language(title_source, raw_text=raw_text)
        else:
            item["title"] = _title(title_source)
    return payload


def _normalize_native_payload_contexts(payload: dict[str, Any], request: ReminderParseRequest) -> dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list):
        return payload
    raw_text = _clean(payload.get("raw_text")) or request.raw_text
    single_item = len([item for item in items if isinstance(item, dict)]) == 1
    for item in items:
        if not isinstance(item, dict):
            continue
        item["context"] = normalize_event_contexts(
            item.get("context") or item.get("contexts"),
            raw_text=raw_text,
            include_extracted=single_item,
        )
    return payload


def _normalize_native_payload_schedules(payload: dict[str, Any], request: ReminderParseRequest) -> dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list):
        return payload
    raw_text = _clean(payload.get("raw_text")) or request.raw_text
    for item in items:
        if not isinstance(item, dict):
            continue
        schedule = item.get("schedule")
        if not isinstance(schedule, dict):
            continue
        event_time = _clean(schedule.get("time"))
        start_at = _clean(schedule.get("start_at"))
        if not start_at and not event_time:
            relative_delay_target = _relative_delay_target(raw_text, now=request.now)
            if relative_delay_target:
                schedule["start_at"] = relative_delay_target.isoformat(timespec="seconds")
                schedule["date"] = relative_delay_target.date().isoformat()
                schedule["time"] = relative_delay_target.strftime("%H:%M")
                schedule["all_day"] = False
                schedule["precision"] = "datetime"
                item["temporal_profile"] = "moment_reminder"
                continue
            schedule["all_day"] = True
            schedule["precision"] = "date"
            _downgrade_temporal_profile_to_date(item)
            continue
        if not _inferred_clock_without_explicit_time(raw_text=raw_text, event_time=event_time, start_at=start_at):
            continue
        if start_at and not _clean(schedule.get("date")):
            try:
                schedule["date"] = datetime.fromisoformat(start_at).date().isoformat()
            except ValueError:
                pass
        schedule["start_at"] = None
        schedule["time"] = None
        schedule["all_day"] = True
        schedule["precision"] = "date"
        _downgrade_temporal_profile_to_date(item)
    return payload


def _downgrade_temporal_profile_to_date(item: dict[str, Any]) -> None:
    profile = _clean(item.get("temporal_profile")).lower()
    if profile == "exact_time":
        item["temporal_profile"] = "day_task"
    elif profile == "recurring_exact_time":
        item["temporal_profile"] = "recurring_day_task"


def _compact_is_error(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return True
    status = str(payload.get("status") or "").lower()
    return status in {"error", "unsupported", "needs_clarification"} or payload.get("success") is False


def _compact_recurrence(value: Any) -> dict[str, Any]:
    recurrence = _recurrence_none()
    if not value:
        return recurrence
    if isinstance(value, str):
        low = value.lower()
        daily_interval = _daily_interval(low)
        if daily_interval:
            return {**recurrence, "frequency": "daily", "interval": daily_interval}
        if "every_other_day" in low or "alternate" in low:
            return {**recurrence, "frequency": "daily", "interval": 2}
        if "biweekly" in low or "every_two_weeks" in low:
            return {**recurrence, "frequency": "weekly", "interval": 2}
        if "daily" in low or "day" in low:
            return {**recurrence, "frequency": "daily"}
        if "weekly" in low or "week" in low:
            return {**recurrence, "frequency": "weekly"}
        if "monthly" in low or "month" in low:
            return {**recurrence, "frequency": "monthly"}
        if "yearly" in low or "annual" in low or "year" in low:
            return {**recurrence, "frequency": "yearly"}
        return recurrence
    if not isinstance(value, dict):
        return recurrence
    frequency = _clean(value.get("frequency") or value.get("type") or value.get("unit") or "none").lower()
    unit = _clean(value.get("unit")).lower()
    interval = _coerce_int(
        value.get("interval") or value.get("every") or value.get("every_n"),
        default=1,
        min_value=1,
    )
    if frequency in {"none", "null", "once", "one_off"}:
        return recurrence
    if frequency in {"every_other_day", "alternate_days", "day_after_day"}:
        frequency = "daily"
        interval = max(interval, 2)
    elif frequency in {"biweekly", "every_two_weeks"}:
        frequency = "weekly"
        interval = max(interval, 2)
    elif frequency in {"day", "days", "daily"} or unit in {"day", "days"}:
        frequency = "daily"
    elif frequency in {"week", "weeks", "weekly"} or unit in {"week", "weeks"}:
        frequency = "weekly"
    elif frequency in {"month", "months", "monthly"} or unit in {"month", "months"}:
        frequency = "monthly"
    elif frequency in {"year", "years", "yearly", "annual", "annually"} or unit in {"year", "years"}:
        frequency = "yearly"
    if frequency not in {"daily", "weekly", "monthly", "yearly"}:
        return recurrence
    return {
        **recurrence,
        "frequency": frequency,
        "interval": interval,
        "weekdays": [
            code
            for item in _as_list(value.get("weekdays") or value.get("days_of_week") or value.get("weekday"))
            if (code := _weekday_code(item))
        ],
        "month_days": _as_int_list(value.get("month_days") or value.get("days_of_month") or value.get("month_day"), min_value=1, max_value=31),
        "months": _as_int_list(value.get("months") or value.get("month"), min_value=1, max_value=12),
        "until": value.get("until"),
        "count": _coerce_optional_int(value.get("count")),
        "rrule": str(value.get("rrule") or ""),
    }


def _compact_offsets(compact: dict[str, Any]) -> list[dict[str, Any]]:
    offsets = compact.get("notification_offsets") or compact.get("offsets") or []
    if not offsets:
        minutes = _coerce_optional_int(
            compact.get("reminder_offset_minutes")
            or compact.get("minutes_before")
            or compact.get("offset_minutes")
            or compact.get("notify_minutes_before")
        )
        return [{"minutes_before": minutes, "source": "explicit"}] if minutes is not None else []
    if not isinstance(offsets, list):
        return []
    normalized = []
    for raw in offsets:
        if isinstance(raw, int):
            normalized.append({"minutes_before": max(0, raw), "source": "explicit"})
            continue
        if not isinstance(raw, dict):
            continue
        minutes = _coerce_optional_int(raw.get("minutes_before") or raw.get("minutes") or raw.get("offset_minutes"))
        if minutes is None:
            continue
        normalized.append(
            {
                "minutes_before": minutes,
                "source": _offset_source(raw.get("source")),
            }
        )
    return normalized


def _parse_iso_date(value: str):
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _weekday_code(value: Any) -> str:
    text = _clean(value).lower()
    if not text:
        return ""
    upper = text.upper()
    if upper in {"MO", "TU", "WE", "TH", "FR", "SA", "SU"}:
        return upper
    mapping = {
        "monday": "MO",
        "mon": "MO",
        "понедельник": "MO",
        "tuesday": "TU",
        "tue": "TU",
        "вторник": "TU",
        "wednesday": "WE",
        "wed": "WE",
        "среда": "WE",
        "среду": "WE",
        "thursday": "TH",
        "thu": "TH",
        "четверг": "TH",
        "friday": "FR",
        "fri": "FR",
        "пятница": "FR",
        "пятницу": "FR",
        "saturday": "SA",
        "sat": "SA",
        "суббота": "SA",
        "субботу": "SA",
        "sunday": "SU",
        "sun": "SU",
        "воскресенье": "SU",
    }
    return mapping.get(text, "")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_int_list(value: Any, *, min_value: int | None = None, max_value: int | None = None) -> list[int]:
    numbers = []
    for item in _as_list(value):
        parsed = _coerce_optional_int(item)
        if parsed is None:
            continue
        if min_value is not None and parsed < min_value:
            continue
        if max_value is not None and parsed > max_value:
            continue
        numbers.append(parsed)
    return numbers


def _coerce_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any, *, default: int, min_value: int) -> int:
    parsed = _coerce_optional_int(value)
    if parsed is None:
        return default
    return max(min_value, parsed)


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, parsed))


def _priority(value: Any) -> str:
    priority = _clean(value).lower()
    return priority if priority in {"low", "normal", "high"} else "normal"


def _offset_source(value: Any) -> str:
    source = _clean(value).lower()
    return source if source in {"explicit", "default_suggested"} else "explicit"


def _looks_like_moment_reminder(raw_text: str) -> bool:
    low = raw_text.lower()
    if _relative_delay_target(low, now=datetime.now()):
        return True
    return bool(re.search(r"^\s*напомн\w+\s+(?:мне\s+)?(?:сегодня|завтра|послезавтра|в\s+\d)", low))


def _date_only_midnight(*, raw_text: str, event_time: str, start_at: str) -> bool:
    if event_time != "00:00":
        return False
    if _extract_time(raw_text.lower()):
        return False
    if "полноч" in raw_text.lower():
        return False
    if start_at:
        try:
            parsed = datetime.fromisoformat(start_at)
        except ValueError:
            return False
        return parsed.hour == 0 and parsed.minute == 0
    return True


def _inferred_clock_without_explicit_time(*, raw_text: str, event_time: str, start_at: str) -> bool:
    if not event_time and not start_at:
        return False
    if _extract_time(raw_text.lower()):
        return False
    return not _looks_like_moment_reminder(raw_text)


def _extract_time(low: str) -> str | None:
    match = re.search(r"(?:в\s*)?(\d{1,2})[:.](\d{2})", low)
    if match:
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    match = re.search(r"\bв\s+(\d{1,2})\b", low)
    if match and 0 <= int(match.group(1)) <= 23:
        return f"{int(match.group(1)):02d}:00"
    return None


def _daily_interval(low: str) -> int | None:
    if re.search(r"\bдень\s+через\s+день\b", low):
        return 2
    match = re.search(
        r"\bкажд\w*\s+(\d+|один|одну|два|две|три|четыре|пять|пару)\s+"
        r"(?:день|дня|дней)\b",
        low,
    )
    if match:
        return max(1, _amount(match.group(1)))
    match = re.search(
        r"\bраз\s+в\s+(\d+|один|одну|два|две|три|четыре|пять|пару)\s+"
        r"(?:день|дня|дней)\b",
        low,
    )
    if match:
        return max(1, _amount(match.group(1)))
    if re.search(r"\bкажд\w*\s+день\b", low):
        return 1
    return None


def _recurring_start_date(*, request: ReminderParseRequest, time_text: str | None):
    hour, minute = _parse_hhmm(time_text or request.default_day_reminder_time)
    if (hour, minute) <= (request.now.hour, request.now.minute):
        return request.now.date() + timedelta(days=1)
    return request.now.date()


def _explicit_offsets(low: str) -> list[dict[str, Any]]:
    match = re.search(r"за\s+(\d+|один|одну|пару)\s+(минут|минуты|час|часа|часов|день|дня|дней)", low)
    if not match:
        return []
    amount = _amount(match.group(1))
    unit = match.group(2)
    minutes = amount
    if unit.startswith("час"):
        minutes = amount * 60
    elif unit.startswith("д"):
        minutes = amount * 1440
    return [{"minutes_before": minutes, "source": "explicit"}]


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


def _next_date(*, day: int, month: int, now: datetime) -> datetime:
    candidate = datetime(year=now.year, month=month, day=day)
    if candidate.date() < now.date():
        candidate = datetime(year=now.year + 1, month=month, day=day)
    return candidate


def _base(raw_text: str, *, intent: str = "create", status: str = "ok", items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": PROMPT_VERSION,
        "intent": intent,
        "status": status,
        "raw_text": raw_text,
        "items": items or [],
        "clarification": {"question": "", "options": []},
    }


def _clarification(raw_text: str, question: str, options: list[str]) -> dict[str, Any]:
    payload = _base(raw_text, status="needs_clarification", items=[])
    question, options = normalize_clarification(question, options)
    payload["clarification"] = {"question": question, "options": options}
    return payload


def _recurrence_none() -> dict[str, Any]:
    return {
        "frequency": "none",
        "interval": 1,
        "weekdays": [],
        "month_days": [],
        "months": [],
        "until": None,
        "count": None,
        "rrule": "",
    }


def _title(text: str) -> str:
    clean = strip_context_from_title(re.sub(r"\s+", " ", text.strip()))
    clean = _strip_helper_words(clean)
    clean = _strip_time_words(clean)
    clean = _strip_helper_words(clean)
    clean = clean.strip(" .,!?:;")
    if not clean:
        return "Напоминание"
    return clean[:1].upper() + clean[1:]


def _title_preserving_raw_language(title_source: str, *, raw_text: str) -> str:
    title = _title(title_source)
    if _looks_translated_title(raw_text=raw_text, title=title):
        fallback = _title(raw_text)
        if fallback != "Напоминание":
            return fallback
    return title


def _looks_translated_title(*, raw_text: str, title: str) -> bool:
    return bool(title) and _contains_cyrillic(raw_text) and not _contains_cyrillic(title)


def _contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text))


def _strip_helper_words(text: str) -> str:
    return re.sub(r"^(?:надо|нужно|напомни|напомнить|пожалуйста|давай)\s+", "", text, flags=re.IGNORECASE)


def _strip_time_words(text: str) -> str:
    clean = re.sub(r"\b(?:сегодня|завтра|послезавтра)\b", "", text, flags=re.IGNORECASE)
    clean = re.sub(r"\b(?:утром|дн[её]м|вечером|ночью)\b", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bчерез\s+(\d+|один|одну|пару)\s+(?:минут|минуты|час|часа|часов|день|дня|дней)\b", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bв\s+\d{1,2}(?::\d{2})?\b", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bза\s+(\d+|один|одну|пару)\s+(?:минут|минуты|час|часа|часов|день|дня|дней)\b", "", clean, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", clean).strip()


def _strip_recurrence_words(text: str) -> str:
    clean = re.sub(r"\bдень\s+через\s+день\b", "", text, flags=re.IGNORECASE)
    clean = re.sub(
        r"\bкажд\w*\s+(?:\d+|один|одну|два|две|три|четыре|пять|пару)?\s*"
        r"(?:день|дня|дней)\b",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\bраз\s+в\s+(?:\d+|один|одну|два|две|три|четыре|пять|пару)\s+"
        r"(?:день|дня|дней)\b",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    return _strip_time_words(clean)


def _parse_hhmm(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value or "")
    if not match:
        return 9, 0
    hour = min(23, max(0, int(match.group(1))))
    minute = min(59, max(0, int(match.group(2))))
    return hour, minute


def _remove_patterns(text: str, patterns: list[str]) -> str:
    clean = text
    for pattern in patterns:
        clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)
    return clean


def _birthday_title(text: str) -> str:
    return _title(text)


def _clean(value: Any) -> str:
    return str(value or "").strip()
