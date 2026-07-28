from __future__ import annotations

import re
from typing import Any

from app.features.shopping_lists.models import ShoppingItemDraft


SHOPPING_CONTENT_KIND = "shopping_list"

_EXPLICIT_SHOPPING_RE = re.compile(
    r"\b(покупк\w*|спис(?:ок|ка)\s+покупок|продукт\w*|магазин\w*)\b",
    re.IGNORECASE,
)
_BUY_VERB_RE = re.compile(
    r"\b(купить|купи|куплю|купим|докупить|возьми|взять|прикупить)\b",
    re.IGNORECASE,
)
_LEADING_WORDS_RE = re.compile(
    r"^(?:и\s+)?(?:еще|ещё|надо|нужно|нужен|нужна|нужны|пожалуйста|потом|также)\s+",
    re.IGNORECASE,
)
_SHOPPING_HELPER_RE = re.compile(
    r"\b(?:в\s+спис(?:ок|ка)\s+покупок|в\s+покупки|для\s+покупок|из\s+покупок)\b",
    re.IGNORECASE,
)
_DATE_TIME_HELPER_RE = re.compile(
    r"\b(?:сегодня|завтра|послезавтра|утром|днем|днём|вечером|ночью|в\s+\d{1,2}(?::\d{2})?)\b",
    re.IGNORECASE,
)


def looks_like_shopping_text(text: str) -> bool:
    raw = _normalize_space(text)
    if not raw:
        return False
    if _EXPLICIT_SHOPPING_RE.search(raw):
        return True
    if not _BUY_VERB_RE.search(raw):
        return False
    return len(parse_shopping_items(raw)) >= 2


def shopping_content_from_text(text: str) -> dict[str, Any] | None:
    if not looks_like_shopping_text(text):
        return None
    drafts = parse_shopping_items(text)
    if not drafts:
        return None
    return shopping_content_from_drafts(drafts)


def shopping_content_from_drafts(drafts: list[ShoppingItemDraft], *, title: str = "Покупки") -> dict[str, Any] | None:
    items = [_draft_to_payload(item) for item in drafts if item.title.strip()]
    if not items:
        return None
    return {
        "kind": SHOPPING_CONTENT_KIND,
        "shopping_list": {
            "title": title,
            "items": items,
        },
    }


def normalize_shopping_content(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, dict):
        if value.get("kind") == SHOPPING_CONTENT_KIND and isinstance(value.get("shopping_list"), dict):
            title = _clean(value["shopping_list"].get("title")) or "Покупки"
            drafts = coerce_shopping_drafts(value["shopping_list"].get("items"))
            return shopping_content_from_drafts(drafts, title=title)
        if "items" in value:
            title = _clean(value.get("title")) or "Покупки"
            return shopping_content_from_drafts(coerce_shopping_drafts(value.get("items")), title=title)
    return shopping_content_from_drafts(coerce_shopping_drafts(value))


def coerce_shopping_drafts(value: Any) -> list[ShoppingItemDraft]:
    if not value:
        return []
    if isinstance(value, str):
        return parse_shopping_items(value)
    if not isinstance(value, list):
        return []
    drafts: list[ShoppingItemDraft] = []
    for raw_item in value:
        if isinstance(raw_item, str):
            title = _clean_item_title(raw_item)
            if title:
                drafts.append(ShoppingItemDraft(title=title))
            continue
        if not isinstance(raw_item, dict):
            continue
        title = _clean_item_title(raw_item.get("title") or raw_item.get("name") or raw_item.get("item"))
        if not title:
            continue
        drafts.append(
            ShoppingItemDraft(
                title=title,
                quantity=_clean(raw_item.get("quantity") or raw_item.get("amount")),
                note=_clean(raw_item.get("note") or raw_item.get("comment")),
            )
        )
    return drafts


def parse_shopping_items(text: str) -> list[ShoppingItemDraft]:
    text = _normalize_space(text)
    if not text:
        return []
    text = _strip_shopping_shell(text)
    parts = _split_items(text)
    drafts: list[ShoppingItemDraft] = []
    seen: set[str] = set()
    for part in parts:
        title = _clean_item_title(part)
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        drafts.append(ShoppingItemDraft(title=title))
    return drafts


def _strip_shopping_shell(text: str) -> str:
    text = _SHOPPING_HELPER_RE.sub(" ", text)
    text = _DATE_TIME_HELPER_RE.sub(" ", text)
    text = re.sub(r"\b(?:надо|нужно|пожалуйста)\b", " ", text, flags=re.IGNORECASE)
    text = _BUY_VERB_RE.sub(" ", text)
    return _normalize_space(text)


def _split_items(text: str) -> list[str]:
    text = text.replace("\n", ",")
    text = re.sub(r"\s+(?:и|а\s+еще|а\s+ещё)\s+", ",", text, flags=re.IGNORECASE)
    return [part.strip(" .,:;!-") for part in re.split(r"[,;]+", text)]


def _draft_to_payload(item: ShoppingItemDraft) -> dict[str, str]:
    return {
        "title": item.title.strip(),
        "quantity": item.quantity.strip(),
        "note": item.note.strip(),
    }


def _clean_item_title(value: Any) -> str:
    text = _clean(value)
    while True:
        cleaned = _LEADING_WORDS_RE.sub("", text).strip()
        if cleaned == text:
            break
        text = cleaned
    text = text.strip(" .,:;!-")
    if not text:
        return ""
    return f"{text[0].lower()}{text[1:]}" if len(text) > 1 else text.lower()


def _clean(value: Any) -> str:
    return _normalize_space(str(value or ""))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())
