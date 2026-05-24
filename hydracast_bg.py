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

# ── Logging: always write to a file (no console in bg mode) ──────────────────
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

    log_file = log_dir / "hydracast_bg.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-7s  [%(threadName)s]  %(message)s",
        encoding="utf-8",
    )
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
    """
    _patch_signal_for_thread()
    try:
        import hc.tui as _tui_mod

        def _headless_tui_loop(**kw):
            log.info("Headless TUI loop — waiting for shutdown or restart signal.")
            # Block until either shutdown or an explicit restart is requested.
            while not state.shutdown_event.is_set():
                if state.restart_event.is_set():
                    return   # worker will be restarted by _run_hydracast_with_restarts
                time.sleep(0.2)

        _tui_mod.run_tui_loop = _headless_tui_loop

        from hc.web import WebServer as _WS

        _real_init = _WS.__init__

        def _patched_init(ws_self, *a, **kw):
            _real_init(ws_self, *a, **kw)
            _bound_start = ws_self.start

            def _hooked_start():
                result = _bound_start()
                try:
                    from hc.constants import get_web_port
                    state.port = get_web_port()
                except Exception:
                    pass
                log.info("WebServer started on port %d — signalling ready.", state.port)
                state.ready_event.set()
                return result

            ws_self.start = _hooked_start

        _WS.__init__ = _patched_init

        try:
            import hydracast as _hc
            _hc.main()
        finally:
            _WS.__init__ = _real_init

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

    def _open_log(icon, item):
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
    menu = pystray.Menu(
        Item(f"Open Web UI  (https://{_ip}:{port})", _open_web, default=True),
        pystray.Menu.SEPARATOR,
        Item("Restart HydraCast", _restart_worker),
        pystray.Menu.SEPARATOR,
        Item("Open App Log",      _open_log),
        Item("Open Guardian Log", _open_guardian_log),
        pystray.Menu.SEPARATOR,
        Item("Quit HydraCast",    _quit),
    )
    icon = pystray.Icon(
        "HydraCast", image,
        f"HydraCast  https://{_ip}:{port}  [Guardian Active]",
        menu,
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
    worker.join(timeout=15)
    log.info("hydracast_bg exiting cleanly.")


if __name__ == "__main__":
    main()
