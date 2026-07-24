# Worklog: MVP skeleton

Date: 2026-07-24

## What changed

- Created local git repo: `C:\Users\Vladislav\Desktop\reminder-bot`.
- Added Python package skeleton and dependencies.
- Added `.env.example` and README.
- Added SQLite initial migration:
  - `events`;
  - `notification_rules`;
  - `event_occurrences`;
  - `notification_jobs`;
  - `parse_attempts`.
- Implemented event service:
  - create event from parser item;
  - materialize occurrences;
  - create notification jobs;
  - due job selection;
  - mark sent/failed;
  - done;
  - snooze;
  - cancel event.
- Implemented fake parser:
  - `завтра`;
  - `сегодня`;
  - `через N минут/часов/дней`;
  - `каждый вторник`;
  - `12 августа день рождения ...`.
- Added Claude parser scaffold through `assistant_toolkit.llm`.
- Added Telegram adapter:
  - owner-only access;
  - text create flow;
  - voice create flow;
  - `/today`;
  - `/upcoming`;
  - due reminder background job;
  - inline buttons for done/snooze/delete.
- Added CLI:
  - `migrate`;
  - `parse-preview`;
  - `add`;
  - `today`;
  - `upcoming`;
  - `due`.
- Added tests for parser, event service and intake service.

## Validation

- Installed with Python 3.12: `python -m pip install -e .`.
- `assistant-toolkit` resolved from GitHub at commit `d0362c6`.
- Ran `python -m unittest discover -s tests`: 10 tests passed.
- Ran `python -m compileall -q app`: no syntax errors.
- Smoke-tested:
  - `python -m app.cli parse-preview "надо завтра пополнить карту наличкой"`;
  - `python -m app.cli add "надо завтра пополнить карту наличкой"`;
  - `python -m app.cli upcoming`.

## Local Secrets Check

- User added `docs/secret_local_envs.txt` with Telegram settings. The file is
  now ignored by Git and must stay local.
- Generated local `.env` from that file without printing token values.
- `TELEGRAM_OWNER_ID` is now the primary owner variable. `TG_USER_ID` remains a
  fallback for compatibility.
- Telegram token was refreshed and verified through Telegram API:
  `@ReminderForKeller_bot` is reachable.
- Claude CLI is installed, but real Claude parsing needs `CLAUDE_CODE_OAUTH_TOKEN`
  or explicit `ALLOW_PAID_API=true`.

## Shared Local STT Plan

- Voice STT should use local `whisper.cpp`, same as LearnKeeper.
- The local reminder `.env` points to LearnKeeper's existing `whisper-cli.exe`
  and `ggml-medium.bin`, so the model is not duplicated.
- VPS target layout:
  - `/opt/assistant-shared/whisper.cpp/bin/whisper-cli`;
  - `/opt/assistant-shared/whisper.cpp/models/ggml-medium.bin`.
- Added `scripts/setup-shared-whisper-cpp-linux.sh` to prepare that shared
  directory once.
- Added `deploy/env.vps.example` with shared STT paths and
  `deploy/systemd/reminder-bot.service`.
- Added CLI checks:
  - `python -m app.cli stt-check`;
  - `python -m app.cli stt-preview path/to/audio.oga`.
- Local polling was started successfully. HTTP client logs were moved to
  WARNING level so Telegram API URLs with bot tokens are not printed in INFO
  logs.

## Confirmation UX

- Text and voice reminders no longer save immediately.
- Intake now has two explicit phases:
  - `parse(request)` builds structured reminder JSON;
  - `create_from_parse_result(request, parse_result)` saves after confirmation.
- Telegram stores short-lived pending reminders in memory for 30 minutes.
- Added inline buttons:
  - `Сохранить`;
  - `Отмена`.
- Added quick views:
  - `/week`;
  - `/month`;
  - reply keyboard buttons `Неделя` and `Месяц`.

## Backlog Update

- Added `docs/feature-list.md` as the main prioritized feature list.
- Added recurring interval reminders:
  - `день через день надо делать замер веса`;
  - `каждые два дня проверять почту`.
- Added morning daily agenda: send today's reminders every day at 07:00.

## Recurring Intervals And Morning Agenda

- Fake parser now supports:
  - `день через день надо делать замер веса`;
  - `каждые два дня проверять почту`;
  - `каждый день пить витамины`.
- Claude prompt now instructs the same mapping:
  - `daily recurrence`;
  - `interval=2` for `день через день` / `каждые два дня`;
  - `interval=1` for `каждый день`.
- Confirmation formatter displays `Повтор: каждые 2 дня`.
- Added daily agenda config:
  - `DAILY_AGENDA_ENABLED`;
  - `DAILY_AGENDA_TIME`;
  - `DAILY_AGENDA_LIMIT`.
- Telegram JobQueue sends `План на сегодня` every day at the configured time.

## Claude Parser Activation

- Local `.env` now uses Claude CLI parser settings copied from the existing
  LearnKeeper Claude setup, without storing secrets in Git.
