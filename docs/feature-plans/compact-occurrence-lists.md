# Compact Occurrence Lists UX

Date: 2026-07-26
Status: implemented MVP

## Problem

Current list messages duplicate the same information twice:

- text contains a numbered list of reminders;
- inline keyboard repeats every reminder as a full-width button.

This is acceptable for 3-4 events, but becomes noisy for week/month/upcoming
views. Telegram inline buttons are visually large, so `1 event = 1 full-width
button` does not scale.

## MVP Decision

Use one unified compact format for all occurrence list outputs:

- `/today`;
- `/week`;
- `/month`;
- `/upcoming`;
- `/annual`;
- daily agenda.

The message text remains the readable source of truth. Inline buttons become
short numeric actions only.

## Implemented MVP

Implemented on 2026-07-26.

Technical shape:

- Added `OccurrenceListView` in `app/adapters/telegram/occurrence_list_view.py`.
- Added one renderer: `format_occurrence_list_view(view)`.
- Added one keyboard builder: `occurrence_list_keyboard(view)`.
- Added `LIST_PAGE_PREFIX=list_page:` callback for pagination.
- Kept `OCCURRENCE_DETAIL_PREFIX=occ_detail:` for item buttons.
- Telegram commands now only choose the list kind:
  - `today`;
  - `week`;
  - `month`;
  - `upcoming`;
  - `annual`;
  - `agenda`.
- The list callback stores only stable metadata:
  - kind;
  - anchor date as `YYYYMMDD`;
  - page index.
- Occurrence ids are still stored only in visible numeric item buttons.

The current MVP intentionally stays on standard Telegram HTML text plus inline
keyboard buttons. Rich Messages can later become a second renderer fed by the
same `OccurrenceListView`.

Tested cases:

- short date and weekday labels without current year;
- year labels for annual/next-year occurrences;
- day view without duplicate date group;
- all-day reminders without internal `09:00`;
- broad time phrases as `утро`, `день`, `вечер`, `ночь`;
- numeric buttons in rows of five;
- pagination row `[←] [1/2] [→]`;
- page 2 uses visible row numbers `1`, `2`, ... instead of global indexes;
- stale occurrence click shows `Не нашел это напоминание. Обнови список.`;
- all list entry kinds build the same view model.

## Message Format

Header:

```text
Неделя · 26.07-01.08
Всего: 12
```

Date group:

```text
Вс 26.07 · сегодня
1. утро · приделать дощечку на кухне
2. помыть машину
3. забрать свайп-гаррес наполнитель
4. утро · Подключить Spotify
```

Other date labels:

```text
Пн 27.07 · завтра
Вт 28.07
Ср 29.07
```

Year is omitted when the date is in the current year. Year is shown when:

- the occurrence is in another year;
- the view is `/annual`;
- a range crosses a year boundary.

## Button Format

For short pages:

```text
[1] [2] [3] [4]
[Скрыть]
```

For longer pages:

```text
[1] [2] [3] [4] [5]
[6] [7] [8] [9] [10]
[←] [1/3] [→]
[Скрыть]
```

Button numbers map to visible rows in the current message page. Reminder titles
must not be repeated in buttons.

## Pagination

Add pagination for list views once visible rows exceed the page size.

Initial defaults:

- `/today`: page size 10;
- daily agenda: page size 10;
- `/week`: page size 10;
- `/upcoming`: page size 10;
- `/month`: page size 10;
- `/annual`: page size 10.

The callback payload must include enough data to rebuild the same page:

- list kind: `today`, `week`, `month`, `upcoming`, `annual`, `agenda`;
- page index;
- anchor date or current list window;
- stable occurrence ids for visible number buttons when possible.

If an occurrence disappears before click, show a short alert:

```text
Не нашел это напоминание. Обнови список.
```

## Date Labels

Weekday abbreviations:

- `Пн`;
- `Вт`;
- `Ср`;
- `Чт`;
- `Пт`;
- `Сб`;
- `Вс`.

Relative labels:

- today: `сегодня`;
- tomorrow: `завтра`;
- yesterday is not expected in active lists, but can be shown as `вчера` if
  historical lists appear later.

Examples:

```text
Вс 26.07 · сегодня
Пн 27.07 · завтра
11.05.2027 · Вт
```

## Time Labels

Keep current human time label logic:

