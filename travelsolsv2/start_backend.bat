@echo off
echo ============================================
echo   TravelRoute Intelligence v2 - Backend
echo ============================================
cd /d "%~dp0backend"

REM Check if venv exists, create if not
IF NOT EXIST "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing requirements...
"venv\Scripts\pip.exe" install -r requirements.txt

echo Starting FastAPI backend on http://127.0.0.1:8001 ...
"venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8001
pause
