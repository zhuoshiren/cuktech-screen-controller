# First-time real-time firmware workflow

The verified offsets in this kit apply only to model `njcuk.enstor.ap01`,
firmware `1.0.2_0031`. Refuse to reuse them on another build. Port and verify
every hook first.

For the four-provider layout, also read
[two-page-coding-dashboard.md](two-page-coding-dashboard.md). It defines the
physical window map, AP2B format and single-active-decoder requirements.

## Prerequisites

- Keep AP01 on stable base power, paired and online in Mi Home.
- Put the bridge computer and AP01 on the same non-isolated LAN.
- Reserve the computer's IPv4 address in the router before embedding it.
- Confirm model/version from current device data, not a filename or memory.
- Install Python dependencies, `riscv64-elf-gcc` and
  `riscv64-elf-binutils`.
- Start the bridge and validate `/health` and `/screen.ap2b` before install.
- Keep a private copy of the matching stock image and last known-good image.

Never commit firmware, credentials, DIDs, signed URLs, local IPs or artifacts.

## Build

Obtain the exact stock image through the owner's legitimate Mi Home account:

```bash
.venv/bin/python mi_cloud.py firmware
.venv/bin/python mi_cloud.py download
```

Build the compatibility image, then inject the RAM loader:

```bash
.venv/bin/python ap01_custom_ota.py artifacts/screen.gif \
  --firmware artifacts/ap01-1.0.2_0031.bin \
  --output artifacts/ap01-1.0.2_0031-screen-compat.bin

.venv/bin/python ap01_realtime_patch.py \
  --input artifacts/ap01-1.0.2_0031-screen-compat.bin \
  --output artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --build-dir artifacts/realtime-build \
  --url http://COMPUTER_LAN_IP:8765/screen.ap2b \
  --refresh-seconds 300
```

Never pass the real-time-patched output back through `ap01_custom_ota.py`; the
asset replacement would erase the injected payload.

Retain and review the patch manifest. Require recovery length/CRC, BFNP,
payload readback, exact hook targets, expected changed ranges, no ELF
relocations and no writable payload globals.

## Upload without exposing the owner account

AP01 has no server-side FDS upload configuration. A real FDS-capable
`lumi.gateway.*` or `xiaomi.gateway.*` identity may obtain the signed upload
URL; the AP01 DID is used only for the later `miIO.ota` install command.

When such a gateway is available:

```bash
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --upload-only --url-output /tmp/ap01-ota-url.txt
```

The restricted shared relay is an alternative for owners without a gateway.
It may accept only the private bridge URL, exact model/version and refresh
interval. It must pin the reviewed stock hash, reject arbitrary firmware,
omit signed URLs from logs, and never receive the owner's Xiaomi credentials,
AP01 DID or coding-provider sessions.

## Host-side verification is mandatory

Do not use device `download-only`. Real-device testing found that AP01
1.0.2_0031 may continue from `proc=dnld` into automatic installation and
reboot. The public CLI refuses `--download-only` before reading URL files or
accessing the network.

Verify the exact uploaded object on the computer:

```bash
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --verify-download --ota-url-file /tmp/ap01-ota-url.txt --timeout 360
```

This action:

- accepts only the official `https://iot-ota-cdn.io.mi.com` host;
- downloads the complete signed object on the host;
- compares BFNP, byte count, SHA-256 and MD5 with the local image;
- does not instantiate `MiCloud`;
- does not contact AP01;
- does not send `miIO.ota` or write Flash.

Do not rebuild between upload, verification and installation.

## Explicitly confirmed install

Stop if the owner has not explicitly approved installing and restarting this
exact verified image. After approval:

```bash
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --install --ota-url-file /tmp/ap01-ota-url.txt --timeout 420
```

Keep stable power. Require all of the following before declaring completion:

1. AP01 accepts the OTA command.
2. Install-stage or progress evidence appears.
3. Uptime decreases after reboot and the device returns online.
4. The bridge logs AP01 `GET /screen.ap2b 200`.
5. The owner visually verifies both physical pages and all retained stock pages.

A successful build, upload, CDN hash or RPC acceptance alone is not enough.

## Runtime storage and Flash behavior

The two-page loader writes recurring data only to tmpfs:

```text
/tmp/.ap01p{0,1,2}{m,o}.gif
/tmp/.ap01q.meta
/tmp/.ap01q.ack
/tmp/.ap01q.ui
/tmp/.ap01blank.gif
```

OTA writes Flash once. Normal five-minute screen refreshes do not write the
firmware or resource partitions.

## Recovery boundary

If either page becomes white, the carousel attaches to Power/Settings, or the
device stops rotating, do not keep flashing variants. Restore the last exact
known-good image, verify its hash and CDN readback, install it once with owner
approval, then prove the known-good page before attempting a focused patch.

Prefer restoring the embedded bridge IP or router reservation over rebuilding
firmware after a DHCP change. Reinstall only when the old address cannot be
restored and the new address has been stabilized.
