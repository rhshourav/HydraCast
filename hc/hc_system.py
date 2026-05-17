"""
aGMvbGljZW5zZV9ndWFyZC5weSDigJQgU29mdHdhcmUgbGljZW5zZSB2YWxpZGF0aW9uIGZvciBIeWRyYUNhc3QuCgpBcmNoaXRlY3R1cmUgb3ZlcnZpZXcK4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAClRoaXMgbW9kdWxlIGltcGxlbWVudHMgYSB0aHJlZS1sYXllciBsaWNlbnNlIGVuZm9yY2VtZW50IHN5c3RlbToKCiAgTGF5ZXIgMSDigJQgU3RhcnR1cCBnYXRlCiAgICBhc3NlcnRfbGljZW5zZWQoKSBpcyBjYWxsZWQgb25jZSB3aGVuIHRoZSBhcHBsaWNhdGlvbiBzdGFydHMuCiAgICBJZiB0aGUgaW5zdGFsbGF0aW9uIGhhcyBiZWVuIGxvY2tlZCBpdCBwcmludHMgYSBjbGVhciBtZXNzYWdlIGFuZCBleGl0cy4KCiAgTGF5ZXIgMiDigJQgUGVyaW9kaWMgcmVtb3RlIHZhbGlkYXRpb24KICAgIHN0YXJ0X2NoZWNrZXIoKSBsYXVuY2hlcyBhIGJhY2tncm91bmQgdGhyZWFkIChvbmUgcGVyIGNhbGxpbmcgbW9kdWxlKQogICAgdGhhdCBmZXRjaGVzIGEgcmVtb3RlIHZhbGlkYXRpb24gdG9rZW4gZXZlcnkgMeKAkzE1IG1pbnV0ZXMgKHJhbmRvbWlzZWQpLgogICAgT25seSBhIGNvbmZpcm1lZCBtaXNtYXRjaCAoc2VydmVyIHJlYWNoYWJsZSwgd3JvbmcgdG9rZW4pIGluY3JlbWVudHMgdGhlCiAgICBmYWlsdXJlIGNvdW50ZXIuIE5ldHdvcmsgZXJyb3JzIGFyZSBpZ25vcmVkIHNvIGxlZ2l0aW1hdGUgdXNlcnMgYmVoaW5kCiAgICBmaXJld2FsbHMgb3Igd2l0aCBpbnRlcm1pdHRlbnQgY29ubmVjdGl2aXR5IGFyZSBub3QgYWZmZWN0ZWQuCgogIExheWVyIDMg4oCUIFBlcnNpc3RlbnQgbG9jawogICAgQWZ0ZXIgTUFYX0ZBSUxVUkVTIGNvbmZpcm1lZCBtaXNtYXRjaGVzIGEgbG9jayBmaWxlIGlzIHdyaXR0ZW4gdG8gYQogICAgc3RhdGUgZGlyZWN0b3J5IHRoYXQgaXMgc2VwYXJhdGUgZnJvbSB0aGUgc291cmNlIHRyZWUuIFRoZSBsb2NrIHBlcnNpc3RzCiAgICBldmVuIGlmIHNvdXJjZSBmaWxlcyBhcmUgcmVwbGFjZWQsIGJlY2F1c2UgaXQgaXMga2V5ZWQgdG8gdGhlCiAgICBpbnN0YWxsYXRpb24gcGF0aCwgbm90IHRoZSBjb2RlIGl0c2VsZi4KClJvYnVzdG5lc3MK4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSACuKAoiBUaGlzIG1vZHVsZSBpcyBpbXBvcnRlZCBhcyBhIGhhcmQgZGVwZW5kZW5jeSBieSBmb3VyIHNlcGFyYXRlIGZpbGVzCiAgKGh5ZHJhY2FzdC5weSwgd2F0Y2hkb2cucHksIGNvbXBsaWFuY2UucHksIHdvcmtlci5weSkuICBSZW1vdmluZyBhbnkgb25lCiAgb2YgdGhvc2UgaW1wb3J0cyBjYXVzZXMgYW4gQXR0cmlidXRlRXJyb3IvSW1wb3J0RXJyb3IgdGhhdCBwcmV2ZW50cyB0aGUKICBhcHBsaWNhdGlvbiBmcm9tIHN0YXJ0aW5nLgrigKIgRWFjaCBpbXBvcnRpbmcgbW9kdWxlIHN0YXJ0cyBpdHMgb3duIGluZGVwZW5kZW50IGNoZWNrZXIgdGhyZWFkLCBzbwogIGRpc2FibGluZyBvbmUgY2hlY2sgZG9lcyBub3QgZGlzYWJsZSB0aGUgb3RoZXJzLgrigKIgVGhlIGZhaWx1cmUgY291bnRlciBhbmQgbG9jayBmaWxlIGFyZSBzdG9yZWQgb3V0c2lkZSB0aGUgc291cmNlIHRyZWUgaW4KICBhIHBlci1pbnN0YWxsYXRpb24gc3RhdGUgZGlyZWN0b3J5IChzZWUgX3N0YXRlX2RpcigpKS4KCkRpc2Nsb3N1cmUK4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAClRoaXMgbWVjaGFuaXNtIGlzIGRpc2Nsb3NlZCB0byBlbmQgdXNlcnMgaW4gdGhlIExJQ0VOU0UgZmlsZSBkaXN0cmlidXRlZAp3aXRoIEh5ZHJhQ2FzdC4gIFVzZXJzIGFyZSBpbmZvcm1lZCB0aGF0OgogIChhKSB0aGUgYXBwbGljYXRpb24gcGVyaW9kaWNhbGx5IGNvbnRhY3RzIHRoZSB2YWxpZGF0aW9uIHNlcnZlcjsKICAoYikgcmVwZWF0ZWQgdmFsaWRhdGlvbiBmYWlsdXJlcyB3aWxsIHBlcm1hbmVudGx5IGRpc2FibGUgdGhlIGluc3RhbGxhdGlvbjsKICAoYykgY29udGFjdCBpbmZvcm1hdGlvbiBmb3IgbGljZW5zZSByZW5ld2FsIGlzIHByb3ZpZGVkLg==
"""
from __future__ import annotations

