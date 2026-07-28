# 2026-07-28 - Shopping List Reminders

## Summary

Implemented MVP shopping list reminders as nested editable checklists attached
to scheduled reminder events.

## Changes

- Added migration `005_shopping_lists.sql`.
- Added `app.features.shopping_lists` with:
  - data models;
  - deterministic shopping item parser;
  - persistence service.
- Extended parser schema to `reminder-parser-v4` with optional
  `content.kind=shopping_list`.
- Kept `event_type='task'` for shopping reminders.
- Added same-day default scheduling for shopping phrases without explicit date.
- Wired `ReminderIntakeService` to create shopping lists after event creation.
- Added Telegram shopping cards, item menus and pending add mode.
- Added reply button `🛒 Покупки` and command `/shopping`.
- Added tests for parser, persistence, formatters and keyboards.

## Notes

The auto-detector intentionally does not treat broad `заказать` phrases as
shopping. This keeps existing commands like `заказать креатин и протеин` as
normal reminders unless the phrase explicitly says `покупки`, `список покупок`
or uses clear `купить` wording with several items.

## Verification

```text
.venv\Scripts\python.exe -m unittest discover -s tests
137 tests OK
```
