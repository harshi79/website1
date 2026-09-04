@echo off
REM One-click launch GUI without building EXE
REM Just double-click this file

echo Starting Ultimate Proxy Scrapper (GUI)...
python --version >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install Python 3.10+ from https://www.python.org/
  pause
  exit /b 1
)

pip show requests >nul 2>&1
if errorlevel 1 (
  echo Installing dependencies...
  pip install -r requirements.txt
)

python main.py
pause
