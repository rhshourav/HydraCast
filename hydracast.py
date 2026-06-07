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
from hc.hc_system import assert_licensed, start_checker  # [LG]


# ── Python version guard ───────────────────────────────────────────────────────
if sys.version_info < (3, 8):
    sys.exit("HydraCast requires Python 3.8 or newer.")


# ── Bootstrap: install runtime deps if missing ────────────────────────────────
def _bootstrap() -> None:
    # When running as a PyInstaller frozen executable all dependencies are
    # already bundled — skip pip and the os.execv restart entirely.
    # os.execv would relaunch the .exe itself rather than python.exe, causing
    # an infinite restart loop, so this guard is critical.
    if getattr(sys, "frozen", False):
        return

    import importlib.util as _ilu
    needed = {
        "rich":     "rich>=13.0",
        "psutil":   "psutil>=5.9",
        "holidays": "holidays>=0.45",
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
# When frozen by PyInstaller, __file__ points inside the unpacked temp dir;
# we want the directory that contains the .exe instead so that config/,
# logs/, media/ etc. are created next to the executable, not in the temp dir.
if getattr(sys, "frozen", False):
    set_base_dir(Path(sys.executable))
else:
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
from hc.ssl_bootstrap import ensure_ssl    # noqa: E402


# =============================================================================
# PROTECT HELPERS
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


# =============================================================================
# SYSTEM TRAY  (Windows only — requires pystray + Pillow)
# =============================================================================

class _TrayIcon:
    """
    Manages a system-tray icon for HydraCast.

    Behaviour
    ---------
    - Minimize button  -> hides the console window to tray.
    - Close (X) button -> hides to tray (does NOT quit).
    - Tray left-click  -> restores the console window.
    - Tray right-click menu:
          Show / Hide HydraCast
          ──────────────────────
          Quit HydraCast          <- only way to close from tray
    - Q key in TUI     -> triggers clean shutdown as before.

    WHY WE DON'T USE SetWindowLongPtrW (WndProc subclassing)
    ---------------------------------------------------------
    The console window is owned by conhost.exe — a completely separate
    Windows process.  SetWindowLongPtrW cannot subclass a window that
    belongs to a different process; the call silently does nothing.

    We use two correct Windows mechanisms instead:
      1. SetConsoleCtrlHandler — intercepts CTRL_CLOSE_EVENT (the X button).
         Returning TRUE suppresses the default termination.
      2. A lightweight polling thread — calls IsIconic() every 250 ms and
         hides the window the moment it is minimized.
    """

    def __init__(self, shutdown_event: threading.Event,
                 glog: Optional["LogBuffer"] = None) -> None:
        self._shutdown     = shutdown_event
        self._glog         = glog
        self._hwnd: int    = 0
        self._icon_obj     = None
        self._hidden       = False
        self._ctrl_handler = None   # must keep a reference to prevent GC

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the tray icon in a background daemon thread."""
        t = threading.Thread(target=self._run, name="TrayIcon", daemon=True)
        t.start()

    def stop(self) -> None:
        """Stop the tray icon (called on clean shutdown)."""
        try:
            if self._icon_obj:
                self._icon_obj.stop()
        except Exception:
            pass

    def show_window(self) -> None:
        """Restore the console window from tray."""
        if not self._hwnd:
            return
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(self._hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(self._hwnd)
            self._hidden = False
        except Exception:
            pass

    def hide_window(self) -> None:
        """Hide the console window to tray."""
        if not self._hwnd:
            return
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(self._hwnd, 0)   # SW_HIDE
            self._hidden = True
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self._glog:
            self._glog.add(msg, "INFO")

    def _make_icon_image(self):
        """Load HydraCast.ico from resources/ or fall back to a coloured square."""
        try:
            from PIL import Image
            candidates = [
                # PyInstaller frozen build
                Path(sys.executable).parent / "_internal" / "resources" / "HydraCast.ico",
                # Development run
                _HERE / "resources" / "HydraCast.ico",
            ]
            for p in candidates:
                if p.exists():
                    return Image.open(p).convert("RGBA").resize((64, 64))
            # Fallback: amber square matching the HydraCast accent colour
            return Image.new("RGBA", (64, 64), (205, 133, 0, 255))
        except Exception:
            try:
                from PIL import Image
                return Image.new("RGBA", (64, 64), (205, 133, 0, 255))
            except Exception:
                return None

    def _install_console_hooks(self) -> None:
        """
        Install two mechanisms to intercept close and minimize.

        1. SetConsoleCtrlHandler with CTRL_CLOSE_EVENT
           The OS calls our handler when the user clicks the console X button.
           Returning TRUE tells Windows not to terminate the process.
           ShowWindow(SW_HIDE) is safe to call from this handler because it
           posts a message to the window queue rather than calling into the
           window procedure directly.

        2. Minimize-watcher polling thread
           IsIconic() is polled every 250 ms.  The moment the window becomes
           iconic we call ShowWindow(SW_HIDE) to move it to the tray instead.
           A thread is necessary because we cannot subclass conhost.exe's
           WndProc from our process.
        """
        import ctypes

        self._hwnd = ctypes.windll.kernel32.GetConsoleWindow()

        # ── 1. Close (X) button ───────────────────────────────────────────────
        CTRL_CLOSE_EVENT = 2
        HandlerRoutine   = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)

        def _ctrl_handler(ctrl_type: int) -> bool:
            if ctrl_type == CTRL_CLOSE_EVENT:
                self.hide_window()
                return True     # TRUE = handled — do NOT terminate the process
            return False        # let the default handler run for Ctrl-C etc.

        # Keep a strong reference so ctypes does not garbage-collect the
        # callback while the handler is still registered.
        self._ctrl_handler = HandlerRoutine(_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(self._ctrl_handler, True)

        # ── 2. Minimize button — polling watcher ──────────────────────────────
        def _minimize_watcher() -> None:
            IsIconic = ctypes.windll.user32.IsIconic
            while not self._shutdown.is_set():
                try:
                    if self._hwnd and not self._hidden and IsIconic(self._hwnd):
                        self.hide_window()
                except Exception:
                    pass
                time.sleep(0.25)

        threading.Thread(
            target=_minimize_watcher, name="MinimizeWatcher", daemon=True
        ).start()

    def _run(self) -> None:
        """Thread entry point — creates and runs the pystray icon."""
        try:
            import pystray
        except ImportError:
            self._log("TrayIcon: pystray not installed — tray icon unavailable.")
            return

        img = self._make_icon_image()
        if img is None:
            self._log("TrayIcon: could not create icon image — tray icon unavailable.")
            return

        # Install close / minimize intercepts BEFORE starting the tray loop.
        self._install_console_hooks()

        def _on_show_hide(icon, item):
            if self._hidden:
                self.show_window()
            else:
                self.hide_window()

        def _on_quit(icon, item):
            self._log("Quit requested from tray menu.")
            self.show_window()      # make console visible for the shutdown msg
            icon.stop()
            self._shutdown.set()

        # default=True → pystray fires _on_show_hide on a plain left-click too,
        # so clicking the tray icon toggles the window without needing on_click.
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda _: "Hide HydraCast" if not self._hidden else "Show HydraCast",
                _on_show_hide,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit HydraCast", _on_quit),
        )

        self._icon_obj = pystray.Icon(
            "HydraCast",
            img,
            "HydraCast — running",
            menu,
        )

        self._log(
            "System tray active — close/minimize hides to tray. "
            "Left-click tray icon to show/hide. Right-click > Quit to exit."
        )

        # pystray.Icon.run() creates a Win32 message loop and must be called
        # from the main thread.  We are on a daemon thread, so we use
        # run_detached() (pystray >= 0.17) which hands off to pystray's own
        # internal thread and returns immediately.  We then block on the
        # shutdown event to keep our object (and _ctrl_handler) alive.
        #
        # Older pystray falls back to run() which blocks here; it generally
        # works from a non-main thread because Win32 creates a per-thread
        # message queue on first GUI call.
        try:
            self._icon_obj.run_detached()   # pystray >= 0.17
            self._shutdown.wait()           # keep alive until Q or Quit
        except AttributeError:
            self._icon_obj.run()            # pystray < 0.17, blocks


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
    return p.parse_args()


# =============================================================================
# PRE-FLIGHT CHECKS
# =============================================================================
def _preflight(console: Console) -> List[StreamConfig]:
    from hc.constants import LISTEN_ADDR, BASE_DIR, MEDIA_DIR, WRITABLE_BASE_DIR

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
    if WRITABLE_BASE_DIR() != BASE_DIR():
        console.print(f"[{CD}]  Data dir  : {WRITABLE_BASE_DIR()}  (redirected — install dir is read-only)[/]")
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

    # ── SSL certificate ───────────────────────────────────────────────────────
    try:
        ensure_ssl(console)
    except RuntimeError as exc:
        console.print(f"[{CR}]✘  SSL error: {exc}[/]")
        sys.exit(1)

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
# UAC ELEVATION (Windows)
# =============================================================================
def _request_admin_if_needed() -> bool:
    """
    Re-launch the current process with administrator privileges via UAC if:
      • We are running on Windows, AND
      • The current process is NOT already elevated.

    Returns True  → already admin (or non-Windows): continue normally.
    Returns False → an elevated process was spawned: caller should exit.

    HydraCast needs elevation to:
      • Create subdirectories inside C:\\Program Files\\HydraCast\\
      • Bind to privileged ports (80, 443)
      • Add Windows Firewall rules

    If the user declines the UAC prompt, the function returns True and the app
    continues — constants.py will silently redirect all writable dirs to
    %%APPDATA%%\\HydraCast so the startup never fails with PermissionError.
    """
    if not IS_WIN:
        return True

    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return True   # already elevated
    except Exception:
        return True       # can't check; assume OK

    try:
        import ctypes
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        if ret > 32:
            return False  # elevated copy launched; exit un-elevated one
    except Exception:
        pass

    return True   # elevation declined or failed — continue without it


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    # ── UAC elevation (Windows) ───────────────────────────────────────────────
    # Request admin rights before any I/O so we can write to the install dir
    # and bind to privileged ports (80/443).  If the user declines, constants.py
    # falls back to %APPDATA%\HydraCast silently.
    if not _request_admin_if_needed():
        sys.exit(0)   # elevated copy is running; exit the un-elevated one

    assert_licensed()                # [LG] exit if locked
    start_checker("hydracast")       # [LG] background validator
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

    # In protect mode Ctrl-C is re-wired to a warning;
    # in normal mode it still triggers a clean shutdown.
    if args.protect:
        _protect_signals(glog)
        glog.add(
            "Protect mode active — Ctrl-C disabled. "
            "Use Q in the TUI or the Web UI to stop.", "INFO"
        )
    else:
        signal.signal(signal.SIGINT,  _on_signal)

    signal.signal(signal.SIGTERM, _on_signal)

    # ── System tray (Windows only) ────────────────────────────────────────────
    # Always active on Windows regardless of --protect.
    # Minimize and close buttons hide the window to the tray.
    # Only Q in the TUI or right-click → Quit from the tray actually exits.
    _tray: Optional[_TrayIcon] = None
    if IS_WIN:
        _win_set_title(f"{APP_NAME} v{APP_VER}  —  Press Q to quit  |  Minimize hides to tray")
        _tray = _TrayIcon(_shutdown, glog)
        _tray.start()

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

    # ── TUI main loop ─────────────────────────────────────────────────────────
    run_tui_loop(
        manager=manager,
        glog=glog,
        console=console,
        shutdown_event=_shutdown,
        export_urls_fn=manager.export_urls,
    )

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    if _tray:
        _tray.show_window()   # ensure console is visible for the shutdown message
        _tray.stop()
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
