#!/usr/bin/env python3
# =============================================================================
# proxy.py — Ultimate Free Proxy Scrapper & Validator
# © 2026 harshi79 / YorichiiPrime — Watermark: HARSHI79-ULTIMATE-PROXY-2026
# Repository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator
#
# ONE FILE. NO SETUP. NO EXE.
#
#   python proxy.py
#
# does everything: scrape 18 public sources -> dedupe -> validate in parallel
# -> save to results/YYYY-MM-DD_HH-MM-SS/ (plus results/latest/).
#
# `requests` is used when installed (adds SOCKS support); otherwise it falls
# back to the Python standard library, so the default run needs no pip install.
# For SOCKS proxies without requests, a tiny built-in SOCKS4/SOCKS5 client is
# used, so socks lists are validated too.
#
# Optional flags (everything has a sane default):
#   --limit N        max proxies to check        (default 2000, 0 = no limit)
#   --timeout S      seconds per proxy           (default 8)
#   --threads N      parallel checks             (default 80)
#   --output DIR     where results/ is created   (default current folder)
#   --test-url URL   endpoint used to check IPs  (auto-detected by default)
#   --protocols P    http,https,socks4,socks5    (default all)
#   --file FILE      validate your own list instead of scraping
#   --quiet          only print the summary
# =============================================================================

from __future__ import annotations

import argparse
import csv
import http.client
import json
import os
import random
import re
import shutil
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# Identity / watermark — keep it, the LICENSE requires attribution
# ---------------------------------------------------------------------------
WATERMARK = "HARSHI79-ULTIMATE-PROXY-2026"
AUTHOR = "harshi79"
AUTHOR_FULL = "harshi79 / YorichiiPrime — https://github.com/harshi79"
VERSION = "2.2.0"
APP_TITLE = f"Ultimate Proxy Scrapper v{VERSION}"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_LIMIT = 2000
DEFAULT_TIMEOUT = 8
DEFAULT_THREADS = 80
DEFAULT_OUTPUT = "results"
SCRAPE_WORKERS = 12
SCRAPE_TIMEOUT = 12
FAST_MS = 800
MEDIUM_MS = 2000

# First reachable endpoint wins — checked directly (no proxy) before validating.
TEST_URL_CANDIDATES = [
    "http://httpbin.org/ip",
    "http://api.ipify.org?format=json",
    "http://icanhazip.com",
    "http://ifconfig.me/ip",
]

IP_PORT_RE = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})")
IP_RE = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
UA = {"User-Agent": "Mozilla/5.0 (ProxyScrapper/2.2)", "Accept": "*/*"}

# `requests` is optional — used when importable (nicer SOCKS support via pysocks)
try:  # pragma: no cover - environment dependent
    import requests  # type: ignore

    try:
        import urllib3

        urllib3.disable_warnings()
    except Exception:
        pass
    HAS_REQUESTS = True
except ImportError:  # pragma: no cover - environment dependent
    requests = None  # type: ignore
    HAS_REQUESTS = False

# requests only speaks SOCKS when PySocks is installed. If it isn't, we use our
# own SOCKS4/SOCKS5 client rather than silently failing every socks proxy.
try:  # pragma: no cover - environment dependent
    import socks as _pysocks  # noqa: F401

    HAS_SOCKS_LIB = True
except ImportError:  # pragma: no cover - environment dependent
    HAS_SOCKS_LIB = False

_print_lock = threading.Lock()

