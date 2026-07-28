# 2026-07-28 - Completed Occurrence Display

## Summary

Changed `Готово` semantics so completed reminders stay visible in their list
period instead of disappearing from today's plan.

## Changes

- `complete_occurrence` marks only the occurrence as `done`.
- One-off events are no longer moved to event status `completed` when pressing
  `Готово`.
- Occurrence lists include `scheduled` and `done` rows inside the selected
  period.
- Overdue carry-over still applies only to unfinished `scheduled` rows, so
  completed past tasks do not leak into future days.
- Telegram renders completed reminders with `✓` and strikethrough title.
- Detail cards show `Статус: выполнено`.
- Shopping items that are marked bought are also rendered with strikethrough.

## Verification

```text
.venv\Scripts\python.exe -m unittest discover -s tests
140 tests OK
```
