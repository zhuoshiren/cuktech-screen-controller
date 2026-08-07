from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageSequence

import codex_plan_bridge as bridge
from quota_dashboard import Quota


class CodexPlanBridgeTests(unittest.TestCase):
    def test_error_text_does_not_expose_home_url_or_token(self) -> None:
        message = bridge._safe_error(
            RuntimeError(
                f"{Path.home()}/secret https://example.test/?x=y sk-testsecret123456"
            )
        )
        self.assertNotIn(str(Path.home()), message)
        self.assertNotIn("x=y", message)
        self.assertNotIn("sk-testsecret", message)

    def test_lan_bind_requires_an_ap01_allow_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires at least one"):
            bridge.allowed_clients_for("0.0.0.0", [], "192.168.50.20")
        allowed = bridge.allowed_clients_for(
            "0.0.0.0", ["192.168.50.30"], "192.168.50.20"
        )
        self.assertEqual(
            allowed,
            {"127.0.0.1", "::1", "192.168.50.20", "192.168.50.30"},
        )
        for value in ("8.8.8.8", "192.0.2.1", "127.0.0.1", "::1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bridge.allowed_clients_for("0.0.0.0", [value], "192.168.50.20")

    def test_codex_only_asset_is_ap01_compatible(self) -> None:
        quota = Quota(
            provider="CODEX",
            used_percent=None,
            weekly_used_percent=14,
            weekly_window_minutes=10_080,
            weekly_resets_at=1_786_162_488,
            plan="pro",
            source="Codex app-server",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(bridge, "ARTIFACTS", root),
                patch.object(bridge, "PNG", root / "codex-plan.png"),
                patch.object(bridge, "GIF", root / "codex-plan.gif"),
                patch.object(bridge, "MASTER", root / "codex-plan-master.png"),
                patch.object(bridge, "PREVIEW", root / "codex-plan@2x.png"),
            ):
                bridge.render_outputs(
                    quota,
                    refreshed_at=datetime.fromtimestamp(1_786_100_000).astimezone(),
                )
                with Image.open(bridge.PNG) as image:
                    self.assertEqual(image.size, (320, 240))
                    self.assertEqual(image.crop((0, 0, 320, 40)).getbbox(), (0, 0, 320, 40))
                    self.assertEqual(image.getpixel((5, 5)), (1, 4, 11))
                self.assertEqual(bridge.GIF.read_bytes()[:6], b"GIF89a")
                self.assertLessEqual(bridge.GIF.stat().st_size, 90_000)
                for path in (bridge.PNG, bridge.GIF, bridge.MASTER, bridge.PREVIEW):
                    self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
                with Image.open(bridge.GIF) as gif:
                    self.assertGreaterEqual(sum(1 for _ in ImageSequence.Iterator(gif)), 2)

    def test_persistent_codex_asset_never_reaches_disconnected_frame(self) -> None:
        quota = Quota(
            provider="CODEX",
            used_percent=12,
            weekly_used_percent=14,
            plan="pro",
            source="Codex app-server",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(bridge, "ARTIFACTS", root),
                patch.object(bridge, "PNG", root / "codex-plan.png"),
                patch.object(bridge, "GIF", root / "codex-plan.gif"),
                patch.object(bridge, "MASTER", root / "codex-plan-master.png"),
                patch.object(bridge, "PREVIEW", root / "codex-plan@2x.png"),
            ):
                bridge.render_outputs(quota, persistent_display=True)
                with Image.open(bridge.GIF) as gif:
                    self.assertEqual(gif.n_frames, 5)
                    self.assertEqual(gif.info.get("loop"), 0)



if __name__ == "__main__":
    unittest.main()
