from __future__ import annotations

from typing import Any


TIME_CLARIFICATION_OPTIONS = ["сегодня", "завтра", "через час"]

_TIME_CLARIFICATION_CODES = {
    "date_missing",
    "date_required",
    "datetime_missing",
    "datetime_required",
    "missing_date",
    "missing_datetime",
    "missing_time",
    "no_date_or_time",
    "no_date_specified",
    "no_datetime_specified",
    "no_time_specified",
    "time_missing",
    "time_required",
}

_OPTION_TRANSLATIONS = {
    "today": "сегодня",
    "tomorrow": "завтра",
    "in_1_hour": "через час",
    "in_an_hour": "через час",
    "in_one_hour": "через час",
    "one_hour": "через час",
}


def normalize_clarification(question: object, options: Any) -> tuple[str, list[str]]:
    raw_question = str(question or "").strip()
    normalized_options = _clean_options(options)
    if _is_time_clarification(raw_question):
        return "Когда напомнить?", normalized_options or list(TIME_CLARIFICATION_OPTIONS)
    return raw_question or "Нужно уточнение.", normalized_options


def clarification_options_from_payload(payload: dict[str, Any]) -> list[str]:
    clarification = payload.get("clarification") if isinstance(payload.get("clarification"), dict) else {}
    _, options = normalize_clarification(
        clarification.get("question"),
        clarification.get("options") if isinstance(clarification.get("options"), list) else [],
    )
    return options[:4]


def normalize_payload_clarification(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") != "needs_clarification":
        return payload
    clarification = payload.get("clarification") if isinstance(payload.get("clarification"), dict) else {}
    question, options = normalize_clarification(
        clarification.get("question"),
        clarification.get("options") if isinstance(clarification.get("options"), list) else [],
    )
    normalized = dict(payload)
    normalized["clarification"] = {"question": question, "options": options}
    return normalized


def _clean_options(options: Any) -> list[str]:
    if not isinstance(options, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_option in options:
        option = _normalize_option(raw_option)
        if not option:
            continue
        key = option.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(option)
    return cleaned


def _normalize_option(raw_option: object) -> str:
    option = str(raw_option or "").strip()
    if not option:
        return ""
    code = _machine_code(option)
    if code in _TIME_CLARIFICATION_CODES:
        return ""
    return _OPTION_TRANSLATIONS.get(code, option)


def _is_time_clarification(question: str) -> bool:
    code = _machine_code(question)
    if code in _TIME_CLARIFICATION_CODES:
        return True
    lowered = question.casefold()
    return any(marker in lowered for marker in ("когда", "дата", "дату", "время", "времен"))


def _machine_code(value: str) -> str:
    return "_".join(value.casefold().replace("-", " ").replace("_", " ").split())
