#!/usr/bin/env python3
# =============================================================================
#
#  ██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗  ██████╗ █████╗ ███████╗████████╗
#  ██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝
#  ███████║ ╚████╔╝ ██║  ██║██████╔╝███████║██║     ███████║███████╗   ██║
#  ██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║██║     ██╔══██║╚════██║   ██║
#  ██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║╚██████╗██║  ██║███████║   ██║
#  ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝
#
#  HydraCast  —  Multi-Stream RTSP Weekly Scheduler  v5.4.0
#  Author  : rhshourav
#  GitHub  : https://github.com/rhshourav/HydraCast
#
#  Architecture (unified TUI + tray, no CLI flags needed)
#  ───────────────────────────────────────────────────────
#  Main thread   : pystray icon loop  (Windows requires tray on the main thread)
#  Worker thread : HydraCast TUI core (streams, web server, scheduler)
#  Heartbeat     : UDP ping to guardian every 10 s (daemon thread)
#
#  Behaviour
#  ─────────
#  Launch     → TUI console opens immediately AND tray icon is always visible.
#  Close / minimize console window → console hides; tray icon stays.
#  Right-click tray → menu with "Show TUI", web links, restart, quit.
#  "Show TUI" → console reappears exactly where it was.
#  "Quit HydraCast" → clean shutdown of streams + guardian.
#
#  No CLI flags are needed or exposed to users.  The guardian is a SEPARATE
#  exe (hydracast_guardian.exe) built from hydracast_guardian.py, unchanged.
# =============================================================================

import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ── Logging: write to daily-rotating CSV before anything else ─────────────────
import csv as _csv
import datetime as _datetime
from logging.handlers import BaseRotatingHandler


class _DailyCSVHandler(BaseRotatingHandler):
    """Rotating CSV log handler — one file per calendar day."""

    CSV_HEADER = ["timestamp", "level", "thread", "message"]

    def __init__(self, log_dir: Path, encoding: str = "utf-8"):
        self.log_dir = log_dir
        self._current_date: str = ""
        filename = self._filename_for_today()
        super().__init__(str(filename), mode="a", encoding=encoding, delay=False)
        self._write_header_if_empty()

    def _filename_for_today(self) -> Path:
        today = _datetime.date.today().isoformat()
        self._current_date = today
        return self.log_dir / f"hydracast_{today}.csv"

    def _write_header_if_empty(self) -> None:
        try:
            if self.stream and self.stream.tell() == 0:
                _csv.writer(self.stream).writerow(self.CSV_HEADER)
                self.stream.flush()
        except Exception:
            pass

    def shouldRollover(self, record) -> bool:
        return _datetime.date.today().isoformat() != self._current_date

    def doRollover(self) -> None:
        if self.stream:
            try:
                self.stream.flush()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.baseFilename = str(self._filename_for_today())
        self.stream = self._open()
        self._write_header_if_empty()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.shouldRollover(record):
                self.doRollover()
            ts = _datetime.datetime.fromtimestamp(record.created).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
            _csv.writer(self.stream).writerow(
                [ts, record.levelname, record.threadName, self.format(record)]
            )
            self.stream.flush()
        except Exception:
            self.handleError(record)


def _setup_logging(base: Path) -> Path:
    """Set up CSV logging; returns the log directory used."""
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(Path(appdata) / "HydraCast" / "logs")
    candidates.append(base / "logs")

    log_dir: Path | None = None
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            tp = c / ".write_test"
            tp.touch()
            tp.unlink()
            log_dir = c
            break
        except Exception:
            continue

    if log_dir is None:
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "HydraCast"
        log_dir.mkdir(parents=True, exist_ok=True)

    handler = _DailyCSVHandler(log_dir)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    return log_dir


log = logging.getLogger("hydracast")


# ── Python version guard ───────────────────────────────────────────────────────
if sys.version_info < (3, 8):
    sys.exit("HydraCast requires Python 3.8 or newer.")


