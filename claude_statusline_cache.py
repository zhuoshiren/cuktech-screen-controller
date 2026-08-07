#!/usr/bin/env python3
"""Cache only the rate-limit fields supplied to Claude Code's status line.

The program has no network code and prints nothing, so it can be called as a
side effect from an existing status-line script without changing its UI.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


DEFAULT_CACHE = Path(__file__).resolve().parent / "artifacts/claude-code-statusline-cache.json"


def _percentage(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 100.0 else None


def _epoch(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        epoch = int(value)
    except (TypeError, ValueError):
        return None
    return epoch if epoch > 0 else None


def sanitized_quota(data: dict[str, Any]) -> dict[str, Any] | None:
    limits = data.get("rate_limits")
    if not isinstance(limits, dict):
        return None
    five = limits.get("five_hour") if isinstance(limits.get("five_hour"), dict) else {}
    seven = limits.get("seven_day") if isinstance(limits.get("seven_day"), dict) else {}
    five_used = _percentage(five.get("used_percentage"))
    seven_used = _percentage(seven.get("used_percentage"))
    if five_used is None and seven_used is None:
        return None
    return {
        "cached_at": time.time(),
        "provider": "CLAUDE",
        "used_percent": five_used,
        "resets_at": _epoch(five.get("resets_at")),
        "weekly_used_percent": seven_used,
        "weekly_resets_at": _epoch(seven.get("resets_at")),
        "plan": "max",
        "source": "Claude Code official statusLine",
    }


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(raw, dict):
        return 0
    payload = sanitized_quota(raw)
    if payload is not None:
        cache = Path(os.environ.get("CUKTECH_CLAUDE_STATUSLINE_CACHE", DEFAULT_CACHE))
        write_atomic(cache, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
