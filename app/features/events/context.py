from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urlparse


CONTEXT_LINK = "link"
CONTEXT_ADDRESS = "address"
CONTEXT_NOTE = "note"
VALID_CONTEXT_KINDS = {CONTEXT_LINK, CONTEXT_ADDRESS, CONTEXT_NOTE}

URL_RE = re.compile(r"(?P<url>(?:https?://|tg://|www\.)[^\s<>()\[\]{}]+)", re.IGNORECASE)
ADDRESS_RE = re.compile(
    r"(?:^|[,;\n])\s*"
    r"(?:(?:по\s+)?адрес(?:у|ом)?(?:\s+(?:встречи|доставки))?|место|локация)"
    r"\s*:?\s*(?P<value>[^\n;]+)",
    re.IGNORECASE,
)


def normalize_event_contexts(value: Any, *, raw_text: str = "", include_extracted: bool = False) -> list[dict[str, str]]:
    contexts: list[dict[str, str]] = []
    if include_extracted:
        contexts.extend(extract_event_contexts(raw_text))
    contexts.extend(_contexts_from_payload(value))
    return _dedupe_contexts(contexts)


def extract_event_contexts(text: str) -> list[dict[str, str]]:
    contexts: list[dict[str, str]] = []
    for url in _urls_from_text(text):
        contexts.append(
            {
                "kind": CONTEXT_LINK,
                "label": link_label(url),
                "value": url,
                "normalized_value": normalize_url(url),
                "source": "extracted",
            }
        )
    address = _address_from_text(text)
    if address:
        contexts.append(
            {
                "kind": CONTEXT_ADDRESS,
                "label": "Адрес",
                "value": address,
                "normalized_value": address,
                "source": "extracted",
            }
        )
    return _dedupe_contexts(contexts)


