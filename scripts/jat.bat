@echo off
title JAT-AI
echo.
echo  ========================================
echo   JAT-AI - Starting...
echo  ========================================
echo.

set "ROOT=%~dp0.."
set BACKEND_PORT=8000
set FRONTEND_PORT=3000

where pnpm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pnpm is required to start the dashboard. Install pnpm first.
    pause
    exit /b 1
)

if not exist "%ROOT%\.env" (
    echo [ERROR] .env file not found. Copy .env.example and fill in your keys.
    pause
    exit /b 1
)

if not exist "%ROOT%\.cache\deps_installed" (
    echo [SETUP] Installing Python dependencies...
    pip install --quiet -e "%ROOT%"
    if not exist "%ROOT%\.cache" mkdir "%ROOT%\.cache"
    echo done > "%ROOT%\.cache\deps_installed"
)

if not exist "%ROOT%\dashboard\node_modules" (
    echo [SETUP] Installing dashboard dependencies...
    cd /d "%ROOT%\dashboard"
    pnpm install
)

echo [BACKEND] Starting FastAPI on port %BACKEND_PORT%...
cd /d "%ROOT%"
start /b "" python -m uvicorn api.server:app --port %BACKEND_PORT% --reload --app-dir src

echo [BACKEND] Waiting for server...
:wait_backend
timeout /t 1 /nobreak >nul
curl -s http://localhost:%BACKEND_PORT%/api/setup >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto wait_backend
echo [BACKEND] Ready on http://localhost:%BACKEND_PORT%

echo [FRONTEND] Starting Vite on port %FRONTEND_PORT%...
cd /d "%ROOT%\dashboard"
start /b "" pnpm exec vite --port %FRONTEND_PORT%

:wait_frontend
timeout /t 1 /nobreak >nul
curl -s http://localhost:%FRONTEND_PORT% >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto wait_frontend
echo [FRONTEND] Ready on http://localhost:%FRONTEND_PORT%

echo.
echo  ========================================
echo   JAT-AI running at http://localhost:%FRONTEND_PORT%
echo   Press Ctrl+C to stop
echo  ========================================
echo.
start "" http://localhost:%FRONTEND_PORT%

:loop
timeout /t 5 /nobreak >nul
goto loop
