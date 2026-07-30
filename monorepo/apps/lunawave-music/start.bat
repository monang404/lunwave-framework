@echo off
color 0B
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo  _      _    _  _   _   ___   __    __   ___  __      __ _____
echo ^| ^|    ^| ^|  ^| ^|^| \ ^| ^| / _ \  \ \  / /  / _ \ \ \    / /^|  ___^|
echo ^| ^|    ^| ^|  ^| ^|^|  \ ^| ^|/ /_\ \  \ \/ /  / /_\ \ \ \  / / ^| ^|__
echo ^| ^|___ ^| ^|__^| ^|^| ^|\  ^|  ___  \  \  /\  /  ___  \ \ \/ /  ^|  __^|
echo ^|_____^| \____/^|_^| \_/_/_/   \_\  \/  \/_/_/   \_\  \__/   ^|_____^|
echo.
echo    ================================================================
echo                      LunaWave Web Server Startup
echo    ================================================================
echo.

:: ----------------------------------------------------------
::  CONFIGURATION
:: ----------------------------------------------------------
set "LUNAWAVE_HOST=0.0.0.0"
set "LUNAWAVE_PORT=8765"

:: support legacy environment variables if set
if defined YTGUI_HOST set "LUNAWAVE_HOST=%YTGUI_HOST%"
if defined YTGUI_PORT set "LUNAWAVE_PORT=%YTGUI_PORT%"
if defined YTGUI_ADMIN_USER set "LUNAWAVE_ADMIN_USER=%YTGUI_ADMIN_USER%"
if defined YTGUI_ADMIN_PASS set "LUNAWAVE_ADMIN_PASS=%YTGUI_ADMIN_PASS%"

:: ----------------------------------------------------------
::  STARTUP SEQUENCE
:: ----------------------------------------------------------

echo  [*] Initializing Environment Variables...

python -m launcher.preflight --host "%LUNAWAVE_HOST%" --port "%LUNAWAVE_PORT%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo  [X] Preflight check failed. Server will not start.
    pause
    exit /b 1
)

echo  [*] Cleaning Up Previous Sessions...
taskkill /F /IM mpv.exe > nul 2>&1

:: ----------------------------------------------------------
::  ADMIN ACCESS INFO
:: ----------------------------------------------------------
echo.
echo  ----------------------------------------------------------------
echo   Admin Access Information
echo  ----------------------------------------------------------------
if defined LUNAWAVE_ADMIN_PASS (
    echo   [i] Password loaded from environment variable LUNAWAVE_ADMIN_PASS.
) else (
    if exist "cache\admin_password.txt" (
        echo   [i] Password stored securely in: cache\admin_password.txt
    ) else (
        echo   [i] A new password will be auto-generated on first launch.
    )
)
if defined LUNAWAVE_ADMIN_USER (
    echo   [i] Username: %LUNAWAVE_ADMIN_USER%
) else (
    echo   [i] Username: admin
)

:: ----------------------------------------------------------
::  SERVER STARTUP
:: ----------------------------------------------------------
echo.
echo    ================================================================
echo       Client Interface : http://localhost:%LUNAWAVE_PORT%/
echo       Admin Interface  : http://localhost:%LUNAWAVE_PORT%/admin
echo       System Health    : http://localhost:%LUNAWAVE_PORT%/health
echo       Metrics          : http://localhost:%LUNAWAVE_PORT%/metrics
echo    ================================================================
echo.
echo  [*] Starting Server...

python main.py
echo.
if %ERRORLEVEL% neq 0 (
    echo  [X] Server terminated with error code: %ERRORLEVEL%
    echo      Please check the application logs for details.
)
pause
