from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlite3 import Row


SHOPPING_STATUS_ACTIVE = "active"
SHOPPING_ITEM_OPEN = "open"
SHOPPING_ITEM_DONE = "done"
SHOPPING_ITEM_DELETED = "deleted"


@dataclass(frozen=True)
class ShoppingItemDraft:
    title: str
    quantity: str = ""
    note: str = ""


@dataclass(frozen=True)
class ShoppingList:
    id: str
    event_id: str
    title: str
    status: str
    source_text: str
    source_kind: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ShoppingItem:
    id: str
    shopping_list_id: str
    title: str
    quantity: str
    note: str
    status: str
    position: int
    source_text: str
    source_kind: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class ShoppingListDetail:
    shopping_list: ShoppingList
    items: tuple[ShoppingItem, ...]

    @property
    def open_items(self) -> tuple[ShoppingItem, ...]:
        return tuple(item for item in self.items if item.status == SHOPPING_ITEM_OPEN)

    @property
    def done_items(self) -> tuple[ShoppingItem, ...]:
        return tuple(item for item in self.items if item.status == SHOPPING_ITEM_DONE)


def shopping_list_from_row(row: Row) -> ShoppingList:
    return ShoppingList(
        id=row["id"],
        event_id=row["event_id"],
        title=row["title"],
        status=row["status"],
        source_text=row["source_text"],
        source_kind=row["source_kind"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def shopping_item_from_row(row: Row) -> ShoppingItem:
    completed_at = row["completed_at"]
    return ShoppingItem(
        id=row["id"],
        shopping_list_id=row["shopping_list_id"],
        title=row["title"],
        quantity=row["quantity"],
        note=row["note"],
        status=row["status"],
        position=int(row["position"]),
        source_text=row["source_text"],
        source_kind=row["source_kind"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
    )
