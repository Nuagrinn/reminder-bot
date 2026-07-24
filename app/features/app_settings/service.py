from __future__ import annotations

from datetime import datetime

from assistant_toolkit.db import Database


DAILY_AGENDA_ENABLED_KEY = "daily_agenda_enabled"
LAST_NOTIFIED_VERSION_KEY = "app_version_last_notified"


class AppSettingsService:
    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: str = "") -> str:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str, *, now: datetime | None = None) -> None:
        updated = (now or datetime.now()).replace(microsecond=0).isoformat(timespec="seconds")
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, updated),
            )

    def is_daily_agenda_enabled(self, *, default: bool) -> bool:
        return _to_bool(self.get(DAILY_AGENDA_ENABLED_KEY, _bool_text(default)))

    def set_daily_agenda_enabled(self, enabled: bool, *, now: datetime | None = None) -> None:
        self.set(DAILY_AGENDA_ENABLED_KEY, _bool_text(enabled), now=now)

    def last_notified_version(self) -> str:
        return self.get(LAST_NOTIFIED_VERSION_KEY, "")

    def set_last_notified_version(self, version: str, *, now: datetime | None = None) -> None:
        self.set(LAST_NOTIFIED_VERSION_KEY, version, now=now)


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
