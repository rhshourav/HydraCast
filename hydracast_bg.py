#!/usr/bin/env python3
"""
hydracast_bg.py  —  Background + system tray entry point for HydraCast.

Architecture (v2)
─────────────────
  Guardian process  : hc/watchdog.py --guardian   (supervises THIS process)
  Main thread       : pystray icon loop            (Windows REQUIRES tray on main thread)
  Worker thread     : HydraCast core               (streams, web server, scheduler)
  Heartbeat thread  : UDP ping to guardian every 10 s (daemon)

The guardian is spawned as a detached process BEFORE this process does anything
else.  If this process crashes, hangs, or exits uncleanly, the guardian
detects it and relaunches it automatically.

Changes vs v1
─────────────
  1.  Guardian integration   — launch_guardian() called at startup so the
                               guardian process owns the restart logic.
  2.  Heartbeat sender       — HeartbeatSender() runs as a daemon thread,
                               pinging the guardian every HEARTBEAT_INTERVAL s.
  3.  Fixed os.execv         — Both restart_process and factory_reset now use
                               subprocess.Popen (DETACHED_PROCESS) + sys.exit(0)
                               instead of os.execv, which is unreliable on
                               frozen Windows .exe files.
  4.  Fixed SystemExit(0)    — No longer sets state.fatal=True; exit code 0
                               from a user-requested quit is respected.
  5.  Fixed restart race     — _restart_worker uses a dedicated restart_event
                               instead of toggling shutdown_event.
  6.  Duplicate start() fix  — watchdog.PlaylistWatchdog.start() was defined
                               twice; now fixed to run start_checker() once.
  7.  get_web_port timing    — port is read after the worker signals ready.
  8.  Console.force_terminal — stdout/stderr redirected before worker starts.
  9.  Tray tooltip/menu      — shows version and port once worker is ready.
 10.  Clean COLLECT in spec  — spec uses collect_submodules for pystray.
 11.  signal.signal patch    — monkey-patched to no-op in worker thread.
"""
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────
WORKER_TIMEOUT = 30.0      # seconds to wait for worker "ready" signal

# ── Logging: always write to a CSV file (no console in bg mode) ──────────────
import csv as _csv
import datetime as _datetime
from logging.handlers import BaseRotatingHandler


class _DailyCSVHandler(BaseRotatingHandler):
    """
    A logging handler that writes structured CSV log entries and rotates to a
    new file each calendar day.

    File naming: hydracast_bg_YYYY-MM-DD.csv
    CSV columns : timestamp, level, thread, message
    """

    CSV_HEADER = ["timestamp", "level", "thread", "message"]

    def __init__(self, log_dir: Path, encoding: str = "utf-8"):
        self.log_dir = log_dir
        self._current_date: str = ""
        # Compute today's filename and open it.
        filename = self._filename_for_today()
        super().__init__(str(filename), mode="a", encoding=encoding, delay=False)
        self._write_header_if_empty()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _filename_for_today(self) -> Path:
        today = _datetime.date.today().isoformat()   # e.g. "2025-06-04"
        self._current_date = today
        return self.log_dir / f"hydracast_bg_{today}.csv"

    def _write_header_if_empty(self) -> None:
        """Write the CSV header row when the file is brand-new (zero bytes)."""
        try:
            if self.stream and self.stream.tell() == 0:
                writer = _csv.writer(self.stream)
                writer.writerow(self.CSV_HEADER)
                self.stream.flush()
        except Exception:
            pass

    # ── Rotation logic ────────────────────────────────────────────────────────

    def shouldRollover(self, record) -> bool:  # type: ignore[override]
        """Roll over when the calendar date has changed."""
        return _datetime.date.today().isoformat() != self._current_date

    def doRollover(self) -> None:
        """Close the current file and open a fresh one for the new day."""
        if self.stream:
            try:
                self.stream.flush()
                self.stream.close()
            except Exception:
                pass
            self.stream = None  # type: ignore[assignment]

        new_path = self._filename_for_today()
        self.baseFilename = str(new_path)
        self.stream = self._open()
        self._write_header_if_empty()

    # ── Emit ─────────────────────────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        """Format the record as a CSV row and write it."""
        try:
            if self.shouldRollover(record):
                self.doRollover()
            timestamp = _datetime.datetime.fromtimestamp(record.created).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]   # trim to milliseconds
            row = [
                timestamp,
                record.levelname,
                record.threadName,
                self.format(record),
            ]
            writer = _csv.writer(self.stream)
            writer.writerow(row)
            self.stream.flush()
        except Exception:
            self.handleError(record)


