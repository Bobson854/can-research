# Publish a CAN Research release: bump version, build, test, tag, push.
# GitHub Actions (.github/workflows/release.yml) publishes the Release asset when the tag lands.
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [switch]$DryRun,

    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

function Invoke-Git {
    param([string[]]$GitArgs)

    # Windows PowerShell 5.1 converts native stderr into ErrorRecord objects.
    # With the script-wide ErrorActionPreference = Stop, harmless git status/progress
    # output (for example from git fetch) can otherwise terminate the script even
    # when git exits successfully. Temporarily allow native stderr, then decide
    # success strictly from git's exit code.
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & git @GitArgs 2>&1
        $gitExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($gitExitCode -ne 0) {
        Fail ("git {0} failed: {1}" -f ($GitArgs -join " "), ($output -join "`n"))
    }
    return $output
}

function Test-GitAvailable {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Fail "git is not on PATH."
    }
}

function Test-UvAvailable {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail "uv is not on PATH."
    }
}

function Test-CanResearchNotRunning {
    $processes = @(Get-Process -Name "canresearch" -ErrorAction SilentlyContinue)
    if ($processes.Count -gt 0) {
        $pids = ($processes | ForEach-Object { $_.Id }) -join ", "
        Fail "canresearch.exe is running (PID(s): $pids). Stop the CAN Research MCP/server before publishing, then retry. No release files have been modified."
    }
}

function Get-CurrentVersion {
    $result = & uv run python scripts/publish_release.py read-version
    if ($LASTEXITCODE -ne 0) { Fail "Could not read current version from pyproject.toml." }
    return ($result | Select-Object -Last 1).Trim()
}

function Get-ReleaseTag {
    param([string]$ReleaseVersion)
    $result = & uv run python scripts/publish_release.py tag-for-version --version $ReleaseVersion
    if ($LASTEXITCODE -ne 0) {
        Fail "Invalid release version: $ReleaseVersion"
    }
    return ($result | Select-Object -Last 1).Trim()
}

