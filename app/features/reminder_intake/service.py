from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from assistant_toolkit.db import Database

from app.core.ids import new_id
from app.core.time import iso
from app.features.events.service import EventService
from app.features.reminder_intake.agent import (
    ReminderParseRequest,
    ReminderParseResult,
    ReminderParserAgent,
)


@dataclass(frozen=True)
class IntakeResult:
    parse_result: ReminderParseResult
    event_ids: list[str]


class ReminderIntakeService:
    def __init__(
        self,
        db: Database,
        parser: ReminderParserAgent,
        events: EventService,
    ):
        self.db = db
        self.parser = parser
        self.events = events

    def ingest(self, request: ReminderParseRequest) -> IntakeResult:
        created_at = request.now.replace(microsecond=0)
        attempt_id = new_id("parse_")
        try:
            parse_result = self.parser.parse(request)
            payload = parse_result.payload
            event_ids: list[str] = []
            if payload.get("intent") == "create" and payload.get("status") == "ok":
                for item in payload.get("items", []):
                    if isinstance(item, dict):
                        event = self.events.create_from_agent_item(
                            item,
                            source_text=request.raw_text,
                            source_kind=request.source_kind,
                            now=request.now,
                        )
                        event_ids.append(event.id)
            self._record_attempt(
                attempt_id=attempt_id,
                request=request,
                parse_result=parse_result,
                event_ids=event_ids,
                status=str(payload.get("status") or "ok"),
                error="",
                created_at=created_at,
            )
            return IntakeResult(parse_result=parse_result, event_ids=event_ids)
        except Exception as exc:
            payload = {
                "schema_version": "error",
                "intent": "unknown",
                "status": "unsupported",
                "raw_text": request.raw_text,
                "items": [],
                "clarification": {"question": "", "options": []},
            }
            parse_result = ReminderParseResult(
                payload=payload,
                provider=getattr(self.parser, "provider", "unknown"),
                model=getattr(self.parser, "model", ""),
                prompt_version=getattr(self.parser, "prompt_version", ""),
            )
            self._record_attempt(
                attempt_id=attempt_id,
                request=request,
                parse_result=parse_result,
                event_ids=[],
                status="failed",
                error=str(exc),
                created_at=created_at,
            )
            raise

    def _record_attempt(
        self,
        *,
        attempt_id: str,
        request: ReminderParseRequest,
        parse_result: ReminderParseResult,
        event_ids: list[str],
        status: str,
        error: str,
        created_at: datetime,
    ) -> None:
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO parse_attempts (
                    id, source_kind, raw_text, transcript, agent_provider,
                    agent_model, prompt_version, agent_json, status, error,
                    created_event_ids_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    request.source_kind,
                    request.raw_text,
                    request.raw_text if request.source_kind == "voice" else "",
                    parse_result.provider,
                    parse_result.model,
                    parse_result.prompt_version,
                    json.dumps(parse_result.payload, ensure_ascii=False),
                    status,
                    error,
                    json.dumps(event_ids, ensure_ascii=False),
                    iso(created_at),
                ),
            )

