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
#  HydraCast  —  Multi-Stream RTSP Weekly Scheduler  v5.1.0
#  Author  : rhshourav
#  GitHub  : https://github.com/rhshourav/HydraCast
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
#  FIXED    After web upload, folder-source streams pick up new files on
#           next start/restart (no manual CSV reload needed).
#  FIXED    seek_start_pos AttributeError on fresh StreamState.
#  IMPROVED restart() no longer races with _monitor auto-restart.
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
    }
    missing = [pkg for mod, pkg in needed.items() if not _ilu.find_spec(mod)]
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
    CPU_COUNT, WEB_PORT,
    CONFIGS_DIR, LOGS_DIR,
    set_base_dir,
    set_ffmpeg, set_ffprobe,
    set_no_firewall, set_listen_addr, set_web_port,
    get_web_port,
)

# Initialise all directory paths relative to this script's folder.
set_base_dir(Path(__file__))

# Now it is safe to import everything else.
from hc import web as _web_module          # noqa: E402
from hc.csv_manager import CSVManager      # noqa: E402
from hc.dependency import DependencyManager # noqa: E402
from hc.firewall import FirewallManager    # noqa: E402
from hc.manager import StreamManager       # noqa: E402
from hc.models import StreamConfig, StreamStatus  # noqa: E402
from hc.tui import run_tui_loop            # noqa: E402
from hc.utils import _local_ip             # noqa: E402
from hc.web import WebServer               # noqa: E402
from hc.worker import LogBuffer            # noqa: E402


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
    console.print()

    # ── MediaMTX ──────────────────────────────────────────────────────────────
    if not DependencyManager.download_mediamtx(console):
        console.print(f"[{CR}]✘  Cannot continue without MediaMTX.[/]")
        sys.exit(1)

    # ── FFmpeg ────────────────────────────────────────────────────────────────
    ffmpeg_path = DependencyManager.check_ffmpeg()
    if not ffmpeg_path:
        console.print(
            f"[{CR}]✘  FFmpeg not found in PATH or bin/[/]\n"
            f"[{CY}]   Linux  : sudo apt install ffmpeg\n"
            f"   Windows: https://www.gyan.dev/ffmpeg/builds/\n"
            f"   macOS  : brew install ffmpeg[/]"
        )
        sys.exit(1)
    set_ffmpeg(ffmpeg_path)
    console.print(f"[{CG}]✔  FFmpeg  : {ffmpeg_path}[/]")

    ffprobe_path = DependencyManager.check_ffprobe()
    if ffprobe_path:
        set_ffprobe(ffprobe_path)
    console.print(f"[{CG}]✔  FFprobe : {ffprobe_path or 'ffprobe (system PATH)'}[/]")

    # ── streams.csv ───────────────────────────────────────────────────────────
    try:
        configs = CSVManager.load()
    except FileNotFoundError as exc:
        console.print(f"\n[{CY}]⚠  {exc}[/]")
        sys.exit(0)
    except ValueError as exc:
        console.print(f"[{CR}]✘  CSV validation error: {exc}[/]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[{CR}]✘  CSV error: {exc}[/]")
        sys.exit(1)

    console.print(
        f"[{CG}]✔  Loaded {len(configs)} stream(s) from streams.csv[/]"
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
            cfgs = CSVManager.load()
        except Exception as exc:
            console.print(f"[{CR}]✘  {exc}[/]")
            sys.exit(1)
        console.print(f"[{CC}]Ports that would be opened:[/]")
        for c in cfgs:
            if c.enabled:
                hls_info = f"  + HLS :{c.hls_port}" if c.hls_enabled else ""
                console.print(f"  {c.name:20s}  TCP :{c.port}{hls_info}")
        sys.exit(0)

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

    # ── Signal handling ───────────────────────────────────────────────────────
    _shutdown = threading.Event()

    def _on_signal(sig: int, _frame: object) -> None:  # noqa: ANN001
        _shutdown.set()

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

    # ── TUI main loop (blocking) ──────────────────────────────────────────────
    run_tui_loop(
        manager=manager,
        glog=glog,
        console=console,
        shutdown_event=_shutdown,
        export_urls_fn=manager.export_urls,
    )

    # ── Graceful shutdown ─────────────────────────────────────────────────────
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
    console.print(f"[{CG}]✔  HydraCast stopped cleanly. Goodbye.[/]\n")


# =============================================================================
if __name__ == "__main__":
    main()