function Get-ArtifactPath {
    param([string]$ReleaseVersion)
    $result = & uv run python scripts/publish_release.py artifact-path --version $ReleaseVersion
    if ($LASTEXITCODE -ne 0) { Fail "Could not resolve artifact path for version $ReleaseVersion." }
    return ($result | Select-Object -Last 1).Trim()
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  CAN Research - Publish release"
Write-Host "============================================================"
Write-Host "  Repository: $RepoRoot"
Write-Host "  Requested:  v$Version"
if ($DryRun) { Write-Host "  Mode:       DRY RUN (no commit/tag/push)" }
Write-Host ""

Test-GitAvailable
Test-UvAvailable
Test-CanResearchNotRunning

& uv run python scripts/publish_release.py validate-version --version $Version | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Version must match semantic versioning X.Y.Z: $Version" }

$currentVersion = Get-CurrentVersion
if ($currentVersion -eq $Version) {
    Fail "Requested version $Version is already the current pyproject.toml version."
}

$tag = Get-ReleaseTag -ReleaseVersion $Version

$branch = (Invoke-Git @("branch", "--show-current")).Trim()
if ($branch -ne "main") {
    Fail "Current branch is '$branch'. Switch to main before publishing."
}

if (-not $AllowDirty) {
    $porcelain = Invoke-Git @("status", "--porcelain")
    if ($porcelain) {
        Fail "Working tree is dirty. Commit or stash changes, or pass -AllowDirty to override.`n$($porcelain -join "`n")"
    }
} else {
    Write-Host "[WARN] AllowDirty set - continuing with uncommitted changes."
}

Invoke-Git @("fetch", "origin") | Out-Null

$localMain = (Invoke-Git @("rev-parse", "main")).Trim()
$remoteMain = (Invoke-Git @("rev-list", "-n", "1", "origin/main")).Trim()

if ($localMain -ne $remoteMain) {
    $ahead = (Invoke-Git @("rev-list", "--count", "origin/main..main")).Trim()
    $behind = (Invoke-Git @("rev-list", "--count", "main..origin/main")).Trim()
    if ([int]$behind -gt 0) {
        Fail "local main is behind origin/main by $behind commit(s). Run 'git pull' on main first."
    }
    if ([int]$ahead -gt 0 -and -not $DryRun) {
        Write-Host "[INFO] local main is ahead of origin/main by $ahead commit(s); push will publish those commits too."
    }
}

try {
    & git rev-parse $tag 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Fail "Tag $tag already exists locally."
    }
} catch {
    # tag absent - expected
}

$remoteTag = & git ls-remote --tags origin "refs/tags/$tag" 2>$null
if ($LASTEXITCODE -eq 0 -and $remoteTag) {
    Fail "Tag $tag already exists on origin."
}

Write-Host "[OK]   Git preflight passed"
Write-Host "       Current version: $currentVersion"
Write-Host "       Target version:  $Version"
Write-Host "       Tag:             $tag"

if ($DryRun) {
    Write-Host ""
    Write-Host "[DRY RUN] Would execute:"
    Write-Host "  uv run python scripts/publish_release.py bump-version --version $Version"
    Write-Host "  uv lock"
    Write-Host "  ./scripts/build-release.ps1"
    Write-Host "  uv run pytest tests/test_release_build.py -q"
    Write-Host "  git add pyproject.toml uv.lock"
    Write-Host "  git commit -m `"Release v$Version`""
    Write-Host "  git tag -a $tag -m `"Release v$Version`""
    Write-Host "  git push origin main"
    Write-Host "  git push origin $tag"
    Write-Host ""
    Write-Host "Pushing tag $tag triggers .github/workflows/release.yml on GitHub Actions,"
    Write-Host "which rebuilds the ZIP, runs release tests, and uploads:"
    Write-Host "  dist/releases/CAN-Research-v$Version-windows.zip"
    exit 0
}

Write-Host ""
Write-Host "[1/6] Bumping pyproject.toml version..."
& uv run python scripts/publish_release.py bump-version --version $Version
if ($LASTEXITCODE -ne 0) { Fail "Version bump failed." }

Write-Host "[2/6] Refreshing uv.lock..."
& uv lock
if ($LASTEXITCODE -ne 0) { Fail "uv lock failed." }

Write-Host "[3/6] Building release ZIP..."
& "$PSScriptRoot/build-release.ps1"
if ($LASTEXITCODE -ne 0) { Fail "Release build failed." }

$artifact = Get-ArtifactPath -ReleaseVersion $Version
if (-not (Test-Path $artifact)) {
    Fail "Expected release artifact not found: $artifact"
}
$item = Get-Item $artifact
Write-Host ('       Artifact: {0} ({1} bytes)' -f $item.FullName, $item.Length)

Write-Host "[4/6] Running release tests..."
& uv run pytest tests/test_release_build.py -q
if ($LASTEXITCODE -ne 0) { Fail "Release tests failed." }

Write-Host ""
Write-Host "============================================================"
Write-Host "  Release summary"
Write-Host "============================================================"
Write-Host "  Version:  $Version"
Write-Host "  Tag:      $tag"
Write-Host "  Artifact: $artifact"
Write-Host "  Commit:   Release v$Version"
Write-Host ""
Write-Host "  Next Git operations are irreversible without manual cleanup."
Write-Host "  Press Enter to commit, tag, and push - Ctrl+C to abort."
Write-Host "============================================================"
[void][System.Console]::ReadLine()

Write-Host "[5/6] Committing and tagging..."
Invoke-Git @("add", "pyproject.toml", "uv.lock") | Out-Null
Invoke-Git @("commit", "-m", "Release v$Version") | Out-Null
Invoke-Git @("tag", "-a", $tag, "-m", "Release v$Version") | Out-Null

Write-Host "[6/6] Pushing to origin..."
Invoke-Git @("push", "origin", "main") | Out-Null
Invoke-Git @("push", "origin", $tag) | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "  Publish complete"
Write-Host "============================================================"
Write-Host "  Pushed $tag to origin."
Write-Host "  GitHub Actions will run .github/workflows/release.yml:"
Write-Host "    uv sync --extra dev"
Write-Host "    ./scripts/build-release.ps1"
Write-Host "    uv run pytest tests/test_release_build.py -q"
Write-Host "    upload dist/releases/CAN-Research-v$Version-windows.zip"
Write-Host ""
Write-Host "  Monitor the workflow run on GitHub before announcing the release."
Write-Host "============================================================"
Write-Host ""
