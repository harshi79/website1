# Ultimate Free Proxy Scrapper & Validator

> Harvest, validate and export free proxies from **18 public sources** — zero API keys, 80-thread validator, elite latency profiling, SSE live streaming.

![Proxy](https://img.shields.io/badge/proxies-18%20sources-6366f1?style=for-the-badge)
![Threads](https://img.shields.io/badge/validator-80%20threads-10b981?style=for-the-badge)
![Export](https://img.shields.io/badge/export-TXT%20JSON%20CSV-0ea5e9?style=for-the-badge)

A single-page Flask dashboard (dark, premium Bootstrap 5 theme) that **scrapes**, **validates** and **exports** free proxies in one click. No checking logic is hidden — everything runs transparently with live progress streamed via Server-Sent Events.

## ✨ Features

- **18 free proxy sources** scraped in parallel:
  - ProxyScrape (http/socks4/socks5), Proxy-List.download, TheSpeedX, Monosans, RoosterKid, Geonode API, JetKai, ClarkTM…
- **Protocol aware** — filter HTTP / HTTPS / SOCKS4 / SOCKS5 at scrape time
- **Deduplication + shuffle + limit** (100 → 5,000, or no limit)
- **80-concurrent validator** hits `httpbin.org/ip` (or custom URL) through each proxy, measures latency, classifies `valid / dead / timeout / invalid`
- **Live SSE** — `source_result`, `progress`, `result`, `done` events feed progress bars, counters and a terminal-style log (never drops fast jobs)
- **Pool management** — in-memory store, status/proto/search filters, per-proxy copy, bulk validate selected, clear
- **One-click export** — valid proxies as `TXT` / `JSON` / `CSV` (sorted by latency, fast < 800 ms)

## Project layout

```
app.py                 Flask app: scrape + validate + SSE + export
templates/index.html   Premium single-page dashboard
requirements.txt       Python deps
Procfile               Render / gunicorn start command
```

## Quick start (local)

Requires **Python 3.10+**.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# run
python app.py
# or
flask --app app run --host 0.0.0.0 --port 5000
```

Open <http://localhost:5000>. No `.env` needed.

## Deploy on Render / Railway / Fly

1. Push to GitHub.
2. **New → Web Service**, connect repo.
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --workers 1 --threads 8 --timeout 180` (Procfile is auto-detected)
3. Deploy. No env vars required.

Optional env vars:

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `5000` | Bind port (Render sets automatically) |
| `VALIDATE_TIMEOUT` | `8` | Seconds per proxy check |
| `SCRAPE_TIMEOUT` | `12` | Seconds per source fetch |
| `MAX_WORKERS_VALIDATE` | `80` | Concurrent validator threads |
| `MAX_WORKERS_SCRAPE` | `12` | Concurrent scraper threads |
| `LOG_LEVEL` | `INFO` | Logging level |

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard HTML |
| GET | `/health` | `{"ok":true, "proxies_total": N, "uptime_seconds": …}` |
| GET | `/api/sources` | List available sources `{id, label, protocol}` |
| GET | `/api/proxies?status=valid&protocol=http&search=1.2.&limit=1000` | Filtered pool |
| POST | `/api/scrape` | `{sources:[ids], protocols:[http,https,socks4,socks5], limit:500}` → `202 {job_id}` |
| POST | `/api/validate` | `{proxies:"ip:port\n…", timeout:8, test_url:"http://httpbin.org/ip", protocol:"http"}` → `202 {job_id}` |
| POST | `/api/clear` | Clear pool |
| GET | `/stream/<job_id>` | SSE: `connected, source_result, source_error, progress, result, done, closed` + `: ping` |
| POST | `/stop/<job_id>` | Cancel running job |
| GET | `/export/<txt\|json\|csv>?status=valid&protocol=http` | Download file |

### SSE example

```
event: source_result
data: {"type":"source_result","source":"monosans_http","label":"Monosans HTTP","count":312,"new":278,"total_found":1240,"current":3,"total":12}

event: progress
data: {"type":"progress","current":3,"total":12,"found":1240}

event: result
data: {"type":"result","current":42,"total":500,"result":{"proxy":"1.2.3.4:8080","status":"valid","latency":342,"speed":"fast"},"counts":{"valid":12,"dead":20,"timeout":10}}

event: done
data: {"type":"done","total":500,"counts":{"valid":67,"dead":300,"timeout":80}}
```

## How validation works

- Each proxy is tested with `requests.get(test_url, proxies={"http": proxy_url, "https": proxy_url}, timeout=…, verify=False)` in a thread pool.
- `200` → `valid` (latency recorded, speed `fast<800ms / medium<2s / slow`), else `invalid/dead/timeout`.
- SOCKS proxies use `socks5://` / `socks4://` via `PySocks` (included).
- Results update the in-memory pool (`status`, `latency`, `last_checked`) and stream to the UI.

## Notes

- Free proxies are **volatile** — expect 5–15% valid at any moment. Re-scrape hourly.
- No credentials are stored; proxies live only in memory until you clear or restart.
- For **elite/anonymity** detection, set `Test URL` to `https://api.ipify.org?format=json` and compare returned IP to your own.

## License

MIT — do what you want, no warranty. Use responsibly and respect target sites’ ToS.
