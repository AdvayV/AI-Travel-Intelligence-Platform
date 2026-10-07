@echo off
setlocal
cd /d "%~dp0frontend" || goto failed
"%SystemRoot%\System32\where.exe" node >nul 2>&1
if errorlevel 1 goto failed
"%SystemRoot%\System32\where.exe" npm.cmd >nul 2>&1
if errorlevel 1 goto failed
if /i "%~1"=="--install" goto install
if exist "node_modules\.bin\vite.cmd" goto run
:install
echo Installing v2 frontend dependencies...
call npm.cmd install
if errorlevel 1 goto failed
:run
echo Starting v2 frontend: http://127.0.0.1:5174
call npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort
if errorlevel 1 goto failed
exit /b 0
:failed
echo ERROR: v2 frontend startup failed. Check Node.js, npm and the output above.
if not defined TRAVELROUTE_NO_PAUSE pause
exit /b 1
