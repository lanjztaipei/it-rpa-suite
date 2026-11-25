@echo off
setlocal
cd /d "%~dp0"

set "SLOW_MO=%~1"
if "%SLOW_MO%"=="" set "SLOW_MO=500"

set "IT_SUITE_SLOW_MO=%SLOW_MO%"
set "IT_SUITE_SANDBOX_MODE=true"

echo ========================================================
echo   IT RPA Suite - Demo ^& Onboarding Training Mode
echo   Playwright slow_mo : %IT_SUITE_SLOW_MO% ms
echo   Sandbox Mode       : enabled (offline safe mode)
echo   Tip: Pass a custom delay, e.g. start_demo_training.bat 600
echo ========================================================
echo.

if exist "%~dp0ITRPASuite.exe" (
    echo [LAUNCH] Starting packaged ITRPASuite.exe ...
    "%~dp0ITRPASuite.exe"
    goto :done
)

if exist "%~dp0ITRPASuite\ITRPASuite.exe" (
    echo [LAUNCH] Starting packaged ITRPASuite\ITRPASuite.exe ...
    "%~dp0ITRPASuite\ITRPASuite.exe"
    goto :done
)

where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [LAUNCH] Starting via uv run python main.py ...
    uv run python main.py
    goto :done
)

echo [LAUNCH] uv not found, falling back to python main.py ...
python main.py

:done
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
endlocal
