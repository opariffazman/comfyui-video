# One-shot setup (Windows 10/11, PowerShell). Safe to re-run: every step skips work already done.
#
#   .\scripts\setup.ps1               # full install, all models (~65GB)
#   .\scripts\setup.ps1 -NoR2V        # skip R2V weights (~43GB)
#   .\scripts\setup.ps1 -SkipModels   # software only
#
# Needs: git, uv (winget install astral-sh.uv), NVIDIA driver >= 580 (CUDA 13.0).
# If script execution is blocked:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
param([switch]$NoR2V, [switch]$SkipModels)
$ErrorActionPreference = "Stop"
$R = Split-Path -Parent $PSScriptRoot
Set-Location $R

# --- Pinned versions: change here, then re-run. Keep in sync with setup.sh ---
$ComfyTag = "v0.34.0"
$Python   = "3.12"
$Torch    = @("torch==2.13.0", "torchvision==0.28.0", "torchaudio==2.11.0")  # cu130: required by int8_convrot
$Sage     = "sageattention==1.0.6"
$Triton   = "triton-windows>=3.7,<3.8"  # SageAttention is pure Triton; Linux gets triton with torch

function Need($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Missing '$cmd'. Install it and re-run."
    }
}
function Run {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $($args -join ' ')" }
}

Need git; Need uv; Need nvidia-smi
$Driver = (nvidia-smi --query-gpu=driver_version --format=csv,noheader | Select-Object -First 1).Trim()
if ([int]($Driver.Split(".")[0]) -lt 580) {
    throw "NVIDIA driver $Driver is too old. torch cu130 needs >= 580. Update the driver and re-run."
}
$Gpu = (nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | Select-Object -First 1).Trim()
Write-Host "### GPU: $Gpu, driver $Driver"

Write-Host "### ComfyUI $ComfyTag"
if (-not (Test-Path "comfy\.git")) {
    Run git clone --branch $ComfyTag --depth 1 https://github.com/comfyanonymous/ComfyUI.git comfy
} else {
    git -C comfy rev-parse -q --verify "refs/tags/$ComfyTag" | Out-Null
    if ($LASTEXITCODE -ne 0) { Run git -C comfy fetch --quiet --depth 1 origin tag $ComfyTag }
    Run git -C comfy checkout --quiet $ComfyTag
}

Write-Host "### Python $Python venv"
if (-not (Test-Path ".venv\Scripts\python.exe")) { Run uv venv --python $Python .venv }

Write-Host "### Python packages"
Run uv pip install --python .venv --torch-backend cu130 @Torch `
    -r comfy\requirements.txt -r comfy\manager_requirements.txt huggingface_hub

Write-Host "### SageAttention (optional: launch falls back to default attention without it)"
& uv pip install --python .venv $Triton $Sage
if ($LASTEXITCODE -ne 0) { Write-Warning "SageAttention install failed. ComfyUI still runs, slower." }

foreach ($d in "models", "outputs", "inputs", "logs", "user") {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

if (-not $SkipModels) {
    Write-Host "### Models"
    $dl = @("scripts\download-models.py")
    if ($NoR2V) { $dl += "--no-r2v" }
    Run .venv\Scripts\python.exe @dl
}

Write-Host ""
Write-Host "Setup complete. Start with: .\scripts\start.ps1"
