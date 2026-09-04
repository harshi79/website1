Ultimate Proxy Scrapper — Executable (Protected)
==================================================
© 2026 harshi79 / YorichiiPrime — Watermark: HARSHI79-ULTIMATE-PROXY-2026
Version: 2.1.0

How to run:
  Windows (with Python installed):
    python UltimateProxyScrapper.exe --auto
    python UltimateProxyScrapper.pyz --auto
    # Or double-click UltimateProxyScrapper.pyz if .pyz is associated
    # For true Windows EXE (no Python needed, no source visible):
    #   Double-click build_exe.bat in project root → dist\UltimateProxyScrapper.exe (real PE, ~30 MB)

  Linux/macOS:
    python3 UltimateProxyScrapper.pyz --auto
    python3 UltimateProxyScrapper.pyz          # GUI (needs display)
    python3 UltimateProxyScrapper.exe --auto   # same as .pyz

CLI examples:
  python UltimateProxyScrapper.pyz --auto --limit 1000 --timeout 8 --output results
  python UltimateProxyScrapper.pyz --help

GUI:
  python UltimateProxyScrapper.pyz             # launches polished Tkinter GUI with splash, tabs, log

Results:
  results/YYYY-MM-DD_HH-MM-SS/
    valid.txt, all.txt, valid.json/csv, stats.json (watermarked), _AUTHOR.txt
  latest/ (copy of last run)

Protection:
  Every file contains watermark HARSHI79-ULTIMATE-PROXY-2026 and author.
  Removing it breaks integrity check (window title shows warning).
  LICENSE requires attribution.

Repository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator
