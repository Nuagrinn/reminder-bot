# Reminder Bot Feature List

Date: 2026-07-24

## P0 - Current Focus

1. Real parser quality
   - Switch production flow from `PARSER_PROVIDER=fake` to Claude CLI.
   - Improve prompt/schema examples for exact dates, exact times, relative dates
     and recurring reminders.
   - Add parser tests from real phrases sent in Telegram.

2. Recurring reminders with intervals
   - Support phrases like `день через день надо делать замер веса`.
   - Support phrases like `каждые два дня проверять почту`.
   - Store this as `frequency=daily` with `interval=2`.
   - Show confirmation as `Повтор: каждые 2 дня`.
   - Current state: recurrence engine already supports `daily interval=2`;
     parser and prompt examples still need to be updated.

3. Morning daily agenda
   - Every morning at `07:00 Europe/Moscow`, send today's planned reminders.
   - Add config:
     - `DAILY_AGENDA_ENABLED=true`;
     - `DAILY_AGENDA_TIME=07:00`;
     - `DAILY_AGENDA_LIMIT=50`.
   - Use the same formatter as `/today`, but with a short morning title.

## Recommended Next Order

1. Implement recurring interval parsing in the fake parser and Claude prompt.
   This is small and immediately improves text/voice capture.
2. Implement the 07:00 daily agenda job.
   This is also compact and makes the bot useful even when no reminder is due
   yet.
3. Then switch real parsing to Claude CLI and collect real Telegram phrases.
   The confirmation screen is already in place, so testing Claude output is much
   safer now.

## P1 - Near Next

1. Clarification buttons
   - If date/time is missing, show suggested buttons instead of plain text only.
   - Examples: `сегодня`, `завтра`, `через час`.

2. Edit before save
   - In the confirmation screen, add quick actions:
     - change date;
     - change time;
     - change reminder offset;
     - cancel.

3. Better list UX
   - Pagination for `/upcoming`, `/week`, `/month`.
   - Event detail screen.
   - Delete/snooze/done from list items, not only from due notifications.

## P2 - Later

1. VPS deploy hardening
   - Full bootstrap/deploy script for `reminder-bot`.
   - Systemd install instructions.
   - SQLite backup timer.

2. Data management
   - Export/import reminders.
   - Cleanup old completed occurrences and sent jobs.

3. Calendar integrations
   - Optional Google Calendar sync after the Telegram-first workflow is stable.
