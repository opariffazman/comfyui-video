#!/usr/bin/env python
"""
Launch ComfyUI for MiniMax H3 with flags picked from the detected GPU.
Called by scripts/start.sh (Linux) and scripts/start.ps1 (Windows).

Profiles (by total VRAM):
  24gb  >= 20GB  e.g. RTX 3090/4090. Weights stream from RAM.
  low   <  20GB  e.g. RTX 3080 10/12GB. Adds --fast-disk: weights stream from NVMe.

Env vars:
  PORT=8188          listen port
  FAST_DISK=1|0      force --fast-disk on/off (default: on for "low" profile)
  RESERVE_VRAM=1.5   GB of VRAM left for the desktop
  EXTRA="--fast"     extra flags passed to main.py
Extra CLI args are passed through to main.py.
"""
import importlib.util, os, platform, shlex, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMFY = ROOT / "comfy"
MODEL_MIB = 21500  # H3 int8 diffusion model + latents at 848x480


def gpu_mib():
    """Return (total, free) MiB of GPU 0, or None without nvidia-smi."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True).stdout
        total, free = (int(x) for x in out.splitlines()[0].split(","))
        return total, free
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        return None


def gpu_holders():
    try:
        return subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
             "--format=csv,noheader"],
            capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def ram_gib():
    try:
        import psutil
        return psutil.virtual_memory().total / 2**30
    except ImportError:
        return None


def sage_available():
    return (importlib.util.find_spec("sageattention") is not None
            and importlib.util.find_spec("triton") is not None)


def main():
    if not (COMFY / "main.py").is_file():
        sys.exit(f"ComfyUI not found at {COMFY}. Run scripts/setup.sh or scripts/setup.ps1 first.")

    gpu = gpu_mib()
    if gpu is None:
        sys.exit("nvidia-smi failed. Install the NVIDIA driver (>=580 for CUDA 13.0) and retry.")
    total, free = gpu
    profile = "24gb" if total >= 20000 else "low"

    # Reduces allocator fragmentation when a 21GB model shares VRAM with video latents.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    args = [
        "--port", os.environ.get("PORT", "8188"),
        "--enable-dynamic-vram",   # layer-wise streaming; lets 21GB weights run on smaller cards
        "--enable-manager",        # ComfyUI-Manager, built into core since v0.34
        "--extra-model-paths-config", str(ROOT / "extra_model_paths.yaml"),
        "--output-directory", str(ROOT / "outputs"),
        "--input-directory", str(ROOT / "inputs"),
        "--user-directory", str(ROOT / "user"),
    ]
    if sage_available():
        args.append("--use-sage-attention")  # Triton SageAttention, ~1.5-2x attention on Ampere
    else:
        print("!! sageattention/triton not importable — running with default attention (slower).")

    fast_disk = os.environ.get("FAST_DISK", "1" if profile == "low" else "0") == "1"
    if fast_disk:
        args.append("--fast-disk")
    if os.environ.get("RESERVE_VRAM"):
        args += ["--reserve-vram", os.environ["RESERVE_VRAM"]]
    if os.environ.get("EXTRA"):
        args += shlex.split(os.environ["EXTRA"], posix=platform.system() != "Windows")
    args += sys.argv[1:]

    ram = ram_gib()
    print(f"GPU: {free} MiB free / {total} MiB  |  profile={profile}  fast_disk={fast_disk}"
          + (f"  |  RAM {ram:.0f}GiB" if ram else ""))

    if profile == "24gb" and free < MODEL_MIB + 500:
        print(f"!! WARNING: H3 int8 wants ~{MODEL_MIB} MiB. These processes hold VRAM:")
        for line in gpu_holders().splitlines():
            print("     " + line)
        print("!! Stop them first, or generation will thrash through CPU/disk offload.\n")
    elif profile == "low":
        print("!! Low-VRAM profile: weights stream from disk each step, so generation is slow.")
        print("!! Start with 848x480, 2s, 8 steps. Keep models/ on an NVMe drive.")
        if total - free > 1500:
            print(f"!! {total - free} MiB VRAM already in use — close games/browsers with GPU acceleration.")
        print()
    if ram is not None and ram < 30 and not fast_disk:
        print(f"!! Only {ram:.0f}GiB RAM. If the system swaps, restart with FAST_DISK=1.\n")

    cmd = [sys.executable, str(COMFY / "main.py"), *args]
    os.chdir(COMFY)
    sys.stdout.flush()  # execv drops unflushed output when stdout is a file
    if platform.system() == "Windows":
        # os.execv on Windows spawns a detached child and breaks Ctrl+C.
        sys.exit(subprocess.call(cmd))
    os.execv(sys.executable, cmd)


if __name__ == "__main__":
    main()
