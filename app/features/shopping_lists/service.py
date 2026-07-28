from __future__ import annotations

from datetime import datetime

from assistant_toolkit.db import Database

from app.core.ids import new_id
from app.core.time import iso
from app.features.shopping_lists.models import (
    SHOPPING_ITEM_DELETED,
    SHOPPING_ITEM_DONE,
    SHOPPING_ITEM_OPEN,
    SHOPPING_STATUS_ACTIVE,
    ShoppingItem,
    ShoppingItemDraft,
    ShoppingListDetail,
    shopping_item_from_row,
    shopping_list_from_row,
)


class ShoppingListService:
    def __init__(self, db: Database):
        self.db = db

    def create_for_event(
        self,
        event_id: str,
        *,
        title: str,
        items: list[ShoppingItemDraft],
        source_text: str,
        source_kind: str,
        now: datetime,
    ) -> ShoppingListDetail:
        created = now.replace(microsecond=0)
        list_id = new_id("shop_")
        clean_title = _clean(title) or "Покупки"
        with self.db.session() as conn:
            existing = conn.execute(
                "SELECT id FROM shopping_lists WHERE event_id = ? AND status = ?",
                (event_id, SHOPPING_STATUS_ACTIVE),
            ).fetchone()
            if existing:
                list_id = existing["id"]
            else:
                conn.execute(
                    """
                    INSERT INTO shopping_lists (
                        id, event_id, title, status, source_text, source_kind,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        list_id,
                        event_id,
                        clean_title,
                        SHOPPING_STATUS_ACTIVE,
                        source_text,
                        source_kind,
                        iso(created),
                        iso(created),
                    ),
                )
            self._insert_items(conn, list_id, items, source_text=source_text, source_kind=source_kind, now=created)
        return self.get_by_id(list_id)

    def add_items(
        self,
        list_id: str,
        items: list[ShoppingItemDraft],
        *,
        source_text: str,
        source_kind: str,
        now: datetime,
    ) -> ShoppingListDetail:
        created = now.replace(microsecond=0)
        with self.db.session() as conn:
            self._require_list(conn, list_id)
            self._insert_items(conn, list_id, items, source_text=source_text, source_kind=source_kind, now=created)
            conn.execute(
                "UPDATE shopping_lists SET updated_at = ? WHERE id = ?",
                (iso(created), list_id),
            )
        return self.get_by_id(list_id)

    def get_by_event_id(self, event_id: str) -> ShoppingListDetail | None:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT * FROM shopping_lists WHERE event_id = ? AND status = ?",
                (event_id, SHOPPING_STATUS_ACTIVE),
            ).fetchone()
        if not row:
            return None
        return self.get_by_id(row["id"])

    def get_by_id(self, list_id: str) -> ShoppingListDetail:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT * FROM shopping_lists WHERE id = ? AND status = ?",
                (list_id, SHOPPING_STATUS_ACTIVE),
            ).fetchone()
            if not row:
                raise ValueError(f"Shopping list not found: {list_id}")
            item_rows = conn.execute(
                """
                SELECT *
                FROM shopping_items
                WHERE shopping_list_id = ? AND status != ?
                ORDER BY position, created_at, id
                """,
                (list_id, SHOPPING_ITEM_DELETED),
            ).fetchall()
        return ShoppingListDetail(
            shopping_list=shopping_list_from_row(row),
            items=tuple(shopping_item_from_row(item) for item in item_rows),
        )

    def get_by_item_id(self, item_id: str) -> tuple[ShoppingListDetail, ShoppingItem]:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT * FROM shopping_items WHERE id = ? AND status != ?",
                (item_id, SHOPPING_ITEM_DELETED),
            ).fetchone()
        if not row:
            raise ValueError(f"Shopping item not found: {item_id}")
        item = shopping_item_from_row(row)
        detail = self.get_by_id(item.shopping_list_id)
        return detail, item

    def toggle_item(self, item_id: str, *, now: datetime) -> tuple[ShoppingListDetail, ShoppingItem]:
        detail, item = self.get_by_item_id(item_id)
        next_status = SHOPPING_ITEM_OPEN if item.status == SHOPPING_ITEM_DONE else SHOPPING_ITEM_DONE
        updated = now.replace(microsecond=0)
        completed_at = iso(updated) if next_status == SHOPPING_ITEM_DONE else None
        with self.db.session() as conn:
            conn.execute(
                """
                UPDATE shopping_items
                SET status = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_status, completed_at, iso(updated), item_id),
            )
            conn.execute(
                "UPDATE shopping_lists SET updated_at = ? WHERE id = ?",
                (iso(updated), detail.shopping_list.id),
            )
        return self.get_by_item_id(item_id)

    def delete_item(self, item_id: str, *, now: datetime) -> ShoppingListDetail:
        detail, item = self.get_by_item_id(item_id)
        updated = now.replace(microsecond=0)
        with self.db.session() as conn:
            conn.execute(
                """
                UPDATE shopping_items
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (SHOPPING_ITEM_DELETED, iso(updated), item.id),
            )
            conn.execute(
                "UPDATE shopping_lists SET updated_at = ? WHERE id = ?",
                (iso(updated), detail.shopping_list.id),
            )
        return self.get_by_id(detail.shopping_list.id)

    def _insert_items(
        self,
        conn,
        list_id: str,
        items: list[ShoppingItemDraft],
        *,
        source_text: str,
        source_kind: str,
        now: datetime,
    ) -> None:
        clean_items = [item for item in items if _clean(item.title)]
        if not clean_items:
            return
        row = conn.execute(
            "SELECT COALESCE(MAX(position), 0) AS max_position FROM shopping_items WHERE shopping_list_id = ?",
            (list_id,),
        ).fetchone()
        position = int(row["max_position"] or 0)
        for item in clean_items:
            position += 1
            conn.execute(
                """
                INSERT INTO shopping_items (
                    id, shopping_list_id, title, quantity, note, status, position,
                    source_text, source_kind, created_at, updated_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("shopi_"),
                    list_id,
                    _clean(item.title),
                    _clean(item.quantity),
                    _clean(item.note),
                    SHOPPING_ITEM_OPEN,
                    position,
                    source_text,
                    source_kind,
                    iso(now),
                    iso(now),
                    None,
                ),
            )

    def _require_list(self, conn, list_id: str) -> None:
        row = conn.execute(
            "SELECT id FROM shopping_lists WHERE id = ? AND status = ?",
            (list_id, SHOPPING_STATUS_ACTIVE),
        ).fetchone()
        if not row:
            raise ValueError(f"Shopping list not found: {list_id}")


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())
