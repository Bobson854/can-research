@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo [FAIL] uv is not installed. Run setup.cmd after installing uv.
    echo   https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)

if not exist "data\config.toml" (
    echo [WARN] data\config.toml not found. Run setup.cmd first.
    echo.
)

echo.
echo ============================================================
echo   CAN Research - MCP service
echo ============================================================
echo   Install directory: %CD%
echo   Endpoint:          http://127.0.0.1:8765/mcp
echo   Transport:         streamable-http
echo.
echo   Leave this window open while using CAN Research with AI.
echo   To stop the service, close this window or press Ctrl+C.
echo.
echo   Health check (another window): status.cmd
echo   AI connection guide: docs\AI_INTEGRATION.md
echo ============================================================
echo.

uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
set EXIT_CODE=%ERRORLEVEL%

echo.
echo MCP service stopped (exit code %EXIT_CODE%).
exit /b %EXIT_CODE%
