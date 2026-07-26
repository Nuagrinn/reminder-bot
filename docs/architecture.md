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
- Clarification flow for missing date/time before confirmation.
- Daily agenda message at configured morning time, with a Telegram runtime
  on/off switch.
- Version update notification after a new git commit is activated.
- Telegram commands:
  - `/start`;
  - `/today`;
  - `/week`;
  - `/month`;
  - `/upcoming`;
  - `/annual`;
  - `/morning`;
  - `/add`.
- Notification actions:
  - done;
  - open occurrence detail from `/today`, `/week`, `/month`, `/upcoming`,
    `/annual` and daily agenda;
  - reschedule one-off reminders;
  - reschedule one recurring occurrence;
  - reschedule a recurring series from the selected occurrence;
  - snooze 1 hour;
  - snooze tomorrow;
  - hide a sent due notification card without changing the reminder;
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

`app_settings` stores small runtime flags such as:

- `daily_agenda_enabled`;
- `app_version_last_notified`.

Claude/fake parser never writes to SQLite directly. It returns a JSON payload;
Python normalizes the shape, applies defaults and persists events.

## Temporal Profiles

Notification defaults are driven by `temporal_profile`, not by a narrow domain
category:

- `moment_reminder`: remind at the target moment itself.
- `exact_time`: concrete date/time, with short pre-event reminders.
- `day_task`: date without exact time, with morning and evening checks. If the
  task is created for today after the morning check is already past, reminders
  use rolling same-day backoff slots, currently +1 hour and +3 hours.
- `deadline`: due-by phrasing, with earlier warnings.
- `time_window`: start/end window, using the window start for reminders.
- `recurring_exact_time`: recurring item with exact time.
- `recurring_day_task`: recurring item without exact time.
- `annual_date`: yearly date such as birthdays.

Explicit offsets from the user override temporal-profile defaults.

## List Actions

Occurrence lists render numbered rows and matching inline buttons. Selecting a
row opens an occurrence detail card with:

- `Готово`;
- `Перенести`;
- `Удалить`;
- `Отмена`.

The delete action reuses the scoped deletion model for recurring reminders.

All-day tasks may be internally materialized at the default day anchor time
(`09:00`) so recurrence and notification jobs have a concrete datetime. Telegram
lists, detail cards and due notifications hide that internal anchor and display
`день` or just the date instead.

Empty list states are explicit and short, for example `На сегодня событий нет`.

## Annual Events View

`/annual` and the reply button `🎂 Ежегодные` are a semantic view over yearly
series, not a wider date range. The service selects active events with
`frequency=yearly` or birthday/anniversary metadata, computes the next annual
target and ensures that concrete occurrence exists.

This matters because the normal materialization horizon is intentionally short
(`materialize_days`, currently 180 days). A birthday next summer should still be
visible in `Ежегодные` even if it is too far away for `/month` or `/upcoming`.
The created occurrence uses the same notification rules as the event, so annual
defaults (`за неделю`, `вечером за день`, `утром в день`) stay consistent.

## Parser Normalization Guard

Claude is instructed to preserve the source language and script in `title` and
`description`. The Python normalization layer also guards the common failure
case: if the original phrase contains Cyrillic but a single parsed item returns
an English-only title, the bot replaces it with a cleaned title from the raw
phrase. Time/helper words such as `сегодня вечером надо` are stripped before the
title is saved.

## Due Notification Actions

Due notification cards are action-oriented:

- `Готово`: completes the occurrence.
- `Через 1 час`: snoozes this notification job for one hour.
- `Завтра`: snoozes this notification job for one day.
- `Перенести`: opens the reschedule flow for the occurrence.
- `Удалить`: opens immediate/scoped deletion depending on recurrence.
- `Скрыть`: deletes only the Telegram card. The occurrence and stored reminder
  state stay unchanged.

## Morning Agenda

The morning agenda job is always registered at startup, but `send_daily_agenda`
checks `app_settings.daily_agenda_enabled` before sending. If no runtime value is
stored yet, the default comes from `DAILY_AGENDA_ENABLED`.

Telegram exposes the setting through:

- reply keyboard button `🌅 Утро`;
- command `/morning`;
- inline toggle `Включить` / `Выключить`.

When enabled, the agenda is sent every morning even when today's list is empty,
so the owner gets a clear `На сегодня событий нет` message.

## Version Notification

On startup, JobQueue runs a one-shot `version-update-notification` job. It reads
the current git commit, compares it with `app_settings.app_version_last_notified`
and sends the owner `Reminder Bot обновлен и перезапущен` only when the commit
changed. This mirrors the LearnKeeper behavior and avoids duplicate messages on
plain restarts of the same version.

## Reschedule Model

One-off reminders are moved by updating the event schedule, moving its only
occurrence and rebuilding default notification rules when the user did not set
explicit offsets.

Recurring reminders are scoped:

- `Только этот раз`: the selected occurrence is marked `cancelled`, a new
  scheduled occurrence is created at the target date/time and pending jobs are
  recreated for the new occurrence. The cancelled original occurrence prevents
  future materialization from adding the old date back.
- `С этого раза и дальше`: the event schedule and recurrence rule are updated,
  selected/future materialized occurrences are cancelled, the target occurrence
  is created and future occurrences are materialized from the updated rule.

For recurrence rules, moving the series to another weekday/month day/yearly date
updates the corresponding recurrence fields (`weekdays`, `month_days`,
`months`). A concrete occurrence can override the event-level all-day flag, so a
single all-day recurring item can be moved to an exact time without changing the
whole series.

Telegram reschedule UX:

- detail/due card button `Перенести`;
- recurring scope menu;
- quick options: `+1 час`, `+3 часа`, `Вечером`, `Завтра`, `Через неделю`;
- custom date/time entry after `Выбрать дату/время`.

## Clarification Flow

When parser status is `needs_clarification`, Telegram keeps the same short-lived
pending reminder draft and renders inline option buttons from parser
`clarification.options`.

Current default quick options for time questions:

- `сегодня`;
- `завтра`;
- `через час`.

Button callbacks store only the option index, not the Russian text itself. On
click the bot resolves the option from the pending draft, appends it to the
original phrase and sends the resolved phrase through the normal parser and
confirmation flow again.

If parsing succeeds, the user sees the regular `Сохранить` / `Отмена`
confirmation screen. If the result still needs clarification, the bot updates
the same message with another clarification prompt.

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

## Diagnostics

Clarification results are logged at INFO level by
`app.features.reminder_intake.service` with:

- source kind;
- parser provider/model/prompt version;
- clarification question;
- suggested options;
- shortened raw text.

Telegram clarification callbacks also log selected option, original phrase and
resolved phrase in `app.telegram_bot`.

## Next work

- See [feature-list.md](feature-list.md) for the current prioritized backlog.
