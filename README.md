# Reminder Bot

Личный Telegram-бот-напоминалка: принимает текст или голос, понимает событие и
дату, сохраняет напоминание в SQLite и присылает его в нужный момент.

Статус: MVP. Уже есть SQLite-модель, fake/Claude parser layer,
одноразовые и recurring events, Telegram adapter, локальный voice STT и тесты.

## Быстрый старт локально

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env
```

Заполнить `.env`:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_OWNER_ID=...
DAILY_AGENDA_ENABLED=true
DAILY_AGENDA_TIME=07:00
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

## Локальный голос через whisper.cpp

Голосовой контур использует общий `assistant-toolkit`, как и LearnKeeper. На
локальной машине можно не скачивать модель второй раз, а указать пути на уже
подготовленный `whisper.cpp` из LearnKeeper:

```env
STT_PROVIDER=whisper_cpp
STT_WHISPER_CPP_BIN=C:\Users\Vladislav\Desktop\ТГ Бот\learnkeeper-bot\tools\whisper.cpp\bin\Release\whisper-cli.exe
STT_WHISPER_CPP_MODEL=C:\Users\Vladislav\Desktop\ТГ Бот\learnkeeper-bot\tools\whisper.cpp\models\ggml-medium.bin
FFMPEG_BIN=ffmpeg
```

Проверить, что пути доступны:

```powershell
.venv\Scripts\python.exe -m app.cli stt-check
```

Проверить расшифровку конкретного аудио:

```powershell
.venv\Scripts\python.exe -m app.cli stt-preview path\to\voice.oga
```

## VPS и общая модель

На VPS модель не должна лежать внутри каждого бота. Общая схема:

```text
/opt/assistant-shared/whisper.cpp/bin/whisper-cli
/opt/assistant-shared/whisper.cpp/models/ggml-medium.bin
```

Оба бота указывают эти же пути в своих `.env`:

```env
STT_PROVIDER=whisper_cpp
STT_WHISPER_CPP_BIN=/opt/assistant-shared/whisper.cpp/bin/whisper-cli
STT_WHISPER_CPP_MODEL=/opt/assistant-shared/whisper.cpp/models/ggml-medium.bin
```

Для подготовки общего `whisper.cpp` есть скрипт:

```bash
bash scripts/setup-shared-whisper-cpp-linux.sh medium
```

Пример VPS-окружения лежит в `deploy/env.vps.example`, systemd-сервис - в
`deploy/systemd/reminder-bot.service`.

Первичная подготовка VPS:

```bash
BOT_REPO_URL=https://github.com/Nuagrinn/reminder-bot.git \
bash scripts/vps-bootstrap.sh
```

Обычная раскатка новой версии происходит автоматически: push в `main`
запускает GitHub Actions workflow `.github/workflows/deploy.yml`, который
заходит на VPS по SSH и выполняет `scripts/vps-deploy.sh`.

Required GitHub Secrets:

- `VPS_SSH_KEY`;
- `VPS_HOST`;
- `VPS_USER`;
- `VPS_PORT` optional, default `22`;
- `APP_DIR` optional, default `/opt/reminder-bot`;
- `SERVICE_NAME` optional, default `reminder-bot.service`.

Ручная раскатка через SSH, если Actions недоступен:

```bash
bash scripts/vps-deploy.sh
```

Deploy-скрипт подтягивает `main`, обновляет Python-пакет, применяет миграции и
перезапускает `reminder-bot.service`.

## Telegram UX

- Свободный текст от владельца воспринимается как команда на создание
  напоминания.
- Voice скачивается, транскрибируется через `assistant_toolkit.speech` и идет в
  тот же intake flow.
- Перед сохранением бот показывает, как он понял напоминание, и ждет кнопку
  `Сохранить`. Если распознавание/парсинг ошиблись, можно нажать `Отмена`.
- Если не хватает даты или времени, бот показывает быстрые кнопки уточнения,
  например `Сегодня`, `Завтра`, `Через час`, и затем снова показывает экран
  подтверждения.
- Каждый день в `DAILY_AGENDA_TIME` бот присылает список напоминаний на день.
  Это можно включать/выключать кнопкой `🌅 Утро` без правки `.env`.
- При старте новой git-версии бот присылает владельцу сообщение, что версия
  обновлена и перезапущена.
- Команды:
  - `/start`
  - `/today`
  - `/week`
  - `/month`
  - `/upcoming`
  - `/annual`
  - `/morning`
  - `/add текст`

Списки `/today`, `/week`, `/month`, `/upcoming`, `/annual` и утренний план
используют компактный paged-формат:
сообщение содержит читаемый список, а inline-кнопки показывают только номера
строк и пагинацию. По номеру открывается карточка напоминания с действиями
`Готово`, `Перенести` и `Удалить`. Если событий нет, бот явно пишет
`На сегодня событий нет` или похожее пустое состояние.
У списков и служебных карточек есть `Скрыть`: она удаляет только
Telegram-сообщение и не меняет само напоминание.
`Ближайшие` включает незакрытые события начиная с сегодняшнего дня, поэтому
all-day задачи не пропадают вечером из-за внутреннего утреннего якоря.
`Ежегодные` показывает ближайшие экземпляры годовых серий: дни рождения,
годовщины и другие `annual_date`, даже если следующая дата дальше обычного
горизонта materialization.
В списках точное время показывается только для реально заданного времени:
широкие слова вроде `утром`/`вечером` остаются такими же короткими метками, а
дела без времени показываются просто названием под нужной датой.

Due-уведомления приходят с кнопками:

- `Готово`
- `Через 1 час`
- `Завтра`
- `Перенести`
- `Удалить`
- `Скрыть`

Для одноразового напоминания `Удалить` отменяет событие целиком. Для
повторяющегося напоминания бот сначала показывает выбор:

- `Только этот раз`;
- `С этого раза и дальше`;
- `Всю серию`;
- `Отмена`.

`Скрыть` только убирает карточку уведомления из чата и не меняет само
напоминание.

## Повторы

Поддерживаются базовые повторы:

- `каждый вторник обновлять отчет`;
- `12 августа день рождения Маши`;
- `каждый день пить витамины`;
- `день через день делать замер веса`;
- `каждые два дня проверять почту`.

## Временные профили и дефолтные напоминания

Дефолты завязаны не на узкий `event_type`, а на временной профиль события:

- `moment_reminder`: `через 2 часа проверить духовку` -> в момент события;
- `exact_time`: событие в дату/время -> вечером за день, за 1 час, за 15 минут;
- `day_task`: дело на день без времени -> вечером за день, утром в день,
  вечером контроль; если дело создано на сегодня после утра, бот ставит
  rolling-напоминания от текущего момента, например через 1 и 3 часа;
- `deadline`: дедлайн -> за несколько дней, вечером за день, в день дедлайна;
- `recurring_exact_time`: повтор с временем -> за день и короткие offset'ы;
- `recurring_day_task`: повтор без времени -> утром и вечером в день;
- `annual_date`: ежегодная дата -> за неделю, вечером за день, утром в день.

Если пользователь явно сказал `за 2 часа` или похожий offset, явное правило
перебивает дефолтную схему.

Claude parser должен сохранять язык исходной команды в названии. Если русская
фраза неожиданно пришла от модели с английским `title`, Python-нормализация
подставит очищенное русское название из исходного текста.

## Логи уточнений

Если парсер возвращает `needs_clarification`, `ReminderIntakeService` пишет
INFO-лог `Reminder clarification needed` с provider/model, вопросом уточнения,
вариантами и коротким фрагментом исходной фразы.

Выбор clarification-кнопки дополнительно пишет INFO-лог
`Reminder clarification selected` с выбранным вариантом и итоговой фразой,
которая повторно отправляется в parser flow.

## Архитектура

```text
Telegram
  -> adapters.telegram
  -> speech-to-text
  -> reminder_intake parser
  -> notification policy
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
вторник`, `каждые два дня`, `день через день`, `12 августа день рождения ...`.

`PARSER_PROVIDER=claude_cli` вызывает Claude Code через `assistant_toolkit.llm`
и просит строгий JSON по схеме `reminder-parser-v3`. На практике Claude иногда
возвращает компактный JSON (`datetime`, `date`, `time`, `recurrence`), поэтому
бот нормализует такой ответ в полный внутренний формат перед сохранением.

Минимальный набор для Claude:

```env
PARSER_PROVIDER=claude_cli
CLAUDE_BIN=claude
CLAUDE_CODE_OAUTH_TOKEN=...
CLAUDE_MODEL=claude-haiku-4-5-20251001
CLAUDE_MAX_BUDGET_USD=0.12
CLAUDE_SYSTEM_PROMPT_MODE=replace
ALLOW_PAID_API=false
```

## Документация

- [docs/architecture.md](docs/architecture.md)
- [docs/feature-list.md](docs/feature-list.md)
- [docs/worklog/2026-07-24-mvp-skeleton.md](docs/worklog/2026-07-24-mvp-skeleton.md)
