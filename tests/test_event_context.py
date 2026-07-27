from __future__ import annotations

from unittest import TestCase

from app.features.events.context import context_action_url
from app.features.events.context import extract_event_contexts
from app.features.events.context import normalize_event_contexts
from app.features.events.context import strip_context_from_title


class EventContextTests(TestCase):
    def test_extracts_multiple_link_labels(self) -> None:
        contexts = extract_event_contexts(
            "созвон https://meet.google.com/abc-defg-hij, "
            "док https://docs.google.com/document/d/123 и zoom https://zoom.us/j/123"
        )

        labels = [item["label"] for item in contexts]

        self.assertEqual(labels, ["Google Meet", "Google Docs", "Zoom"])

    def test_normalizes_www_link_for_button_url(self) -> None:
        contexts = extract_event_contexts("завтра посмотреть www.example.com/path")

        self.assertEqual(contexts[0]["value"], "www.example.com/path")
        self.assertEqual(contexts[0]["normalized_value"], "https://www.example.com/path")
        self.assertEqual(context_action_url(contexts[0]), "https://www.example.com/path")

    def test_extracts_explicit_address_and_map_url(self) -> None:
        contexts = extract_event_contexts("завтра встреча, адрес: Москва, Никольская 10")

        self.assertEqual(contexts[0]["kind"], "address")
        self.assertEqual(contexts[0]["value"], "Москва, Никольская 10")
        self.assertEqual(
            context_action_url(contexts[0]),
            "https://yandex.ru/maps/?text=%D0%9C%D0%BE%D1%81%D0%BA%D0%B2%D0%B0%2C+"
            "%D0%9D%D0%B8%D0%BA%D0%BE%D0%BB%D1%8C%D1%81%D0%BA%D0%B0%D1%8F+10",
        )

    def test_extracts_delivery_address_label(self) -> None:
        contexts = extract_event_contexts("завтра забрать заказ, адрес доставки: Москва, Арбат 1")

        self.assertEqual(contexts[0]["kind"], "address")
        self.assertEqual(contexts[0]["value"], "Москва, Арбат 1")

    def test_strip_context_from_title_removes_link_and_address_clauses(self) -> None:
        link_title = strip_context_from_title(
            "Завтра в 14:00 собес/скрининг, ссылка в телемост: https://telemost.yandex.ru/j/123"
        )
        address_title = strip_context_from_title("Завтра в 19:00 встреча, адрес: Москва, Никольская 10")

        self.assertEqual(link_title, "Завтра в 14:00 собес/скрининг")
        self.assertEqual(address_title, "Завтра в 19:00 встреча")

    def test_parser_label_can_override_extracted_domain_label(self) -> None:
        contexts = normalize_event_contexts(
            {"links": [{"url": "https://example.com/abc", "label": "Бронь"}], "locations": []},
            raw_text="завтра проверить бронь https://example.com/abc",
            include_extracted=True,
        )

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["label"], "Бронь")
