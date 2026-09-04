#!/usr/bin/env python3
# =============================================================================
# Ultimate Proxy Scrapper — © 2026 harshi79 / YorichiiPrime
# All rights reserved. Licensed for personal use. Redistribution without
# attribution is prohibited. Watermark: HARSHI79-ULTIMATE-PROXY-2026
# Repository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator
# Version: 2.1.0  — Advanced Desktop EXE with auto-harvest & protected results
# =============================================================================
# Build to EXE:  pyinstaller --onefile --windowed --name UltimateProxyScrapper --icon=icon.ico main.py
# Run GUI:       python main.py
# Run CLI:       python main.py --auto --limit 1000 --output results
# =============================================================================

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("UltimateProxy")

# Watermark / author protection — changing this breaks verification
WATERMARK = "HARSHI79-ULTIMATE-PROXY-2026"
AUTHOR = "harshi79"
AUTHOR_FULL = "harshi79 / YorichiiPrime — https://github.com/harshi79"
VERSION = "2.1.0"
APP_TITLE = f"Ultimate Proxy Scrapper v{VERSION}"
ENCODED_AUTHOR = base64.b64encode(AUTHOR.encode()).decode()  # aGFyc2hpNzk=

def verify_integrity() -> bool:
    """Simple integrity check — ensures file still contains watermark."""
    try:
        text = Path(__file__).read_text(encoding="utf-8")
        return WATERMARK in text and AUTHOR in text and ENCODED_AUTHOR in text
    except:
        return True  # if file not found (frozen), assume ok

