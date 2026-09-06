@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set FAIL=0

echo.
echo ============================================================
echo   CAN Research - Status
echo ============================================================
echo   Install directory: %CD%
echo.

where uv >nul 2>&1
if errorlevel 1 (
    echo [FAIL] uv not on PATH - run setup.cmd after installing uv
    set FAIL=1
    goto :done
)
echo [OK]   uv available

if not exist "data\config.toml" (
    echo [FAIL] data\config.toml missing - run setup.cmd
    set FAIL=1
) else (
    echo [OK]   data\config.toml present
)

echo.
echo --- Configuration ---
uv run canresearch config show
if errorlevel 1 (
    echo [FAIL] CAN Research CLI or configuration
    set FAIL=1
) else (
    echo [OK]   CAN Research CLI responds
)

echo.
echo --- MCP (http://127.0.0.1:8765/mcp) ---
uv run python scripts\mcp_verify_http.py --url http://127.0.0.1:8765/mcp
if errorlevel 1 (
    echo [FAIL] MCP not reachable or tool registry mismatch
    echo        Run start-can-research.cmd
    set FAIL=1
) else (
    echo [OK]   MCP endpoint healthy
)

echo.
echo --- OpenAI tunnel ---
uv run python scripts\tunnel_windows.py status
if errorlevel 1 (
    echo [FAIL] OpenAI tunnel is not ready
    echo        Run start-can-research.cmd
    echo        Do NOT recreate the ChatGPT connector just because the tunnel is stopped
    set FAIL=1
) else (
    echo [OK]   OpenAI tunnel health listener reachable
)

echo.
echo --- CANsub.2 (uses configured host) ---
uv run canresearch device info
if errorlevel 1 (
    echo [SKIP] CANsub not reachable or not configured yet
    echo        See docs\CANSUB_SETUP.md
) else (
    echo [OK]   CANsub device responded
)

:done
echo.
echo ============================================================
if %FAIL%==0 (
    echo   Overall: AI connection prerequisites passed
) else (
    echo   Overall: one or more checks failed - see messages above
)
echo ============================================================
echo.
exit /b %FAIL%
