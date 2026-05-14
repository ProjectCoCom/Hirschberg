@echo off
title JAT-AI Installer
echo.
echo  ========================================
echo   JAT-AI - Installing...
echo  ========================================
echo.

where pnpm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pnpm is required for the dashboard. Install pnpm first, then rerun this installer.
    pause
    exit /b 1
)

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..

:: Step 1: Install Python dependencies
echo [1/3] Installing Python dependencies...
pip install --quiet --progress-bar on -e "%ROOT%"
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] pip failed, trying pip3...
    pip3 install --quiet --progress-bar on -e "%ROOT%"
)
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Could not install dependencies. Make sure Python and pip are on PATH.
    pause
    exit /b 1
)
echo [OK] Python dependencies installed.

:: Step 2: Install frontend dependencies
echo [2/3] Checking frontend dependencies...
if not exist "%ROOT%\dashboard\node_modules" (
    echo       Installing pnpm packages...
    cd /d "%ROOT%\dashboard"
    pnpm install
    echo [OK] Frontend dependencies installed.
) else (
    echo [OK] Frontend already installed.
)

:: Step 3: Setup jat command and PATH
echo [3/3] Setting up jat command...
set TARGET=%USERPROFILE%\jat.cmd
echo @echo off > "%TARGET%"
echo call "%SCRIPT_DIR%jat.bat" %%* >> "%TARGET%"

echo %PATH% | findstr /i "%USERPROFILE%" >nul
if %ERRORLEVEL% NEQ 0 (
    setx PATH "%PATH%;%USERPROFILE%"
    echo [OK] Added %USERPROFILE% to PATH.
) else (
    echo [OK] PATH already configured.
)

echo.
echo  ========================================
echo   JAT-AI installed successfully!
echo   First run may download embedding models (~100MB).
echo   Open a new terminal and type: jat
echo  ========================================
echo.
pause
