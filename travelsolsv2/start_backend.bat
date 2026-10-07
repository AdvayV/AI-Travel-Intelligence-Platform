@echo off
setlocal
cd /d "%~dp0backend" || goto failed
set "BACKEND_PYTHON=%~dp0backend\venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" (
    "%SystemRoot%\System32\where.exe" python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Install Python and add it to PATH.
        goto failed
    )
    python -m venv "%~dp0backend\venv"
    if errorlevel 1 goto failed
)
if /i "%~1"=="--install" goto install
"%BACKEND_PYTHON%" -c "import importlib.util,sys; sys.exit(any(importlib.util.find_spec(name) is None for name in ['fastapi','uvicorn','neo4j','chromadb','langchain','openai','langchain_openai','langchain_community','sentence_transformers','httpx','dotenv','truststore','pydantic','torch','apscheduler','pandas','numpy','chronos','pypdf','fast_flights']))"
if not errorlevel 1 goto run
:install
echo Installing v2 backend dependencies...
"%BACKEND_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:run
echo Starting v2 backend: http://127.0.0.1:8001
"%BACKEND_PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8001
if errorlevel 1 goto failed
exit /b 0
:failed
echo ERROR: v2 backend startup failed. Review the output above.
if not defined TRAVELROUTE_NO_PAUSE pause
exit /b 1
