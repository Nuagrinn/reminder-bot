from __future__ import annotations

from datetime import datetime, time
from unittest import TestCase

from app.features.events.recurrence import occurrence_datetimes


class RecurrenceTest(TestCase):
    def test_weekly_interval_is_respected(self) -> None:
        dates = occurrence_datetimes(
            recurrence={
                "frequency": "weekly",
                "interval": 2,
                "weekdays": ["MO"],
            },
            start_date=None,
            event_time=time(9, 0),
            now=datetime(2026, 7, 24, 12, 0),
            horizon_days=40,
        )

        self.assertEqual([item.date().isoformat() for item in dates[:3]], [
            "2026-07-27",
            "2026-08-10",
            "2026-08-24",
        ])