- exact numeric user time: `09:00`;
- broad source phrase: `утро`, `день`, `вечер`, `ночь`;
- no time: no prefix.

Use shorter nouns in compact lists:

- `утро` instead of `утром`;
- `день` instead of `днем`;
- `вечер` instead of `вечером`;
- `ночь` instead of `ночью`.

Detail cards may keep the more natural phrase:

```text
Когда: 26.07.2026, утром
```

## Unified Formatter Shape

Introduce a small list view model before formatting:

```text
OccurrenceListView
  title
  kind
  range_start
  range_end
  page
  page_size
  total_count
  items
```

The Telegram formatter should not know whether data came from `/today`,
`/week`, `/month`, `/upcoming`, `/annual`, or daily agenda. Each command only
builds the view parameters.

## Implementation Steps

1. Add `OccurrenceListView` / `OccurrenceListPage` helper in Telegram adapter
   or a small feature-level view module.
2. Replace `format_occurrence_list(items, title, empty_text)` with a paged
   formatter that receives view metadata.
3. Replace full-width title buttons with compact numeric rows.
4. Add `LIST_PAGE_PREFIX` callback for previous/next page.
5. Keep existing `OCCURRENCE_DETAIL_PREFIX` for numeric item buttons.
6. Update `/today`, `/week`, `/month`, `/upcoming`, `/annual`, daily agenda to
   use the unified formatter.
7. Add regression tests for:
   - compact date label without current year;
   - weekday label;
   - numeric keyboard buttons;
   - pagination buttons;
   - stale occurrence click;
   - all list entry points using the same formatter.

Status: all MVP steps are done. `format_occurrence_list(items, title,
empty_text)` remains as a compatibility wrapper around the new renderer.

## Open Questions

- Should `/month` default to day-summary first when there are more than 10
  events, or stay as a paged event list for MVP?
- Should number buttons be 5 per row or adapt to page size?
- Should `Скрыть` be last row everywhere, or share a row with pagination when
  there are few buttons?

MVP answer:

- keep paged event list for all views;
- use 5 number buttons per row;
- keep `Скрыть` as the last row.

## Rich Messages Research

Telegram Bot API status:

- Bot API 10.1 added Rich Messages on 2026-06-11.
- Bot API 10.2 added more Rich Message media/list capabilities on 2026-07-14.
- Official API includes `sendRichMessage`, `sendRichMessageDraft`, and
  `editMessageText` support for `rich_message`.

Current Python library status:

- Project dependency: `python-telegram-bot[job-queue]>=21.6,<23`.
- Installed local version: `python-telegram-bot 22.8`.
- PyPI latest checked on 2026-07-26: `22.8`.
- GitHub latest release checked on 2026-07-26: `v22.8`, published
  2026-06-12.
- `telegram.Bot` in `22.8` has no `send_rich_message` method.

Conclusion:

- Rich Messages are available in raw Telegram Bot API.
- They are not yet available through our current high-level
  `python-telegram-bot` interface.

Possible paths:

1. Wait for `python-telegram-bot` support.
   - Lowest maintenance risk.
   - No custom Telegram API wrapper.
   - Not useful for immediate UX work.

2. Add a raw Bot API adapter for `sendRichMessage`.
   - Use the existing Telegram token and HTTP client.
   - Feature flag it, for example `TELEGRAM_RICH_MESSAGES_ENABLED=false`.
   - Fallback to current `send_message` formatter on any API/library issue.
   - Keep tests around payload generation only.

3. Build the compact MVP first, then revisit Rich Messages.
   - Best near-term value.
   - The compact list view model can later render to either HTML text or Rich
     Message blocks.

Recommendation:

- Implement compact paged lists first.
- Design the formatter around a neutral view model so Rich Messages can become
  a second renderer later.
- Do not use raw `sendRichMessage` in production until we test it in a small
  isolated command, for example `/rich_test`.

References:

- Telegram Bot API changelog: https://core.telegram.org/bots/api-changelog
- Telegram Bot API `sendRichMessage`: https://core.telegram.org/bots/api#sendrichmessage
- Telegram Bot API `InputRichMessage`: https://core.telegram.org/bots/api#inputrichmessage
- python-telegram-bot PyPI: https://pypi.org/project/python-telegram-bot/
- python-telegram-bot releases: https://github.com/python-telegram-bot/python-telegram-bot/releases