# ── Bootstrap: install runtime deps when running from source ──────────────────
def _bootstrap() -> None:
    # PyInstaller bundles all deps — skip pip entirely to avoid os.execv loops.
    if getattr(sys, "frozen", False):
        return

    import importlib.util as _ilu

    needed = {
        "rich":     "rich>=13.0",
        "psutil":   "psutil>=5.9",
        "holidays": "holidays>=0.45",
        "pystray":  "pystray>=0.19",
        "PIL":      "Pillow>=9.0",
    }

    def _ok(mod: str) -> bool:
        try:
            return _ilu.find_spec(mod) is not None
        except (ModuleNotFoundError, ValueError):
            return False

    missing = [pkg for mod, pkg in needed.items() if not _ok(mod)]
    if not missing:
        return
    import subprocess
    print(f"[HydraCast] Installing: {', '.join(missing)} …")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", *missing, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("[HydraCast] Done. Restarting …\n")
    os.execv(sys.executable, [sys.executable] + sys.argv)


_bootstrap()

# ── hc package ────────────────────────────────────────────────────────────────
import subprocess

def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


_HERE = _exe_dir()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from hc.constants import (
    APP_NAME, APP_VER,
    CC, CD, CG, CR, CY,
    IS_WIN,
    CONFIG_DIR, CONFIGS_DIR, LOGS_DIR,
    set_base_dir, set_ffmpeg, set_ffprobe,
    set_no_firewall, set_listen_addr, set_web_port,
    get_web_port, WEB_PORT,
)

if getattr(sys, "frozen", False):
    set_base_dir(Path(sys.executable))
else:
    set_base_dir(Path(__file__))

from hc import web as _web_module
from hc.hc_system import assert_licensed, start_checker   # [LG]
from hc.watchdog import launch_guardian, HeartbeatSender


# =============================================================================
# WORKER TIMEOUT
# =============================================================================

WORKER_TIMEOUT = 30.0   # seconds to wait for the worker to signal ready


# =============================================================================
# CONSOLE WINDOW HELPERS  (Windows only)
# =============================================================================

def _get_console_hwnd() -> int:
    try:
        import ctypes
        return ctypes.windll.kernel32.GetConsoleWindow()
    except Exception:
        return 0


def _show_console(visible: bool) -> None:
    """SW_SHOW = 5, SW_HIDE = 0."""
    try:
        import ctypes
        hwnd = _get_console_hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5 if visible else 0)
    except Exception:
        pass


def _set_console_title(title: str) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def _install_close_hook(callback) -> None:
    """
    Hook the console ✕ button so it calls callback() instead of killing
    the process.  SetConsoleCtrlHandler intercepts CTRL_CLOSE_EVENT (2).
    Returning True from the handler suppresses the default termination.
    We must return within ~5 s or Windows force-kills us anyway —
    callback() must be fast (just set an event / hide window).
    """
    if not IS_WIN:
        return
    try:
        import ctypes

        CTRL_CLOSE_EVENT = 2

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
        def _handler(ctrl_type: int) -> bool:
            if ctrl_type == CTRL_CLOSE_EVENT:
                callback()
                # Block until the tray is actually showing so the process
                # doesn't exit before pystray has taken over.
                time.sleep(0.5)
                return True
            return False

        # Keep a reference so GC doesn't collect the ctypes function pointer.
        _install_close_hook._ref = _handler
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_handler, True)
    except Exception as exc:
        log.warning("Could not install console close hook: %s", exc)


# =============================================================================
# ICON LOADER
# =============================================================================

def _load_tray_image():
    from PIL import Image
    candidates = [
        _HERE / "resources" / "HydraCast.ico",
        _HERE / "_internal" / "resources" / "HydraCast.ico",
        _HERE / "resources" / "logo.png",
        _HERE / "_internal" / "resources" / "logo.png",
    ]
    for p in candidates:
        if p.exists():
            try:
                return Image.open(p).convert("RGBA")
            except Exception:
                pass
    # Fallback: simple green circle
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(img).ellipse([4, 4, 60, 60], fill=(34, 197, 94, 255))
    return img


# =============================================================================
# ERROR POPUP
# =============================================================================

