from __future__ import annotations

import re

from app.features.events.models import NotificationJobView, OccurrenceView


def occurrence_time_prefix(item: OccurrenceView) -> str:
    broad_label = broad_time_label(item.source_text)
    if broad_label and not has_explicit_clock_time(item.source_text):
        return broad_label
    if item.all_day:
        return ""
    return item.occurs_at.strftime("%H:%M")


def occurrence_when_label(item: OccurrenceView) -> str:
    prefix = occurrence_time_prefix(item)
    if not prefix:
        return item.occurs_at.strftime("%d.%m.%Y")
    return f"{item.occurs_at:%d.%m.%Y}, {prefix}" if not _looks_like_clock_time(prefix) else item.occurs_at.strftime("%d.%m.%Y %H:%M")


def job_when_label(job: NotificationJobView) -> str:
    broad_label = broad_time_label(job.source_text)
    if broad_label and not has_explicit_clock_time(job.source_text):
        return f"{job.occurs_at:%d.%m.%Y}, {broad_label}"
    if job.all_day:
        return job.occurs_at.strftime("%d.%m.%Y")
    return job.occurs_at.strftime("%d.%m.%Y %H:%M")


def occurrence_button_label(index: int, item: OccurrenceView) -> str:
    title = item.title
    if len(title) > 34:
        title = f"{title[:31]}..."
    prefix = occurrence_time_prefix(item)
    if not prefix:
        return f"{index}. {title}"
    return f"{index}. {prefix} · {title}"


def broad_time_label(text: str) -> str:
    low = text.lower()
    if re.search(r"\bутром\b", low):
        return "утром"
    if re.search(r"\bдн[её]м\b", low):
        return "днем"
    if re.search(r"\bвечером\b", low):
        return "вечером"
    if re.search(r"\bночью\b", low):
        return "ночью"
    return ""


def has_explicit_clock_time(text: str) -> bool:
    low = text.lower()
    if re.search(r"(?:^|\s)в\s*\d{1,2}[:.]\d{2}\b", low):
        return True
    return bool(re.search(r"(?:^|\s)в\s+\d{1,2}\b", low))


def _looks_like_clock_time(text: str) -> bool:
    return bool(re.fullmatch(r"\d{2}:\d{2}", text))
