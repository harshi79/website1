#!/usr/bin/env python3
"""
Ultimate Proxy Scrapper — Desktop EXE
=====================================
One-click advanced proxy harvester that auto-generates, validates and saves results
to a timestamped folder.

Run without args -> launches GUI.
Run with --auto   -> CLI auto mode (scrape -> validate -> save -> exit)
Build to EXE:  pyinstaller --onefile --windowed --name UltimateProxyScrapper --icon=icon.ico main.py
               or  python -m PyInstaller UltimateProxyScrapper.spec
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Ensure logs visible
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("desktop")

# local imports
try:
    from proxy_engine import SOURCES, SAMPLE_PROXIES, scrape_proxies, validate_proxies, save_results
except ImportError:
    # fallback if proxy_engine not found (should not happen)
    print("proxy_engine.py not found — make sure it is next to main.py")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CLI auto mode
# ---------------------------------------------------------------------------
def run_auto(
    limit: int = 500,
    timeout: int = 8,
    test_url: str = "http://httpbin.org/ip",
    protocols: Optional[Set[str]] = None,
    source_ids: Optional[List[str]] = None,
    output: Optional[Path] = None,
    threads_validate: int = 80,
    verbose: bool = True,
) -> Path:
    if protocols is None:
        protocols = {"http", "https", "socks4", "socks5"}
    if source_ids is None:
        source_ids = list(SOURCES.keys())

    print("="*70)
    print(" ULTIMATE PROXY SCRAPPER — AUTO MODE")
    print("="*70)
    print(f" Sources: {len(source_ids)}  Protocols: {protocols}  Limit: {limit or '∞'}")
    print(f" Timeout: {timeout}s  Test URL: {test_url}")
    print("-"*70)

    stop_event = threading.Event()

    def progress_cb(info: Dict[str, Any]):
        t = info.get("type")
        if t == "source_result":
            print(f" [✓] {info['label']:30s} +{info['new']:4d}  (total {info['total_found']:5d})")
        elif t == "source_error":
            print(f" [✗] {info['label']:30s} ERROR: {info['error'][:80]}")
        elif t == "note":
            print(f" [i] {info['message']}")
        elif t == "result":
            r = info["result"]
            status = r.get("status")
            icon = "✓" if status=="valid" else "✗" if status in ("dead","timeout") else "?"
            lat = f"{r.get('latency','?')}ms" if r.get("latency") else ""
            if info["current"] % 50 == 0 or status=="valid":
                print(f"   [{icon}] {r['proxy']:22s} {status:8s} {lat:8s} ({info['current']}/{info['total']})")
        elif t == "progress":
            # occasional
            pass

    print("\n[1/3] Scraping proxies...")
    start = time.time()
    proxies, meta = scrape_proxies(
        source_ids=source_ids,
        protocols=protocols,
        limit=limit,
        progress_callback=progress_cb,
        stop_event=stop_event,
        timeout=12,
    )
    elapsed = time.time() - start
    print(f"\n -> Scraped {len(proxies)} unique proxies in {elapsed:.1f}s")
    if meta.get("demo_used"):
        print("    (demo sample used — network restricted, real run will fetch live)")
    if not proxies:
        print(" No proxies found — aborting.")
        return Path(".")

    print(f"\n[2/3] Validating {len(proxies)} proxies with {threads_validate} threads...")
    start = time.time()
    results, counts = validate_proxies(
        proxies=proxies,
        timeout=timeout,
        test_url=test_url,
        protocol_hint="http",
        progress_callback=progress_cb,
        max_workers=threads_validate,
    )
    elapsed = time.time() - start
    print("\n" + "-"*70)
    print(f" Validation done in {elapsed:.1f}s")
    print(f"  Valid   : {counts['valid']}")
    print(f"  Dead    : {counts['dead']}")
    print(f"  Timeout : {counts['timeout']}")
    print(f"  Invalid : {counts['invalid']}")
    print(f"  Error   : {counts['error']}")
    if counts["valid"]:
        avg = sum(r["latency"] for r in results if r.get("status")=="valid" and r.get("latency")) // counts["valid"]
        print(f"  Avg latency (valid): {avg}ms")
    print("-"*70)

    print("\n[3/3] Saving results...")
    # Determine output base cleanly
    if output is None:
        base = Path.cwd() / "results"
    else:
        base = Path(output)
        if base.suffix:  # looks like a file
            base = base.parent
    base.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = base / timestamp
    out = save_results(proxies, results, output_dir=out_dir, base_dir=base)

    print(f"\n Saved to: {out.resolve()}")
    print(f"  - valid.txt   ({counts['valid']} proxies)")
    print(f"  - all.txt     ({len(proxies)} proxies)")
    print(f"  - valid.json / valid.csv / all.json / stats.json")
    print(f"  - latest/ copy updated")
    try:
        size = (out / "valid.txt").stat().st_size
        print(f"  - valid.txt size: {size} bytes")
    except:
        pass
    print("\nDone! Open the folder to use your proxies.")
    print("="*70)
    return out

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
def launch_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import subprocess

    # Try to use modern theme
    root = tk.Tk()
    root.title("Ultimate Proxy Scrapper — Advanced")
    root.geometry("1140x760")
    root.minsize(1020, 680)

    # Icon handling — try to set if icon exists
    try:
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
    except:
        pass

    # Style
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except:
        pass
    BG = "#070b14"
    PANEL = "#0e1629"
    PANEL2 = "#111d33"
    BORDER = "#24304a"
    ACCENT = "#6366f1"
    ACCENT2 = "#8b5cf6"
    TEXT = "#e6edf6"
    DIM = "#8b9bb4"
    OK = "#10b981"
    root.configure(bg=BG)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=PANEL, relief="flat")
    style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 9))
    style.configure("Card.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 16, "bold"))
    style.configure("Sub.TLabel", background=BG, foreground=DIM, font=("Segoe UI", 9))
    style.configure("Small.TLabel", background=PANEL, foreground=DIM, font=("Segoe UI", 8))
    style.configure("Header.TLabel", background=PANEL, foreground=DIM, font=("Segoe UI", 8, "bold"))
    style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6)
    style.configure("Accent.TButton", background=ACCENT, foreground="white")
    style.map("Accent.TButton", background=[("active", ACCENT2)])
    style.configure("Success.TButton", background=OK, foreground="#022c22")
    style.configure("TProgressbar", troughcolor="#02060e", background=ACCENT, bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)
    style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
    style.configure("TEntry", fieldbackground="#02060e", foreground=TEXT)
    style.configure("TCombobox", fieldbackground="#02060e", background="#02060e", foreground=TEXT)

    # Variables
    var_limit = tk.StringVar(value="500")
    var_timeout = tk.StringVar(value="8")
    var_test_url = tk.StringVar(value="http://httpbin.org/ip")
    var_threads = tk.StringVar(value="80")
    var_output = tk.StringVar(value=str((Path.cwd() / "results").resolve()))
    var_protocols = {p: tk.BooleanVar(value=(p in ("http","https"))) for p in ("http","https","socks4","socks5")}
    var_sources: Dict[str, tk.BooleanVar] = {sid: tk.BooleanVar(value=True) for sid in SOURCES}
    # progress
    var_scrape_prog = tk.StringVar(value="Ready")
    var_validate_prog = tk.StringVar(value="Ready")

    # State
    scrape_thread: Optional[threading.Thread] = None
    validate_thread: Optional[threading.Thread] = None
    stop_event = threading.Event()
    current_proxies: List[str] = []
    last_results: Optional[List[Dict[str, Any]]] = None
    last_output_dir: Optional[Path] = None

    # ---- Header ----
    header = ttk.Frame(root)
    header.pack(fill="x", padx=16, pady=(14, 8))
    # brand
    brand = ttk.Frame(header)
    brand.pack(side="left", fill="y")
    ttk.Label(brand, text="⬢ Ultimate Proxy Scrapper", style="Title.TLabel").pack(anchor="w")
    ttk.Label(brand, text="Auto-harvest • Validate • Export  →  results/ with TXT/JSON/CSV & stats", style="Sub.TLabel").pack(anchor="w")
    # header actions
    hbtns = ttk.Frame(header)
    hbtns.pack(side="right")
    def open_results():
        p = Path(var_output.get())
        if not p.exists():
            messagebox.showinfo("Results", f"Folder not found:\n{p}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(p))  # type: ignore
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as e:
            messagebox.showerror("Open", str(e))
    ttk.Button(hbtns, text="📁 Open Results", command=open_results).pack(side="left", padx=4)
    ttk.Button(hbtns, text="🌐 Web Dashboard", command=lambda: webbrowser.open("http://localhost:5000")).pack(side="left", padx=4)
    # stats top
    stats_frame = ttk.Frame(root)
    stats_frame.pack(fill="x", padx=16, pady=4)
    stat_cards = {}
    for label, key in [("Total", "total"), ("Valid", "valid"), ("Avg ms", "latency"), ("Sources", "sources")]:
        card = tk.Frame(stats_frame, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, bd=0)
        card.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(card, text=label.upper(), bg=PANEL, fg=DIM, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(8,0))
        val = tk.Label(card, text="0" if key!="latency" else "—", bg=PANEL, fg=TEXT, font=("Segoe UI", 16, "bold"))
        val.pack(anchor="w", padx=10)
        sub = tk.Label(card, text="in memory" if key=="total" else "0% success" if key=="valid" else "validate to measure" if key=="latency" else "18 live", bg=PANEL, fg=DIM, font=("Segoe UI", 8))
        sub.pack(anchor="w", padx=10, pady=(0,8))
        stat_cards[key] = (val, sub)
    def update_stats_top():
        total = len(current_proxies)
        if last_results:
            valid = sum(1 for r in last_results if r.get("status")=="valid")
            lats = [r["latency"] for r in last_results if r.get("status")=="valid" and r.get("latency")]
            avg = sum(lats)//len(lats) if lats else 0
            stat_cards["total"][0].config(text=str(total))
            stat_cards["valid"][0].config(text=str(valid), fg=OK if valid else TEXT)
            stat_cards["valid"][1].config(text=f"{round(valid/max(1,total)*100)}% success")
            stat_cards["latency"][0].config(text=str(avg) if avg else "—")
            stat_cards["latency"][1].config(text="fast <800ms" if avg and avg<800 else "medium" if avg and avg<2000 else "validate to measure" if not avg else "slow")
        else:
            stat_cards["total"][0].config(text=str(total))
            stat_cards["valid"][0].config(text="0")
            stat_cards["valid"][1].config(text="0% success")
            stat_cards["latency"][0].config(text="—")
        stat_cards["sources"][0].config(text=str(len(SOURCES)))
    update_stats_top()

    # ---- Main Panes ----
    paned = ttk.PanedWindow(root, orient="horizontal")
    paned.pack(fill="both", expand=True, padx=16, pady=8)

    left = ttk.Frame(paned)
    right = ttk.Frame(paned)
    paned.add(left, weight=1)
    paned.add(right, weight=1)

    # Left scroll
    left_canvas = tk.Canvas(left, bg=BG, highlightthickness=0)
    left_scroll = ttk.Scrollbar(left, orient="vertical", command=left_canvas.yview)
    left_inner = ttk.Frame(left_canvas)
    left_inner.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
    left_canvas.create_window((0,0), window=left_inner, anchor="nw")
    left_canvas.configure(yscrollcommand=left_scroll.set)
    left_canvas.pack(side="left", fill="both", expand=True)
    left_scroll.pack(side="right", fill="y")

    # ---- Scrape Card ----
    scrape_card = tk.Frame(left_inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    scrape_card.pack(fill="x", pady=6, padx=2)
    tk.Label(scrape_card, text="①  SCRAPE", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(10,4))
    tk.Label(scrape_card, text="Select sources & protocols, then scrape. Auto mode does this for you.", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w", padx=12)

    # sources grid with checkboxes
    src_frame = tk.Frame(scrape_card, bg=PANEL)
    src_frame.pack(fill="x", padx=12, pady=8)
    # two columns
    src_inner = tk.Frame(src_frame, bg=PANEL)
    src_inner.pack(fill="x")
    row = col = 0
    for idx, (sid, cfg) in enumerate(SOURCES.items()):
        cb = tk.Checkbutton(src_inner, text=f"{cfg['label']} ({cfg['protocol']})", variable=var_sources[sid],
                            bg=PANEL, fg=TEXT, selectcolor="#02060e", activebackground=PANEL, activeforeground=TEXT,
                            font=("Segoe UI", 8))
        cb.grid(row=row, column=col, sticky="w", padx=6, pady=2)
        col += 1
        if col>1:
            col=0; row+=1
    # select all/none
    sel_frame = tk.Frame(scrape_card, bg=PANEL)
    sel_frame.pack(fill="x", padx=12, pady=(0,6))
    tk.Button(sel_frame, text="Select all", bg="#1a2744", fg=TEXT, bd=0, padx=8, pady=2, font=("Segoe UI", 8),
              command=lambda: [v.set(True) for v in var_sources.values()]).pack(side="left", padx=4)
    tk.Button(sel_frame, text="None", bg="#1a2744", fg=TEXT, bd=0, padx=8, pady=2, font=("Segoe UI", 8),
              command=lambda: [v.set(False) for v in var_sources.values()]).pack(side="left", padx=4)

    # protocol toggles
    proto_frame = tk.Frame(scrape_card, bg=PANEL)
    proto_frame.pack(fill="x", padx=12, pady=6)
    tk.Label(proto_frame, text="Protocols:", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(side="left")
    for proto in ("http","https","socks4","socks5"):
        tk.Checkbutton(proto_frame, text=proto.upper(), variable=var_protocols[proto],
                       bg=PANEL, fg=TEXT, selectcolor=ACCENT, activebackground=PANEL, font=("Segoe UI", 8, "bold")).pack(side="left", padx=6)

    # limit / threads row
    limit_frame = tk.Frame(scrape_card, bg=PANEL)
    limit_frame.pack(fill="x", padx=12, pady=6)
    tk.Label(limit_frame, text="Limit:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left")
    limit_combo = ttk.Combobox(limit_frame, textvariable=var_limit, values=["100","500","1000","2000","5000","0"], width=7, state="readonly")
    limit_combo.pack(side="left", padx=6)
    tk.Label(limit_frame, text="(0 = no limit)", bg=PANEL, fg=DIM, font=("Segoe UI", 7)).pack(side="left")
    tk.Label(limit_frame, text="Threads:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left", padx=(12,0))
    tk.Entry(limit_frame, textvariable=var_threads, width=4, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER).pack(side="left", padx=6)

    # scrape button + progress
    scrape_btn_frame = tk.Frame(scrape_card, bg=PANEL)
    scrape_btn_frame.pack(fill="x", padx=12, pady=(6,8))
    btn_scrape = tk.Button(scrape_btn_frame, text="▶  Scrape Proxies", bg=ACCENT, fg="white", bd=0, padx=14, pady=7, font=("Segoe UI", 9, "bold"), cursor="hand2")
    btn_scrape.pack(side="left", fill="x", expand=True, padx=(0,6))
    btn_stop = tk.Button(scrape_btn_frame, text="⏹ Stop", bg="#7f1d1d", fg="white", bd=0, padx=12, pady=7, font=("Segoe UI", 9, "bold"), cursor="hand2", state="disabled")
    btn_stop.pack(side="left")
    prog_scrape = ttk.Progressbar(scrape_card, mode="determinate", maximum=100)
    prog_scrape.pack(fill="x", padx=12, pady=(0,4))
    lbl_scrape = tk.Label(scrape_card, textvariable=var_scrape_prog, bg=PANEL, fg=DIM, font=("Consolas", 8), anchor="w")
    lbl_scrape.pack(fill="x", padx=12, pady=(0,8))

    # ---- Validate Card ----
    validate_card = tk.Frame(left_inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    validate_card.pack(fill="x", pady=6, padx=2)
    tk.Label(validate_card, text="②  VALIDATE", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(10,4))
    # timeout / url
    val_row = tk.Frame(validate_card, bg=PANEL)
    val_row.pack(fill="x", padx=12, pady=6)
    tk.Label(val_row, text="Timeout:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left")
    ttk.Combobox(val_row, textvariable=var_timeout, values=["3","5","8","12","15"], width=4, state="readonly").pack(side="left", padx=6)
    tk.Label(val_row, text="Test URL:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left", padx=(12,0))
    tk.Entry(val_row, textvariable=var_test_url, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8)).pack(side="left", fill="x", expand=True, padx=6)
    # validate buttons
    val_btn_frame = tk.Frame(validate_card, bg=PANEL)
    val_btn_frame.pack(fill="x", padx=12, pady=6)
    btn_validate = tk.Button(val_btn_frame, text="✔  Validate Proxies", bg=OK, fg="#022c22", bd=0, padx=14, pady=7, font=("Segoe UI", 9, "bold"), cursor="hand2")
    btn_validate.pack(side="left", fill="x", expand=True, padx=(0,6))
    btn_stop2 = tk.Button(val_btn_frame, text="⏹ Stop", bg="#7f1d1d", fg="white", bd=0, padx=12, pady=7, font=("Segoe UI", 9, "bold"), cursor="hand2", state="disabled")
    btn_stop2.pack(side="left")
    # use scraped button
    use_frame = tk.Frame(validate_card, bg=PANEL)
    use_frame.pack(fill="x", padx=12, pady=(0,6))
    btn_use = tk.Button(use_frame, text="↺ Use scraped proxies", bg="#1a2744", fg=TEXT, bd=0, padx=8, pady=4, font=("Segoe UI", 8))
    btn_use.pack(side="left")
    tk.Label(use_frame, text="or paste custom list below", bg=PANEL, fg=DIM, font=("Segoe UI", 7)).pack(side="left", padx=8)
    prog_validate = ttk.Progressbar(validate_card, mode="determinate", maximum=100)
    prog_validate.pack(fill="x", padx=12, pady=(0,4))
    lbl_validate = tk.Label(validate_card, textvariable=var_validate_prog, bg=PANEL, fg=DIM, font=("Consolas", 8), anchor="w")
    lbl_validate.pack(fill="x", padx=12, pady=(0,8))

    # ---- Auto Card ----
    auto_card = tk.Frame(left_inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    auto_card.pack(fill="x", pady=6, padx=2)
    tk.Label(auto_card, text="③  AUTO  —  ONE CLICK HARVEST", bg=PANEL, fg="#a5b4fc", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10,4))
    tk.Label(auto_card, text="Scrapes → Validates → Saves to results/YYYY-MM-DD_HH-MM-SS/ (valid.txt, json, csv, stats.json)", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w", padx=12)
    auto_btn = tk.Button(auto_card, text="⚡  START AUTO (Generate → Check → Save)", bg=ACCENT2, fg="white", bd=0, padx=14, pady=10, font=("Segoe UI", 10, "bold"), cursor="hand2")
    auto_btn.pack(fill="x", padx=12, pady=10)
    # output folder
    out_frame = tk.Frame(auto_card, bg=PANEL)
    out_frame.pack(fill="x", padx=12, pady=(0,8))
    tk.Label(out_frame, text="Output:", bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left")
    tk.Entry(out_frame, textvariable=var_output, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8)).pack(side="left", fill="x", expand=True, padx=6)
    def browse():
        d = filedialog.askdirectory(initialdir=var_output.get() or str(Path.cwd()))
        if d:
            var_output.set(d)
    tk.Button(out_frame, text="Browse", bg="#1a2744", fg=TEXT, bd=0, padx=8, pady=2, font=("Segoe UI", 8), command=browse).pack(side="left")

    # ---- Right side: Log + Proxy preview + Manual input ----
    # Manual proxy input (for custom validate)
    input_card = tk.Frame(right, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    input_card.pack(fill="x", pady=6, padx=2)
    tk.Label(input_card, text="PROXY LIST (for custom validate)", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(8,2))
    txt_input = tk.Text(input_card, height=6, bg="#02060e", fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8), padx=8, pady=6)
    txt_input.pack(fill="x", padx=12, pady=(0,8))
    txt_input.insert("1.0", "# Paste proxies here or click 'Use scraped proxies'\n# e.g.\n# 1.2.3.4:8080\n# 5.6.7.8:3128")
    # proxy count label
    lbl_count = tk.Label(input_card, text="0 proxies loaded", bg=PANEL, fg=DIM, font=("Segoe UI", 7))
    lbl_count.pack(anchor="e", padx=12, pady=(0,6))
    def on_input_change(*args):
        # limit to avoid lag
        pass
    # Log
    log_card = tk.Frame(right, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    log_card.pack(fill="both", expand=True, pady=6, padx=2)
    log_header = tk.Frame(log_card, bg=PANEL)
    log_header.pack(fill="x", padx=12, pady=(8,4))
    tk.Label(log_header, text="LIVE LOG", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(side="left")
    lbl_log_count = tk.Label(log_header, text="0 lines", bg=PANEL, fg=DIM, font=("Segoe UI", 7))
    lbl_log_count.pack(side="right")
    def clear_log():
        txt_log.config(state="normal")
        txt_log.delete("1.0", "end")
        txt_log.config(state="disabled")
        lbl_log_count.config(text="0 lines")
    tk.Button(log_header, text="Clear", bg="#1a2744", fg=TEXT, bd=0, padx=6, pady=1, font=("Segoe UI", 7), command=clear_log).pack(side="right", padx=6)
    txt_log = tk.Text(log_card, bg="#02060e", fg="#cbd5e1", insertbackground=TEXT, relief="flat", highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8), padx=8, pady=6, wrap="word", state="disabled")
    txt_log.pack(fill="both", expand=True, padx=12, pady=(0,8))
    # add scrollbar to log
    log_scroll = ttk.Scrollbar(log_card, command=txt_log.yview)
    txt_log.configure(yscrollcommand=log_scroll.set)
    # Place scrollbar overlay - pack issue, embed via place?
    # Keep simple: log_scroll not needed as text scrolls itself.

    # Footer actions
    foot = tk.Frame(right, bg=BG)
    foot.pack(fill="x", pady=6, padx=2)
    def copy_valid():
        if not last_results:
            messagebox.showwarning("Copy", "No validation results yet")
            return
        valid = [r["proxy"] for r in last_results if r.get("status")=="valid"]
        if not valid:
            messagebox.showwarning("Copy", "No valid proxies")
            return
        root.clipboard_clear()
        root.clipboard_append("\n".join(valid))
        messagebox.showinfo("Copy", f"Copied {len(valid)} valid proxies to clipboard")
    def save_now():
        if not current_proxies and not last_results:
            messagebox.showwarning("Save", "Nothing to save — scrape first")
            return
        # if validated, save validated; else save scraped
        out = save_results(current_proxies, last_results, base_dir=Path(var_output.get()) if var_output.get() else None)
        messagebox.showinfo("Saved", f"Saved to:\n{out.resolve()}")
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(out))  # type: ignore
        except:
            pass
    tk.Button(foot, text="📋 Copy Valid", bg="#1a2744", fg=TEXT, bd=0, padx=10, pady=6, font=("Segoe UI", 8, "bold"), command=copy_valid).pack(side="left", padx=4)
    tk.Button(foot, text="💾 Save Now", bg=ACCENT, fg="white", bd=0, padx=10, pady=6, font=("Segoe UI", 8, "bold"), command=save_now).pack(side="left", padx=4)
    tk.Button(foot, text="📁 Open Folder", bg="#1a2744", fg=TEXT, bd=0, padx=10, pady=6, font=("Segoe UI", 8, "bold"), command=open_results).pack(side="left", padx=4)

    # Helpers
    log_lock = threading.Lock()
    log_lines = [0]
    def append_log(tag, msg):
        def _do():
            txt_log.config(state="normal")
            # color tag?
            prefix = f"[{tag}] " if tag else ""
            txt_log.insert("end", f"{prefix}{msg}\n")
            txt_log.see("end")
            txt_log.config(state="disabled")
            log_lines[0]+=1
            lbl_log_count.config(text=f"{log_lines[0]} lines")
        root.after(0, _do)
        log.info(f"{tag}: {msg}")

    def set_scrape_state(running: bool):
        def _do():
            btn_scrape.config(state="disabled" if running else "normal", bg="#24304a" if running else ACCENT)
            btn_stop.config(state="normal" if running else "disabled")
            auto_btn.config(state="disabled" if running else "normal", bg="#334155" if running else ACCENT2)
            btn_validate.config(state="disabled" if running else "normal")
        root.after(0, _do)
    def set_validate_state(running: bool):
        def _do():
            btn_validate.config(state="disabled" if running else "normal", bg="#24304a" if running else OK)
            btn_stop2.config(state="normal" if running else "disabled")
            auto_btn.config(state="disabled" if running else "normal")
            btn_scrape.config(state="disabled" if running else "normal")
        root.after(0, _do)

    # Scrape action
    def do_scrape():
        nonlocal current_proxies, last_results
        selected = [sid for sid, v in var_sources.items() if v.get()]
        if not selected:
            messagebox.showwarning("Scrape", "Select at least one source")
            return
        protos = {p for p, v in var_protocols.items() if v.get()}
        if not protos:
            messagebox.showwarning("Scrape", "Select at least one protocol")
            return
        try:
            limit = int(var_limit.get() or "0")
        except:
            limit = 500
        threads = 12
        try:
            threads = int(var_threads.get() or "12")
        except:
            pass
        stop_event.clear()
        set_scrape_state(True)
        prog_scrape.config(value=0)
        var_scrape_prog.set("Starting...")
        append_log("scrape", f"Starting scrape {len(selected)} sources, protocols={protos}, limit={limit}")

        def worker():
            nonlocal current_proxies
            def cb(info):
                t = info.get("type")
                if t == "source_result":
                    root.after(0, lambda: var_scrape_prog.set(f"{info['current']}/{info['total']} — {info['label']} +{info['new']} (total {info['total_found']})"))
                    root.after(0, lambda: prog_scrape.config(value= int(info['current']/info['total']*100) if info['total'] else 0))
                    append_log("scrape", f"{info['label']}: +{info['new']} (total {info['total_found']})")
                    cur = info['total_found']
                    root.after(0, lambda c=cur: lbl_count.config(text=f"{c} proxies scraped"))
                elif t == "source_error":
                    append_log("error", f"{info['label']}: {info['error'][:100]}")
                elif t == "note":
                    append_log("info", info['message'])
                elif t == "progress":
                    root.after(0, lambda: prog_scrape.config(value= int(info['current']/info['total']*100) if info['total'] else 0))
            proxies, meta = scrape_proxies(selected, protos, limit=limit, progress_callback=cb, stop_event=stop_event, max_workers=threads)
            current_proxies = proxies
            last_results = None
            root.after(0, lambda: lbl_count.config(text=f"{len(proxies)} proxies scraped"))
            root.after(0, update_stats_top)
            if meta.get("demo_used"):
                append_log("info", "Demo sample used — real scrape needs internet")
            append_log("done", f"Scrape finished: {len(proxies)} proxies")
            root.after(0, lambda: var_scrape_prog.set(f"Done — {len(proxies)} proxies"))
            root.after(0, lambda: prog_scrape.config(value=100))
            # fill txt_input
            def fill():
                txt_input.delete("1.0", "end")
                txt_input.insert("1.0", "\n".join(proxies[:500]))
                if len(proxies)>500:
                    txt_input.insert("end", f"\n# ... and {len(proxies)-500} more (see results folder)")
            root.after(0, fill)
            set_scrape_state(False)
        threading.Thread(target=worker, daemon=True).start()

    btn_scrape.config(command=do_scrape)
    btn_stop.config(command=lambda: (stop_event.set(), append_log("info", "Stop requested")))
    btn_stop2.config(command=lambda: (stop_event.set(), append_log("info", "Stop requested")))

    def do_use_scraped():
        if not current_proxies:
            messagebox.showwarning("Validate", "No scraped proxies — scrape first")
            return
        txt_input.delete("1.0", "end")
        txt_input.insert("1.0", "\n".join(current_proxies[:500]))
        if len(current_proxies)>500:
            txt_input.insert("end", f"\n# ... and {len(current_proxies)-500} more (all will be validated)")
        append_log("info", f"Loaded {len(current_proxies)} scraped proxies into validator")
        # keep current_proxies for validate if input is scraped? validate will read from txt_input if needed
        # but we also keep current_proxies
    btn_use.config(command=do_use_scraped)

    def do_validate():
        nonlocal last_results
        # get proxies from txt_input if filled, else current_proxies
        raw = txt_input.get("1.0", "end").strip()
        # filter lines
        lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
        # if lines empty but current_proxies exists, use that
        if not lines and current_proxies:
            lines = current_proxies
        # also extract ip:port via regex if needed
        import re
        ip_port = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})")
        proxies = []
        for l in lines:
            m = ip_port.search(l)
            if m:
                proxies.append(m.group(1))
            elif ":" in l and "." in l:
                proxies.append(l.split()[0])
        proxies = list(dict.fromkeys(proxies))  # dedupe
        if not proxies:
            messagebox.showwarning("Validate", "No proxies to validate — paste list or scrape first")
            return
        if len(proxies)>5000:
            messagebox.showwarning("Validate", "Too many (max 5000)")
            return
        try:
            timeout = int(var_timeout.get() or "8")
        except:
            timeout = 8
        test_url = var_test_url.get().strip() or "http://httpbin.org/ip"
        stop_event.clear()
        set_validate_state(True)
        prog_validate.config(value=0)
        var_validate_prog.set(f"Validating 0 / {len(proxies)}")
        append_log("validate", f"Validating {len(proxies)} proxies timeout={timeout}s url={test_url}")

        def worker():
            nonlocal last_results
            counts = {"valid":0, "dead":0, "timeout":0, "invalid":0, "error":0}
            def cb(info):
                if info.get("type")=="result":
                    r = info["result"]
                    cur = info["current"]; total = info["total"]; counts.update(info["counts"])
                    root.after(0, lambda: var_validate_prog.set(f"{cur}/{total}  valid:{counts['valid']} dead:{counts['dead']} timeout:{counts['timeout']}"))
                    root.after(0, lambda: prog_validate.config(value= int(cur/total*100) ))
                    if r.get("status")=="valid":
                        append_log("valid", f"{r['proxy']:22s} {r.get('latency','?')}ms {r.get('speed','')}")
                    elif info["current"] % 25==0:
                        append_log(r.get("status","info"), f"{r['proxy']} → {r.get('status')} {r.get('error','')[:50]}")
                    # update top stats periodically
                    if cur % 50==0:
                        root.after(0, update_stats_top)
                elif info.get("type")=="progress":
                    pass
            results, final_counts = validate_proxies(proxies, timeout=timeout, test_url=test_url, progress_callback=cb, stop_event=stop_event,
                                                     max_workers=int(var_threads.get() or "80"))
            last_results = results
            append_log("done", f"Validation done: valid {final_counts['valid']}/{len(proxies)} ({round(final_counts['valid']/len(proxies)*100) if proxies else 0}%)")
            root.after(0, lambda: var_validate_prog.set(f"Done — {final_counts['valid']} valid / {len(proxies)}"))
            root.after(0, lambda: prog_validate.config(value=100))
            root.after(0, update_stats_top)
            set_validate_state(False)
            # auto save?
            # keep for manual save
        threading.Thread(target=worker, daemon=True).start()

    btn_validate.config(command=do_validate)

    # Auto
    def do_auto():
        selected = [sid for sid, v in var_sources.items() if v.get()]
        if not selected:
            messagebox.showwarning("Auto", "Select at least one source")
            return
        protos = {p for p, v in var_protocols.items() if v.get()}
        if not protos:
            messagebox.showwarning("Auto", "Select protocol")
            return
        try:
            limit = int(var_limit.get() or "0")
            timeout = int(var_timeout.get() or "8")
        except:
            limit, timeout = 500, 8
        test_url = var_test_url.get().strip() or "http://httpbin.org/ip"
        output = Path(var_output.get()) if var_output.get() else Path.cwd() / "results"
        stop_event.clear()
        set_scrape_state(True)
        set_validate_state(True)
        auto_btn.config(state="disabled", text="⏳  Running auto... (see log)")
        append_log("auto", f"Auto start: scrape {len(selected)} sources limit={limit} → validate timeout={timeout}s → save to {output}")

        def worker():
            nonlocal current_proxies, last_results, last_output_dir
            # scrape
            def cb1(info):
                if info.get("type")=="source_result":
                    root.after(0, lambda: var_scrape_prog.set(f"{info['current']}/{info['total']} {info['label']}"))
                    root.after(0, lambda: prog_scrape.config(value= int(info['current']/info['total']*100) ))
                    append_log("scrape", f"{info['label']}: +{info['new']} total {info['total_found']}")
                elif info.get("type")=="source_error":
                    append_log("error", f"{info['label']}: {info['error'][:80]}")
                elif info.get("type")=="note":
                    append_log("info", info["message"])
            proxies, meta = scrape_proxies(selected, protos, limit=limit, progress_callback=cb1, stop_event=stop_event, max_workers=12)
            current_proxies = proxies
            root.after(0, lambda: txt_input.delete("1.0","end"))
            root.after(0, lambda: txt_input.insert("1.0", "\n".join(proxies[:300])))
            root.after(0, lambda: lbl_count.config(text=f"{len(proxies)} scraped"))
            root.after(0, update_stats_top)
            append_log("auto", f"Scrape done: {len(proxies)} proxies, now validating...")
            root.after(0, lambda: var_validate_prog.set(f"Validating {len(proxies)}..."))
            if not proxies:
                append_log("error", "No proxies scraped — aborting auto")
                root.after(0, lambda: auto_btn.config(state="normal", text="⚡  START AUTO (Generate → Check → Save)", bg=ACCENT2))
                set_scrape_state(False); set_validate_state(False)
                return
            # validate
            def cb2(info):
                if info.get("type")=="result":
                    r = info["result"]
                    counts = info["counts"]
                    root.after(0, lambda: var_validate_prog.set(f"{info['current']}/{info['total']} valid:{counts['valid']}"))
                    root.after(0, lambda: prog_validate.config(value= int(info['current']/info['total']*100) ))
                    # log valid only to avoid spam
                    if r.get("status")=="valid":
                        append_log("valid", f"{r['proxy']} {r.get('latency')}ms")
                    elif info["current"] % 40==0:
                        append_log(r.get("status","info"), f"{r['proxy']} → {r.get('status')}")
            results, counts = validate_proxies(proxies, timeout=timeout, test_url=test_url, progress_callback=cb2, stop_event=stop_event, max_workers=int(var_threads.get() or "80"))
            last_results = results
            append_log("done", f"Validate done: {counts['valid']} valid/{len(proxies)}")
            root.after(0, update_stats_top)
            # save
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                out_dir = output / timestamp if output.exists() and output.is_dir() else Path.cwd() / "results" / timestamp
                # if output is file-like or custom, handle
                if not output.exists():
                    output.mkdir(parents=True, exist_ok=True)
                    out_dir = output / timestamp
                out = save_results(proxies, results, output_dir=out_dir, base_dir=output if output.is_dir() else Path.cwd())
                last_output_dir = out
                append_log("done", f"Saved to {out}")
                append_log("info", f"valid.txt: {counts['valid']} | all.txt: {len(proxies)} | stats.json")
                root.after(0, lambda: messagebox.showinfo("Auto Done", f"Saved {counts['valid']} valid proxies to:\n{out.resolve()}\n\nvalid.txt, valid.json, valid.csv, stats.json\n+ latest/ copy"))
                # open folder?
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(str(out))  # type: ignore
                except:
                    pass
            except Exception as e:
                append_log("error", f"Save failed: {e}")
                root.after(0, lambda: messagebox.showerror("Save failed", str(e)))
            root.after(0, lambda: auto_btn.config(state="normal", text="⚡  START AUTO (Generate → Check → Save)", bg=ACCENT2))
            set_scrape_state(False); set_validate_state(False)
            root.after(0, lambda: var_scrape_prog.set("Auto done"))
            root.after(0, lambda: var_validate_prog.set("Auto done"))
        threading.Thread(target=worker, daemon=True).start()
    auto_btn.config(command=do_auto)

    # Footer tip
    tip = tk.Label(right, text="Tip: Results auto-saved to results/YYYY-MM-DD_HH-MM-SS/  —  double-click exe to launch GUI, or run with --auto for headless.", bg=BG, fg=DIM, font=("Segoe UI", 7), wraplength=500, justify="left")
    tip.pack(fill="x", padx=2, pady=4)

    # Handle close
    def on_close():
        stop_event.set()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Ultimate Proxy Scrapper — Desktop & CLI")
    parser.add_argument("--auto", action="store_true", help="Run in auto CLI mode (scrape -> validate -> save and exit)")
    parser.add_argument("--limit", type=int, default=500, help="Max proxies to scrape (0=no limit)")
    parser.add_argument("--timeout", type=int, default=8, help="Validation timeout seconds")
    parser.add_argument("--test-url", default="http://httpbin.org/ip", help="Test URL for validation")
    parser.add_argument("--output", type=str, default="results", help="Output folder (default ./results)")
    parser.add_argument("--threads", type=int, default=80, help="Validate threads")
    parser.add_argument("--sources", type=str, default="", help="Comma-separated source ids (default all)")
    parser.add_argument("--protocols", type=str, default="http,https,socks4,socks5", help="Comma protocols")
    parser.add_argument("--gui", action="store_true", help="Force GUI")
    parser.add_argument("--web", action="store_true", help="Launch web dashboard (Flask) instead of desktop GUI")
    parser.add_argument("--port", type=int, default=5000, help="Web port")
    args = parser.parse_args()

    if args.web:
        # Launch Flask web dashboard
        print(f"Launching web dashboard on http://0.0.0.0:{args.port}")
        try:
            from app import app
            app.run(host="0.0.0.0", port=args.port, threaded=True)
        except Exception as e:
            print(f"Web launch failed: {e}")
            sys.exit(1)
        return

    if args.auto and not args.gui:
        # CLI auto
        protocols = {p.strip().lower() for p in args.protocols.split(",") if p.strip()}
        source_ids = [s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else list(SOURCES.keys())
        # filter valid
        source_ids = [s for s in source_ids if s in SOURCES] or list(SOURCES.keys())
        output = Path(args.output).resolve() if args.output else None
        run_auto(
            limit=args.limit,
            timeout=args.timeout,
            test_url=args.test_url,
            protocols=protocols,
            source_ids=source_ids,
            output=output,
            threads_validate=args.threads,
        )
        return

    # Default: GUI
    # If running as frozen exe with --auto flag, handled above. Otherwise launch GUI.
    # Detect if no display (headless linux): fallback to CLI auto
    if not args.gui:
        # If DISPLAY not available on Linux, use CLI
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            print("No display detected — running auto CLI mode. Use --gui to force GUI.")
            run_auto(limit=args.limit, timeout=args.timeout, test_url=args.test_url)
            return
    try:
        launch_gui()
    except Exception as e:
        log.exception("GUI failed, falling back to CLI")
        print(f"GUI failed ({e}), running auto CLI...")
        run_auto()

if __name__ == "__main__":
    main()
