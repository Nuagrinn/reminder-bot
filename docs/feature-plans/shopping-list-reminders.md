# Shopping List Reminders

Date: 2026-07-28
Status: MVP implemented

## Goal

Make a shopping reminder that can be created quickly by text or voice and then
edited as a nested checklist:

```text
купить корм для кошек, молоко, хлеб, яйца
```

The reminder should behave like a normal scheduled event, but its content should
be a mutable list rather than one flat title/description.

## Architecture

The MVP keeps scheduling in the existing event stack:

- `events`;
- `event_occurrences`;
- `notification_rules`;
- `notification_jobs`.

Shopping-specific data is stored separately:

- `shopping_lists`: one active list per event;
- `shopping_items`: ordered items with `open`, `done`, `deleted`.

This keeps shopping list editing independent from recurrence and notification
logic. It also leaves room for future checklist-like features without forcing
more values into `event_type`.

## Parser Contract

The parser keeps broad compatibility metadata:

```json
{
  "event_type": "task",
  "content": {
    "kind": "shopping_list",
    "shopping_list": {
      "title": "Покупки",
      "items": [
        {"title": "молоко", "quantity": "", "note": ""}
      ]
    }
  }
}
```

If there is no explicit date/time, shopping lists default to today as an all-day
`day_task`. Explicit date/time still wins.

## Telegram UX

MVP controls:

- reply button `🛒 Покупки`;
- `/shopping`;
- shopping detail card;
- item number buttons;
- per-item actions: `Куплено` / `Вернуть`, `Удалить`, `Назад к списку`;
- `Добавить` mode that accepts the next text or voice message as more items;
- normal reminder actions: `Готово`, `Напомнить +1ч`, `На завтра`,
  `Перенести`, `Удалить`, `Скрыть`.

## Next Iterations

- Natural-language edits: `удали молоко`, `вычеркни хлеб`, `замени кофе на чай`.
- Multiple active shopping lists selection.
- Better quantity parsing and product normalization.
- Optional categories for large lists.
- Reusable templates such as weekly groceries.
