@echo off
echo Starting Backend and Frontend for TravelRoute v2...
start "TravelRoute v2 Backend" /D "%~dp0travelsolsv2" "%~dp0travelsolsv2\start_backend.bat"
start "TravelRoute v2 Frontend" /D "%~dp0travelsolsv2" "%~dp0travelsolsv2\start_frontend.bat"
