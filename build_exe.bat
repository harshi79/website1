@echo off
REM Build Ultimate Proxy Scrapper EXE for Windows
REM Requires: Python 3.10+ and pip
echo ============================================================
echo  Ultimate Proxy Scrapper — Build EXE
echo ============================================================

python --version
if errorlevel 1 (
  echo Python not found. Install Python 3.10+ and add to PATH.
  pause
  exit /b 1
)

echo [1/3] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [2/3] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

echo [3/3] Building EXE with PyInstaller...
REM --onefile : single EXE
REM --windowed : no console (GUI mode). Remove --windowed if you want console.
REM --name : output name
REM --icon : optional icon (if you have icon.ico, else remove line)

if exist icon.ico (
  pyinstaller --onefile --windowed --name UltimateProxyScrapper --icon=icon.ico --add-data "templates;templates" main.py
) else (
  pyinstaller --onefile --windowed --name UltimateProxyScrapper main.py
)

if errorlevel 1 (
  echo Build failed — trying console mode...
  pyinstaller --onefile --name UltimateProxyScrapper main.py
)

echo.
echo ============================================================
echo  Build finished!
echo  EXE location: dist\UltimateProxyScrapper.exe
echo.
echo  Run it:
echo    dist\UltimateProxyScrapper.exe            (launches GUI)
echo    dist\UltimateProxyScrapper.exe --auto     (CLI auto scrape->validate->save)
echo    dist\UltimateProxyScrapper.exe --help     (see options)
echo.
echo  Results are saved to: results\YYYY-MM-DD_HH-MM-SS\
echo    - valid.txt / valid.json / valid.csv
echo    - all.txt / all.json
echo    - stats.json
echo    - latest\  (always the last run)
echo ============================================================
pause
