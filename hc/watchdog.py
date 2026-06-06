"""
hc/watchdog.py  —  HydraCast Guardian Watchdog

Architecture
────────────
The watchdog runs as its own SEPARATE PROCESS (not a thread), launched by
hydracast.py via subprocess before the main HC process starts.  It outlives
the main process and restarts it whenever it crashes or becomes unresponsive.

                    ┌──────────────────────────────┐
                    │  hydracast_guardian.exe /     │
                    │  watchdog.py --guardian       │  ← THIS PROCESS
                    │                               │
                    │  • Heartbeat IPC (UDP 17777)  │
                    │  • HTTP status  (:17778)      │
                    │  • Crash log    (logs/)       │
                    │  • Auto-restart w/ backoff    │
                    └──────────┬───────────────────┘
                               │ subprocess.Popen
                               ▼
                    ┌──────────────────────────────┐
                    │  hydracast.exe (main app)     │
                    │                               │
                    │  • Sends heartbeat UDP pings  │
                    │  • Writes PID to guardian.pid │
                    └──────────────────────────────┘

What it guards
──────────────
1. Main process crash      → detect via poll() + stderr; restart with backoff
2. Heartbeat timeout       → detect hung/frozen process; SIGKILL + restart
3. Playlist file missing   → warn early in per-stream log + global log
4. File too small/corrupt  → same
5. Port stuck in use       → logged as pre-start warning
6. Max restarts exceeded   → stop retrying; write crash dump; pop native error

IPC / Status endpoint
─────────────────────
• Guardian exposes http://localhost:17778/guardian/status  (JSON)
  The main web handler polls this and merges it into /api/system_stats so
  the Web UI can render a "Guardian" card showing:
    - guardian alive (always True if endpoint responds)
    - main process PID + uptime
    - restart count + last restart time
    - crash log tail (last 20 lines)
    - per-stream file health warnings
    - heartbeat age (how long since last ping)

Heartbeat
─────────
The main app calls HeartbeatSender.start() from a daemon thread.
This sends a tiny UDP packet to 127.0.0.1:HEARTBEAT_PORT every
HEARTBEAT_INTERVAL seconds.  If the guardian sees no packet for
HEARTBEAT_TIMEOUT seconds it assumes the process is frozen and
kills + restarts it.

IMPORTANT: last_heartbeat is reset to None every time a new child
is launched so stale timestamps from the previous run never cause
instant false-positive kills.

Usage
─────
Launched automatically by hydracast.py at startup.
Can also run standalone for testing:

    python -m hc.watchdog --guardian --target hydracast.exe
    python -m hc.watchdog --guardian --target "python hydracast.py"

Playlist watchdog (legacy API preserved)
─────────────────────────────────────────
PlaylistWatchdog and find_next_valid_item are still exported so existing
worker.py call-sites are unchanged.  The per-stream file checks now also
feed into the guardian status endpoint so the Web UI sees them.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import re
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from hc.models import PlaylistItem, StreamState, StreamStatus

# ── Constants ─────────────────────────────────────────────────────────────────
GUARDIAN_VERSION    = "2.1.0"
HEARTBEAT_PORT      = 17777        # UDP — main process sends pings here
STATUS_PORT         = 17778        # TCP — guardian exposes JSON status here
HEARTBEAT_INTERVAL  = 10.0         # seconds between pings from main process
HEARTBEAT_TIMEOUT   = 45.0         # seconds before guardian considers process frozen
# Startup grace period: after launching the child, ignore heartbeat absence
# for this many seconds.  Gives the app time to import, boot the web server,
# and start the HeartbeatSender thread before the guardian starts checking.
HEARTBEAT_GRACE     = 60.0         # seconds — covers slow cold-start on HDD
MAX_RESTARTS        = 10           # give up after this many consecutive crashes
BASE_RESTART_DELAY  = 3.0          # initial backoff delay (doubles each crash)
MAX_RESTART_DELAY   = 120.0        # cap backoff at 2 minutes
CHECK_INTERVAL      = 30.0         # playlist watchdog poll interval (seconds)
MIN_FILE_BYTES      = 1024         # files smaller than this are treated as corrupt
GUARDIAN_PID_FILE   = "guardian.pid"  # written relative to LOGS_DIR

IS_WIN = platform.system() == "Windows"

log = logging.getLogger("hc.watchdog")


# =============================================================================
# SHARED STATUS STORE  (guardian process writes; status HTTP reads)
# =============================================================================
class _GuardianStatus:
    """Thread-safe store for everything the status endpoint returns."""

    def __init__(self) -> None:
        self._lock           = threading.Lock()
        self.started_at      = datetime.now(timezone.utc).isoformat()
        self.target_cmd: str = ""
        self.target_pid: Optional[int] = None
        self.target_started: Optional[str] = None   # ISO timestamp
        self.restart_count: int  = 0
        self.last_restart:  Optional[str] = None    # ISO timestamp
        self.last_crash_reason: str = ""
        self.last_heartbeat: Optional[float] = None  # time.monotonic()
        self.heartbeat_ok: bool = False
        self.crash_log: List[str] = []              # last 200 lines
        self.file_warnings: Dict[str, List[str]] = {}  # stream→[warnings]
        self.stopping: bool = False

    # ── Snapshot (for JSON serialisation) ─────────────────────────────────────
    def snapshot(self) -> dict:
        with self._lock:
            hb_age = (
                round(time.monotonic() - self.last_heartbeat, 1)
                if self.last_heartbeat is not None else None
            )
            return {
                "guardian_version": GUARDIAN_VERSION,
                "guardian_started": self.started_at,
                "target_cmd":       self.target_cmd,
                "target_pid":       self.target_pid,
                "target_started":   self.target_started,
                "restart_count":    self.restart_count,
                "last_restart":     self.last_restart,
                "last_crash_reason":self.last_crash_reason,
                "heartbeat_age_s":  hb_age,
                "heartbeat_ok":     self.heartbeat_ok,
                "crash_log_tail":   list(self.crash_log[-20:]),
                "file_warnings":    dict(self.file_warnings),
                "stopping":         self.stopping,
            }

    # ── Mutators (always called under lock or from a single thread) ───────────
    def set_pid(self, pid: Optional[int]) -> None:
        with self._lock:
            self.target_pid = pid
            self.target_started = (
                datetime.now(timezone.utc).isoformat() if pid else None
            )

    def record_restart(self, reason: str) -> None:
        with self._lock:
            self.restart_count += 1
            self.last_restart = datetime.now(timezone.utc).isoformat()
            self.last_crash_reason = reason

    def record_heartbeat(self) -> None:
        with self._lock:
            self.last_heartbeat = time.monotonic()
            self.heartbeat_ok = True

    def reset_heartbeat(self) -> None:
        """
        Clear heartbeat state when a new child is launched.

        FIX (Bug #4 + #5): Without this, last_heartbeat holds the timestamp
        from the previous run.  The new process needs HEARTBEAT_GRACE seconds
        to boot; checking against a stale old timestamp would immediately fire
        a false-positive timeout and kill the freshly-started child.
        """
        with self._lock:
            self.last_heartbeat = None
            self.heartbeat_ok = False

    def check_heartbeat_freshness(self, launch_time: float) -> bool:
        """
        Return True if the heartbeat is within tolerance.

        FIX (Bug #4): Adds a per-launch startup grace window.
        If the child was launched less than HEARTBEAT_GRACE seconds ago AND
        no heartbeat has been received yet, we return True (not timed out).
        This prevents killing a freshly-started process that hasn't had time
        to boot its HeartbeatSender thread yet.

        Parameters
        ──────────
        launch_time : time.monotonic() value recorded just before Popen().
        """
        with self._lock:
            now = time.monotonic()

            # Still inside the startup grace window — don't check yet.
            if self.last_heartbeat is None:
                if (now - launch_time) < HEARTBEAT_GRACE:
                    return True          # give it time to boot
                # Grace expired and still no heartbeat — timed out.
                self.heartbeat_ok = False
                return False

            age = now - self.last_heartbeat
            self.heartbeat_ok = age < HEARTBEAT_TIMEOUT
            return self.heartbeat_ok

    def append_crash_log(self, line: str) -> None:
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            self.crash_log.append(f"[{ts}] {line}")
            if len(self.crash_log) > 200:
                self.crash_log = self.crash_log[-200:]

    def set_file_warning(self, stream: str, warnings: List[str]) -> None:
        with self._lock:
            self.file_warnings[stream] = warnings

    def clear_file_warnings(self, stream: str) -> None:
        with self._lock:
            self.file_warnings.pop(stream, None)


# Single global instance — populated by the guardian main loop.
_STATUS = _GuardianStatus()


# =============================================================================
# STATUS HTTP SERVER  (lightweight — only serves /guardian/status)
# =============================================================================
class _StatusHandler(BaseHTTPRequestHandler):

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/guardian/status", "/guardian"):
            body = json.dumps(_STATUS.snapshot(), indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args) -> None:  # noqa: N802
        pass   # suppress access log noise


def _start_status_server() -> Optional[threading.Thread]:
    """Start the guardian status HTTP server on STATUS_PORT in a daemon thread."""
    try:
        server = HTTPServer(("127.0.0.1", STATUS_PORT), _StatusHandler)
    except OSError as exc:
        log.warning("Guardian status server could not bind to :%d — %s", STATUS_PORT, exc)
        return None

    t = threading.Thread(target=server.serve_forever, daemon=True,
                         name="guardian-status-http")
    t.start()
    log.info("Guardian status HTTP running on http://127.0.0.1:%d/guardian/status",
             STATUS_PORT)
    return t


# =============================================================================
# HEARTBEAT LISTENER  (UDP receiver in guardian process)
# =============================================================================
def _start_heartbeat_listener() -> Optional[threading.Thread]:
    """Listen for UDP heartbeat pings from the main process."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", HEARTBEAT_PORT))
        sock.settimeout(2.0)
    except OSError as exc:
        log.warning(
            "Guardian heartbeat listener could not bind to UDP :%d — %s",
            HEARTBEAT_PORT, exc)
        return None

    def _loop() -> None:
        log.info("Heartbeat listener on UDP :%d", HEARTBEAT_PORT)
        while not _STATUS.stopping:
            try:
                data, _ = sock.recvfrom(64)
                if data.startswith(b"HC-ALIVE"):
                    _STATUS.record_heartbeat()
            except socket.timeout:
                pass
            except OSError:
                break
        sock.close()

    t = threading.Thread(target=_loop, daemon=True, name="guardian-heartbeat-rx")
    t.start()
    return t