- Claude calls are constrained through:
  - `CLAUDE_MODEL=claude-haiku-4-5-20251001`;
  - `CLAUDE_MAX_BUDGET_USD=0.12`;
  - `CLAUDE_SYSTEM_PROMPT_MODE=replace`;
  - `ALLOW_PAID_API=false`.
- `assistant-toolkit` was updated and pushed so the shared Claude runner:
  - passes UTF-8 to the Windows subprocess;
  - supports explicit budget limits;
  - can replace the system prompt;
  - prefers Claude structured output when available.
- Reminder parser prompt moved to `reminder-parser-v2`.
- User prompt is ASCII-safe JSON so Russian text survives Windows CLI transport.
- Added normalization for compact Claude responses like:
  - `datetime/date/time/title`;
  - nested `reminder`;
  - `recurrence`/`repeat`;
  - `reminder_offset_minutes`.
- Verified live Claude parsing:
  - `25 июля в 15:30 оплатить счет` -> one-off datetime reminder;
  - `каждые два дня проверять почту` -> daily recurring reminder with
    `interval=2`.
- Added tests for compact Claude normalization and prompt safety.

## Temporal-Profile Notification Policy

- Replaced domain-type-first notification defaults with temporal profiles:
  - `moment_reminder`;
  - `exact_time`;
  - `day_task`;
  - `deadline`;
  - `time_window`;
  - `recurring_exact_time`;
  - `recurring_day_task`;
  - `annual_date`.
- Prompt/schema moved to `reminder-parser-v3`.
- Claude/fake parsers now include `temporal_profile`.
- Compact Claude normalization derives `temporal_profile` if Claude omits it.
- Added `app/features/notifications/policy.py`.
- Default policies:
  - relative delay -> in the target moment;
  - exact time today -> 1 hour and 15 minutes before;
  - exact future time -> evening before, 1 hour before, 15 minutes before;
  - day task -> evening before, morning in day, evening check;
  - recurring day task -> morning/evening in day, plus evening before for
    weekly/monthly;
  - annual date -> week before, evening before, morning in day.
- `notification_rules` now use both:
  - `kind=relative`;
  - `kind=time_of_day`.
- Confirmation preview now shows the calculated default reminder pattern.
- Verified:
  - fake parse preview for `надо завтра пополнить карту наличкой`;
  - live Claude parse preview for `25 июля в 15:30 оплатить счет`.

## Safe Delete Scopes

- Changed due notification `Удалить` action:
  - one-off event -> delete immediately;
  - recurring event -> show scope menu.
- Added recurring delete scopes:
  - `Только этот раз`;
  - `С этого раза и дальше`;
  - `Всю серию`;
  - `Отмена`.
- Added `EventService.cancel_occurrence`.
- Added `EventService.cancel_series_from_occurrence`.
- `cancel_series_from_occurrence` writes `recurrence.until` as the day before
  the selected occurrence and cancels selected/future materialized occurrences.
- Recurrence engine now respects `until`.
- Materialization skips occurrences that were already cancelled.
- Added tests for:
  - skipping one occurrence;
  - stopping a recurring series from one occurrence;
  - recurrence `until`;
  - Telegram delete-scope keyboards.

## List Detail Actions And Clarification Logging

- `/today`, `/week`, `/month`, `/upcoming` now show numbered inline buttons for
  each occurrence.
- Daily agenda uses the same occurrence buttons when the day has items.
- Added occurrence detail card with:
  - `Готово`;
  - `Удалить`.
- Delete from occurrence detail reuses the existing scoped delete flow.
- Added `EventService.get_occurrence`.
- Clarification parse results now write INFO logs through
  `app.features.reminder_intake.service`.
- Clarification log fields:
  - source kind;
  - parser provider/model/prompt version;
  - question;
  - options;
  - shortened raw text.
- Added tests for:
  - occurrence detail retrieval;
  - occurrence list/detail keyboards;
  - occurrence detail formatter;
  - clarification logging.

## Clarification Buttons

- Added inline clarification keyboard for parser results with
  `status=needs_clarification`.
- Current quick options:
  - parser-provided `clarification.options`;
  - fallback `сегодня`, `завтра`, `через час` for generic time questions.
- Telegram callback stores the option index and resolves the actual option from
  the pending draft, so future parser-generated options do not require new
  callback formats.
- On button click the bot:
  - appends the selected option to the original text;
  - reruns the regular parser flow;
  - updates the same message with either confirmation buttons or another
    clarification prompt.
- Added clarification callback logs:
  - selected option;
  - original phrase;
  - resolved phrase.
- Added tests for clarification keyboard callback data.

## Notes

- GitHub repository `Nuagrinn/reminder-bot` was connected after implementation
  and `main` was pushed.
- `PARSER_PROVIDER=fake` is the local default for safe development. Production
  should use `PARSER_PROVIDER=claude_cli`.
- The first UX is intentionally simple: free text/voice creates reminders, menus
  are only for listing and handling due notifications.
