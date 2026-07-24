from __future__ import annotations

from typing import Any


PROMPT_VERSION = "reminder-parser-v2"

REMINDER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "intent", "status", "raw_text", "items", "clarification"],
    "properties": {
        "schema_version": {"type": "string"},
        "intent": {
            "type": "string",
            "enum": ["create", "list", "update", "cancel", "complete", "snooze", "unknown"],
        },
        "status": {
            "type": "string",
            "enum": ["ok", "needs_clarification", "unsupported"],
        },
        "raw_text": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "client_ref",
                    "title",
                    "description",
                    "event_type",
                    "priority",
                    "schedule",
                    "notification_offsets",
                    "confidence",
                    "assumptions",
                ],
                "properties": {
                    "client_ref": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "event_type": {
                        "type": "string",
                        "enum": ["task", "calendar_event", "deadline", "birthday", "anniversary", "habit"],
                    },
                    "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                    "schedule": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "kind",
                            "timezone",
                            "all_day",
                            "start_at",
                            "date",
                            "time",
                            "precision",
                            "recurrence",
                        ],
                        "properties": {
                            "kind": {"type": "string", "enum": ["once", "recurring"]},
                            "timezone": {"type": "string"},
                            "all_day": {"type": "boolean"},
                            "start_at": {"type": ["string", "null"]},
                            "date": {"type": ["string", "null"]},
                            "time": {"type": ["string", "null"]},
                            "precision": {"type": "string", "enum": ["datetime", "date", "week", "month", "unknown"]},
                            "recurrence": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["frequency", "interval", "weekdays", "month_days", "months", "until", "count", "rrule"],
                                "properties": {
                                    "frequency": {
                                        "type": "string",
                                        "enum": ["none", "daily", "weekly", "monthly", "yearly", "custom_rrule"],
                                    },
                                    "interval": {"type": "integer", "minimum": 1},
                                    "weekdays": {
                                        "type": "array",
                                        "items": {"type": "string", "enum": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]},
                                    },
                                    "month_days": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 1, "maximum": 31},
                                    },
                                    "months": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 1, "maximum": 12},
                                    },
                                    "until": {"type": ["string", "null"]},
                                    "count": {"type": ["integer", "null"]},
                                    "rrule": {"type": "string"},
                                },
                            },
                        },
                    },
                    "notification_offsets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["minutes_before", "source"],
                            "properties": {
                                "minutes_before": {"type": "integer", "minimum": 0},
                                "source": {"type": "string", "enum": ["explicit", "default_suggested"]},
                            },
                        },
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "clarification": {
            "type": "object",
            "additionalProperties": False,
            "required": ["question", "options"],
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}
