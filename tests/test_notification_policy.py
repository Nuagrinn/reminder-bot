from __future__ import annotations

from datetime import datetime
from unittest import TestCase

from app.features.events.service import EventDefaults
from app.features.notifications.policy import build_notification_rules, notification_rule_labels
from tests.test_fake_parser import request
from app.features.reminder_intake.agent import FakeReminderParserAgent


def item_for(text: str):
    return FakeReminderParserAgent().parse(request(text)).payload["items"][0]


class NotificationPolicyTest(TestCase):
    def setUp(self) -> None:
        self.defaults = EventDefaults(timezone="Europe/Moscow")
        self.now = datetime(2026, 7, 24, 12, 0)

    def test_future_day_task_gets_day_before_morning_and_evening(self) -> None:
        rules = build_notification_rules(item_for("надо завтра пополнить карту наличкой"), now=self.now, defaults=self.defaults)

        self.assertEqual(notification_rule_labels(rules), ["вечером за день", "утром в день", "вечером в день"])

    def test_today_exact_time_gets_hour_and_quarter_offsets(self) -> None:
        rules = build_notification_rules(item_for("сегодня в 15:30 оплатить счет"), now=self.now, defaults=self.defaults)

        self.assertEqual(notification_rule_labels(rules), ["за 1 ч.", "за 15 мин."])

    def test_relative_delay_is_a_moment_reminder(self) -> None:
        rules = build_notification_rules(item_for("через 2 часа проверить духовку"), now=self.now, defaults=self.defaults)

        self.assertEqual(notification_rule_labels(rules), ["в момент события"])

    def test_weekly_day_task_gets_day_before_and_day_checks(self) -> None:
        rules = build_notification_rules(item_for("каждый вторник обновлять отчет по калориям"), now=self.now, defaults=self.defaults)

        self.assertEqual(notification_rule_labels(rules), ["вечером за день", "утром в день", "вечером в день"])

    def test_annual_date_gets_week_day_before_and_morning(self) -> None:
        rules = build_notification_rules(item_for("12 августа день рождения Маши"), now=self.now, defaults=self.defaults)

        self.assertEqual(notification_rule_labels(rules), ["за 7 дн. в 09:00", "вечером за день", "утром в день"])

    def test_explicit_offsets_override_defaults(self) -> None:
        item = item_for("завтра в 15:30 оплатить счет за 2 часа")
        rules = build_notification_rules(item, now=self.now, defaults=self.defaults)

        self.assertEqual(notification_rule_labels(rules), ["за 2 ч."])