# =============================================================================
# PROCESS LAUNCHER + SUPERVISOR LOOP
# =============================================================================

def _resolve_cmd(target: str) -> List[str]:
    """
    Convert a target string to an argv list.

    FIX (Bug #7): The original used target.split() which breaks on paths
    containing spaces (e.g. "C:\\Program Files\\HydraCast\\hydracast.exe").
    We now use shlex.split() on POSIX and a smarter parser on Windows that
    respects double-quoted tokens, so paths with spaces work correctly.

    Examples
    ────────
    "C:\\Program Files\\HydraCast\\hydracast.exe"  → one element (quoted path)
    "python hydracast.py"                          → ["python", "hydracast.py"]
    '"C:\\Program Files\\HC\\hydracast.exe"'       → one element, quotes stripped
    """
    target = target.strip()

    if IS_WIN:
        # On Windows, shlex uses POSIX rules which mishandles backslashes.
        # Use a simple quoted-token parser instead.
        parts: List[str] = []
        i = 0
        while i < len(target):
            if target[i] == '"':
                end = target.find('"', i + 1)
                if end == -1:
                    parts.append(target[i + 1:])
                    break
                parts.append(target[i + 1:end])
                i = end + 1
            elif target[i] == ' ':
                i += 1
            else:
                j = i
                while j < len(target) and target[j] != ' ':
                    j += 1
                parts.append(target[i:j])
                i = j
    else:
        parts = shlex.split(target)

    if not parts:
        return [target]

    # If running as frozen exe, look for the target beside our own executable.
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidate = exe_dir / Path(parts[0]).name
        if candidate.exists():
            parts[0] = str(candidate)

    return parts


