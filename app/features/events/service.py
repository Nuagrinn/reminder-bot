from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from assistant_toolkit.db import Database

from app.core.ids import new_id
from app.core.time import iso, parse_date, parse_time
from app.features.events.models import (
    Event,
    NotificationJobView,
    OccurrenceView,
    event_from_row,
    notification_job_view_from_row,
    notification_rule_from_row,
    occurrence_view_from_row,
)
from app.features.events.recurrence import occurrence_datetimes
from app.features.events.reschedule import RescheduleTarget
from app.features.notifications.policy import build_notification_rules


ACTIVE = "active"
SCHEDULED = "scheduled"
PENDING = "pending"


@dataclass(frozen=True)
class EventDefaults:
    timezone: str
    day_reminder_hhmm: tuple[int, int] = (9, 0)
    evening_reminder_hhmm: tuple[int, int] = (20, 0)
    day_before_reminder_hhmm: tuple[int, int] = (20, 0)
    timed_event_offset_minutes: int = 120
    exact_time_today_offsets_minutes: tuple[int, ...] = (60, 15)
    exact_time_future_offsets_minutes: tuple[int, ...] = (60, 15)
    birthday_offsets_minutes: tuple[int, ...] = (1440, 0)
    deadline_days_before: tuple[int, ...] = (3, 1)
    annual_days_before: tuple[int, ...] = (7, 1)
    same_day_backoff_offsets_minutes: tuple[int, ...] = (60, 180)
    materialize_days: int = 180