import json
import logging
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Remote file that must contain exactly VALIDATION_TOKEN to pass.
VALIDATION_URL = (
    "https://raw.githubusercontent.com/rhshourav/HydraCast"
    "/refs/heads/main/resources/status.hc.fa"
)

# Token the remote file is expected to contain.
VALIDATION_TOKEN = "ZmFhYWFhYWEuLg=="

# Number of *confirmed* failures (server reachable, wrong token) before lock.
MAX_FAILURES = 10

# Background check interval: random value in [MIN, MAX] seconds.
CHECK_INTERVAL_MIN = 60    # 1 minute
CHECK_INTERVAL_MAX = 900   # 15 minutes

# Contact shown in the lock message.
SUPPORT_URL = "https://github.com/rhshourav/HydraCast"

# ---------------------------------------------------------------------------
# State directory  (outside the source tree so it survives source replacement)
# ---------------------------------------------------------------------------

def _state_dir() -> Path:
    """
    Return (and create) the directory that holds the counter and lock files.

    Location: <home>/.hydracast/  — persists across reinstalls.
    """
    d = Path.home() / ".hydracast"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _counter_file() -> Path:
    return _state_dir() / "validation_failures.json"


def _lock_file() -> Path:
    return _state_dir() / "installation.lock"


# ---------------------------------------------------------------------------
# Failure counter
# ---------------------------------------------------------------------------

def _read_failures() -> int:
    try:
        data = json.loads(_counter_file().read_text())
        return int(data.get("failures", 0))
    except Exception:
        return 0


def _write_failures(n: int) -> None:
    try:
        _counter_file().write_text(json.dumps({
            "failures":  n,
            "updated":   datetime.now().isoformat(),
            "max":       MAX_FAILURES,
        }, indent=2))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Lock  (permanent once written)
# ---------------------------------------------------------------------------

def is_locked() -> bool:
    """Return True when this installation has been permanently locked."""
    return _lock_file().exists()


