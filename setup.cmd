@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ============================================================
echo   CAN Research - Setup
echo ============================================================
echo   Install directory: %CD%
echo.

where uv >nul 2>&1
if errorlevel 1 (
    echo [FAIL] uv is not installed or not on PATH.
    echo.
    echo CAN Research uses uv to manage Python and dependencies.
    echo.
    echo Install uv, then run setup.cmd again:
    echo   https://docs.astral.sh/uv/getting-started/installation/
    echo.
    echo Windows PowerShell one-liner:
    echo   irm https://astral.sh/uv/install.ps1 ^| iex
    echo   Then open a NEW terminal and run setup.cmd again.
    echo.
    echo Python 3.11+ is required. uv installs it automatically on first sync.
    echo Full prerequisites: docs\INSTALLATION.md
    exit /b 1
)

echo [1/4] Syncing dependencies (uv sync)...
uv sync
if errorlevel 1 (
    echo.
    echo [FAIL] Dependency sync failed. See output above.
    exit /b 1
)

echo.
echo [2/4] Checking local configuration...
if not exist "data" mkdir "data"
if not exist "data\config.toml" (
    if exist "config.toml.example" (
        copy /Y "config.toml.example" "data\config.toml" >nul
        echo       Created data\config.toml from config.toml.example
    ) else (
        echo [WARN] config.toml.example not found; create data\config.toml manually.
    )
) else (
    echo       data\config.toml already exists
)

echo.
echo [3/4] Verifying CAN Research CLI...
uv run canresearch --help >nul 2>&1
if errorlevel 1 (
    echo [FAIL] CAN Research CLI did not start. See output above.
    exit /b 1
)

echo.
echo [4/4] Current configuration:
uv run canresearch config show
if errorlevel 1 (
    echo [WARN] config show reported a problem.
)

echo.
echo ============================================================
echo   Setup complete
echo ============================================================
echo.
echo Next steps:
echo   1. Connect CANsub.2  - see docs\CANSUB_SETUP.md
echo   2. Edit data\config.toml if needed (CANsub hostname, instance name)
echo   3. Run start-can-research.cmd to start the MCP service
echo   4. Open docs\AI_INTEGRATION.md and connect your AI frontend
echo   5. Install bundled Skills from skills\dist\ — docs\SKILL_INSTALLATION.md
echo   6. Start can-onboarding in ChatGPT
echo.
echo Quick health check anytime: status.cmd
echo Developer details: docs\INSTALLATION.md
echo.
exit /b 0
