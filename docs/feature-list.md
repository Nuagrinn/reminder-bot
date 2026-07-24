# Reminder Bot Feature List

Date: 2026-07-24

## P0 - Current Focus

1. Real parser quality
   - Switch production flow from `PARSER_PROVIDER=fake` to Claude CLI.
   - Improve prompt/schema examples for exact dates, exact times, relative dates
     and recurring reminders.
   - Add parser tests from real phrases sent in Telegram.

2. Recurring reminders with intervals - done in MVP parser
   - Support phrases like `день через день надо делать замер веса`.
   - Support phrases like `каждые два дня проверять почту`.
   - Store this as `frequency=daily` with `interval=2`.
   - Show confirmation as `Повтор: каждые 2 дня`.
   - Current state: recurrence engine, fake parser, formatter and Claude prompt
     are updated.

3. Morning daily agenda - done
   - Every morning at `07:00 Europe/Moscow`, send today's planned reminders.
   - Config:
     - `DAILY_AGENDA_ENABLED=true`;
     - `DAILY_AGENDA_TIME=07:00`;
     - `DAILY_AGENDA_LIMIT=50`.
   - Uses the same formatter as `/today`, but with a short morning title.

## Recommended Next Order

1. Switch real parsing to Claude CLI and collect real Telegram phrases.
   The confirmation screen is already in place, so testing Claude output is much
   safer now.
2. Add clarification buttons for missing date/time.
3. Add edit controls on the confirmation screen.

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
