#!/usr/bin/env bash
# Build Ultimate Proxy Scrapper binary for Linux / macOS
set -e
echo "============================================================"
echo " Ultimate Proxy Scrapper — Build Binary"
echo "============================================================"

python3 --version || { echo "python3 not found"; exit 1; }

echo "[1/3] Installing dependencies..."
pip install --break-system-packages -r requirements.txt 2>/dev/null || pip install -r requirements.txt
pip install --break-system-packages pyinstaller 2>/dev/null || pip install pyinstaller

echo "[2/3] Cleaning previous build..."
rm -rf build dist __pycache__

echo "[3/3] Building with PyInstaller..."
# Windowed for GUI on macOS, console for Linux shows logs
if [[ "$OSTYPE" == "darwin"* ]]; then
  pyinstaller --onefile --windowed --name UltimateProxyScrapper main.py
else
  pyinstaller --onefile --name UltimateProxyScrapper main.py
fi

echo ""
echo "============================================================"
echo " Build finished!"
echo " Binary: dist/UltimateProxyScrapper"
echo ""
echo " Run:"
echo "   ./dist/UltimateProxyScrapper                  # GUI"
echo "   ./dist/UltimateProxyScrapper --auto           # CLI auto"
echo "   ./dist/UltimateProxyScrapper --help"
echo ""
echo " Results: ./results/YYYY-MM-DD_HH-MM-SS/"
echo "============================================================"
