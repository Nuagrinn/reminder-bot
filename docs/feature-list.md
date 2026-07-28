# Reminder Bot Feature List

Date: 2026-07-24

## P0 - Current Focus

1. Real parser quality - initial Claude path done
   - Local `.env` can run `PARSER_PROVIDER=claude_cli`.
   - Prompt/schema version is `reminder-parser-v4`.
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
   - Runtime Telegram toggle:
     - reply keyboard button `🌅 Утро`;
     - command `/morning`;
     - inline `Включить` / `Выключить`.
   - If there are no events today, the morning message still says:
     `На сегодня событий нет`.

5. Safe deletion scopes - done
   - One-off reminders delete directly.
   - Recurring reminders open a scope menu:
     - only this occurrence;
     - this occurrence and future occurrences;
     - whole series.
   - `recurrence.until` is respected by the recurrence engine.

6. List detail/actions - done
   - `/today`, `/week`, `/month`, `/upcoming`, `/annual` render compact paged
     lists with numeric action buttons.
   - Daily agenda also renders action buttons when there are items.
   - List buttons show only row numbers; reminder text stays in the message.
   - Pages use 10 visible rows and compact pagination buttons.
   - Detail card supports `Готово`, `Перенести`, `Удалить` and neutral
     `Отмена`.
   - Service cards and menus support `Скрыть`, which removes only the Telegram
     message.
   - Delete from detail reuses recurring scope menu.
   - All-day tasks are shown without a noisy time prefix instead of the
     internal `09:00` materialization anchor.
   - Broad source phrases like `утром` / `вечером` are shown as human labels,
     while exact user-provided clock times remain `HH:MM`.
   - List rows use a compact table-like left cell:
     number + time/part-of-day, then the title as normal text.
   - `Ежегодные` is a semantic annual-series view, not a long month range:
     it shows the next occurrence of yearly events and materializes it when it
     is beyond the normal 180-day horizon.
   - Annual lists are grouped by month, for example `Май 2027`, with rows like
     `11 Вт День рождения`.
   - Current and upcoming lists include unfinished overdue tasks once their
     next pending reminder falls into the requested period. This keeps a task
     visible after pressing notification snooze like `Завтра`, even though the
     original event date stays in the past.

7. Reschedule reminders - done
   - One-off reminders can be moved from the detail card.
   - Recurring reminders can be moved as:
     - only this occurrence;
     - this occurrence and future occurrences.
   - Quick options:
     - `+1 час`;
     - `+3 часа`;
     - `Вечером`;
     - `Завтра`;
     - `Через неделю`.
   - Custom date/time text after `Выбрать дату/время` supports phrases like:
     - `завтра`;
     - `в 18:30`;
     - `через 2 часа`;
     - `в понедельник`.
   - Moving a one-off reminder rebuilds default notification timings, so a
     same-day backoff task moved to tomorrow gets tomorrow-style reminders.

8. Due notification hide action - done
   - Due notification cards include `Скрыть`.
   - The action deletes the Telegram notification card only.
   - It does not mark the reminder done, delete it, or reschedule anything.
   - Due notification quick actions are explicit:
     - `Напомнить +1ч` postpones only the notification;
     - `На завтра` reschedules the reminder occurrence to tomorrow.

9. Clarification diagnostics - done
   - `needs_clarification` parse results are logged at INFO level.
   - Logs include provider/model, prompt version, question, options and short
     raw text.

10. Clarification buttons - done
   - If date/time is missing, Telegram shows inline quick options.
   - Current options come from parser `clarification.options`; for generic time
     questions the fallback is `сегодня`, `завтра`, `через час`.
   - Button click reuses the pending draft, appends the selected option to the
     original phrase and reruns the parser.
   - If the resolved parse is OK, the bot shows the normal confirmation screen.
   - Clarification selections are logged at INFO level.
   - Clarification button callbacks are acknowledged immediately before the
     slower parser/Claude roundtrip, so Telegram does not expire the clicked
     button while the bot is thinking.

11. Concurrent Telegram processing - done
   - `TELEGRAM_CONCURRENT_UPDATES=4` lets Telegram process independent updates
     in parallel.
   - Heavy operations are still bounded:
     - `STT_MAX_CONCURRENT=1`;
     - `PARSER_MAX_CONCURRENT=2`.
   - This keeps the bot responsive when several voice messages arrive in a row
     without launching multiple heavy whisper jobs at once.

