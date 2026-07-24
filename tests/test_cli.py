from __future__ import annotations

from unittest import TestCase

from app.cli import build_parser


class CliParserTest(TestCase):
    def test_stt_check_command_is_registered(self) -> None:
        args = build_parser().parse_args(["stt-check", "--provider", "whisper_cpp"])

        self.assertEqual(args.command, "stt-check")
        self.assertEqual(args.provider, "whisper_cpp")

    def test_stt_preview_command_is_registered(self) -> None:
        args = build_parser().parse_args(["stt-preview", "voice.oga", "--provider", "whisper_cpp"])

        self.assertEqual(args.command, "stt-preview")
        self.assertEqual(args.audio, "voice.oga")
        self.assertEqual(args.provider, "whisper_cpp")

