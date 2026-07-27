from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from sqlite3 import Row
from typing import Any


@dataclass(frozen=True)
class EventContext:
    id: str
    event_id: str
    kind: str
    label: str
    value: str
    normalized_value: str
    source: str
    position: int
    created_at: datetime


@dataclass(frozen=True)
class Event:
    id: str
    title: str
    description: str
    event_type: str
    status: str
    timezone: str
    all_day: bool
    start_at: datetime | None
    event_date: str
    event_time: str
    recurrence: dict[str, Any]
    source_text: str
    source_kind: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NotificationRule:
    id: str
    event_id: str
    kind: str
    minutes_before: int
    time_of_day: str
    source: str
    enabled: bool
    created_at: datetime


@dataclass(frozen=True)
class OccurrenceView:
    occurrence_id: str
    event_id: str
    title: str
    description: str
    event_type: str
    occurs_at: datetime
    occurrence_date: str
    occurrence_status: str
    event_status: str
    next_notify_at: datetime | None
    all_day: bool = False
    source_text: str = ""
    contexts: tuple[EventContext, ...] = ()


@dataclass(frozen=True)
class NotificationJobView:
    job_id: str
    event_id: str
    occurrence_id: str
    notification_rule_id: str
    title: str
    description: str
    event_type: str
    occurs_at: datetime
    notify_at: datetime
    job_status: str
    all_day: bool = False
    source_text: str = ""
    contexts: tuple[EventContext, ...] = ()


def event_from_row(row: Row) -> Event:
    return Event(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        event_type=row["event_type"],
        status=row["status"],
        timezone=row["timezone"],
        all_day=bool(row["all_day"]),
        start_at=datetime.fromisoformat(row["start_at"]) if row["start_at"] else None,
        event_date=row["event_date"] or "",
        event_time=row["event_time"] or "",
        recurrence=json.loads(row["recurrence_json"] or "{}"),
        source_text=row["source_text"],
        source_kind=row["source_kind"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def event_context_from_row(row: Row) -> EventContext:
    return EventContext(
        id=row["id"],
        event_id=row["event_id"],
        kind=row["kind"],
        label=row["label"],
        value=row["value"],
        normalized_value=row["normalized_value"],
        source=row["source"],
        position=int(row["position"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def notification_rule_from_row(row: Row) -> NotificationRule:
    return NotificationRule(
        id=row["id"],
        event_id=row["event_id"],
        kind=row["kind"],
        minutes_before=int(row["minutes_before"]),
        time_of_day=row["time_of_day"] or "",
        source=row["source"],
        enabled=bool(row["enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def occurrence_view_from_row(row: Row) -> OccurrenceView:
    next_notify = row["next_notify_at"]
    return OccurrenceView(
        occurrence_id=row["occurrence_id"],
        event_id=row["event_id"],
        title=row["title"],
        description=row["description"],
        event_type=row["event_type"],
        occurs_at=datetime.fromisoformat(row["occurs_at"]),
        occurrence_date=row["occurrence_date"],
        occurrence_status=row["occurrence_status"],
        event_status=row["event_status"],
        next_notify_at=datetime.fromisoformat(next_notify) if next_notify else None,
        all_day=_row_bool(row, "all_day"),
        source_text=_row_text(row, "source_text"),
    )


def notification_job_view_from_row(row: Row) -> NotificationJobView:
    return NotificationJobView(
        job_id=row["job_id"],
        event_id=row["event_id"],
        occurrence_id=row["occurrence_id"],
        notification_rule_id=row["notification_rule_id"],
        title=row["title"],
        description=row["description"],
        event_type=row["event_type"],
        occurs_at=datetime.fromisoformat(row["occurs_at"]),
        notify_at=datetime.fromisoformat(row["notify_at"]),
        job_status=row["job_status"],
        all_day=_row_bool(row, "all_day"),
        source_text=_row_text(row, "source_text"),
    )


def _row_bool(row: Row, key: str) -> bool:
    if key not in row.keys():
        return False
    return bool(row[key])


def _row_text(row: Row, key: str) -> str:
    if key not in row.keys():
        return ""
    return str(row[key] or "")
