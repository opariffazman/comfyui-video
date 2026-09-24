# Launch ComfyUI for MiniMax H3 (Windows). Flags are picked in scripts\launch.py.
#
# Tunables (env vars, e.g. $env:PORT = "8189"):
#   PORT=8188          port to serve on
#   FAST_DISK=1        offload to NVMe instead of system RAM (default on below 20GB VRAM)
#   RESERVE_VRAM=1.5   GB of VRAM to leave for the desktop
#   EXTRA="--fast"     extra flags passed through to main.py
$ErrorActionPreference = "Stop"
$R = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $R ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Error "No .venv found at $Py. Run scripts\setup.ps1 first."
}
& $Py (Join-Path $R "scripts\launch.py") @args
exit $LASTEXITCODE
