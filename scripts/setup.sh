#!/usr/bin/env bash
# One-shot setup (Linux). Safe to re-run: every step skips work already done.
#
#   ./scripts/setup.sh               # full install, all models (~65GB)
#   ./scripts/setup.sh --no-r2v      # skip R2V weights (~43GB)
#   ./scripts/setup.sh --skip-models # software only
#
# Needs: git, NVIDIA driver >= 580 (CUDA 13.0). Installs uv to ~/.local/bin when missing.
# Python 3.12 comes from uv.
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$R"

# --- Pinned versions: change here, then re-run ---
COMFY_TAG=v0.34.0
PYTHON=3.12
TORCH=(torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0)  # cu130: required by int8_convrot
SAGE=sageattention==1.0.6

SKIP_MODELS=0
DL_ARGS=()
for a in "$@"; do
  case "$a" in
    --skip-models) SKIP_MODELS=1 ;;
    --no-r2v)      DL_ARGS+=(--no-r2v) ;;
    *) echo "Unknown arg: $a (valid: --skip-models, --no-r2v)" >&2; exit 2 ;;
  esac
done

if ! command -v uv >/dev/null; then
  echo "### Installing uv (official installer, to ~/.local/bin)"
  command -v curl >/dev/null || { echo "Missing 'curl' to install uv. Install curl or uv and re-run." >&2; exit 1; }
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
for cmd in git uv nvidia-smi; do
  command -v "$cmd" >/dev/null || { echo "Missing '$cmd'. Install it and re-run." >&2; exit 1; }
done
DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
if [ "${DRIVER%%.*}" -lt 580 ]; then
  echo "NVIDIA driver $DRIVER is too old. torch cu130 needs >= 580. Update the driver and re-run." >&2
  exit 1
fi
echo "### GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1), driver $DRIVER"

echo "### ComfyUI $COMFY_TAG"
if [ ! -d comfy/.git ]; then
  git clone --branch "$COMFY_TAG" --depth 1 https://github.com/comfyanonymous/ComfyUI.git comfy
else
  git -C comfy rev-parse -q --verify "refs/tags/$COMFY_TAG" >/dev/null \
    || git -C comfy fetch --quiet --depth 1 origin tag "$COMFY_TAG"
  git -C comfy checkout --quiet "$COMFY_TAG"
fi

echo "### Python $PYTHON venv"
[ -x .venv/bin/python ] || uv venv --python "$PYTHON" .venv

echo "### Python packages"
uv pip install --python .venv --torch-backend cu130 \
  "${TORCH[@]}" \
  -r comfy/requirements.txt \
  -r comfy/manager_requirements.txt \
  "$SAGE" huggingface_hub

mkdir -p models outputs inputs logs user

if [ "$SKIP_MODELS" = 0 ]; then
  echo "### Models"
  .venv/bin/python scripts/download-models.py "${DL_ARGS[@]}"
fi

echo
echo "Setup complete. Start with: ./scripts/start.sh"
