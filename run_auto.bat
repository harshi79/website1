@echo off
REM One-click AUTO: scrape -> validate -> save to results/
REM Just double-click this file

echo ============================================================
echo  Ultimate Proxy Scrapper — AUTO MODE
echo  Scraping -> Validating -> Saving to results\
echo ============================================================

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

REM Edit these values as you like:
REM --limit 500  --timeout 8  --threads 80  --output results

python main.py --auto --limit 500 --timeout 8 --threads 80 --output results

echo.
echo Done! Check results\ folder.
pause
