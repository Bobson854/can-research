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

for /f "usebackq delims=" %%L in (`uv run python scripts\tunnel_windows.py env`) do %%L
if not exist "%TUNNEL_EXE%" (
    echo [FAIL] OpenAI tunnel client is not installed at:
    echo        %TUNNEL_EXE%
    echo        Run setup.cmd to migrate/install it.
    exit /b 1
)

echo.
echo ============================================================
echo   CAN Research - Start AI services
echo ============================================================
echo   MCP endpoint:  http://127.0.0.1:8765/mcp
echo   Tunnel:        %TUNNEL_PROFILE%
echo   Tunnel health: %TUNNEL_HEALTH_HOST%:%TUNNEL_HEALTH_PORT%
echo.

uv run python scripts\mcp_verify_http.py >nul 2>&1
if errorlevel 1 (
    echo [INFO] Starting CAN Research MCP in a new window...
    start "CAN Research MCP" /D "%CD%" cmd /k uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
    call :wait_mcp
    if errorlevel 1 (
        echo [FAIL] MCP did not become healthy within 12 seconds.
        echo        Check the "CAN Research MCP" window.
        exit /b 1
    )
) else (
    echo [OK]   MCP already running and healthy
)

echo [OK]   MCP registry verified

uv run python scripts\tunnel_windows.py status >nul 2>&1
if errorlevel 1 (
    if "%CONTROL_PLANE_API_KEY%"=="" (
        echo [FAIL] CONTROL_PLANE_API_KEY is not available in this terminal.
        echo        If it was set with setx, close this terminal and open a new one.
        exit /b 1
    )

    echo [INFO] Checking OpenAI tunnel profile...
    "%TUNNEL_EXE%" doctor --profile "%TUNNEL_PROFILE%" --explain --health.listen-addr %TUNNEL_HEALTH_HOST%:%TUNNEL_HEALTH_PORT%
    if errorlevel 1 (
        echo [FAIL] Tunnel doctor failed. Do not recreate the ChatGPT connector.
        echo        Fix the profile/API-key issue shown above, then rerun this command.
        exit /b 1
    )

    echo [INFO] Starting OpenAI tunnel in a new window...
    start "OpenAI Tunnel - %TUNNEL_PROFILE%" /D "%TUNNEL_DIR%" cmd /k tunnel-client.exe run --profile "%TUNNEL_PROFILE%" --health.listen-addr %TUNNEL_HEALTH_HOST%:%TUNNEL_HEALTH_PORT%
    call :wait_tunnel
    if errorlevel 1 (
        echo [FAIL] Tunnel health listener did not become reachable within 12 seconds.
        echo        Check the "OpenAI Tunnel" window.
        exit /b 1
    )
) else (
    echo [OK]   OpenAI tunnel already running
)

echo.
echo ============================================================
echo   CAN Research is ready for ChatGPT
echo ============================================================
echo   Use the EXISTING ChatGPT connector for %TUNNEL_PROFILE%.
echo   Do not recreate the connector after reboot.
echo   Run status.cmd any time for diagnostics.
echo.
exit /b 0

:wait_mcp
for /L %%I in (1,1,12) do (
    timeout /t 1 /nobreak >nul
    uv run python scripts\mcp_verify_http.py >nul 2>&1
    if not errorlevel 1 exit /b 0
)
exit /b 1

:wait_tunnel
for /L %%I in (1,1,12) do (
    timeout /t 1 /nobreak >nul
    uv run python scripts\tunnel_windows.py status >nul 2>&1
    if not errorlevel 1 exit /b 0
)
exit /b 1
