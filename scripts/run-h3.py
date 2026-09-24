#!/usr/bin/env python
"""
CLI driver for MiniMax H3 on ComfyUI (RTX 3090 tuned).

Builds the same graph as the official Comfy-Org t2v/i2v templates and submits
it to a running ComfyUI over the HTTP API.

  ./scripts/run-h3.py t2v "a neon city at dusk, anamorphic lens"
  ./scripts/run-h3.py i2v "the mouse slowly rotates" --image mouse.png
  ./scripts/run-h3.py t2v "..." --seconds 5 --width 1344 --height 768 --steps 8

Frame count is snapped to the model's 17k+5 grid automatically.
"""
import argparse, json, sys, time, urllib.request, urllib.error

MODEL   = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
CLIP    = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VAE_VID = "minimax_h3_video_vae_fp16.safetensors"
VAE_AUD = "minimax_h3_audio_vae_fp32.safetensors"
LORA_8  = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
LORA_4  = "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"


def snap_frames(seconds: float) -> int:
    """Model accepts 17k+5 frame counts at 24fps. Round up to the grid."""
    n = max(5, round(seconds * 24))
    return n + (5 - (n % 17)) % 17


def build(mode, prompt, width, height, length, steps, seed, lora, strength,
          image=None, last_image=None, fps=24.0, prefix="video/MiniMax_H3"):
    g = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": MODEL, "weight_dtype": "default"}},
        "2": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["1", 0], "lora_name": lora,
                         "strength_model": strength}},
        "3": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": CLIP, "type": "minimax", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_VID}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_AUD}},
        "6": {"class_type": "MiniMaxH3ImageToVideo",
              "inputs": {"clip": ["3", 0], "vae": ["4", 0], "prompt": prompt,
                         "width": width, "height": height, "length": length}},
        "7": {"class_type": "BasicGuider",
              "inputs": {"model": ["2", 0], "conditioning": ["6", 0]}},
        "8": {"class_type": "KSamplerSelect",
              "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler",
              "inputs": {"model": ["2", 0], "scheduler": "simple",
                         "steps": steps, "denoise": 1.0}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced",
               "inputs": {"noise": ["10", 0], "guider": ["7", 0],
                          "sampler": ["8", 0], "sigmas": ["9", 0],
                          "latent_image": ["6", 1]}},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
        "13": {"class_type": "VAEDecodeAudio",
               "inputs": {"samples": ["11", 0], "vae": ["5", 0]}},
        "14": {"class_type": "CreateVideo",
               "inputs": {"images": ["12", 0], "audio": ["13", 0], "fps": fps}},
        "15": {"class_type": "SaveVideo",
               "inputs": {"video": ["14", 0], "filename_prefix": prefix,
                          "format": "auto", "codec": "auto"}},
    }
    if mode == "i2v":
        if not image:
            sys.exit("i2v needs --image (a file in the inputs/ directory)")
        g["20"] = {"class_type": "LoadImage", "inputs": {"image": image}}
        g["6"]["inputs"]["first_frame"] = ["20", 0]
        if last_image:
            g["21"] = {"class_type": "LoadImage", "inputs": {"image": last_image}}
            g["6"]["inputs"]["last_frame"] = ["21", 0]
    return g


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(json.dumps(err, indent=2)[:4000], file=sys.stderr)
        except Exception:
            print(body[:4000], file=sys.stderr)
        sys.exit(f"ComfyUI rejected the prompt (HTTP {e.code})")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["t2v", "i2v"])
    p.add_argument("prompt")
    p.add_argument("--image", help="first frame, filename inside inputs/")
    p.add_argument("--last-image", help="optional last frame (FLF2V)")
    p.add_argument("--seconds", type=float, default=2.0)
    p.add_argument("--width", type=int, default=848)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--steps", type=int, default=8)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--lora", choices=["8step", "4step"], default="8step")
    p.add_argument("--lora-strength", type=float, default=1.0)
    p.add_argument("--host", default="http://127.0.0.1:8188")
    p.add_argument("--dry-run", action="store_true",
                   help="print the graph instead of submitting")
    a = p.parse_args()

    length = snap_frames(a.seconds)
    lora = LORA_8 if a.lora == "8step" else LORA_4
    g = build(a.mode, a.prompt, a.width, a.height, length, a.steps, a.seed,
              lora, a.lora_strength, a.image, a.last_image)

    if a.dry_run:
        print(json.dumps(g, indent=2)); return

    print(f"{a.mode}: {a.width}x{a.height} {length}f (~{length/24:.1f}s) "
          f"{a.steps} steps, {a.lora}")
    r = post(f"{a.host}/prompt", {"prompt": g})
    pid = r["prompt_id"]
    print("queued", pid)

    while True:
        h = json.load(urllib.request.urlopen(f"{a.host}/history/{pid}"))
        if pid in h:
            st = h[pid]["status"]
            print("status:", st.get("status_str"))
            for out in h[pid]["outputs"].values():
                for vids in out.values():
                    for v in vids:
                        if isinstance(v, dict) and "filename" in v:
                            print("OUTPUT:", v["filename"])
            if not st.get("completed"):
                print(json.dumps(st.get("messages", []), indent=2)[:3000])
                sys.exit(1)
            return
        time.sleep(3)


if __name__ == "__main__":
    main()
