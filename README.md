# ComfyUI — MiniMax H3 video generation

Local text-to-video, image-to-video, and reference-to-video with **MiniMax H3** (Hailuo 3.0).
It is a 33B open-weights omni-modal model.
It generates video **with native stereo audio** in a single pass.

## Quick start

Requirements on every machine:
- NVIDIA GPU, Ampere (RTX 30xx) or newer
- NVIDIA driver **>= 580** (torch cu130)
- ~70GB free disk for `models/`, on NVMe for cards under 20GB

Setup installs the rest:

| Tool | Linux | Windows |
|---|---|---|
| `git` | you install it | winget (`Git.Git`) |
| `uv` | official installer → `~/.local/bin` | winget, else official installer |
| Python 3.12 | `uv` downloads it | `uv` downloads it |

### Linux

```bash
git clone git@github.com:opariffazman/comfyui-video.git && cd comfyui-video
./scripts/setup.sh              # add --no-r2v to skip 22GB of R2V weights
./scripts/start.sh              # http://127.0.0.1:8188
```

### Windows 10/11 (PowerShell)

On a fresh machine, paste this one line. It installs git, clones to `$HOME\comfyui-video`, and runs setup:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/opariffazman/comfyui-video/main/scripts/bootstrap.ps1))) -NoR2V
```

- `-Dir D:\comfyui-video` picks the clone location. Use an NVMe drive.
- Drop `-NoR2V` to also fetch the 22GB of R2V weights.
- The Git installer shows one UAC prompt.

Then start ComfyUI (http://127.0.0.1:8188):

```powershell
cd $HOME\comfyui-video
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

With the repo already cloned, run `.\scripts\setup.ps1` directly. It installs uv when missing.
If scripts are blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

The Windows scripts are unconfirmed on real hardware.
The dependency set resolves for `win_amd64` (`torch 2.13.0+cu130`, `triton-windows 3.7.1`).
If SageAttention fails to install, `setup.ps1` warns and ComfyUI runs with default attention.

Then in the UI: **Workflow → Open** → pick a file from `workflows/`.

Re-run `setup` any time. Each step skips work already done. Weights with the correct size are never downloaded again.

## Hardware profiles

`scripts/launch.py` reads VRAM with `nvidia-smi` and picks the flags.

| Profile | VRAM | Example GPU | Flags added | Status |
|---|---|---|---|---|
| `24gb` | >= 20GB | RTX 3090, 4090 | `--enable-dynamic-vram` | tested (3090, Linux) |
| `low` | < 20GB | RTX 3080 10/12GB | `--enable-dynamic-vram --fast-disk` | unconfirmed |

On the `low` profile, weights stream from disk every step.
Expect generation many times slower than on a 3090.
Start with 848x480, 2 seconds, 8 steps.
Close GPU-accelerated apps (browsers, games) first. The launcher warns when more than 1.5GB of VRAM is in use.

Env vars for `start.sh` / `start.ps1`:

| Var | Effect |
|---|---|
| `PORT=8188` | listen port |
| `FAST_DISK=1` / `0` | force NVMe offload on or off (default: on for `low`) |
| `RESERVE_VRAM=1.5` | GB held back for the desktop |
| `EXTRA="--fast"` | extra `main.py` flags |

Linux only: `scripts/start-capped.sh` runs ComfyUI in a systemd scope with a hard RAM ceiling.
Use it on a box where other services compete for RAM.

## Layout

```
comfyui-video/
├── comfy/                  ComfyUI checkout, pinned tag (created by setup, git-ignored)
├── models/                 ~65GB of weights, OUTSIDE comfy/ (git-ignored)
├── user/                   ComfyUI settings + saved workflows (git-ignored)
├── workflows/              official Comfy-Org t2v / i2v / r2v templates
├── prompts/                prompt templates
├── inputs/                 source images for i2v (git-ignored)
├── outputs/                generated videos (git-ignored)
├── extra_model_paths.yaml  points ComfyUI at models/ (path relative to the repo)
└── scripts/
    ├── bootstrap.ps1                Windows one-liner: git + clone + setup
    ├── setup.sh / setup.ps1         install everything
    ├── start.sh / start.ps1         launch
    ├── launch.py                    GPU detection + ComfyUI flags
    ├── download-models.py           fetch weights (--no-r2v, --check)
    ├── run-h3.py                    CLI generation, no browser
    └── start-capped.sh              Linux RAM-capped launch
```

