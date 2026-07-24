# Reminder Bot Feature List

Date: 2026-07-24

## P0 - Current Focus

1. Real parser quality - initial Claude path done
   - Local `.env` can run `PARSER_PROVIDER=claude_cli`.
   - Prompt/schema version is `reminder-parser-v3`.
   - Exact date/time parsing is verified through Claude CLI.
   - Recurring interval parsing is verified through Claude CLI.
   - Compact Claude output is normalized into the internal reminder schema.
   - Remaining work: collect parser tests from real phrases sent in Telegram.

2. Temporal-profile notification policy - done
   - Default reminders are based on time shape, not narrow event categories.
   - Profiles:
     - `moment_reminder`;
     - `exact_time`;
     - `day_task`;
     - `deadline`;
     - `time_window`;
     - `recurring_exact_time`;
     - `recurring_day_task`;
     - `annual_date`.
   - Explicit user offsets override defaults.
   - Confirmation preview shows the planned reminder pattern.
   - Same-day `day_task` reminders created after the morning window use rolling
     backoff slots, currently `через 1 ч.` and `через 3 ч.`.

3. Recurring reminders with intervals - done in MVP parser
   - Support phrases like `день через день надо делать замер веса`.
   - Support phrases like `каждые два дня проверять почту`.
   - Store this as `frequency=daily` with `interval=2`.
   - Show confirmation as `Повтор: каждые 2 дня`.
   - Current state: recurrence engine, fake parser, formatter and Claude prompt
     are updated.

4. Morning daily agenda - done
   - Every morning at `07:00 Europe/Moscow`, send today's planned reminders.
   - Config:
     - `DAILY_AGENDA_ENABLED=true`;
     - `DAILY_AGENDA_TIME=07:00`;
     - `DAILY_AGENDA_LIMIT=50`.
   - Uses the same formatter as `/today`, but with a short morning title.

5. Safe deletion scopes - done
   - One-off reminders delete directly.
   - Recurring reminders open a scope menu:
     - only this occurrence;
     - this occurrence and future occurrences;
     - whole series.
   - `recurrence.until` is respected by the recurrence engine.

6. List detail/actions - done
   - `/today`, `/week`, `/month`, `/upcoming` render numbered action buttons.
   - Daily agenda also renders action buttons when there are items.
   - Detail card supports `Готово`, `Удалить` and neutral `Отмена`.
   - Delete from detail reuses recurring scope menu.
   - All-day tasks are shown as `день` / date-only instead of the internal
     `09:00` materialization anchor.

7. Clarification diagnostics - done
   - `needs_clarification` parse results are logged at INFO level.
   - Logs include provider/model, prompt version, question, options and short
     raw text.

8. Clarification buttons - done
   - If date/time is missing, Telegram shows inline quick options.
   - Current options come from parser `clarification.options`; for generic time
     questions the fallback is `сегодня`, `завтра`, `через час`.
   - Button click reuses the pending draft, appends the selected option to the
     original phrase and reruns the parser.
   - If the resolved parse is OK, the bot shows the normal confirmation screen.
   - Clarification selections are logged at INFO level.

## Recommended Next Order

1. Run the bot in Telegram with Claude enabled and collect real phrases that
   parse poorly.
2. Add edit controls on the confirmation screen for reminder pattern:
   default / only in moment / custom offset.
3. Add pagination for long `/upcoming`, `/week`, `/month` lists.
4. Improve clarification UX after real usage:
   - add custom date/time entry from button;
   - optionally add richer option generation from Claude.

## P1 - Near Next

1. Edit before save
   - In the confirmation screen, add quick actions:
     - change date;
     - change time;
     - change reminder offset;
     - cancel.

2. Better list UX
   - Pagination for `/upcoming`, `/week`, `/month`.
   - Optional back button from detail to the previous list.
   - Optional snooze from list detail when there is a pending job.

3. Clarification improvements
   - Button for custom date/time text.
   - Button for custom reminder offset when parser understands the event but
     uncertainty is only in notification timing.

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