def _setup_logging(base: Path) -> None:
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(Path(appdata) / "HydraCast" / "logs")
    candidates.append(base / "logs")

    log_dir = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.touch()
            test_file.unlink()
            log_dir = candidate
            break
        except Exception:
            continue

    if log_dir is None:
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "HydraCast"
        log_dir.mkdir(parents=True, exist_ok=True)

    # ── Attach the daily-rotating CSV handler ─────────────────────────────────
    csv_handler = _DailyCSVHandler(log_dir, encoding="utf-8")
    # Use a plain message format; timestamp/level/thread are separate CSV columns.
    csv_handler.setFormatter(logging.Formatter("%(message)s"))
    csv_handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(csv_handler)

    # ── Redirect stdout / stderr to today's CSV file ──────────────────────────
    try:
        today = _datetime.date.today().isoformat()
        log_file = log_dir / f"hydracast_bg_{today}.csv"
        _fh = open(log_file, "a", encoding="utf-8", errors="replace")
        sys.stdout = _fh
        sys.stderr = _fh
    except Exception:
        pass

log = logging.getLogger("hydracast_bg")


# ── Base-dir helpers ──────────────────────────────────────────────────────────
def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def _setup_base_dir() -> None:
    from hc.constants import set_base_dir
    if getattr(sys, "frozen", False):
        set_base_dir(Path(sys.executable))
    else:
        set_base_dir(Path(__file__).resolve())


# ── Icon resolution ───────────────────────────────────────────────────────────
def _icon_path() -> Path:
    base = _exe_dir()
    candidates = [
        base / "resources" / "HydraCast.ico",
        base / "_internal" / "resources" / "HydraCast.ico",
        base / "resources" / "logo.png",
        base / "_internal" / "resources" / "logo.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _load_image():
    """Return a PIL Image suitable for the system tray, with fallback."""
    from PIL import Image
    path = _icon_path()
    if path.exists():
        try:
            img = Image.open(path)
            return img.convert("RGBA")
        except Exception as exc:
            log.warning("Could not open icon %s: %s — using fallback", path, exc)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(34, 197, 94, 255))
    return img


# ── Native error popup ────────────────────────────────────────────────────────
def _show_error_box(title: str, message: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass


# ── UAC elevation ─────────────────────────────────────────────────────────────
def _request_admin_if_needed() -> bool:
    try:
        import ctypes
        is_admin: bool = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return True

    if is_admin:
        return True

    log.info("Not running as administrator — requesting UAC elevation.")
    try:
        import ctypes
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1,
        )
        if ret > 32:
            log.info("Elevated process launched (ShellExecute ret=%d) — exiting.", ret)
            return False
        log.warning(
            "UAC elevation failed or declined (ret=%d) — continuing without admin.", ret
        )
    except Exception as exc:
        log.warning("Could not request UAC elevation: %s — continuing.", exc)

    return True


# ── signal.signal patch ───────────────────────────────────────────────────────
import signal as _signal_mod

_REAL_SIGNAL = _signal_mod.signal


def _noop_signal(signum, handler):
    log.debug("signal.signal(%s, ...) suppressed in worker thread.", signum)


def _patch_signal_for_thread() -> None:
    _signal_mod.signal = _noop_signal


def _unpatch_signal() -> None:
    _signal_mod.signal = _REAL_SIGNAL


