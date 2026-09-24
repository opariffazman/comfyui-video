#!/usr/bin/env bash
# Launch ComfyUI for MiniMax H3 (Linux). Flags are picked in scripts/launch.py.
#
# Tunables (env vars):
#   PORT=8188          port to serve on
#   FAST_DISK=1        offload to NVMe instead of system RAM (default on below 20GB VRAM)
#   RESERVE_VRAM=1.5   GB of VRAM to leave for the desktop compositor
#   EXTRA="--fast"     extra flags passed through to main.py
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -x "$R/.venv/bin/python" ] || { echo "No .venv found. Run scripts/setup.sh first." >&2; exit 1; }
exec "$R/.venv/bin/python" "$R/scripts/launch.py" "$@"
