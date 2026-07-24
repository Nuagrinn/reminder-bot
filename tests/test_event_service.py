from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.core.db import MIGRATIONS_DIR
from app.features.events.service import EventDefaults, EventService
from app.features.reminder_intake.agent import FakeReminderParserAgent
from tests.test_fake_parser import request

from assistant_toolkit.db import Database


class EventServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "reminder.sqlite3", migrations_dir=MIGRATIONS_DIR)
        self.db.migrate()
        self.service = EventService(
            self.db,
            EventDefaults(
                timezone="Europe/Moscow",
                day_reminder_hhmm=(9, 0),
                timed_event_offset_minutes=120,
                birthday_offsets_minutes=(1440, 0),
                materialize_days=180,
            ),
        )
        self.now = datetime(2026, 7, 24, 12, 0)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _create(self, text: str):
        payload = FakeReminderParserAgent().parse(request(text)).payload
        return self.service.create_from_agent_item(
            payload["items"][0],
            source_text=text,
            source_kind="text",
            now=self.now,
        )

    def test_creates_one_off_all_day_event_and_default_job(self) -> None:
        event = self._create("надо завтра пополнить карту наличкой")
        upcoming = self.service.upcoming(now=self.now, limit=10)
        due_day_before = self.service.due_jobs(now=datetime(2026, 7, 24, 20, 0), limit=10)
        due_evening_check = self.service.due_jobs(now=datetime(2026, 7, 25, 20, 0), limit=10)

        self.assertEqual(event.title, "Пополнить карту наличкой")
        self.assertEqual(len(upcoming), 1)
        self.assertEqual(upcoming[0].occurs_at, datetime(2026, 7, 25, 9, 0))
        self.assertEqual(upcoming[0].next_notify_at, datetime(2026, 7, 24, 20, 0))
        self.assertEqual(due_day_before[0].notify_at, datetime(2026, 7, 24, 20, 0))
        self.assertEqual(due_evening_check[-1].notify_at, datetime(2026, 7, 25, 20, 0))

    def test_get_occurrence_returns_detail_view(self) -> None:
        self._create("надо завтра пополнить карту наличкой")
        occurrence = self.service.upcoming(now=self.now, limit=1)[0]

        detail = self.service.get_occurrence(occurrence.occurrence_id)

        self.assertEqual(detail.occurrence_id, occurrence.occurrence_id)
        self.assertEqual(detail.title, "Пополнить карту наличкой")

    def test_due_job_for_relative_timed_event(self) -> None:
        self._create("через 2 часа проверить духовку")
        due = self.service.due_jobs(now=datetime(2026, 7, 24, 14, 0), limit=10)

        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].occurs_at, datetime(2026, 7, 24, 14, 0))
        self.assertEqual(due[0].notify_at, datetime(2026, 7, 24, 14, 0))

    def test_today_exact_time_gets_hour_and_quarter_jobs(self) -> None:
        self._create("сегодня в 15:30 оплатить счет")
        due_first = self.service.due_jobs(now=datetime(2026, 7, 24, 14, 30), limit=10)
        due_second = self.service.due_jobs(now=datetime(2026, 7, 24, 15, 15), limit=10)

        self.assertEqual(due_first[0].notify_at, datetime(2026, 7, 24, 14, 30))
        self.assertEqual(due_second[-1].notify_at, datetime(2026, 7, 24, 15, 15))

    def test_snooze_creates_new_pending_job(self) -> None:
        self._create("через 2 часа проверить духовку")
        due_at_event = datetime(2026, 7, 24, 14, 0)
        job = self.service.due_jobs(now=due_at_event, limit=10)[0]
        self.service.mark_job_sent(job.job_id, message_id=123, now=due_at_event)
        new_job_id = self.service.snooze_job(job.job_id, minutes=60, now=due_at_event)
        due_now = self.service.due_jobs(now=due_at_event, limit=10)
        due_later = self.service.due_jobs(now=datetime(2026, 7, 24, 15, 0), limit=10)

        self.assertTrue(new_job_id.startswith("job_"))
        self.assertEqual(len(due_now), 0)
        self.assertEqual(len(due_later), 1)

    def test_weekly_recurring_materializes_next_tuesdays(self) -> None:
        self._create("каждый вторник обновлять отчет по калориям")
        upcoming = self.service.upcoming(now=self.now, limit=3)

        self.assertGreaterEqual(len(upcoming), 3)
        self.assertEqual(upcoming[0].occurs_at.date().isoformat(), "2026-07-28")
        self.assertEqual(upcoming[1].occurs_at.date().isoformat(), "2026-08-04")

    def test_cancel_occurrence_skips_only_one_recurring_item(self) -> None:
        self._create("каждый вторник обновлять отчет по калориям")
        first = self.service.upcoming(now=self.now, limit=3)[0]

        self.service.cancel_occurrence(first.occurrence_id, now=self.now)
        self.service.materialize_event(first.event_id, now=self.now)
        upcoming = self.service.upcoming(now=self.now, limit=3)
        with self.db.session() as conn:
            row = conn.execute("SELECT status FROM event_occurrences WHERE id = ?", (first.occurrence_id,)).fetchone()
            pending_jobs = conn.execute(
                "SELECT COUNT(*) AS count FROM notification_jobs WHERE occurrence_id = ? AND status = 'pending'",
                (first.occurrence_id,),
            ).fetchone()["count"]

        self.assertEqual(row["status"], "cancelled")
        self.assertEqual(pending_jobs, 0)
        self.assertEqual(upcoming[0].occurs_at.date().isoformat(), "2026-08-04")

    def test_cancel_series_from_occurrence_keeps_previous_and_stops_future(self) -> None:
        self._create("каждый вторник обновлять отчет по калориям")
        first, second, third = self.service.upcoming(now=self.now, limit=3)

        self.service.cancel_series_from_occurrence(second.occurrence_id, now=self.now)
        upcoming = self.service.upcoming(now=self.now, limit=5)
        event = self.service.get_event(first.event_id)
        with self.db.session() as conn:
            second_row = conn.execute("SELECT status FROM event_occurrences WHERE id = ?", (second.occurrence_id,)).fetchone()
            third_row = conn.execute("SELECT status FROM event_occurrences WHERE id = ?", (third.occurrence_id,)).fetchone()

        self.assertEqual([item.occurs_at.date().isoformat() for item in upcoming], ["2026-07-28"])
        self.assertEqual(event.recurrence["until"], "2026-08-03")
        self.assertEqual(second_row["status"], "cancelled")
        self.assertEqual(third_row["status"], "cancelled")

    def test_every_two_days_materializes_interval(self) -> None:
        self._create("каждые два дня проверять почту")
        upcoming = self.service.upcoming(now=self.now, limit=3)

        self.assertEqual([item.occurs_at.date().isoformat() for item in upcoming], [
            "2026-07-25",
            "2026-07-27",
            "2026-07-29",
        ])

    def test_birthday_creates_two_default_jobs(self) -> None:
        self._create("12 августа день рождения Маши")
        upcoming = self.service.upcoming(now=self.now, limit=3)
        due_week_before = self.service.due_jobs(now=datetime(2026, 8, 5, 9, 0), limit=10)
        due_day_before = self.service.due_jobs(now=datetime(2026, 8, 11, 20, 0), limit=10)
        day_before_notify_times = [item.notify_at for item in due_day_before]

        self.assertEqual(upcoming[0].occurs_at, datetime(2026, 8, 12, 9, 0))
        self.assertEqual(len(due_week_before), 1)
        self.assertEqual(due_week_before[0].notify_at, datetime(2026, 8, 5, 9, 0))
        self.assertIn(datetime(2026, 8, 11, 20, 0), day_before_notify_times)


if __name__ == "__main__":
    unittest.main()
