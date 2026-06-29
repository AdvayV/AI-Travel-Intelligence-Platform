@echo off
echo ============================================
echo   SabreRoute Intelligence - Auto Launcher
echo ============================================

cd /d "%~dp0"

REM Check if venv exists, create if not
IF NOT EXIST "venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
    IF ERRORLEVEL 1 (
        echo ERROR: Could not create venv. Make sure Python is installed.
        pause
        exit /b 1
    )
) ELSE (
    echo [1/4] Virtual environment found, skipping creation.
)

REM Activate venv
echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements
echo [3/4] Installing/updating requirements...
cd backend
pip install -r requirements.txt --quiet
IF ERRORLEVEL 1 (
    echo ERROR: pip install failed. See above for details.
    pause
    exit /b 1
)

REM Start the server
echo [4/4] Starting FastAPI backend on http://127.0.0.1:8000 ...
echo.
echo  Press CTRL+C to stop the server.
echo ============================================
python -m uvicorn main:app --reload --port 8000

pause
