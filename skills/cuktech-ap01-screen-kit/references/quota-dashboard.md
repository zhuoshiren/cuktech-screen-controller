# Legacy single-page migration note

The repository retains an older one-page renderer for compatibility. Its
Claude collector decrypts the local Claude Desktop cookie store and calls a
web-account endpoint. That path is **not** part of the reviewed two-page case,
and this Skill must not enable or recommend it for a new deployment.

For the real-device-tested four-provider physical two-page layout, read
[two-page-coding-dashboard.md](two-page-coding-dashboard.md).

## Safe migration choices

Choose one:

- Use `codex_plan_bridge.py` for a Codex-only page through the official local
  `codex app-server`.
- Use `coding_balances_bridge.py` plus `claude_statusline_cache.py` for Claude
  Code. The cache helper has no network code and keeps only official quota
  percentages, reset times, plan label and cache time.
- Preserve the old renderer only as a visual reference; do not call
  `fetch_claude_desktop()`, read Claude Safe Storage, export browser cookies,
  or copy a Chromium cookie database.

If an existing installation still depends on the legacy collector, explain
the difference and obtain an explicit migration decision. Do not silently
switch account access methods.

## Preserve the visual contract

When reusing the old one-page design, preserve these invariants:

1. Keep rows `0..39` empty for the AP01 clock/date overlay.
2. Keep the device output exactly 320x240.
3. Keep large numbers visually centered inside their rings.
4. Export at least two slow frames; one-frame GIFs may render black.
5. Keep the GIF under 90 KB for smooth playback when practical.

Use the render commands from the selected safe workflow. All generated quota
JSON and previews are private runtime artifacts and must remain ignored by Git.

## Verify the replacement

Require a localhost health check, an AP01 allow-list hit without printing its
address, and visual confirmation. The two-page route must show a Claude source
of `Claude Code official statusLine`; any cookie-based source means migration
is incomplete.
