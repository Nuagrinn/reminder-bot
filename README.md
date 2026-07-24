# Reminder Bot

Личный Telegram-бот-напоминалка: принимает текст или голос, понимает событие и
дату, сохраняет напоминание в SQLite и присылает его в нужный момент.

Статус: MVP skeleton. Уже есть SQLite-модель, fake/Claude parser layer,
одноразовые и базовые recurring events, Telegram adapter и тесты.

## Быстрый старт локально

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env
```

Заполнить `.env`:

```env
TELEGRAM_BOT_TOKEN=...
TG_USER_ID=...
PARSER_PROVIDER=fake
STT_PROVIDER=disabled
```

Применить миграции:

```powershell
.venv\Scripts\python.exe -m app.cli migrate
```

Проверить парсинг без Telegram:

```powershell
.venv\Scripts\python.exe -m app.cli parse-preview "надо завтра пополнить карту наличкой"
```

Добавить напоминание через CLI:

```powershell
.venv\Scripts\python.exe -m app.cli add "надо завтра пополнить карту наличкой"
.venv\Scripts\python.exe -m app.cli upcoming
```

Запустить Telegram polling:

```powershell
.venv\Scripts\python.exe -m app.telegram_bot
```

## Telegram UX

- Свободный текст от владельца воспринимается как команда на создание
  напоминания.
- Voice скачивается, транскрибируется через `assistant_toolkit.speech` и идет в
  тот же intake flow.
- Команды:
  - `/start`
  - `/today`
  - `/upcoming`
  - `/add текст`

Due-уведомления приходят с кнопками:

- `Готово`
- `Через 1 час`
- `Завтра`
- `Удалить`

## Архитектура

```text
Telegram
  -> adapters.telegram
  -> speech-to-text
  -> reminder_intake parser
  -> events service
  -> notifications service
  -> SQLite
```

Общий инфраструктурный код берется из
[`assistant-toolkit`](https://github.com/Nuagrinn/assistant-toolkit):

- STT providers;
- Claude CLI structured JSON runner;
- SQLite helper;
- config helpers;
- Telegram formatting helpers.

## Parser providers

`PARSER_PROVIDER=fake` нужен для локальной разработки без LLM. Он понимает
несколько типовых фраз: `завтра`, `сегодня`, `через N минут/часов`, `каждый
вторник`, `12 августа день рождения ...`.

`PARSER_PROVIDER=claude_cli` вызывает Claude Code через `assistant_toolkit.llm`
и ожидает строгий JSON.

## Документация

- [docs/architecture.md](docs/architecture.md)
- [docs/worklog/2026-07-24-mvp-skeleton.md](docs/worklog/2026-07-24-mvp-skeleton.md)