def _launch(cmd: List[str]) -> subprocess.Popen:
    """
    Launch the target process.

    FIX (Bug #8): The original used CREATE_NO_WINDOW (0x08000000) which
    suppresses the console window of hydracast.exe — a console app.  That
    made the TUI invisible when the guardian restarted the app.

    We now use CREATE_NEW_CONSOLE (0x00000010) so the restarted process
    gets its own console window, which hydracast.py then manages via
    ShowWindow() / SetConsoleTitle() exactly as on first launch.
    """
    kwargs: dict = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge so we capture everything
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if IS_WIN:
        # CREATE_NEW_CONSOLE: give the child its own console window.
        # hydracast.py's _show_console() / _set_console_title() will manage it.
        CREATE_NEW_CONSOLE = 0x00000010
        kwargs["creationflags"] = CREATE_NEW_CONSOLE
    return subprocess.Popen(cmd, **kwargs)


def _drain_output(proc: subprocess.Popen) -> None:
    """
    Read all remaining stdout/stderr from a finished process and store in
    the crash log.  Called after poll() returns non-None.
    """
    if proc.stdout is None:
        return
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _STATUS.append_crash_log(line)
                log.debug("[target] %s", line)
    except Exception:
        pass


def _stream_output(proc: subprocess.Popen) -> threading.Thread:
    """
    Background thread that continuously reads proc stdout and feeds it into
    the crash log buffer + Python logger (at DEBUG level).
    """
    def _reader():
        if proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    _STATUS.append_crash_log(line)
                    log.debug("[target] %s", line)
        except Exception:
            pass

    t = threading.Thread(target=_reader, daemon=True,
                         name="guardian-output-drain")
    t.start()
    return t


