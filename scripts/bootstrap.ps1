# Fresh Windows machine, nothing installed: installs git, clones this repo, runs setup.ps1.
# setup.ps1 then installs uv, Python 3.12, ComfyUI, and the models.
#
# Run in PowerShell (no admin needed; the Git installer shows one UAC prompt):
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/opariffazman/comfyui-video/main/scripts/bootstrap.ps1)))
# Options (append after the closing parenthesis):
#   -Dir D:\comfyui-video   clone location (default: $HOME\comfyui-video). Pick an NVMe drive.
#   -NoR2V                  skip the 22GB R2V weights
#   -SkipModels             software only
param(
    [string]$Dir = (Join-Path $HOME "comfyui-video"),
    [switch]$NoR2V,
    [switch]$SkipModels
)
$ErrorActionPreference = "Stop"
$Repo = "https://github.com/opariffazman/comfyui-video.git"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Missing 'git' and winget is unavailable. Install Git from https://git-scm.com/download/win and re-run."
    }
    Write-Host "### Installing Git.Git with winget"
    winget install --id Git.Git --exact --source winget --silent `
        --accept-package-agreements --accept-source-agreements | Out-Host
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git install finished but 'git' is not on PATH. Open a new PowerShell window and re-run."
    }
}

if (Test-Path (Join-Path $Dir ".git")) {
    Write-Host "### Updating existing clone at $Dir"
    git -C $Dir pull --ff-only
} else {
    Write-Host "### Cloning into $Dir"
    git clone $Repo $Dir
}
if ($LASTEXITCODE -ne 0) { throw "git failed ($LASTEXITCODE) for $Dir" }

$setupArgs = @()
if ($NoR2V) { $setupArgs += "-NoR2V" }
if ($SkipModels) { $setupArgs += "-SkipModels" }
# -ExecutionPolicy Bypass applies to this child process only. It avoids a machine-wide policy change.
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dir "scripts\setup.ps1") @setupArgs
if ($LASTEXITCODE -ne 0) { throw "setup.ps1 failed ($LASTEXITCODE). Fix the error above, then re-run $Dir\scripts\setup.ps1." }

Write-Host ""
Write-Host "Done. Start with:"
Write-Host "  cd $Dir"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1"
