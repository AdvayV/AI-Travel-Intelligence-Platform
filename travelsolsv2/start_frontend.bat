@echo off
echo ============================================
echo   TravelRoute Intelligence v2 - Frontend
echo ============================================
cd /d "%~dp0frontend"

echo Installing npm packages...
call npm install

echo Starting frontend on http://localhost:5174 ...
call npm run dev
pause
