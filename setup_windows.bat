@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Python launcher missing. Install Python 3.11.& pause & exit /b 1)
where ffmpeg >nul 2>nul
if errorlevel 1 (echo FFmpeg missing. Install using winget install Gyan.FFmpeg and restart terminal.& pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 (echo Python 3.11 unavailable.& pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency installation failed.& pause & exit /b 1)
if not exist .env copy .env.example .env
if not exist data mkdir data
echo.
echo Installation complete. Next time you only need start_windows.bat.
pause
