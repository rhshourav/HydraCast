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
#  HydraCast  —  Multi-Stream RTSP Weekly Scheduler  v5.3.0
#  Author  : rhshourav
#  GitHub  : https://github.com/rhshourav/HydraCast
#
#  v5.3 changelog
#  ──────────────
#  CHANGED  streams.csv / events.csv replaced with JSON files in config/:
#             config/streams.json  — stream definitions
#             config/events.json   — one-shot events
#  NEW      CSVManager removed; JSONManager (hc/json_manager.py) handles
#           all persistence.  Public API is identical so all call-sites only
#           needed their import updated.
#  NEW      Folder-source playlist is now TODAY-AWARE:
#             1. Files tagged _today_ (e.g. _tue_) stream FIRST.
#             2. Untagged files stream SECOND (available every day).
#             3. Other weekday files stream LAST (in weekday order).
#           This means a correctly named folder auto-curates the right
#           content for the current day without any manual intervention.
#
#  v5.1 changelog
#  ──────────────
#  FIXED    Stop (S key) no longer causes stream to restart — _auto_restart
#           now checks the _stop flag before every restart attempt.
#  FIXED    K key no longer conflicts with UP navigation; only ↑/↓ arrows
#           and J navigate; K is now a free hotkey.
#  FIXED    Number key stream selection (1-9) works correctly.
#  NEW      D key — interactive stream detail overlay (config, files, URLs).
#  NEW      V key — scrollable per-stream log viewer overlay.
#  NEW      H / ? key — keyboard help overlay.
#  NEW      F key — force folder rescan for folder-source streams.
#  NEW      C key — clear error state and reset restart count.
#  NEW      Page Up/Down — scroll 5 streams at a time.
#  NEW      --protect  — prevent accidental closure via Ctrl-C / close button.
#  NEW      --background — daemonize (Linux/macOS fork; Windows detached proc);
#                          runs web-only with no TUI, safe for unattended use.
#  FIXED    After web upload, folder-source streams pick up new files on
#           next start/restart (no manual JSON reload needed).
#  FIXED    seek_start_pos AttributeError on fresh StreamState.
#  IMPROVED restart() no longer races with _monitor auto-restart.
#  IMPROVED FolderWatcher polls folder sources every 15 s and updates
#           playlists live without any manual intervention.
# =============================================================================

import os
import platform
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

# ── Python version guard ───────────────────────────────────────────────────────
if sys.version_info < (3, 8):
    sys.exit("HydraCast requires Python 3.8 or newer.")


# ── Bootstrap: install runtime deps if missing ────────────────────────────────
def _bootstrap() -> None:
    import importlib.util as _ilu
    needed = {
        "rich":                  "rich>=13.0",
        "psutil":                "psutil>=5.9",
        "google.auth":           "google-auth>=2.0",
        "google_auth_oauthlib":  "google-auth-oauthlib>=1.0",
        "googleapiclient":       "google-api-python-client>=2.0",
        "holidays":              "holidays>=0.45",
    }

    def _is_available(mod: str) -> bool:
        # find_spec raises ModuleNotFoundError for dotted names (e.g. "google.auth")
        # when the parent package ("google") does not exist yet.
        try:
            return _ilu.find_spec(mod) is not None
        except (ModuleNotFoundError, ValueError):
            return False

    missing = [pkg for mod, pkg in needed.items() if not _is_available(mod)]
    if not missing:
        return
    print(f"[HydraCast] Installing: {', '.join(missing)} …")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", *missing, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("[HydraCast] Done. Restarting …\n")
    os.execv(sys.executable, [sys.executable] + sys.argv)


_bootstrap()

# ── Third-party imports (available after bootstrap) ───────────────────────────
import argparse
import logging

from rich.console import Console

# ── hc package: set_base_dir MUST be called before any path-dependent import ──
_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from hc.constants import (
    APP_NAME, APP_VER, APP_AUTHOR,
    CC, CD, CG, CR, CY,
    CPU_COUNT, IS_LINUX, IS_MAC, IS_WIN, WEB_PORT,
    CONFIG_DIR, CONFIGS_DIR, LOGS_DIR,
    set_base_dir,
    set_ffmpeg, set_ffprobe,
    set_no_firewall, set_listen_addr, set_web_port,
    get_web_port,
)

# Initialise all directory paths relative to this script's folder.
set_base_dir(Path(__file__))

# Now it is safe to import everything else.
from hc import web as _web_module          # noqa: E402
from hc.json_manager import JSONManager    # noqa: E402  (replaces csv_manager)
from hc.dependency import DependencyManager # noqa: E402
from hc.firewall import FirewallManager    # noqa: E402
from hc.manager import StreamManager       # noqa: E402
from hc.models import StreamConfig, StreamStatus  # noqa: E402
from hc.tui import run_tui_loop            # noqa: E402
from hc.utils import _local_ip             # noqa: E402
from hc.web import WebServer               # noqa: E402
from hc.worker import LogBuffer            # noqa: E402


