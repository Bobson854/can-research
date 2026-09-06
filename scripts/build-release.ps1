# Build a versioned Windows release ZIP (see docs/RELEASING.md).
param(
    [string]$OutputDir = "",
    [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Error "uv is not on PATH. Install uv before building releases: https://docs.astral.sh/uv/getting-started/installation/"
}

$args = @("run", "python", "scripts/build_release.py")
if ($OutputDir) {
    $args += @("--output-dir", $OutputDir)
}
if ($KeepStaging) {
    $args += "--keep-staging"
}

& uv @args
exit $LASTEXITCODE
