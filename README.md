# Ultimate Free Proxy Scrapper & Validator — v2.2

> Harvest, validate and export free proxies from **18 public sources**.
> One file. One command. **No EXE, no build step, no `pip install` required.**

![Sources](https://img.shields.io/badge/sources-18-6366f1?style=for-the-badge)
![Threads](https://img.shields.io/badge/validator-80%20threads-10b981?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.8%2B%20stdlib%20only-0ea5e9?style=for-the-badge)

**© 2026 harshi79 / YorichiiPrime — Watermark: `HARSHI79-ULTIMATE-PROXY-2026`**

<p align="center"><img src="icon.png" width="120" alt="icon"></p>

---

## 🚀 Run it

```bash
python proxy.py
```

That's the whole thing. It scrapes 18 sources, dedupes, validates every proxy in
parallel (80 threads), and saves the working ones. No arguments, no setup, no
`pip install` — `proxy.py` runs on the Python standard library alone.

Output goes to a fresh timestamped folder next to you:

```
results/
  2026-09-04_12-30-45/
    valid.txt        ← only the working ones, fastest first
    all.txt          ← every proxy that was checked
    raw_scraped.txt  ← everything the sources returned
    valid.json / all.json / valid.csv / all.csv
    http.txt / socks4.txt / socks5.txt   ← per protocol
    stats.json       ← counts, hit-rate, latency, watermark
    _AUTHOR.txt      ← proves authenticity
  latest/            ← copy of the newest run (results/latest/valid.txt)
```

Console looks like this:

```
[1/3] Scraping 18 sources (http, https, socks4, socks5)...
  [+] ProxyScrape HTTP                4123   (1/18)
  [x] Geonode API                        0   (2/18)
  -> 9,812 unique proxies

[2/3] Validating 2000 proxies · 80 threads · 8s timeout · via http://httpbin.org/ip
  1840/2000 checked · valid 63 · dead 1690 · timeout 47 · 41/s · ~4s left

[3/3] Saving results...

==================================================================
  DONE in 51.3s — 63 working proxies out of 2000 checked
  dead 1690 · timeout 47

  fastest:
    45.77.56.114:3128        212 ms
    ...

  folder : /home/you/results/2026-09-04_12-30-45
  files  : valid.txt · all.txt · valid.json · valid.csv · stats.json
  always : results/latest/valid.txt
==================================================================
```

---

## 📦 What's in the repo

```
proxy.py              ← EVERYTHING lives here. Run this.
main.py               ← optional Tkinter GUI (needs requests + tkinter)
app.py                ← optional Flask web dashboard (needs Flask)
proxy_engine.py       ← core used by main.py / app.py
templates/index.html  ← web UI
requirements.txt      ← optional extras only
icon.png / icon.ico   ← icon
```

**The EXE is gone.** `executable/UltimateProxyScrapper.exe` and the PyInstaller
build scripts were removed in v2.2 — the binary failed to launch for many people
(SmartScreen, missing DLLs, unpacked one-file builds) and needed a rebuild for
every single code change. `python proxy.py` does the same job, starts faster,
and you can actually read and fix it yourself. If you still want a binary:

```bash
pip install pyinstaller
pyinstaller --onefile --name proxy proxy.py
```

---

## ⚙️ Options (all optional)

| Flag | Default | Meaning |
|---|---|---|
| `--limit N` | `2000` | Max proxies to check (`0` = no limit). Scraping pulls far more than you can validate, so keeping a cap is what makes a run finish in a minute instead of an hour. |
| `--timeout S` | `8` | Seconds to wait for each proxy. Lower = faster run, fewer slow-but-working proxies. |
| `--threads N` | `80` | Parallel checks. |
| `--output DIR` | `results` | Where the `results/` folder is created. |
| `--test-url URL` | auto | Endpoint used to check each proxy (must echo your IP). Auto-picks the first reachable one of httpbin/ipify/icanhazip/ifconfig.me. |
| `--protocols P` | all | `http,https,socks4,socks5` — filter which source types to scrape. |
| `--sources IDS` | all | Comma-separated source ids (`--sources thespeedx_http,geonode`). |
| `--file FILE` | — | Skip scraping: validate a list you already have, one `ip:port` per line. |
| `--quiet` | off | Only print the final summary. |

Examples:

```bash
python proxy.py                          # the default: scrape → validate → save
python proxy.py --limit 500 --timeout 5  # quick pass
python proxy.py --protocols socks5       # only SOCKS5
python proxy.py --file mylist.txt        # validate your own list, no scraping
python proxy.py --limit 0 --threads 150  # check everything, flat out
```

Exit codes: `0` = at least one working proxy, `1` = none found, `130` = stopped
with Ctrl+C.

---

## 🧠 How it decides a proxy works

1. **Scrape** — 18 sources fetched in parallel (12 workers), `ip:port` entries
   pulled out with a regex, deduped, shuffled, capped at `--limit`.
2. **Validate** — each proxy is used to fetch an IP-echo endpoint. `200` within
   `--timeout` means the proxy works; the round-trip time becomes its latency
   (`fast` < 800 ms, `medium` < 2 s, `slow` above that).
3. **Save** — everything, sorted fastest first, with `stats.json` + `_AUTHOR.txt`.

SOCKS notes:

* With `requests` **and** `pysocks` installed, SOCKS4/SOCKS5 are handled by
  requests.
* Without them, `proxy.py` uses a small built-in SOCKS4/SOCKS5 client, so socks
  lists still validate — that's why a bare `python proxy.py` works everywhere.
* A plain `ip:port` in a list could be either, so proxies that fail as HTTP get
  one automatic SOCKS5 retry before being written off.

---

## 🛠 Troubleshooting

**`No proxies found — every source was unreachable`**
Your network (or firewall / ISP / corporate proxy) is blocking the proxy-list
sites. The run prints the actual error for the first three sources. Check with:

```bash
python -c "import urllib.request;print(urllib.request.urlopen('https://api.proxyscrape.com/v2/?request=getproxies&protocol=http',timeout=10).status)"
```

If that fails too, it's the network, not the script. You can still validate a
list obtained elsewhere: `python proxy.py --file mylist.txt`.

**Everything comes back dead**
The IP-echo endpoint may be blocked as well. Run `python proxy.py --test-url
http://api.ipify.org?format=json` (or `--timeout 12` on a slow link).

**Slow runs**
Validation is the bottleneck: `proxies ÷ threads × timeout`. Drop `--limit`,
raise `--threads`, or lower `--timeout`.

**`python` isn't found**
Try `python3 proxy.py`. Requires Python 3.8+ (stdlib only).

---

## 🌐 Optional extras

**Desktop GUI** (needs `requests` + tkinter):

```bash
pip install requests
python main.py
```

**Web dashboard** (live progress, filters, exports):

```bash
pip install -r requirements.txt
python app.py        # http://localhost:5000
```

Deploy: `gunicorn app:app --workers 1 --threads 8 --timeout 180` (Procfile included).

---

## 🔌 Sources (18)

ProxyScrape `http/socks4/socks5` · Proxy-List.download `http/https/socks4` ·
TheSpeedX `http/socks4/socks5` · Monosans `http/socks4/socks5` · RoosterKid
`https/socks4/socks5` · Geonode · JetKai · ClarkTM

Add your own in `proxy.py → SOURCES`.

---

## License

**MIT + Attribution** — keep the watermark and author in the UI and in results.
See `LICENSE`. © 2026 harshi79 / YorichiiPrime —
https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator
Watermark: `HARSHI79-ULTIMATE-PROXY-2026` — do not remove.
