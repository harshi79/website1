# =============================================================================
# Ultimate Proxy Scrapper — © 2026 harshi79 / YorichiiPrime
# All rights reserved. Watermark: HARSHI79-ULTIMATE-PROXY-2026
# Repository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator
# Version: 2.1.0 — shared core (protected)
# =============================================================================
"""
proxy_engine — shared core for web + desktop + CLI
Provides:
- SOURCES dict (18 free proxy sources)
- fetch_source / scrape_proxies
- validate_one / validate_proxies
- save_results (auto folder structure)
Used by app.py (Flask) and main.py (desktop exe)
"""

from __future__ import annotations

import csv
import json
import logging
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

log = logging.getLogger("proxy_engine")

IP_PORT_RE = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})")

DEFAULT_TIMEOUT = int(os.environ.get("VALIDATE_TIMEOUT", "8"))
SCRAPE_TIMEOUT = int(os.environ.get("SCRAPE_TIMEOUT", "12"))
MAX_WORKERS_SCRAPE = int(os.environ.get("MAX_WORKERS_SCRAPE", "12"))
MAX_WORKERS_VALIDATE = int(os.environ.get("MAX_WORKERS_VALIDATE", "80"))

SOURCES: Dict[str, Dict[str, Any]] = {
    "proxyscrape_http": {
        "label": "ProxyScrape HTTP",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "type": "txt",
        "protocol": "http",
    },
    "proxyscrape_socks4": {
        "label": "ProxyScrape SOCKS4",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
        "type": "txt",
        "protocol": "socks4",
    },
    "proxyscrape_socks5": {
        "label": "ProxyScrape SOCKS5",
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
        "type": "txt",
        "protocol": "socks5",
    },
    "proxy_list_download_http": {
        "label": "Proxy-List.download HTTP",
        "url": "https://www.proxy-list.download/api/v1/get?type=http",
        "type": "txt",
        "protocol": "http",
    },
    "proxy_list_download_https": {
        "label": "Proxy-List.download HTTPS",
        "url": "https://www.proxy-list.download/api/v1/get?type=https",
        "type": "txt",
        "protocol": "https",
    },
    "proxy_list_download_socks4": {
        "label": "Proxy-List.download SOCKS4",
        "url": "https://www.proxy-list.download/api/v1/get?type=socks4",
        "type": "txt",
        "protocol": "socks4",
    },
    "thespeedx_http": {
        "label": "TheSpeedX HTTP",
        "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "type": "txt",
        "protocol": "http",
    },
    "thespeedx_socks4": {
        "label": "TheSpeedX SOCKS4",
        "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "type": "txt",
        "protocol": "socks4",
    },
    "thespeedx_socks5": {
        "label": "TheSpeedX SOCKS5",
        "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "type": "txt",
        "protocol": "socks5",
    },
    "monosans_http": {
        "label": "Monosans HTTP",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "type": "txt",
        "protocol": "http",
    },
    "monosans_socks4": {
        "label": "Monosans SOCKS4",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "type": "txt",
        "protocol": "socks4",
    },
    "monosans_socks5": {
        "label": "Monosans SOCKS5",
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "type": "txt",
        "protocol": "socks5",
    },
    "roosterkid_https": {
        "label": "RoosterKid HTTPS",
        "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "type": "txt",
        "protocol": "https",
    },
    "roosterkid_socks4": {
        "label": "RoosterKid SOCKS4",
        "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "type": "txt",
        "protocol": "socks4",
    },
    "roosterkid_socks5": {
        "label": "RoosterKid SOCKS5",
        "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "type": "txt",
        "protocol": "socks5",
    },
    "geonode": {
        "label": "Geonode API",
        "url": "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "type": "geonode",
        "protocol": "http",
    },
    "jetkai_http": {
        "label": "JetKai HTTP",
        "url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "type": "txt",
        "protocol": "http",
    },
    "clarketm": {
        "label": "ClarkTM Raw",
        "url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "type": "clarketm",
        "protocol": "http",
    },
}

