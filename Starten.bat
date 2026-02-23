@echo off
title LaTeX Quellen Manager v4.1
echo Starte LaTeX Quellen Manager...
echo.

REM ── Alten Server auf Port 5000 beenden (falls noch aktiv) ──────────────────
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 " ^| findstr "LISTEN"') do (
    echo Beende alten Server-Prozess PID %%a ...
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM ── Prüfe ob Flask installiert ist ────────────────────────────────────────
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Flask wird installiert...
    pip install flask
    echo.
)

REM ── Starte die Anwendung ──────────────────────────────────────────────────
python "%~dp0latex_quellen_manager.py"

pause