# =============================================================================
# BACKGROUND / PROTECT HELPERS
# =============================================================================

def _win_disable_close_button() -> None:
    """
    Grey-out the ✕ button on the Windows console window so users cannot
    accidentally dismiss HydraCast.  Requires no elevation.
    """
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return
        hmenu = ctypes.windll.user32.GetSystemMenu(hwnd, False)
        # MF_BYCOMMAND | MF_GRAYED
        ctypes.windll.user32.EnableMenuItem(hmenu, 0xF060, 0x00000001)
    except Exception:
        pass   # not fatal — TUI still works without it


def _win_set_title(title: str) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def _protect_signals(glog: Optional["LogBuffer"] = None) -> None:
    """
    Re-wire SIGINT (Ctrl-C) so it logs a reminder instead of quitting.
    On Linux/macOS also ignore SIGHUP so closing the terminal does NOT
    kill the process.
    """
    def _ignore_sigint(sig, frame):  # noqa: ANN001
        if glog:
            glog.add("Ctrl-C blocked — press Q in the TUI or use the Web UI to quit.", "WARN")
        else:
            print("\n[HydraCast] Ctrl-C blocked. Press Q in the TUI or use the Web UI to quit.")

    signal.signal(signal.SIGINT, _ignore_sigint)

    if IS_LINUX or IS_MAC:
        try:
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
        except (OSError, ValueError):
            pass   # some environments (e.g. Windows WSL edge cases) raise here


def _daemonize_linux(console: Console, log_path: str) -> None:
    """
    POSIX double-fork daemonisation.  The *parent* process prints a message
    and exits; the grandchild continues as a fully detached daemon.
    """
    # First fork — parent exits immediately.
    pid = os.fork()
    if pid > 0:
        console.print(
            f"\n[{CG}]✔  HydraCast daemonized (PID will appear in log).[/]\n"
            f"[{CD}]   Logs   : {log_path}[/]\n"
            f"[{CD}]   Web UI : http://localhost:{get_web_port()}[/]\n"
        )
        sys.exit(0)

    # Decouple from parent environment.
    os.setsid()
    os.umask(0o022)

    # Second fork — orphan the session leader so it can never acquire a tty.
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect stdin/stdout/stderr.
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "rb") as fi:
        os.dup2(fi.fileno(), sys.stdin.fileno())
    with open(log_path, "ab") as fo:
        os.dup2(fo.fileno(), sys.stdout.fileno())
        os.dup2(fo.fileno(), sys.stderr.fileno())


def _daemonize_windows(console: Console) -> None:
    """
    Re-launch this script as a fully detached Windows process (no console
    window) then exit the current process.  The child will skip the
    --background flag so it runs normally.
    """
    import ctypes

    # Build the new argv without --background so the child doesn't loop.
    args = [a for a in sys.argv if a not in ("--background", "-b")]

    DETACHED_PROCESS    = 0x00000008
    CREATE_NO_WINDOW    = 0x08000000
    CREATE_NEW_PG       = 0x00000200

    proc = subprocess.Popen(
        [sys.executable] + args,
        creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PG,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    console.print(
        f"\n[{CG}]✔  HydraCast launched in background (PID {proc.pid}).[/]\n"
        f"[{CD}]   Web UI : http://localhost:{get_web_port()}[/]\n"
    )
    sys.exit(0)


def _apply_background_mode(console: Console) -> bool:
    """
    Daemonize the process.  Returns True if execution should continue in
    this process (i.e. we are the daemon child on Linux/macOS).
    Returns False is never reached on Windows (sys.exit called in parent).
    """
    log_path = str(LOGS_DIR() / "hydracast.log")

    if IS_WIN:
        _daemonize_windows(console)
        return False  # unreachable — _daemonize_windows calls sys.exit

    # Linux / macOS: double-fork.  After _daemonize_linux the current
    # process *is* the daemon grandchild if we reach here.
    _daemonize_linux(console, log_path)
    return True


# =============================================================================
# CLI
# =============================================================================
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="hydracast",
        description=f"{APP_NAME} v{APP_VER} — Multi-Stream RTSP Weekly Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--no-firewall", action="store_true",
        help="Skip automatic firewall port-opening.",
    )
    p.add_argument(
        "--listen", metavar="IP", default="0.0.0.0",
        help="IP address for MediaMTX to bind (default: 0.0.0.0).",
    )
    p.add_argument(
        "--web-port", type=int, default=WEB_PORT,
        help=f"Web UI port (default: {WEB_PORT}).",
    )
    p.add_argument(
        "--no-web", action="store_true",
        help="Disable the embedded Web UI.",
    )
    p.add_argument(
        "--list-ports", action="store_true",
        help="Print which TCP ports would be opened, then exit.",
    )
    p.add_argument(
        "--export-urls", action="store_true",
        help="Write stream_urls.txt next to this script at startup.",
    )
    p.add_argument(
        "--protect", action="store_true",
        help=(
            "Prevent accidental shutdown: ignore Ctrl-C, disable the console "
            "close button (Windows) and ignore SIGHUP (Linux/macOS). "
            "Only Q in the TUI or the Web UI can stop HydraCast."
        ),
    )
    p.add_argument(
        "--background", "-b", action="store_true",
        help=(
            "Detach from the terminal and run as a background process. "
            "Linux/macOS: double-fork daemon. "
            "Windows: re-launch without a console window. "
            "In background mode the TUI is disabled; use the Web UI to manage streams. "
            "Implies --protect."
        ),
    )
    return p.parse_args()


