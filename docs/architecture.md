# Reminder Bot Architecture

Date: 2026-07-24

## Goal

Fast personal reminders from Telegram text or voice:

```text
Telegram text/voice
  -> optional STT
  -> reminder parser
  -> event service
  -> SQLite
  -> notification job
  -> Telegram reminder
```

## Current MVP

- SQLite migrations through `assistant_toolkit.db`.
- Text intake through `ReminderIntakeService`.
- Voice intake through `assistant_toolkit.speech`.
- Fake parser for local no-LLM development.
- Claude CLI parser scaffold through `assistant_toolkit.llm.StructuredClaudeRunner`.
- One-off events.
- Basic recurring events:
  - daily with interval;
  - weekly by weekday;
  - monthly by month day;
  - yearly birthdays/anniversaries.
- Materialized occurrences and notification jobs.
- Confirmation flow before saving parsed reminders.
- Daily agenda message at configured morning time.
- Telegram commands:
  - `/start`;
  - `/today`;
  - `/week`;
  - `/month`;
  - `/upcoming`;
  - `/add`.
- Notification actions:
  - done;
  - snooze 1 hour;
  - snooze tomorrow;
  - delete event.

## Package layout

```text
app/
  config.py
  services.py
  cli.py
  telegram_bot.py

  core/
    db.py
    ids.py
    time.py
    migrations/

  features/
    reminder_intake/
      agent.py
      factory.py
      prompt.py
      schema.py
      service.py
    events/
      models.py
      recurrence.py
      service.py

  adapters/
    telegram/
      formatters.py
      keyboards.py
```

## Data model

`events` store the semantic reminder. `event_occurrences` store concrete future
dates. `notification_rules` store relative reminder offsets. `notification_jobs`
store concrete Telegram sends.

Claude/fake parser never writes to SQLite directly. It returns a JSON payload;
Python validates enough shape for MVP, applies defaults and persists events.

## Assistant Toolkit usage

The bot depends on `assistant-toolkit` for infrastructure:

- `assistant_toolkit.speech` for STT providers;
- `assistant_toolkit.llm` for safe Claude CLI JSON calls;
- `assistant_toolkit.db` for SQLite migration/session helper;
- `assistant_toolkit.config` for `.env` parsing helpers;
- `assistant_toolkit.telegram` for HTML formatting helpers.

Domain code stays local to `reminder-bot`.

## Next work

- See [feature-list.md](feature-list.md) for the current prioritized backlog.
