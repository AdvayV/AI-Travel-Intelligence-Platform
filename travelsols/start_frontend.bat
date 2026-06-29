@echo off
echo ============================================
echo   SabreRoute Intelligence - Frontend
echo ============================================

cd /d "%~dp0frontend"

echo [1/2] Installing npm packages...
call npm install

echo [2/2] Starting frontend on http://localhost:5173 ...
echo.
echo  Press CTRL+C to stop.
echo ============================================
call npm run dev

pause
