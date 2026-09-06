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

echo [1/5] Syncing dependencies (uv sync)...
uv sync
if errorlevel 1 (
    echo.
    echo [FAIL] Dependency sync failed. See output above.
    exit /b 1
)

echo.
echo [2/5] Checking local configuration...
if not exist "data" mkdir "data"
if not exist "data\config.toml" (
    if exist "config.toml.example" (
        copy /Y "config.toml.example" "data\config.toml" >nul
        echo       Created data\config.toml from config.toml.example
    ) else (
        echo [FAIL] config.toml.example not found; cannot create data\config.toml.
        exit /b 1
    )
) else (
    echo       data\config.toml already exists
)

echo.
echo [3/5] Verifying CAN Research CLI...
uv run canresearch --help >nul 2>&1
if errorlevel 1 (
    echo [FAIL] CAN Research CLI did not start. See output above.
    exit /b 1
)

echo.
echo [4/5] Current configuration:
uv run canresearch config show
if errorlevel 1 (
    echo [WARN] config show reported a problem.
)

echo.
echo [5/5] Preparing OpenAI tunnel client...
uv run python scripts\tunnel_windows.py install
if errorlevel 1 (
    echo.
    echo [FAIL] OpenAI tunnel client setup is incomplete.
    echo        CAN Research itself is installed, but ChatGPT MCP will not work yet.
    echo        See docs\MCP_SETUP.md and rerun setup.cmd after tunnel-client.exe is available.
    exit /b 1
)
uv run python scripts\tunnel_windows.py show

echo.
echo ============================================================
echo   Setup complete
echo ============================================================
echo.
echo Next steps:
echo   1. Edit data\config.toml if needed (instance, CANsub, tunnel profile)
echo   2. Ensure the OpenAI tunnel profile and CONTROL_PLANE_API_KEY already exist
echo   3. Run start-can-research.cmd - it starts BOTH MCP and the OpenAI tunnel
echo   4. Run status.cmd for an end-to-end local/tunnel health check
echo   5. Use the existing ChatGPT connector; do NOT recreate it after reboot
echo   6. Install bundled Skills from skills\dist\ if not already installed
echo.
echo OpenAI tunnel setup: docs\MCP_SETUP.md
echo Quick health check anytime: status.cmd
echo.
exit /b 0
