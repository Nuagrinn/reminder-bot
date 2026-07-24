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

## Notes

- GitHub repository `Nuagrinn/reminder-bot` was connected after implementation
  and `main` was pushed.
- `PARSER_PROVIDER=fake` is the local default for safe development. Production
  should use `PARSER_PROVIDER=claude_cli`.
- The first UX is intentionally simple: free text/voice creates reminders, menus
  are only for listing and handling due notifications.
