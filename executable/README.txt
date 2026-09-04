Ultimate Proxy Scrapper — Executable
==================================================
© 2026 harshi79 / YorichiiPrime — Watermark: HARSHI79-ULTIMATE-PROXY-2026
Version: 2.1.0

>>> UltimateProxyScrapper.exe <<<
This is a REAL 64-bit Windows program (PE executable) built with PyInstaller
on a genuine Windows build server. It runs on EVERY Windows 10 and Windows 11
PC — x64 natively, Windows-on-ARM via built-in x64 emulation. No Python or
any other dependency is required.

  How to use:
    Double-click UltimateProxyScrapper.exe        -> GUI (dark dashboard)
    Open a terminal in this folder:
      UltimateProxyScrapper.exe --auto            -> scrape + validate + save
      UltimateProxyScrapper.exe --auto --limit 1000 --timeout 8
      UltimateProxyScrapper.exe --help            -> all CLI options

  SmartScreen warning the first time? This exe is not code-signed (signing
  certificates cost money). Click "More info" -> "Run anyway". That warning
  is NOT the same as an incompatibility error — the exe will run fine.

  Results are saved to: results\YYYY-MM-DD_HH-MM-SS\ next to the exe.


>>> UltimateProxyScrapper.pyz <<<
A Python "zipapp" for machines that HAVE Python installed (Linux, macOS,
Windows). It is NOT a Windows program by itself — never rename it to .exe,
Windows will reject it with "This app can't run on your PC".

  python3 UltimateProxyScrapper.pyz              (GUI)
  python3 UltimateProxyScrapper.pyz --auto       (CLI)


>>> Build it yourself <<<
  Windows : double-click build_exe.bat in the project root
            -> dist\UltimateProxyScrapper.exe (real PE, ~15-30 MB)
  CI      : every push builds a fresh exe automatically
            (.github/workflows/build-windows-exe.yml) — download it from the
            GitHub "Actions" tab (artifact) or the "Releases" page.

Protection:
  Every file contains watermark HARSHI79-ULTIMATE-PROXY-2026 and author.
  Removing it breaks integrity check (window title shows warning).
  LICENSE requires attribution.

Repository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator
