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

## Voice Status Reliability

- Checked local logs after a voice test with no visible Telegram reaction.
- Root cause: the update reached `voice_message`, but Telegram timed out while
  sending the first status message `Распознаю голосовое...`.
- Before this fix, that timeout stopped the whole voice flow before download and
  transcription.
- Status messages are now best-effort:
  - if the first status message fails, voice processing continues;
  - if transcription succeeds, the status message is deleted after the normal
    parse/confirmation response is sent;
  - if the final preview cannot be sent, the status message is edited with a
    short failure notice when possible.
- Added INFO logs for voice receive/download/transcription/preview stages.
- Checked another voice case where STT succeeded, but sending the final preview
  as a new Telegram message timed out.
- Voice preview delivery now prefers editing the existing status message into
  the final confirmation/clarification card. If edit fails, it falls back to a
  normal reply.
- The temporary status message is deleted only when the final result was sent as
  a separate reply; if it was edited into the final result, it stays as the
  actionable message with inline buttons.

## Clarification Machine Codes

- Checked a real voice test where Claude returned
  `question='no_time_specified'` and `options=[]`.
- Added clarification normalization for machine-readable reasons such as
  `no_time_specified`, `missing_date`, `datetime_required`.
- These reasons now render as `Когда напомнить?`.
- Empty time/date clarification options now fall back to:
  - `сегодня`;
  - `завтра`;
  - `через час`.
- Normalization is applied in Claude payload handling, Telegram formatting and
  Telegram callback option resolution.
- Added regression tests for compact and native Claude clarification payloads.

## Confirmation And Same-Day Reminder UX

- Checked a real Telegram confirmation for a voice-created reminder:
  `Закинуть наличку на карту`.
- Removed user-facing confirmation line `Заметка: Claude compact output
  normalized by reminder-bot.` because it is internal parser/debug context, not
  useful reminder content.
- Changed same-day `day_task` policy:
  - before the morning reminder time, keep morning/evening checks;
  - after the morning reminder time, use same-day rolling backoff slots from
    the creation moment.
- Added normalization for Claude compact payloads where a date-only phrase like
  `сегодня` is returned as midnight `00:00`; if the user did not say an exact
  time, this is treated as all-day `day_task`, not `exact_time`.
- Current same-day backoff defaults:
  - `через 1 ч.`;
  - `через 3 ч.`.
- Added neutral `Отмена` to occurrence detail cards so opening an item from
  `/today` or another list does not force `Готово` / `Удалить`.
- Added regression tests for:
  - same-day backoff labels;
  - persisted notification jobs at backoff times;
  - hiding internal assumptions from confirmation;
  - detail-card cancel button.
- Checked a real `/today` list where an all-day task was displayed as `09:00`.
- Root cause: all-day tasks are internally materialized at the default day
  anchor time so SQLite occurrences have a concrete datetime.
- Added `all_day` to occurrence and notification view models.
- Telegram lists, detail cards, inline list buttons and due notifications now
  hide that internal anchor:
  - lists/buttons show `день`;
  - detail/due cards show the date without `09:00`.
- CLI `today` / `upcoming` also use a date-only `day` label for all-day
  occurrences.

## Reschedule Actions

- Added `Перенести` to occurrence detail cards and due notification cards.
- One-off reminders can now be moved to a new date/time. When the reminder used
  default notification rules, those rules are rebuilt for the new temporal
  shape. Example: a same-day all-day task moved to tomorrow no longer keeps the
  old same-day backoff slots.
- Recurring reminders now open a reschedule scope menu:
  - `Только этот раз`;
  - `С этого раза и дальше`;
  - `Отмена`.
- Moving one recurring occurrence:
  - marks the original occurrence as `cancelled`;
  - creates a new scheduled occurrence at the target date/time;
  - recreates pending notification jobs for the new occurrence;
  - keeps the recurrence rule unchanged.
- Moving a recurring series from the selected occurrence:
  - updates the event schedule;
  - updates recurrence fields for weekly/monthly/yearly moves;
  - cancels selected/future materialized occurrences;
  - materializes future occurrences from the updated rule.
- Added occurrence-level `all_day_override` so a single all-day recurring
  occurrence can be moved to an exact time without changing the whole series.
- Added quick reschedule options:
  - `+1 час`;
  - `+3 часа`;
  - `Вечером`;
  - `Завтра`;
  - `Через неделю`.
- Added custom reschedule text flow after `Выбрать дату/время`.
  Supported local parser examples:
  - `завтра`;
  - `в 18:30`;
  - `через 2 часа`;
  - `в понедельник`.
- Added migration `002_occurrence_all_day_override.sql`.
- Added tests for:
  - one-off reschedule with default notification rebuild;
  - single recurring occurrence move without old-date duplication;
  - recurring series move with weekday update;
  - reschedule parser;
  - Telegram reschedule keyboards and formatters.

