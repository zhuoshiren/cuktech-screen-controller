#!/usr/bin/env python3
"""Serve AP01 dashboards for Codex, Claude, Kimi and DeepSeek.

Credentials stay in their providers' local stores.  Rendered JSON contains only
usage numbers, reset times and provider availability; tokens and API keys are
never persisted to project artifacts or returned over the LAN.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import struct
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw

from codex_plan_bridge import (
    AP01_GIF_MAX_BYTES,
    BACKGROUND,
    HEIGHT,
    MASTER_SCALE,
    WIDTH,
    Quota as CodexQuota,
    _cjk_font,
    _fit_frame,
    _font,
    fetch_codex,
    render_master as render_codex_master,
)
from quota_dashboard import Quota as ClaudeQuota


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
GIF = ARTIFACTS / "coding-balances.gif"
GIF_MAIN = ARTIFACTS / "coding-balances-codex-claude.gif"
GIF_OTHERS = ARTIFACTS / "coding-balances-kimi-deepseek.gif"
BUNDLE = ARTIFACTS / "coding-balances.ap2b"
PNG = ARTIFACTS / "coding-balances.png"
JSON_OUT = ARTIFACTS / "coding-balances.json"
PAGE_MAIN = ARTIFACTS / "coding-balances-codex-claude@2x.png"
PAGE_OTHERS = ARTIFACTS / "coding-balances-kimi-deepseek@2x.png"
CLAUDE_CACHE = ARTIFACTS / "claude-code-statusline-cache.json"

KIMI_TOKEN = Path.home() / ".kimi-code/credentials/kimi-code.json"
KIMI_OAUTH_URL = "https://auth.kimi.com/api/oauth/token"
KIMI_USAGE_URL = "https://api.kimi.com/coding/v1/usages"
KIMI_CLIENT_ID = "17e5f671-d194-4dfb-9706-5516cb48c098"
DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
DEEPSEEK_KEYCHAIN_SERVICE = "com.wqytommy.CUKTECHScreenController.deepseek-api-key"
DEEPSEEK_KEYCHAIN_ACCOUNT = "api"
PRIVATE_LAN_NETWORKS = tuple(
    ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


@dataclass
class KimiUsage:
    weekly_used: int
    weekly_limit: int
    weekly_resets_at: str | None
    five_hour_used: int | None
    five_hour_limit: int | None
    five_hour_resets_at: str | None
    extra_balance: float | None
    extra_currency: str | None
    plan: str | None = None
    source: str = "Kimi Code / api.kimi.com"

    @property
    def weekly_remaining_percent(self) -> float | None:
        return _remaining_percent(self.weekly_used, self.weekly_limit)

    @property
    def five_hour_remaining_percent(self) -> float | None:
        return _remaining_percent(self.five_hour_used, self.five_hour_limit)


@dataclass
class DeepSeekBalance:
    available: bool
    total_balance: float
    granted_balance: float
    topped_up_balance: float
    currency: str
    source: str = "DeepSeek / api.deepseek.com"


@dataclass
class Snapshot:
    codex: CodexQuota | None
    claude: ClaudeQuota | None
    kimi: KimiUsage | None
    deepseek: DeepSeekBalance | None
    errors: dict[str, str]
    generated_at: datetime


class RuntimeState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_refresh: float | None = None
        self.last_attempt: float | None = None
        self.refreshing = False
        self.error: str | None = None
        self.status = "starting"


STATE = RuntimeState()


def _remaining_percent(used: int | None, limit: int | None) -> float | None:
    if used is None or limit is None or limit <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (limit - used) / limit))


def _short_error(error: Exception) -> str:
    if isinstance(error, requests.HTTPError):
        status = error.response.status_code if error.response is not None else "unknown"
        return f"provider HTTP {status}"
    if isinstance(error, requests.RequestException):
        return "provider network request failed"
    message = str(error).strip().replace("\n", " ")
    home = str(Path.home())
    if home:
        message = message.replace(home, "[HOME]")
    message = re.sub(r"https?://\S+", "[URL]", message)
    message = re.sub(
        r"(?i)(?:bearer\s+|sk-|gh[pousr]_|github_pat_)[A-Za-z0-9._=-]{8,}",
        "[REDACTED]",
        message,
    )
    return message[:180] or type(error).__name__


def _iso_reset(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _atomic_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        os.chmod(temporary, mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _claude_cache() -> ClaudeQuota | None:
    if not CLAUDE_CACHE.exists():
        return None
    try:
        payload = json.loads(CLAUDE_CACHE.read_text(encoding="utf-8"))
        cached_at = float(payload.pop("cached_at"))
        allowed = {field.name for field in fields(ClaudeQuota)}
        return ClaudeQuota(**{key: value for key, value in payload.items() if key in allowed})
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def fetch_claude() -> ClaudeQuota:
    """Read only the event-driven data Claude Code gives its status line.

    This function deliberately never launches Claude, opens a browser session,
    reads cookies, or performs a network request.  The cache is refreshed only
    when the user's existing official Claude Code status line runs.
    """

    cached = _claude_cache()
    if cached is not None:
        return cached
    raise RuntimeError("等待 Claude Code 官方 statusLine 首次提供额度数据")


def _refresh_kimi_token(token: dict[str, Any]) -> dict[str, Any]:
    refresh_token = str(token.get("refresh_token") or "")
    if not refresh_token:
        raise RuntimeError("Kimi Code 登录已失效，请重新运行 /login")
    response = requests.post(
        KIMI_OAUTH_URL,
        data={
            "client_id": KIMI_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    access_token = str(payload.get("access_token") or "")
    new_refresh = str(payload.get("refresh_token") or "")
    expires_in = int(payload.get("expires_in") or 0)
    if not access_token or not new_refresh or expires_in <= 0:
        raise RuntimeError("Kimi OAuth 刷新响应不完整")
    updated = {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "expires_at": int(time.time()) + expires_in,
        "scope": str(payload.get("scope") or ""),
        "token_type": str(payload.get("token_type") or "Bearer"),
        "expires_in": expires_in,
    }
    _atomic_json(KIMI_TOKEN, updated)
    return updated


def _kimi_token() -> str:
    if not KIMI_TOKEN.exists():
        raise RuntimeError("Kimi Code 尚未登录")
    token = json.loads(KIMI_TOKEN.read_text(encoding="utf-8"))
    if int(token.get("expires_at") or 0) <= int(time.time()) + 60:
        token = _refresh_kimi_token(token)
    access_token = str(token.get("access_token") or "")
    if not access_token:
        raise RuntimeError("Kimi Code OAuth 凭据缺少 access_token")
    return access_token


def _window_is_five_hours(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    duration = int(raw.get("duration") or 0)
    unit = str(raw.get("timeUnit") or "")
    return (unit == "TIME_UNIT_MINUTE" and duration == 300) or (
        unit == "TIME_UNIT_HOUR" and duration == 5
    )


def _booster_balance(raw: Any) -> tuple[float | None, str | None]:
    if not isinstance(raw, dict):
        return None, None
    balance = raw.get("balance")
    if not isinstance(balance, dict) or balance.get("type") != "BOOSTER":
        return None, None
    amount_left = balance.get("amountLeft")
    if amount_left is None:
        return None, None
    try:
        cents = int(amount_left) / 1_000_000
    except (TypeError, ValueError):
        return None, None
    money = raw.get("monthlyChargeLimit") or raw.get("monthlyUsed") or {}
    currency = str(money.get("currency") or "CNY") if isinstance(money, dict) else "CNY"
    return cents / 100.0, currency


def parse_kimi_usage(payload: dict[str, Any]) -> KimiUsage:
    summary = payload.get("usage")
    if not isinstance(summary, dict):
        raise RuntimeError("Kimi 用量响应缺少周额度")
    try:
        weekly_used = int(summary.get("used") or 0)
        weekly_limit = int(summary.get("limit") or 0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Kimi 周额度格式无效") from exc
    five_detail: dict[str, Any] | None = None
    for item in payload.get("limits") or []:
        if isinstance(item, dict) and _window_is_five_hours(item.get("window")):
            detail = item.get("detail")
            five_detail = detail if isinstance(detail, dict) else None
            break
    extra_balance, extra_currency = _booster_balance(payload.get("boosterWallet"))
    user = payload.get("user")
    membership = user.get("membership") if isinstance(user, dict) else None
    membership_level = membership.get("level") if isinstance(membership, dict) else None
    # Kimi returns an internal membership level rather than the public plan
    # label.  This account's LEVEL_ADVANCED tier is confirmed as Allegro in
    # the signed-in membership UI.
    plan = "Allegro" if membership_level == "LEVEL_ADVANCED" else None
    return KimiUsage(
        weekly_used=weekly_used,
        weekly_limit=weekly_limit,
        weekly_resets_at=_iso_reset(summary.get("resetTime")),
        five_hour_used=int(five_detail.get("used") or 0) if five_detail else None,
        five_hour_limit=int(five_detail.get("limit") or 0) if five_detail else None,
        five_hour_resets_at=_iso_reset(five_detail.get("resetTime")) if five_detail else None,
        extra_balance=extra_balance,
        extra_currency=extra_currency,
        plan=plan,
    )


def fetch_kimi() -> KimiUsage:
    response = requests.get(
        KIMI_USAGE_URL,
        headers={"Authorization": f"Bearer {_kimi_token()}", "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    return parse_kimi_usage(response.json())


def _keychain_secret(service: str, account: str, missing_message: str) -> str:
    completed = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            service,
            "-a",
            account,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    secret = completed.stdout.strip()
    if completed.returncode != 0 or not secret:
        raise RuntimeError(missing_message)
    return secret


def _deepseek_key() -> str:
    environment = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if environment:
        return environment
    return _keychain_secret(
        DEEPSEEK_KEYCHAIN_SERVICE,
        DEEPSEEK_KEYCHAIN_ACCOUNT,
        "DeepSeek API Key 尚未保存在钥匙串",
    )


def parse_deepseek_balance(payload: dict[str, Any]) -> DeepSeekBalance:
    rows = payload.get("balance_infos")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("DeepSeek 余额响应为空")
    row = next(
        (item for item in rows if isinstance(item, dict) and item.get("currency") == "CNY"),
        rows[0],
    )
    if not isinstance(row, dict):
        raise RuntimeError("DeepSeek 余额格式无效")
    return DeepSeekBalance(
        available=bool(payload.get("is_available")),
        total_balance=float(row.get("total_balance") or 0),
        granted_balance=float(row.get("granted_balance") or 0),
        topped_up_balance=float(row.get("topped_up_balance") or 0),
        currency=str(row.get("currency") or "CNY"),
    )


def fetch_deepseek() -> DeepSeekBalance:
    response = requests.get(
        DEEPSEEK_BALANCE_URL,
        headers={"Authorization": f"Bearer {_deepseek_key()}", "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    return parse_deepseek_balance(response.json())


def collect_snapshot() -> Snapshot:
    collectors: dict[str, Callable[[], Any]] = {
        "codex": fetch_codex,
        "claude": fetch_claude,
        "kimi": fetch_kimi,
        "deepseek": fetch_deepseek,
    }
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="balance") as pool:
        futures = {pool.submit(function): name for name, function in collectors.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                values[name] = future.result()
            except Exception as exc:
                errors[name] = _short_error(exc)
    return Snapshot(
        codex=values.get("codex"),
        claude=values.get("claude"),
        kimi=values.get("kimi"),
        deepseek=values.get("deepseek"),
        errors=errors,
        generated_at=datetime.now().astimezone(),
    )


def _scaled(value: float, scale: int = MASTER_SCALE) -> int:
    return int(round(value * scale))


def _reset_label(value: int | str | None) -> str:
    if value is None:
        return "重置时间未知"
    try:
        when = (
            datetime.fromtimestamp(value).astimezone()
            if isinstance(value, int)
            else datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        )
    except (TypeError, ValueError, OSError):
        return "重置时间未知"
    return when.strftime("%m-%d %H:%M 重置")


def _base_page(title: str, accent: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    s = _scaled
    image = Image.new("RGB", (WIDTH * MASTER_SCALE, HEIGHT * MASTER_SCALE), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (s(15), s(48), s(305), s(229)),
        radius=s(18),
        fill="#050D19",
        outline="#213047",
        width=s(1),
    )
    draw.text((s(26), s(65)), title, font=_font(s(15), bold=True), fill=accent, anchor="lm")
    if subtitle:
        draw.text((s(294), s(65)), subtitle, font=_cjk_font(s(9), bold=True), fill="#8EA1B5", anchor="rm")
    draw.rectangle((0, 0, WIDTH * MASTER_SCALE - 1, s(40) - 1), fill=BACKGROUND)
    return image, draw


def _status_page(title: str, accent: str, headline: str, detail: str) -> Image.Image:
    image, draw = _base_page(title, accent)
    s = _scaled
    draw.text((s(160), s(132)), headline, font=_cjk_font(s(27), bold=True), fill="#F5F8FC", anchor="mm")
    draw.text((s(160), s(173)), detail, font=_cjk_font(s(12), bold=True), fill="#F6A15E", anchor="mm")
    draw.text((s(160), s(207)), "配置后自动刷新", font=_cjk_font(s(9), bold=True), fill="#8193A7", anchor="mm")
    return image


def _remaining_from_used(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(100.0, 100.0 - float(value)))


def render_codex_claude_master(
    codex: CodexQuota | None,
    claude: ClaudeQuota | None,
    *,
    refreshed_at: datetime,
) -> Image.Image:
    """Render Codex Pro and Claude Max as one balanced split-screen page."""

    s = _scaled
    image = Image.new("RGB", (WIDTH * MASTER_SCALE, HEIGHT * MASTER_SCALE), BACKGROUND)
    draw = ImageDraw.Draw(image)
    panels = (
        (10, 156, "#20C8EE", "#04101A", "#153A4C"),
        (164, 310, "#D97757", "#100D0C", "#402A22"),
    )
    for left, right, accent, fill, outline in panels:
        draw.rounded_rectangle(
            (s(left), s(48), s(right), s(229)),
            radius=s(16),
            fill=fill,
            outline=outline,
            width=s(1),
        )
        draw.line((s(left + 18), s(76), s(right - 18), s(76)), fill=accent, width=s(2))

    draw.text((s(23), s(63)), "CODEX", font=_font(s(13), bold=True), fill="#F5F8FC", anchor="lm")
    codex_plan = ((codex.plan if codex is not None else "PRO") or "PRO").upper()
    draw.rounded_rectangle((s(108), s(55), s(146), s(71)), radius=s(8), fill="#062B3A", outline="#168EAA", width=s(1))
    draw.text((s(127), s(63)), codex_plan, font=_font(s(6), bold=True), fill="#39D9F7", anchor="mm")
    if codex is None:
        draw.text((s(83), s(126)), "未连接", font=_cjk_font(s(20), bold=True), fill="#F5F8FC", anchor="mm")
        draw.text((s(83), s(158)), "等待 Codex", font=_cjk_font(s(9), bold=True), fill="#F6A15E", anchor="mm")
        draw.text((s(83), s(181)), "App Server", font=_font(s(9), bold=True), fill="#7790A5", anchor="mm")
    else:
        codex_five = _remaining_from_used(codex.used_percent)
        codex_week = _remaining_from_used(codex.weekly_used_percent)
        draw.text((s(83), s(112)), f"{codex.remaining_percent:.0f}%", font=_font(s(31), bold=True), fill="#F5F8FC", anchor="mm")
        draw.text((s(83), s(136)), "严格额度剩余", font=_cjk_font(s(8), bold=True), fill="#88A2B5", anchor="mm")
        draw.text((s(24), s(165)), "5小时", font=_cjk_font(s(8), bold=True), fill="#71899D", anchor="lm")
        draw.text((s(143), s(165)), "--" if codex_five is None else f"{codex_five:.0f}%", font=_font(s(12), bold=True), fill="#35D4F2", anchor="rm")
        draw.text((s(24), s(190)), "7天", font=_cjk_font(s(8), bold=True), fill="#71899D", anchor="lm")
        draw.text((s(143), s(190)), "--" if codex_week is None else f"{codex_week:.0f}%", font=_font(s(12), bold=True), fill="#D9F8FF", anchor="rm")
        draw.text((s(83), s(214)), _reset_label(codex.weekly_resets_at), font=_cjk_font(s(6), bold=True), fill="#647C90", anchor="mm")

    clay = "#D97757"
    cream = "#F4EEE8"
    draw.text((s(177), s(63)), "CLAUDE", font=_font(s(13), bold=True), fill=cream, anchor="lm")
    claude_plan = ((claude.plan if claude is not None else "MAX") or "MAX").upper()
    draw.rounded_rectangle((s(262), s(55), s(300), s(71)), radius=s(8), fill=clay)
    draw.text((s(281), s(63)), claude_plan, font=_font(s(6), bold=True), fill="#170E0B", anchor="mm")
    if claude is None:
        draw.text((s(237), s(126)), "等待数据", font=_cjk_font(s(19), bold=True), fill=cream, anchor="mm")
        draw.text((s(237), s(158)), "使用一次", font=_cjk_font(s(9), bold=True), fill="#B4A097", anchor="mm")
        draw.text((s(237), s(181)), "Claude Code", font=_font(s(9), bold=True), fill=clay, anchor="mm")
    else:
        claude_five = _remaining_from_used(claude.used_percent)
        claude_week = _remaining_from_used(claude.weekly_used_percent)
        strict_values = [value for value in (claude_five, claude_week) if value is not None]
        claude_strict = min(strict_values) if strict_values else 0.0
        draw.text((s(237), s(112)), f"{claude_strict:.0f}%", font=_font(s(31), bold=True), fill=cream, anchor="mm")
        draw.text((s(237), s(136)), "严格额度剩余", font=_cjk_font(s(8), bold=True), fill="#A89B91", anchor="mm")
        draw.text((s(178), s(165)), "5小时", font=_cjk_font(s(8), bold=True), fill="#8D7A70", anchor="lm")
        draw.text((s(297), s(165)), "--" if claude_five is None else f"{claude_five:.0f}%", font=_font(s(12), bold=True), fill=clay, anchor="rm")
        draw.text((s(178), s(190)), "7天", font=_cjk_font(s(8), bold=True), fill="#8D7A70", anchor="lm")
        draw.text((s(297), s(190)), "--" if claude_week is None else f"{claude_week:.0f}%", font=_font(s(12), bold=True), fill=cream, anchor="rm")
        draw.text((s(237), s(214)), _reset_label(claude.weekly_resets_at), font=_cjk_font(s(6), bold=True), fill="#74675F", anchor="mm")

    draw.text((s(160), s(43)), f"更新 {refreshed_at.astimezone():%H:%M}", font=_cjk_font(s(6), bold=True), fill="#506174", anchor="mm")
    draw.rectangle((0, 0, WIDTH * MASTER_SCALE - 1, s(40) - 1), fill=BACKGROUND)
    return image


def render_claude_master(quota: ClaudeQuota | None, error: str | None = None) -> Image.Image:
    s = _scaled
    clay = "#D97757"
    cream = "#F4EEE8"
    muted = "#A89B91"
    image = Image.new("RGB", (WIDTH * MASTER_SCALE, HEIGHT * MASTER_SCALE), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (s(15), s(48), s(305), s(229)),
        radius=s(18),
        fill="#0F0D0C",
        outline="#3A2A24",
        width=s(1),
    )
    draw.line((s(27), s(81), s(293), s(81)), fill="#35241F", width=s(1))
    draw.text((s(27), s(65)), "CLAUDE CODE", font=_font(s(15), bold=True), fill=cream, anchor="lm")
    if quota is None:
        draw.rounded_rectangle((s(251), s(54), s(294), s(75)), radius=s(10), fill=clay)
        draw.text((s(272.5), s(65)), "MAX", font=_font(s(8), bold=True), fill="#160E0B", anchor="mm")
        draw.arc((s(64), s(101), s(144), s(181)), -90, 269, fill="#3A2A24", width=s(7))
        draw.arc((s(64), s(101), s(144), s(181)), -90, 18, fill=clay, width=s(7))
        draw.text((s(104), s(141)), "…", font=_font(s(27), bold=True), fill=cream, anchor="mm")
        draw.text((s(164), s(120)), "等待首次数据", font=_cjk_font(s(16), bold=True), fill=cream, anchor="lm")
        draw.text((s(164), s(151)), "正常使用一次", font=_cjk_font(s(9), bold=True), fill=muted, anchor="lm")
        draw.text((s(164), s(172)), "Claude Code 即可", font=_cjk_font(s(9), bold=True), fill=clay, anchor="lm")
        draw.text((s(160), s(216)), "OFFICIAL STATUSLINE · LOCAL ONLY", font=_font(s(6), bold=True), fill="#695A52", anchor="mm")
        draw.rectangle((0, 0, WIDTH * MASTER_SCALE - 1, s(40) - 1), fill=BACKGROUND)
        return image
    plan = (quota.plan or "").upper()
    if plan:
        draw.rounded_rectangle((s(251), s(54), s(294), s(75)), radius=s(10), fill=clay)
        draw.text((s(272.5), s(65)), plan, font=_font(s(8), bold=True), fill="#160E0B", anchor="mm")
    five_remaining = 100.0 - float(quota.used_percent or 0.0)
    weekly_remaining = (
        100.0 - float(quota.weekly_used_percent)
        if quota.weekly_used_percent is not None
        else None
    )
    strictest = min(value for value in (five_remaining, weekly_remaining) if value is not None)
    center = (s(91), s(145))
    radius = s(45)
    ring_box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    draw.arc(ring_box, -90, 269, fill="#3A2A24", width=s(8))
    draw.arc(ring_box, -90, -90 + 3.6 * strictest, fill=clay, width=s(8))
    draw.text(center, f"{strictest:.0f}%", font=_font(s(26), bold=True), fill=cream, anchor="mm")
    draw.text((center[0], s(176)), "可用", font=_cjk_font(s(8), bold=True), fill=muted, anchor="mm")

    draw.rounded_rectangle((s(153), s(94), s(291), s(144)), radius=s(11), fill="#171311", outline="#33251F", width=s(1))
    draw.rounded_rectangle((s(153), s(153), s(291), s(203)), radius=s(11), fill="#171311", outline="#33251F", width=s(1))
    draw.text((s(166), s(108)), "5 小时", font=_cjk_font(s(8), bold=True), fill=muted, anchor="lm")
    draw.text((s(279), s(116)), f"{five_remaining:.0f}%", font=_font(s(20), bold=True), fill=clay, anchor="rm")
    draw.text((s(166), s(133)), _reset_label(quota.resets_at), font=_cjk_font(s(6), bold=True), fill="#74675F", anchor="lm")
    draw.text((s(166), s(167)), "7 天", font=_cjk_font(s(8), bold=True), fill=muted, anchor="lm")
    weekly_text = "--" if weekly_remaining is None else f"{weekly_remaining:.0f}%"
    draw.text((s(279), s(175)), weekly_text, font=_font(s(20), bold=True), fill=cream, anchor="rm")
    draw.text((s(166), s(192)), _reset_label(quota.weekly_resets_at), font=_cjk_font(s(6), bold=True), fill="#74675F", anchor="lm")
    draw.text((s(160), s(216)), "OFFICIAL STATUSLINE · LOCAL ONLY", font=_font(s(6), bold=True), fill="#695A52", anchor="mm")
    draw.rectangle((0, 0, WIDTH * MASTER_SCALE - 1, s(40) - 1), fill=BACKGROUND)
    return image


def _money_symbol(currency: str | None) -> str:
    return "¥" if (currency or "").upper() == "CNY" else "$"


def render_others_master(
    kimi: KimiUsage | None,
    deepseek: DeepSeekBalance | None,
    errors: dict[str, str] | None = None,
) -> Image.Image:
    s = _scaled
    image = Image.new("RGB", (WIDTH * MASTER_SCALE, HEIGHT * MASTER_SCALE), BACKGROUND)
    draw = ImageDraw.Draw(image)
    panels = (
        (10, 156, "#F5F5F2", "#050505", "#2A2A2A"),
        (164, 310, "#6495FF", "#071A3C", "#244A82"),
    )
    for left, right, accent, fill, outline in panels:
        draw.rounded_rectangle(
            (s(left), s(48), s(right), s(229)),
            radius=s(16),
            fill=fill,
            outline=outline,
            width=s(1),
        )
        draw.line((s(left + 18), s(76), s(right - 18), s(76)), fill=accent, width=s(2))

    draw.text((s(23), s(63)), "KIMI CODE", font=_font(s(12), bold=True), fill="#F5F5F2", anchor="lm")
    if kimi is not None and kimi.plan:
        draw.rounded_rectangle((s(96), s(55), s(146), s(71)), radius=s(8), outline="#F5F5F2", width=s(1))
        draw.text((s(121), s(63)), kimi.plan.upper(), font=_font(s(5), bold=True), fill="#F5F5F2", anchor="mm")
    if kimi is None:
        draw.text((s(83), s(129)), "待登录", font=_cjk_font(s(21), bold=True), fill="#F5F8FC", anchor="mm")
        draw.text((s(83), s(163)), "运行 Kimi /login", font=_cjk_font(s(9), bold=True), fill="#F6A15E", anchor="mm")
    else:
        weekly = kimi.weekly_remaining_percent
        five = kimi.five_hour_remaining_percent
        draw.text((s(83), s(116)), "--" if weekly is None else f"{weekly:.0f}%", font=_font(s(32), bold=True), fill="#F8FAFC", anchor="mm")
        draw.text((s(83), s(140)), "周额度剩余", font=_cjk_font(s(9), bold=True), fill="#93A6B8", anchor="mm")
        draw.text((s(24), s(165)), "5小时", font=_cjk_font(s(8), bold=True), fill="#71869C", anchor="lm")
        draw.text((s(143), s(165)), "--" if five is None else f"{five:.0f}%", font=_font(s(12), bold=True), fill="#F5F5F2", anchor="rm")
        extra = "未启用" if kimi.extra_balance is None else f"{_money_symbol(kimi.extra_currency)}{kimi.extra_balance:.2f}"
        draw.text((s(24), s(190)), "Extra", font=_font(s(8), bold=True), fill="#71869C", anchor="lm")
        extra_font = _cjk_font(s(11), bold=True) if kimi.extra_balance is None else _font(s(11), bold=True)
        draw.text((s(143), s(190)), extra, font=extra_font, fill="#C7D6E5", anchor="rm")
        draw.text((s(83), s(214)), _reset_label(kimi.weekly_resets_at), font=_cjk_font(s(7), bold=True), fill="#71869C", anchor="mm")

    draw.text((s(177), s(63)), "DEEPSEEK", font=_font(s(12), bold=True), fill="#74A7FF", anchor="lm")
    if deepseek is None:
        draw.text((s(237), s(129)), "待配置", font=_cjk_font(s(21), bold=True), fill="#F5F8FC", anchor="mm")
        draw.text((s(237), s(163)), "需要 API Key", font=_cjk_font(s(9), bold=True), fill="#F6A15E", anchor="mm")
    else:
        symbol = _money_symbol(deepseek.currency)
        draw.text((s(237), s(116)), f"{symbol}{deepseek.total_balance:.2f}", font=_font(s(25), bold=True), fill="#F8FAFC", anchor="mm")
        draw.text((s(237), s(140)), "账户余额", font=_cjk_font(s(9), bold=True), fill="#93A6B8", anchor="mm")
        draw.text((s(178), s(165)), "赠送", font=_cjk_font(s(8), bold=True), fill="#71869C", anchor="lm")
        draw.text((s(297), s(165)), f"{symbol}{deepseek.granted_balance:.2f}", font=_font(s(11), bold=True), fill="#74A7FF", anchor="rm")
        draw.text((s(178), s(190)), "充值", font=_cjk_font(s(8), bold=True), fill="#71869C", anchor="lm")
        draw.text((s(297), s(190)), f"{symbol}{deepseek.topped_up_balance:.2f}", font=_font(s(11), bold=True), fill="#C7D6E5", anchor="rm")
        availability = "API 可用" if deepseek.available else "余额不足"
        draw.text((s(237), s(214)), availability, font=_cjk_font(s(8), bold=True), fill="#30D29A" if deepseek.available else "#F6A15E", anchor="mm")
    draw.rectangle((0, 0, WIDTH * MASTER_SCALE - 1, s(40) - 1), fill=BACKGROUND)
    return image



def _snapshot_document(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "schema": 1,
        "generated_at": snapshot.generated_at.isoformat(timespec="seconds"),
        "codex": None if snapshot.codex is None else asdict(snapshot.codex) | {"remaining_percent": snapshot.codex.remaining_percent},
        "claude": None if snapshot.claude is None else asdict(snapshot.claude) | {"remaining_percent": snapshot.claude.remaining_percent},
        "kimi": None if snapshot.kimi is None else asdict(snapshot.kimi) | {
            "weekly_remaining_percent": snapshot.kimi.weekly_remaining_percent,
            "five_hour_remaining_percent": snapshot.kimi.five_hour_remaining_percent,
        },
        "deepseek": None if snapshot.deepseek is None else asdict(snapshot.deepseek),
        "errors": snapshot.errors,
    }


def _previous_value(name: str, value_type: type[Any]) -> Any | None:
    if not JSON_OUT.is_file():
        return None
    try:
        payload = json.loads(JSON_OUT.read_text(encoding="utf-8"))
        raw = payload.get(name)
        if not isinstance(raw, dict):
            return None
        allowed = {field.name for field in fields(value_type)}
        return value_type(**{key: value for key, value in raw.items() if key in allowed})
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def retain_previous_values(snapshot: Snapshot) -> Snapshot:
    """Keep the last successful provider value through a temporary outage."""

    value_types: dict[str, type[Any]] = {
        "codex": CodexQuota,
        "claude": ClaudeQuota,
        "kimi": KimiUsage,
        "deepseek": DeepSeekBalance,
    }
    for name, value_type in value_types.items():
        if getattr(snapshot, name) is not None:
            continue
        previous = _previous_value(name, value_type)
        if name == "claude" and previous is not None and not previous.source.startswith(
            "Claude Code official statusLine"
        ):
            previous = None
        if previous is not None:
            setattr(snapshot, name, previous)
            snapshot.errors[name] = f"{snapshot.errors.get(name, '暂时无法刷新')}（显示上次成功数据）"
    return snapshot


def _save_page_gif(frame: Image.Image, path: Path) -> None:
    """Save an AP01-safe page that never changes its displayed content."""

    palette = frame.quantize(colors=40, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pulse = frame.copy()
    pulse.putpixel((WIDTH - 1, HEIGHT - 1), (255, 255, 255))
    pulse = pulse.quantize(palette=palette, dither=Image.Dither.NONE)
    palette.save(
        path,
        format="GIF",
        save_all=True,
        append_images=[pulse],
        duration=[60_000, 60_000],
        disposal=2,
        loop=0,
        optimize=False,
    )
    if path.stat().st_size > AP01_GIF_MAX_BYTES:
        raise RuntimeError(f"AP01 page GIF exceeds limit: {path.name} {path.stat().st_size} bytes")
    if path.read_bytes()[:6] != b"GIF89a":
        raise RuntimeError(f"AP01 page is not GIF89a: {path.name}")


def _write_page_bundle(path: Path, page_paths: tuple[Path, Path]) -> None:
    """Write the two logical GIF pages into one AP2B HTTP payload."""

    pages = tuple(page.read_bytes() for page in page_paths)
    sizes = tuple(len(page) for page in pages)
    magic = 0x42325041  # "AP2B" as little-endian u32
    version = 1
    check = magic ^ version ^ sizes[0] ^ sizes[1] ^ 0xA50102B2
    header = struct.pack("<5I", magic, version, *sizes, check)
    path.write_bytes(header + b"".join(pages))


def render_snapshot(snapshot: Snapshot, *, persistent_display: bool = False) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    main_master = render_codex_claude_master(
        snapshot.codex,
        snapshot.claude,
        refreshed_at=snapshot.generated_at,
    )
    others_master = render_others_master(snapshot.kimi, snapshot.deepseek, snapshot.errors)
    pages = [_fit_frame(page) for page in (main_master, others_master)]
    pages[0].save(PNG, format="PNG", optimize=True)
    _fit_frame(main_master, 2).save(PAGE_MAIN, format="PNG", optimize=True)
    _fit_frame(others_master, 2).save(PAGE_OTHERS, format="PNG", optimize=True)

    _save_page_gif(pages[0], GIF_MAIN)
    _save_page_gif(pages[1], GIF_OTHERS)
    _write_page_bundle(BUNDLE, (GIF_MAIN, GIF_OTHERS))
    # Compatibility endpoint for the already-installed one-page loader.  It
    # shows the combined Codex+Claude page while the two-page firmware is built
    # and reviewed offline.
    GIF.write_bytes(GIF_MAIN.read_bytes())
    _atomic_json(JSON_OUT, _snapshot_document(snapshot), mode=0o600)
    for path in (PNG, PAGE_MAIN, PAGE_OTHERS, GIF, GIF_MAIN, GIF_OTHERS, BUNDLE):
        os.chmod(path, 0o600)


def refresh(*, persistent_display: bool = False) -> dict[str, Any]:
    with STATE.lock:
        STATE.last_attempt = time.time()
        STATE.refreshing = True
    try:
        snapshot = collect_snapshot()
        if persistent_display:
            snapshot = retain_previous_values(snapshot)
        render_snapshot(snapshot, persistent_display=persistent_display)
        document = _snapshot_document(snapshot)
        with STATE.lock:
            STATE.last_refresh = time.time()
            STATE.error = None
            STATE.status = "live" if snapshot.codex is not None else "partial"
        return document
    except Exception as exc:
        with STATE.lock:
            STATE.error = _short_error(exc)
            STATE.status = "error"
        raise
    finally:
        with STATE.lock:
            STATE.refreshing = False


def _local_ipv4() -> set[str]:
    addresses = {"127.0.0.1", "::1"}
    try:
        addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return addresses


class BalanceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], allowed_clients: set[str]):
        super().__init__(address, BalanceHandler)
        self.allowed_clients = allowed_clients
        self.local_addresses = _local_ipv4()


class BalanceHandler(BaseHTTPRequestHandler):
    server_version = "AP01CodingBalancesBridge/0.1"

    def _allowed(self) -> bool:
        client = self.client_address[0]
        server = self.server
        assert isinstance(server, BalanceServer)
        return client in server.allowed_clients or client in server.local_addresses

    def _send_file(self, path: Path, content_type: str, *, head_only: bool = False) -> None:
        if not self._allowed():
            self.send_error(403)
            return
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("ETag", f'"{hashlib.sha256(payload).hexdigest()}"')
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)

    def _health(self) -> dict[str, Any]:
        with STATE.lock:
            age = None if STATE.last_refresh is None else round(time.time() - STATE.last_refresh, 1)
            return {
                "ok": STATE.status in {"live", "partial"},
                "status": STATE.status,
                "last_refresh": STATE.last_refresh,
                "last_attempt": STATE.last_attempt,
                "age_seconds": age,
                "error": STATE.error,
                "refreshing": STATE.refreshing,
                "snapshot_ready": GIF.exists(),
                "mode": "coding-balances",
            }

    def _handle(self, *, head_only: bool = False) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            if not self._allowed():
                self.send_error(403)
                return
            payload = json.dumps(self._health(), separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if not head_only:
                self.wfile.write(payload)
            return
        if path in {"/screen.gif", "/screen/codex.gif", "/screen/claude.gif", "/screen/codex-claude.gif"}:
            self._send_file(GIF, "image/gif", head_only=head_only)
            return
        if path in {"/screen/kimi-deepseek.gif", "/screen/others.gif"}:
            self._send_file(GIF_OTHERS, "image/gif", head_only=head_only)
            return
        if path == "/screen.ap2b":
            self._send_file(BUNDLE, "application/octet-stream", head_only=head_only)
            return
        if path == "/screen.png":
            self._send_file(PNG, "image/png", head_only=head_only)
            return
        if path == "/api/v1/balances":
            if self.client_address[0] not in {"127.0.0.1", "::1"}:
                self.send_error(403)
                return
            self._send_file(JSON_OUT, "application/json", head_only=head_only)
            return
        self.send_error(404)

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle(head_only=True)

    def log_message(self, fmt: str, *args: Any) -> None:
        try:
            label = "local" if ipaddress.ip_address(self.client_address[0]).is_loopback else "allowed-client"
        except ValueError:
            label = "allowed-client"
        status = str(args[1]) if len(args) > 1 else "unknown"
        print(f"[{self.log_date_time_string()}] {label} HTTP {status}", flush=True)


def _validated_allowed_clients(values: list[str]) -> set[str]:
    allowed: set[str] = set()
    for value in values:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as error:
            raise ValueError(f"invalid --allow-client address {value!r}") from error
        if (
            address.version != 4
            or not any(address in network for network in PRIVATE_LAN_NETWORKS)
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValueError("--allow-client must be a private AP01 IPv4 address")
        allowed.add(str(address))
    return allowed


def _refresh_loop(interval: int, persistent_display: bool) -> None:
    while True:
        time.sleep(interval)
        try:
            refresh(persistent_display=persistent_display)
        except Exception as exc:
            print(f"balance refresh failed: {_short_error(exc)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--allow-client", action="append", default=[])
    parser.add_argument(
        "--persistent-display",
        action="store_true",
        help="keep live pages looping forever instead of using the offline fallback frame",
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.bind not in {"127.0.0.1", "::1", "localhost"} and not args.allow_client:
        parser.error("LAN binding requires at least one --allow-client AP01_IP")
    try:
        allowed_clients = _validated_allowed_clients(args.allow_client)
    except ValueError as error:
        parser.error(str(error))
    document = refresh(persistent_display=args.persistent_display)
    if args.once:
        print(json.dumps(document, ensure_ascii=False, indent=2))
        return 0
    thread = threading.Thread(
        target=_refresh_loop,
        args=(max(30, args.interval), args.persistent_display),
        daemon=True,
    )
    thread.start()
    server = BalanceServer((args.bind, args.port), allowed_clients)
    print(f"AP01 coding balances: LAN bridge active on TCP {args.port}", flush=True)
    if args.allow_client:
        print(f"AP01 allow-list active: {len(allowed_clients)} device(s)", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