def _show_fatal_error(title: str, msg: str) -> None:
    """Show a native error dialog on Windows; log on other platforms."""
    log.error("FATAL: %s — %s", title, msg)
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
        except Exception:
            pass


def _write_pid_file(pid_path: Path, pid: int) -> None:
    try:
        pid_path.write_text(str(pid), encoding="utf-8")
    except Exception as exc:
        log.warning("Could not write PID file %s: %s", pid_path, exc)


def _remove_pid_file(pid_path: Path) -> None:
    try:
        pid_path.unlink(missing_ok=True)
    except Exception:
        pass


def guardian_loop(target: str, log_dir: Path) -> None:
    """
    Main guardian supervisor loop.

    Runs until MAX_RESTARTS is exceeded or _STATUS.stopping is set.

    Key fixes in this version
    ─────────────────────────
    • Bug #1: Removed the broken `proc._start_new_session` uptime calculation.
      launch_time is now recorded with time.monotonic() right before Popen().

    • Bug #2: attempts incremented correctly; first restart always gets a delay.

    • Bug #3: frozen_kills > 0 forces non-zero rc so the guardian never
      mistakes a force-killed process for a clean user-quit.

    • Bug #4 + #5: _STATUS.reset_heartbeat() is called before each new launch.
      check_heartbeat_freshness() now receives launch_time and honours a
      HEARTBEAT_GRACE startup window so a freshly-booted child is never
      instantly killed because of a stale timestamp from the previous run.
    """
    _STATUS.target_cmd = target
    cmd = _resolve_cmd(target)
    pid_path = log_dir / GUARDIAN_PID_FILE

    delay    = BASE_RESTART_DELAY
    attempts = 0
    proc: Optional[subprocess.Popen] = None

    while not _STATUS.stopping:
        # ── Apply restart delay after first crash ──────────────────────────────
        if attempts > 0:
            reason = _STATUS.last_crash_reason or "unknown"
            log.warning(
                "Restarting target (attempt %d/%d) in %.0fs — reason: %s",
                attempts, MAX_RESTARTS, delay, reason,
            )
            _STATUS.append_crash_log(
                f"--- Restart #{attempts}/{MAX_RESTARTS} in {delay:.0f}s "
                f"(reason: {reason}) ---"
            )
            # Interruptible sleep so we react to _STATUS.stopping quickly.
            deadline = time.monotonic() + delay
            while time.monotonic() < deadline and not _STATUS.stopping:
                time.sleep(0.2)
            if _STATUS.stopping:
                break
            delay = min(delay * 2, MAX_RESTART_DELAY)

        if attempts >= MAX_RESTARTS:
            msg = (
                f"HydraCast crashed {MAX_RESTARTS} times and the guardian "
                f"has given up restarting.\n\nLast reason: {_STATUS.last_crash_reason}\n\n"
                f"Check logs\\guardian.log for details."
            )
            _show_fatal_error("HydraCast — Guardian Gave Up", msg)
            _STATUS.stopping = True
            break

        # FIX (Bug #4 + #5): Reset heartbeat state BEFORE launching the child.
        # This clears the stale last_heartbeat from the previous run so the
        # new process gets a fresh HEARTBEAT_GRACE window to boot up.
        _STATUS.reset_heartbeat()

        # ── Launch the target ─────────────────────────────────────────────────
        log.info("Guardian launching: %s", " ".join(cmd))
        _STATUS.append_crash_log(
            f"=== Guardian launching (attempt {attempts + 1}): {' '.join(cmd)} ==="
        )
        try:
            # Record launch time BEFORE Popen so the grace window starts now.
            launch_time = time.monotonic()   # FIX (Bug #1)
            proc = _launch(cmd)
        except Exception as exc:
            reason = f"Launch failed: {exc}"
            log.error(reason)
            _STATUS.record_restart(reason)
            _STATUS.append_crash_log(reason)
            attempts += 1
            continue

        _STATUS.set_pid(proc.pid)
        _write_pid_file(pid_path, proc.pid)
        log.info("Target PID %d started.", proc.pid)

        # Start draining output in background.
        output_thread = _stream_output(proc)

        # ── Poll loop — watch for crash OR heartbeat timeout ───────────────────
        frozen_kills = 0
        while True:
            rc = proc.poll()
            if rc is not None:
                # Process exited on its own.
                output_thread.join(timeout=3)
                break

            # FIX (Bug #4): pass launch_time so check honours the grace window.
            if not _STATUS.check_heartbeat_freshness(launch_time):
                frozen_kills += 1
                log.error(
                    "Heartbeat timeout after %.0fs — process PID %d appears frozen. "
                    "Sending SIGKILL (kill #%d).",
                    HEARTBEAT_TIMEOUT, proc.pid, frozen_kills,
                )
                _STATUS.append_crash_log(
                    f"HEARTBEAT TIMEOUT — PID {proc.pid} frozen after "
                    f"{HEARTBEAT_TIMEOUT:.0f}s silence — force-killing."
                )
                _STATUS.record_restart(f"heartbeat timeout (kill #{frozen_kills})")
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
                output_thread.join(timeout=3)

                # FIX (Bug #3): If we force-killed, always treat rc as non-zero
                # so the guardian never mistakes this for a clean user-quit.
                polled = proc.poll()
                rc = polled if (polled is not None and polled != 0) else -9
                break

            if _STATUS.stopping:
                log.info("Shutdown requested — terminating target PID %d.", proc.pid)
                try:
                    proc.terminate()
                    proc.wait(timeout=8)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                output_thread.join(timeout=3)
                rc = 0
                break

            time.sleep(1.0)

        # ── Process is gone — analyse exit ─────────────────────────────────────
        _STATUS.set_pid(None)
        _remove_pid_file(pid_path)
        attempts += 1

        # FIX (Bug #3): Only treat rc==0 as intentional quit when we did NOT
        # force-kill the process.  frozen_kills > 0 means we killed it ourselves;
        # a rc of 0 in that case is a Windows quirk, not a clean user quit.
        if _STATUS.stopping:
            log.info("Stop was requested — not restarting.")
            break

        if rc == 0 and frozen_kills == 0:
            # Clean exit — user pressed Quit in the UI or closed the tray.
            log.info("Target exited with code 0 — treating as intentional quit.")
            _STATUS.stopping = True
            break

        # Non-zero exit, or we killed it — schedule a restart.
        reason = (
            f"exited with code {rc}"
            if frozen_kills == 0
            else f"force-killed after heartbeat timeout (code {rc})"
        )
        if not _STATUS.last_crash_reason:
            # Only set if not already set by the heartbeat-kill path above.
            _STATUS.record_restart(reason)
        log.warning("Target %s — scheduling restart.", reason)

    log.info("Guardian loop finished. Total restarts: %d.", _STATUS.restart_count)