class EventService:
    def __init__(self, db: Database, defaults: EventDefaults):
        self.db = db
        self.defaults = defaults

    def create_from_agent_item(
        self,
        item: dict[str, Any],
        *,
        source_text: str,
        source_kind: str,
        now: datetime,
    ) -> Event:
        schedule = item.get("schedule") if isinstance(item.get("schedule"), dict) else {}
        recurrence = schedule.get("recurrence") if isinstance(schedule.get("recurrence"), dict) else {}
        recurrence = _normalize_recurrence(recurrence)
        event_id = new_id("evt_")
        created = now.replace(microsecond=0)
        title = _clean(item.get("title")) or "Напоминание"
        description = _clean(item.get("description"))
        event_type = _clean(item.get("event_type")) or "task"
        timezone = _clean(schedule.get("timezone")) or self.defaults.timezone
        all_day = bool(schedule.get("all_day", False))
        start_at = _parse_datetime_or_none(schedule.get("start_at"))
        event_date = _clean(schedule.get("date"))
        event_time = _clean(schedule.get("time"))

        if start_at and not event_date:
            event_date = start_at.date().isoformat()
        if start_at and not event_time:
            event_time = start_at.strftime("%H:%M")

        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    id, title, description, event_type, status, timezone, all_day,
                    start_at, event_date, event_time, recurrence_json, source_text,
                    source_kind, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    title,
                    description,
                    event_type,
                    ACTIVE,
                    timezone,
                    1 if all_day else 0,
                    iso(start_at) if start_at else None,
                    event_date or None,
                    event_time or None,
                    json.dumps(recurrence, ensure_ascii=False),
                    source_text,
                    source_kind,
                    iso(created),
                    iso(created),
                ),
            )
            for rule in build_notification_rules(item, now=now, defaults=self.defaults):
                conn.execute(
                    """
                    INSERT INTO notification_rules (
                        id, event_id, kind, minutes_before, time_of_day, source,
                        enabled, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("rule_"),
                        event_id,
                        rule.kind,
                        rule.minutes_before,
                        rule.time_of_day,
                        rule.source,
                        1,
                        iso(created),
                    ),
                )

        event = self.get_event(event_id)
        self.materialize_event(event_id, now=now)
        return event

    def get_event(self, event_id: str) -> Event:
        with self.db.session() as conn:
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            raise ValueError(f"Event not found: {event_id}")
        return event_from_row(row)

    def get_event_for_occurrence(self, occurrence_id: str) -> Event:
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT e.*
                FROM events e
                JOIN event_occurrences eo ON eo.event_id = e.id
                WHERE eo.id = ?
                """,
                (occurrence_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"Occurrence not found: {occurrence_id}")
        return event_from_row(row)

    def is_recurring(self, event: Event) -> bool:
        return _is_recurring(event.recurrence)

    def materialize_event(self, event_id: str, *, now: datetime) -> None:
        event = self.get_event(event_id)
        if event.status != ACTIVE:
            return
        event_time = _event_time(event, self.defaults.day_reminder_hhmm)
        start_date = parse_date(event.event_date) if event.event_date else None
        occurrence_values = occurrence_datetimes(
            recurrence=event.recurrence,
            start_date=start_date,
            event_time=event_time,
            now=now,
            horizon_days=self.defaults.materialize_days,
        )
        if not occurrence_values:
            return

        created = iso(now)
        with self.db.session() as conn:
            rules = [
                notification_rule_from_row(row)
                for row in conn.execute(
                    "SELECT * FROM notification_rules WHERE event_id = ? AND enabled = 1",
                    (event_id,),
                ).fetchall()
            ]
            for occurs_at in occurrence_values:
                occurrence_id = new_id("occ_")
                conn.execute(
                    """
                    INSERT INTO event_occurrences (
                        id, event_id, occurs_at, occurrence_date, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id, occurs_at) DO NOTHING
                    """,
                    (
                        occurrence_id,
                        event_id,
                        iso(occurs_at),
                        occurs_at.date().isoformat(),
                        SCHEDULED,
                        created,
                    ),
                )
                row = conn.execute(
                    "SELECT id, status FROM event_occurrences WHERE event_id = ? AND occurs_at = ?",
                    (event_id, iso(occurs_at)),
                ).fetchone()
                if not row or row["status"] != SCHEDULED:
                    continue
                occurrence_id = row["id"]
                for rule in rules:
                    notify_at = _notification_datetime(occurs_at, rule, default_hhmm=self.defaults.day_reminder_hhmm)
                    if notify_at < now.replace(microsecond=0):
                        continue
                    conn.execute(
                        """
                        INSERT INTO notification_jobs (
                            id, event_id, occurrence_id, notification_rule_id,
                            notify_at, status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(occurrence_id, notification_rule_id, notify_at) DO NOTHING
                        """,
                        (
                            new_id("job_"),
                            event_id,
                            occurrence_id,
                            rule.id,
                            iso(notify_at),
                            PENDING,
                            created,
                            created,
                        ),
                    )

    def materialize_all(self, *, now: datetime) -> int:
        with self.db.session() as conn:
            rows = conn.execute("SELECT id FROM events WHERE status = ?", (ACTIVE,)).fetchall()
        for row in rows:
            self.materialize_event(row["id"], now=now)
        return len(rows)

    def list_occurrences(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        limit: int = 50,
    ) -> list[OccurrenceView]:
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT
                    eo.id AS occurrence_id,
                    eo.event_id,
                    eo.occurs_at,
                    eo.occurrence_date,
                    eo.status AS occurrence_status,
                    e.title,
                    e.description,
                    e.event_type,
                    COALESCE(eo.all_day_override, e.all_day) AS all_day,
                    e.status AS event_status,
                    MIN(CASE WHEN nj.status = 'pending' THEN nj.notify_at END) AS next_notify_at
                FROM event_occurrences eo
                JOIN events e ON e.id = eo.event_id
                LEFT JOIN notification_jobs nj ON nj.occurrence_id = eo.id
                WHERE e.status = ?
                  AND eo.status = ?
                  AND eo.occurs_at >= ?
                  AND eo.occurs_at <= ?
                GROUP BY eo.id
                ORDER BY eo.occurs_at ASC
                LIMIT ?
                """,
                (ACTIVE, SCHEDULED, iso(start_at), iso(end_at), max(1, min(100, limit))),
            ).fetchall()
        return [occurrence_view_from_row(row) for row in rows]

    def get_occurrence(self, occurrence_id: str) -> OccurrenceView:
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT
                    eo.id AS occurrence_id,
                    eo.event_id,
                    eo.occurs_at,
                    eo.occurrence_date,
                    eo.status AS occurrence_status,
                    e.title,
                    e.description,
                    e.event_type,
                    COALESCE(eo.all_day_override, e.all_day) AS all_day,
                    e.status AS event_status,
                    MIN(CASE WHEN nj.status = 'pending' THEN nj.notify_at END) AS next_notify_at
                FROM event_occurrences eo
                JOIN events e ON e.id = eo.event_id
                LEFT JOIN notification_jobs nj ON nj.occurrence_id = eo.id
                WHERE eo.id = ?
                GROUP BY eo.id
                """,
                (occurrence_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"Occurrence not found: {occurrence_id}")
        return occurrence_view_from_row(row)

    def upcoming(self, *, now: datetime, limit: int = 20) -> list[OccurrenceView]:
        end_at = now + timedelta(days=self.defaults.materialize_days)
        return self.list_occurrences(start_at=now, end_at=end_at, limit=limit)

    def due_jobs(self, *, now: datetime, limit: int = 20) -> list[NotificationJobView]:
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT
                    nj.id AS job_id,
                    nj.event_id,
                    nj.occurrence_id,
                    nj.notification_rule_id,
                    nj.notify_at,
                    nj.status AS job_status,
                    eo.occurs_at,
                    e.title,
                    e.description,
                    e.event_type,
                    COALESCE(eo.all_day_override, e.all_day) AS all_day
                FROM notification_jobs nj
                JOIN event_occurrences eo ON eo.id = nj.occurrence_id
                JOIN events e ON e.id = nj.event_id
                WHERE nj.status = ?
                  AND e.status = ?
                  AND eo.status = ?
                  AND nj.notify_at <= ?
                ORDER BY nj.notify_at ASC
                LIMIT ?
                """,
                (PENDING, ACTIVE, SCHEDULED, iso(now), max(1, min(100, limit))),
            ).fetchall()
        return [notification_job_view_from_row(row) for row in rows]

    def mark_job_sent(self, job_id: str, *, message_id: int | None, now: datetime) -> None:
        with self.db.session() as conn:
            conn.execute(
                """
                UPDATE notification_jobs
                SET status = 'sent', sent_at = ?, telegram_message_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (iso(now), message_id, iso(now), job_id),
            )

    def mark_job_failed(self, job_id: str, *, reason: str, now: datetime) -> None:
        with self.db.session() as conn:
            conn.execute(
                """
                UPDATE notification_jobs
                SET status = 'failed', failure_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (reason[:500], iso(now), job_id),
            )

    def complete_occurrence(self, occurrence_id: str, *, now: datetime) -> None:
        with self.db.session() as conn:
            conn.execute(
                "UPDATE event_occurrences SET status = 'done' WHERE id = ?",
                (occurrence_id,),
            )
            row = conn.execute(
                """
                SELECT e.id, e.recurrence_json
                FROM events e
                JOIN event_occurrences eo ON eo.event_id = e.id
                WHERE eo.id = ?
                """,
                (occurrence_id,),
            ).fetchone()
            if row and json.loads(row["recurrence_json"] or "{}").get("frequency") == "none":
                conn.execute(
                    "UPDATE events SET status = 'completed', updated_at = ? WHERE id = ?",
                    (iso(now), row["id"]),
                )
            conn.execute(
                """
                UPDATE notification_jobs
                SET status = 'cancelled', updated_at = ?
                WHERE occurrence_id = ? AND status = 'pending'
                """,
                (iso(now), occurrence_id),
            )

    def snooze_job(self, job_id: str, *, minutes: int, now: datetime) -> str:
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT event_id, occurrence_id, notification_rule_id
                FROM notification_jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Notification job not found: {job_id}")
            new_job_id = new_id("job_")
            notify_at = now + timedelta(minutes=minutes)
            conn.execute(
                """
                INSERT INTO notification_jobs (
                    id, event_id, occurrence_id, notification_rule_id, notify_at,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    new_job_id,
                    row["event_id"],
                    row["occurrence_id"],
                    row["notification_rule_id"],
                    iso(notify_at),
                    iso(now),
                    iso(now),
                ),
            )
        return new_job_id

    def reschedule_occurrence(
        self,
        occurrence_id: str,
        *,
        target: RescheduleTarget,
        now: datetime,
    ) -> OccurrenceView:
        _validate_reschedule_target(target, now=now)
        with self.db.session() as conn:
            row = _occurrence_event_row(conn, occurrence_id)
            if not row:
                raise ValueError(f"Occurrence not found: {occurrence_id}")
            recurrence = json.loads(row["recurrence_json"] or "{}")
            if _is_recurring(recurrence):
                conn.execute(
                    "UPDATE event_occurrences SET status = ? WHERE id = ?",
                    ("cancelled", occurrence_id),
                )
                _cancel_pending_jobs_for_occurrence(conn, occurrence_id=occurrence_id, now=now)
                new_occurrence_id = _ensure_occurrence(
                    conn,
                    event_id=row["event_id"],
                    target=target,
                    now=now,
                    all_day_override=target.all_day,
                )
                _create_jobs_for_occurrence(
                    conn,
                    event_id=row["event_id"],
                    occurrence_id=new_occurrence_id,
                    occurs_at=target.occurs_at,
                    now=now,
                    default_hhmm=self.defaults.day_reminder_hhmm,
                )
            else:
                new_occurrence_id = occurrence_id
                _write_event_schedule(conn, event_id=row["event_id"], target=target, now=now)
                _move_occurrence(conn, occurrence_id=occurrence_id, target=target)
                _cancel_pending_jobs_for_occurrence(conn, occurrence_id=occurrence_id, now=now)
                _maybe_rebuild_default_rules(
                    conn,
                    event_id=row["event_id"],
                    event_type=row["event_type"],
                    recurrence=recurrence,
                    target=target,
                    now=now,
                    defaults=self.defaults,
                )
                _create_jobs_for_occurrence(
                    conn,
                    event_id=row["event_id"],
                    occurrence_id=occurrence_id,
                    occurs_at=target.occurs_at,
                    now=now,
                    default_hhmm=self.defaults.day_reminder_hhmm,
                )
        return self.get_occurrence(new_occurrence_id)

    def reschedule_series_from_occurrence(
        self,
        occurrence_id: str,
        *,
        target: RescheduleTarget,
        now: datetime,
    ) -> OccurrenceView:
        event = self.get_event_for_occurrence(occurrence_id)
        if not self.is_recurring(event):
            return self.reschedule_occurrence(occurrence_id, target=target, now=now)

        _validate_reschedule_target(target, now=now)
        with self.db.session() as conn:
            row = _occurrence_event_row(conn, occurrence_id)
            if not row:
                raise ValueError(f"Occurrence not found: {occurrence_id}")
            recurrence = _rescheduled_recurrence(json.loads(row["recurrence_json"] or "{}"), target=target)
            _write_event_schedule(
                conn,
                event_id=row["event_id"],
                target=target,
                now=now,
                recurrence=recurrence,
            )
            _cancel_scheduled_occurrences_from(
                conn,
                event_id=row["event_id"],
                occurs_at=datetime.fromisoformat(row["occurs_at"]),
                now=now,
            )
            _ensure_occurrence(
                conn,
                event_id=row["event_id"],
                target=target,
                now=now,
                all_day_override=target.all_day,
            )
            _maybe_rebuild_default_rules(
                conn,
                event_id=row["event_id"],
                event_type=row["event_type"],
                recurrence=recurrence,
                target=target,
                now=now,
                defaults=self.defaults,
            )
        self.materialize_event(event.id, now=now)
        new_occurrence_id = self._occurrence_id_by_event_datetime(event.id, target.occurs_at)
        return self.get_occurrence(new_occurrence_id)

    def _occurrence_id_by_event_datetime(self, event_id: str, occurs_at: datetime) -> str:
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM event_occurrences
                WHERE event_id = ?
                  AND occurs_at = ?
                  AND status = ?
                """,
                (event_id, iso(occurs_at), SCHEDULED),
            ).fetchone()
        if not row:
            raise ValueError(f"Occurrence not found after reschedule: {event_id} {iso(occurs_at)}")
        return row["id"]

    def cancel_event(self, event_id: str, *, now: datetime) -> None:
        with self.db.session() as conn:
            conn.execute(
                "UPDATE events SET status = 'cancelled', updated_at = ? WHERE id = ?",
                (iso(now), event_id),
            )
            conn.execute(
                "UPDATE notification_jobs SET status = 'cancelled', updated_at = ? WHERE event_id = ? AND status = 'pending'",
                (iso(now), event_id),
            )

    def cancel_occurrence(self, occurrence_id: str, *, now: datetime) -> None:
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT eo.id, eo.event_id, e.recurrence_json
                FROM event_occurrences eo
                JOIN events e ON e.id = eo.event_id
                WHERE eo.id = ?
                """,
                (occurrence_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Occurrence not found: {occurrence_id}")
            conn.execute(
                "UPDATE event_occurrences SET status = 'cancelled' WHERE id = ?",
                (occurrence_id,),
            )
            conn.execute(
                """
                UPDATE notification_jobs
                SET status = 'cancelled', updated_at = ?
                WHERE occurrence_id = ? AND status = 'pending'
                """,
                (iso(now), occurrence_id),
            )
            if not _is_recurring(json.loads(row["recurrence_json"] or "{}")):
                conn.execute(
                    "UPDATE events SET status = 'cancelled', updated_at = ? WHERE id = ?",
                    (iso(now), row["event_id"]),
                )

    def cancel_series_from_occurrence(self, occurrence_id: str, *, now: datetime) -> None:
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT eo.event_id, eo.occurs_at, eo.occurrence_date, e.recurrence_json
                FROM event_occurrences eo
                JOIN events e ON e.id = eo.event_id
                WHERE eo.id = ?
                """,
                (occurrence_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Occurrence not found: {occurrence_id}")
            recurrence = json.loads(row["recurrence_json"] or "{}")
            if not _is_recurring(recurrence):
                conn.execute(
                    "UPDATE events SET status = 'cancelled', updated_at = ? WHERE id = ?",
                    (iso(now), row["event_id"]),
                )
            else:
                stop_before = parse_date(row["occurrence_date"]) - timedelta(days=1)
                recurrence["until"] = stop_before.isoformat()
                conn.execute(
                    "UPDATE events SET recurrence_json = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(recurrence, ensure_ascii=False), iso(now), row["event_id"]),
                )
            conn.execute(
                """
                UPDATE event_occurrences
                SET status = 'cancelled'
                WHERE event_id = ?
                  AND status = ?
                  AND occurs_at >= ?
                """,
                (row["event_id"], SCHEDULED, row["occurs_at"]),
            )
            conn.execute(
                """
                UPDATE notification_jobs
                SET status = 'cancelled', updated_at = ?
                WHERE event_id = ?
                  AND status = 'pending'
                  AND occurrence_id IN (
                      SELECT id
                      FROM event_occurrences
                      WHERE event_id = ?
                        AND occurs_at >= ?
                  )
                """,
                (iso(now), row["event_id"], row["event_id"], row["occurs_at"]),
            )


def _occurrence_event_row(conn, occurrence_id: str):
    return conn.execute(
        """
        SELECT
            eo.id AS occurrence_id,
            eo.event_id,
            eo.occurs_at,
            eo.occurrence_date,
            eo.status AS occurrence_status,
            e.event_type,
            e.recurrence_json
        FROM event_occurrences eo
        JOIN events e ON e.id = eo.event_id
        WHERE eo.id = ?
        """,
        (occurrence_id,),
    ).fetchone()


def _validate_reschedule_target(target: RescheduleTarget, *, now: datetime) -> None:
    if target.all_day:
        if target.occurs_at.date() < now.date():
            raise ValueError("Target date is in the past")
        return
    if target.occurs_at <= now.replace(second=0, microsecond=0):
        raise ValueError("Target datetime is in the past")


def _write_event_schedule(
    conn,
    *,
    event_id: str,
    target: RescheduleTarget,
    now: datetime,
    recurrence: dict[str, Any] | None = None,
) -> None:
    start_at = None if target.all_day else iso(target.occurs_at)
    event_time = None if target.all_day else target.occurs_at.strftime("%H:%M")
    if recurrence is None:
        conn.execute(
            """
            UPDATE events
            SET all_day = ?,
                start_at = ?,
                event_date = ?,
                event_time = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                1 if target.all_day else 0,
                start_at,
                target.occurs_at.date().isoformat(),
                event_time,
                iso(now),
                event_id,
            ),
        )
        return
    conn.execute(
        """
        UPDATE events
        SET all_day = ?,
            start_at = ?,
            event_date = ?,
            event_time = ?,
            recurrence_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            1 if target.all_day else 0,
            start_at,
            target.occurs_at.date().isoformat(),
            event_time,
            json.dumps(recurrence, ensure_ascii=False),
            iso(now),
            event_id,
        ),
    )


def _move_occurrence(conn, *, occurrence_id: str, target: RescheduleTarget) -> None:
    conn.execute(
        """
        UPDATE event_occurrences
        SET occurs_at = ?,
            occurrence_date = ?,
            status = ?,
            all_day_override = NULL
        WHERE id = ?
        """,
        (iso(target.occurs_at), target.occurs_at.date().isoformat(), SCHEDULED, occurrence_id),
    )


def _ensure_occurrence(
    conn,
    *,
    event_id: str,
    target: RescheduleTarget,
    now: datetime,
    all_day_override: bool,
) -> str:
    row = conn.execute(
        """
        SELECT id
        FROM event_occurrences
        WHERE event_id = ?
          AND occurs_at = ?
        """,
        (event_id, iso(target.occurs_at)),
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE event_occurrences
            SET occurrence_date = ?,
                status = ?,
                all_day_override = ?
            WHERE id = ?
            """,
            (target.occurs_at.date().isoformat(), SCHEDULED, 1 if all_day_override else 0, row["id"]),
        )
        return row["id"]

    occurrence_id = new_id("occ_")
    conn.execute(
        """
        INSERT INTO event_occurrences (
            id, event_id, occurs_at, occurrence_date, status, created_at,
            all_day_override
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            occurrence_id,
            event_id,
            iso(target.occurs_at),
            target.occurs_at.date().isoformat(),
            SCHEDULED,
            iso(now),
            1 if all_day_override else 0,
        ),
    )
    return occurrence_id


def _cancel_pending_jobs_for_occurrence(conn, *, occurrence_id: str, now: datetime) -> None:
    conn.execute(
        """
        UPDATE notification_jobs
        SET status = 'cancelled', updated_at = ?
        WHERE occurrence_id = ?
          AND status = 'pending'
        """,
        (iso(now), occurrence_id),
    )


def _cancel_scheduled_occurrences_from(conn, *, event_id: str, occurs_at: datetime, now: datetime) -> None:
    conn.execute(
        """
        UPDATE event_occurrences
        SET status = 'cancelled'
        WHERE event_id = ?
          AND status = ?
          AND occurs_at >= ?
        """,
        (event_id, SCHEDULED, iso(occurs_at)),
    )
    conn.execute(
        """
        UPDATE notification_jobs
        SET status = 'cancelled', updated_at = ?
        WHERE event_id = ?
          AND status = 'pending'
          AND occurrence_id IN (
              SELECT id
              FROM event_occurrences
              WHERE event_id = ?
                AND occurs_at >= ?
          )
        """,
        (iso(now), event_id, event_id, iso(occurs_at)),
    )


def _create_jobs_for_occurrence(
    conn,
    *,
    event_id: str,
    occurrence_id: str,
    occurs_at: datetime,
    now: datetime,
    default_hhmm: tuple[int, int],
) -> None:
    created = iso(now)
    rules = [
        notification_rule_from_row(row)
        for row in conn.execute(
            "SELECT * FROM notification_rules WHERE event_id = ? AND enabled = 1",
            (event_id,),
        ).fetchall()
    ]
    for rule in rules:
        notify_at = _notification_datetime(occurs_at, rule, default_hhmm=default_hhmm)
        if notify_at < now.replace(microsecond=0):
            continue
        conn.execute(
            """
            INSERT INTO notification_jobs (
                id, event_id, occurrence_id, notification_rule_id, notify_at,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(occurrence_id, notification_rule_id, notify_at) DO NOTHING
            """,
            (
                new_id("job_"),
                event_id,
                occurrence_id,
                rule.id,
                iso(notify_at),
                PENDING,
                created,
                created,
            ),
        )


def _maybe_rebuild_default_rules(
    conn,
    *,
    event_id: str,
    event_type: str,
    recurrence: dict[str, Any],
    target: RescheduleTarget,
    now: datetime,
    defaults: EventDefaults,
) -> None:
    explicit_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM notification_rules
        WHERE event_id = ?
          AND enabled = 1
          AND source = 'explicit'
        """,
        (event_id,),
    ).fetchone()["count"]
    if explicit_count:
        return

    conn.execute(
        "UPDATE notification_rules SET enabled = 0 WHERE event_id = ? AND enabled = 1",
        (event_id,),
    )
    for rule in build_notification_rules(
        _policy_item(event_type=event_type, recurrence=recurrence, target=target),
        now=now,
        defaults=defaults,
    ):
        conn.execute(
            """
            INSERT INTO notification_rules (
                id, event_id, kind, minutes_before, time_of_day, source,
                enabled, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("rule_"),
                event_id,
                rule.kind,
                rule.minutes_before,
                rule.time_of_day,
                rule.source,
                1,
                iso(now),
            ),
        )


def _policy_item(*, event_type: str, recurrence: dict[str, Any], target: RescheduleTarget) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "temporal_profile": _target_temporal_profile(event_type=event_type, recurrence=recurrence, target=target),
        "schedule": {
            "kind": "recurring" if _is_recurring(recurrence) else "once",
            "all_day": target.all_day,
            "start_at": None if target.all_day else iso(target.occurs_at),
            "date": target.occurs_at.date().isoformat(),
            "time": None if target.all_day else target.occurs_at.strftime("%H:%M"),
            "recurrence": recurrence,
        },
        "notification_offsets": [],
    }


def _target_temporal_profile(*, event_type: str, recurrence: dict[str, Any], target: RescheduleTarget) -> str:
    frequency = _clean(recurrence.get("frequency")) or "none"
    if frequency == "yearly" or event_type in {"birthday", "anniversary"}:
        return "annual_date"
    if frequency != "none":
        return "recurring_day_task" if target.all_day else "recurring_exact_time"
    if event_type == "deadline":
        return "deadline"
    return "day_task" if target.all_day else "exact_time"


def _rescheduled_recurrence(recurrence: dict[str, Any], *, target: RescheduleTarget) -> dict[str, Any]:
    result = {**recurrence}
    frequency = _clean(result.get("frequency")) or "none"
    if frequency == "weekly":
        result["weekdays"] = [_weekday_code(target.occurs_at)]
    elif frequency == "monthly":
        result["month_days"] = [target.occurs_at.day]
    elif frequency == "yearly":
        result["months"] = [target.occurs_at.month]
        result["month_days"] = [target.occurs_at.day]
    return result


def _weekday_code(value: datetime) -> str:
    return ("MO", "TU", "WE", "TH", "FR", "SA", "SU")[value.weekday()]


def _event_time(event: Event, default_hhmm: tuple[int, int]):
    if event.event_time:
        return parse_time(event.event_time, default=default_hhmm)
    if event.start_at:
        return event.start_at.time().replace(second=0, microsecond=0)
    return parse_time(None, default=default_hhmm)


def _notification_datetime(occurs_at: datetime, rule, *, default_hhmm: tuple[int, int]) -> datetime:
    if rule.kind == "time_of_day":
        notify_date = occurs_at.date() - timedelta(days=rule.minutes_before)
        notify_time = parse_time(rule.time_of_day, default=default_hhmm)
        return datetime.combine(notify_date, notify_time)
    return occurs_at - timedelta(minutes=rule.minutes_before)


def _normalize_recurrence(value: dict[str, Any]) -> dict[str, Any]:
    frequency = _clean(value.get("frequency")) or "none"
    return {
        "frequency": frequency,
        "interval": max(1, int(value.get("interval") or 1)),
        "weekdays": [str(item).upper() for item in value.get("weekdays", []) if str(item).strip()],
        "month_days": [int(item) for item in value.get("month_days", []) if str(item).strip()],
        "months": [int(item) for item in value.get("months", []) if str(item).strip()],
        "until": value.get("until"),
        "count": value.get("count"),
        "rrule": _clean(value.get("rrule")),
    }


def _is_recurring(recurrence: dict[str, Any]) -> bool:
    return (_clean(recurrence.get("frequency")) or "none") != "none"


def _parse_datetime_or_none(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=None, microsecond=0)


def _clean(value: Any) -> str:
    return str(value or "").strip()
