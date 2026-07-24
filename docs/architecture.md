# Reminder Bot Architecture

Date: 2026-07-24

## Goal

Fast personal reminders from Telegram text or voice:

```text
Telegram text/voice
  -> optional STT
  -> reminder parser
  -> notification policy
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
- Claude CLI parser through `assistant_toolkit.llm.StructuredClaudeRunner`.
- Claude prompt/schema version `reminder-parser-v3`.
- Compact Claude JSON normalization before persistence.
- Temporal-profile notification policy before persistence.
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
  - delete one-off event;
  - skip one recurring occurrence;
  - stop recurring series from selected occurrence;
  - delete entire recurring series.

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
    notifications/
      policy.py
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
dates. `notification_rules` store relative reminder offsets and time-of-day
rules. `notification_jobs` store concrete Telegram sends.

Claude/fake parser never writes to SQLite directly. It returns a JSON payload;
Python normalizes the shape, applies defaults and persists events.

## Temporal Profiles

Notification defaults are driven by `temporal_profile`, not by a narrow domain
category:

- `moment_reminder`: remind at the target moment itself.
- `exact_time`: concrete date/time, with short pre-event reminders.
- `day_task`: date without exact time, with morning and evening checks.
- `deadline`: due-by phrasing, with earlier warnings.
- `time_window`: start/end window, using the window start for reminders.
- `recurring_exact_time`: recurring item with exact time.
- `recurring_day_task`: recurring item without exact time.
- `annual_date`: yearly date such as birthdays.

Explicit offsets from the user override temporal-profile defaults.

## Deletion Model

One-off deletion cancels the whole event and its pending notification jobs.

Recurring deletion is scoped:

- `Только этот раз`: marks the selected occurrence as `cancelled` and cancels
  its pending jobs. Future occurrences continue.
- `С этого раза и дальше`: sets recurrence `until` to the day before the
  selected occurrence, cancels selected/future materialized occurrences and
  their pending jobs.
- `Всю серию`: marks the event as `cancelled` and cancels all pending jobs.

## Assistant Toolkit usage

The bot depends on `assistant-toolkit` for infrastructure:

- `assistant_toolkit.speech` for STT providers;
- `assistant_toolkit.llm` for Claude CLI JSON calls with budget limits,
  UTF-8 handling and structured-output extraction;
- `assistant_toolkit.db` for SQLite migration/session helper;
- `assistant_toolkit.config` for `.env` parsing helpers;
- `assistant_toolkit.telegram` for HTML formatting helpers.

Domain code stays local to `reminder-bot`.

## Next work

- See [feature-list.md](feature-list.md) for the current prioritized backlog.
