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
from app.features.shopping_lists.models import SHOPPING_ITEM_DONE
from app.features.shopping_lists.parser import parse_shopping_items
from app.features.shopping_lists.service import ShoppingListService
from tests.test_fake_parser import request


class ShoppingParserTests(unittest.TestCase):
    def test_parser_splits_shopping_items(self) -> None:
        items = parse_shopping_items("купить корм для кошек, молоко, хлеб и яйца")

        self.assertEqual([item.title for item in items], ["корм для кошек", "молоко", "хлеб", "яйца"])

    def test_fake_parser_creates_today_shopping_list_without_date(self) -> None:
        result = FakeReminderParserAgent().parse(request("купить молоко, хлеб, яйца"))
        item = result.payload["items"][0]

        self.assertEqual(result.payload["status"], "ok")
        self.assertEqual(item["title"], "Покупки")
        self.assertEqual(item["event_type"], "task")
        self.assertEqual(item["temporal_profile"], "day_task")
        self.assertEqual(item["schedule"]["date"], "2026-07-24")
        self.assertTrue(item["schedule"]["all_day"])
        self.assertEqual(item["content"]["kind"], "shopping_list")
        self.assertEqual(
            [raw["title"] for raw in item["content"]["shopping_list"]["items"]],
            ["молоко", "хлеб", "яйца"],
        )

    def test_fake_parser_keeps_explicit_shopping_time(self) -> None:
        result = FakeReminderParserAgent().parse(request("завтра в 14:00 купить молоко, хлеб"))
        item = result.payload["items"][0]

        self.assertEqual(item["title"], "Покупки")
        self.assertEqual(item["temporal_profile"], "exact_time")
        self.assertEqual(item["schedule"]["start_at"], "2026-07-25T14:00:00")
        self.assertEqual(
            [raw["title"] for raw in item["content"]["shopping_list"]["items"]],
            ["молоко", "хлеб"],
        )


class ShoppingListServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "reminder.sqlite3", migrations_dir=MIGRATIONS_DIR)
        self.db.migrate()
        self.events = EventService(self.db, EventDefaults(timezone="Europe/Moscow"))
        self.shopping_lists = ShoppingListService(self.db)
        self.intake = ReminderIntakeService(
            self.db,
            FakeReminderParserAgent(),
            self.events,
            self.shopping_lists,
        )
        self.now = datetime(2026, 7, 24, 12, 0)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_intake_creates_shopping_list_for_event(self) -> None:
        result = self.intake.ingest(request("купить молоко, хлеб, яйца"))

        self.assertEqual(len(result.event_ids), 1)
        detail = self.shopping_lists.get_by_event_id(result.event_ids[0])

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail.shopping_list.title, "Покупки")
        self.assertEqual([item.title for item in detail.items], ["молоко", "хлеб", "яйца"])

    def test_add_toggle_and_delete_items(self) -> None:
        result = self.intake.ingest(request("купить молоко, хлеб"))
        detail = self.shopping_lists.get_by_event_id(result.event_ids[0])
        assert detail is not None

        updated = self.shopping_lists.add_items(
            detail.shopping_list.id,
            parse_shopping_items("сыр, кофе"),
            source_text="сыр, кофе",
            source_kind="text",
            now=self.now,
        )
        self.assertEqual([item.title for item in updated.items], ["молоко", "хлеб", "сыр", "кофе"])

        _, toggled = self.shopping_lists.toggle_item(updated.items[0].id, now=self.now)
        self.assertEqual(toggled.status, SHOPPING_ITEM_DONE)

        deleted = self.shopping_lists.delete_item(updated.items[1].id, now=self.now)
        self.assertEqual([item.title for item in deleted.items], ["молоко", "сыр", "кофе"])


if __name__ == "__main__":
    unittest.main()
