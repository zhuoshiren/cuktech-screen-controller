#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
PYTHON="$ROOT/.venv/bin/python"
MODE_FILE="$ROOT/artifacts/ap01-mode"
CUSTOM_GIF="$ROOT/artifacts/custom-screen.gif"
AP01_IP_FILE="$ROOT/artifacts/ap01-ip"

if [[ ! -x "$PYTHON" ]]; then
    echo "CUKTECH runtime missing"
    echo "Run the installer again or execute scripts/setup-macos.sh from the repository."
    exit 1
fi

mode="quota"
if [[ -f "$MODE_FILE" ]]; then
    mode="$(tr -d '[:space:]' < "$MODE_FILE")"
fi

cd "$ROOT"
if [[ "$mode" == "custom" && -f "$CUSTOM_GIF" ]]; then
    echo "AP01 mode: custom"
    exec "$PYTHON" -u "$ROOT/ap01_screen_bridge.py" \
        "$CUSTOM_GIF" --bind 0.0.0.0 --port 8765
fi

if [[ "$mode" == "codex" ]]; then
    if [[ ! -f "$AP01_IP_FILE" ]]; then
        echo "Missing AP01 allow-list address file"
        echo "Pair AP01 in Mi Home, confirm its private IPv4, then write that address to the file."
        exit 1
    fi
    AP01_IP="$(tr -d '[:space:]' < "$AP01_IP_FILE")"
    echo "AP01 mode: Codex plan only"
    exec "$PYTHON" -u "$ROOT/codex_plan_bridge.py" \
        --bind 0.0.0.0 --port 8765 --interval 300 --persistent-display --allow-client "$AP01_IP"
fi

if [[ "$mode" == "coding" ]]; then
    if [[ ! -f "$AP01_IP_FILE" ]]; then
        echo "Missing AP01 allow-list address file"
        exit 1
    fi
    AP01_IP="$(tr -d '[:space:]' < "$AP01_IP_FILE")"
    echo "AP01 mode: Codex + Claude + Kimi + DeepSeek"
    exec "$PYTHON" -u "$ROOT/coding_balances_bridge.py" \
        --bind 0.0.0.0 --port 8765 --interval 300 --persistent-display --allow-client "$AP01_IP"
fi

echo "AP01 mode: quota"
exec "$PYTHON" -u "$ROOT/ap01_wifi_bridge.py" \
    --bind 0.0.0.0 --port 8765 --interval 300
