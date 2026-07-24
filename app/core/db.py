from __future__ import annotations

from assistant_toolkit.db import Database

from app.config import PROJECT_ROOT


MIGRATIONS_DIR = PROJECT_ROOT / "app" / "core" / "migrations"


def build_database(path) -> Database:
    return Database(path, migrations_dir=MIGRATIONS_DIR)

