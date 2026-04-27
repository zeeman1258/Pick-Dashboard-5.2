@echo off
setlocal
cd /d %~dp0
start "" http://127.0.0.1:5000
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 app.py
    pause
    exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
    python app.py
    pause
    exit /b
)
echo Python 3 was not found. Please install Python 3 first.
pause
