from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from assistant_toolkit.db import Database

from app.core.db import MIGRATIONS_DIR
from app.features.events.service import EventDefaults, EventService
from app.features.reminder_intake.agent import FakeReminderParserAgent
from app.features.reminder_intake.service import ReminderIntakeService
from tests.test_fake_parser import request


class IntakeServiceTests(unittest.TestCase):
    def test_ingest_records_parse_attempt_and_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "reminder.sqlite3", migrations_dir=MIGRATIONS_DIR)
            db.migrate()
            events = EventService(db, EventDefaults(timezone="Europe/Moscow"))
            intake = ReminderIntakeService(db, FakeReminderParserAgent(), events)

            result = intake.ingest(request("надо завтра пополнить карту наличкой"))

            self.assertEqual(len(result.event_ids), 1)
            with db.session() as conn:
                attempts = conn.execute("SELECT * FROM parse_attempts").fetchall()
                events_rows = conn.execute("SELECT * FROM events").fetchall()

            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["status"], "ok")
            self.assertEqual(len(events_rows), 1)


if __name__ == "__main__":
    unittest.main()

