#!/usr/bin/env bash
# start.sh wrapped in a systemd scope with a hard RAM ceiling.
#
# Why: this box has 31GB RAM but other services (vLLM, meilisearch, browsers)
# usually hold ~14GB, and swap is zram — compressed RAM, not disk. Model
# weights are incompressible, so swapping them just burns CPU and eats more
# RAM. Without a cap, ComfyUI's CPU-offload path will drive the box into
# unresponsive swap-thrash.
#
# What this does:
#   MemoryHigh  soft ceiling — kernel throttles and reclaims hard past this.
#   MemoryMax   hard ceiling — the scope is OOM-killed instead of the desktop.
#   MemorySwapMax  keeps ComfyUI from filling zram (which is RAM).
# The cap is the safety net; FAST_DISK=1 is the actual fix — it offloads to
# NVMe (1.1TB free) instead of system RAM.
#
# Tunables:
#   MEM_HIGH=10G  MEM_MAX=14G  MEM_SWAP=2G
#   FAST_DISK=1   RESERVE_VRAM=1.5   CACHE_NONE=1   PORT=8188
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MEM_HIGH="${MEM_HIGH:-10G}"
MEM_MAX="${MEM_MAX:-14G}"
MEM_SWAP="${MEM_SWAP:-2G}"

export FAST_DISK="${FAST_DISK:-1}"
export RESERVE_VRAM="${RESERVE_VRAM:-1.5}"

# --cache-none keeps only the executing node's outputs in RAM instead of
# retaining every intermediate. Set CACHE_NONE=0 to trade RAM for faster re-runs.
if [ "${CACHE_NONE:-1}" = "1" ]; then
  EXTRA="${EXTRA:-} --cache-none"
fi

# ComfyUI sizes its pinned-memory budget from TOTAL system RAM and ignores
# cgroup limits (model_management.py: MAX_PINNED_MEMORY = max(ram*0.40, ...)),
# so on this 31GB box it budgets ~15.6GB — more than MEM_MAX. Pinned pages are
# unswappable, so leaving this on guarantees the scope gets OOM-killed the
# moment a 21GB model loads. Disabling costs some host<->device transfer speed,
# which --fast-disk largely sidesteps anyway. Set PINNED=1 to re-enable
# (raise MEM_MAX above ~17G first).
if [ "${PINNED:-0}" != "1" ]; then
  EXTRA="${EXTRA:-} --disable-pinned-memory"
fi
export EXTRA

echo "RAM cap: high=$MEM_HIGH max=$MEM_MAX swap=$MEM_SWAP  |  FAST_DISK=$FAST_DISK  EXTRA='${EXTRA:-}'"
echo "If it exceeds $MEM_MAX the scope is killed — the desktop stays alive."
echo

exec systemd-run --user --scope \
  --unit="comfyui-$$" \
  --description="ComfyUI (RAM-capped)" \
  -p MemoryHigh="$MEM_HIGH" \
  -p MemoryMax="$MEM_MAX" \
  -p MemorySwapMax="$MEM_SWAP" \
  -p OOMPolicy=stop \
  -- "$R/scripts/start.sh" "$@"
