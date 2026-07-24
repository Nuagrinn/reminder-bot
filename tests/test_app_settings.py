from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from assistant_toolkit.db import Database

from app.core.db import MIGRATIONS_DIR
from app.features.app_settings.service import AppSettingsService


class AppSettingsServiceTest(TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "reminder.sqlite3", migrations_dir=MIGRATIONS_DIR)
        self.db.migrate()
        self.service = AppSettingsService(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_daily_agenda_uses_default_until_overridden(self) -> None:
        self.assertTrue(self.service.is_daily_agenda_enabled(default=True))

        self.service.set_daily_agenda_enabled(False)

        self.assertFalse(self.service.is_daily_agenda_enabled(default=True))

    def test_last_notified_version_roundtrip(self) -> None:
        self.service.set_last_notified_version("abc123")

        self.assertEqual(self.service.last_notified_version(), "abc123")