## Morning Toggle, Empty States And Deploy Readiness

- Added persistent `app_settings` table and `AppSettingsService`.
- Added `daily_agenda_enabled` runtime setting:
  - defaults to `DAILY_AGENDA_ENABLED` from `.env` until manually changed;
  - can be toggled without editing `.env` or restarting the bot.
- Added Telegram entry points for morning agenda settings:
  - reply keyboard button `🌅 Утро`;
  - `/morning`;
  - inline `Включить` / `Выключить`.
- Daily agenda JobQueue task is now always registered; it checks the runtime
  flag before sending.
- Empty states are clearer:
  - `/today`: `На сегодня событий нет`;
  - morning agenda: `Доброе утро. На сегодня событий нет`;
  - week/month/upcoming use the same `событий нет` wording.
- Added version activation notification, mirroring LearnKeeper:
  - reads current git commit;
  - compares it with `app_settings.app_version_last_notified`;
  - sends `Reminder Bot обновлен и перезапущен` once per new commit;
  - skips duplicate messages on plain restarts of the same version.
- Added VPS deploy kit:
  - `scripts/vps-bootstrap.sh`;
  - `scripts/vps-deploy.sh`;
  - hardened `deploy/systemd/reminder-bot.service`.
- Current VPS readiness status:
  - ready for manual VPS bootstrap/deploy;
  - still worth adding a SQLite backup timer before long-term unattended use;
  - optional later improvement: GitHub Actions SSH deploy workflow.
- Added tests for:
  - app settings persistence;
  - morning agenda toggle keyboard/texts;
  - empty agenda state;
  - version update notification text.

## Due Notification Hide Action

- Added `Скрыть` button to due notification cards.
- `Скрыть` deletes the Telegram card only:
  - does not mark the occurrence done;
  - does not delete the event;
  - does not reschedule notification jobs.
- Added callback logging for successful hide and Telegram delete/edit failures.
- Added regression tests for the keyboard callback data and handler behavior.

## First VPS Deployment

- Deployed reminder-bot to VPS `213.239.157.243`.
- Runtime layout:
  - app: `/opt/reminder-bot`;
  - service: `reminder-bot.service`;
  - database: `/opt/reminder-bot/data/reminder.sqlite3`;
  - voice files: `/opt/reminder-bot/data/voice`;
  - shared STT binary:
    `/opt/assistant-shared/whisper.cpp/bin/whisper-cli`;
  - shared STT model:
    `/opt/assistant-shared/whisper.cpp/models/ggml-medium.bin`.
- Installed `.env` on VPS from local secrets with VPS-safe paths.
- Applied migrations:
  - `001_initial`;
  - `002_occurrence_all_day_override`;
  - `003_app_settings`.
- Verified on VPS:
  - unit tests: 85 passed;
  - compile check: OK;
  - `stt-check`: OK;
  - Claude parser smoke test: OK.
- Started `reminder-bot.service`; service is active and sends the version
  activation notification.
- Stopped local Windows polling process before starting VPS polling to avoid
  Telegram token conflicts.
- Fixed `scripts/vps-bootstrap.sh` so shared whisper setup runs from the app
  user's home directory instead of inheriting `/root`.

## Upcoming Today All-Day Fix

- Fixed `/upcoming` / `Ближайшие` selection window.
- Before the fix, `upcoming()` started from the current minute. All-day tasks
  are stored with an internal `09:00` anchor, so an unfinished task for today
  disappeared from `Ближайшие` in the evening even though it still appeared in
  `/today`.
- `upcoming()` now starts from the beginning of the current day and still keeps
  the normal future horizon.
- Added a regression test for a same-day all-day task created after the
  internal morning anchor.

## Annual View And Title Language Guard

- User-facing issue observed in Telegram:
  - Russian voice/text command `Сегодня вечером надо заказать креатин и
    протеин` was saved with English title `Order creatine and protein`.
- Prompt fix:
  - Claude now gets an explicit rule to preserve source language/script;
  - Russian/Cyrillic raw text must produce Russian/Cyrillic title;
  - titles must not be translated to English.
- Normalization safety net:
  - if a single Russian command comes back with an English-only title, Python
    falls back to a cleaned title from the raw command;
  - title cleanup now removes helper/time words in a more robust order, so
    `сегодня вечером надо заказать креатин` becomes `Заказать креатин`.
- Added organic annual events view:
  - command `/annual`;
  - reply keyboard button `🎂 Ежегодные`;
  - shows the next occurrence of yearly series, birthdays and anniversaries;
  - materializes the next annual occurrence when it is beyond the default
    180-day materialization horizon.