# =============================================================================
# GUARDIAN ENTRY POINT
# =============================================================================

def _setup_guardian_logging(log_dir: Path) -> None:
    log_file = log_dir / "guardian.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-7s  [%(threadName)s]  %(message)s",
        encoding="utf-8",
    )
    # Mirror to stderr as well (useful when run manually).
    _sh = logging.StreamHandler(sys.stderr)
    _sh.setLevel(logging.INFO)
    _sh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))
    logging.getLogger().addHandler(_sh)


def run_guardian(target: str, log_dir: Path) -> None:
    """
    Full guardian main — sets up logging, IPC, status server, then supervises.
    Called from guardian_main() or directly from hydracast.py.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    _setup_guardian_logging(log_dir)

    log.info(
        "HydraCast Guardian v%s starting. Target: %s  PID: %d",
        GUARDIAN_VERSION, target, os.getpid(),
    )

    # Write our own PID so the main app can check if we're alive.
    own_pid_path = log_dir / "guardian_self.pid"
    try:
        own_pid_path.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    # ── Signal handling ────────────────────────────────────────────────────────
    def _on_signal(sig, _frame):
        log.info("Guardian received signal %s — initiating shutdown.", sig)
        _STATUS.stopping = True

    signal.signal(signal.SIGTERM, _on_signal)
    if not IS_WIN:
        signal.signal(signal.SIGHUP, _on_signal)
    try:
        signal.signal(signal.SIGINT, _on_signal)
    except Exception:
        pass

    # ── Start IPC services ────────────────────────────────────────────────────
    _start_heartbeat_listener()
    _start_status_server()

    # ── Run the supervisor ────────────────────────────────────────────────────
    try:
        guardian_loop(target, log_dir)
    except Exception as exc:
        log.exception("Guardian loop raised unexpected exception: %s", exc)
        _STATUS.append_crash_log(f"GUARDIAN INTERNAL ERROR: {exc}")

    # Cleanup
    try:
        own_pid_path.unlink(missing_ok=True)
    except Exception:
        pass
    log.info("Guardian exiting.")


def guardian_main() -> None:
    """
    Entry point when watchdog.py / hydracast_guardian.exe is run directly.

        hydracast_guardian.exe --target hydracast.exe --log-dir logs
    """
    parser = argparse.ArgumentParser(
        prog="hydracast_guardian",
        description="HydraCast Guardian Watchdog — supervises the main process.",
    )
    parser.add_argument(
        "--target", "-t",
        default="hydracast.exe" if IS_WIN else "python hydracast.py",
        help="Command to launch and supervise (default: hydracast.exe).",
    )
    parser.add_argument(
        "--log-dir", "-l",
        default="logs",
        help="Directory for guardian.log (default: logs/).",
    )
    parser.add_argument(
        "--guardian", action="store_true",
        help="Alias for compatibility — always implied.",
    )
    args = parser.parse_args()
    run_guardian(args.target, Path(args.log_dir).resolve())


# =============================================================================
# HEARTBEAT SENDER  (runs inside the MAIN PROCESS)
# =============================================================================

class HeartbeatSender:
    """
    Lightweight UDP heartbeat sender.  One instance lives in the main HC process.

    Usage (in hydracast.py):

        from hc.watchdog import HeartbeatSender
        _hb = HeartbeatSender()
        _hb.start()          # daemon thread; stops automatically on process exit
        ...
        _hb.stop()           # call before sys.exit() for a clean shutdown
    """

    _PAYLOAD = b"HC-ALIVE"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = HEARTBEAT_PORT,
        interval: float = HEARTBEAT_INTERVAL,
    ) -> None:
        self._host     = host
        self._port     = port
        self._interval = interval
        self._stop_ev  = threading.Event()
        self._t: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> None:
        """Start the background heartbeat thread."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as exc:
            log.warning("HeartbeatSender: could not create socket — %s", exc)
            return
        self._stop_ev.clear()
        self._t = threading.Thread(
            target=self._loop, daemon=True, name="hc-heartbeat-tx"
        )
        self._t.start()
        log.debug("Heartbeat sender started → %s:%d every %.0fs",
                  self._host, self._port, self._interval)

    def stop(self) -> None:
        """Signal the heartbeat thread to stop."""
        self._stop_ev.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def _loop(self) -> None:
        while not self._stop_ev.is_set():
            self._send()
            self._stop_ev.wait(self._interval)

    def _send(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.sendto(self._PAYLOAD, (self._host, self._port))
        except Exception:
            pass   # guardian may not be running; that's fine


# =============================================================================
# GUARDIAN STATUS CLIENT  (called from web_handler.py to merge into /api/status)
# =============================================================================

def fetch_guardian_status(timeout: float = 0.5) -> Optional[dict]:
    """
    Fetch the guardian JSON status from the local status HTTP endpoint.
    Returns None if the guardian is not running or the request fails.
    Call this from the WebHandler (e.g. in _get_system_stats) and merge
    the result into the response dict so the Web UI can render a Guardian card.

    Example (in web_handler.py _get_system_stats):

        from hc.watchdog import fetch_guardian_status
        guardian = fetch_guardian_status()
        payload["guardian"] = guardian or {"guardian_version": None}
    """
    import urllib.request
    url = f"http://127.0.0.1:{STATUS_PORT}/guardian/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


# =============================================================================
# GUARDIAN LAUNCHER  (called from hydracast.py to spawn the guardian process)
# =============================================================================

def launch_guardian(
    target_cmd: str,
    log_dir: Path,
    *,
    guardian_exe: Optional[str] = None,
) -> Optional[subprocess.Popen]:
    """
    Spawn the guardian as a completely independent (detached) process.

    hydracast.py calls this at startup BEFORE starting its own worker thread.
    The guardian then restarts hydracast.exe if it crashes.  If the guardian
    is already running (guardian_self.pid exists and the process is alive)
    this is a no-op.

    FIX (Bug #6): Process-name verification added.  pid_exists() alone is not
    sufficient on Windows because PIDs are recycled.  We now also check the
    process name to make sure the PID actually belongs to the guardian and not
    to some unrelated process that reused the number.

    Parameters
    ──────────
    target_cmd   : the command the guardian should supervise, e.g.
                   "hydracast.exe" or '"C:\\Program Files\\HC\\hydracast.exe"'
    log_dir      : Path to the logs/ directory
    guardian_exe : override guardian executable path (optional)

    Returns the Popen handle (detached — don't call wait() on it) or None.
    """
    # ── Check if a guardian is already alive ──────────────────────────────────
    self_pid_path = log_dir / "guardian_self.pid"
    if self_pid_path.exists():
        try:
            existing_pid = int(self_pid_path.read_text().strip())
            import psutil as _psutil
            if _psutil.pid_exists(existing_pid):
                try:
                    p = _psutil.Process(existing_pid)
                    # FIX (Bug #6): verify the process name, not just the PID.
                    pname = p.name().lower()
                    if "guardian" in pname or "python" in pname:
                        log.info(
                            "Guardian already running (PID %d, name=%s) — skipping launch.",
                            existing_pid, p.name(),
                        )
                        return None
                    # PID exists but belongs to a different program — stale file.
                    log.info(
                        "PID %d exists but is '%s', not the guardian — relaunching.",
                        existing_pid, p.name(),
                    )
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    pass  # process gone between pid_exists and Process() — relaunch
        except Exception:
            pass   # stale or malformed PID file — continue with launch

    # ── Build the guardian command ────────────────────────────────────────────
    if guardian_exe:
        cmd = [guardian_exe]
    elif getattr(sys, "frozen", False):
        # Frozen: look for hydracast_guardian.exe beside the current .exe
        exe_dir = Path(sys.executable).parent
        g_exe   = exe_dir / ("hydracast_guardian.exe" if IS_WIN else "hydracast_guardian")
        if g_exe.exists():
            cmd = [str(g_exe)]
        else:
            # Fall back: run the bundled watchdog module via the main exe
            # (requires hydracast.exe to handle --guardian-mode).
            cmd = [sys.executable, "--guardian-mode"]
    else:
        # Source run: python -m hc.watchdog
        cmd = [sys.executable, "-m", "hc.watchdog"]

    cmd += ["--target", target_cmd, "--log-dir", str(log_dir)]

    log.info("Launching guardian process: %s", " ".join(cmd))

    kw: dict = dict(
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    if IS_WIN:
        # Fully detached — survives the parent exiting.
        DETACHED_PROCESS         = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kw["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kw["close_fds"]     = True
    else:
        kw["start_new_session"] = True   # setsid() equivalent

    try:
        proc = subprocess.Popen(cmd, **kw)
        log.info("Guardian process started with PID %d.", proc.pid)
        return proc
    except Exception as exc:
        log.error("Failed to launch guardian process: %s", exc)
        return None


# =============================================================================
# PLAYLIST WATCHDOG  (in-process, per-stream — legacy API preserved)
# =============================================================================

class PlaylistWatchdog:
    """
    Background thread that warns early about a bad next-queued file.

    One instance per stream; started when the stream goes LIVE and stopped
    when it is stopped/restarted.  Warnings are fed into both the stream log
    and _STATUS.file_warnings so the guardian status endpoint (and thus the
    Web UI) can show them.
    """

    def __init__(self, state: "StreamState", glog: "LogBuffer") -> None:  # type: ignore[name-defined]
        self.state  = state
        self.glog   = glog
        self._stop  = threading.Event()
        self._t: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the watchdog background thread."""
        self._stop.clear()
        self._t = threading.Thread(
            target=self._loop, daemon=True,
            name=f"playlist-wd-{self.state.config.port}",
        )
        self._t.start()

    def stop(self) -> None:
        """Signal the watchdog thread to stop."""
        self._stop.set()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "INFO") -> None:
        full = f"[{self.state.config.name}][WD] {msg}"
        self.state.log_add(full)
        self.glog.add(full, level)
        if level in ("ERROR", "WARN"):
            # Also surface in the guardian status so Web UI sees it.
            existing = _STATUS.file_warnings.get(self.state.config.name, [])
            ts = datetime.now().strftime("%H:%M:%S")
            updated = (existing + [f"[{ts}] {msg}"])[-10:]  # keep last 10
            _STATUS.set_file_warning(self.state.config.name, updated)

    def _next_playlist_item(self) -> "Optional[PlaylistItem]":  # type: ignore[name-defined]
        """Return the PlaylistItem *after* the current one, or None."""
        pl    = self.state.config.playlist
        order = self.state.playlist_order
        idx   = self.state.playlist_index

        if len(pl) <= 1 or not order:
            return None

        next_pos = (idx + 1) % len(order)
        try:
            return pl[order[next_pos]]
        except IndexError:
            return None

    def _loop(self) -> None:
        # Clear any stale file warnings from a previous run.
        _STATUS.clear_file_warnings(self.state.config.name)

        while not self._stop.is_set():
            try:
                from hc.models import StreamStatus as _SS
                if self.state.status == _SS.LIVE:
                    item = self._next_playlist_item()
                    if item is not None:
                        ok = _check_file(item.file_path, self._log)
                        if ok:
                            _STATUS.clear_file_warnings(self.state.config.name)
            except Exception as exc:
                log.debug("PlaylistWatchdog loop error: %s", exc)

            # Interruptible sleep.
            for _ in range(int(CHECK_INTERVAL * 10)):
                if self._stop.is_set():
                    return
                time.sleep(0.1)


# =============================================================================
# SHARED FILE CHECKER
# =============================================================================

def _check_file(path: "Path", log_fn) -> bool:  # type: ignore[name-defined]
    """
    Return True if *path* is a valid, non-empty media file.
    Calls *log_fn* with an ERROR message if not.
    """
    if not path.exists():
        log_fn(f"Next queued file MISSING: '{path.name}'", "ERROR")
        return False
    try:
        size = path.stat().st_size
    except OSError as exc:
        log_fn(f"Next queued file unreadable: '{path.name}' — {exc}", "ERROR")
        return False
    if size < MIN_FILE_BYTES:
        log_fn(
            f"Next queued file too small ({size} B, likely corrupt): '{path.name}'",
            "ERROR",
        )
        return False
    return True


# =============================================================================
# SKIP-BAD-FILES HELPER  (called from worker._monitor when advancing playlist)
# =============================================================================

def find_next_valid_item(
    state: "StreamState",  # type: ignore[name-defined]
    log_fn,
) -> "Optional[PlaylistItem]":  # type: ignore[name-defined]
    """
    Starting from the item *after* the current playlist_index, walk forward
    until a valid file is found (up to one full loop of the playlist).

    Advances ``state.playlist_index`` in-place and returns the valid
    ``PlaylistItem``, or ``None`` if the entire playlist is unusable.
    """
    pl    = state.config.playlist
    order = state.playlist_order
    n     = len(order)

    if n == 0:
        return None

    for attempt in range(n):
        state.playlist_index = (state.playlist_index + 1) % n
        try:
            item = pl[order[state.playlist_index]]
        except IndexError:
            continue
        if _check_file(item.file_path, log_fn):
            return item
        log_fn(
            f"Skipping bad file [{attempt + 1}/{n}]: '{item.file_path.name}'",
            "WARN",
        )

    log_fn("All playlist files are missing or corrupt — cannot advance.", "ERROR")
    return None


# =============================================================================
# MODULE ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    guardian_main()