# curated sample for offline/restricted demo
SAMPLE_PROXIES = [
    "8.210.83.33:80", "47.74.152.29:8888", "103.149.162.194:80",
    "8.219.97.248:80", "47.88.3.19:8080", "104.19.191.28:80",
    "172.104.9.115:3128", "20.210.113.32:80", "47.251.43.115:33333",
    "152.32.128.67:80", "172.67.178.64:80", "45.77.56.114:3128",
    "167.71.5.83:8080", "45.136.198.154:3128", "194.102.116.189:80",
    "51.158.123.35:8811", "103.214.109.68:80", "8.213.128.122:80",
    "159.69.57.20:8880", "114.129.2.38:8080", "8.213.23.57:80",
    "20.24.43.214:80", "104.21.45.27:80", "47.90.205.231:33333",
    "8.220.204.11:80", "34.102.48.16:80", "8.212.165.66:80",
    "51.75.147.41:8080", "47.122.13.217:80", "213.199.38.250:8080",
    "5.161.103.242:80", "8.222.180.77:80", "47.243.43.115:80",
    "103.155.217.122:83", "8.210.21.171:80", "104.21.198.165:80",
    # extra
    "18.143.48.227:80", "20.78.13.122:80", "47.252.29.28:11222",
    "47.89.184.18:80", "3.10.140.43:80", "51.81.82.175:1711",
]


def fetch_source(source_id: str, cfg: Dict[str, Any], timeout: int = SCRAPE_TIMEOUT) -> Tuple[str, List[str], Optional[str]]:
    url = cfg["url"]
    stype = cfg["type"]
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (ProxyScrapper/1.0)",
            "Accept": "*/*",
        })
        resp.raise_for_status()
        text = resp.text or ""
        proxies: List[str] = []
        if stype == "txt":
            proxies = IP_PORT_RE.findall(text)
        elif stype == "geonode":
            try:
                data = resp.json()
                for item in data.get("data", []):
                    ip = item.get("ip")
                    port = item.get("port")
                    if ip and port:
                        proxies.append(f"{ip}:{port}")
            except Exception:
                proxies = IP_PORT_RE.findall(text)
        elif stype == "clarketm":
            for line in text.splitlines():
                m = IP_PORT_RE.search(line)
                if m:
                    proxies.append(m.group(1))
        else:
            proxies = IP_PORT_RE.findall(text)

        seen: Set[str] = set()
        uniq: List[str] = []
        for p in proxies:
            if p not in seen:
                seen.add(p)
                ip, _, port = p.partition(":")
                try:
                    pn = int(port)
                    if 1 <= pn <= 65535:
                        uniq.append(p)
                except:
                    continue
        return source_id, uniq, None
    except Exception as exc:
        log.warning("Source %s failed: %s", source_id, exc)
        return source_id, [], str(exc)[:220]


