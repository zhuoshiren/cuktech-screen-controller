from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

import ap01_install_firmware
from ap01_custom_ota import choose_fds_device, verify_ota_readback
from mi_cloud import MiCloud


class InstallFirmwareTests(unittest.TestCase):
    def test_keychain_credentials_are_loaded_without_printing_tokens(self) -> None:
        completed = Mock(stdout='{"userId":"10001","passToken":"secret","deviceId":"mac"}')
        with (
            patch.dict(
                "os.environ",
                {
                    "CUKTECH_MI_KEYCHAIN_SERVICE": "test.service",
                    "CUKTECH_MI_KEYCHAIN_ACCOUNT": "relay",
                },
                clear=True,
            ),
            patch("mi_cloud.subprocess.run", return_value=completed) as run,
        ):
            self.assertEqual(
                MiCloud._load_account(),
                {"userId": "10001", "passToken": "secret", "deviceId": "mac"},
            )
        command = run.call_args.args[0]
        self.assertNotIn("secret", command)

    def test_windows_json_credentials_are_loaded_without_persisting_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mi-credentials.json"
            path.write_text(
                '{"userId":"10001","passToken":"secret","deviceId":"windows-device"}',
                encoding="utf-8",
            )
            self.assertEqual(
                MiCloud._load_account(credentials=path),
                {
                    "userId": "10001",
                    "passToken": "secret",
                    "deviceId": "windows-device",
                },
            )

    def make_firmware(self, root: Path) -> Path:
        path = root / "screen-realtime.bin"
        path.write_bytes(b"BFNP" + bytes(60))
        return path

    def test_explicit_fds_identity_does_not_require_device_listing(self) -> None:
        cloud = Mock()
        selected = choose_fds_device(
            cloud,
            did="gateway-did",
            model="lumi.gateway.example",
        )
        self.assertEqual(
            selected,
            {"did": "gateway-did", "model": "lumi.gateway.example"},
        )
        cloud.devices.assert_not_called()

    def test_upload_only_writes_transferable_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firmware = self.make_firmware(root)
            output = root / "ota-url.txt"
            stdout = io.StringIO()
            with (
                patch.object(ap01_install_firmware, "MiCloud", return_value=Mock()),
                patch.object(
                    ap01_install_firmware,
                    "upload_to_xiaomi",
                    return_value="https://iot-ota-cdn.io.mi.com/object?signature=test",
                ),
                patch.object(ap01_install_firmware, "deliver") as deliver,
                patch(
                    "sys.argv",
                    [
                        "ap01_install_firmware.py",
                        str(firmware),
                        "--upload-only",
                        "--url-output",
                        str(output),
                    ],
                ),
                contextlib.redirect_stdout(stdout),
            ):
                self.assertEqual(ap01_install_firmware.main(), 0)
            self.assertEqual(
                output.read_text(encoding="utf-8").strip(),
                "https://iot-ota-cdn.io.mi.com/object?signature=test",
            )
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("signature=test", stdout.getvalue())
            deliver.assert_not_called()

    def test_upload_only_refuses_to_print_a_signed_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            firmware = self.make_firmware(Path(directory))
            stderr = io.StringIO()
            with (
                patch(
                    "sys.argv",
                    ["ap01_install_firmware.py", str(firmware), "--upload-only"],
                ),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit),
            ):
                ap01_install_firmware.main()
            self.assertIn("requires --url-output", stderr.getvalue())

    def test_signed_url_command_line_is_rejected_without_echoing_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            firmware = self.make_firmware(Path(directory))
            secret_url = "https://iot-ota-cdn.io.mi.com/object?Signature=TOPSECRET"
            stderr = io.StringIO()
            with (
                patch(
                    "sys.argv",
                    [
                        "ap01_install_firmware.py",
                        str(firmware),
                        "--install",
                        "--ota-url",
                        secret_url,
                    ],
                ),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit),
            ):
                ap01_install_firmware.main()
            self.assertIn("--ota-url is disabled", stderr.getvalue())
            self.assertNotIn("TOPSECRET", stderr.getvalue())

    def test_download_only_signed_url_is_refused_before_network_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firmware = self.make_firmware(root)
            url = "https://iot-ota-cdn.io.mi.com/object?signature=test"
            with (
                patch.object(ap01_install_firmware, "MiCloud") as cloud,
                patch.object(ap01_install_firmware, "probe_ota_url") as probe,
                patch.object(ap01_install_firmware, "upload_to_xiaomi") as upload,
                patch.object(ap01_install_firmware, "deliver") as deliver,
                patch(
                    "sys.argv",
                    [
                        "ap01_install_firmware.py",
                        str(firmware),
                        "--download-only",
                        "--ota-url",
                        url,
                    ],
                ),
                self.assertRaisesRegex(SystemExit, "已禁用 --download-only"),
            ):
                ap01_install_firmware.main()
            cloud.assert_not_called()
            probe.assert_not_called()
            upload.assert_not_called()
            deliver.assert_not_called()

    def test_download_only_url_file_is_refused_before_file_or_network_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firmware = self.make_firmware(root)
            url = "https://iot-ota-cdn.io.mi.com/object?signature=test"
            url_file = root / "ota-url.txt"
            url_file.write_text(url + "\n", encoding="utf-8")
            with (
                patch.object(ap01_install_firmware, "MiCloud") as cloud,
                patch.object(ap01_install_firmware, "probe_ota_url") as probe,
                patch.object(ap01_install_firmware, "upload_to_xiaomi") as upload,
                patch.object(ap01_install_firmware, "deliver") as deliver,
                patch(
                    "sys.argv",
                    [
                        "ap01_install_firmware.py",
                        str(firmware),
                        "--download-only",
                        "--ota-url-file",
                        str(url_file),
                    ],
                ),
                self.assertRaisesRegex(SystemExit, "已禁用 --download-only"),
            ):
                ap01_install_firmware.main()
            cloud.assert_not_called()
            probe.assert_not_called()
            upload.assert_not_called()
            deliver.assert_not_called()

    def test_verify_download_never_creates_micloud_or_dispatches_ota(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firmware = self.make_firmware(root)
            url_file = root / "ota-url.txt"
            url_file.write_text(
                "https://iot-ota-cdn.io.mi.com/object?signature=test\n",
                encoding="utf-8",
            )
            with (
                patch.object(ap01_install_firmware, "MiCloud") as cloud,
                patch.object(
                    ap01_install_firmware,
                    "verify_ota_readback",
                    return_value={
                        "size": firmware.stat().st_size,
                        "sha256": "a" * 64,
                        "md5": "b" * 32,
                        "header": "BFNP",
                    },
                ) as verify,
                patch.object(ap01_install_firmware, "upload_to_xiaomi") as upload,
                patch.object(ap01_install_firmware, "deliver") as deliver,
                patch(
                    "sys.argv",
                    [
                        "ap01_install_firmware.py",
                        str(firmware),
                        "--verify-download",
                        "--ota-url-file",
                        str(url_file),
                    ],
                ),
            ):
                self.assertEqual(ap01_install_firmware.main(), 0)
                self.assertEqual(url_file.stat().st_mode & 0o777, 0o600)
            verify.assert_called_once_with(
                "https://iot-ota-cdn.io.mi.com/object?signature=test",
                firmware,
                360,
            )
            cloud.assert_not_called()
            upload.assert_not_called()
            deliver.assert_not_called()

    def test_host_readback_verification_accepts_exact_firmware(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            firmware = self.make_firmware(Path(directory))
            payload = firmware.read_bytes()
            response = Mock()
            response.iter_content.return_value = [payload[:3], payload[3:17], payload[17:]]
            with patch("ap01_custom_ota.requests.get", return_value=response):
                result = verify_ota_readback(
                    "https://iot-ota-cdn.io.mi.com/object?signature=test",
                    firmware,
                )
            self.assertEqual(result["size"], len(payload))
            self.assertEqual(result["header"], "BFNP")
            response.raise_for_status.assert_called_once_with()
            response.close.assert_called_once_with()

    def test_host_readback_verification_rejects_same_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            firmware = self.make_firmware(Path(directory))
            payload = bytearray(firmware.read_bytes())
            payload[-1] ^= 0xFF
            response = Mock()
            response.iter_content.return_value = [bytes(payload)]
            with (
                patch("ap01_custom_ota.requests.get", return_value=response),
                self.assertRaisesRegex(RuntimeError, "SHA-256 不一致"),
            ):
                verify_ota_readback(
                    "https://iot-ota-cdn.io.mi.com/object?signature=test",
                    firmware,
                )

    def test_host_readback_network_error_does_not_expose_signed_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            firmware = self.make_firmware(Path(directory))
            leaked = "https://iot-ota-cdn.io.mi.com/object?Signature=TOPSECRET"
            with (
                patch(
                    "ap01_custom_ota.requests.get",
                    side_effect=requests.RequestException(f"failed {leaked}"),
                ),
                self.assertRaisesRegex(RuntimeError, "完整回读请求失败") as raised,
            ):
                verify_ota_readback(leaked, firmware)
            self.assertNotIn("TOPSECRET", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
