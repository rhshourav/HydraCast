#!/usr/bin/env python3
"""
hydracast_bg.py  —  Background + system tray entry point for HydraCast.

Architecture
────────────
  Main thread  : pystray icon loop  (Windows REQUIRES tray on main thread)
  Worker thread: HydraCast core     (streams, web server, scheduler)

Robustness fixes vs original
─────────────────────────────
  1. Startup-race guard    — tray watches worker readiness via an Event
                             before declaring itself "running".
  2. Crash-restart         — worker thread auto-restarts up to MAX_RESTARTS
                             times with exponential back-off before giving up.
  3. Early-exit detection  — if HydraCast crashes before pystray even starts
                             we pop a native Windows MessageBox instead of
                             silently vanishing.
  4. sys.exit() swallowed  — assert_licensed / start_checker call sys.exit();
                             worker catches SystemExit and checks the code so
                             a legitimate licence failure is NOT retried.
  5. No double --background— strips the flag so hydracast's argparse never
                             tries to re-launch / daemonize (would call
                             sys.exit() on Windows and kill the tray).
  6. Logging to file        — all errors written to logs/hydracast_bg.log
                             next to the exe so crashes are diagnosable.
  7. get_web_port timing   — port is read after the worker signals ready,
                             not before hc.constants is fully initialised.
  8. Console.force_terminal — hydracast.py creates Console(force_terminal=True)
                             which raises inside a windowless process; we
                             redirect stdout/stderr to the log file before
                             the worker starts.
  9. Tray tooltip / menu    — shows version and port once worker is ready.
 10. Clean COLLECT in spec  — spec now uses collect_submodules for pystray
                             so _win32 backend is never missing.
 11. signal.signal patch    — Python forbids signal.signal() on non-main
                             threads (ValueError).  We monkey-patch the
                             stdlib signal module to a no-op inside the
                             worker thread so hydracast.main() can run
                             without modification.  The main thread still
                             owns real signal handling via the tray quit.
"""
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_RESTARTS   = 5          # max automatic worker restarts
RESTART_DELAY  = 3.0       # base delay (seconds); doubles each retry
WORKER_TIMEOUT = 30.0      # seconds to wait for worker "ready" signal


# ── Logging: always write to a file (no console in bg mode) ──────────────────
def _setup_logging(base: Path) -> None:
    # Program Files is read-only for normal users, so prefer APPDATA first.
    # Fall back to the exe dir only if APPDATA is unavailable (unusual).
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(Path(appdata) / "HydraCast" / "logs")
    candidates.append(base / "logs")   # last resort (needs admin if in Program Files)

    log_dir = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            # Verify we can actually write here before committing.
            test_file = candidate / ".write_test"
            test_file.touch()
            test_file.unlink()
            log_dir = candidate
            break
        except Exception:
            continue

    if log_dir is None:
        # Absolute last resort: temp dir — always writable.
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "HydraCast"
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "hydracast_bg.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-7s  [%(threadName)s]  %(message)s",
        encoding="utf-8",
    )
    # Also redirect bare stdout/stderr so rich Console output goes somewhere.
    try:
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

    # Fallback: green circle on transparent background.
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(34, 197, 94, 255))
    return img


