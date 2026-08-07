---
name: cuktech-ap01-screen-kit
description: Create, validate, deploy, recover, and operate Wi-Fi-updated screens for the CUKTECH AP01 detachable display. Use when Codex needs to convert images or GIFs, deploy the real-device-tested two-page Codex plus Claude Code and Kimi Code plus DeepSeek dashboard, build the exact 1.0.2_0031 loader, safely verify and install it through Xiaomi OTA, diagnose white pages or wrong carousel positions, or explain Flash versus RAM updates.
---

# CUKTECH Screen Controller

Build a reusable AP01 project, choose the smallest applicable workflow, and
validate both the rendered asset and the device request path.

## Bootstrap a project

Use an existing AP01 project when present. Otherwise copy the bundled template:

```bash
python3 "<skill-root>/scripts/create_project.py" ./cuktech-ap01-screen \
  --venv
cd ./cuktech-ap01-screen
```

On Windows, run the same script with `py -3`; it automatically uses
`.venv\Scripts\python.exe`. This repository ships a native SwiftUI controller
for macOS and a PySide6 controller for Windows; the project template, image
converter and LAN Bridge also support both systems.

Do not copy firmware, cookies, tokens, signed URLs, device IDs, or generated
artifacts into a shareable project.

## Choose the workflow

1. **Replace artwork on an already-patched display**: read
   [references/custom-content.md](references/custom-content.md). Convert the
   asset, atomically replace the served GIF, and avoid OTA.
2. **Deploy the verified two-page coding dashboard**: read
   [references/two-page-coding-dashboard.md](references/two-page-coding-dashboard.md).
   Use physical window 7 for Codex + Claude Code and stock Weather window 5
   for Kimi Code + DeepSeek. Preserve the single-active-decoder design.
3. **Encounter the legacy single-page Claude/Codex panel**: read
   [references/quota-dashboard.md](references/quota-dashboard.md). Do not use
   its Claude Desktop cookie collector for a new deployment. Migrate Claude
   to the official statusLine cache in the verified two-page workflow, or use
   the Codex-only bridge.
4. **Install real-time loading for the first time**: read
   [references/realtime-firmware.md](references/realtime-firmware.md). Verify
   the exact firmware version before touching binary offsets. When the owner
   has no FDS-capable gateway, prefer the Controller's restricted shared-relay
   package flow; do not ask them to buy a gateway or share Xiaomi credentials.
5. **Fix connectivity, IP changes, or persistent service operation**: read
   [references/network-operations.md](references/network-operations.md).

## Preserve device invariants

- Emit exactly 320x240 GIF89a with at least two frames per page.
- Keep animation bounded and prefer less than 90 KB for smooth decoding; still
  images use two slow frames, while source GIFs may retain up to eight frames.
- Keep rows `0..39` empty when retaining the stock clock/date overlay.
- Keep the Bridge computer and AP01 on the same non-isolated LAN and reserve
  the computer's IP.
- Treat Wi-Fi/LAN as the content path; do not ask the user to prepare a USB
  data cable or rely on the charging-base contacts.
- For first-loader work, require stable AP01 power, Mi Home pairing/online
  status, internet access, and the owner's Xiaomi account. For ordinary local
  artwork, internet is optional after the loader is installed. Automatic
  quota mode still needs internet access on its host computer.
- Ensure macOS or Windows firewall/VPN settings allow inbound LAN access to
  TCP 8765. Windows should allow the packaged runtime (or Python when running
  from source) on Private networks only.
- Treat the firmware patch as specific to model `njcuk.enstor.ap01`, firmware
  `1.0.2_0031`; do not reuse its offsets on another build.
- For the two-page dashboard, keep the fixed physical order
  `Settings 6 → Codex/Claude 7 → Kimi/DeepSeek 5 → Date 4 → Time 3 → Power 0`.
  Window 0 is Power, not Weather.
- Keep exactly one full-size GIF decoder active. Reuse the window 7 stock GIF
  object, create one object on window 5, and point the other object to the 1x1
  tmpfs placeholder. Multiple decoders cause white pages.
- Start the bridge before installing and require a logged AP01
  `GET /screen.ap2b` after reboot for two-page firmware, or `/screen.gif` for
  the legacy single-page workflow.
- Install the real-time firmware once. Perform later two-page updates through
  `/tmp/.ap01p{0,1,2}{m,o}.gif` RAM slots instead of OTA.
- Never pass an already real-time-patched image through
  `ap01_custom_ota.py`; that would overwrite the injected payload area.
- A shared relay may accept only the private Bridge URL, fixed model/version
  and refresh interval. It must reject arbitrary firmware uploads, pin the
  reviewed stock SHA-256, omit signed URLs from logs, and never receive the
  AP01 owner's Xiaomi credentials or DID.
- The public workflow must refuse device `--download-only`: AP01 1.0.2_0031
  may continue into installation. Verify a signed package by downloading the
  entire official CDN object on the host and comparing BFNP, size, SHA-256 and
  MD5 without creating a Mi Home session or contacting AP01.
- Never put Xiaomi PassTokens, provider keys or signed OTA URLs in command-line
  arguments. Pass credentials through a secure prompt/stdin into Keychain and
  put OTA tickets only in atomic mode-0600 files. Redact URL query strings,
  local addresses and account paths from persistent logs.
- Do not invoke `fetch_claude_desktop()` or export/decrypt browser cookies for
  the verified dashboard. Claude Code data must arrive through the official
  `statusLine.rate_limits` input and be reduced to quota fields before caching.
- Live dashboards must expose freshness. The verified persistent two-page mode
  keeps the last successful values and timestamp through outages; report
  provider errors in local health/JSON and never describe an old timestamp as
  current. The legacy single-page workflow may use a disconnected fallback.

## Validate before delivery

Run the available unit tests and inspect the 2x preview. For arbitrary content,
validate dimensions, GIF version, frame count, trailer, and byte size. For a
firmware build, retain the patcher's manifest, CRC, MD5, payload readback,
hook-target checks, and zero-relocation result.

Confirm bridge health and the correct content endpoint:

```bash
curl --noproxy '*' http://127.0.0.1:8765/health
```

For two-page mode also validate `/screen.ap2b`. On Windows use
`Invoke-RestMethod http://127.0.0.1:8765/health`.

Report separately:

- design-master size;
- device-GIF dimensions, frames, and bytes;
- refresh interval and latest AP01 request time;
- whether OTA was required;
- that recurring updates use RAM rather than Flash.

## Bundled resources

- `scripts/create_project.py`: create a clean working project from the template.
- `assets/project-template/`: renderer, bridges, firmware builder, exact-image
  installer, payload source, icons, tests, and dependency list.
- `references/`: load only the workflow relevant to the user's request.
