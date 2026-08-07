# Verified two-page coding dashboard

Use this runbook for the real-device layout with Codex + Claude Code on one
physical knob page and Kimi Code + DeepSeek on the next. It has been verified
on model `njcuk.enstor.ap01`, firmware `1.0.2_0031`.

Do not reuse binary offsets on another model or version. Do not distribute the
vendor firmware or commit firmware, signed OTA URLs, credentials, DIDs, local
IPs, account balances, caches or generated artifacts.

## Result and physical page map

The AP01 carousel is circular. Its relevant internal order is:

```text
Settings 6
  → virtual-pet 7      Codex + Claude Code
  → Weather 5          Kimi Code + DeepSeek
  → Date 4
  → Time 3
  → Power 0
  → Settings 6
```

`window 0` is Power, not Weather. Never infer window identity only from the
page immediately before or after the current knob position.

Transport order and physical order are intentionally separate:

```text
AP2B page 0 = Codex + Claude Code = physical window 7
AP2B page 1 = Kimi Code + DeepSeek = physical window 5
```

The runtime must preserve all of these invariants:

- reuse the stock GIF object in window 7;
- create exactly one new GIF object in stock window 5;
- keep only the selected 320x240 decoder active;
- point the non-selected object to `/tmp/.ap01blank.gif`, a 1x1 GIF;
- recenter the object after every source change;
- reset only runtime idle counters to prevent the stock screen saver;
- do not modify persisted screen settings;
- retain Settings, Date, Time and Power.

Multiple live full-size GIF decoders exceed the practical memory budget and
produce white pages. Adding an eighth page is not a substitute: the stock UI
owns its page list and may delete, overlap or ignore an injected page.

## Account-source safety

Use only the four implemented sources. Do not silently substitute account
scraping, unofficial endpoints or browser-cookie export.

| Provider | Source | Local secret handling |
| --- | --- | --- |
| Codex | official local `codex app-server` | use the existing signed-in Codex session |
| Claude Code | official `statusLine.rate_limits` input | cache sanitized percentages/reset times only |
| Kimi Code | official local OAuth file and `api.kimi.com/coding/v1/usages` | reuse the user's Kimi Code login; never print tokens |
| DeepSeek | official `/user/balance` API | store the key in macOS Keychain |

The active bridge contains no OpenCode Go or Qwen collectors. Do not describe
those abandoned experiments as supported.

Quota artifacts are account data. The bridge writes JSON, GIF, PNG and AP2B
files as mode 0600, serves raw JSON to loopback only, and exposes images only
to loopback plus the exact RFC1918 AP01 allow-list. Logs label the requester as
`local` or `allowed-client` without storing its address.

### Claude Code statusLine integration

`claude_statusline_cache.py` has no network code and prints nothing. It retains
only `used_percentage`, `resets_at`, the `max` plan label and cache time. It
does not retain session ID, transcript path/content or token data.

Read the user's current Claude `statusLine` configuration and script before
editing. Back up the script. Preserve its existing output and feed the same
captured JSON to the cache helper as a side effect:

```bash
input=$(cat)
printf '%s' "$input" | /ABSOLUTE/REPO/.venv/bin/python \
  /ABSOLUTE/REPO/claude_statusline_cache.py 2>/dev/null || true

# Continue the original status-line renderer using "$input".
```

Do not install a second status-line command that consumes stdin before the
existing renderer, and do not make network requests with Claude credentials.

### DeepSeek Keychain setup

Use the secure macOS prompt. Never place the key in a command line, README,
shell history or project file:

```bash
swift macos/store-deepseek-key.swift
```

The background bridge reads only the Keychain item named
`com.wqytommy.CUKTECHScreenController.deepseek-api-key / api`.
DeepSeek does not provide a balance-only key scope; the stored key retains its
normal API privileges. Rotate it if the machine or Keychain item is exposed.

## Render and serve

Create the environment and confirm each official client is already signed in:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Write only the AP01 private IPv4 to the ignored allow-list file, select coding
mode, and start the bridge:

```bash
mkdir -p artifacts
printf '%s\n' 'AP01_PRIVATE_IP' > artifacts/ap01-ip
printf '%s\n' 'coding' > artifacts/ap01-mode
./macos/ap01-bridge-runner.sh
```

Direct invocation is equivalent:

```bash
.venv/bin/python -u coding_balances_bridge.py \
  --bind 0.0.0.0 --port 8765 --interval 300 \
  --persistent-display --allow-client AP01_PRIVATE_IP
```

The allow-list is mandatory for non-loopback binding. Sanitized JSON is
localhost-only. The runtime endpoints are:

```text
GET /health
GET /screen.gif          compatibility copy of page 0
GET /screen.ap2b         AP2B header plus two complete GIF89a pages
GET /screen/kimi-deepseek.gif
GET /api/v1/balances     localhost only
```

