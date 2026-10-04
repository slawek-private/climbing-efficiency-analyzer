@echo off
cd /d "%~dp0..\.."
".venv\Scripts\python.exe" -m viewer
if errorlevel 1 pause
