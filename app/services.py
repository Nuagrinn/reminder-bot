from __future__ import annotations

from assistant_toolkit.speech import build_speech_to_text

from app.config import Settings
from app.core.db import build_database
from app.features.app_settings.service import AppSettingsService
from app.features.events.service import EventDefaults, EventService
from app.features.reminder_intake.factory import build_reminder_parser_agent
from app.features.reminder_intake.service import ReminderIntakeService
from app.features.shopping_lists.service import ShoppingListService


class AppServices:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = build_database(settings.db_path)
        self.db.migrate()
        self.app_settings = AppSettingsService(self.db)
        self.events = EventService(
            self.db,
            EventDefaults(
                timezone=settings.timezone,
                day_reminder_hhmm=settings.default_day_reminder_hhmm,
                evening_reminder_hhmm=settings.default_evening_reminder_hhmm,
                day_before_reminder_hhmm=settings.default_day_before_reminder_hhmm,
                timed_event_offset_minutes=settings.default_timed_event_offset_minutes,
                exact_time_today_offsets_minutes=tuple(settings.default_exact_time_today_offsets_minutes),
                exact_time_future_offsets_minutes=tuple(settings.default_exact_time_future_offsets_minutes),
                birthday_offsets_minutes=tuple(settings.default_birthday_offsets_minutes),
                deadline_days_before=tuple(settings.default_deadline_days_before),
                annual_days_before=tuple(settings.default_annual_days_before),
                materialize_days=settings.materialize_days,
            ),
        )
        self.shopping_lists = ShoppingListService(self.db)
        self.parser = build_reminder_parser_agent(settings)
        self.intake = ReminderIntakeService(self.db, self.parser, self.events, self.shopping_lists)
        self.speech = build_speech_to_text(settings)
