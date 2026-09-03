"""
Subscription Status Verifier — single-page dashboard.

A Flask application that lets a user verify the status of their own
subscriptions (ExpressVPN, Crunchyroll, Disney+). Credentials are checked
by the externally provided ``checkers`` module — no checking logic lives
in this file.

Routes
------
GET  /                      → HTML dashboard
POST /check                 → start a background check job for one service
GET  /stream/<service>      → Server-Sent Events stream (progress / result / done)
POST /stop/<service>        → request cancellation of a running job
GET  /health                → liveness probe
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, Response, jsonify, render_template, request

# ---------------------------------------------------------------------------
# checkers.py — provided separately (see checkers.example.py for the contract)
# ---------------------------------------------------------------------------
try:
    from checkers import DisneyChecker  # noqa: F401
    from checkers import ExpressVPNChecker  # noqa: F401
    from checkers import ProxyManager  # noqa: F401
    from checkers import CrunchyrollChecker  # noqa: F401

    CHECKERS_AVAILABLE = True
    CHECKERS_IMPORT_ERROR: Optional[str] = None
except ImportError as exc:  # pragma: no cover - depends on external file
    ExpressVPNChecker = CrunchyrollChecker = DisneyChecker = ProxyManager = None  # type: ignore
    CHECKERS_AVAILABLE = False
    CHECKERS_IMPORT_ERROR = str(exc)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
)
log = logging.getLogger("subcheck")

# Seconds a single check_account() call may run before it is treated as a timeout.
CHECK_TIMEOUT = int(os.environ.get("CHECK_TIMEOUT", "90"))
# Heartbeat interval (seconds) for SSE keep-alive pings.
PING_INTERVAL = 15

SERVICE_ALIASES: Dict[str, str] = {
    "expressvpn": "expressvpn",
    "crunchyroll": "crunchyroll",
    "disney": "disney",
    "disney+": "disney",
    "disneyplus": "disney",
    "disney_plus": "disney",
}

CHECKER_CLASSES: Dict[str, Any] = {
    "expressvpn": ExpressVPNChecker,
    "crunchyroll": CrunchyrollChecker,
    "disney": DisneyChecker,
}

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# ---------------------------------------------------------------------------
# Job management (one job per service, one background thread per job)
# ---------------------------------------------------------------------------
class Job:
    """Holds the queue, cancellation flag and state of a single check run."""

    def __init__(self, service: str) -> None:
        self.service = service
        self.queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.total = 0
        self.current = 0
        self.finished = False


JOBS: Dict[str, Job] = {}
JOBS_LOCK = threading.Lock()


def _stage_job(service: str) -> Job:
    """Create a job for *service*, cancelling any previous run for it."""
    with JOBS_LOCK:
        previous = JOBS.get(service)
        if previous is not None:
            previous.stop_event.set()
        job = Job(service)
        JOBS[service] = job
    return job


def _push(job: Job, payload: Dict[str, Any]) -> None:
    """Put an event on the job queue (never blocks)."""
    try:
        job.queue.put_nowait(payload)
    except queue.Full:  # pragma: no cover - queue is unbounded in practice
        log.warning("Queue full for %s, dropping event %s", job.service, payload.get("type"))


# ---------------------------------------------------------------------------
# checkers integration helpers
# ---------------------------------------------------------------------------
def _parse_entries(raw: str) -> List[Tuple[Optional[str], Optional[str]]]:
    """
    Parse a multiline string of ``email:password`` lines.

    Returns a list of ``(email, password)`` tuples.  Malformed lines are kept
    as ``(None, line)`` so the UI can report them instead of silently dropping.
    """
    entries: List[Tuple[Optional[str], Optional[str]]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            entries.append((None, line))
            continue
        email, _, password = line.partition(":")
        entries.append((email.strip(), password))
    return entries


def _parse_proxies(raw: str) -> List[str]:
    """Parse a multiline proxy list (one proxy per line, ``#`` comments allowed)."""
    proxies: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        proxies.append(line)
    return proxies


def _build_proxy_manager(proxies: List[str]):
    """Best-effort construction of the checkers' ProxyManager."""
    if not CHECKERS_AVAILABLE:
        return None
    attempts: List[Tuple[tuple, dict]] = [
        ((proxies,), {}),
        ((), {"proxies": proxies}),
        ((), {}),
    ]
    for args, kwargs in attempts:
        try:
            return ProxyManager(*args, **kwargs)
        except TypeError:
            continue
        except Exception as exc:  # constructor may validate/filter proxies
            log.warning("ProxyManager(%s) failed: %s", proxies[:3], exc)
            return None
    log.warning("Could not build ProxyManager with %d proxies", len(proxies))
    return None


def _build_checker(checker_cls, proxy_manager=None):
    """Best-effort construction of a checker, passing the ProxyManager if supported."""
    attempts: List[Tuple[tuple, dict]] = [((), {}), ((), {"proxy_manager": proxy_manager})]
    if proxy_manager is not None:
        attempts.insert(0, ((proxy_manager,), {}))
    for args, kwargs in attempts:
        try:
            return checker_cls(*args, **kwargs)
        except TypeError:
            continue
        except Exception as exc:  # pragma: no cover - checker-specific
            log.warning("Could not build checker %s with args %s: %s", checker_cls.__name__, args, exc)
            return None
    return None


def _run_single_check(checker, email: str, password: str) -> Dict[str, Any]:
    """
    Run one ``check_account`` call in its own daemon thread so a hung call can
    never block the rest of the job. Returns a normalised result dict.
    """
    result_q: "queue.Queue[Tuple[str, Any]]" = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result_q.put(("ok", checker.check_account(email, password)))
        except Exception as exc:  # reported below; thread must never die silently
            result_q.put(("err", exc))

    thread = threading.Thread(
        target=worker, name=f"check-{email[:24]}", daemon=True,
    )
    thread.start()
    thread.join(timeout=CHECK_TIMEOUT)

    if thread.is_alive():
        return {"status": "Timeout", "message": f"No response within {CHECK_TIMEOUT}s"}

    kind, value = result_q.get()
    if kind == "err":
        log.warning("check_account(%s) raised: %s", email, value)
        return {"status": "Error", "message": str(value)[:300] or value.__class__.__name__}
    return _coerce_result(value)


def _coerce_result(raw: Any) -> Dict[str, Any]:
    """
    Normalise whatever ``check_account`` returns into
    ``{"status": str, "message": str|None}``.
    """
    if raw is None:
        return {"status": "Unknown", "message": None}
    if isinstance(raw, dict):
        status = raw.get("status", raw.get("result", "Unknown"))
        return {"status": str(status), "message": raw.get("message") or raw.get("detail") or raw.get("reason")}
    if isinstance(raw, (tuple, list)) and raw and isinstance(raw[0], bool):
        status = "Valid" if raw[0] else "Invalid"
        message = str(raw[1]) if len(raw) > 1 else None
        return {"status": status, "message": message}
    return {"status": str(raw), "message": None}


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------
def _run_job(job: Job, entries: List[Tuple[Optional[str], Optional[str]]], proxies: List[str]) -> None:
    """Run one service's checks in a background thread, feeding the SSE queue."""
    service = job.service
    total = len(entries)
    job.total = total
    counts = {"valid": 0, "invalid": 0, "error": 0, "skipped": 0}
    done_sent = False

    def send_done() -> None:
        """Push the single terminal ``done`` event for this job (idempotent)."""
        nonlocal done_sent
        if done_sent:
            return
        done_sent = True
        _push(job, {
            "type": "done",
            "service": service,
            "total": total,
            "processed": job.current,
            "stopped": job.stop_event.is_set(),
            "summary": counts,
        })

    _push(job, {"type": "start", "service": service, "total": total})
    log.info("Job %s started with %d entries and %d proxies", service, total, len(proxies))

    try:
        checker_cls = CHECKER_CLASSES.get(service)
        if checker_cls is None:  # pragma: no cover - service is validated in /check
            _push(job, {"type": "error", "message": f"Unknown service: {service}"})
            return

        proxy_manager = _build_proxy_manager(proxies)
        checker = _build_checker(checker_cls, proxy_manager)
        if proxy_manager is None and proxies:
            _push(job, {"type": "note", "message": "Proxies supplied but ProxyManager is unavailable; running direct."})

        for index, (email, password) in enumerate(entries, start=1):
            if job.stop_event.is_set():
                log.info("Job %s cancelled by user", service)
                break

            # Malformed line — report and continue.
            if email is None:
                counts["skipped"] += 1
                _push(job, {
                    "type": "result",
                    "service": service,
                    "entry": password,
                    "status": "Skipped",
                    "message": "Malformed line (expected email:password)",
                    "current": index,
                    "total": total,
                })
                _push(job, {"type": "progress", "current": index, "total": total})
                job.current = index
                continue

            if checker is None:
                counts["error"] += 1
                _push(job, {
                    "type": "result",
                    "service": service,
                    "entry": email,
                    "status": "Error",
                    "message": "Checker could not be initialised",
                    "current": index,
                    "total": total,
                })
                _push(job, {"type": "progress", "current": index, "total": total})
                job.current = index
                continue

            result = _run_single_check(checker, email, password)
            status = result["status"]
            if status.lower() in {"valid", "active", "live", "ok", "working", "good"}:
                counts["valid"] += 1
            elif status.lower() in {"invalid", "dead", "bad", "expired", "failure", "fail"}:
                counts["invalid"] += 1
            else:
                counts["error"] += 1

            _push(job, {
                "type": "result",
                "service": service,
                "entry": email,
                "status": status,
                "message": result.get("message"),
                "current": index,
                "total": total,
            })
            _push(job, {"type": "progress", "current": index, "total": total})
            job.current = index

        send_done()
    except Exception:  # safety net: an unexpected failure must never kill the worker silently
        log.exception("Unexpected error in job %s", service)
        _push(job, {"type": "error", "message": "Internal error while checking entries."})
        send_done()
    finally:
        job.finished = True
        log.info("Job %s finished (%d/%d processed)", service, job.current, total)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index() -> str:
    return render_template("index.html", checkers_available=CHECKERS_AVAILABLE)


@app.route("/health")
def health() -> Response:
    return jsonify({"ok": True, "checkers_available": CHECKERS_AVAILABLE})


@app.post("/check")
def check() -> Tuple[Response, int] | Response:
    """Start a background verification job. Accepts JSON or form-encoded bodies."""
    data: Dict[str, Any]
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    service_raw = str(data.get("service", "")).strip().lower()
    service = SERVICE_ALIASES.get(service_raw)
    if not service:
        return jsonify({"ok": False, "error": f"Unknown service: {service_raw or '(empty)'}"}), 400

    entries_raw = str(data.get("entries", "") or "")
    proxies_raw = str(data.get("proxies", "") or "")

    if not entries_raw.strip():
        return jsonify({"ok": False, "error": "No credentials provided."}), 400

    if not CHECKERS_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "checkers.py is missing. Place it next to app.py, then restart the app. "
                     f"(import error: {CHECKERS_IMPORT_ERROR})",
        }), 503

    entries = _parse_entries(entries_raw)
    proxies = _parse_proxies(proxies_raw)
    if not entries:
        return jsonify({"ok": False, "error": "No valid credential lines found."}), 400

    job = _stage_job(service)

    thread = threading.Thread(
        target=_run_job,
        args=(job, entries, proxies),
        name=f"job-{service}-{int(time.time())}",
        daemon=True,
    )
    job.thread = thread
    thread.start()

    log.info("POST /check → %s (%d entries, %d proxies)", service, len(entries), len(proxies))
    return jsonify({"ok": True, "service": service, "total": len(entries), "proxies": len(proxies)}), 202