def _write_lock() -> None:
    try:
        _lock_file().write_text(json.dumps({
            "locked_at": datetime.now().isoformat(),
            "reason":    "Repeated license validation failures",
            "contact":   SUPPORT_URL,
        }, indent=2))
        log.warning("license: installation locked — validation failed %d times.",
                    MAX_FAILURES)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Layer 1 — Startup gate
# ---------------------------------------------------------------------------

def assert_licensed() -> None:
    """
    Call once at startup (before any service begins).

    If the installation is locked, prints a clear message and exits with
    a non-zero status code.  Otherwise returns immediately.
    """
    if not is_locked():
        return

    border = "═" * 58
    lines = [
        f"╔{border}╗",
        f"║{'HydraCast — License Validation Failed':^58}║",
        f"║{'':<58}║",
        f"║{'This installation has been disabled because license':<58}║",
        f"║{'validation failed repeatedly.':58}║",
        f"║{'':<58}║",
        f"║{'To restore access, contact the author:':58}║",
        f"║{f'  {SUPPORT_URL}':<58}║",
        f"╚{border}╝",
    ]
    print("\n" + "\n".join(lines) + "\n", file=sys.stderr)
    sys.exit(74)   # BSD EX_IOERR — distinctive, non-zero


# ---------------------------------------------------------------------------
# Layer 2 — Remote validation
# ---------------------------------------------------------------------------

def validate_once() -> None:
    """
    Perform one validation check against the remote server.

    Outcomes:
      • Network unreachable  → counter unchanged  (legitimate user protection)
      • Token matches        → counter reset to 0
      • Token mismatches     → counter + 1; lock + exit when MAX_FAILURES reached
    """
    if is_locked():
        assert_licensed()
        return

    # ── Fetch remote token ────────────────────────────────────────────────
    try:
        request = urllib.request.Request(
            VALIDATION_URL,
            headers={"User-Agent": "HydraCast/5.3 LicenseCheck"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            remote_token = response.read().decode().strip()

    except (urllib.error.URLError, OSError, TimeoutError):
        # Server unreachable — do not penalise the user.
        log.debug("license: server unreachable — check skipped")
        return

    except Exception as exc:
        log.debug("license: unexpected fetch error (%s) — check skipped", exc)
        return

    # ── Compare ───────────────────────────────────────────────────────────
    if remote_token == VALIDATION_TOKEN:
        _write_failures(0)
        log.debug("license: validation passed")
        return

    # Reachable but wrong token → genuine failure.
    failures = _read_failures() + 1
    _write_failures(failures)
    log.warning(
        "license: validation failed (%d / %d) — token mismatch",
        failures, MAX_FAILURES,
    )

    if failures >= MAX_FAILURES:
        _write_lock()
        assert_licensed()   # exits immediately


# ---------------------------------------------------------------------------
# Layer 3 — Background checker thread
# ---------------------------------------------------------------------------

_active_checkers: set[str] = set()
_checkers_lock   = threading.Lock()


def start_checker(name: str) -> None:
    """
    Start a named background checker thread.

    Each calling module should pass a unique *name* so it is possible to
    confirm in logs that all checker threads are running.  Calling with the
    same name twice is a safe no-op.

    Example::
        from hc.license_guard import start_checker
        start_checker("watchdog")
    """
    with _checkers_lock:
        if name in _active_checkers:
            return
        _active_checkers.add(name)

    def _loop() -> None:
        # Stagger: threads start at different random offsets.
        initial_wait = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
        log.debug("license checker '%s': first check in %.0f s", name, initial_wait)
        time.sleep(initial_wait)

        while True:
            try:
                validate_once()
            except SystemExit:
                raise   # let assert_licensed() propagate
            except Exception:
                pass    # never crash the background thread

            wait = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
            log.debug("license checker '%s': next check in %.0f s", name, wait)
            time.sleep(wait)

    thread = threading.Thread(
        target=_loop,
        daemon=True,
        name=f"license-checker-{name}",
    )
    thread.start()
    log.info("license: checker '%s' started (interval 1–15 min)", name)
