from __future__ import annotations

from datetime import datetime
from unittest import TestCase

from app.features.events.reschedule import parse_reschedule_target, quick_reschedule_target


class RescheduleParserTest(TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 24, 17, 30)
        self.current = datetime(2026, 7, 25, 9, 0)

    def test_parses_tomorrow_as_all_day(self) -> None:
        target = self._parse("завтра")

        self.assertTrue(target.all_day)
        self.assertEqual(target.occurs_at, datetime(2026, 7, 25, 9, 0))

    def test_parses_time_on_current_occurrence_date(self) -> None:
        target = self._parse("в 18:30")

        self.assertFalse(target.all_day)
        self.assertEqual(target.occurs_at, datetime(2026, 7, 25, 18, 30))

    def test_parses_relative_hours_from_now(self) -> None:
        target = self._parse("через 2 часа")

        self.assertFalse(target.all_day)
        self.assertEqual(target.occurs_at, datetime(2026, 7, 24, 19, 30))

    def test_parses_weekday(self) -> None:
        target = self._parse("в понедельник")

        self.assertTrue(target.all_day)
        self.assertEqual(target.occurs_at, datetime(2026, 7, 27, 9, 0))

    def test_quick_shift_series_uses_current_occurrence(self) -> None:
        target = quick_reschedule_target(
            "plus_1h",
            now=self.now,
            current_occurs_at=self.current,
            current_all_day=False,
            default_day_hhmm=(9, 0),
            evening_hhmm=(20, 0),
            relative_to_current=True,
        )

        self.assertEqual(target.occurs_at, datetime(2026, 7, 25, 10, 0))

    def test_quick_tomorrow_preserves_exact_time(self) -> None:
        target = quick_reschedule_target(
            "tomorrow",
            now=self.now,
            current_occurs_at=datetime(2026, 7, 25, 15, 30),
            current_all_day=False,
            default_day_hhmm=(9, 0),
            evening_hhmm=(20, 0),
        )

        self.assertFalse(target.all_day)
        self.assertEqual(target.occurs_at, datetime(2026, 7, 25, 15, 30))

    def _parse(self, text: str):
        return parse_reschedule_target(
            text,
            now=self.now,
            current_occurs_at=self.current,
            default_day_hhmm=(9, 0),
            evening_hhmm=(20, 0),
        )