def strip_context_from_title(text: str) -> str:
    clean = URL_RE.sub("", text)
    clean = re.sub(
        r"[,;\s]*(?:ссылка|линк|url)\s*(?:в|на|по)?\s*[\wа-яё.\- ]*:?",
        " ",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"[,;\s]*(?:(?:по\s+)?адрес(?:у|ом)?(?:\s+(?:встречи|доставки))?|место|локация)\s*:?.*$",
        " ",
        clean,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", clean).strip()


def link_label(url: str) -> str:
    domain = _domain(url)
    provider_labels = {
        "telemost.yandex.ru": "Телемост",
        "zoom.us": "Zoom",
        "meet.google.com": "Google Meet",
        "teams.microsoft.com": "Teams",
        "docs.google.com": "Google Docs",
        "drive.google.com": "Google Drive",
        "forms.gle": "Google Forms",
        "calendar.google.com": "Google Calendar",
        "notion.so": "Notion",
        "github.com": "GitHub",
        "figma.com": "Figma",
        "t.me": "Telegram",
        "yandex.ru": "Яндекс",
    }
    for suffix, label in provider_labels.items():
        if domain == suffix or domain.endswith(f".{suffix}"):
            return label
    return domain or "Ссылка"


def normalize_url(url: str) -> str:
    clean = _trim_url(url)
    if clean.startswith("www."):
        return f"https://{clean}"
    return clean


def context_action_url(context: Any) -> str:
    kind = _context_attr(context, "kind")
    value = _context_attr(context, "value")
    normalized_value = _context_attr(context, "normalized_value")
    if kind == CONTEXT_LINK:
        return normalize_url(normalized_value or value)
    if kind == CONTEXT_ADDRESS and value:
        return f"https://yandex.ru/maps/?text={quote_plus(value)}"
    return ""


def context_button_label(context: Any) -> str:
    kind = _context_attr(context, "kind")
    label = _context_attr(context, "label")
    if kind == CONTEXT_LINK:
        button = "Открыть ссылку" if label in {"", "Ссылка"} else f"Открыть: {label}"
        return _short_button_label(button)
    if kind == CONTEXT_ADDRESS:
        return "Открыть карту"
    return label or "Открыть"


def context_summary_label(context: Any) -> str:
    kind = _context_attr(context, "kind")
    label = _context_attr(context, "label")
    value = _context_attr(context, "value")
    if kind == CONTEXT_LINK:
        return label or link_label(value)
    if kind == CONTEXT_ADDRESS:
        return value
    return label or value


def context_kind_marker(contexts: tuple[Any, ...] | list[Any]) -> str:
    has_link = any(_context_attr(item, "kind") == CONTEXT_LINK for item in contexts)
    has_address = any(_context_attr(item, "kind") == CONTEXT_ADDRESS for item in contexts)
    markers = []
    if has_link:
        markers.append("🔗")
    if has_address:
        markers.append("📍")
    return "".join(markers)


def _contexts_from_payload(value: Any) -> list[dict[str, str]]:
    if not value:
        return []
    if isinstance(value, list):
        contexts = []
        for item in value:
            context = _normalize_context_item(item)
            if context:
                contexts.append(context)
        return contexts
    if not isinstance(value, dict):
        return []

    contexts: list[dict[str, str]] = []
    for item in _as_list(value.get("links") or value.get("link") or value.get("url") or value.get("urls")):
        context = _normalize_link_item(item)
        if context:
            contexts.append(context)
    for item in _as_list(value.get("locations") or value.get("location") or value.get("address") or value.get("venue")):
        context = _normalize_address_item(item)
        if context:
            contexts.append(context)
    for item in _as_list(value.get("notes") or value.get("note")):
        context = _normalize_note_item(item)
        if context:
            contexts.append(context)
    return contexts


def _normalize_context_item(item: Any) -> dict[str, str]:
    if isinstance(item, str):
        if _looks_like_url(item):
            return _normalize_link_item(item)
        return _normalize_note_item(item)
    if not isinstance(item, dict):
        return {}
    kind = str(item.get("kind") or item.get("type") or "").strip().lower()
    if not kind:
        if item.get("url") or item.get("link"):
            kind = CONTEXT_LINK
        elif item.get("address") or item.get("location") or item.get("venue"):
            kind = CONTEXT_ADDRESS
        else:
            kind = CONTEXT_NOTE
    if kind in {"url", "link"}:
        return _normalize_link_item(item)
    if kind in {"address", "location", "place", "venue"}:
        return _normalize_address_item(item)
    if kind == CONTEXT_NOTE:
        return _normalize_note_item(item)
    return {}


def _normalize_link_item(item: Any) -> dict[str, str]:
    if isinstance(item, str):
        url = _trim_url(item)
        label = ""
    elif isinstance(item, dict):
        url = _trim_url(str(item.get("url") or item.get("link") or item.get("value") or ""))
        label = str(item.get("label") or item.get("title") or item.get("name") or "").strip()
    else:
        return {}
    if not _looks_like_url(url):
        return {}
    normalized = normalize_url(url)
    return {
        "kind": CONTEXT_LINK,
        "label": label or link_label(normalized),
        "value": url,
        "normalized_value": normalized,
        "source": "parser",
    }


def _normalize_address_item(item: Any) -> dict[str, str]:
    if isinstance(item, str):
        address = _trim_address(item)
        label = ""
    elif isinstance(item, dict):
        address = _trim_address(str(item.get("address") or item.get("location") or item.get("venue") or item.get("value") or ""))
        label = str(item.get("label") or item.get("title") or item.get("name") or "").strip()
    else:
        return {}
    if not address:
        return {}
    return {
        "kind": CONTEXT_ADDRESS,
        "label": label or "Адрес",
        "value": address,
        "normalized_value": address,
        "source": "parser",
    }


def _normalize_note_item(item: Any) -> dict[str, str]:
    if isinstance(item, dict):
        value = str(item.get("value") or item.get("text") or item.get("note") or "").strip()
        label = str(item.get("label") or item.get("title") or "").strip()
    else:
        value = str(item or "").strip()
        label = ""
    if not value:
        return {}
    return {
        "kind": CONTEXT_NOTE,
        "label": label or "Заметка",
        "value": value,
        "normalized_value": value,
        "source": "parser",
    }


def _urls_from_text(text: str) -> list[str]:
    return [_trim_url(match.group("url")) for match in URL_RE.finditer(text or "")]


def _address_from_text(text: str) -> str:
    match = ADDRESS_RE.search(text or "")
    if not match:
        return ""
    return _trim_address(match.group("value"))


def _trim_url(url: str) -> str:
    return str(url or "").strip().rstrip(".,;!?")


def _trim_address(value: str) -> str:
    clean = URL_RE.sub("", value)
    clean = re.split(r"\b(?:ссылка|линк|url)\b", clean, maxsplit=1, flags=re.IGNORECASE)[0]
    clean = clean.strip(" \t\r\n.,;:")
    return re.sub(r"\s+", " ", clean)


def _looks_like_url(value: str) -> bool:
    clean = str(value or "").strip().lower()
    return clean.startswith(("http://", "https://", "tg://", "www."))


def _domain(url: str) -> str:
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    domain = parsed.netloc or parsed.path.split("/", 1)[0]
    domain = domain.lower().removeprefix("www.")
    return domain


def _dedupe_contexts(contexts: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    indexes: dict[tuple[str, str], int] = {}
    for context in contexts:
        kind = str(context.get("kind") or "").strip().lower()
        value = str(context.get("value") or "").strip()
        if kind not in VALID_CONTEXT_KINDS or not value:
            continue
        normalized = str(context.get("normalized_value") or value).strip()
        key = (kind, normalized.casefold())
        if key in seen:
            existing = result[indexes[key]]
            incoming_label = str(context.get("label") or "").strip()
            if existing["source"] == "extracted" and incoming_label:
                existing["label"] = incoming_label
                existing["source"] = str(context.get("source") or "parser").strip() or "parser"
            continue
        seen.add(key)
        indexes[key] = len(result)
        result.append(
            {
                "kind": kind,
                "label": str(context.get("label") or "").strip() or _default_label(kind, value),
                "value": value,
                "normalized_value": normalized,
                "source": str(context.get("source") or "parser").strip() or "parser",
            }
        )
    return result


def _default_label(kind: str, value: str) -> str:
    if kind == CONTEXT_LINK:
        return link_label(value)
    if kind == CONTEXT_ADDRESS:
        return "Адрес"
    return "Заметка"


def _short_button_label(value: str) -> str:
    return value if len(value) <= 40 else f"{value[:37]}..."


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _context_attr(context: Any, key: str) -> str:
    if isinstance(context, dict):
        return str(context.get(key) or "").strip()
    return str(getattr(context, key, "") or "").strip()
