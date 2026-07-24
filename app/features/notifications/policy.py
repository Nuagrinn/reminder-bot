from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol


VALID_TEMPORAL_PROFILES = {
    "moment_reminder",
    "exact_time",
    "day_task",
    "deadline",
    "time_window",
    "recurring_exact_time",
    "recurring_day_task",
    "annual_date",
    "floating",
}


class NotificationPolicyDefaults(Protocol):
    day_reminder_hhmm: tuple[int, int]
    evening_reminder_hhmm: tuple[int, int]
    day_before_reminder_hhmm: tuple[int, int]
    timed_event_offset_minutes: int
    exact_time_today_offsets_minutes: tuple[int, ...]
    exact_time_future_offsets_minutes: tuple[int, ...]
    deadline_days_before: tuple[int, ...]
    annual_days_before: tuple[int, ...]


@dataclass(frozen=True)
class NotificationRuleSpec:
    kind: str
    minutes_before: int
    time_of_day: str = ""
    source: str = "default"


def annotate_notification_preview(
    payload: dict[str, Any],
    *,
    now: datetime,
    defaults: NotificationPolicyDefaults,
) -> None:
    if payload.get("intent") != "create" or payload.get("status") != "ok":
        return
    items = payload.get("items")
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        item["temporal_profile"] = derive_temporal_profile(item)
        item["notification_preview"] = notification_rule_labels(
            build_notification_rules(item, now=now, defaults=defaults)
        )


def build_notification_rules(
    item: dict[str, Any],
    *,
    now: datetime,
    defaults: NotificationPolicyDefaults,
) -> list[NotificationRuleSpec]:
    explicit = _explicit_rules(item)
    if explicit:
        return explicit

    profile = derive_temporal_profile(item)
    schedule = _schedule(item)
    event_date = _event_date(schedule)
    recurrence = _recurrence(schedule)
    frequency = _clean(recurrence.get("frequency")) or "none"
    is_today = event_date == now.date() if event_date else False

    if profile == "moment_reminder":
        return [_relative(0)]

    if profile == "exact_time":
        rules = [_relative(minutes) for minutes in _positive_offsets(defaults.exact_time_today_offsets_minutes)]
        if not is_today:
            rules = [_time_of_day(days_before=1, hhmm=defaults.day_before_reminder_hhmm)] + [
                _relative(minutes) for minutes in _positive_offsets(defaults.exact_time_future_offsets_minutes)
            ]
        return _dedupe(rules)

    if profile == "day_task":
        rules = [
            _time_of_day(days_before=0, hhmm=defaults.day_reminder_hhmm),
            _time_of_day(days_before=0, hhmm=defaults.evening_reminder_hhmm),
        ]
        if not is_today:
            rules.insert(0, _time_of_day(days_before=1, hhmm=defaults.day_before_reminder_hhmm))
        return _dedupe(rules)

    if profile == "deadline":
        rules = [
            _time_of_day(
                days_before=days_before,
                hhmm=defaults.day_before_reminder_hhmm if days_before == 1 else defaults.day_reminder_hhmm,
            )
            for days_before in defaults.deadline_days_before
        ]
        if _has_time(schedule):
            rules.extend(_relative(minutes) for minutes in _deadline_offsets(defaults))
        else:
            rules.extend(
                [
                    _time_of_day(days_before=0, hhmm=defaults.day_reminder_hhmm),
                    _time_of_day(days_before=0, hhmm=defaults.evening_reminder_hhmm),
                ]
            )
        return _dedupe(rules)

    if profile == "time_window":
        return _dedupe(
            [
                _time_of_day(days_before=1, hhmm=defaults.day_before_reminder_hhmm),
                _time_of_day(days_before=0, hhmm=defaults.day_reminder_hhmm),
                _relative(30),
            ]
        )

    if profile == "recurring_exact_time":
        if frequency == "daily":
            return [_relative(15)]
        return _dedupe(
            [_time_of_day(days_before=1, hhmm=defaults.day_before_reminder_hhmm)]
            + [_relative(minutes) for minutes in _positive_offsets(defaults.exact_time_future_offsets_minutes)]
        )

    if profile == "recurring_day_task":
        rules = [
            _time_of_day(days_before=0, hhmm=defaults.day_reminder_hhmm),
            _time_of_day(days_before=0, hhmm=defaults.evening_reminder_hhmm),
        ]
        if frequency in {"weekly", "monthly"}:
            rules.insert(0, _time_of_day(days_before=1, hhmm=defaults.day_before_reminder_hhmm))
        return _dedupe(rules)

    if profile == "annual_date":
        rules = [
            _time_of_day(
                days_before=days_before,
                hhmm=defaults.day_before_reminder_hhmm if days_before == 1 else defaults.day_reminder_hhmm,
            )
            for days_before in defaults.annual_days_before
        ]
        rules.append(_time_of_day(days_before=0, hhmm=defaults.day_reminder_hhmm))
        return _dedupe(rules)

    return [_time_of_day(days_before=0, hhmm=defaults.day_reminder_hhmm)]


