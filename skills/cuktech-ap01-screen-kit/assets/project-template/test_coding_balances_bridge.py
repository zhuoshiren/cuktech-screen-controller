from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import coding_balances_bridge as bridge
import claude_statusline_cache
from quota_dashboard import Quota


class CodingBalancesBridgeTests(unittest.TestCase):

    def test_error_text_redacts_tokens_urls_and_home_paths(self) -> None:
        message = bridge._short_error(
            RuntimeError(
                f"failed at {Path.home()}/private with "
                "https://example.test/path?token=secret and sk-testsecret123456"
            )
        )
        self.assertNotIn(str(Path.home()), message)
        self.assertNotIn("token=secret", message)
        self.assertNotIn("sk-testsecret", message)

    def test_ap01_allow_list_accepts_only_private_ipv4(self) -> None:
        self.assertEqual(
            bridge._validated_allowed_clients(["192.168.50.30"]),
            {"192.168.50.30"},
        )
        for value in ("8.8.8.8", "127.0.0.1", "::1", "not-an-ip"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bridge._validated_allowed_clients([value])

    def test_kimi_usage_parser_keeps_week_five_hour_and_extra_balance(self) -> None:
        usage = bridge.parse_kimi_usage(
            {
                "usage": {"used": "250", "limit": "1000", "resetTime": "2026-08-14T00:00:00Z"},
                "limits": [
                    {
                        "window": {"duration": 300, "timeUnit": "TIME_UNIT_MINUTE"},
                        "detail": {"used": "20", "limit": "100", "resetTime": "2026-08-07T08:00:00Z"},
                    }
                ],
                "boosterWallet": {
                    "balance": {"type": "BOOSTER", "amount": "5000000000", "amountLeft": "2500000000"},
                    "monthlyUsed": {"priceInCents": 100, "currency": "CNY"},
                },
                "user": {"membership": {"level": "LEVEL_ADVANCED"}},
            }
        )
        self.assertEqual(usage.weekly_remaining_percent, 75.0)
        self.assertEqual(usage.five_hour_remaining_percent, 80.0)
        self.assertEqual(usage.extra_balance, 25.0)
        self.assertEqual(usage.extra_currency, "CNY")
        self.assertEqual(usage.plan, "Allegro")

    def test_deepseek_balance_prefers_cny(self) -> None:
        balance = bridge.parse_deepseek_balance(
            {
                "is_available": True,
                "balance_infos": [
                    {"currency": "USD", "total_balance": "1.00", "granted_balance": "0", "topped_up_balance": "1"},
                    {"currency": "CNY", "total_balance": "20.50", "granted_balance": "2.50", "topped_up_balance": "18"},
                ],
            }
        )
        self.assertEqual(balance.currency, "CNY")
        self.assertEqual(balance.total_balance, 20.5)
        self.assertTrue(balance.available)

    def test_statusline_cache_keeps_only_official_quota_fields(self) -> None:
        payload = claude_statusline_cache.sanitized_quota(
            {
                "session_id": "secret-session-id",
                "transcript_path": "/private/conversation.jsonl",
                "rate_limits": {
                    "five_hour": {"used_percentage": 23.5, "resets_at": 1_738_425_600},
                    "seven_day": {"used_percentage": 41.2, "resets_at": 1_738_857_600},
                },
            }
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["used_percent"], 23.5)
        self.assertEqual(payload["weekly_used_percent"], 41.2)
        self.assertEqual(payload["plan"], "max")
        serialized = json.dumps(payload)
        self.assertNotIn("secret-session-id", serialized)
        self.assertNotIn("transcript", serialized)

    def test_two_combined_page_gifs_are_ap01_compatible(self) -> None:
        now = datetime.now().astimezone()
        snapshot = bridge.Snapshot(
            codex=Quota(
                provider="CODEX",
                used_percent=12,
                weekly_used_percent=14,
                resets_at=1_786_162_488,
                weekly_resets_at=1_786_162_488,
                plan="pro",
            ),
            claude=Quota(
                provider="CLAUDE",
                used_percent=6,
                weekly_used_percent=24,
                resets_at=1_786_162_488,
                weekly_resets_at=1_786_162_488,
                plan="max",
            ),
            kimi=bridge.KimiUsage(
                weekly_used=250,
                weekly_limit=1000,
                weekly_resets_at="2026-08-14T00:00:00Z",
                five_hour_used=20,
                five_hour_limit=100,
                five_hour_resets_at="2026-08-07T08:00:00Z",
                extra_balance=25,
                extra_currency="CNY",
                plan="Allegro",
            ),
            deepseek=bridge.DeepSeekBalance(
                available=True,
                total_balance=20.5,
                granted_balance=2.5,
                topped_up_balance=18,
                currency="CNY",
            ),
            errors={},
            generated_at=now,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                "ARTIFACTS": root,
                "GIF": root / "screen.gif",
                "GIF_MAIN": root / "codex-claude.gif",
                "GIF_OTHERS": root / "others.gif",
                "BUNDLE": root / "pages.ap2b",
                "PNG": root / "screen.png",
                "JSON_OUT": root / "balances.json",
                "PAGE_MAIN": root / "codex-claude.png",
                "PAGE_OTHERS": root / "others.png",
            }
            with patch.multiple(bridge, **paths):
                bridge.render_snapshot(snapshot, persistent_display=True)
            for key in ("GIF_MAIN", "GIF_OTHERS"):
                with Image.open(paths[key]) as image:
                    self.assertEqual(image.size, (320, 240))
                    self.assertEqual(image.n_frames, 2)
                    self.assertEqual(image.info.get("loop"), 0)
                    for frame in range(image.n_frames):
                        image.seek(frame)
                        self.assertEqual(image.info.get("duration"), 60_000)
                self.assertLessEqual(paths[key].stat().st_size, bridge.AP01_GIF_MAX_BYTES)
                self.assertEqual(paths[key].read_bytes()[:6], b"GIF89a")
            self.assertEqual(paths["GIF"].read_bytes(), paths["GIF_MAIN"].read_bytes())
            bundle = paths["BUNDLE"].read_bytes()
            magic, version, main_size, others_size, check = __import__("struct").unpack(
                "<5I", bundle[:20]
            )
            self.assertEqual(magic, 0x42325041)
            self.assertEqual(version, 1)
            self.assertEqual(main_size, paths["GIF_MAIN"].stat().st_size)
            self.assertEqual(others_size, paths["GIF_OTHERS"].stat().st_size)
            self.assertEqual(check, magic ^ version ^ main_size ^ others_size ^ 0xA50102B2)
            self.assertEqual(len(bundle), 20 + main_size + others_size)
            self.assertEqual(bundle[20 : 20 + main_size], paths["GIF_MAIN"].read_bytes())
            self.assertEqual(bundle[20 + main_size :], paths["GIF_OTHERS"].read_bytes())
            document = json.loads(paths["JSON_OUT"].read_text(encoding="utf-8"))
            serialized = json.dumps(document)
            self.assertNotIn("access_token", serialized)
            self.assertNotIn("api_key", serialized)
            self.assertNotIn("access_key", serialized)
            for name, path in paths.items():
                if name != "ARTIFACTS":
                    self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
