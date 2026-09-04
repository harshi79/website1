# Ultimate Free Proxy Scrapper & Validator

> Harvest, validate and export free proxies from **18 public sources** — zero API keys, 80-thread validator, elite latency profiling, **now as EXE + Web + CLI**.

![Proxy](https://img.shields.io/badge/proxies-18%20sources-6366f1?style=for-the-badge)
![Threads](https://img.shields.io/badge/validator-80%20threads-10b981?style=for-the-badge)
![Export](https://img.shields.io/badge/export-TXT%20JSON%20CSV-0ea5e9?style=for-the-badge)
![EXE](https://img.shields.io/badge/EXE-Windows%20%7C%20Linux%20%7C%20macOS-f43f5e?style=for-the-badge)

A **premium Bootstrap 5 dark dashboard** + **standalone desktop EXE** that scrapes, validates and auto-saves free proxies to a timestamped folder in one click. Live SSE streaming on the web, native Tkinter GUI on desktop, CLI headless mode — same `proxy_engine` core.

<p align="center"><img src="icon.png" width="120" alt="icon"></p>

---

## ✨ Two ways to run

| Mode | File | How |
|---|---|---|
| **Desktop EXE (recommended for Windows)** | `main.py` → `dist/UltimateProxyScrapper.exe` | Double-click → GUI, or `exe --auto` → CLI |
| **Web Dashboard** | `app.py` | `python app.py` → `http://localhost:5000` |
| **CLI headless** | `main.py --auto` | `python main.py --auto --limit 1000` |

---

## 🖥️ Desktop EXE — Advanced Auto Workflow

Double-click the EXE and hit **⚡ START AUTO**:

```
[1/3] Scrape 18 sources in parallel (ProxyScrape, GitHub mirrors, Geonode, JetKai, ClarkTM…) → dedupe → shuffle
[2/3] Validate with 80 threads via http://httpbin.org/ip (or custom URL) → latency, speed, valid/dead/timeout
[3/3] Auto-save to results/YYYY-MM-DD_HH-MM-SS/
```

**Folder structure after each run:**

```
results/
  2025-09-04_12-30-45/
    valid.txt        # only valid proxies, sorted fast→slow
    all.txt          # all checked
    raw_scraped.txt  # original scraped list
    valid.json       # [{proxy, latency, speed, protocol, origin}]
    all.json
    valid.csv / all.csv
    http.txt / https.txt / socks4.txt / socks5.txt  # per-protocol valid
    stats.json       # {total_scraped, valid, counts, avg_latency_ms}
  latest/            # copy of last run (always overwritten)
```

**No console? No problem** — GUI shows live log, progress bars, counters, copy/save buttons. Logs are also written to `stats.json`.

### Build EXE on your computer (3 steps)

**Windows:**

```bat
# 1. Install Python 3.10+ from python.org (check "Add to PATH")
# 2. Open CMD in the project folder:
pip install -r requirements.txt
pip install pyinstaller
# 3. Build:
build_exe.bat
# OR manual:
pyinstaller --onefile --windowed --name UltimateProxyScrapper --icon=icon.ico main.py
# EXE appears at: dist\UltimateProxyScrapper.exe
```

**Linux / macOS:**

```bash
pip install -r requirements.txt
chmod +x build_exe.sh
./build_exe.sh
# Binary at dist/UltimateProxyScrapper
./dist/UltimateProxyScrapper --auto   # headless
./dist/UltimateProxyScrapper          # GUI (needs display)
```

**CLI options (exe or python):**

```bash
# Auto CLI — scrape → validate → save → exit
UltimateProxyScrapper.exe --auto --limit 1000 --timeout 8 --threads 100 --output ./results
python main.py --auto --limit 2000 --timeout 12 --test-url https://api.ipify.org?format=json
python main.py --auto --sources monosans_http,thespeedx_http --protocols http,socks5

# GUI
UltimateProxyScrapper.exe
python main.py
python main.py --gui

# Web dashboard (still available)
python main.py --web --port 5000
python app.py
```

| CLI flag | Default | Meaning |
|---|---|---|
| `--limit` | `500` | Max proxies to scrape (0=no limit) |
| `--timeout` | `8` | Seconds per proxy check |
| `--test-url` | `http://httpbin.org/ip` | URL to test through proxy |
| `--threads` | `80` | Validate workers |
| `--output` | `results` | Base results folder |
| `--sources` | `all` | Comma source ids |
| `--protocols` | `http,https,socks4,socks5` | Filter |

---

## 🌐 Web Dashboard (Flask + SSE)

If you prefer browser:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
# open http://localhost:5000
```

**Features:**

- **18 sources** scraped in parallel, protocol-filtered, deduplicated
- **80-concurrent validator** with latency classes (`fast<800ms / medium<2s / slow`)
- **Live SSE** (`source_result`, `progress`, `result`, `done` + `: ping`)
- **Pool management** — filters (valid/dead/timeout/http/socks), search, copy selected, bulk validate
- **One-click export** `TXT / JSON / CSV` sorted by latency
- **Built on `proxy_engine.py`** — same core as EXE

### Deploy Web to Render / Railway

Build: `pip install -r requirements.txt`  
Start: `gunicorn app:app --workers 1 --threads 8 --timeout 180` (Procfile included)

---

## 📂 Project layout

```
proxy_engine.py      Shared core: SOURCES, scrape, validate, save_results
main.py              Desktop GUI + CLI auto (builds to EXE)
app.py               Flask web dashboard (SSE)
templates/index.html Premium single-page dashboard
requirements.txt     Flask, requests, pysocks, pyinstaller, Pillow
build_exe.bat        Windows EXE builder
build_exe.sh         Linux/macOS builder
UltimateProxyScrapper.spec  PyInstaller spec (windowed, icon)
icon.png / icon.ico  App icon
results/             Auto-created, timestamped runs (gitignored)
```

---

## 🔌 Proxy sources (18)

ProxyScrape `http/socks4/socks5` · Proxy-List.download `http/https/socks4` · TheSpeedX `http/socks4/socks5` · Monosans `http/socks4/socks5` · RoosterKid `https/socks4/socks5` · Geonode API · JetKai · ClarkTM

Add more in `proxy_engine.py` → `SOURCES`.

---

## API (web)

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/health` | `{"ok":true, "proxies_total":N}` |
| GET | `/api/sources` | List sources |
| GET | `/api/proxies?status=valid&protocol=http&search=1.2.&limit=1000` | Filtered pool |
| POST | `/api/scrape` | `{sources:[ids], protocols:[], limit:500}` → `202 {job_id}` |
| POST | `/api/validate` | `{proxies:"ip:port\n…", timeout:8}` → `202 {job_id}` |
| GET | `/stream/<job_id>` | SSE |
| POST | `/stop/<job_id>` | Cancel |
| GET | `/export/<txt\|json\|csv>?status=valid` | Download |

---

## Tips

- Free proxies are volatile — expect 5–15% valid; re-scrape hourly.
- For **elite/anonymity** check, set test URL to `https://api.ipify.org?format=json` and compare returned IP.
- EXE is portable — no install, no admin, results folder is created next to EXE.
- GUI needs a display; on headless servers use `--auto` or web dashboard.

---

## License

MIT — do what you want, no warranty. Use responsibly and respect target sites’ ToS.