def derive_temporal_profile(item: dict[str, Any]) -> str:
    explicit = _clean(item.get("temporal_profile")).lower()
    if explicit in VALID_TEMPORAL_PROFILES:
        return explicit

    schedule = _schedule(item)
    recurrence = _recurrence(schedule)
    frequency = _clean(recurrence.get("frequency")) or "none"
    if frequency == "yearly":
        return "annual_date"
    if frequency != "none":
        return "recurring_exact_time" if _has_time(schedule) else "recurring_day_task"
    if _clean(item.get("event_type")).lower() == "deadline":
        return "deadline"
    if _has_time(schedule):
        return "exact_time"
    if _event_date(schedule):
        return "day_task"
    return "floating"


def notification_rule_labels(specs: list[NotificationRuleSpec]) -> list[str]:
    return [_rule_label(spec) for spec in specs]


def _explicit_rules(item: dict[str, Any]) -> list[NotificationRuleSpec]:
    offsets = item.get("notification_offsets")
    if not isinstance(offsets, list) or not offsets:
        return []
    rules: list[NotificationRuleSpec] = []
    for raw in offsets:
        if isinstance(raw, int):
            rules.append(_relative(raw, source="explicit"))
            continue
        if not isinstance(raw, dict):
            continue
        minutes = _coerce_int(raw.get("minutes_before") or raw.get("minutes") or raw.get("offset_minutes"), default=0)
        rules.append(_relative(minutes, source=_source(raw.get("source"))))
    return _dedupe(rules)


def _rule_label(spec: NotificationRuleSpec) -> str:
    if spec.kind == "time_of_day":
        if spec.minutes_before == 0:
            if spec.time_of_day < "12:00":
                return "утром в день"
            return "вечером в день"
        if spec.minutes_before == 1:
            if spec.time_of_day < "12:00":
                return "утром за день"
            return "вечером за день"
        return f"за {spec.minutes_before} дн. в {spec.time_of_day}"
    if spec.minutes_before == 0:
        return "в момент события"
    if spec.minutes_before % 1440 == 0:
        return f"за {spec.minutes_before // 1440} дн."
    if spec.minutes_before % 60 == 0:
        return f"за {spec.minutes_before // 60} ч."
    return f"за {spec.minutes_before} мин."


def _relative(minutes_before: int, *, source: str = "default") -> NotificationRuleSpec:
    return NotificationRuleSpec(
        kind="relative",
        minutes_before=max(0, int(minutes_before)),
        source=source,
    )


def _time_of_day(*, days_before: int, hhmm: tuple[int, int], source: str = "default") -> NotificationRuleSpec:
    return NotificationRuleSpec(
        kind="time_of_day",
        minutes_before=max(0, int(days_before)),
        time_of_day=_hhmm(hhmm),
        source=source,
    )


def _deadline_offsets(defaults: NotificationPolicyDefaults) -> tuple[int, ...]:
    values = [defaults.timed_event_offset_minutes, 15]
    return tuple(minutes for minutes in values if minutes >= 0)


def _positive_offsets(values: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(minutes for minutes in values if minutes >= 0)


def _dedupe(specs: list[NotificationRuleSpec]) -> list[NotificationRuleSpec]:
    result: list[NotificationRuleSpec] = []
    seen: set[tuple[str, int, str]] = set()
    for spec in specs:
        key = (spec.kind, spec.minutes_before, spec.time_of_day)
        if key in seen:
            continue
        seen.add(key)
        result.append(spec)
    return result


def _schedule(item: dict[str, Any]) -> dict[str, Any]:
    schedule = item.get("schedule")
    return schedule if isinstance(schedule, dict) else {}


def _recurrence(schedule: dict[str, Any]) -> dict[str, Any]:
    recurrence = schedule.get("recurrence")
    return recurrence if isinstance(recurrence, dict) else {}


def _event_date(schedule: dict[str, Any]) -> date | None:
    value = _clean(schedule.get("date"))
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    start_at = _clean(schedule.get("start_at"))
    if not start_at:
        return None
    try:
        return datetime.fromisoformat(start_at).date()
    except ValueError:
        return None


def _has_time(schedule: dict[str, Any]) -> bool:
    return bool(_clean(schedule.get("time")) or _clean(schedule.get("start_at")))


def _hhmm(value: tuple[int, int]) -> str:
    hour, minute = value
    return f"{hour:02d}:{minute:02d}"


def _source(value: Any) -> str:
    source = _clean(value).lower()
    return source if source else "explicit"


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _clean(value: Any) -> str:
    return str(value or "").strip()