# ── Native error popup (no-console process) ───────────────────────────────────
def _show_error_box(title: str, message: str) -> None:
    """Show a Windows MessageBox so the user knows something went wrong."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        pass   # non-Windows or ctypes missing — already logged


# ── UAC elevation ─────────────────────────────────────────────────────────────
def _request_admin_if_needed() -> bool:
    """
    Re-launch the current process with administrator privileges via UAC if:
      • We are running on Windows, AND
      • The current process is NOT already elevated.

    Returns True  → caller is already admin (or non-Windows): continue normally.
    Returns False → a new elevated process was spawned: the caller should exit.

    Why this is needed
    ──────────────────
    When HydraCast is installed under C:\\Program Files the install directory
    is protected by Windows ACLs.  Creating sub-directories (bin/, config/,
    logs/, media/, ssl/) raises PermissionError: [WinError 5] unless the
    process holds SeBackupPrivilege / admin token.  Binding to ports 80 and
    443 also requires elevation.

    Fallback
    ────────
    If the user clicks "No" on the UAC prompt (ret ≤ 32), this function
    returns True and lets the app continue; constants.py will redirect all
    writable dirs to %%APPDATA%%\\HydraCast as a silent fallback, so the app
    still works — just without the ability to bind privileged ports.
    """
    try:
        import ctypes
        is_admin: bool = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return True   # can't check elevation state — assume OK

    if is_admin:
        return True   # already running as administrator

    log.info("Not running as administrator — requesting UAC elevation.")
    try:
        import ctypes
        # Build the command-line string for the re-launched process.
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "runas",        # verb — triggers UAC prompt
            sys.executable, # file
            params,         # parameters
            None,           # directory (inherit)
            1,              # nShowCmd: SW_SHOWNORMAL
        )
        if ret > 32:
            log.info("Elevated process launched (ShellExecute ret=%d) — exiting current instance.", ret)
            return False    # elevated copy is now running; exit the un-elevated one
        # ret ≤ 32 means the user declined or an error occurred.
        log.warning(
            "UAC elevation failed or was declined (ShellExecute ret=%d). "
            "Continuing without admin rights — writable dirs will fall back to %%APPDATA%%.",
            ret,
        )
    except Exception as exc:
        log.warning("Could not request UAC elevation: %s — continuing without admin.", exc)

    return True   # proceed without elevation


# ── signal.signal patch ───────────────────────────────────────────────────────
# Python raises ValueError("signal only works in main thread") when
# signal.signal() is called from any non-main thread.  hydracast.main()
# always calls signal.signal(SIGINT, ...) and signal.signal(SIGTERM, ...).
# Since the worker runs in a daemon thread we neutralise the stdlib function
# for the duration of the call and restore it afterwards.
#
# The main thread (tray) still has real signal handling via icon.stop() /
# shutdown_event, so nothing is lost.

import signal as _signal_mod

_REAL_SIGNAL = _signal_mod.signal   # save original


def _noop_signal(signum, handler):  # noqa: ANN001
    """Drop-in replacement for signal.signal that does nothing."""
    log.debug("signal.signal(%s, ...) suppressed in worker thread.", signum)


def _patch_signal_for_thread() -> None:
    """Replace signal.signal with a no-op (call from worker thread only)."""
    _signal_mod.signal = _noop_signal


def _unpatch_signal() -> None:
    """Restore the real signal.signal (call after worker is done)."""
    _signal_mod.signal = _REAL_SIGNAL


# ── HydraCast worker ──────────────────────────────────────────────────────────
class _WorkerState:
    """Shared state between the tray (main thread) and the worker thread."""
    def __init__(self):
        self.ready_event    = threading.Event()   # set when HC is running
        self.shutdown_event = threading.Event()   # set to request shutdown
        self.port: int      = 8080                # updated once HC is ready
        self.restart_count: int = 0
        self.fatal: bool    = False               # True → do NOT restart


def _run_hydracast_once(state: _WorkerState) -> bool:
    """
    Run the HydraCast core once.  Returns True if it should be restarted,
    False if shutdown was requested or a fatal/licence error occurred.
    """
    # ── Neutralise signal.signal for this thread ──────────────────────────────
    # Python only allows signal.signal() on the main thread.  hydracast.main()
    # always calls it, so we swap it with a no-op for the duration of this call.
    # _unpatch_signal() is called in the finally block regardless of outcome.
    _patch_signal_for_thread()
    try:
        # ── Suppress the TUI ─────────────────────────────────────────────────
        import hc.tui as _tui_mod

        def _headless_tui_loop(**kw):
            """Block until the tray-requested shutdown fires."""
            log.info("Headless TUI loop started — waiting for shutdown signal.")
            state.shutdown_event.wait()

        _tui_mod.run_tui_loop = _headless_tui_loop

        # ── Hook WebServer.__init__ to intercept the instance's start() ────────
        # Patching _WS.start at class level fails because Python passes the
        # WebServer instance as the first positional arg to the replacement
        # callable, which our hook receives as its own 'self' — dropping the
        # real instance entirely.  Wrapping __init__ lets us replace start()
        # on the *instance* with a plain bound closure instead.
        from hc.web import WebServer as _WS

        _real_init = _WS.__init__

        def _patched_init(ws_self, *a, **kw):
            _real_init(ws_self, *a, **kw)           # run the real __init__
            _bound_start = ws_self.start            # capture real bound method

            def _hooked_start():
                result = _bound_start()             # call real start()
                try:
                    from hc.constants import get_web_port
                    state.port = get_web_port()
                except Exception:
                    pass
                log.info("WebServer started on port %d — signalling ready.", state.port)
                state.ready_event.set()
                return result

            ws_self.start = _hooked_start           # shadow on instance only

        _WS.__init__ = _patched_init

        try:
            import hydracast as _hc
            _hc.main()
        finally:
            # Restore __init__ so a restarted run gets a clean class.
            _WS.__init__ = _real_init

    except SystemExit as exc:
        code = exc.code
        log.warning("HydraCast exited with code %s.", code)
        if code in (None, 0):
            # Clean exit (e.g. user quit from web UI).
            state.fatal = True
            return False
        # Non-zero exit: licence failure or fatal startup error — don't retry.
        log.error("HydraCast fatal exit (code=%s) — will not restart.", code)
        state.fatal = True
        return False

    except ValueError as exc:
        # Should not happen now that signal.signal is patched, but guard anyway.
        log.exception("Worker ValueError: %s", exc)
        state.fatal = True
        return False

    except Exception as exc:
        log.exception("HydraCast worker raised unhandled exception: %s", exc)
        # Retry unless a shutdown was already requested.
        return not state.shutdown_event.is_set()

    finally:
        _unpatch_signal()

    return False   # main() returned normally — treat as clean exit


def _run_hydracast_with_restarts(state: _WorkerState) -> None:
    """
    Outer loop: runs _run_hydracast_once() with automatic restart on crash.
    Gives up after MAX_RESTARTS attempts and fires a native error dialog.
    """
    delay = RESTART_DELAY

    for attempt in range(MAX_RESTARTS + 1):
        if state.shutdown_event.is_set():
            break

        if attempt > 0:
            log.warning("Restarting HydraCast (attempt %d/%d) in %.0fs …",
                        attempt, MAX_RESTARTS, delay)
            time.sleep(delay)
            delay = min(delay * 2, 60)     # exponential back-off, cap at 60 s
            state.restart_count = attempt
            # Reset ready event for the new attempt.
            state.ready_event.clear()

        should_restart = _run_hydracast_once(state)

        if not should_restart or state.fatal:
            break
    else:
        msg = (
            f"HydraCast background service crashed {MAX_RESTARTS} times "
            "and has given up restarting.\n\n"
            "Please check logs\\hydracast_bg.log for details."
        )
        log.error(msg)
        _show_error_box("HydraCast — Fatal Error", msg)

    # Ensure the ready event is set so any waiting thread unblocks.
    state.ready_event.set()
    state.shutdown_event.set()
    log.info("Worker thread exiting.")


# ── Tray (runs on main thread) ────────────────────────────────────────────────
def _build_and_run_tray(state: _WorkerState) -> None:
    """Build the pystray icon and block on icon.run() (main-thread required)."""

    try:
        import pystray
        from pystray import MenuItem as Item
    except ImportError:
        log.warning("pystray not available — running without system tray.")
        state.shutdown_event.wait()
        return

    # Wait for worker to be ready (or crash) before starting the tray.
    log.info("Waiting up to %.0fs for HydraCast to start …", WORKER_TIMEOUT)
    became_ready = state.ready_event.wait(timeout=WORKER_TIMEOUT)

    if state.fatal or state.shutdown_event.is_set():
        # Worker died before we could show anything useful.
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
        log.info("User requested worker restart via tray.")
        state.ready_event.clear()
        # Signal the existing headless TUI loop to exit, triggering a restart.
        # The outer restart loop will pick it up.
        state.shutdown_event.set()
        # Give the worker a moment, then reset for a fresh start.
        time.sleep(1)
        state.shutdown_event.clear()
        state.fatal = False

        worker = threading.Thread(
            target=_run_hydracast_with_restarts,
            args=(state,),
            name="hydracast-worker",
            daemon=True,
        )
        worker.start()

    def _quit(icon, item):
        log.info("Quit requested from tray.")
        state.shutdown_event.set()
        icon.stop()

    def _open_log(icon, item):
        # Mirror the path-resolution logic in _setup_logging.
        appdata = os.environ.get("APPDATA")
        log_path = None
        if appdata:
            candidate = Path(appdata) / "HydraCast" / "logs" / "hydracast_bg.log"
            if candidate.exists():
                log_path = candidate
        if log_path is None:
            log_path = _exe_dir() / "logs" / "hydracast_bg.log"
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
    menu = pystray.Menu(
        Item(f"Open Web UI  (https://{_ip}:{port})", _open_web, default=True),
        pystray.Menu.SEPARATOR,
        Item("Open Log File", _open_log),
        pystray.Menu.SEPARATOR,
        Item("Quit HydraCast", _quit),
    )
    icon = pystray.Icon("HydraCast", image, f"HydraCast  https://{_ip}:{port}", menu)

    # If the worker crashes after tray starts, stop the tray too.
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


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    # ── UAC elevation (Windows) ───────────────────────────────────────────────
    # Must happen before any file I/O so we either have admin rights or have
    # already redirected writable dirs to %APPDATA%.  The helper is called
    # before _setup_logging because logging itself may need to create dirs.
    if not _request_admin_if_needed():
        # An elevated copy has been spawned.  Exit the un-elevated instance.
        sys.exit(0)

    # ── Ensure package root is on sys.path ────────────────────────────────────
    _here = _exe_dir()
    if str(_here) not in sys.path:
        sys.path.insert(0, str(_here))

    # ── Set up file logging as early as possible ──────────────────────────────
    _setup_logging(_here)
    log.info("hydracast_bg starting (frozen=%s, pid=%d).",
             getattr(sys, "frozen", False), os.getpid())

    # ── Strip flags that would cause hydracast to re-launch / daemonize ───────
    sys.argv = [a for a in sys.argv if a not in ("--background", "-b")]

    # ── Initialise hc path constants ──────────────────────────────────────────
    try:
        _setup_base_dir()
    except Exception as exc:
        log.exception("_setup_base_dir failed: %s", exc)
        _show_error_box("HydraCast — Init Error",
                        f"Failed to initialise path constants:\n{exc}")
        return

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
    worker.join(timeout=15)
    log.info("hydracast_bg exiting cleanly.")


if __name__ == "__main__":
    main()
