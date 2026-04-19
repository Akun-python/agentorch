@echo off
setlocal
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_codexharness.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo codexharness finished.
) else (
    echo codexharness failed with exit code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
