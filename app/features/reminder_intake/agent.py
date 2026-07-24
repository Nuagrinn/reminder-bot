from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from assistant_toolkit.llm import StructuredClaudeRunner

from app.features.reminder_intake.schema import PROMPT_VERSION, REMINDER_JSON_SCHEMA


WEEKDAYS_RU = {
    "понедельник": "MO",
    "понедельникам": "MO",
    "вторник": "TU",
    "вторникам": "TU",
    "среду": "WE",
    "средам": "WE",
    "четверг": "TH",
    "четвергам": "TH",
    "пятницу": "FR",
    "пятницам": "FR",
    "субботу": "SA",
    "субботам": "SA",
    "воскресенье": "SU",
    "воскресеньям": "SU",
}

MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


@dataclass(frozen=True)
class ReminderParseRequest:
    raw_text: str
    source_kind: str
    now: datetime
    timezone: str
    default_day_reminder_time: str
    default_timed_event_offset_minutes: int
    default_birthday_offsets_minutes: list[int]


@dataclass(frozen=True)
class ReminderParseResult:
    payload: dict[str, Any]
    provider: str
    model: str
    prompt_version: str = PROMPT_VERSION
    stdout: str = ""


class ReminderParserError(RuntimeError):
    pass


class ReminderParserAgent(Protocol):
    provider: str
    model: str
    prompt_version: str

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        ...


class FakeReminderParserAgent:
    provider = "fake"
    model = "fake"
    prompt_version = "fake-reminder-parser-v1"

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        payload = fake_parse_payload(request)
        return ReminderParseResult(
            payload=payload,
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
        )


class ClaudeCliReminderParserAgent:
    provider = "claude_cli"
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        *,
        claude_bin: str,
        oauth_token: str,
        model: str,
        timeout_seconds: int,
        allow_paid_api: bool,
    ):
        self.model = model
        self.runner = StructuredClaudeRunner(
            claude_bin=claude_bin,
            oauth_token=oauth_token,
            model=model,
            timeout_seconds=timeout_seconds,
            allow_paid_api=allow_paid_api,
        )

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        from app.features.reminder_intake.prompt import build_system_prompt, build_user_prompt

        try:
            result = self.runner.run(
                system_prompt=build_system_prompt(request),
                user_prompt=build_user_prompt(request),
                json_schema=REMINDER_JSON_SCHEMA,
                expected_keys=("intent", "status", "items"),
            )
        except Exception as exc:
            raise ReminderParserError(str(exc)) from exc
        return ReminderParseResult(
            payload=result.payload,
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            stdout=result.stdout,
        )


def fake_parse_payload(request: ReminderParseRequest) -> dict[str, Any]:
    text = request.raw_text.strip()
    low = text.lower()
    if not text:
        return _clarification(text, "Что нужно напомнить?", [])

    if low in {"ближайшие", "покажи ближайшие"}:
        return _base(text, intent="list", status="ok", items=[])

    schedule = None
    event_type = "task"
    recurrence = _recurrence_none()
    all_day = True
    title_source = text

    if "кажд" in low:
        for word, weekday in WEEKDAYS_RU.items():
            if word in low:
                schedule = {
                    "kind": "recurring",
                    "timezone": request.timezone,
                    "all_day": True,
                    "start_at": None,
                    "date": None,
                    "time": _extract_time(low),
                    "precision": "date",
                    "recurrence": {**_recurrence_none(), "frequency": "weekly", "weekdays": [weekday]},
                }
                event_type = "habit"
                title_source = _remove_patterns(low, [r"кажд\w+\s+\w+"])
                break

    birthday_match = re.search(r"(\d{1,2})\s+([а-яё]+).*день\s+рожд", low)
    if birthday_match:
        day = int(birthday_match.group(1))
        month = MONTHS_RU.get(birthday_match.group(2), request.now.month)
        first_date = _next_date(day=day, month=month, now=request.now)
        schedule = {
            "kind": "recurring",
            "timezone": request.timezone,
            "all_day": True,
            "start_at": None,
            "date": first_date.date().isoformat(),
            "time": None,
            "precision": "date",
            "recurrence": {
                **_recurrence_none(),
                "frequency": "yearly",
                "months": [month],
                "month_days": [day],
            },
        }
        event_type = "birthday"
        title_source = _birthday_title(text)

    if schedule is None:
        target = _one_off_datetime(low, request.now)
        if target:
            all_day = target["time"] is None
            schedule = {
                "kind": "once",
                "timezone": request.timezone,
                "all_day": all_day,
                "start_at": target["start_at"],
                "date": target["date"],
                "time": target["time"],
                "precision": "datetime" if target["time"] else "date",
                "recurrence": recurrence,
            }
            title_source = _strip_time_words(text)

    if schedule is None:
        return _clarification(text, "Когда напомнить?", ["сегодня", "завтра", "через час"])

    item = {
        "client_ref": "item_1",
        "title": _title(title_source),
        "description": "",
        "event_type": event_type,
        "priority": "normal",
        "schedule": schedule,
        "notification_offsets": _explicit_offsets(low),
        "confidence": 0.75,
        "assumptions": ["Fake parser: локальная эвристика без LLM."],
    }
    return _base(text, items=[item])