def _show_error(title: str, msg: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
    except Exception:
        pass


# =============================================================================
# UAC ELEVATION
# =============================================================================

def _request_admin_if_needed() -> bool:
    """
    Returns True  → already admin or non-Windows; continue.
    Returns False → elevated copy was spawned; caller must sys.exit(0).

    Only called ONCE per process on first launch.  Guardian restarts inherit
    the elevated token so IsUserAnAdmin() returns True immediately —
    no UAC prompt loop.
    """
    if not IS_WIN:
        return True
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return True
    except Exception:
        return True

    try:
        import ctypes
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        if ret > 32:
            return False
    except Exception:
        pass
    return True   # elevation declined — continue without it


# =============================================================================
# STARTUP REGISTRY  (HKCU — no admin needed at runtime)
# =============================================================================

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_startup_enabled() -> bool:
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(k, APP_NAME)
        winreg.CloseKey(k)
        return True
    except Exception:
        return False


def _set_startup_enabled(enabled: bool) -> None:
    try:
        import winreg
        target = str(Path(sys.executable)) if getattr(sys, "frozen", False) \
                 else str(Path(__file__).resolve())
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{target}"')
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(k)
    except Exception as exc:
        log.warning("startup registry update failed: %s", exc)


# =============================================================================
# WORKER STATE  (shared between tray main-thread and worker thread)
# =============================================================================

class _WorkerState:
    def __init__(self):
        self.ready_event    = threading.Event()  # set when web server responds
        self.shutdown_event = threading.Event()  # set to begin full shutdown
        self.restart_event  = threading.Event()  # set to hot-restart worker
        self.show_tui_event = threading.Event()  # set to restore console
        self.port: int      = WEB_PORT
        self.scheme: str    = "http"
        self.fatal: bool    = False
        self.restart_count: int = 0


# =============================================================================
# SIGNAL PATCH  (suppress signal.signal() calls from inside the worker thread;
# only the main thread is allowed to register OS signals on Windows)
# =============================================================================

import signal as _signal_mod
_REAL_SIGNAL = _signal_mod.signal


def _noop_signal(signum, handler):
    log.debug("signal.signal(%s, …) suppressed in worker thread.", signum)


def _patch_signal():
    _signal_mod.signal = _noop_signal


def _unpatch_signal():
    _signal_mod.signal = _REAL_SIGNAL


# =============================================================================
# HYDRACAST CORE WORKER
# Runs the full hydracast.main() inside a thread, with two patches:
#   1. run_tui_loop → headless wrapper that respects shutdown/restart events.
#   2. WebServer.start → hooked to capture the real port+scheme and signal ready.
# =============================================================================

def _run_hydracast_once(state: _WorkerState) -> bool:
    """
    Run the HydraCast core once — directly, without re-entering main().

    Calls hc.manager and hc.tui directly so the full launcher path
    (UAC elevation, guardian spawn, heartbeat setup, worker loop) is
    never executed again inside this thread.

    Returns True  → restart is appropriate (crash / non-fatal exception).
    Returns False → do not restart (clean exit, fatal error, or user quit).

    KEY FIX
    ───────
    The previous implementation did:
        import hydracast as _hc_main
        _hc_main.main()
    That re-entered the TOP-LEVEL LAUNCHER which:
      1. Re-ran UAC elevation (spawning a new elevated process)
      2. Called launch_guardian() again (second guardian, which spawns a third…)
      3. Started a second HeartbeatSender
      4. Started another _run_worker_loop thread
      5. … and so on exponentially → hundreds of processes within seconds.

    The fix: import and call only the hc *core* (Manager + run_tui_loop)
    and hook WebServer.__init__ to capture port/scheme and signal ready —
    exactly as before, but without touching hydracast.main().
    """
    _patch_signal()
    try:
        # ── Import core modules ───────────────────────────────────────────────
        # All of these are already in sys.modules from the initial startup;
        # these imports are effectively free lookups.
        import hc.tui as _tui_mod
        from hc.manager import Manager
        from hc.web import WebServer as _WS

        # ── Patch 1: WebServer.start → capture port/scheme, signal ready ─────
        _real_ws_init = _WS.__init__

        def _patched_ws_init(ws_self, *a, **kw):
            _real_ws_init(ws_self, *a, **kw)
            _real_start = ws_self.start

            def _hooked_start():
                result = _real_start()
                try:
                    from hc.constants import get_web_port as _gwp
                    state.port = _gwp()
                except Exception:
                    pass

                _use_ssl = getattr(ws_self, "_use_ssl", False)
                state.scheme = "https" if _use_ssl else "http"
                port   = state.port
                scheme = state.scheme

                # Wait for the server to actually respond before signalling ready.
                import http.client as _hc_lib
                import ssl as _ssl
                deadline  = time.time() + 15.0
                signalled = False
                while time.time() < deadline:
                    if state.shutdown_event.is_set():
                        break
                    try:
                        if _use_ssl:
                            ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
                            ctx.check_hostname = False
                            ctx.verify_mode    = _ssl.CERT_NONE
                            conn = _hc_lib.HTTPSConnection(
                                "127.0.0.1", port, timeout=1.0, context=ctx)
                        else:
                            conn = _hc_lib.HTTPConnection(
                                "127.0.0.1", port, timeout=1.0)
                        conn.request("GET", "/health")
                        resp = conn.getresponse()
                        resp.read()
                        conn.close()
                        log.info("WebServer %s://127.0.0.1:%d HTTP %d — ready.",
                                 scheme, port, resp.status)
                        state.ready_event.set()
                        signalled = True
                        break
                    except Exception:
                        time.sleep(0.15)
                if not signalled:
                    log.warning("WebServer did not respond in 15 s — signalling anyway.")
                    state.ready_event.set()
                return result

            ws_self.start = _hooked_start

        _WS.__init__ = _patched_ws_init

        # ── Patch 2: replace run_tui_loop with a shutdown/restart-aware wrapper ─
        _real_tui = _tui_mod.run_tui_loop

        def _wrapped_tui(*, manager, glog, console, shutdown_event,
                         export_urls_fn, **kw):
            """
            Calls the real run_tui_loop but bridges state.shutdown_event and
            state.restart_event into the inner shutdown_event so the TUI exits
            cleanly when either fires.
            """
            _stop = threading.Event()

            def _watch():
                while not _stop.is_set():
                    if state.shutdown_event.is_set() or state.restart_event.is_set():
                        _stop.set()
                        return
                    time.sleep(0.1)

            threading.Thread(target=_watch, daemon=True,
                             name="hc-tui-watcher").start()

            log.info("TUI loop starting.")
            try:
                _real_tui(manager=manager, glog=glog, console=console,
                          shutdown_event=_stop, export_urls_fn=export_urls_fn,
                          **kw)
            finally:
                _stop.set()
                log.info("TUI loop exited.")
                try:
                    from hc.web_handler import _WEB_MANAGER
                    if _WEB_MANAGER is not None:
                        log.info("Calling manager.shutdown() from TUI finally …")
                        _WEB_MANAGER.shutdown()
                except Exception as exc:
                    log.warning("manager.shutdown() in TUI finally: %s", exc)

        _tui_mod.run_tui_loop = _wrapped_tui

        # ── Run the core ──────────────────────────────────────────────────────
        # Import hc.main (the core entry point, NOT hydracast.main) and run it.
        # hc.main sets up the Manager, web server, and TUI — nothing else.
        try:
            import hc.main as _hc_core
            _hc_core.main()
        finally:
            _tui_mod.run_tui_loop = _real_tui
            _WS.__init__ = _real_ws_init

    except SystemExit as exc:
        code = exc.code
        log.warning("HydraCast core exited with code %s.", code)
        if code in (None, 0):
            return False          # clean user-initiated quit
        log.error("Fatal exit (code=%s) — no restart.", code)
        state.fatal = True
        return False

    except ValueError as exc:
        log.exception("Worker ValueError: %s", exc)
        state.fatal = True
        return False

    except Exception as exc:
        log.exception("Unhandled exception in worker: %s", exc)
        return not state.shutdown_event.is_set()

    finally:
        _unpatch_signal()

    return False


def _run_worker_loop(state: _WorkerState) -> None:
    """Outer restart loop for tray-triggered hot-restarts."""
    while not state.shutdown_event.is_set():
        state.restart_event.clear()
        state.ready_event.clear()

        should_restart = _run_hydracast_once(state)

        if state.fatal or state.shutdown_event.is_set():
            break

        if state.restart_event.is_set():
            log.info("Hot-restart requested from tray.")
            state.restart_count += 1
            state.ready_event.clear()
            time.sleep(1.0)
            continue

        if not should_restart:
            break

    state.ready_event.set()    # unblock anything waiting
    state.shutdown_event.set()
    log.info("Worker loop finished.")


# =============================================================================
# ORPHAN CLEANUP  (kill any surviving mediamtx / ffmpeg children)
# =============================================================================

def _kill_orphans() -> None:
    try:
        import psutil
        me = psutil.Process()
        targets = [
            p for p in me.children(recursive=True)
            if any(n in p.name().lower() for n in ("mediamtx", "ffmpeg"))
        ]
        if not targets:
            return
        for p in targets:
            try:
                p.terminate()
            except Exception:
                pass
        _, alive = psutil.wait_procs(targets, timeout=4)
        for p in alive:
            try:
                p.kill()
            except Exception:
                pass
    except Exception as exc:
        log.warning("_kill_orphans: %s", exc)


# =============================================================================
# TRAY  (runs on the MAIN thread — Windows requirement)
# =============================================================================

def _run_tray(state: _WorkerState, log_dir: Path) -> None:
    """
    Build and run the pystray icon on the main thread.

    The tray icon is ALWAYS visible while HydraCast is running.
    Right-click → menu with: Show TUI, Open Web UI, Restart, Startup toggle,
                              Open Log, Quit.
    """
    try:
        import pystray
        from pystray import MenuItem as Item
    except ImportError:
        log.warning("pystray not available — no system tray; waiting for worker.")
        state.shutdown_event.wait()
        return

    # ── Wait for the worker to be ready before building the full menu ─────────
    log.info("Waiting up to %.0fs for HydraCast worker …", WORKER_TIMEOUT)
    became_ready = state.ready_event.wait(timeout=WORKER_TIMEOUT)

    if state.fatal or (not became_ready and state.shutdown_event.is_set()):
        log.error("Worker failed to start — aborting tray.")
        _show_error(
            "HydraCast — Startup Failed",
            "HydraCast failed to start.\n\nCheck the logs folder for details.",
        )
        return

    port   = state.port
    scheme = state.scheme

    try:
        from hc.utils import _local_ip
        ip = _local_ip()
    except Exception:
        ip = "localhost"

    # ── Menu action callbacks ─────────────────────────────────────────────────

    def _show_tui(icon, item):
        """Make the console window visible again."""
        log.info("Show TUI requested.")
        _show_console(True)

    def _open_web(icon, item):
        url = f"{scheme}://{ip}:{state.port}"
        log.info("Opening %s", url)
        webbrowser.open(url)

    def _restart(icon, item):
        log.info("Hot-restart requested from tray menu.")
        state.restart_event.set()

    def _toggle_startup(icon, item):
        cur = _get_startup_enabled()
        _set_startup_enabled(not cur)
        # Rebuild menu so the checkmark flips immediately.
        icon.menu = _build_menu()
        log.info("Startup toggle: now %s", "ON" if not cur else "OFF")

    def _open_log(icon, item):
        today = _datetime.date.today().isoformat()
        candidates = [
            log_dir / f"hydracast_{today}.csv",
            log_dir / "hydracast.log",
        ]
        for p in candidates:
            if p.exists():
                try:
                    os.startfile(str(p))
                    return
                except Exception:
                    webbrowser.open(p.as_uri())
                    return

    def _open_guardian_log(icon, item):
        candidates = [
            log_dir / "guardian.log",
        ]
        for p in candidates:
            if p.exists():
                try:
                    os.startfile(str(p))
                    return
                except Exception:
                    webbrowser.open(p.as_uri())
                    return

    def _quit(icon, item):
        log.info("Quit requested from tray.")
        state.shutdown_event.set()
        icon.stop()

    def _build_menu():
        su = _get_startup_enabled()
        su_label = "✔  Run at Windows startup" if su else "     Run at Windows startup"
        return pystray.Menu(
            Item(f"Open Web UI  ({scheme}://{ip}:{port})", _open_web, default=True),
            pystray.Menu.SEPARATOR,
            Item("Show TUI",            _show_tui),
            Item("Restart HydraCast",   _restart),
            pystray.Menu.SEPARATOR,
            Item(su_label,              _toggle_startup),
            pystray.Menu.SEPARATOR,
            Item("Open Log",            _open_log),
            Item("Open Guardian Log",   _open_guardian_log),
            pystray.Menu.SEPARATOR,
            Item("Quit HydraCast",      _quit),
        )

    # ── Build icon ────────────────────────────────────────────────────────────
    image = _load_tray_image()
    icon = pystray.Icon(
        "HydraCast",
        image,
        f"HydraCast  {scheme}://{ip}:{port}",
        _build_menu(),
    )

    # ── Watch worker — stop icon when worker exits ────────────────────────────
    def _worker_watcher():
        state.shutdown_event.wait()
        log.info("Shutdown event — stopping tray icon.")
        try:
            icon.stop()
        except Exception:
            pass

    threading.Thread(target=_worker_watcher, daemon=True, name="tray-watcher").start()

    log.info("Starting pystray icon loop (main thread).")
    try:
        icon.run()
    except Exception as exc:
        log.exception("pystray icon.run() raised: %s", exc)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main() -> None:
    # ── Re-entry guard ────────────────────────────────────────────────────────
    # Prevent recursive calls: the worker thread must NEVER call hydracast.main()
    # again (it would re-launch the guardian, re-start heartbeat, re-enter the
    # worker loop, and create hundreds of processes).
    if os.environ.get("_HYDRACAST_RUNNING") == str(os.getpid()):
        raise RuntimeError(
            "hydracast.main() called recursively inside the same process "
            "(pid=%d). The worker thread must call hc core functions directly, "
            "not re-enter the launcher." % os.getpid()
        )
    os.environ["_HYDRACAST_RUNNING"] = str(os.getpid())

    # ── UAC elevation ─────────────────────────────────────────────────────────
    if not _request_admin_if_needed():
        sys.exit(0)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_dir = _setup_logging(_HERE)
    log.info("hydracast starting (frozen=%s, pid=%d).",
             getattr(sys, "frozen", False), os.getpid())

    # ── License check  [LG] ───────────────────────────────────────────────────
    assert_licensed()
    # start_checker runs ONCE here — never inside the worker loop.
    start_checker("hydracast")

    # ── Launch guardian (separate EXE) ────────────────────────────────────────
    try:
        from hc.constants import LOGS_DIR
        guardian_log_dir = LOGS_DIR()
        guardian_log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        guardian_log_dir = log_dir

    try:
        target_cmd = (
            str(Path(sys.executable))
            if getattr(sys, "frozen", False)
            else f"{sys.executable} {Path(__file__).resolve()}"
        )
        gp = launch_guardian(target_cmd, guardian_log_dir)
        if gp is not None:
            log.info("Guardian launched (PID %d).", gp.pid)
        else:
            log.info("Guardian already running or not needed.")
    except Exception as exc:
        log.warning("Guardian launch failed: %s — continuing without supervisor.", exc)

    # ── Heartbeat sender ──────────────────────────────────────────────────────
    heartbeat = HeartbeatSender()
    heartbeat.start()
    log.info("Heartbeat sender started.")

    # ── Shared state ──────────────────────────────────────────────────────────
    state = _WorkerState()

    # ── Open the TUI console immediately ─────────────────────────────────────
    # The TUI lives in its own thread.  The main thread runs the tray.
    # hydracast.main() already opens its own Rich console and blocks in
    # run_tui_loop — we just need to start it and show the window.
    _show_console(True)
    _set_console_title(f"{APP_NAME} v{APP_VER}  —  close or minimize to tray")

    # ── Install console close hook → hide to tray instead of killing ──────────
    def _on_close():
        log.info("Console ✕ clicked — hiding to tray.")
        _show_console(False)

    _install_close_hook(_on_close)

    # ── Worker thread (TUI + streams + web server) ────────────────────────────
    worker = threading.Thread(
        target=_run_worker_loop,
        args=(state,),
        name="hydracast-worker",
        daemon=True,
    )
    worker.start()
    log.info("Worker thread started.")

    # ── Main thread: run pystray (blocking) ───────────────────────────────────
    _run_tray(state, log_dir)

    # ── Clean shutdown ────────────────────────────────────────────────────────
    log.info("Tray exited — signalling shutdown.")
    state.shutdown_event.set()
    heartbeat.stop()

    # Give the worker and its stop-stream daemon threads up to 15 s.
    worker.join(timeout=15)

    # Belt-and-suspenders: kill any surviving mediamtx / ffmpeg processes.
    _kill_orphans()

    log.info("hydracast exiting cleanly.")


if __name__ == "__main__":
    main()
