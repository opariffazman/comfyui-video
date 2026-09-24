#!/usr/bin/env python
"""
Download MiniMax H3 weights into models/. Cross-platform (Linux, Windows).

  python scripts/download-models.py            # full set, incl. R2V (~65GB)
  python scripts/download-models.py --no-r2v   # skip R2V (~43GB)
  python scripts/download-models.py --check    # report only, download nothing

Files already present with the remote size are skipped.

Selection rationale (see README "Why these specific files"):
  - fl2va_pruned_int8_convrot : covers T2V + I2V + FLF2V. INT8 runs on Ampere tensor cores (needs torch cu130).
  - qwen3vl_32b nvfp4_awq     : smallest text encoder, no Blackwell GPU required.
  - turbo LoRAs               : 4-step 768p and 8-step presets.
  - ref2va + ref2v LoRA       : reference-to-video (R2V), optional.
"""
import argparse, os, sys
from pathlib import Path

os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
from huggingface_hub import HfApi, hf_hub_download  # noqa: E402

REPO = "Comfy-Org/MiniMax-H3"
ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

CORE = [
    "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "vae/minimax_h3_video_vae_fp16.safetensors",
    "vae/minimax_h3_audio_vae_fp32.safetensors",
    "loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
    "loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
]
R2V = [
    "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
]
EMPTY_DIRS = ["checkpoints", "clip_vision", "upscale_models"]


def gb(n):
    return f"{n / 1e9:.1f}GB"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-r2v", action="store_true", help="skip R2V files (~22GB)")
    p.add_argument("--check", action="store_true", help="report status, download nothing")
    a = p.parse_args()

    api = HfApi()
    embeddings = sorted(f for f in api.list_repo_files(REPO) if f.startswith("embeddings/"))
    wanted = CORE + ([] if a.no_r2v else R2V) + embeddings
    remote = {i.path: i.size for i in api.get_paths_info(REPO, wanted)}

    todo = []
    for f in wanted:
        local = MODELS / f
        size = remote.get(f)
        if size is None:
            sys.exit(f"{f}: not found in {REPO}. The repo layout changed — update this script.")
        if local.is_file() and local.stat().st_size == size:
            print(f"ok       {f}")
            continue
        state = "partial" if local.is_file() else "missing"
        print(f"{state:8} {f} ({gb(size)})")
        todo.append(f)

    for d in EMPTY_DIRS:
        (MODELS / d).mkdir(parents=True, exist_ok=True)

    if not todo:
        print("All models present.")
        return
    total = sum(remote[f] for f in todo)
    print(f"\nTo download: {len(todo)} files, {gb(total)}")
    if a.check:
        sys.exit(1)

    for f in todo:
        print(f"### {f}")
        hf_hub_download(REPO, f, local_dir=MODELS)
    print("=== DOWNLOAD COMPLETE ===")


if __name__ == "__main__":
    main()
