@echo off
REM Launch web dashboard at http://localhost:5000
echo Starting web dashboard...
python --version >nul 2>&1
if errorlevel 1 (
  echo Python not found.
  pause
  exit /b 1
)
pip show Flask >nul 2>&1
if errorlevel 1 pip install -r requirements.txt

start http://localhost:5000
python app.py
pause