Inspect both previews before firmware work:

```text
artifacts/coding-balances-codex-claude@2x.png
artifacts/coding-balances-kimi-deepseek@2x.png
```

Validate the bridge locally and from the LAN address. A successful response is
not yet device proof; require a logged AP01 `GET /screen.ap2b 200` after reboot.

## AP2B contract

The bridge writes a 20-byte little-endian header followed by two complete GIFs:

```text
u32 magic      0x42325041 ("AP2B")
u32 version    1
u32 page0_size
u32 page1_size
u32 check      magic ^ version ^ sizes ^ 0xA50102B2
bytes page0
bytes page1
```

Each page must be 320x240 GIF89a, at least two frames, terminated by `0x3b`,
and no larger than 256 KiB. The current renderer uses two slow frames so the
display remains stable indefinitely in `--persistent-display` mode.

The payload rotates three generations in tmpfs:

```text
/tmp/.ap01p{0,1,2}{m,o}.gif
/tmp/.ap01q.meta
/tmp/.ap01q.ack
/tmp/.ap01q.ui
/tmp/.ap01blank.gif
```

The writer excludes both the published and decoder-acknowledged generations,
so it never truncates a page currently being decoded.

## Build the exact loader

Obtain the matching stock firmware through the owner's legitimate Mi Home
account. Do not commit it. Build the fallback image, then inject the two-page
runtime URL:

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

Never pass the already real-time-patched output back through
`ap01_custom_ota.py`; replacing the asset slot would erase the injected
payload. Retain the patch manifest and require BFNP, recovery CRC, payload
readback, exact hook targets and zero relocations.

## Safe upload, host verification and install

AP01 1.0.2_0031 may continue into install after a device
`proc=dnld`/`--download-only` request reports downloaded. The public tools
therefore refuse `--download-only`.

Use this sequence:

```bash
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --upload-only --url-output /tmp/ap01-ota-url.txt

.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --verify-download --ota-url-file /tmp/ap01-ota-url.txt --timeout 360
```

`--verify-download` runs on the computer only. It requires the official Xiaomi
OTA CDN hostname and compares BFNP, full byte count, SHA-256 and MD5. It does
not construct `MiCloud`, contact AP01 or send `miIO.ota`.
The signed URL is never accepted as a command-line value or printed. Both the
uploader and shared-relay client write it atomically to a mode-0600 ticket file;
network exceptions discard the original URL before reaching logs.

Only after the owner explicitly confirms the exact verified image:

```bash
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --install --ota-url-file /tmp/ap01-ota-url.txt --timeout 420
```

Keep stable power. Completion requires an accepted OTA, install/reboot evidence,
the AP01 back online, a new `GET /screen.ap2b 200`, and visual confirmation of
both knob pages. A successful build or CDN checksum alone is not completion.

## Failure diagnosis and recovery

| Symptom | Likely cause | Correct response |
| --- | --- | --- |
| both custom pages are white | more than one full-size decoder, invalid source swap, or hiding the page object | restore the known-good loader; enforce one active decoder and the 1x1 placeholder |
| Kimi page replaces Power | custom object attached to `window 0` | attach it to stock Weather `window 5` |
| custom page appears beside Settings | physical order was inferred instead of mapped | use the fixed `6 → 7 → 5 → 4 → 3 → 0` map |
| Weather remains and Kimi disappears | an unsupported extra/eighth page was added | replace `window 5`; do not append a page |
| Codex page worked before but all pages became blank | loader/UI experiment regressed the known-good single-page object | reinstall the last known-good exact image, prove page 7, then reapply only the single-decoder two-page patch |
| screen falls back to stock screen saver | idle counters are not reset in RAM | use the runtime-only reset; do not overwrite persisted settings |
| bridge is healthy but display never refreshes | embedded host IP changed, AP isolation/firewall, wrong path, or client not allow-listed | restore the reserved IP first, then verify `/health`, `/screen.ap2b`, logs and allow-list |

Never recover by repeatedly flashing unreviewed variants. Keep the matching
stock image and the last known-good custom image locally, compare hashes, and
make one controlled install only after host-side readback verification.

## Acceptance checks

Run the test suite and inspect the deterministic demo:

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python scripts/render-two-page-demo.py
```

Report separately:

- exact model and firmware version;
- both 320x240 GIF sizes/frame counts and AP2B header validation;
- patch manifest and firmware hash, without publishing the firmware;
- host-side CDN readback result;
- install/reboot evidence;
- AP01 `/screen.ap2b` request time;
- visual confirmation that page 7 and page 5 both render and stock pages remain;
- confirmation that recurring updates use tmpfs RAM only.
