@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run setup_windows.bat first.& pause & exit /b 1)
".venv\Scripts\python.exe" -m uvicorn server:app --host 127.0.0.1 --port 8501
if errorlevel 1 pause
