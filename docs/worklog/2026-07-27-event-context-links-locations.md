# 2026-07-27 - Event Context: Links And Locations

## Что сделали

- Добавили структурное хранение контекста события в `event_contexts`.
- Добавили модель `EventContext` и прикрепление context к `OccurrenceView` и
  `NotificationJobView`.
- Научили парсер и нормализацию сохранять ссылки и явные адреса отдельно от
  title/description.
- Добавили детерминированное извлечение ссылок из raw text, чтобы Claude не был
  единственным источником URL.
- Добавили очистку title от URL и служебных фраз:
  `ссылка в ...`, `адрес: ...`, `место: ...`, `локация: ...`.
- Добавили Telegram-отображение:
  - confirmation;
  - saved result;
  - occurrence detail;
  - due notification;
  - compact list markers `🔗` / `📍`.
- Добавили inline URL/map buttons:
  - `Открыть: Телемост`, `Открыть: Google Meet`, etc.;
  - `Открыть карту` для адресов через Yandex Maps search.

## Какие кейсы покрыты

- Telemost meeting link.
- Google Meet link.
- Google Docs link.
- Zoom link.
- `www.example.com` without scheme.
- Parser label override, например `Бронь`.
- Явные адреса:
  - `адрес: ...`;
  - `по адресу ...`;
  - `адрес встречи: ...`;
  - `адрес доставки: ...`;
  - `место: ...`;
  - `локация: ...`.

## Ограничения MVP

- Адреса пока не геокодятся и не превращаются в точную Telegram venue/location
  точку.
- Если в одном сообщении несколько событий и несколько ссылок, ссылка должна
  прийти в `context` конкретного item от parser. Сервис не прикрепляет все
  ссылки raw text ко всем item, чтобы не загрязнять много-событийные команды.
- Редактирования ссылок/адресов после сохранения пока нет.

## Проверка

- `python -m pytest` недоступен в локальном окружении: нет установленного
  `pytest`.
- Прогон через стандартный runner:
  `.venv\Scripts\python.exe -m unittest discover -s tests`.

На момент записи прогон был зеленым.

## 2026-07-28 UX follow-up

- Заменили малозаметный suffix `· ссылка` / `· адрес` на front marker перед
  названием события.
- В списках строки с контекстом теперь выделяют title жирным:
  `🔗 Собес/скрининг`, `📍 Встреча`.