# ── Detached process restart helper ──────────────────────────────────────────
def _spawn_detached_and_exit() -> None:
    """
    Spawn a fresh detached copy of this process and exit the current one.
    Correct on Windows with a frozen .exe (os.execv is NOT reliable here).
    """
    import subprocess as _sp
    kw: dict = {}
    if sys.platform == "win32":
        DETACHED_PROCESS         = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kw["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kw["close_fds"]     = True
    else:
        kw["start_new_session"] = True
    _sp.Popen(
        [sys.executable] + sys.argv,
        stdout=_sp.DEVNULL,
        stderr=_sp.DEVNULL,
        stdin=_sp.DEVNULL,
        **kw,
    )
    sys.exit(0)


# ── Worker state ───────────────────────────────────────────────────────────────
class _WorkerState:
    """Shared state between the tray (main thread) and the worker thread."""
    def __init__(self):
        self.ready_event    = threading.Event()
        self.shutdown_event = threading.Event()
        # Separate event for tray-triggered worker restart (not a full quit).
        self.restart_event  = threading.Event()
        self.port: int      = 8080
        self.restart_count: int = 0
        # True only for a genuine licence/fatal error; clean exits leave it False.
        self.fatal: bool    = False


# ── HydraCast worker ──────────────────────────────────────────────────────────

def _run_hydracast_once(state: _WorkerState) -> bool:
    """
    Run the HydraCast core once.

    Returns True  → should be restarted (crash / non-fatal error).
    Returns False → clean exit or fatal error; do not restart automatically.

    Background-mode TUI strategy
    ─────────────────────────────
    The original stub replaced run_tui_loop with a bare sleep loop.  That broke
    everything: the real run_tui_loop is not just a display loop — it owns the
    StreamManager lifecycle (start_all on launch, scheduler ticks, compliance
    checks, auto-restart signals).  Replacing it meant streams were never
    started, monitored, or recovered from errors.

    Fix: inject a *headless-safe* wrapper that calls the REAL run_tui_loop with
    a Rich Console whose output is directed to a null sink (force_terminal=True,
    no_color=True).  KeyboardHandler gets no input in bg mode (no TTY attached)
    so its readline thread simply blocks harmlessly; the shutdown_event drives
    the clean exit as usual.  The restart_event is forwarded via a combined
    stop-event so the TUI loop exits promptly on tray-menu restart requests.
    """
    _patch_signal_for_thread()
    try:
        import hc.tui as _tui_mod

        _real_run_tui_loop = _tui_mod.run_tui_loop

        def _headless_tui_loop(
            *,
            manager,
            glog,
            console,
            shutdown_event: threading.Event,
            export_urls_fn,
            **kw,
        ) -> None:
            """
            Drop-in replacement for run_tui_loop in background mode.

            Runs the REAL TUI loop (which manages streams, scheduler, compliance,
            auto-restart, etc.) but feeds it a headless Rich Console so Rich
            never tries to render escape codes to a missing TTY.

            Both shutdown_event and state.restart_event are watched; either one
            causes the loop to exit cleanly.
            """
            import io
            from rich.console import Console as _Console

            # Null-sink console: Rich renders to a StringIO and discards output.
            # force_terminal=True prevents Rich from disabling colour/markup
            # detection which would raise errors on some Rich widgets.
            # no_color=True prevents ANSI escape sequences polluting the log.
            _sink = io.StringIO()
            _headless_console = _Console(
                file=_sink,
                force_terminal=True,
                no_color=True,
                highlight=False,
                markup=False,
                width=120,
            )

            # Combined stop-event: fires when either full-shutdown OR tray-
            # triggered restart is requested, so the TUI loop exits promptly
            # in both cases.
            _combined_stop = threading.Event()

            def _watch_combined() -> None:
                while not _combined_stop.is_set():
                    if shutdown_event.is_set() or state.restart_event.is_set():
                        _combined_stop.set()
                        return
                    time.sleep(0.1)

            _watcher = threading.Thread(
                target=_watch_combined, daemon=True, name="bg-tui-watcher"
            )
            _watcher.start()

            log.info("BG-mode TUI loop starting (real run_tui_loop, headless console).")
            try:
                _real_run_tui_loop(
                    manager=manager,
                    glog=glog,
                    console=_headless_console,
                    shutdown_event=_combined_stop,
                    export_urls_fn=export_urls_fn,
                    **kw,
                )
            finally:
                _combined_stop.set()   # unblock the watcher thread
                log.info("BG-mode TUI loop exited.")
                # Explicit manager stop: manager.shutdown() calls stop_all()
                # synchronously (up to 12 s wait).  This gives each worker's
                # _kill_ffmpeg + _kill_mediamtx a chance to run in the calling
                # thread context before the process exits, rather than relying
                # on daemon threads that may be reaped prematurely.
                try:
                    from hc.web_handler import _WEB_MANAGER
                    _mgr = _WEB_MANAGER
                    if _mgr is not None:
                        log.info("BG-mode: calling manager.shutdown() …")
                        _mgr.shutdown()
                        log.info("BG-mode: manager.shutdown() complete.")
                except Exception as _exc:
                    log.warning("BG-mode: manager.shutdown() error: %s", _exc)

        _tui_mod.run_tui_loop = _headless_tui_loop

        from hc.web import WebServer as _WS

        _real_init = _WS.__init__

        def _patched_init(ws_self, *a, **kw):
            _real_init(ws_self, *a, **kw)
            _bound_start = ws_self.start

            def _hooked_start():
                result = _bound_start()
                # ── Read the real port AFTER start() has called set_web_port() ──
                # web_server.WebServer.start() now calls set_web_port(real_port)
                # before returning, so get_web_port() is authoritative here.
                try:
                    from hc.constants import get_web_port
                    state.port = get_web_port()
                except Exception:
                    pass

                # ── Read the SSL flag set by WebServer.start() ────────────────
                # ws_self._use_ssl is set by the patched start() in web_server.py.
                # Fall back to False (plain HTTP) if the attribute is absent so
                # older builds don't break.
                _use_ssl    = getattr(ws_self, "_use_ssl", False)
                _probe_port = state.port
                _scheme     = "https" if _use_ssl else "http"

                # ── Wait until the server actually responds to an HTTP request ──
                # WebServer.start() spawns a daemon thread and returns before
                # serve_forever() is fully running.  A bare TCP connect would
                # succeed immediately on an SSL server (the TCP layer opens) but
                # the server then drops the connection waiting for a TLS
                # ClientHello that never comes — so the browser gets
                # ERR_EMPTY_RESPONSE.  Instead we send a real HTTP GET to
                # /api/health (which WebHandler serves in <1 ms) and only signal
                # ready once we receive any HTTP response (any status code counts;
                # a 503 "manager not ready yet" is still proof the socket works).
                import http.client as _http
                import ssl as _ssl_mod
                _deadline  = time.time() + 15.0
                _signalled = False
                while time.time() < _deadline:
                    if state.shutdown_event.is_set():
                        break
                    try:
                        if _use_ssl:
                            _ctx = _ssl_mod.SSLContext(_ssl_mod.PROTOCOL_TLS_CLIENT)
                            _ctx.check_hostname = False
                            _ctx.verify_mode    = _ssl_mod.CERT_NONE
                            conn = _http.HTTPSConnection(
                                "127.0.0.1", _probe_port,
                                timeout=1.0, context=_ctx,
                            )
                        else:
                            conn = _http.HTTPConnection(
                                "127.0.0.1", _probe_port, timeout=1.0
                            )
                        conn.request("GET", "/health")
                        resp = conn.getresponse()
                        resp.read()   # drain so the connection closes cleanly
                        conn.close()
                        log.info(
                            "WebServer %s://127.0.0.1:%d responded HTTP %d — "
                            "signalling ready.", _scheme, _probe_port, resp.status
                        )
                        state.ready_event.set()
                        _signalled = True
                        break
                    except Exception:
                        time.sleep(0.15)
                if not _signalled:
                    log.warning(
                        "WebServer %s://127.0.0.1:%d did not respond within "
                        "15 s — signalling ready anyway.",
                        _scheme, _probe_port,
                    )
                    state.ready_event.set()
                return result

            ws_self.start = _hooked_start

        _WS.__init__ = _patched_init

        # ── Suppress auto-start on first run ──────────────────────────────
        # Streams are started by the user from the Web UI.  Patching
        # StreamManager.start_all() to a no-op prevents the scheduler from
        # launching every enabled stream automatically at boot.
        import hc.manager as _mgr_mod
        _real_start_all = _mgr_mod.StreamManager.start_all

        def _no_autostart(self_mgr):
            log.info("start_all() suppressed — user will start streams from Web UI.")

        _mgr_mod.StreamManager.start_all = _no_autostart

        try:
            import hydracast as _hc
            _hc.main()
        finally:
            # Restore ALL patches so a tray-triggered restart gets
            # a clean re-injection on the next _run_hydracast_once() call.
            _mgr_mod.StreamManager.start_all = _real_start_all
            _WS.__init__ = _real_init
            _tui_mod.run_tui_loop = _real_run_tui_loop

    except SystemExit as exc:
        code = exc.code
        log.warning("HydraCast exited with code %s.", code)
        if code in (None, 0):
            # Clean exit — user quit deliberately.  Do NOT set fatal; let
            # the guardian decide whether to restart.
            return False
        # Non-zero → licence failure or fatal startup error.
        log.error("HydraCast fatal exit (code=%s) — will not restart.", code)
        state.fatal = True
        return False

    except ValueError as exc:
        log.exception("Worker ValueError: %s", exc)
        state.fatal = True
        return False

    except Exception as exc:
        log.exception("HydraCast worker raised unhandled exception: %s", exc)
        return not state.shutdown_event.is_set()

    finally:
        _unpatch_signal()

    return False   # main() returned normally — treat as clean exit


def _run_hydracast_with_restarts(state: _WorkerState) -> None:
    """
    Outer loop: runs _run_hydracast_once() and handles tray-requested restarts.
    The guardian process handles crashes; this loop only handles user-triggered
    restarts from the tray menu (which don't exit the process).
    """
    while not state.shutdown_event.is_set():
        state.restart_event.clear()
        state.ready_event.clear()

        should_restart = _run_hydracast_once(state)

        if state.fatal or state.shutdown_event.is_set():
            break

        if state.restart_event.is_set():
            # Tray "Restart HydraCast" was clicked — loop and restart.
            log.info("Worker restart requested via tray — restarting.")
            state.restart_count += 1
            state.ready_event.clear()
            time.sleep(1.0)
            continue

        if not should_restart:
            break

    # Always signal both events so waiting threads unblock.
    state.ready_event.set()
    state.shutdown_event.set()
    log.info("Worker thread exiting.")


# ── Startup registry helpers (HKCU — no admin needed) ────────────────────────

def _startup_reg_key() -> str:
    return r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_startup_enabled() -> bool:
    """Return True when the HKCU Run entry for HydraCast exists."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _startup_reg_key(), 0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, "HydraCast")
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def _set_startup_enabled(enabled: bool) -> None:
    """Write or remove the HKCU Run entry for HydraCast."""
    try:
        import winreg
        # Determine the bg exe path
        if getattr(sys, "frozen", False):
            exe = Path(sys.executable)
            bg  = exe.with_name("hydracast_bg.exe")
            target = str(bg) if bg.exists() else str(exe)
        else:
            target = str(Path(__file__).resolve())

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _startup_reg_key(),
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            winreg.SetValueEx(key, "HydraCast", 0, winreg.REG_SZ, f'"{target}"')
            log.info("startup: HKCU Run entry added -> %s", target)
        else:
            try:
                winreg.DeleteValue(key, "HydraCast")
                log.info("startup: HKCU Run entry removed")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as exc:
        log.warning("startup: could not update registry — %s", exc)


# ── Tray (main thread) ────────────────────────────────────────────────────────

def _build_and_run_tray(state: _WorkerState) -> None:
    try:
        import pystray
        from pystray import MenuItem as Item
    except ImportError:
        log.warning("pystray not available — running without system tray.")
        state.shutdown_event.wait()
        return

    log.info("Waiting up to %.0fs for HydraCast to start …", WORKER_TIMEOUT)
    became_ready = state.ready_event.wait(timeout=WORKER_TIMEOUT)

    if state.fatal or state.shutdown_event.is_set():
        log.error("Worker did not start successfully — aborting tray.")
        if not became_ready:
            _show_error_box(
                "HydraCast — Startup Failed",
                "HydraCast failed to start within the expected time.\n\n"
                "Please check logs\\hydracast_bg.log for details."
            )
        return

    port = state.port
    log.info("HydraCast ready on port %d — showing tray icon.", port)

    # ── Menu actions ──────────────────────────────────────────────────────────
    def _open_web(icon, item):
        try:
            from hc.utils import _local_ip
            ip = _local_ip()
        except Exception:
            ip = "localhost"
        url = f"https://{ip}:{state.port}"
        log.info("Opening %s", url)
        webbrowser.open(url)

    def _restart_worker(icon, item):
        """Ask the running worker to restart cleanly (no process exit)."""
        log.info("User requested worker restart via tray.")
        state.restart_event.set()

    def _quit(icon, item):
        log.info("Quit requested from tray.")
        state.shutdown_event.set()
        icon.stop()

    def _toggle_startup(icon, item):
        """Toggle the Windows startup entry and refresh the tray menu."""
        current = _get_startup_enabled()
        _set_startup_enabled(not current)
        # Rebuild the menu so the label flips immediately
        icon.menu = _build_menu()
        log.info("startup toggled: now %s", "ON" if not current else "OFF")

    def _build_menu():
        startup_on = _get_startup_enabled()
        startup_label = "✔  Run at Windows startup" if startup_on else "     Run at Windows startup"
        return pystray.Menu(
            Item(f"Open Web UI  (https://{_ip}:{port})", _open_web, default=True),
            pystray.Menu.SEPARATOR,
            Item("Restart HydraCast",   _restart_worker),
            pystray.Menu.SEPARATOR,
            Item(startup_label,         _toggle_startup),
            pystray.Menu.SEPARATOR,
            Item("Open App Log",        _open_log),
            Item("Open Guardian Log",   _open_guardian_log),
            pystray.Menu.SEPARATOR,
            Item("Quit HydraCast",      _quit),
        )

    def _open_log(icon, item):
        import datetime as _dt
        today = _dt.date.today().isoformat()
        csv_name = f"hydracast_bg_{today}.csv"
        appdata = os.environ.get("APPDATA")
        log_path = None
        if appdata:
            candidate = Path(appdata) / "HydraCast" / "logs" / csv_name
            if candidate.exists():
                log_path = candidate
        if log_path is None:
            log_path = _exe_dir() / "logs" / csv_name
        try:
            os.startfile(str(log_path))
        except Exception:
            webbrowser.open(log_path.as_uri())

    def _open_guardian_log(icon, item):
        appdata = os.environ.get("APPDATA")
        log_path = None
        if appdata:
            candidate = Path(appdata) / "HydraCast" / "logs" / "guardian.log"
            if candidate.exists():
                log_path = candidate
        if log_path is None:
            log_path = _exe_dir() / "logs" / "guardian.log"
        try:
            os.startfile(str(log_path))
        except Exception:
            webbrowser.open(log_path.as_uri())

    try:
        from hc.utils import _local_ip
        _ip = _local_ip()
    except Exception:
        _ip = "localhost"

    image = _load_image()
    icon = pystray.Icon(
        "HydraCast", image,
        f"HydraCast  https://{_ip}:{port}  [Guardian Active]",
        _build_menu(),
    )

    def _watch_worker():
        state.shutdown_event.wait()
        log.info("Shutdown event set — stopping tray icon.")
        try:
            icon.stop()
        except Exception:
            pass

    threading.Thread(target=_watch_worker, daemon=True, name="tray-watcher").start()

    log.info("Starting pystray icon loop.")
    try:
        icon.run()
    except Exception as exc:
        log.exception("pystray icon.run() raised: %s", exc)



# ── Orphan-process cleanup ─────────────────────────────────────────────────────

def _force_kill_orphans() -> None:
    """
    Belt-and-suspenders sweep: kill any MediaMTX or FFmpeg processes that are
    still children of the current process after a normal shutdown.

    Why this is needed
    ──────────────────
    manager.stop_all() dispatches one daemon thread per stream (worker.stop()
    → _kill_ffmpeg + _kill_mediamtx).  Those daemon threads are NOT joined
    anywhere.  On a fast or clean exit path Python can reach sys.exit() before
    those threads finish their proc.terminate() + proc.wait() calls, leaving
    both MediaMTX and FFmpeg alive as orphans.

    This function is called from main() AFTER worker.join(timeout=15) so the
    normal stop paths have had their chance first.  The psutil sweep is a
    last resort that is completely safe to run unconditionally.
    """
    try:
        import psutil, signal as _sig, os as _os
        current = psutil.Process()
        children = current.children(recursive=True)
        targets = [
            p for p in children
            if any(
                name in p.name().lower()
                for name in ("mediamtx", "ffmpeg")
            )
        ]
        if not targets:
            log.info("_force_kill_orphans: no surviving mediamtx/ffmpeg children.")
            return
        for p in targets:
            try:
                log.warning(
                    "_force_kill_orphans: terminating %s PID=%d", p.name(), p.pid
                )
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        # Give them 4 s to honour SIGTERM, then SIGKILL anything left.
        _, still_alive = psutil.wait_procs(targets, timeout=4)
        for p in still_alive:
            try:
                log.warning(
                    "_force_kill_orphans: KILL %s PID=%d (did not terminate)",
                    p.name(), p.pid,
                )
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        # psutil not available — fall back to os.kill on the stored PIDs
        # (best-effort; PIDs may have been reused by the OS)
        log.warning("_force_kill_orphans: psutil not available, falling back to pid scan.")
        _force_kill_orphans_fallback()
    except Exception as exc:
        log.warning("_force_kill_orphans error: %s", exc)


def _force_kill_orphans_fallback() -> None:
    """Fallback when psutil is absent: collect PIDs from the web manager."""
    try:
        from hc.web_handler import _WEB_MANAGER
        mgr = _WEB_MANAGER
        if not mgr:
            return
        import os as _os, subprocess as _sp
        for st in mgr.states:
            for proc_attr in ("ffmpeg_proc", "mtx_proc"):
                proc = getattr(st, proc_attr, None)
                if proc is None:
                    continue
                if proc.poll() is not None:
                    continue   # already gone
                try:
                    log.warning(
                        "_force_kill_orphans_fallback: killing %s PID=%d",
                        proc_attr, proc.pid
                    )
                    proc.terminate()
                    proc.wait(timeout=4)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
    except Exception as exc:
        log.warning("_force_kill_orphans_fallback error: %s", exc)

# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    # ── Guardian mode (spawned by launch_guardian) ────────────────────────────
    # When hydracast_bg.exe is called with --guardian-mode it acts as the
    # supervisor rather than the supervised app.  This is the frozen-exe
    # fallback when hydracast_guardian.exe is not present beside the main exe.
    if "--guardian-mode" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--guardian-mode"]
        _here = _exe_dir()
        import tempfile
        log_dir_str = None
        for i, a in enumerate(sys.argv):
            if a == "--log-dir" and i + 1 < len(sys.argv):
                log_dir_str = sys.argv[i + 1]
                break
        log_dir = Path(log_dir_str) if log_dir_str else _here / "logs"
        target_str = None
        for i, a in enumerate(sys.argv):
            if a == "--target" and i + 1 < len(sys.argv):
                target_str = sys.argv[i + 1]
                break
        target = target_str or str(sys.executable)
        from hc.watchdog import run_guardian
        run_guardian(target, log_dir)
        return

    # ── Normal bg mode ────────────────────────────────────────────────────────
    if not _request_admin_if_needed():
        sys.exit(0)

    _here = _exe_dir()
    if str(_here) not in sys.path:
        sys.path.insert(0, str(_here))

    _setup_logging(_here)
    log.info("hydracast_bg starting (frozen=%s, pid=%d).",
             getattr(sys, "frozen", False), os.getpid())

    sys.argv = [a for a in sys.argv if a not in ("--background", "-b")]

    try:
        _setup_base_dir()
    except Exception as exc:
        log.exception("_setup_base_dir failed: %s", exc)
        _show_error_box("HydraCast — Init Error",
                        f"Failed to initialise path constants:\n{exc}")
        return

    # ── Determine log dir for guardian ────────────────────────────────────────
    try:
        from hc.constants import LOGS_DIR
        _log_dir = LOGS_DIR()
    except Exception:
        appdata = os.environ.get("APPDATA")
        _log_dir = (Path(appdata) / "HydraCast" / "logs") if appdata else (_here / "logs")
    _log_dir.mkdir(parents=True, exist_ok=True)

    # ── Launch the Guardian process (supervises THIS process) ─────────────────
    # The guardian is a separate detached process that monitors hydracast_bg
    # via heartbeat UDP pings.  If this process exits with a non-zero code
    # (crash, factory reset, restart request) the guardian relaunches it.
    # If a guardian is already running, launch_guardian() is a no-op.
    try:
        from hc.watchdog import launch_guardian
        if getattr(sys, "frozen", False):
            _target_cmd = sys.executable
        else:
            _target_cmd = f"{sys.executable} {Path(__file__).resolve()}"
        _guardian_proc = launch_guardian(_target_cmd, _log_dir)
        if _guardian_proc is not None:
            log.info("Guardian launched (PID %d) — supervising: %s",
                     _guardian_proc.pid, _target_cmd)
        else:
            log.info("Guardian already running or skipped.")
    except Exception as _exc:
        log.warning("Could not launch guardian: %s — running without supervisor.", _exc)

    # ── Start heartbeat sender (pings the guardian to prove we're alive) ──────
    from hc.watchdog import HeartbeatSender
    _heartbeat = HeartbeatSender()
    _heartbeat.start()
    log.info("Heartbeat sender started.")

    # ── Shared state between tray and worker ─────────────────────────────────
    state = _WorkerState()

    # ── Start HydraCast worker on a background thread ─────────────────────────
    worker = threading.Thread(
        target=_run_hydracast_with_restarts,
        args=(state,),
        name="hydracast-worker",
        daemon=True,
    )
    worker.start()
    log.info("Worker thread started.")

    # ── Run tray on the MAIN thread (Windows requirement) ─────────────────────
    _build_and_run_tray(state)

    # ── Clean shutdown ────────────────────────────────────────────────────────
    log.info("Tray exited — signalling shutdown and waiting for worker …")
    state.shutdown_event.set()
    _heartbeat.stop()
    # Give the worker (and its stop-stream daemon threads) up to 15 s to finish
    # their normal proc.terminate() / proc.wait() cleanup.
    worker.join(timeout=15)
    # Belt-and-suspenders: kill any MediaMTX or FFmpeg processes that are still
    # alive after the normal shutdown path.  daemon stop-threads are not joined
    # so they can outlive the worker join; this sweep ensures they don't.
    _force_kill_orphans()
    log.info("hydracast_bg exiting cleanly.")


if __name__ == "__main__":
    main()
