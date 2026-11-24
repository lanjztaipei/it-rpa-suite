@echo off
cd /d "%~dp0"

echo ========================================================
echo   IT RPA Suite - Packaging Release
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_release.ps1"

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo   [SUCCESS] Packaging finished!
    echo   Output: released\ITRPASuite.zip
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo   [ERROR] Packaging failed! Exit Code: %ERRORLEVEL%
    echo ========================================================
)

echo.
pause