12. Version activation notification - done
   - On startup, the bot checks the current git commit.
   - If the commit differs from `app_version_last_notified`, it sends the owner
     a short `Reminder Bot обновлен и перезапущен` message.
   - The last notified commit is stored in `app_settings`, so normal restarts of
     the same version do not spam.

13. VPS deploy kit - deployed
   - `deploy/env.vps.example`;
   - hardened `deploy/systemd/reminder-bot.service`;
   - `scripts/setup-shared-whisper-cpp-linux.sh`;
   - `scripts/vps-bootstrap.sh`;
   - `scripts/vps-deploy.sh`.
   - GitHub Actions auto-deploy:
     `.github/workflows/deploy.yml`;
   - push в `main` должен автоматически запускать SSH-deploy на VPS.
   - First VPS deployment completed on `213.239.157.243`:
     - app path: `/opt/reminder-bot`;
     - service: `reminder-bot.service`;
     - shared STT model:
       `/opt/assistant-shared/whisper.cpp/models/ggml-medium.bin`.

14. Parser title language guard - done
   - Claude prompt now explicitly says to preserve raw_text language/script.
   - If a Russian command returns an English-only `title`, normalization falls
     back to a cleaned Russian title from the original phrase.
   - The title cleaner also strips date/time helper words like `сегодня
     вечером` before saving.

15. Shopping list reminders - MVP done
   - Shopping reminders reuse normal event scheduling and notification jobs.
   - Shopping items are stored in separate `shopping_lists` and
     `shopping_items` tables, not in event description text.
   - Parser returns optional `content.kind=shopping_list` while keeping
     `event_type=task`.
   - Phrases like `купить молоко, хлеб, яйца` create a same-day shopping
     reminder by default.
   - Explicit time still works, for example `завтра в 14:00 купить молоко,
     хлеб`.
   - Telegram supports opening the list, item actions, soft delete and
     voice/text add mode from the `Добавить` button.

## Feature Plans

- [Compact Occurrence Lists UX](feature-plans/compact-occurrence-lists.md):
  unified MVP for `/today`, `/week`, `/month`, `/upcoming`, `/annual` and daily
  agenda; includes Rich Messages research.
- [Event Context: Links And Locations](feature-plans/event-context-links-locations.md):
  MVP implemented for preserving URLs, meeting links and raw addresses with
  detail/due buttons.
- [Shopping List Reminders](feature-plans/shopping-list-reminders.md):
  MVP implemented for nested editable shopping lists inside scheduled reminders.

## Recommended Next Order

1. Run the bot in Telegram with Claude enabled and collect real phrases that
   parse poorly.
2. Add edit controls on the confirmation screen for reminder pattern:
   default / only in moment / custom offset.
3. Improve clarification UX after real usage:
   - add custom date/time entry from button;
   - optionally add richer option generation from Claude.
4. Revisit event context after real usage:
   - add link/address edit controls;
   - add optional geocoding for precise venue/location cards.
5. Improve shopping lists after real usage:
   - natural-language delete/replace commands;
   - several active lists selection;
   - quantities and product normalization.
6. Revisit Rich Messages as a second renderer once the Python Telegram library
   supports them or after a small raw Bot API experiment.

## P1 - Near Next

1. Edit before save
   - In the confirmation screen, add quick actions:
     - change date;
     - change time;
     - change reminder offset;
     - cancel.

2. Better list UX
   - Compact paged list MVP is implemented:
     [Compact Occurrence Lists UX](feature-plans/compact-occurrence-lists.md).
   - Optional back button from detail to the previous list.
   - Optional snooze from list detail when there is a pending job.

3. Clarification improvements
   - Button for custom date/time text.
   - Button for custom reminder offset when parser understands the event but
     uncertainty is only in notification timing.

## P2 - Later

1. VPS deploy hardening
   - Add SQLite backup timer.
   - Add deploy result notification if GitHub Actions fails before reaching
     the bot.

2. Data management
   - Export/import reminders.
   - Cleanup old completed occurrences and sent jobs.

3. Calendar integrations
   - Optional Google Calendar sync after the Telegram-first workflow is stable.
