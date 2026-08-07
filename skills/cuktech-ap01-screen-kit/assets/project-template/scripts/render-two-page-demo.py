#!/usr/bin/env python3
"""Render the README's two-page preview with synthetic account data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/images/two-page-coding-dashboard.png"
sys.path.insert(0, str(ROOT))

import coding_balances_bridge as bridge  # noqa: E402


def main() -> int:
    generated_at = datetime(2026, 8, 7, 12, 0).astimezone()
    codex = bridge.CodexQuota(
        provider="CODEX",
        used_percent=28,
        weekly_used_percent=44,
        resets_at=1_786_162_488,
        weekly_resets_at=1_786_162_488,
        plan="pro",
    )
    claude = bridge.ClaudeQuota(
        provider="CLAUDE",
        used_percent=18,
        weekly_used_percent=36,
        resets_at=1_786_162_488,
        weekly_resets_at=1_786_162_488,
        plan="max",
    )
    kimi = bridge.KimiUsage(
        weekly_used=240,
        weekly_limit=1000,
        weekly_resets_at="2026-08-14T00:00:00+08:00",
        five_hour_used=16,
        five_hour_limit=100,
        five_hour_resets_at="2026-08-07T16:00:00+08:00",
        extra_balance=25.0,
        extra_currency="CNY",
        plan="Allegro",
    )
    deepseek = bridge.DeepSeekBalance(
        available=True,
        total_balance=88.50,
        granted_balance=18.50,
        topped_up_balance=70.00,
        currency="CNY",
    )

    pages = (
        bridge._fit_frame(
            bridge.render_codex_claude_master(
                codex,
                claude,
                refreshed_at=generated_at,
            ),
            2,
        ),
        bridge._fit_frame(bridge.render_others_master(kimi, deepseek), 2),
    )
    canvas = Image.new("RGB", (1320, 540), "#050A12")
    canvas.paste(pages[0], (10, 50))
    canvas.paste(pages[1], (670, 50))
    draw = ImageDraw.Draw(canvas)
    font = bridge._font(20, bold=True)
    draw.text((10, 23), "PAGE 1 · CODEX + CLAUDE CODE", font=font, fill="#52D8FF", anchor="lm")
    draw.text((670, 23), "PAGE 2 · KIMI CODE + DEEPSEEK", font=font, fill="#F5F5F2", anchor="lm")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT, format="PNG", optimize=True)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
