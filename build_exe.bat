@echo off
REM ============================================================
REM  Ultimate Proxy Scrapper - Build a REAL Windows EXE
REM  Produces a genuine 64-bit Windows program (PE) that runs on
REM  every Windows 10 / Windows 11 PC (x64 + ARM64 via emulation).
REM  Requires: Python 3.10+ installed from python.org (tick "Add to PATH")
REM ============================================================
setlocal
echo ============================================================
echo  Ultimate Proxy Scrapper - Build EXE
echo ============================================================

REM -- Find Python (python or py launcher) --------------------
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  echo Python not found.
  echo Install Python 3.10+ from https://www.python.org/downloads/
  echo IMPORTANT: tick "Add python.exe to PATH" during install.
  pause
  exit /b 1
)
%PY% --version

echo.
echo [1/4] Creating private build environment (.venv-build)...
if not exist .venv-build (
  %PY% -m venv .venv-build || (echo venv creation failed & pause & exit /b 1)
)
call .venv-build\Scripts\activate.bat

echo.
echo [2/4] Installing dependencies...
python -m pip install --upgrade pip >nul
pip install "requests>=2.31,<3" "pysocks>=1.7" "urllib3>=2.0" "pyinstaller>=6.0" || (echo pip install failed & pause & exit /b 1)

echo.
echo [3/4] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist UltimateProxyScrapper.spec del /q UltimateProxyScrapper.spec

echo.
echo [4/4] Building EXE with PyInstaller...
REM --onefile  : single .exe file
REM --windowed : no console window (GUI app)
REM --add-data : bundle the icon INSIDE the exe so it always loads
set "EXTRA="
if exist icon.ico set "EXTRA=--icon icon.ico --add-data "icon.ico;.""

pyinstaller --noconfirm --clean --onefile --windowed --name UltimateProxyScrapper %EXTRA% ^
  --exclude-module flask --exclude-module gunicorn --exclude-module PIL ^
  --exclude-module numpy --exclude-module pandas ^
  main.py

if errorlevel 1 (
  echo.
  echo Build failed - retrying in console mode...
  pyinstaller --noconfirm --clean --onefile --name UltimateProxyScrapper %EXTRA% main.py
  if errorlevel 1 (echo Build failed again - see errors above & pause & exit /b 1)
)

echo.
echo Verifying the EXE is a real Windows program...
powershell -NoProfile -Command "$h=[IO.File]::ReadAllBytes('dist\UltimateProxyScrapper.exe')[0..1]; if([Text.Encoding]::ASCII.GetString($h)-ne'MZ'){throw 'NOT a real Windows exe'} ; 'OK: genuine Windows x64 EXE'"

echo.
echo ============================================================
echo  Build finished!
echo  EXE location: %cd%\dist\UltimateProxyScrapper.exe
echo.
echo  Run it (no Python needed on the target PC):
echo    double-click dist\UltimateProxyScrapper.exe   (GUI)
echo    dist\UltimateProxyScrapper.exe --auto         (CLI auto)
echo    dist\UltimateProxyScrapper.exe --help
echo.
echo  Note: SmartScreen may warn the first time (unsigned exe).
echo        Click "More info" then "Run anyway".
echo.
echo  Results are saved to: results\YYYY-MM-DD_HH-MM-SS\
echo ============================================================
pause
