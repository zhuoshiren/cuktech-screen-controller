#!/usr/bin/env python3
"""Upload or deliver an already-built AP01 image without rebuilding it."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from ap01_custom_ota import (
    deliver,
    probe_ota_url,
    upload_to_xiaomi,
    verify_ota_readback,
)
from mi_cloud import MiCloud


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--upload-only",
        action="store_true",
        help="upload through a gateway-enabled account and print the signed OTA URL",
    )
    action.add_argument(
        "--download-only",
        action="store_true",
        help="disabled: AP01 1.0.2_0031 auto-installs after download",
    )
    action.add_argument(
        "--verify-download",
        action="store_true",
        help="download from the signed CDN on this computer and compare every byte",
    )
    action.add_argument("--install", action="store_true")
    parser.add_argument(
        "--ota-url-file",
        type=Path,
        help="read an existing signed AP01-compatible OTA URL from a private text file",
    )
    parser.add_argument("--ota-url", help=argparse.SUPPRESS)
    parser.add_argument(
        "--url-output",
        type=Path,
        help="required with --upload-only; write the signed OTA URL to a private file",
    )
    parser.add_argument("--fds-did", help="explicit FDS-capable gateway DID")
    parser.add_argument("--fds-model", help="explicit FDS-capable gateway model")
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()
    if args.download_only:
        raise SystemExit(
            "AP01 1.0.2_0031 实测会在 download-only 返回 downloaded 后继续自动安装并重启；"
            "为避免未经确认的刷写，此工具已禁用 --download-only。请先 --upload-only，"
            "并仅在用户明确确认后使用 --install。"
        )
    header = args.firmware.read_bytes()[:4]
    if header != b"BFNP":
        raise SystemExit("firmware does not have an AP01 BFNP header")
    if bool(args.fds_did) != bool(args.fds_model):
        parser.error("--fds-did and --fds-model must be supplied together")
    if args.ota_url:
        parser.error(
            "--ota-url is disabled because command lines leak into shell history and "
            "process listings; use a mode-0600 --ota-url-file"
        )
    supplied_url = None
    if args.ota_url_file:
        if args.ota_url_file.is_symlink() or not args.ota_url_file.is_file():
            parser.error("--ota-url-file must be a regular file, not a symlink")
        try:
            os.chmod(args.ota_url_file, 0o600)
        except OSError:
            if os.name != "nt":
                parser.error("--ota-url-file permissions could not be restricted to mode 0600")
        supplied_url = args.ota_url_file.read_text(encoding="utf-8").strip()
        if not supplied_url:
            parser.error("--ota-url-file is empty")
    if supplied_url and args.upload_only:
        parser.error("an existing OTA URL cannot be combined with --upload-only")
    if supplied_url and (args.fds_did or args.fds_model):
        parser.error("an existing OTA URL cannot be combined with FDS device options")
    if args.url_output and not args.upload_only:
        parser.error("--url-output requires --upload-only")
    if args.upload_only and not args.url_output:
        parser.error(
            "--upload-only requires --url-output; signed OTA URLs are never printed "
            "or accepted on the command line"
        )

    if args.verify_download:
        if not supplied_url:
            parser.error("--verify-download requires --ota-url-file")
        result = verify_ota_readback(supplied_url, args.firmware, args.timeout)
        print(
            "电脑端 OTA CDN 回读验证通过："
            f"BFNP，{result['size']} 字节，SHA-256 与 MD5 完全一致；"
            "未连接 AP01、未下发 OTA。"
        )
        return 0

    cloud = MiCloud()
    if supplied_url:
        url = supplied_url
        probe_ota_url(url)
        print("已验证外部 OTA URL 的 BFNP 文件头；跳过 FDS 上传")
    else:
        url = upload_to_xiaomi(
            cloud,
            args.firmware,
            fds_did=args.fds_did,
            fds_model=args.fds_model,
        )

    if args.upload_only:
        assert args.url_output is not None
        _write_private_text(args.url_output, url + "\n")
        print(f"OTA URL 已安全写入私有文件：{args.url_output}")
        return 0

    deliver(cloud, args.firmware, url, args.timeout)
    return 0


def _write_private_text(path: Path, value: str) -> None:
    """Atomically create a mode-0600 ticket without a world-readable window."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