- Added tests for:
  - Claude prompt language-preservation rule;
  - compact and native Claude title fallback;
  - annual occurrence materialization beyond the normal horizon;
  - reply keyboard annual button.

## Human Time Labels In Lists

- User-facing issue observed in Telegram:
  - all-day rows rendered as `день`, which looked technical and noisy;
  - broad time words like `утром` could appear as the internal/default
    materialization time `09:00`, which looked like an exact user-set time.
- Updated list/button labels:
  - exact numeric times still render as `09:00`;
  - broad source phrases render as short labels: `утром`, `днем`, `вечером`,
    `ночью`;
  - date-only all-day rows omit the time prefix entirely and show just the
    title under the date group.
- Added `source_text` to occurrence/job views so Telegram formatting can tell
  broad time wording from an explicit clock time without changing the database
  schema.
- Parser and persistence guards:
  - Claude prompt now says not to convert broad day parts into fake clock
    times unless the user gave a numeric time;
  - normalization drops inferred clock times when raw text has no explicit
    clock time;
  - event persistence corrects `all_day=false` with missing `time/start_at` to
    a date-only all-day event.
- Existing VPS data cleanup:
  - events with `all_day=0` and no concrete `time/start_at` should be marked
    all-day, then rematerialized.

## Generic Hide Button For Service Cards

- User-facing issue observed in Telegram:
  - occurrence lists had numbered inline buttons, but no quick way to remove
    the list card from chat after viewing it.
- Added generic `hide_message` callback:
  - deletes only the Telegram message;
  - does not mark occurrences done;
  - does not delete events;
  - does not reschedule jobs.
- Added `Скрыть` to non-due service cards:
  - parse confirmation;
  - clarification choices;
  - occurrence lists;
  - occurrence detail;
  - delete scope menu;
  - reschedule scope/options;
  - morning agenda settings.
- Due notification cards keep their job-specific hide action, so logs still
  record the notification job id.
- If a hidden card belongs to an active reschedule text flow, the temporary
  pending reschedule state is cleared to avoid applying the next free-text
  message unexpectedly.
- Added tests for keyboard callback data and generic hide callback deletion.

## Compact Occurrence Lists Feature Plan

- Created separate feature plan:
  `docs/feature-plans/compact-occurrence-lists.md`.
- MVP decision:
  - one unified compact list renderer for `/today`, `/week`, `/month`,
    `/upcoming`, `/annual` and daily agenda;
  - readable content stays in message text;
  - inline buttons become short numeric actions like `[1] [2] [3]`;
  - add compact dates such as `Вс 26.07 · сегодня`;
  - add pagination once a list exceeds the visible page size.
- Rich Messages research:
  - Telegram Bot API already has Rich Messages (`sendRichMessage`);
  - installed and latest `python-telegram-bot` is `22.8`;
  - `telegram.Bot` in `22.8` has no `send_rich_message` method;
  - recommendation is to build the compact list MVP first around a neutral view
    model, then optionally add a raw Bot API Rich Messages renderer behind a
    feature flag.

## Compact Occurrence Lists MVP

- Implemented unified compact list rendering for:
  - `/today`;
  - `/week`;
  - `/month`;
  - `/upcoming`;
  - `/annual`;
  - morning daily agenda.
- Added `OccurrenceListView` as a Telegram adapter view model.
- Message text is now the source of truth:
  - compact header, for example `Неделя · 26.07-01.08`;
  - short date groups, for example `Вс 26.07 · сегодня`;
  - page range when needed, for example `Показано: 11-20 из 24`.
- Inline list buttons are numeric only:
  - up to five numbers per row;
  - `←`, `1/2`, `→` pagination row when a list has more than 10 visible items;
  - `Скрыть` remains the last row.
- Button numbers map to rows visible on the current page, so page 2 starts
  from button/text row `1`, not `11`.
- Updated human time labels for compact lists:
  - broad phrases show `утро`, `день`, `вечер`, `ночь`;
  - exact user times still show `HH:MM`;
  - date-only all-day rows still have no noisy time prefix.
- Added `list_page:` callback:
  - payload contains kind, anchor date and page index;
  - the bot rebuilds the current list window instead of storing page data in
    memory;
  - stale/deleted occurrence clicks show
    `Не нашел это напоминание. Обнови список.`.
- Added regression tests for formatter, keyboard pagination, stale occurrence
  click and all list entry kinds using the shared view builder.

## Notes

- GitHub repository `Nuagrinn/reminder-bot` was connected after implementation
  and `main` was pushed.
- `PARSER_PROVIDER=fake` is the local default for safe development. Production
  should use `PARSER_PROVIDER=claude_cli`.
- The first UX is intentionally simple: free text/voice creates reminders, menus
  are only for listing and handling due notifications.