@app.post("/stop/<service>")
def stop(service: str) -> Tuple[Response, int] | Response:
    """Request cancellation of a running job for *service*."""
    key = SERVICE_ALIASES.get(service.strip().lower())
    if not key:
        return jsonify({"ok": False, "error": f"Unknown service: {service}"}), 400
    with JOBS_LOCK:
        job = JOBS.get(key)
    if job is None or job.finished:
        return jsonify({"ok": True, "running": False})
    job.stop_event.set()
    return jsonify({"ok": True, "running": True, "stopping": True})


@app.get("/stream/<service>")
def stream(service: str) -> Response:
    """Server-Sent Events stream for a service's live progress and results."""
    key = SERVICE_ALIASES.get(service.strip().lower())
    if not key:
        return jsonify({"ok": False, "error": f"Unknown service: {service}"}), 404
    with JOBS_LOCK:
        job = JOBS.get(key)
    if job is None:
        return jsonify({"ok": False, "error": "No active job for this service."}), 404
    # Even if the job finished before the client attached, queued events are
    # replayed so a fast run is never lost.
    return _sse_response(_event_stream(job))


def _sse_response(generator) -> Response:
    resp = Response(generator, mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache, no-transform"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp


def _format_sse(event: str, payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    # json.dumps escapes newlines, so data stays on a single line.
    return f"event: {event}\ndata: {data}\n\n"


def _event_stream(job: Job):
    """Yield SSE events from the job queue until the terminal ``done`` event."""
    yield _format_sse("connected", {"service": job.service, "total": job.total})
    while True:
        if job.finished and job.queue.empty():
            break
        try:
            payload = job.queue.get(timeout=PING_INTERVAL)
        except queue.Empty:
            if job.finished and job.queue.empty():
                break
            # Heartbeat so proxies keep the connection alive during long checks.
            yield f": ping {int(time.time())}\n\n"
            continue
        event_type = payload.get("type", "message")
        yield _format_sse(event_type, payload)
        if event_type == "done":
            break
    yield _format_sse("closed", {"service": job.service})


@app.after_request
def security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    log.info("Starting dashboard on http://0.0.0.0:%s", port)
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
