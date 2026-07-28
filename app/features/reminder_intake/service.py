from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from assistant_toolkit.db import Database

from app.core.ids import new_id
from app.core.time import iso
from app.features.events.service import EventService
from app.features.notifications.policy import annotate_notification_preview
from app.features.reminder_intake.agent import (
    ReminderParseRequest,
    ReminderParseResult,
    ReminderParserAgent,
)
from app.features.shopping_lists.parser import coerce_shopping_drafts
from app.features.shopping_lists.parser import normalize_shopping_content
from app.features.shopping_lists.service import ShoppingListService


log = logging.getLogger(__name__)


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
        shopping_lists: ShoppingListService | None = None,
    ):
        self.db = db
        self.parser = parser
        self.events = events
        self.shopping_lists = shopping_lists

    def ingest(self, request: ReminderParseRequest) -> IntakeResult:
        parse_result = self.parse(request)
        return self.create_from_parse_result(request, parse_result)

    def parse(self, request: ReminderParseRequest) -> ReminderParseResult:
        try:
            parse_result = self.parser.parse(request)
            annotate_notification_preview(
                parse_result.payload,
                now=request.now,
                defaults=self.events.defaults,
            )
            _log_clarification_if_needed(request, parse_result)
            return parse_result
        except Exception as exc:
            self._record_attempt(
                attempt_id=new_id("parse_"),
                request=request,
                parse_result=_failed_parse_result(request, self.parser),
                event_ids=[],
                status="failed",
                error=str(exc),
                created_at=request.now.replace(microsecond=0),
            )
            raise

    def create_from_parse_result(
        self,
        request: ReminderParseRequest,
        parse_result: ReminderParseResult,
    ) -> IntakeResult:
        created_at = request.now.replace(microsecond=0)
        attempt_id = new_id("parse_")
        payload = parse_result.payload
        annotate_notification_preview(
            payload,
            now=request.now,
            defaults=self.events.defaults,
        )
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
                    self._create_shopping_list_if_needed(event.id, item, request=request)
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

    def _create_shopping_list_if_needed(
        self,
        event_id: str,
        item: dict,
        *,
        request: ReminderParseRequest,
    ) -> None:
        if self.shopping_lists is None:
            return
        content = normalize_shopping_content(item.get("content"))
        if not content:
            return
        shopping_list = content.get("shopping_list") if isinstance(content.get("shopping_list"), dict) else {}
        drafts = coerce_shopping_drafts(shopping_list.get("items"))
        if not drafts:
            return
        self.shopping_lists.create_for_event(
            event_id,
            title=str(shopping_list.get("title") or "Покупки"),
            items=drafts,
            source_text=request.raw_text,
            source_kind=request.source_kind,
            now=request.now,
        )


def _failed_parse_result(
    request: ReminderParseRequest,
    parser: ReminderParserAgent,
) -> ReminderParseResult:
    payload = {
        "schema_version": "error",
        "intent": "unknown",
        "status": "unsupported",
        "raw_text": request.raw_text,
        "items": [],
        "clarification": {"question": "", "options": []},
    }
    return ReminderParseResult(
        payload=payload,
        provider=getattr(parser, "provider", "unknown"),
        model=getattr(parser, "model", ""),
        prompt_version=getattr(parser, "prompt_version", ""),
    )


def _log_clarification_if_needed(
    request: ReminderParseRequest,
    parse_result: ReminderParseResult,
) -> None:
    payload = parse_result.payload
    if payload.get("status") != "needs_clarification":
        return
    clarification = payload.get("clarification") if isinstance(payload.get("clarification"), dict) else {}
    options = clarification.get("options") if isinstance(clarification.get("options"), list) else []
    log.info(
        "Reminder clarification needed source_kind=%s provider=%s model=%s prompt_version=%s question=%r options=%s raw_text=%r",
        request.source_kind,
        parse_result.provider,
        parse_result.model,
        parse_result.prompt_version,
        str(clarification.get("question") or ""),
        [str(option) for option in options[:5]],
        _short_text(request.raw_text),
    )


def _short_text(value: str, *, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."
