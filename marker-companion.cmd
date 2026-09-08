@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo [FAIL] uv is not installed. Run setup.cmd after installing uv.
    exit /b 1
)

if not exist "data\config.toml" (
    echo [FAIL] data\config.toml not found. Run setup.cmd first.
    exit /b 1
)

echo.
echo ============================================================
echo   CAN Research - Capture marker companion
echo ============================================================
echo   Passive annotation only. Start live capture first.
echo.

uv run python scripts\marker_companion.py %*
exit /b %ERRORLEVEL%