def resource_path(rel: str) -> Path:
    """Absolute path to a bundled resource (works in dev AND frozen PyInstaller exe).

    In a --onefile exe, PyInstaller unpacks bundled data to sys._MEIPASS.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    return Path(__file__).parent / rel

# Import engine
try:
    from proxy_engine import SOURCES, scrape_proxies, validate_proxies, save_results
except ImportError as e:
    print(f"[fatal] proxy_engine.py missing: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CLI auto
# ---------------------------------------------------------------------------
def run_auto(
    limit: int = 500,
    timeout: int = 8,
    test_url: str = "http://httpbin.org/ip",
    protocols: Optional[Set[str]] = None,
    source_ids: Optional[List[str]] = None,
    output: Optional[Path] = None,
    threads_validate: int = 80,
) -> Path:
    if protocols is None:
        protocols = {"http", "https", "socks4", "socks5"}
    if source_ids is None:
        source_ids = list(SOURCES.keys())

    print(f"\n{'='*72}")
    print(f" {APP_TITLE} — © {AUTHOR_FULL}")
    print(f" Watermark: {WATERMARK}")
    print(f"{'='*72}")
    print(f" Sources: {len(source_ids)} | Protocols: {sorted(protocols)} | Limit: {limit or '∞'}")
    print(f" Timeout: {timeout}s | Threads: {threads_validate} | Output: {output or 'results/'}")
    print(f" Author: {AUTHOR_FULL} — protected build")
    print(f"{'-'*72}\n")

    stop_event = threading.Event()

    def progress_cb(info: Dict[str, Any]):
        t = info.get("type")
        if t == "source_result":
            print(f"  [✓] {info['label']:28s} +{info['new']:4d}  total {info['total_found']:5d} ({info['current']}/{info['total']})")
        elif t == "source_error":
            print(f"  [✗] {info['label']:28s} {info['error'][:70]}")
        elif t == "note":
            print(f"  [i] {info['message']}")
        elif t == "result":
            r = info["result"]
            if r.get("status") == "valid":
                print(f"    [✓ VALID] {r['proxy']:22s} {r.get('latency', '?')}ms ({info['current']}/{info['total']})")
            elif info["current"] % 40 == 0:
                print(f"    [{r.get('status','?'):7s}] {r['proxy']:22s} ({info['current']}/{info['total']})")

    print("[1/3] Scraping proxies...")
    start = time.time()
    proxies, meta = scrape_proxies(source_ids, protocols, limit=limit, progress_callback=progress_cb, stop_event=stop_event, timeout=12)
    print(f"\n → Scraped {len(proxies)} proxies in {time.time()-start:.1f}s" + (" (sample — offline demo)" if meta.get("demo_used") else ""))

    if not proxies:
        print(" No proxies — abort.")
        return Path(".")

    print(f"\n[2/3] Validating {len(proxies)} proxies...")
    start = time.time()
    results, counts = validate_proxies(proxies, timeout=timeout, test_url=test_url, progress_callback=progress_cb, max_workers=threads_validate)
    print(f"\n → Validation {time.time()-start:.1f}s | Valid {counts['valid']} | Dead {counts['dead']} | Timeout {counts['timeout']} | {round(counts['valid']/len(proxies)*100) if proxies else 0}% hit")

    print("\n[3/3] Saving results with watermark...")
    base = Path(output) if output else Path.cwd() / "results"
    if base.suffix:
        base = base.parent
    base.mkdir(parents=True, exist_ok=True)
    out_dir = base / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Inject watermark into save via extra handling after
    out = save_results(proxies, results, output_dir=out_dir, base_dir=base)
    # Add protected watermark file
    try:
        (out / "_AUTHOR.txt").write_text(f"Generated by {APP_TITLE}\nAuthor: {AUTHOR_FULL}\nWatermark: {WATERMARK}\nTimestamp: {datetime.now().isoformat()}\nRepository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator\nDO NOT REMOVE — proves authenticity.\n", encoding="utf-8")
        # Inject into stats.json
        stats_path = out / "stats.json"
        if stats_path.exists():
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            stats["author"] = AUTHOR
            stats["author_full"] = AUTHOR_FULL
            stats["watermark"] = WATERMARK
            stats["app"] = APP_TITLE
            stats["version"] = VERSION
            stats["repository"] = "https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator"
            stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        # quick copy latest already done by engine
    except Exception as e:
        log.warning(f"Watermark write failed: {e}")

    print(f"\n Saved → {out.resolve()}")
    print(f"  valid.txt ({counts['valid']}) | all.txt ({len(proxies)}) | valid.json/csv | stats.json | _AUTHOR.txt")
    print(f"  latest/ updated")
    print(f"{'='*72}\n")
    return out

# ---------------------------------------------------------------------------
# GUI — polished, protected, professional
# ---------------------------------------------------------------------------
def launch_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import subprocess
    import re

    # Integrity notice
    if not verify_integrity():
        log.warning("Integrity check failed — watermark missing. This build may be tampered.")

    root = tk.Tk()
    root.title(f"{APP_TITLE}  —  by {AUTHOR}  [Protected]")
    root.geometry("1260x820")
    root.minsize(1180, 740)
    try:
        icon = resource_path("icon.ico")
        if icon.exists():
            root.iconbitmap(str(icon))
    except: pass

    # Theme
    BG = "#060a14"
    PANEL = "#0e1629"
    PANEL2 = "#111e3a"
    BORDER = "#24314e"
    BORDER2 = "#2e3d5e"
    ACCENT = "#6366f1"
    ACCENT2 = "#8b5cf6"
    ACCENT3 = "#06b6d4"
    TEXT = "#e6edf6"
    DIM = "#8b9bb4"
    DIM2 = "#5a6b87"
    OK = "#10b981"
    WARN = "#f59e0b"
    BAD = "#ef4444"

    root.configure(bg=BG)
    style = ttk.Style()
    try: style.theme_use("clam")
    except: pass
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 9))
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 18, "bold"))
    style.configure("Sub.TLabel", background=BG, foreground=DIM, font=("Segoe UI", 9))
    style.configure("Card.TFrame", background=PANEL)
    style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(10,6))
    style.configure("Accent.TButton", background=ACCENT, foreground="white")
    style.map("Accent.TButton", background=[("active", ACCENT2)])
    style.configure("Success.TButton", background=OK, foreground="#022c22")
    style.map("Success.TButton", background=[("active", "#0ecb8a")])
    style.configure("Ghost.TButton", background="#16233f", foreground=TEXT)
    style.map("Ghost.TButton", background=[("active", "#1e2f52")])
    style.configure("TProgressbar", troughcolor="#02060e", background=ACCENT, bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background="#0e1629", foreground=DIM, padding=(14,7), font=("Segoe UI", 9, "bold"))
    style.map("TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", TEXT)])
    style.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 9))
    style.configure("TEntry", fieldbackground="#02060e")
    style.configure("Treeview", background="#02060e", foreground=TEXT, fieldbackground="#02060e", bordercolor=BORDER, rowheight=26, font=("Consolas", 9))
    style.configure("Treeview.Heading", background="#0e1629", foreground=DIM, font=("Segoe UI", 8, "bold"), relief="flat")
    style.map("Treeview", background=[("selected", "#1e2f52")])

    # Vars
    var_limit = tk.StringVar(value="500")
    var_timeout = tk.StringVar(value="8")
    var_test_url = tk.StringVar(value="http://httpbin.org/ip")
    var_threads = tk.StringVar(value="80")
    var_output = tk.StringVar(value=str((Path.cwd() / "results").resolve()))
    var_protocols = {p: tk.BooleanVar(value=(p in ("http","https"))) for p in ("http","https","socks4","socks5")}
    var_sources = {sid: tk.BooleanVar(value=True) for sid in SOURCES}
    var_scrape_prog = tk.StringVar(value="Ready")
    var_validate_prog = tk.StringVar(value="Ready")
    var_status = tk.StringVar(value=f"Ready — by {AUTHOR} • v{VERSION} • Protected")

    stop_event = threading.Event()
    current_proxies: List[str] = []
    last_results: Optional[List[Dict[str, Any]]] = None
    last_output_dir: Optional[Path] = None

    # Splash (brief)
    splash = tk.Toplevel(root)
    splash.geometry("520x260")
    splash.overrideredirect(True)
    splash.configure(bg=PANEL2)
    # Center splash
    splash.update_idletasks()
    x = (splash.winfo_screenwidth() - 520)//2
    y = (splash.winfo_screenheight() - 260)//2
    splash.geometry(f"520x260+{x}+{y}")
    tk.Label(splash, text="⬢", bg=PANEL2, fg=ACCENT, font=("Segoe UI", 48, "bold")).pack(pady=(22,4))
    tk.Label(splash, text="Ultimate Proxy Scrapper", bg=PANEL2, fg=TEXT, font=("Segoe UI", 18, "bold")).pack()
    tk.Label(splash, text=f"v{VERSION}  •  by {AUTHOR}", bg=PANEL2, fg=DIM, font=("Segoe UI", 9)).pack()
    tk.Label(splash, text=WATERMARK, bg=PANEL2, fg=DIM2, font=("Consolas", 7)).pack(pady=(6,0))
    tk.Label(splash, text="Loading engine • 18 sources • 80 threads", bg=PANEL2, fg=DIM, font=("Segoe UI", 9)).pack(pady=(8,0))
    pb = ttk.Progressbar(splash, mode="indeterminate")
    pb.pack(fill="x", padx=40, pady=16)
    pb.start(12)
    tk.Label(splash, text="© 2026 harshi79 — All rights reserved", bg=PANEL2, fg=DIM2, font=("Segoe UI", 7)).pack()
    root.withdraw()
    def close_splash():
        pb.stop(); splash.destroy(); root.deiconify()
    root.after(1300, close_splash)

    # Header
    header = tk.Frame(root, bg=BG, height=74, highlightbackground=BORDER, highlightthickness=1)
    header.pack(fill="x", padx=0, pady=0)
    header.pack_propagate(False)
    h_left = tk.Frame(header, bg=BG)
    h_left.pack(side="left", padx=18, pady=10)
    # brand mark
    mark = tk.Label(h_left, text="⬢", bg=ACCENT, fg="white", font=("Segoe UI", 16, "bold"), width=3, height=1, relief="flat", bd=0)
    mark.pack(side="left", padx=(0,12))
    # configure mark bg via label bg? make rounded via padding
    title_box = tk.Frame(h_left, bg=BG)
    title_box.pack(side="left")
    tk.Label(title_box, text="Ultimate Proxy Scrapper", bg=BG, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w")
    tk.Label(title_box, text="Auto-harvest • Validate • Export  —  results/ with _AUTHOR protection", bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w")

    h_right = tk.Frame(header, bg=BG)
    h_right.pack(side="right", padx=18, pady=10)
    # pills
    def pill(frame, text, bgc, fgc):
        l = tk.Label(frame, text=text, bg=bgc, fg=fgc, font=("Segoe UI", 7, "bold"), padx=10, pady=4, bd=1, relief="solid", highlightbackground=BORDER2)
        l.pack(side="left", padx=4)
        return l
    pill(h_right, f"v{VERSION}  •  Protected", "#111e3a", "#a5b4fc")
    pill(h_right, f"by {AUTHOR}", "#0f1f2f", "#7dd3fc")
    # header buttons
    def open_results_folder():
        p = Path(var_output.get())
        if not p.exists():
            messagebox.showinfo("Results", f"Folder not found:\n{p}\n\nRun Auto first.")
            return
        try:
            if sys.platform.startswith("win"): os.startfile(str(p))  # type: ignore
            elif sys.platform == "darwin": subprocess.Popen(["open", str(p)])
            else: subprocess.Popen(["xdg-open", str(p)])
        except Exception as e: messagebox.showerror("Open", str(e))
    def show_about():
        win = tk.Toplevel(root)
        win.title("About")
        win.geometry("560x420")
        win.configure(bg=PANEL)
        win.transient(root); win.grab_set()
        try:
            win.iconbitmap(str(resource_path("icon.ico")))
        except: pass
        tk.Label(win, text="⬢ Ultimate Proxy Scrapper", bg=PANEL, fg=TEXT, font=("Segoe UI", 16, "bold")).pack(pady=(18,4))
        tk.Label(win, text=f"Version {VERSION} — Advanced Desktop", bg=PANEL, fg=DIM, font=("Segoe UI", 9)).pack()
        tk.Label(win, text=f"Author: {AUTHOR_FULL}", bg=PANEL, fg="#a5b4fc", font=("Segoe UI", 9, "bold")).pack(pady=(8,0))
        tk.Label(win, text=f"Watermark: {WATERMARK}", bg=PANEL, fg=DIM2, font=("Consolas", 8)).pack()
        tk.Label(win, text="18 sources • 80-thread validator • auto-save to results/", bg=PANEL, fg=DIM, font=("Segoe UI", 9)).pack(pady=(10,0))
        tk.Label(win, text="© 2026 harshi79. All rights reserved.\nLicensed for personal use. Redistribution without attribution is prohibited.\nResults are watermarked with _AUTHOR.txt & stats.json to prove authenticity.", bg=PANEL, fg=DIM, font=("Segoe UI", 8), justify="center", wraplength=480).pack(pady=12, padx=18)
        tk.Label(win, text="Repository:", bg=PANEL, fg=DIM2, font=("Segoe UI", 8)).pack()
        link = tk.Label(win, text="github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator", bg=PANEL, fg=ACCENT3, font=("Segoe UI", 8, "underline"), cursor="hand2")
        link.pack()
        link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator"))
        tk.Label(win, text="If you paid for this and didn't get it from harshi79, you were scammed.", bg="#1a2744", fg="#fbbf24", font=("Segoe UI", 8, "bold"), wraplength=500, justify="center", padx=10, pady=6).pack(pady=12, padx=12, fill="x")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=6)
        ttk.Button(win, text="Open GitHub", command=lambda: webbrowser.open("https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator")).pack()
    tk.Button(h_right, text="📁 Results", bg="#16233f", fg=TEXT, bd=0, padx=10, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2", command=open_results_folder).pack(side="left", padx=4)
    tk.Button(h_right, text="ℹ About", bg="#16233f", fg=TEXT, bd=0, padx=10, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2", command=show_about).pack(side="left", padx=4)

    # Stats bar
    stats_frame = tk.Frame(root, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    stats_frame.pack(fill="x", padx=12, pady=(12,0))
    stat_widgets = {}
    for icon, label, key in [("◉", "Total", "total"), ("✓", "Valid", "valid"), ("⚡", "Avg ms", "latency"), ("🌐", "Sources", "sources")]:
        card = tk.Frame(stats_frame, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(side="left", fill="both", expand=True, padx=6, pady=8)
        tk.Label(card, text=f"{icon}  {label.upper()}", bg=PANEL, fg=DIM2, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(8,0))
        val = tk.Label(card, text="0" if key != "latency" else "—", bg=PANEL, fg=TEXT, font=("Segoe UI", 20, "bold"))
        val.pack(anchor="w", padx=10)
        sub = tk.Label(card, text="in memory" if key=="total" else "0% success" if key=="valid" else "validate to measure" if key=="latency" else "18 live • protected", bg=PANEL, fg=DIM, font=("Segoe UI", 8))
        sub.pack(anchor="w", padx=10, pady=(0,8))
        stat_widgets[key] = (val, sub)
    def update_stats():
        total = len(current_proxies)
        if last_results:
            valid = sum(1 for r in last_results if r.get("status")=="valid")
            lats = [r["latency"] for r in last_results if r.get("status")=="valid" and r.get("latency")]
            avg = sum(lats)//len(lats) if lats else 0
            stat_widgets["total"][0].config(text=str(total))
            stat_widgets["valid"][0].config(text=str(valid), fg=OK if valid else TEXT)
            stat_widgets["valid"][1].config(text=f"{round(valid/max(1,total)*100)}% success • watermarked")
            stat_widgets["latency"][0].config(text=str(avg) if avg else "—")
            stat_widgets["latency"][1].config(text="fast <800ms" if avg and avg<800 else "medium" if avg and avg<2000 else "validate to measure" if not avg else "slow")
        else:
            stat_widgets["total"][0].config(text=str(total))
            stat_widgets["valid"][0].config(text="0")
        stat_widgets["sources"][0].config(text=str(len(SOURCES)))
        stat_widgets["sources"][1].config(text="18 live • protected")
    update_stats()

    # Main notebook
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=10)

    tab_auto = ttk.Frame(notebook)
    tab_scrape = ttk.Frame(notebook)
    tab_validate = ttk.Frame(notebook)
    tab_results = ttk.Frame(notebook)
    tab_log = ttk.Frame(notebook)
    notebook.add(tab_auto, text="  ⚡ AUTO  ")
    notebook.add(tab_scrape, text="  ① Scrape  ")
    notebook.add(tab_validate, text="  ② Validate  ")
    notebook.add(tab_results, text="  Results  ")
    notebook.add(tab_log, text="  Log  ")

    # Helper to create card
    def make_card(parent, title, subtitle=""):
        card = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, bd=0)
        card.pack(fill="x", padx=12, pady=8)
        tk.Label(card, text=title, bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(12,2))
        if subtitle:
            tk.Label(card, text=subtitle, bg=PANEL, fg=DIM, font=("Segoe UI", 8), wraplength=700, justify="left").pack(anchor="w", padx=14, pady=(0,8))
        body = tk.Frame(card, bg=PANEL)
        body.pack(fill="x", padx=14, pady=(0,12))
        return card, body

    # ---- AUTO TAB ----
    auto_card, auto_body = make_card(tab_auto, "ONE-CLICK HARVEST — Generate → Check → Save", "Scrapes 18 sources, validates 80 threads, auto-saves to results/YYYY-MM-DD_HH-MM-SS/ with _AUTHOR.txt watermark. Perfect for beginners.")
    # Row: limit, threads, timeout
    row1 = tk.Frame(auto_body, bg=PANEL)
    row1.pack(fill="x", pady=4)
    tk.Label(row1, text="Limit:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left")
    cb_limit = ttk.Combobox(row1, textvariable=var_limit, values=["100","500","1000","2000","5000","0"], width=7, state="readonly")
    cb_limit.pack(side="left", padx=6)
    tk.Label(row1, text="(0=no limit)", bg=PANEL, fg=DIM2, font=("Segoe UI", 7)).pack(side="left")
    tk.Label(row1, text="Threads:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left", padx=(18,0))
    tk.Entry(row1, textvariable=var_threads, width=5, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8), justify="center").pack(side="left", padx=6)
    tk.Label(row1, text="Timeout:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left", padx=(18,0))
    ttk.Combobox(row1, textvariable=var_timeout, values=["3","5","8","12","15"], width=5, state="readonly").pack(side="left", padx=6)
    tk.Label(row1, text="Test URL:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left", padx=(18,0))
    tk.Entry(row1, textvariable=var_test_url, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8)).pack(side="left", fill="x", expand=True, padx=6)

    # Output folder
    out_row = tk.Frame(auto_body, bg=PANEL)
    out_row.pack(fill="x", pady=6)
    tk.Label(out_row, text="Output:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left")
    tk.Entry(out_row, textvariable=var_output, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8)).pack(side="left", fill="x", expand=True, padx=6)
    def browse_out():
        d = filedialog.askdirectory(initialdir=var_output.get() or str(Path.cwd()))
        if d: var_output.set(d)
    tk.Button(out_row, text="Browse", bg="#16233f", fg=TEXT, bd=0, padx=12, pady=4, font=("Segoe UI", 8), cursor="hand2", command=browse_out).pack(side="left", padx=4)

    # Auto progress
    auto_prog = ttk.Progressbar(auto_body, mode="determinate", maximum=100)
    auto_prog.pack(fill="x", pady=6)
    auto_status = tk.Label(auto_body, text="Ready to harvest — watermark protected", bg=PANEL, fg=DIM, font=("Consolas", 8), anchor="w")
    auto_status.pack(fill="x")

    btn_auto = tk.Button(auto_body, text="⚡  START AUTO  —  Generate → Validate → Save", bg=ACCENT2, fg="white", bd=0, padx=18, pady=12, font=("Segoe UI", 11, "bold"), cursor="hand2", activebackground="#7c3aed", activeforeground="white")
    btn_auto.pack(fill="x", pady=(10,4))
    tk.Label(auto_body, text=f"© {AUTHOR} • {WATERMARK} • Results watermarked to prove authenticity", bg=PANEL, fg=DIM2, font=("Consolas", 7)).pack()

    # ---- SCRAPE TAB ----
    scrape_card, scrape_body = make_card(tab_scrape, "SOURCES & PROTOCOLS", "Pick up to 18 sources and protocols. Scrape is parallel (12 workers) with dedupe & shuffle.")
    # Sources grid
    src_grid = tk.Frame(scrape_body, bg=PANEL)
    src_grid.pack(fill="x", pady=6)
    r = c = 0
    for sid, cfg in SOURCES.items():
        cb = tk.Checkbutton(src_grid, text=f"{cfg['label']} [{cfg['protocol']}]", variable=var_sources[sid],
                            bg=PANEL, fg=TEXT, selectcolor="#02060e", activebackground=PANEL, font=("Segoe UI", 8))
        cb.grid(row=r, column=c, sticky="w", padx=8, pady=2)
        c += 1
        if c > 2:
            c=0; r+=1
    sel_row = tk.Frame(scrape_body, bg=PANEL)
    sel_row.pack(fill="x", pady=4)
    tk.Button(sel_row, text="Select all", bg="#16233f", fg=TEXT, bd=0, padx=10, pady=4, font=("Segoe UI", 8), command=lambda: [v.set(True) for v in var_sources.values()]).pack(side="left", padx=4)
    tk.Button(sel_row, text="Deselect", bg="#16233f", fg=TEXT, bd=0, padx=10, pady=4, font=("Segoe UI", 8), command=lambda: [v.set(False) for v in var_sources.values()]).pack(side="left", padx=4)
    # Protocols
    proto_row = tk.Frame(scrape_body, bg=PANEL)
    proto_row.pack(fill="x", pady=6)
    tk.Label(proto_row, text="Protocols:", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(side="left")
    for proto in ("http","https","socks4","socks5"):
        tk.Checkbutton(proto_row, text=proto.upper(), variable=var_protocols[proto], bg=PANEL, fg=TEXT, selectcolor=ACCENT, font=("Segoe UI", 8, "bold")).pack(side="left", padx=8)
    # Scrape action row
    scrape_action = tk.Frame(scrape_body, bg=PANEL)
    scrape_action.pack(fill="x", pady=8)
    btn_scrape = tk.Button(scrape_action, text="▶  Scrape Proxies", bg=ACCENT, fg="white", bd=0, padx=16, pady=8, font=("Segoe UI", 9, "bold"), cursor="hand2")
    btn_scrape.pack(side="left", fill="x", expand=True, padx=(0,6))
    btn_stop = tk.Button(scrape_action, text="⏹ Stop", bg="#7f1d1d", fg="white", bd=0, padx=14, pady=8, font=("Segoe UI", 9, "bold"), state="disabled", cursor="hand2")
    btn_stop.pack(side="left")
    prog_scrape = ttk.Progressbar(scrape_body, mode="determinate", maximum=100)
    prog_scrape.pack(fill="x", pady=4)
    lbl_scrape = tk.Label(scrape_body, textvariable=var_scrape_prog, bg=PANEL, fg=DIM, font=("Consolas", 8), anchor="w")
    lbl_scrape.pack(fill="x")

    # ---- VALIDATE TAB ----
    validate_card, validate_body = make_card(tab_validate, "VALIDATE PROXIES", "Paste proxies or use scraped. 80 threads, custom timeout & test URL, live stats.")
    # Top controls
    val_top = tk.Frame(validate_body, bg=PANEL)
    val_top.pack(fill="x", pady=4)
    tk.Label(val_top, text="Timeout:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left")
    ttk.Combobox(val_top, textvariable=var_timeout, values=["3","5","8","12","15"], width=5, state="readonly").pack(side="left", padx=6)
    tk.Label(val_top, text="Test URL:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left", padx=(12,0))
    tk.Entry(val_top, textvariable=var_test_url, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8)).pack(side="left", fill="x", expand=True, padx=6)
    # Proxy input
    tk.Label(validate_body, text="Proxy list (ip:port per line):", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w", pady=(8,2))
    txt_input = tk.Text(validate_body, height=7, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8), padx=8, pady=6, wrap="word")
    txt_input.pack(fill="x", pady=2)
    txt_input.insert("1.0", "# Paste here or click 'Use scraped'\n# 1.2.3.4:8080\n")
    # Footer for input
    inp_foot = tk.Frame(validate_body, bg=PANEL)
    inp_foot.pack(fill="x", pady=4)
    lbl_input_count = tk.Label(inp_foot, text="0 lines", bg=PANEL, fg=DIM, font=("Segoe UI", 7))
    lbl_input_count.pack(side="right")
    def use_scraped():
        if not current_proxies:
            messagebox.showwarning("Validate", "No scraped proxies — scrape in Auto or Scrape tab first.")
            return
        txt_input.delete("1.0","end")
        txt_input.insert("1.0", "\n".join(current_proxies[:600]))
        if len(current_proxies)>600:
            txt_input.insert("end", f"\n# ... and {len(current_proxies)-600} more")
        lbl_input_count.config(text=f"{len(current_proxies)} scraped loaded")
    tk.Button(inp_foot, text="↺ Use scraped proxies", bg="#16233f", fg=TEXT, bd=0, padx=10, pady=4, font=("Segoe UI", 8), cursor="hand2", command=use_scraped).pack(side="left")
    def update_input_count(event=None):
        raw = txt_input.get("1.0","end").strip()
        lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
        lbl_input_count.config(text=f"{len(lines)} proxies")
    txt_input.bind("<KeyRelease>", update_input_count)
    # Validate buttons
    val_action = tk.Frame(validate_body, bg=PANEL)
    val_action.pack(fill="x", pady=8)
    btn_validate = tk.Button(val_action, text="✔  Validate Proxies", bg=OK, fg="#022c22", bd=0, padx=16, pady=8, font=("Segoe UI", 9, "bold"), cursor="hand2")
    btn_validate.pack(side="left", fill="x", expand=True, padx=(0,6))
    btn_stop2 = tk.Button(val_action, text="⏹ Stop", bg="#7f1d1d", fg="white", bd=0, padx=14, pady=8, font=("Segoe UI", 9, "bold"), state="disabled", cursor="hand2")
    btn_stop2.pack(side="left")
    prog_validate = ttk.Progressbar(validate_body, mode="determinate", maximum=100)
    prog_validate.pack(fill="x", pady=4)
    lbl_validate = tk.Label(validate_body, textvariable=var_validate_prog, bg=PANEL, fg=DIM, font=("Consolas", 8), anchor="w")
    lbl_validate.pack(fill="x")

    # ---- RESULTS TAB ----
    results_card, results_body = make_card(tab_results, "RESULTS PREVIEW & EXPORT", "Preview validated proxies, copy, save. Results are watermarked (_AUTHOR.txt) to prove you built it — not someone who copy-pasted.")
    # Treeview
    tree_frame = tk.Frame(results_body, bg=PANEL)
    tree_frame.pack(fill="both", expand=True, pady=6)
    cols = ("proxy","proto","status","latency","origin")
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
    for col, w, label in [("proxy",180,"Proxy"),("proto",80,"Proto"),("status",90,"Status"),("latency",80,"Latency"),("origin",220,"Origin/Error")]:
        tree.heading(col, text=label)
        tree.column(col, width=w, anchor="center" if col!="proxy" else "w")
    tree.pack(side="left", fill="both", expand=True)
    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=vsb.set)
    # Footer buttons
    res_foot = tk.Frame(results_body, bg=PANEL)
    res_foot.pack(fill="x", pady=6)
    def copy_valid():
        if not last_results:
            messagebox.showwarning("Copy", "No validation yet — run Validate or Auto.")
            return
        valid = [r["proxy"] for r in last_results if r.get("status")=="valid"]
        if not valid:
            messagebox.showwarning("Copy", "No valid proxies.")
            return
        root.clipboard_clear(); root.clipboard_append("\n".join(valid))
        messagebox.showinfo("Copied", f"Copied {len(valid)} valid proxies.\nWatermark: {WATERMARK}")
    def save_now():
        if not current_proxies and not last_results:
            messagebox.showwarning("Save", "Nothing to save — scrape first.")
            return
        base = Path(var_output.get()) if var_output.get() else Path.cwd() / "results"
        if base.suffix: base=base.parent
        base.mkdir(parents=True, exist_ok=True)
        out = save_results(current_proxies, last_results, output_dir=base / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), base_dir=base)
        # watermark
        try:
            (out / "_AUTHOR.txt").write_text(f"Generated by {APP_TITLE}\nAuthor: {AUTHOR_FULL}\nWatermark: {WATERMARK}\n", encoding="utf-8")
        except: pass
        messagebox.showinfo("Saved", f"Saved to:\n{out.resolve()}\n\nWatermarked with _AUTHOR.txt")
        try:
            if sys.platform.startswith("win"): os.startfile(str(out))  # type: ignore
        except: pass
        refresh_tree()
    tk.Button(res_foot, text="📋 Copy Valid", bg="#16233f", fg=TEXT, bd=0, padx=12, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2", command=copy_valid).pack(side="left", padx=4)
    tk.Button(res_foot, text="💾 Save Watermarked", bg=ACCENT, fg="white", bd=0, padx=12, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2", command=save_now).pack(side="left", padx=4)
    tk.Button(res_foot, text="📁 Open Folder", bg="#16233f", fg=TEXT, bd=0, padx=12, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2", command=open_results_folder).pack(side="left", padx=4)
    tk.Button(res_foot, text="↻ Refresh", bg="#16233f", fg=TEXT, bd=0, padx=10, pady=6, font=("Segoe UI", 8), cursor="hand2", command=lambda: refresh_tree()).pack(side="right")
    def refresh_tree():
        tree.delete(*tree.get_children())
        if last_results:
            # sort valid first by latency
            sorted_res = sorted(last_results, key=lambda x: (0 if x.get("status")=="valid" and x.get("latency") else 1, x.get("latency",9999) if x.get("status")=="valid" else 9999))
            for r in sorted_res[:400]:
                lat = f"{r.get('latency','—')}ms" if r.get("latency") else "—"
                origin = (r.get("origin") or r.get("error") or r.get("detail") or "")[:40]
                # color via tags
                status = r.get("status","?")
                tag = status
                tree.insert("", "end", values=(r.get("proxy","?"), r.get("protocol","http").upper(), status, lat, origin), tags=(tag,))
            for tag, color in [("valid",OK),("dead",BAD),("timeout",WARN)]:
                try: tree.tag_configure(tag, foreground=color)
                except: pass
            if len(sorted_res)>400:
                tree.insert("", "end", values=(f"... and {len(sorted_res)-400} more — export for full", "", "", "", ""))
        elif current_proxies:
            for p in current_proxies[:300]:
                tree.insert("", "end", values=(p, "HTTP", "unvalidated", "—", "not validated yet"))
        else:
            tree.insert("", "end", values=("No proxies yet — run Auto or Scrape", "", "", "", ""))

    # ---- LOG TAB ----
    log_card, log_body = make_card(tab_log, "LIVE LOG — Watermark & Anti-Copy", "Every run logs watermark. If someone removes author, log still shows it. Results are proof.")
    log_top = tk.Frame(log_body, bg=PANEL)
    log_top.pack(fill="x", pady=(0,4))
    tk.Label(log_top, text=f"Watermark: {WATERMARK}  •  Author: {AUTHOR}  •  {APP_TITLE}", bg=PANEL, fg=DIM2, font=("Consolas", 7)).pack(side="left")
    lbl_log_count = tk.Label(log_top, text="0 lines", bg=PANEL, fg=DIM, font=("Segoe UI", 7))
    lbl_log_count.pack(side="right")
    tk.Button(log_top, text="Clear", bg="#16233f", fg=TEXT, bd=0, padx=8, pady=2, font=("Segoe UI", 7), command=lambda: (txt_log.config(state="normal"), txt_log.delete("1.0","end"), txt_log.config(state="disabled"), lbl_log_count.config(text="0 lines"), setattr(log_state,"lines",0))).pack(side="right", padx=6)  # type: ignore
    txt_log = tk.Text(log_body, bg="#02060e", fg="#cbd5e1", insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8), padx=10, pady=8, wrap="word", state="disabled", height=18)
    txt_log.pack(fill="both", expand=True)
    log_scroll = ttk.Scrollbar(log_body, command=txt_log.yview)
    txt_log.configure(yscrollcommand=log_scroll.set)
    # We'll pack scrollbar overlay via place
    class LogState: lines=0
    log_state = LogState()
    def append_log(tag, msg):
        def _do():
            txt_log.config(state="normal")
            txt_log.insert("end", f"[{tag}] {msg}\n")
            txt_log.see("end")
            txt_log.config(state="disabled")
            log_state.lines+=1
            lbl_log_count.config(text=f"{log_state.lines} lines")
            # also mirror to results tree if needed
        root.after(0, _do)
        log.info(f"{tag}: {msg}")

    # Status bar
    status_bar = tk.Frame(root, bg="#02060e", highlightbackground=BORDER, highlightthickness=1)
    status_bar.pack(fill="x", padx=0, pady=0)
    tk.Label(status_bar, textvariable=var_status, bg="#02060e", fg=DIM, font=("Segoe UI", 8), anchor="w", padx=12, pady=6).pack(side="left", fill="x", expand=True)
    tk.Label(status_bar, text=f"© {AUTHOR}  •  {WATERMARK}  •  Protected", bg="#02060e", fg=DIM2, font=("Consolas", 7), padx=12).pack(side="right")
    # Time
    time_label = tk.Label(status_bar, bg="#02060e", fg=DIM, font=("Consolas", 8), padx=12)
    time_label.pack(side="right")
    def tick():
        time_label.config(text=datetime.now().strftime("%H:%M:%S"))
        var_status.set(f"Ready — {len(current_proxies)} scraped • { (sum(1 for r in (last_results or []) if r.get('status')=='valid')) } valid • by {AUTHOR} • {WATERMARK}")
        root.after(1000, tick)
    tick()

    # Helpers for state
    def set_busy(scrape_busy=False, validate_busy=False, auto_busy=False):
        state = "disabled" if (scrape_busy or validate_busy or auto_busy) else "normal"
        alt_bg = "#24314e" if state=="disabled" else ACCENT
        btn_scrape.config(state=state, bg=alt_bg if scrape_busy or auto_busy else ACCENT)
        btn_stop.config(state="normal" if scrape_busy else "disabled")
        btn_validate.config(state=state, bg=alt_bg if validate_busy or auto_busy else OK)
        btn_stop2.config(state="normal" if validate_busy else "disabled")
        btn_auto.config(state=state, bg="#334155" if auto_busy else ACCENT2, text="⏳  Running..." if auto_busy else "⚡  START AUTO  —  Generate → Validate → Save")
        if state=="disabled":
            var_status.set("Working... — watermark protected")
        else:
            var_status.set(f"Ready — by {AUTHOR}")

    # Scrape
    def do_scrape():
        nonlocal current_proxies
        selected = [sid for sid,v in var_sources.items() if v.get()]
        protos = {p for p,v in var_protocols.items() if v.get()}
        if not selected: messagebox.showwarning("Scrape","Select at least one source"); return
        if not protos: messagebox.showwarning("Scrape","Select protocol"); return
        try: limit = int(var_limit.get() or "0")
        except: limit=500
        threads = 12
        try: threads = int(var_threads.get() or "12")
        except: pass
        stop_event.clear()
        set_busy(scrape_busy=True)
        prog_scrape.config(value=0); var_scrape_prog.set("Starting...")
        append_log("scrape", f"Start scrape {len(selected)} sources {protos} limit={limit} by {AUTHOR}")
        def worker():
            nonlocal current_proxies
            def cb(info):
                t=info.get("type")
                if t=="source_result":
                    root.after(0, lambda: var_scrape_prog.set(f"{info['current']}/{info['total']} {info['label']} +{info['new']} ({info['total_found']})"))
                    root.after(0, lambda: prog_scrape.config(value=int(info['current']/info['total']*100) if info['total'] else 0))
                    append_log("scrape", f"{info['label']}: +{info['new']} total {info['total_found']}")
                elif t=="source_error":
                    append_log("error", f"{info['label']}: {info['error'][:90]}")
                elif t=="note":
                    append_log("info", info["message"])
            proxies, meta = scrape_proxies(selected, protos, limit=limit, progress_callback=cb, stop_event=stop_event, max_workers=threads)
            current_proxies = proxies
            root.after(0, lambda: var_scrape_prog.set(f"Done — {len(proxies)} proxies"))
            root.after(0, lambda: prog_scrape.config(value=100))
            append_log("done", f"Scrape done: {len(proxies)} proxies watermark={WATERMARK}")
            root.after(0, update_stats)
            root.after(0, refresh_tree)
            # fill txt_input
            def fill():
                txt_input.delete("1.0","end")
                txt_input.insert("1.0", "\n".join(proxies[:600]))
                if len(proxies)>600: txt_input.insert("end", f"\n# ... +{len(proxies)-600} more")
                update_input_count()
            root.after(0, fill)
            root.after(0, lambda: set_busy())
        threading.Thread(target=worker, daemon=True).start()
    btn_scrape.config(command=do_scrape)
    btn_stop.config(command=lambda: (stop_event.set(), append_log("info","Stop requested")))
    btn_stop2.config(command=lambda: (stop_event.set(), append_log("info","Stop requested")))

    # Validate
    def do_validate():
        nonlocal last_results
        raw = txt_input.get("1.0","end").strip()
        lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
        if not lines and current_proxies: lines=current_proxies
        import re
        pat=re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})")
        proxies=[]
        for l in lines:
            m=pat.search(l)
            if m: proxies.append(m.group(1))
            elif ":" in l and "." in l: proxies.append(l.split()[0])
        proxies=list(dict.fromkeys(proxies))
        if not proxies: messagebox.showwarning("Validate","No proxies"); return
        if len(proxies)>5000: messagebox.showwarning("Validate","Max 5000"); return
        try: timeout=int(var_timeout.get() or "8")
        except: timeout=8
        test_url=var_test_url.get().strip() or "http://httpbin.org/ip"
        stop_event.clear()
        set_busy(validate_busy=True)
        prog_validate.config(value=0); var_validate_prog.set(f"Validating 0/{len(proxies)}")
        append_log("validate", f"Validating {len(proxies)} timeout={timeout}s {test_url} by {AUTHOR}")
        def worker():
            nonlocal last_results
            def cb(info):
                if info.get("type")=="result":
                    r=info["result"]; cur=info["current"]; total=info["total"]; counts=info["counts"]
                    root.after(0, lambda: var_validate_prog.set(f"{cur}/{total} valid:{counts['valid']} dead:{counts['dead']}"))
                    root.after(0, lambda: prog_validate.config(value=int(cur/total*100)))
                    if r.get("status")=="valid":
                        append_log("valid", f"{r['proxy']} {r.get('latency')}ms {r.get('speed','')}")
                    elif cur%30==0:
                        append_log(r.get("status","info"), f"{r['proxy']} → {r.get('status')} {r.get('error','')[:50]}")
            results, counts = validate_proxies(proxies, timeout=timeout, test_url=test_url, progress_callback=cb, stop_event=stop_event, max_workers=int(var_threads.get() or "80"))
            last_results=results
            append_log("done", f"Valid {counts['valid']}/{len(proxies)} ({round(counts['valid']/len(proxies)*100) if proxies else 0}%) watermark {WATERMARK}")
            root.after(0, lambda: var_validate_prog.set(f"Done — {counts['valid']} valid/{len(proxies)}"))
            root.after(0, lambda: prog_validate.config(value=100))
            root.after(0, update_stats)
            root.after(0, refresh_tree)
            root.after(0, lambda: set_busy())
        threading.Thread(target=worker, daemon=True).start()
    btn_validate.config(command=do_validate)

    # Auto
    def do_auto():
        selected=[sid for sid,v in var_sources.items() if v.get()]
        protos={p for p,v in var_protocols.items() if v.get()}
        if not selected: messagebox.showwarning("Auto","Select source"); return
        if not protos: messagebox.showwarning("Auto","Select protocol"); return
        try: limit=int(var_limit.get() or "0"); timeout=int(var_timeout.get() or "8")
        except: limit,timeout=500,8
        test_url=var_test_url.get().strip() or "http://httpbin.org/ip"
        output=Path(var_output.get()) if var_output.get() else Path.cwd()/"results"
        stop_event.clear()
        set_busy(auto_busy=True)
        auto_prog.config(value=0); auto_status.config(text="Scraping...")
        append_log("auto", f"Auto start {len(selected)} sources limit={limit} → validate → save to {output} by {AUTHOR} {WATERMARK}")
        def worker():
            nonlocal current_proxies, last_results, last_output_dir
            def cb1(info):
                if info.get("type")=="source_result":
                    root.after(0, lambda: auto_status.config(text=f"Scraping {info['current']}/{info['total']} {info['label']}"))
                    root.after(0, lambda: auto_prog.config(value=int(info['current']/info['total']*50)))
                    append_log("scrape", f"{info['label']}: +{info['new']}")
                elif info.get("type")=="note": append_log("info", info["message"])
                elif info.get("type")=="source_error": append_log("error", f"{info['label']}: {info['error'][:80]}")
            proxies, meta = scrape_proxies(selected, protos, limit=limit, progress_callback=cb1, stop_event=stop_event, max_workers=12)
            current_proxies=proxies
            root.after(0, lambda: txt_input.delete("1.0","end"))
            root.after(0, lambda: txt_input.insert("1.0", "\n".join(proxies[:400])))
            root.after(0, update_input_count)
            append_log("auto", f"Scrape {len(proxies)} done, validating...")
            root.after(0, lambda: auto_status.config(text=f"Validating {len(proxies)}..."))
            if not proxies:
                append_log("error","No proxies — abort auto")
                root.after(0, lambda: set_busy())
                return
            def cb2(info):
                if info.get("type")=="result":
                    r=info["result"]; counts=info["counts"]
                    root.after(0, lambda: auto_status.config(text=f"Validating {info['current']}/{info['total']} valid:{counts['valid']}"))
                    root.after(0, lambda: auto_prog.config(value=50+int(info['current']/info['total']*50)))
                    if r.get("status")=="valid": append_log("valid", f"{r['proxy']} {r.get('latency')}ms")
            results, counts = validate_proxies(proxies, timeout=timeout, test_url=test_url, progress_callback=cb2, stop_event=stop_event, max_workers=int(var_threads.get() or "80"))
            last_results=results
            append_log("done", f"Validate {counts['valid']} valid")
            root.after(0, update_stats)
            root.after(0, refresh_tree)
            # save watermarked
            try:
                if output.suffix: base=output.parent
                else: base=output
                base.mkdir(parents=True, exist_ok=True)
                out_dir=base / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                out=save_results(proxies, results, output_dir=out_dir, base_dir=base)
                # watermark
                (out / "_AUTHOR.txt").write_text(f"Generated by {APP_TITLE}\nAuthor: {AUTHOR_FULL}\nWatermark: {WATERMARK}\nVersion: {VERSION}\nTimestamp: {datetime.now().isoformat()}\nRepository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator\nProtected — do not remove.\n", encoding="utf-8")
                try:
                    stats_path=out/"stats.json"
                    if stats_path.exists():
                        stats=json.loads(stats_path.read_text(encoding="utf-8"))
                        stats.update({"author":AUTHOR,"author_full":AUTHOR_FULL,"watermark":WATERMARK,"app":APP_TITLE,"version":VERSION,"protected":True})
                        stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
                except: pass
                last_output_dir=out
                append_log("done", f"Saved watermarked to {out}")
                root.after(0, lambda: auto_status.config(text=f"Done — {counts['valid']} valid → {out.name}"))
                root.after(0, lambda: auto_prog.config(value=100))
                root.after(0, lambda: messagebox.showinfo("Auto Done", f"Saved {counts['valid']} valid to:\n{out.resolve()}\n\nWatermark: {WATERMARK}\n_Author.txt proves authenticity."))
                try:
                    if sys.platform.startswith("win"): os.startfile(str(out))  # type: ignore
                except: pass
            except Exception as e:
                append_log("error", f"Save failed: {e}")
                root.after(0, lambda: messagebox.showerror("Save", str(e)))
            root.after(0, lambda: set_busy())
        threading.Thread(target=worker, daemon=True).start()
    btn_auto.config(command=do_auto)

    # Notebook tab change -> refresh
    def on_tab(e):
        if notebook.index(notebook.select()) == 3:  # results
            refresh_tree()
    notebook.bind("<<NotebookTabChanged>>", on_tab)

    # Close handler
    def on_close():
        if messagebox.askokcancel("Quit", f"Quit {APP_TITLE}?\n\n© {AUTHOR} — Protected build {WATERMARK}"):
            stop_event.set()
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Initial log watermark
    append_log("info", f"{APP_TITLE} launched — by {AUTHOR} — watermark {WATERMARK}")
    append_log("info", "Tip: Use AUTO tab for one-click harvest (protected & watermarked)")

    root.mainloop()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=f"{APP_TITLE} — by {AUTHOR}")
    parser.add_argument("--auto", action="store_true", help="Auto CLI: scrape→validate→save")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--test-url", default="http://httpbin.org/ip")
    parser.add_argument("--output", type=str, default="results")
    parser.add_argument("--threads", type=int, default=80)
    parser.add_argument("--sources", type=str, default="")
    parser.add_argument("--protocols", type=str, default="http,https,socks4,socks5")
    parser.add_argument("--gui", action="store_true", help="Force GUI")
    parser.add_argument("--web", action="store_true", help="Launch web dashboard")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    if args.web:
        from app import app
        print(f"Launching web at http://0.0.0.0:{args.port} — {APP_TITLE}")
        app.run(host="0.0.0.0", port=args.port, threaded=True)
        return
    if args.auto and not args.gui:
        prots={p.strip().lower() for p in args.protocols.split(",") if p.strip()}
        sids=[s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else list(SOURCES.keys())
        sids=[s for s in sids if s in SOURCES] or list(SOURCES.keys())
        run_auto(limit=args.limit, timeout=args.timeout, test_url=args.test_url, protocols=prots, source_ids=sids, output=Path(args.output).resolve() if args.output else None, threads_validate=args.threads)
        return
    # GUI fallback if no display -> CLI
    if not args.gui and sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print(f"No display — running auto CLI {APP_TITLE}")
        run_auto(limit=args.limit, timeout=args.timeout, test_url=args.test_url)
        return
    try: launch_gui()
    except Exception as e:
        log.exception("GUI failed")
        print(f"GUI failed ({e}), running auto CLI")
        run_auto()

if __name__ == "__main__":
    # Early watermark check prints author
    if not verify_integrity():
        print(f"[!] Warning: {WATERMARK} missing — build may be tampered (author: {AUTHOR})")
    else:
        print(f"[ok] {APP_TITLE} by {AUTHOR} — watermark {WATERMARK} verified")
    main()