Pinned versions live at the top of `scripts/setup.sh` and `scripts/setup.ps1`. Keep both in sync.

## CLI (no browser)

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
./scripts/run-h3.py t2v "neon city at dusk, anamorphic lens, shallow depth of field"
./scripts/run-h3.py i2v "the mouse slowly rotates" --image transparent_rgb_gaming_mouse.png
./scripts/run-h3.py t2v "..." --seconds 5 --width 1344 --height 768 --steps 8
./scripts/run-h3.py t2v "..." --dry-run          # print graph, submit nothing
```

On Windows, run it as `python scripts\run-h3.py ...`.
`--image` refers to a filename inside `inputs/`.
Frame counts snap to the model's 17k+5 grid automatically (124 frames ≈ 5s at 24fps).

## Why these specific files

The stack targets **Ampere (sm_86)** and still runs on newer cards.

| Component | File | Reason |
|---|---|---|
| Diffusion | `fl2va_pruned_int8_convrot` (21GB) | FL2VA covers t2v **and** i2v **and** first+last-frame. Ampere has native INT8 tensor cores and **no** FP8 units, so `int8_convrot` beats `fp8_scaled` here. |
| Diffusion (R2V) | `ref2va_pruned_int8_convrot` (21GB) | Reference-to-video. Used only by `video_minimax_h3_r2v.json`. |
| Text encoder | `qwen3vl_32b_nvfp4_awq` (15.7GB) | Smallest of the three. Comfy-Org confirm NVFP4 here does **not** need a Blackwell GPU. |
| PyTorch | `2.13.0+cu130` | `int8_convrot` needs a cu130 build. `sm_86` is in `torch.cuda.get_arch_list()`. |
| Attention | SageAttention 1.0.6 | Pure Triton, runs on Ampere. Windows uses `triton-windows`. |
| VRAM | `--enable-dynamic-vram` | Layer-wise streaming. It lets a 21GB model run on a 24GB card alongside video latents. |

Peak VRAM is `max(text_encoder, diffusion)`, not the sum.
ComfyUI encodes the prompt, unloads the encoder, then loads the diffusion model.

## Resolution / step presets

| Preset | Settings | Notes |
|---|---|---|
| Fast draft | 848x480, 8 steps, 8step LoRA | template default, ~0.4MP |
| Quality | 1344x768, 8 steps, 8step LoRA | 768p, the model's native sweet spot |
| Fastest | 768p, 4 steps, `--lora 4step` | 4-step LoRA is tuned for 768p |

Both turbo LoRAs are distilled, so the graph uses `BasicGuider` (no CFG).

## Style embeddings

10 are installed. Reference them in a prompt by filename:

```
embedding:minimaxh3_bullet_time
```

Available: `art_is_explosion`, `blooming_flowers`, `bullet_time`, `dark_magic`,
`fire_breath`, `four_seasons`, `kiss_camera`, `spiral_ascent`, `storm_magic`,
`truman_show`.

## Notes

- **GPU contention.** H3 needs ~21.5GB on the `24gb` profile. The launcher lists processes holding VRAM when free VRAM is below that. Stop them before generating.
- **Licence.** MiniMax H3 ships under the MiniMax Community License. It excludes the US, EU, UK and South Korea from local deployment rights.
  Check it applies to you: <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE>
- **Updating ComfyUI.** Change `COMFY_TAG` / `$ComfyTag` in both setup scripts, then re-run setup. Weights are untouched.