# =============================================================================
# PRE-FLIGHT CHECKS
# =============================================================================
def _preflight(console: Console) -> List[StreamConfig]:
    from hc.constants import LISTEN_ADDR, BASE_DIR, MEDIA_DIR

    console.rule(f"[{CC}]{APP_NAME} v{APP_VER}[/]  Pre-flight checks")
    console.print()

    # Remove stale per-stream MediaMTX YAML configs from a previous run.
    for f in CONFIGS_DIR().glob("mediamtx_*.yml"):
        try:
            f.unlink()
        except Exception:
            pass

    console.print(
        f"[{CD}]  OS        : {platform.system()} "
        f"{platform.release()} ({platform.machine()})[/]"
    )
    console.print(f"[{CD}]  Python    : {sys.version.split()[0]}[/]")
    console.print(f"[{CD}]  CPU cores : {CPU_COUNT}[/]")
    console.print(f"[{CD}]  LAN IP    : {_local_ip()}[/]")
    console.print(f"[{CD}]  Bind addr : {LISTEN_ADDR()}[/]")
    console.print(f"[{CD}]  Base dir  : {BASE_DIR()}[/]")
    console.print(f"[{CD}]  Media dir : {MEDIA_DIR()}[/]")
    console.print(f"[{CD}]  Config dir: {CONFIG_DIR()}[/]")
    console.print()

    # ── MediaMTX ──────────────────────────────────────────────────────────────
    if not DependencyManager.download_mediamtx(console):
        console.print(f"[{CR}]✘  Cannot continue without MediaMTX.[/]")
        sys.exit(1)

    # ── FFmpeg ────────────────────────────────────────────────────────────────
    # ensure_ffmpeg prints its own ✔ / ⚠ / ✘ lines and auto-downloads if needed.
    ffmpeg_path = DependencyManager.ensure_ffmpeg(console)
    if not ffmpeg_path:
        console.print(
            f"[{CR}]✘  FFmpeg could not be found or downloaded automatically.[/]\n"
            f"[{CY}]   Install it manually then re-run HydraCast:\n"
            f"   Linux  : sudo apt install ffmpeg\n"
            f"   Windows: https://www.gyan.dev/ffmpeg/builds/\n"
            f"   macOS  : brew install ffmpeg[/]"
        )
        sys.exit(1)
    set_ffmpeg(ffmpeg_path)

    # ensure_ffprobe is non-fatal; it also auto-downloads when possible.
    ffprobe_path = DependencyManager.ensure_ffprobe(console)
    if ffprobe_path:
        set_ffprobe(ffprobe_path)
    else:
        console.print(f"[{CY}]⚠  FFprobe not available (optional — some probing features disabled).[/]")

    # ── config/streams.json ───────────────────────────────────────────────────
    try:
        configs = JSONManager.load()
    except Exception as exc:
        console.print(f"[{CR}]✘  Config error: {exc}[/]")
        sys.exit(1)

    if configs:
        console.print(
            f"[{CG}]✔  Loaded {len(configs)} stream(s) from config/streams.json[/]"
        )
        # Show folder-source streams so the operator can verify the scan.
        for c in configs:
            if c.folder_source:
                console.print(
                    f"[{CD}]   └─ [{c.name}] folder-source: {c.folder_source.name} "
                    f"({len(c.playlist)} file(s) found, today's tagged files first)[/]"
                )
    else:
        console.print(
            f"[{CY}]⚠  No valid streams configured yet — "
            f"starting in web-only mode.[/]"
        )
        console.print(
            f"[{CD}]   Open the Web UI → Configure tab to add streams.[/]"
        )

    # ── Firewall ──────────────────────────────────────────────────────────────
    enabled_ports = [c.port for c in configs if c.enabled]
    if enabled_ports:
        console.print()
        FirewallManager.open_ports(enabled_ports, console)

    console.print()
    time.sleep(0.6)
    return configs


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    args = _parse_args()

    set_no_firewall(args.no_firewall)
    set_listen_addr(args.listen)
    set_web_port(args.web_port)

    console = Console(force_terminal=True, highlight=False)

    # ── --list-ports mode ─────────────────────────────────────────────────────
    if args.list_ports:
        try:
            cfgs = JSONManager.load()
        except Exception as exc:
            console.print(f"[{CR}]✘  {exc}[/]")
            sys.exit(1)
        console.print(f"[{CC}]Ports that would be opened:[/]")
        for c in cfgs:
            if c.enabled:
                hls_info = f"  + HLS :{c.hls_port}" if c.hls_enabled else ""
                console.print(f"  {c.name:20s}  TCP :{c.port}{hls_info}")
        sys.exit(0)

    # ── Background mode ───────────────────────────────────────────────────────
    # Must happen BEFORE pre-flight so the parent can exit cleanly.
    background_mode = args.background
    if background_mode:
        console.print(
            f"[{CY}]⚡  Background mode requested — "
            f"{'daemonizing' if not IS_WIN else 'detaching'} …[/]"
        )
        # On Linux/macOS _apply_background_mode forks; only the daemon child
        # continues past this call.  On Windows sys.exit() is called.
        _apply_background_mode(console)
        # If we reach here we are the daemon child (Linux/macOS).
        # Re-create console since we have new stdout/stderr.
        console = Console(force_terminal=False, highlight=False)

    # ── Pre-flight ────────────────────────────────────────────────────────────
    configs = _preflight(console)

    # ── File logging ──────────────────────────────────────────────────────────
    logging.basicConfig(
        filename=str(LOGS_DIR() / "hydracast.log"),
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    # ── Core objects ──────────────────────────────────────────────────────────
    glog    = LogBuffer()
    manager = StreamManager(configs, glog)

    # Expose the manager to the web module so upload handlers can trigger
    # in-memory folder rescans after a file is uploaded.
    _web_module._WEB_MANAGER = manager

    # ── Signal handling / process protection ──────────────────────────────────
    _shutdown = threading.Event()

    def _on_signal(sig: int, _frame: object) -> None:  # noqa: ANN001
        _shutdown.set()

    # In protect or background mode Ctrl-C is re-wired to a warning;
    # in normal mode it still triggers a clean shutdown.
    if args.protect or background_mode:
        _protect_signals(glog)
        if IS_WIN and not background_mode:
            _win_disable_close_button()
            _win_set_title(f"{APP_NAME} v{APP_VER}  —  Press Q to quit")
        glog.add(
            "Protect mode active — Ctrl-C disabled. "
            "Use Q in the TUI or the Web UI to stop.", "INFO"
        )
    else:
        signal.signal(signal.SIGINT,  _on_signal)

    signal.signal(signal.SIGTERM, _on_signal)

    # ── Start everything ──────────────────────────────────────────────────────
    glog.add(
        f"{APP_NAME} v{APP_VER} started — "
        f"{len(configs)} stream(s) configured."
    )
    manager.start_all()
    manager.run_scheduler()

    if args.export_urls:
        try:
            url_file = manager.export_urls()
            glog.add(f"Stream URLs exported → {url_file.name}")
        except Exception as exc:
            glog.add(f"URL export error: {exc}", "ERROR")

    web: Optional[WebServer] = None
    if not args.no_web:
        web = WebServer(get_web_port())
        web.start()
        glog.add(
            f"Web UI → http://{_local_ip()}:{get_web_port()}", "INFO"
        )

    # ── TUI main loop — skipped in background mode ────────────────────────────
    if not background_mode:
        run_tui_loop(
            manager=manager,
            glog=glog,
            console=console,
            shutdown_event=_shutdown,
            export_urls_fn=manager.export_urls,
        )
    else:
        # Background / daemon mode: no TUI.  Block until SIGTERM or web shutdown.
        glog.add("Running in background mode — Web UI is the only control interface.")
        _shutdown.wait()

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    if not background_mode:
        console.clear()
        console.print(f"\n[{CY}]⏳  Stopping all streams … please wait.[/]")
    manager.shutdown()
    if web:
        web.stop()
    # Clean up per-stream MediaMTX YAML configs.
    for f in CONFIGS_DIR().glob("mediamtx_*.yml"):
        try:
            f.unlink()
        except Exception:
            pass
    if not background_mode:
        console.print(f"[{CG}]✔  HydraCast stopped cleanly. Goodbye.[/]\n")


# =============================================================================
if __name__ == "__main__":
    main()