def _one_off_datetime(low: str, now: datetime) -> dict[str, Any] | None:
    time_text = _extract_time(low)
    if "послезавтра" in low:
        target_date = now.date() + timedelta(days=2)
    elif "завтра" in low:
        target_date = now.date() + timedelta(days=1)
    elif "сегодня" in low:
        target_date = now.date()
    else:
        rel = re.search(r"через\s+(\d+|один|одну|пару)\s+(минут|минуты|час|часа|часов|день|дня|дней)", low)
        if rel:
            amount = _amount(rel.group(1))
            unit = rel.group(2)
            delta = timedelta(minutes=amount)
            if unit.startswith("час"):
                delta = timedelta(hours=amount)
            elif unit.startswith("д"):
                delta = timedelta(days=amount)
            target = now + delta
            return {
                "start_at": target.isoformat(timespec="seconds"),
                "date": target.date().isoformat(),
                "time": target.strftime("%H:%M"),
            }
        date_match = re.search(r"(\d{1,2})\s+([а-яё]+)", low)
        if not date_match:
            return None
        day = int(date_match.group(1))
        month = MONTHS_RU.get(date_match.group(2))
        if not month:
            return None
        target_date = _next_date(day=day, month=month, now=now).date()
    if time_text:
        return {"start_at": f"{target_date.isoformat()}T{time_text}:00", "date": target_date.isoformat(), "time": time_text}
    return {"start_at": None, "date": target_date.isoformat(), "time": None}


def _extract_time(low: str) -> str | None:
    match = re.search(r"(?:в\s*)?(\d{1,2})[:.](\d{2})", low)
    if match:
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    match = re.search(r"\bв\s+(\d{1,2})\b", low)
    if match and 0 <= int(match.group(1)) <= 23:
        return f"{int(match.group(1)):02d}:00"
    return None


def _explicit_offsets(low: str) -> list[dict[str, Any]]:
    match = re.search(r"за\s+(\d+|один|одну|пару)\s+(минут|минуты|час|часа|часов|день|дня|дней)", low)
    if not match:
        return []
    amount = _amount(match.group(1))
    unit = match.group(2)
    minutes = amount
    if unit.startswith("час"):
        minutes = amount * 60
    elif unit.startswith("д"):
        minutes = amount * 1440
    return [{"minutes_before": minutes, "source": "explicit"}]


def _amount(value: str) -> int:
    if value in {"один", "одну"}:
        return 1
    if value == "пару":
        return 2
    return int(value)


def _next_date(*, day: int, month: int, now: datetime) -> datetime:
    candidate = datetime(year=now.year, month=month, day=day)
    if candidate.date() < now.date():
        candidate = datetime(year=now.year + 1, month=month, day=day)
    return candidate


def _base(raw_text: str, *, intent: str = "create", status: str = "ok", items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": PROMPT_VERSION,
        "intent": intent,
        "status": status,
        "raw_text": raw_text,
        "items": items or [],
        "clarification": {"question": "", "options": []},
    }


def _clarification(raw_text: str, question: str, options: list[str]) -> dict[str, Any]:
    payload = _base(raw_text, status="needs_clarification", items=[])
    payload["clarification"] = {"question": question, "options": options}
    return payload


def _recurrence_none() -> dict[str, Any]:
    return {
        "frequency": "none",
        "interval": 1,
        "weekdays": [],
        "month_days": [],
        "months": [],
        "until": None,
        "count": None,
        "rrule": "",
    }


def _title(text: str) -> str:
    clean = re.sub(r"\s+", " ", text.strip())
    clean = re.sub(r"^(?:надо|нужно|напомни|напомнить|пожалуйста|давай)\s+", "", clean, flags=re.IGNORECASE)
    clean = _strip_time_words(clean)
    clean = clean.strip(" .,!?:;")
    if not clean:
        return "Напоминание"
    return clean[:1].upper() + clean[1:]


def _strip_time_words(text: str) -> str:
    clean = re.sub(r"\b(?:сегодня|завтра|послезавтра)\b", "", text, flags=re.IGNORECASE)
    clean = re.sub(r"\bчерез\s+(\d+|один|одну|пару)\s+(?:минут|минуты|час|часа|часов|день|дня|дней)\b", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bв\s+\d{1,2}(?::\d{2})?\b", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bза\s+(\d+|один|одну|пару)\s+(?:минут|минуты|час|часа|часов|день|дня|дней)\b", "", clean, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", clean).strip()


def _remove_patterns(text: str, patterns: list[str]) -> str:
    clean = text
    for pattern in patterns:
        clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)
    return clean


def _birthday_title(text: str) -> str:
    return _title(text)

