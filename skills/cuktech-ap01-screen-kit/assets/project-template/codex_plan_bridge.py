#!/usr/bin/env python3
"""Render and serve a Codex-only AP01 plan balance over the local LAN.

The collector talks only to the signed-in official ``codex app-server``. It
does not inspect Claude Desktop, browser cookies, or Xiaomi credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw

from ap01_wifi_bridge import lan_ip
from quota_dashboard import (
    AP01_GIF_MAX_BYTES,
    HEIGHT,
    MASTER_SCALE,
    PREVIEW_SCALE,
    WIDTH,
    Quota,
    _cjk_font,
    _condensed_font,
    _font,
    fetch_codex,
)


HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
PNG = ARTIFACTS / "codex-plan.png"
GIF = ARTIFACTS / "codex-plan.gif"
MASTER = ARTIFACTS / "codex-plan-master.png"
PREVIEW = ARTIFACTS / "codex-plan@2x.png"
JSON_OUT = ARTIFACTS / "codex-plan.json"
BACKGROUND = "#01040B"
ALLOWED_CLIENTS: set[str] = {"127.0.0.1", "::1"}
PRIVATE_LAN_NETWORKS = tuple(
    ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_refresh: float | None = None
        self.last_attempt: float | None = None
        self.error: str | None = None
        self.refreshing = False
        self.status = "starting"
        self.stale_after = 420
        self.persistent_display = False


STATE = State()


def _safe_error(error: Exception) -> str:
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


def _write_private_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _remaining(used: float | None) -> float | None:
    if used is None:
        return None
    return max(0.0, min(100.0, 100.0 - float(used)))


def _reset_label(timestamp: int | None) -> str:
    if not timestamp:
        return "等待启用"
    return datetime.fromtimestamp(timestamp).astimezone().strftime("%m/%d %H:%M")


def _fit_frame(master: Image.Image, scale: int = 1) -> Image.Image:
    target = (WIDTH * scale, HEIGHT * scale)
    return master.resize(target, Image.Resampling.LANCZOS)


def render_master(
    quota: Quota,
    *,
    refreshed_at: datetime | None = None,
    phase: float = 0.0,
    scale: int = MASTER_SCALE,
) -> Image.Image:
    """Render the Codex-only 320x240 design at a supersampled resolution."""

    if scale < 1:
        raise ValueError("scale must be at least 1")
    refreshed_at = (refreshed_at or datetime.now().astimezone()).astimezone()

    def s(value: float) -> int:
        return int(round(value * scale))

    cyan = "#20C8EE"
    cyan_soft = "#0D91B3"
    text = "#F5F8FC"
    muted = "#8291A6"
    panel = "#050D19"
    track = "#1B2A3D"
    master = Image.new("RGB", (WIDTH * scale, HEIGHT * scale), BACKGROUND)
    draw = ImageDraw.Draw(master)

    draw.rounded_rectangle(
        (s(8), s(42), s(312), s(234)),
        radius=s(17),
        fill=panel,
        outline="#17334A",
        width=max(1, s(1)),
    )
    draw.rounded_rectangle(
        (s(8), s(64), s(11), s(212)),
        radius=s(2),
        fill=cyan,
    )

    draw.ellipse((s(21), s(51), s(29), s(59)), fill=cyan)
    draw.text((s(35), s(55)), "CODEX", font=_font(s(18), bold=True), fill=text, anchor="lm")
    plan = (quota.plan or "PLAN").upper()
    plan_width = max(42, 16 + len(plan) * 8)
    draw.rounded_rectangle(
        (s(116), s(47), s(116 + plan_width), s(64)),
        radius=s(8),
        fill="#062433",
        outline=cyan_soft,
        width=max(1, s(1)),
    )
    draw.text(
        (s(116 + plan_width / 2), s(55.5)),
        plan,
        font=_font(s(9), bold=True),
        fill=cyan,
        anchor="mm",
    )
    draw.text(
        (s(302), s(55)),
        f"更新 {refreshed_at:%H:%M}",
        font=_cjk_font(s(9), bold=True),
        fill=muted,
        anchor="rm",
    )

    remaining = quota.remaining_percent
    ring = (s(25), s(76), s(159), s(210))
    draw.arc(ring, 0, 359, fill=track, width=s(10))
    draw.arc(
        ring,
        -90,
        -90 + max(0.0, min(100.0, remaining)) * 3.6,
        fill=cyan,
        width=s(10),
    )
    glow = int(round(3 + phase * 3))
    draw.ellipse(
        (s(89 - glow), s(76 - glow), s(89 + glow), s(76 + glow)),
        fill="#75E9FF",
    )
    draw.text(
        (s(92), s(132)),
        f"{remaining:.0f}",
        font=_condensed_font(s(47)),
        fill=text,
        anchor="mm",
    )
    draw.text((s(129), s(141)), "%", font=_font(s(14), bold=True), fill=cyan, anchor="mm")
    draw.text(
        (s(92), s(169)),
        "剩余额度",
        font=_cjk_font(s(12), bold=True),
        fill=muted,
        anchor="mm",
    )

    draw.line((s(171), s(80), s(171), s(213)), fill="#183047", width=max(1, s(1)))
    session_remaining = _remaining(quota.used_percent)
    weekly_remaining = _remaining(quota.weekly_used_percent)

    draw.text((s(187), s(88)), "本周", font=_cjk_font(s(11), bold=True), fill=muted)
    draw.text(
        (s(302), s(88)),
        "--" if weekly_remaining is None else f"{weekly_remaining:.0f}% 余",
        font=_cjk_font(s(17), bold=True),
        fill=text,
        anchor="ra",
    )
    draw.text(
        (s(187), s(116)),
        f"重置  {_reset_label(quota.weekly_resets_at)}",
        font=_cjk_font(s(10), bold=True),
        fill="#9EBDD0",
    )

    draw.rounded_rectangle(
        (s(183), s(134), s(302), s(192)),
        radius=s(11),
        fill="#071523",
        outline="#15374D",
        width=max(1, s(1)),
    )
    draw.text((s(194), s(148)), "5 小时窗口", font=_cjk_font(s(10), bold=True), fill=muted)
    if session_remaining is None:
        session_value = "当前未启用"
        session_fill = "#A8B3C4"
    else:
        session_value = f"{session_remaining:.0f}% 剩余"
        session_fill = cyan
    draw.text(
        (s(194), s(169)),
        session_value,
        font=_cjk_font(s(15), bold=True),
        fill=session_fill,
        anchor="lm",
    )
    if quota.resets_at:
        draw.text(
            (s(194), s(184)),
            f"重置 {_reset_label(quota.resets_at)}",
            font=_cjk_font(s(8), bold=True),
            fill=muted,
            anchor="lm",
        )

    draw.ellipse((s(187), s(207), s(195), s(215)), fill="#28D597")
    draw.text(
        (s(201), s(211)),
        "官方 Codex App Server",
        font=_cjk_font(s(9), bold=True),
        fill="#9BB0C2",
        anchor="lm",
    )

    # AP01 draws its stock clock/date over this band.
    draw.rectangle((0, 0, WIDTH * scale - 1, s(40) - 1), fill=BACKGROUND)
    return master


def render_disconnected_master(
    *, last_success_at: datetime | None = None, scale: int = MASTER_SCALE
) -> Image.Image:
    def s(value: float) -> int:
        return int(round(value * scale))

    master = Image.new("RGB", (WIDTH * scale, HEIGHT * scale), BACKGROUND)
    draw = ImageDraw.Draw(master)
    draw.rounded_rectangle(
        (s(18), s(51), s(302), s(228)),
        radius=s(18),
        fill="#050D19",
        outline="#213047",
        width=max(1, s(1)),
    )
    draw.text((s(160), s(103)), "CODEX", font=_font(s(20), bold=True), fill="#20C8EE", anchor="mm")
    draw.text((s(160), s(143)), "未连接", font=_cjk_font(s(32), bold=True), fill="#F5F8FC", anchor="mm")
    draw.text((s(160), s(174)), "请连接", font=_cjk_font(s(18), bold=True), fill="#F6A15E", anchor="mm")
    footer = (
        "等待首次成功刷新"
        if last_success_at is None
        else f"最后成功 {last_success_at.astimezone():%m-%d %H:%M}"
    )
    draw.text((s(160), s(207)), footer, font=_cjk_font(s(9), bold=True), fill="#91A0B4", anchor="mm")
    draw.rectangle((0, 0, WIDTH * scale - 1, s(40) - 1), fill=BACKGROUND)
    return master


def render_outputs(
    quota: Quota,
    *,
    refreshed_at: datetime | None = None,
    persistent_display: bool = False,
) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    refreshed_at = (refreshed_at or datetime.now().astimezone()).astimezone()
    master = render_master(quota, refreshed_at=refreshed_at)
    frame = _fit_frame(master)
    master.save(MASTER, format="PNG", optimize=True)
    frame.save(PNG, format="PNG", optimize=True)
    _fit_frame(master, PREVIEW_SCALE).save(PREVIEW, format="PNG", optimize=True)

    disconnected = (
        None
        if persistent_display
        else _fit_frame(render_disconnected_master(last_success_at=refreshed_at))
    )
    palette_source = Image.new(
        "RGB", (WIDTH * (1 if disconnected is None else 2), HEIGHT), BACKGROUND
    )
    palette_source.paste(frame, (0, 0))
    if disconnected is not None:
        palette_source.paste(disconnected, (WIDTH, 0))
    for colors in (80, 64, 56, 48):
        shared_palette = palette_source.quantize(
            colors=colors,
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.NONE,
        )
        live_frames = [
            _fit_frame(render_master(quota, refreshed_at=refreshed_at, phase=phase)).quantize(
                palette=shared_palette, dither=Image.Dither.NONE
            )
            for phase in (0.0, 0.45, 1.0, 0.45)
        ]
        live_frames.append(frame.quantize(palette=shared_palette, dither=Image.Dither.NONE))
        if disconnected is not None:
            live_frames.append(
                disconnected.quantize(palette=shared_palette, dither=Image.Dither.NONE)
            )
        durations = (
            [600, 600, 600, 600, 417_600]
            if persistent_display
            else [600, 600, 600, 600, 417_600, 60_000]
        )
        save_options: dict[str, int] = {"loop": 0} if persistent_display else {}
        live_frames[0].save(
            GIF,
            format="GIF",
            save_all=True,
            append_images=live_frames[1:],
            duration=durations,
            disposal=2,
            optimize=False,
            **save_options,
        )
        if GIF.stat().st_size <= min(AP01_GIF_MAX_BYTES, 90_000):
            break
    else:
        raise RuntimeError(f"Codex GIF exceeds AP01 target: {GIF.stat().st_size} bytes")
    if GIF.read_bytes()[:6] != b"GIF89a":
        raise RuntimeError("Codex balance asset is not GIF89a")
    for path in (PNG, GIF, MASTER, PREVIEW):
        os.chmod(path, 0o600)


def render_disconnected_outputs(*, last_success_at: datetime | None = None) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    master = render_disconnected_master(last_success_at=last_success_at)
    frame = _fit_frame(master)
    master.save(MASTER, format="PNG", optimize=True)
    frame.save(PNG, format="PNG", optimize=True)
    _fit_frame(master, PREVIEW_SCALE).save(PREVIEW, format="PNG", optimize=True)
    palette = frame.quantize(colors=40, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    frames = [palette.copy(), palette.copy()]
    frames[0].save(
        GIF,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=1200,
        disposal=2,
        optimize=False,
    )
    for path in (PNG, GIF, MASTER, PREVIEW):
        os.chmod(path, 0o600)


def refresh(*, persistent_display: bool = False) -> dict[str, object]:
    with STATE.lock:
        STATE.last_attempt = time.time()
        STATE.refreshing = True
    try:
        quota = fetch_codex()
        refreshed_at = datetime.now().astimezone()
        render_outputs(
            quota,
            refreshed_at=refreshed_at,
            persistent_display=persistent_display,
        )
        document: dict[str, object] = {
            "schema": 1,
            "status": "live",
            "generated_at": refreshed_at.isoformat(timespec="seconds"),
            "codex": asdict(quota) | {"remaining_percent": quota.remaining_percent},
        }
        _write_private_json(JSON_OUT, document)
        with STATE.lock:
            STATE.last_refresh = time.time()
            STATE.error = None
            STATE.status = "live"
        return document
    finally:
        with STATE.lock:
            STATE.refreshing = False


def _publish_disconnected(reason: str) -> None:
    with STATE.lock:
        last_refresh = STATE.last_refresh
    last_success = (
        datetime.fromtimestamp(last_refresh).astimezone() if last_refresh is not None else None
    )
    render_disconnected_outputs(last_success_at=last_success)
    document = {
        "schema": 1,
        "status": "disconnected",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "last_success_at": last_success.isoformat(timespec="seconds") if last_success else None,
        "message": "未连接，请连接",
    }
    _write_private_json(JSON_OUT, document)
    with STATE.lock:
        STATE.error = reason
        STATE.status = "disconnected"


def _refresh_once(persistent_display: bool) -> None:
    try:
        refresh(persistent_display=persistent_display)
    except Exception as error:
        if persistent_display and GIF.is_file():
            with STATE.lock:
                STATE.error = _safe_error(error)
                STATE.status = "stale"
            print(f"Codex refresh failed; retaining last successful screen: {_safe_error(error)}")
        else:
            _publish_disconnected(_safe_error(error))
            print(f"Codex refresh failed; showing disconnected screen: {_safe_error(error)}")


def _refresh_loop(interval: int, initial_delay: bool, persistent_display: bool) -> None:
    if initial_delay:
        time.sleep(interval)
    while True:
        _refresh_once(persistent_display)
        time.sleep(interval)


def _disconnect_if_stale() -> None:
    with STATE.lock:
        last_refresh = STATE.last_refresh
        stale_after = STATE.stale_after
        stale = (
            not STATE.persistent_display
            and STATE.status == "live"
            and not STATE.refreshing
            and last_refresh is not None
            and time.time() - last_refresh > stale_after
        )
    if stale:
        _publish_disconnected(f"Codex data is older than {stale_after} seconds")


class Handler(BaseHTTPRequestHandler):
    server_version = "AP01CodexPlanBridge/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if not self._client_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        _disconnect_if_stale()
        if self.path == "/health":
            with STATE.lock:
                age = time.time() - STATE.last_refresh if STATE.last_refresh else None
                body = {
                    "ok": STATE.status == "live" and STATE.error is None,
                    "status": STATE.status,
                    "last_refresh": STATE.last_refresh,
                    "last_attempt": STATE.last_attempt,
                    "age_seconds": round(age, 1) if age is not None else None,
                    "stale_after": STATE.stale_after,
                    "error": STATE.error,
                    "refreshing": STATE.refreshing,
                    "snapshot_ready": GIF.is_file(),
                    "mode": "codex-only",
                }
            self._send(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(), "application/json; charset=utf-8")
            return
        item = {
            "/screen.gif": (GIF, "image/gif"),
            "/screen.png": (PNG, "image/png"),
            "/api/v1/quota": (JSON_OUT, "application/json; charset=utf-8"),
        }.get(self.path)
        if self.path == "/api/v1/quota" and not ipaddress.ip_address(
            self.client_address[0]
        ).is_loopback:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if item is None or not item[0].is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send(item[0].read_bytes(), item[1])

    def do_HEAD(self) -> None:  # noqa: N802
        if not self._client_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        item = {"/screen.gif": (GIF, "image/gif"), "/screen.png": (PNG, "image/png")}.get(self.path)
        if item is None or not item[0].is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send(item[0].read_bytes(), item[1], include_body=False)

    def _send(self, body: bytes, content_type: str, *, include_body: bool = True) -> None:
        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("ETag", etag)
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _client_allowed(self) -> bool:
        return self.client_address[0] in ALLOWED_CLIENTS

    def log_message(self, fmt: str, *args: object) -> None:
        message = fmt % args
        if '"GET /health ' not in message:
            try:
                label = "local" if ipaddress.ip_address(self.client_address[0]).is_loopback else "allowed-client"
            except ValueError:
                label = "allowed-client"
            status = str(args[1]) if len(args) > 1 else "unknown"
            print(f"[{self.log_date_time_string()}] {label} HTTP {status}")


def allowed_clients_for(bind: str, clients: list[str], local_address: str) -> set[str]:
    try:
        bind_address = ipaddress.ip_address(bind)
    except ValueError as error:
        raise ValueError(f"--bind must be a literal IP address: {error}") from error
    allowed: set[str] = {"127.0.0.1", "::1"}
    if local_address != "127.0.0.1":
        allowed.add(local_address)
    for value in clients:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as error:
            raise ValueError(f"invalid --allow-client address {value!r}: {error}") from error
        if address.version != 4 or not any(
            address in network for network in PRIVATE_LAN_NETWORKS
        ):
            raise ValueError("--allow-client must be a private IPv4 address")
        allowed.add(str(address))
    if not bind_address.is_loopback and not clients:
        raise ValueError("LAN binding requires at least one --allow-client AP01 address")
    return allowed


def main() -> int:
    global ALLOWED_CLIENTS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--stale-after", type=int)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-initial-refresh", action="store_true")
    parser.add_argument(
        "--persistent-display",
        action="store_true",
        help="keep the last successful Codex page visible instead of expiring it",
    )
    parser.add_argument(
        "--allow-client",
        action="append",
        default=[],
        help="private AP01 IPv4 allowed to fetch screen.gif; repeatable",
    )
    args = parser.parse_args()

    if args.once:
        try:
            document = refresh(persistent_display=args.persistent_display)
        except Exception as error:
            print(f"Codex refresh failed: {_safe_error(error)}")
            return 1
        print(json.dumps(document, ensure_ascii=False, indent=2))
        print(PREVIEW)
        return 0

    local_address = lan_ip()
    try:
        ALLOWED_CLIENTS = allowed_clients_for(args.bind, args.allow_client, local_address)
    except ValueError as error:
        parser.error(str(error))

    STATE.stale_after = args.stale_after or max(args.interval + 120, round(args.interval * 1.4))
    STATE.persistent_display = args.persistent_display
    if STATE.stale_after < 90:
        parser.error("--stale-after must be at least 90 seconds")
    if not GIF.is_file() or not JSON_OUT.is_file():
        _publish_disconnected("waiting for first Codex refresh")
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"AP01 Codex plan: LAN bridge active on TCP {args.port}")
    if args.allow_client:
        print(f"AP01 allow-list active: {len(args.allow_client)} device(s)")
    print("Bridge is ready; Codex refresh continues every five minutes")
    threading.Thread(
        target=_refresh_loop,
        args=(args.interval, args.no_initial_refresh, args.persistent_display),
        daemon=True,
    ).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