# ---------------------------------------------------------------------------
# 18 public sources
# ---------------------------------------------------------------------------
SOURCES: Dict[str, Dict[str, str]] = {
    "proxyscrape_http": {"label": "ProxyScrape HTTP", "proto": "http", "kind": "txt",
                         "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"},
    "proxyscrape_socks4": {"label": "ProxyScrape SOCKS4", "proto": "socks4", "kind": "txt",
                           "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all"},
    "proxyscrape_socks5": {"label": "ProxyScrape SOCKS5", "proto": "socks5", "kind": "txt",
                           "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all"},
    "proxy_list_http": {"label": "Proxy-List.download HTTP", "proto": "http", "kind": "txt",
                        "url": "https://www.proxy-list.download/api/v1/get?type=http"},
    "proxy_list_https": {"label": "Proxy-List.download HTTPS", "proto": "https", "kind": "txt",
                         "url": "https://www.proxy-list.download/api/v1/get?type=https"},
    "proxy_list_socks4": {"label": "Proxy-List.download SOCKS4", "proto": "socks4", "kind": "txt",
                          "url": "https://www.proxy-list.download/api/v1/get?type=socks4"},
    "thespeedx_http": {"label": "TheSpeedX HTTP", "proto": "http", "kind": "txt",
                       "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"},
    "thespeedx_socks4": {"label": "TheSpeedX SOCKS4", "proto": "socks4", "kind": "txt",
                         "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt"},
    "thespeedx_socks5": {"label": "TheSpeedX SOCKS5", "proto": "socks5", "kind": "txt",
                         "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"},
    "monosans_http": {"label": "Monosans HTTP", "proto": "http", "kind": "txt",
                      "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"},
    "monosans_socks4": {"label": "Monosans SOCKS4", "proto": "socks4", "kind": "txt",
                        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt"},
    "monosans_socks5": {"label": "Monosans SOCKS5", "proto": "socks5", "kind": "txt",
                        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt"},
    "roosterkid_https": {"label": "RoosterKid HTTPS", "proto": "https", "kind": "txt",
                         "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt"},
    "roosterkid_socks4": {"label": "RoosterKid SOCKS4", "proto": "socks4", "kind": "txt",
                          "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt"},
    "roosterkid_socks5": {"label": "RoosterKid SOCKS5", "proto": "socks5", "kind": "txt",
                          "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt"},
    "geonode": {"label": "Geonode API", "proto": "http", "kind": "geonode",
                "url": "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc"},
    "jetkai_http": {"label": "JetKai HTTP", "proto": "http", "kind": "txt",
                    "url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt"},
    "clarketm": {"label": "ClarkTM Raw", "proto": "http", "kind": "txt",
                 "url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"},
}

ALL_PROTOCOLS = ("http", "https", "socks4", "socks5")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def say(msg: str = "", quiet: bool = False) -> None:
    if not quiet:
        with _print_lock:
            print(msg, flush=True)


def parse_proxy_list(text: str) -> List[str]:
    """Extract valid host:port entries from a blob of text."""
    found: List[str] = []
    seen: Set[str] = set()
    for raw in IP_PORT_RE.findall(text or ""):
        host, _, port = raw.partition(":")
        try:
            if not (1 <= int(port) <= 65535):
                continue
        except ValueError:
            continue
        if raw not in seen:
            seen.add(raw)
            found.append(raw)
    return found


def dedupe(items: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Step 1 — scrape
# ---------------------------------------------------------------------------
def fetch_text(url: str, timeout: int = SCRAPE_TIMEOUT) -> str:
    if HAS_REQUESTS:
        resp = requests.get(url, timeout=timeout, headers=UA)
        resp.raise_for_status()
        return resp.text or ""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_source(sid: str) -> Tuple[str, List[str], Optional[str]]:
    """Return (source_id, proxies, error)."""
    cfg = SOURCES[sid]
    try:
        text = fetch_text(cfg["url"])
        if cfg["kind"] == "geonode":
            try:
                data = json.loads(text)
                found = [
                    f"{item['ip']}:{item['port']}"
                    for item in data.get("data", [])
                    if item.get("ip") and item.get("port")
                ]
            except Exception:
                found = parse_proxy_list(text)
        else:
            found = parse_proxy_list(text)
        return sid, found, None
    except Exception as exc:
        return sid, [], f"{type(exc).__name__}: {str(exc)[:120]}"


def scrape(source_ids: Sequence[str], limit: int = DEFAULT_LIMIT,
           quiet: bool = False) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    """Hit every source in parallel.

    Returns ({proxy: protocol_hint}, [(source_label, error), ...]).
    """
    found_map: Dict[str, str] = {}
    failures: List[Tuple[str, str]] = []
    done = 0
    total = len(source_ids)
    lock = threading.Lock()

    def on_done(sid: str, found: List[str], err: Optional[str]) -> None:
        nonlocal done
        with lock:
            done += 1
            if err:
                failures.append((SOURCES[sid]["label"], err))
            else:
                for p in found:
                    found_map.setdefault(p, SOURCES[sid]["proto"])
            label = SOURCES[sid]["label"]
            say(f"  [{'x' if err else '+'}] {label:<28} {len(found):>6}   "
                f"({done}/{total})", quiet)

    with ThreadPoolExecutor(max_workers=min(SCRAPE_WORKERS, max(total, 1))) as pool:
        futures = {pool.submit(fetch_source, sid): sid for sid in source_ids}
        for fut in as_completed(futures):
            on_done(*fut.result())

    items = list(found_map.items())
    random.shuffle(items)
    if limit and len(items) > limit:
        items = items[:limit]
    return dict(items), failures


# ---------------------------------------------------------------------------
# Step 2 — validate
# ---------------------------------------------------------------------------
def pick_test_url(timeout: int = 6) -> Optional[str]:
    """Pick the first IP-echo endpoint reachable from this machine."""
    for url in TEST_URL_CANDIDATES:
        try:
            fetch_text(url, timeout=timeout)
            return url
        except Exception:
            continue
    return None


def _origin_from(body: str) -> str:
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return str(data.get("origin") or data.get("ip") or "")
    except Exception:
        pass
    match = IP_RE.search(body or "")
    return match.group(0) if match else ""


def _check_with_requests(proxy: str, test_url: str, timeout: int, hint: str) -> Dict[str, object]:
    scheme = hint if hint in ("socks4", "socks5") else "http"
    proxy_url = proxy if "://" in proxy else f"{scheme}://{proxy}"
    start = time.monotonic()
    resp = requests.get(test_url, proxies={"http": proxy_url, "https": proxy_url},
                        timeout=timeout, headers=UA, verify=False)
    latency = int((time.monotonic() - start) * 1000)
    body = resp.text or ""
    return {"status": "valid" if resp.status_code == 200 else "dead",
            "latency": latency, "code": resp.status_code, "body": body}


# --- standard-library fallback -------------------------------------------
def _socks5_connect(sock: socket.socket, host: str, port: int, timeout: int) -> None:
    sock.sendall(b"\x05\x01\x00")
    greeting = sock.recv(2)
    if len(greeting) < 2 or greeting[0] != 0x05 or greeting[1] == 0xFF:
        raise ConnectionError("socks5: no acceptable auth method")
    host_b = host.encode("idna")
    sock.sendall(b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b + struct.pack(">H", port))
    reply = sock.recv(4)
    if len(reply) < 2 or reply[1] != 0x00:
        raise ConnectionError(f"socks5: request rejected (code {reply[1] if len(reply) > 1 else '?'})")
    atyp = reply[3] if len(reply) > 3 else 1
    if atyp == 1:
        sock.recv(6)
    elif atyp == 3:
        length = sock.recv(1)[0]
        sock.recv(length + 2)
    elif atyp == 4:
        sock.recv(18)


def _socks4_connect(sock: socket.socket, host: str, port: int, timeout: int) -> None:
    try:
        ip_bytes = socket.inet_aton(socket.gethostbyname(host))
        request = b"\x04\x01" + struct.pack(">H", port) + ip_bytes + b"\x00"
    except socket.gaierror:
        request = (b"\x04\x01" + struct.pack(">H", port) + b"\x00\x00\x00\x01"
                   + b"\x00" + host.encode("idna") + b"\x00")
    sock.sendall(request)
    reply = sock.recv(8)
    if len(reply) < 2 or reply[1] != 0x5A:
        raise ConnectionError("socks4: request rejected")


def _check_with_stdlib(proxy: str, test_url: str, timeout: int, hint: str) -> Dict[str, object]:
    """HTTP(S) GET through a proxy using only the standard library."""
    target = urlsplit(test_url)
    t_host = target.hostname or ""
    t_port = target.port or (443 if target.scheme == "https" else 80)
    path = target.path or "/"
    if target.query:
        path += "?" + target.query

    p_host, _, p_port_s = proxy.rpartition(":")
    p_port = int(p_port_s)
    scheme = hint if hint in ("socks4", "socks5") else "http"

    start = time.monotonic()
    sock = socket.create_connection((p_host, p_port), timeout)
    absolute_form = False
    try:
        if scheme == "socks5":
            _socks5_connect(sock, t_host, t_port, timeout)
        elif scheme == "socks4":
            _socks4_connect(sock, t_host, t_port, timeout)
        elif target.scheme == "https":
            sock.sendall(f"CONNECT {t_host}:{t_port} HTTP/1.1\r\nHost: {t_host}:{t_port}\r\n\r\n".encode())
            buf = b""
            while b"\r\n\r\n" not in buf and len(buf) < 8192:
                chunk = sock.recv(512)
                if not chunk:
                    break
                buf += chunk
            if b" 200 " not in buf.split(b"\r\n", 1)[0]:
                raise ConnectionError("proxy refused CONNECT")
        else:
            absolute_form = True  # plain HTTP proxy: use absolute request URI

        if target.scheme == "https":
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=t_host)

        conn = http.client.HTTPConnection(t_host, t_port, timeout=timeout)
        conn.sock = sock
        try:
            conn.request("GET", f"http://{t_host}{path}" if absolute_form else path,
                         headers={"User-Agent": UA["User-Agent"], "Host": t_host,
                                  "Connection": "close"})
            resp = conn.getresponse()
            body = resp.read(4096).decode("utf-8", "replace")
            code = resp.status
        finally:
            conn.close()
        latency = int((time.monotonic() - start) * 1000)
        return {"status": "valid" if code == 200 else "dead",
                "latency": latency, "code": code, "body": body}
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _use_requests_for(hint: str) -> bool:
    """requests is preferred, except for SOCKS when PySocks is missing."""
    if not HAS_REQUESTS:
        return False
    return hint not in ("socks4", "socks5") or HAS_SOCKS_LIB


def check_one(proxy: str, test_url: str, timeout: int, hint: str = "http") -> Dict[str, object]:
    """Check a single proxy -> {proxy, protocol, status, latency, origin, error}."""
    result: Dict[str, object] = {"proxy": proxy, "protocol": hint, "status": "dead",
                                 "latency": None, "origin": "", "error": ""}
    try:
        info = (_check_with_requests(proxy, test_url, timeout, hint)
                if _use_requests_for(hint)
                else _check_with_stdlib(proxy, test_url, timeout, hint))
        result.update(info)
        if info.get("status") == "valid":
            body = str(info.get("body") or "")
            result["origin"] = _origin_from(body)
        else:
            result["error"] = f"HTTP {info.get('code')}"
    except socket.timeout:
        result["status"] = "timeout"
        result["error"] = f"no answer in {timeout}s"
    except (ConnectionRefusedError, ConnectionResetError, socket.gaierror) as exc:
        result["status"] = "dead"
        result["error"] = type(exc).__name__
    except Exception as exc:
        message = str(exc).lower()
        if "timed out" in message or "timeout" in message:
            result["status"] = "timeout"
            result["error"] = f"no answer in {timeout}s"
        else:
            result["status"] = "dead"
            result["error"] = f"{type(exc).__name__}: {str(exc)[:90]}"
    result.pop("code", None)
    result.pop("body", None)
    return result


def validate(proxies: Sequence[Tuple[str, str]], test_url: str, timeout: int = DEFAULT_TIMEOUT,
             threads: int = DEFAULT_THREADS, quiet: bool = False) -> List[Dict[str, object]]:
    """Check every (proxy, protocol_hint) pair in parallel, printing a live counter."""
    results: List[Dict[str, object]] = []
    counts = {"valid": 0, "dead": 0, "timeout": 0}
    total = len(proxies)
    threads = max(1, min(threads, total, 200))
    done = 0
    lock = threading.Lock()
    started = time.monotonic()

    # protocol hint per proxy: remembered from the source it came from
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = {pool.submit(check_one, p, test_url, timeout, hint): p
                   for p, hint in proxies}  # type: ignore[misc]
        for fut in as_completed(futures):
            res = fut.result()
            with lock:
                results.append(res)
                done += 1
                status = str(res["status"])
                counts[status] = counts.get(status, 0) + 1
                if not quiet:
                    elapsed = time.monotonic() - started
                    rate = done / elapsed if elapsed else 0
                    eta = (total - done) / rate if rate else 0
                    print(f"\r  {done}/{total} checked · valid {counts['valid']} · "
                          f"dead {counts['dead']} · timeout {counts['timeout']} · "
                          f"{rate:.0f}/s · ~{eta:.0f}s left   ", end="", flush=True)
    if not quiet:
        print("", flush=True)
    return results


# ---------------------------------------------------------------------------
# Step 3 — save
# ---------------------------------------------------------------------------
def save(proxies: Sequence[str], results: Sequence[Dict[str, object]],
         base_dir: Path) -> Path:
    """Write results/<timestamp>/ and refresh results/latest/."""
    base_dir.mkdir(parents=True, exist_ok=True)
    out_dir = base_dir / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    valid = sorted([r for r in results if r["status"] == "valid"],
                   key=lambda r: r["latency"] if r["latency"] is not None else 99999)
    for r in valid:
        r["speed"] = ("fast" if (r["latency"] or 9999) < FAST_MS
                      else "medium" if (r["latency"] or 9999) < MEDIUM_MS else "slow")

    def write(name: str, text: str) -> None:
        (out_dir / name).write_text(text, encoding="utf-8")

    write("valid.txt", "\n".join(str(r["proxy"]) for r in valid))
    write("all.txt", "\n".join(str(r["proxy"]) for r in results))
    write("raw_scraped.txt", "\n".join(proxies))
    write("valid.json", json.dumps(valid, indent=2))
    write("all.json", json.dumps(list(results), indent=2))

    fields = ["proxy", "protocol", "status", "latency", "speed", "origin", "error"]
    with open(out_dir / "valid.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in valid:
            writer.writerow({k: r.get(k, "") for k in fields})
    with open(out_dir / "all.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})

    by_proto: Dict[str, List[str]] = {}
    for r in valid:
        by_proto.setdefault(str(r["protocol"]), []).append(str(r["proxy"]))
    for proto, items in by_proto.items():
        write(f"{proto}.txt", "\n".join(items))

    latencies = [int(r["latency"]) for r in valid if r["latency"] is not None]
    stats = {
        "app": APP_TITLE,
        "version": VERSION,
        "timestamp": datetime.now().isoformat(),
        "scraped": len(proxies),
        "checked": len(results),
        "valid": len(valid),
        "counts": {k: sum(1 for r in results if r["status"] == k)
                   for k in ("valid", "dead", "timeout")},
        "hit_rate_pct": round(len(valid) / len(results) * 100, 2) if results else 0,
        "avg_latency_ms": sum(latencies) // len(latencies) if latencies else None,
        "fastest_ms": min(latencies) if latencies else None,
        "author": AUTHOR,
        "author_full": AUTHOR_FULL,
        "watermark": WATERMARK,
        "repository": "https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator",
    }
    write("stats.json", json.dumps(stats, indent=2))
    write("_AUTHOR.txt",
          f"Generated by {APP_TITLE}\nAuthor: {AUTHOR_FULL}\nWatermark: {WATERMARK}\n"
          f"Timestamp: {stats['timestamp']}\n"
          f"Repository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator\n"
          f"Protected — do not remove. This file proves authenticity.\n")

    latest = base_dir / "latest"
    try:
        if latest.is_symlink():
            latest.unlink()
        elif latest.is_dir():
            shutil.rmtree(latest)
        shutil.copytree(out_dir, latest)
    except Exception:
        pass
    return out_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proxy.py",
        description=f"{APP_TITLE} — scrape, validate and export free proxies. "
                    f"Running it with no arguments does everything.",
        epilog="example:  python proxy.py --limit 500 --timeout 6")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"max proxies to check, 0 = no limit (default {DEFAULT_LIMIT})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"seconds to wait per proxy (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS,
                        help=f"parallel checks (default {DEFAULT_THREADS})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help=f"folder for results/ (default ./{DEFAULT_OUTPUT})")
    parser.add_argument("--test-url", default="",
                        help="IP-echo endpoint used for checking (auto-detected)")
    parser.add_argument("--protocols", default=",".join(ALL_PROTOCOLS),
                        help="comma list: http,https,socks4,socks5 (default all)")
    parser.add_argument("--sources", default="",
                        help="comma list of source ids (default all 18)")
    parser.add_argument("--file", default="",
                        help="validate proxies from this file instead of scraping")
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    quiet = args.quiet
    started = time.monotonic()

    say(f"\n{APP_TITLE} — © {AUTHOR_FULL}", quiet)
    engine = "requests" if HAS_REQUESTS else "stdlib"
    say(f"Watermark {WATERMARK} · engine: {engine}"
        + ("" if HAS_SOCKS_LIB else " (built-in socks client)"), quiet)

    # ---- step 1: gather proxies -----------------------------------------
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
        found = dedupe(parse_proxy_list(text) or
                       [ln.strip() for ln in text.splitlines() if ":" in ln])
        hint_map: Dict[str, str] = {p: "http" for p in found}
        say(f"\n[1/3] Loaded {len(found)} proxies from {args.file}", quiet)
        if not found:
            print("  nothing usable in that file — it needs one ip:port per line")
            return 1
    else:
        wanted = {p.strip().lower() for p in args.protocols.split(",") if p.strip()}
        source_ids = [s.strip() for s in args.sources.split(",") if s.strip()] or list(SOURCES)
        source_ids = [s for s in source_ids if s in SOURCES and
                      (not wanted or SOURCES[s]["proto"] in wanted)]
        if not source_ids:
            source_ids = list(SOURCES)
        say(f"\n[1/3] Scraping {len(source_ids)} sources "
            f"({', '.join(sorted(wanted)) or 'all'})...", quiet)
        hint_map, failures = scrape(source_ids, args.limit, quiet)
        say(f"  -> {len(hint_map)} unique proxies"
            + (f"  ({len(failures)} sources unreachable)" if failures else ""), quiet)
        if not hint_map:
            # fatal: always shown, even with --quiet
            print("\n  No proxies found — every source was unreachable. Check your "
                  "internet /\n  firewall and try again, or validate your own list with:\n"
                  "    python proxy.py --file mylist.txt")
            for label, err in failures[:3]:
                print(f"    {label}: {err}")
            return 1

    proxies = list(hint_map.keys())
    if args.limit and len(proxies) > args.limit:
        proxies = proxies[:args.limit]
    hint_list = [(p, hint_map[p]) for p in proxies]

    # ---- validate --------------------------------------------------------
    detected = pick_test_url()
    test_url = args.test_url or detected or TEST_URL_CANDIDATES[0]
    say(f"\n[2/3] Validating {len(proxies)} proxies · {args.threads} threads · "
        f"{args.timeout}s timeout · via {test_url}", quiet)
    if not args.test_url and not detected:
        say("  ! no IP-echo endpoint answered directly — every proxy will look "
            "dead.\n    Check the connection, or pass --test-url manually.", quiet)
    try:
        results = validate(hint_list, test_url, args.timeout, args.threads, quiet)
    except KeyboardInterrupt:
        say("\n  stopped by user — nothing saved", quiet)
        return 130

    # A proxy written as ip:port may be socks even when the list said http.
    # Give those failures one cheap SOCKS5 retry (capped, so it stays quick).
    retry = [str(r["proxy"]) for r in results
             if r["status"] in ("dead", "timeout") and r["protocol"] == "http"][:300]
    if retry:
        say(f"  retrying {len(retry)} as SOCKS5...", quiet)
        sock_results = validate([(p, "socks5") for p in retry], test_url,
                                min(args.timeout, 6), args.threads, quiet)
        better = {str(r["proxy"]): r for r in sock_results if r["status"] == "valid"}
        for r in results:
            replacement = better.get(str(r["proxy"]))
            if replacement:
                r.update(replacement)

    valid = [r for r in results if r["status"] == "valid"]
    dead = [r for r in results if r["status"] == "dead"]
    timed_out = [r for r in results if r["status"] == "timeout"]

    # ---- save ------------------------------------------------------------
    say("\n[3/3] Saving results...", quiet)
    out_dir = save(proxies, results, Path(args.output))
    elapsed = time.monotonic() - started

    say(f"\n{'=' * 66}\n  DONE in {elapsed:.1f}s — {len(valid)} working "
        f"{'proxy' if len(valid) == 1 else 'proxies'} out of {len(results)} checked", quiet)
    say(f"  dead {len(dead)} · timeout {len(timed_out)}", quiet)
    if valid:
        fastest = sorted(valid, key=lambda r: r["latency"] if r["latency"] is not None else 99999)[:10]
        say("\n  fastest:", quiet)
        for r in fastest:
            say(f"    {r['proxy']:<24} {r['latency']} ms", quiet)
    say(f"\n  folder : {out_dir.resolve()}", quiet)
    say( "  files  : valid.txt · all.txt · valid.json · valid.csv · stats.json", quiet)
    say( "  always : results/latest/valid.txt", quiet)
    say(f"{'=' * 66}\n", quiet)

    if sys.platform.startswith("win") and not quiet:  # open the folder on Windows
        try:
            os.startfile(str(out_dir))  # type: ignore[attr-defined]
        except Exception:
            pass
    return 0 if valid else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nbye")
        sys.exit(130)