def scrape_proxies(
    source_ids: List[str],
    protocols: Set[str],
    limit: int = 0,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    stop_event: Optional[threading.Event] = None,
    timeout: int = SCRAPE_TIMEOUT,
    max_workers: int = MAX_WORKERS_SCRAPE,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Scrape proxies. Returns (all_proxies, meta).
    progress_callback receives dicts like {"type": "source_result", "label":..., "count":...}
    """
    # filter by protocol
    filtered: List[str] = []
    for sid in source_ids:
        cfg = SOURCES.get(sid)
        if not cfg:
            continue
        if protocols and cfg["protocol"] not in protocols:
            if not (protocols == {"http", "https"} and cfg["protocol"] in {"http", "https"}):
                if cfg["protocol"] in {"socks4", "socks5"} and cfg["protocol"] not in protocols:
                    continue
                if cfg["protocol"] in {"http", "https"} and not protocols.intersection({"http", "https"}):
                    continue
        filtered.append(sid)
    if not filtered:
        filtered = [s for s in source_ids if s in SOURCES]

    all_proxies: List[str] = []
    seen_global: Set[str] = set()
    completed = 0
    total = len(filtered)
    source_results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    if total == 0:
        return [], {"total": 0, "filtered": filtered, "errors": errors}

    with ThreadPoolExecutor(max_workers=min(max_workers, total or 1)) as pool:
        future_to_sid = {pool.submit(fetch_source, sid, SOURCES[sid], timeout): sid for sid in filtered}
        for fut in as_completed(future_to_sid):
            if stop_event and stop_event.is_set():
                log.info("Scrape cancelled")
                # cancel remaining
                for f in future_to_sid:
                    f.cancel()
                break
            sid = future_to_sid[fut]
            try:
                src_id, proxies, err = fut.result()
            except Exception as exc:
                proxies, err = [], str(exc)
                src_id = sid
            completed += 1
            if err:
                info = {"type": "source_error", "source": src_id, "label": SOURCES[src_id]["label"], "error": err, "current": completed, "total": total}
                errors.append(info)
                if progress_callback:
                    progress_callback(info)
            else:
                new_count = 0
                for p in proxies:
                    if p not in seen_global:
                        seen_global.add(p)
                        all_proxies.append(p)
                        new_count += 1
                info = {"type": "source_result", "source": src_id, "label": SOURCES[src_id]["label"], "count": len(proxies), "new": new_count, "total_found": len(all_proxies), "current": completed, "total": total}
                source_results.append(info)
                if progress_callback:
                    progress_callback(info)
                    progress_callback({"type": "progress", "current": completed, "total": total, "found": len(all_proxies)})
            if limit and len(all_proxies) >= limit:
                all_proxies = all_proxies[:limit]
                break

    if limit and len(all_proxies) > limit:
        all_proxies = all_proxies[:limit]

    random.shuffle(all_proxies)

    # fallback sample if nothing and network restricted
    demo_used = False
    if not all_proxies and completed == total and total > 0:
        sample = SAMPLE_PROXIES.copy()
        if limit and limit < len(sample):
            sample = sample[:limit]
        random.shuffle(sample)
        all_proxies = sample
        demo_used = True
        if progress_callback:
            progress_callback({"type": "note", "message": "Network restricted — showing sample proxies for demo. Real scrape works when deployed."})

    meta = {
        "total": len(all_proxies),
        "filtered": filtered,
        "completed": completed,
        "total_sources": total,
        "demo_used": demo_used,
        "source_results": source_results,
        "errors": errors,
    }
    return all_proxies, meta


def validate_one(proxy: str, timeout: int = DEFAULT_TIMEOUT, test_url: str = "http://httpbin.org/ip", protocol_hint: str = "http") -> Dict[str, Any]:
    raw = proxy.strip()
    if not raw:
        return {"proxy": proxy, "status": "invalid", "error": "empty"}
    if "://" not in raw:
        if protocol_hint in ("socks4", "socks5"):
            proxy_url = f"{protocol_hint}://{raw}"
        else:
            proxy_url = f"http://{raw}"
    else:
        proxy_url = raw
        protocol_hint = raw.split("://", 1)[0].lower()
    proxies_dict = {"http": proxy_url, "https": proxy_url}
    start = time.monotonic()
    try:
        resp = requests.get(
            test_url,
            proxies=proxies_dict,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json, */*"},
            verify=False,
        )
        latency = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            speed = "fast" if latency < 800 else "medium" if latency < 2000 else "slow"
            try:
                j = resp.json()
                origin = j.get("origin") or j.get("ip") or ""
            except:
                origin = resp.text[:60]
            return {
                "proxy": raw if "://" not in proxy else proxy,
                "status": "valid",
                "latency": latency,
                "speed": speed,
                "protocol": protocol_hint,
                "anonymity": "unknown",
                "origin": origin if isinstance(origin, str) else str(origin)[:60],
                "code": resp.status_code,
            }
        else:
            latency = int((time.monotonic() - start) * 1000)
            return {"proxy": raw, "status": "invalid", "latency": latency, "error": f"HTTP {resp.status_code}"}
    except requests.exceptions.ProxyError as exc:
        return {"proxy": raw, "status": "dead", "error": "ProxyError", "detail": str(exc)[:140]}
    except requests.exceptions.ConnectTimeout:
        return {"proxy": raw, "status": "timeout", "error": f"Timeout after {timeout}s"}
    except requests.exceptions.ReadTimeout:
        return {"proxy": raw, "status": "timeout", "error": f"Read timeout {timeout}s"}
    except requests.exceptions.ConnectionError as exc:
        msg = str(exc)[:140]
        if "SOCKS" in msg or "socks" in msg:
            return {"proxy": raw, "status": "dead", "error": "SOCKS failed", "detail": msg}
        return {"proxy": raw, "status": "dead", "error": "Connection failed", "detail": msg}
    except Exception as exc:
        return {"proxy": raw, "status": "error", "error": str(exc)[:160]}


def validate_proxies(
    proxies: List[str],
    timeout: int = DEFAULT_TIMEOUT,
    test_url: str = "http://httpbin.org/ip",
    protocol_hint: str = "http",
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    stop_event: Optional[threading.Event] = None,
    max_workers: int = MAX_WORKERS_VALIDATE,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validate proxies concurrently. Returns (results, counts).
    progress_callback receives {"type":"result", "result":..., "current":..., "total":..., "counts":...}
    """
    counts = {"valid": 0, "dead": 0, "timeout": 0, "invalid": 0, "error": 0}
    results: List[Dict[str, Any]] = []
    # deduplicate preserving order
    seen: Set[str] = set()
    uniq: List[str] = []
    for p in proxies:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    proxies = uniq
    total = len(proxies)
    if total == 0:
        return [], counts

    max_workers = min(max_workers, total, 100) or 1
    index = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_proxy = {pool.submit(validate_one, p, timeout, test_url, protocol_hint): p for p in proxies}
        for fut in as_completed(future_to_proxy):
            if stop_event and stop_event.is_set():
                log.info("Validate cancelled")
                for f in future_to_proxy:
                    f.cancel()
                break
            index += 1
            try:
                res = fut.result()
            except Exception as exc:
                res = {"proxy": future_to_proxy[fut], "status": "error", "error": str(exc)[:140]}
            status = res.get("status", "error")
            if status == "valid":
                counts["valid"] += 1
            elif status == "timeout":
                counts["timeout"] += 1
            elif status == "dead":
                counts["dead"] += 1
            elif status == "invalid":
                counts["invalid"] += 1
            else:
                counts["error"] += 1
            results.append(res)
            if progress_callback:
                progress_callback({"type": "result", "result": res, "current": index, "total": total, "counts": dict(counts)})
                progress_callback({"type": "progress", "current": index, "total": total, "counts": dict(counts)})
    return results, counts


def save_results(
    proxies: List[str],
    validation_results: Optional[List[Dict[str, Any]]] = None,
    output_dir: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    prefix: str = "",
) -> Path:
    """
    Save results to a timestamped folder.
    Returns path to the created folder.

    Folder structure:
    results/YYYY-MM-DD_HH-MM-SS/
        valid.txt
        valid.json
        valid.csv
        all.txt
        all.json
        raw_scraped.txt
        http.txt / https.txt / socks4.txt / socks5.txt (if protocol info)
        stats.json
        log.txt (caller should write)
    Also updates results/latest (copy) if possible.
    """
    if base_dir is None:
        # exe is frozen -> use exe directory; else use cwd
        if getattr(__import__("sys"), "frozen", False):
            base_dir = Path(__import__("sys").executable).parent
        else:
            base_dir = Path.cwd()
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = base_dir / "results" / f"{prefix}{timestamp}" if prefix else base_dir / "results" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine valid list
    if validation_results is not None:
        valid = [r["proxy"] for r in validation_results if r.get("status") == "valid"]
        # sort valid by latency
        valid_sorted = sorted([r for r in validation_results if r.get("status") == "valid"], key=lambda x: x.get("latency", 9999))
        valid = [r["proxy"] for r in valid_sorted]
        all_proxies = [r["proxy"] for r in validation_results]
        # protocol splits for valid
        proto_map: Dict[str, List[str]] = {}
        for r in valid_sorted:
            proto = r.get("protocol", "http")
            proto_map.setdefault(proto, []).append(r["proxy"])
    else:
        valid = []
        all_proxies = proxies
        proto_map = {}
        # naive split if proxies list has no validation: assume all http
        proto_map["http"] = proxies

    # Write files
    # valid.txt
    (output_dir / "valid.txt").write_text("\n".join(valid), encoding="utf-8")
    # all.txt
    (output_dir / "all.txt").write_text("\n".join(all_proxies if validation_results else proxies), encoding="utf-8")
    # raw_scraped.txt (original proxies before validation)
    (output_dir / "raw_scraped.txt").write_text("\n".join(proxies), encoding="utf-8")

    # valid.json
    if validation_results is not None:
        (output_dir / "valid.json").write_text(json.dumps(valid_sorted, indent=2), encoding="utf-8")
        (output_dir / "all.json").write_text(json.dumps(validation_results, indent=2), encoding="utf-8")
        # csv
        with open(output_dir / "valid.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["proxy", "status", "latency", "speed", "protocol", "origin", "error"])
            w.writeheader()
            for r in valid_sorted:
                w.writerow({k: r.get(k, "") for k in w.fieldnames})
        with open(output_dir / "all.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["proxy", "status", "latency", "speed", "protocol", "origin", "error", "detail"])
            w.writeheader()
            for r in validation_results:
                w.writerow({k: r.get(k, "") for k in w.fieldnames})
    else:
        # no validation yet
        (output_dir / "valid.json").write_text(json.dumps([], indent=2), encoding="utf-8")
        (output_dir / "all.json").write_text(json.dumps([{"proxy": p, "status": "unvalidated"} for p in proxies], indent=2), encoding="utf-8")

    # per-protocol valid files
    for proto, lst in proto_map.items():
        safe = re.sub(r"[^a-z0-9]", "_", proto.lower())
        (output_dir / f"{safe}.txt").write_text("\n".join(lst), encoding="utf-8")

    # stats.json — watermarked, protected
    stats = {
        "timestamp": datetime.now().isoformat(),
        "total_scraped": len(proxies),
        "total_validated": len(validation_results) if validation_results else 0,
        "valid": len(valid),
        "counts": None,
        "author": "harshi79",
        "author_full": "harshi79 / YorichiiPrime — https://github.com/harshi79",
        "watermark": "HARSHI79-ULTIMATE-PROXY-2026",
        "app": "Ultimate Proxy Scrapper v2.1.0",
        "version": "2.1.0",
        "repository": "https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator",
        "protected": True,
    }
    if validation_results is not None:
        # compute counts
        c = {"valid": 0, "dead": 0, "timeout": 0, "invalid": 0, "error": 0}
        for r in validation_results:
            st = r.get("status", "error")
            if st in c:
                c[st] += 1
            else:
                c["error"] += 1
        stats["counts"] = c
        # avg latency
        lats = [r["latency"] for r in validation_results if r.get("status") == "valid" and r.get("latency") is not None]
        if lats:
            stats["avg_latency_ms"] = sum(lats) // len(lats)
            stats["fastest_ms"] = min(lats)
            stats["slowest_ms"] = max(lats)
    (output_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    # _AUTHOR.txt — proves authenticity, prevents copy-cat claims
    try:
        (output_dir / "_AUTHOR.txt").write_text(
            f"Generated by Ultimate Proxy Scrapper v2.1.0\n"
            f"Author: harshi79 / YorichiiPrime — https://github.com/harshi79\n"
            f"Watermark: HARSHI79-ULTIMATE-PROXY-2026\n"
            f"Version: 2.1.0\n"
            f"Timestamp: {datetime.now().isoformat()}\n"
            f"Repository: https://github.com/harshi79/Ultimate-Free-Proxy-Scrapper-And-Validator\n"
            f"Protected — do not remove. This file proves authenticity.\n",
            encoding="utf-8"
        )
    except Exception as exc:
        log.warning(f"Could not write _AUTHOR.txt: {exc}")

    # latest -> copy to results/latest folder and keep symlink attempt
    try:
        latest_dir = output_dir.parent / "latest"
        if latest_dir.exists():
            # remove old latest if it's a dir or symlink
            import shutil
            if latest_dir.is_symlink():
                latest_dir.unlink()
            elif latest_dir.is_dir():
                shutil.rmtree(latest_dir)
        # copy entire folder to latest (as copy, not symlink for Windows compatibility)
        import shutil
        shutil.copytree(output_dir, latest_dir)
    except Exception as exc:
        log.warning("Could not create latest copy: %s", exc)

    return output_dir
