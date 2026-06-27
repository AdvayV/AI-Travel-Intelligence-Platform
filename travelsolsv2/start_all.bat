@echo off
echo Starting Backend and Frontend for TravelRoute Intelligence v2...
start "TravelRoute v2 Backend" /D "%~dp0" "%~dp0start_backend.bat"
start "TravelRoute v2 Frontend" /D "%~dp0" "%~dp0start_frontend.bat"
