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
#  HydraCast  —  Multi-Stream RTSP Weekly Scheduler
#  Author  : rhshourav
#  Version : 2.0.0
#  GitHub  : https://github.com/rhshourav/HydraCast
#  License : MIT
#
#  Fully automated, multi-core RTSP streaming from a CSV schedule.
#  Supports mixed formats · per-port isolation · weekly loops · seek start
#
#  v2.0 changelog
#  ──────────────
#  FIXED  MediaMTX v1.9.x YAML compat: removed deprecated rtspEncryption,
#         hls: no, webrtc: no, srt: no  (caused "json: unknown field" crash)
#  FIXED  FFmpeg now waits for MediaMTX port to be *actually* listening
#         before connecting (replaces the unreliable 1.5-second sleep)
#  FIXED  Orphan process detection + kill before binding a port
#  NEW    FirewallManager: auto-opens RTSP ports on Windows (netsh),
#         Linux ufw / firewalld / iptables, with root/admin detection
#  NEW    --listen IP flag: bind MediaMTX on a specific interface
#  NEW    --no-firewall flag to skip all firewall changes
#  NEW    --list-ports: dry-run print of ports that would be opened
#  NEW    --export-urls: write stream_urls.txt at startup
#  NEW    [U] hotkey: export stream URLs from inside the TUI at any time
#  NEW    video_bitrate / audio_bitrate columns in CSV (per-stream quality)
#  NEW    hls_enabled column: serve HLS alongside RTSP (per stream)
#  NEW    LAN IP shown in the System panel
#  NEW    macOS detection with user guidance
# =============================================================================

import os
import sys
import csv
import time
import json
import shutil
import signal
import socket
import platform
import argparse
import threading
import subprocess
import multiprocessing
import re
import urllib.request
import zipfile
import tarfile
import stat
import logging
import queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# ── Python guard ──────────────────────────────────────────────────────────────
if sys.version_info < (3, 8):
    sys.exit("HydraCast requires Python 3.8 or newer. Please upgrade.")

# ── Bootstrap: silently install missing pip packages ──────────────────────────
def _bootstrap() -> None:
    import importlib
    needed = {"rich": "rich>=13.0", "psutil": "psutil>=5.9"}
    missing = [pkg for mod, pkg in needed.items()
               if not importlib.util.find_spec(mod)]
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

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.align import Align
from rich.rule import Rule
from rich import box
import psutil

# =============================================================================
# CONSTANTS & PATHS
# =============================================================================
APP_NAME   = "HydraCast"
APP_VER    = "2.0.0"
APP_AUTHOR = "rhshourav"
APP_GITHUB = "https://github.com/rhshourav/HydraCast"

IS_WIN   = platform.system() == "Windows"
IS_MAC   = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
OS_KEY   = "windows" if IS_WIN else "linux"
ARCH_KEY = platform.machine()           # e.g. x86_64, aarch64, AMD64
CPU_COUNT = max(1, multiprocessing.cpu_count())

BASE_DIR    = Path(__file__).parent.resolve()
BIN_DIR     = BASE_DIR / "bin"
CONFIGS_DIR = BASE_DIR / "configs"
LOGS_DIR    = BASE_DIR / "logs"
CSV_FILE    = BASE_DIR / "streams.csv"

for _d in (BIN_DIR, CONFIGS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── MediaMTX ──────────────────────────────────────────────────────────────────
MEDIAMTX_VER = "1.9.1"
MEDIAMTX_BIN = BIN_DIR / ("mediamtx.exe" if IS_WIN else "mediamtx")

_MTX_BASE = f"https://github.com/bluenviron/mediamtx/releases/download/v{MEDIAMTX_VER}"
MEDIAMTX_URLS: Dict[Tuple[str, str], str] = {
    ("linux",   "x86_64"):  f"{_MTX_BASE}/mediamtx_v{MEDIAMTX_VER}_linux_amd64.tar.gz",
    ("linux",   "aarch64"): f"{_MTX_BASE}/mediamtx_v{MEDIAMTX_VER}_linux_arm64v8.tar.gz",
    ("linux",   "armv7l"):  f"{_MTX_BASE}/mediamtx_v{MEDIAMTX_VER}_linux_armv7.tar.gz",
    ("linux",   "i686"):    f"{_MTX_BASE}/mediamtx_v{MEDIAMTX_VER}_linux_386.tar.gz",
    ("windows", "AMD64"):   f"{_MTX_BASE}/mediamtx_v{MEDIAMTX_VER}_windows_amd64.zip",
    ("windows", "x86"):     f"{_MTX_BASE}/mediamtx_v{MEDIAMTX_VER}_windows_386.zip",
}

# ── FFmpeg ────────────────────────────────────────────────────────────────────
FFMPEG_BIN_NAME  = "ffmpeg.exe"  if IS_WIN else "ffmpeg"
FFPROBE_BIN_NAME = "ffprobe.exe" if IS_WIN else "ffprobe"
FFMPEG_PATH:  str = FFMPEG_BIN_NAME
FFPROBE_PATH: str = FFPROBE_BIN_NAME

# ── Schedule map ──────────────────────────────────────────────────────────────
WEEKDAY_MAP: Dict[str, Any] = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
    "all": list(range(7)), "everyday": list(range(7)),
    "weekdays": list(range(5)), "weekends": [5, 6],
}
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ── Rich colour tokens ────────────────────────────────────────────────────────
CG = "bright_green"
CR = "bright_red"
CY = "yellow"
CC = "bright_cyan"
CW = "white"
CD = "dim white"
CM = "bright_magenta"
CB = "bright_blue"

# ── Global CLI flags (mutated by _parse_args → main) ─────────────────────────
NO_FIREWALL = False
LISTEN_ADDR = "0.0.0.0"   # bind MediaMTX on all interfaces by default


# =============================================================================
# DATA MODELS
# =============================================================================
class StreamStatus(Enum):
    STOPPED   = ("●", "dim white",    "STOPPED")
    STARTING  = ("◌", "yellow",       "STARTING")
    LIVE      = ("●", "bright_green", "LIVE")
    SCHEDULED = ("◷", "bright_cyan",  "SCHED")
    ERROR     = ("●", "bright_red",   "ERROR")
    DISABLED  = ("⊘", "dim",          "DISABLED")

    @property
    def dot(self)   -> str: return self.value[0]
    @property
    def color(self) -> str: return self.value[1]
    @property
    def label(self) -> str: return self.value[2]


@dataclass
class StreamConfig:
    name:           str
    port:           int
    file_path:      Path
    weekdays:       List[int]
    start_position: str       # HH:MM:SS
    enabled:        bool
    row_index:      int  = 0
    video_bitrate:  str  = "2500k"   # v2: per-stream video bitrate
    audio_bitrate:  str  = "128k"    # v2: per-stream audio bitrate
    hls_enabled:    bool = False     # v2: also serve HLS on port+10000

    @property
    def start_seconds(self) -> float:
        try:
            h, m, s = self.start_position.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            return 0.0

    @property
    def rtsp_url(self) -> str:
        return f"rtsp://127.0.0.1:{self.port}/live"

    @property
    def rtsp_url_external(self) -> str:
        ip = LISTEN_ADDR if LISTEN_ADDR != "0.0.0.0" else _local_ip()
        return f"rtsp://{ip}:{self.port}/live"

    @property
    def hls_port(self) -> int:
        return self.port + 10000

    @property
    def hls_url(self) -> str:
        ip = LISTEN_ADDR if LISTEN_ADDR != "0.0.0.0" else _local_ip()
        return f"http://{ip}:{self.hls_port}/live/index.m3u8"

    def is_scheduled_today(self) -> bool:
        return datetime.now().weekday() in self.weekdays

    def weekdays_display(self) -> str:
        if set(self.weekdays) == set(range(7)):  return "ALL"
        if set(self.weekdays) == set(range(5)):  return "Weekdays"
        if set(self.weekdays) == {5, 6}:         return "Weekends"
        return "|".join(DAY_ABBR[d] for d in sorted(self.weekdays))


@dataclass
class StreamState:
    config:        StreamConfig
    status:        StreamStatus              = StreamStatus.STOPPED
    mtx_proc:      Optional[subprocess.Popen] = None
    ffmpeg_proc:   Optional[subprocess.Popen] = None
    progress:      float                     = 0.0
    current_pos:   float                     = 0.0
    duration:      float                     = 0.0
    loop_count:    int                       = 0
    fps:           float                     = 0.0
    bitrate:       str                       = "—"
    speed:         str                       = "—"
    error_msg:     str                       = ""
    started_at:    Optional[datetime]        = None
    restart_count: int                       = 0
    log:           List[str]                 = field(default_factory=list)
    _lock:         threading.Lock            = field(default_factory=threading.Lock)

    def log_add(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.log.append(f"[{ts}] {msg}")
            if len(self.log) > 300:
                self.log.pop(0)

    def format_pos(self) -> str:
        def _f(s: float) -> str:
            s = int(max(0, s))
            return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
        if self.duration > 0:
            return f"{_f(self.current_pos)} / {_f(self.duration)}"
        return "—"


# =============================================================================
# UTILITY HELPERS
# =============================================================================
def _local_ip() -> str:
    """Best-guess LAN IP (not 127.0.0.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if something is already bound to the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _wait_for_port(port: int, host: str = "127.0.0.1",
                   timeout: float = 10.0, interval: float = 0.25) -> bool:
    """Block until the port is listening or timeout expires. Returns True if ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(port, host):
            return True
        time.sleep(interval)
    return False


def _kill_orphan_on_port(port: int) -> None:
    """Terminate any process already occupying a port (best-effort)."""
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr.port == port and conn.status in ("LISTEN", "ESTABLISHED"):
                if conn.pid:
                    try:
                        psutil.Process(conn.pid).terminate()
                        logging.info("Killed orphan PID %s on port %d", conn.pid, port)
                    except Exception:
                        pass
    except Exception:
        pass


# =============================================================================
# FIREWALL MANAGER
# =============================================================================
class FirewallManager:
    """
    Auto-configure the OS firewall to allow inbound TCP on the RTSP ports.

    Detects:
      Windows → netsh advfirewall  (requires Administrator)
      Linux   → ufw / firewalld / iptables  (requires root)
      macOS   → prints user guidance (no auto-config)

    Skips silently when NO_FIREWALL is True.
    """

    _linux_tool: Optional[str] = None

    @classmethod
    def open_ports(cls, ports: List[int], console: Console) -> None:
        if NO_FIREWALL:
            console.print(f"[{CD}]ℹ  Firewall config skipped (--no-firewall).[/]")
            return

        if IS_WIN:
            cls._windows(ports, console)
        elif IS_LINUX:
            cls._linux(ports, console)
        elif IS_MAC:
            console.print(
                f"[{CY}]⚠  macOS: If streams aren't reachable from other machines,\n"
                f"   go to System Settings → Network → Firewall → Options and\n"
                f"   allow incoming connections on ports "
                f"{', '.join(map(str, ports))}.[/]"
            )
        else:
            console.print(f"[{CD}]ℹ  Unknown OS — skipping firewall config.[/]")

    # ── Windows (netsh) ───────────────────────────────────────────────────────
    @classmethod
    def _windows(cls, ports: List[int], console: Console) -> None:
        if not cls._is_admin_win():
            console.print(
                f"[{CY}]⚠  Firewall: not running as Administrator.\n"
                f"   Re-run as Admin or manually allow TCP inbound on ports "
                f"{', '.join(map(str, ports))} in Windows Defender Firewall.[/]"
            )
            return

        opened, skipped = [], []
        for port in ports:
            rule = f"HydraCast RTSP {port}"
            exists = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule}"],
                capture_output=True, text=True,
            )
            if "No rules match" not in exists.stdout and exists.returncode == 0:
                skipped.append(port)
                continue
            r = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule}", "dir=in", "action=allow",
                 "protocol=TCP", f"localport={port}"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                opened.append(port)
            else:
                console.print(f"[{CR}]✘  netsh failed for port {port}: {r.stdout.strip()}[/]")

        if opened:
            console.print(
                f"[{CG}]✔  Firewall (netsh): opened TCP {', '.join(map(str, opened))}[/]"
            )
        if skipped:
            console.print(
                f"[{CD}]ℹ  Firewall: rules already exist for {', '.join(map(str, skipped))}[/]"
            )

    @staticmethod
    def _is_admin_win() -> bool:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:
            return False

    # ── Linux ─────────────────────────────────────────────────────────────────
    @classmethod
    def _linux(cls, ports: List[int], console: Console) -> None:
        if os.geteuid() != 0:  # type: ignore[attr-defined]
            console.print(
                f"[{CY}]⚠  Firewall: not running as root — streams on this machine\n"
                f"   are accessible locally.  To allow remote access run:\n"
                f"     sudo ufw allow <port>/tcp    (ufw)\n"
                f"     sudo iptables -I INPUT -p tcp --dport <port> -j ACCEPT  (iptables)[/]"
            )
            return

        tool = cls._detect_linux_tool()
        if tool is None:
            console.print(
                f"[{CD}]ℹ  No recognised firewall (ufw/firewalld/iptables) found — skipping.[/]"
            )
            return

        if tool == "ufw":
            cls._ufw(ports, console)
        elif tool == "firewalld":
            cls._firewalld(ports, console)
        else:
            cls._iptables(ports, console)

    @classmethod
    def _detect_linux_tool(cls) -> Optional[str]:
        if cls._linux_tool is not None:
            return cls._linux_tool
        for binary, key in [("ufw", "ufw"), ("firewall-cmd", "firewalld"),
                              ("iptables", "iptables")]:
            if shutil.which(binary):
                cls._linux_tool = key
                return key
        return None

    @classmethod
    def _ufw(cls, ports: List[int], console: Console) -> None:
        opened = []
        for port in ports:
            r = subprocess.run(
                ["ufw", "allow", f"{port}/tcp"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                opened.append(port)
            else:
                console.print(
                    f"[{CY}]⚠  ufw: {(r.stderr or r.stdout).strip()}[/]"
                )
        if opened:
            console.print(
                f"[{CG}]✔  Firewall (ufw): allowed TCP {', '.join(map(str, opened))}[/]"
            )

    @classmethod
    def _firewalld(cls, ports: List[int], console: Console) -> None:
        for port in ports:
            subprocess.run(
                ["firewall-cmd", "--permanent", "--add-port", f"{port}/tcp"],
                capture_output=True,
            )
        subprocess.run(["firewall-cmd", "--reload"], capture_output=True)
        console.print(
            f"[{CG}]✔  Firewall (firewalld): permanent rules added for "
            f"TCP {', '.join(map(str, ports))}[/]"
        )

    @classmethod
    def _iptables(cls, ports: List[int], console: Console) -> None:
        opened = []
        for port in ports:
            # Skip if rule already present
            already = subprocess.run(
                ["iptables", "-C", "INPUT", "-p", "tcp",
                 "--dport", str(port), "-j", "ACCEPT"],
                capture_output=True,
            )
            if already.returncode == 0:
                continue
            r = subprocess.run(
                ["iptables", "-I", "INPUT", "-p", "tcp",
                 "--dport", str(port), "-j", "ACCEPT"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                opened.append(port)
        if opened:
            console.print(
                f"[{CG}]✔  Firewall (iptables): opened TCP "
                f"{', '.join(map(str, opened))}\n"
                f"[{CD}]   Note: iptables rules are lost on reboot unless saved.[/]"
            )


# =============================================================================
# DEPENDENCY MANAGER
# =============================================================================
class DependencyManager:

    @staticmethod
    def _find_binary(name: str) -> Optional[str]:
        try:
            r = subprocess.run([name, "-version"], capture_output=True, timeout=8)
            if r.returncode == 0:
                return shutil.which(name) or name
        except Exception:
            pass
        local = BIN_DIR / name
        if local.exists():
            return str(local)
        return None

    @classmethod
    def check_ffmpeg(cls) -> Optional[str]:
        return cls._find_binary(FFMPEG_BIN_NAME)

    @classmethod
    def check_ffprobe(cls) -> Optional[str]:
        return cls._find_binary(FFPROBE_BIN_NAME)

    @staticmethod
    def _pick_mediamtx_url() -> Optional[str]:
        key = (OS_KEY, ARCH_KEY)
        if key in MEDIAMTX_URLS:
            return MEDIAMTX_URLS[key]
        for (os_, _), url in MEDIAMTX_URLS.items():
            if os_ == OS_KEY:
                return url
        return None

    @staticmethod
    def download_mediamtx(console: Console) -> bool:
        if MEDIAMTX_BIN.exists():
            console.print(f"[{CG}]✔  MediaMTX already present.[/]")
            return True

        url = DependencyManager._pick_mediamtx_url()
        if not url:
            console.print(f"[{CR}]✘  No MediaMTX build for {OS_KEY}/{ARCH_KEY}.[/]")
            return False

        archive = BIN_DIR / Path(url).name
        console.print(f"[{CY}]⬇  Downloading MediaMTX v{MEDIAMTX_VER} …[/]")

        try:
            def _progress(block_num: int, block_size: int, total_size: int) -> None:
                if total_size <= 0:
                    return
                pct    = min(100, block_num * block_size * 100 // total_size)
                filled = pct // 5
                bar    = "█" * filled + "░" * (20 - filled)
                print(f"\r  [{bar}] {pct:3d}%", end="", flush=True)

            urllib.request.urlretrieve(url, archive, reporthook=_progress)
            print()
        except Exception as exc:
            console.print(f"\n[{CR}]✘  Download failed: {exc}[/]")
            return False

        try:
            if archive.suffix in (".gz", ".tgz") or archive.name.endswith(".tar.gz"):
                with tarfile.open(archive, "r:gz") as tf:
                    for m in tf.getmembers():
                        bname = Path(m.name).name
                        if bname in ("mediamtx", "mediamtx.exe") and m.isfile():
                            m.name = MEDIAMTX_BIN.name
                            tf.extract(m, BIN_DIR)
                            break
            elif archive.suffix == ".zip":
                with zipfile.ZipFile(archive) as zf:
                    for name in zf.namelist():
                        if Path(name).name.lower().startswith("mediamtx"):
                            MEDIAMTX_BIN.write_bytes(zf.read(name))
                            break
            archive.unlink(missing_ok=True)
        except Exception as exc:
            console.print(f"[{CR}]✘  Extraction failed: {exc}[/]")
            return False

        if not IS_WIN:
            MEDIAMTX_BIN.chmod(MEDIAMTX_BIN.stat().st_mode | stat.S_IEXEC)

        console.print(f"[{CG}]✔  MediaMTX installed → {MEDIAMTX_BIN}[/]")
        return True


# =============================================================================
# CSV MANAGER
# =============================================================================
CSV_COLUMNS = [
    "stream_name", "port", "file_path", "weekdays",
    "start_position", "enabled",
    # v2 optional:
    "video_bitrate", "audio_bitrate", "hls_enabled",
]

CSV_TEMPLATE_ROWS = [
    ["Stream_1", "8554", "/path/to/video.mp4",         "ALL",         "00:00:00", "true",  "2500k", "128k", "false"],
    ["Stream_2", "8555", "/path/to/clip.mkv",           "Mon|Wed|Fri", "00:05:30", "true",  "4000k", "192k", "false"],
    ["Stream_3", "8556", "C:\\Videos\\show.avi",        "Sat|Sun",     "00:00:00", "false", "1500k", "128k", "false"],
    ["Stream_4", "8557", "/media/recordings/demo.mp4",  "Weekdays",    "00:10:00", "true",  "2500k", "128k", "true"],
]


class CSVManager:

    @staticmethod
    def create_template() -> None:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_COLUMNS)
            w.writerows(CSV_TEMPLATE_ROWS)

    @staticmethod
    def parse_weekdays(raw: str) -> List[int]:
        result: set = set()
        for part in re.split(r"[|,;/\s]+", raw.strip()):
            part = part.strip().lower()
            if not part:
                continue
            val = WEEKDAY_MAP.get(part)
            if val is None:
                continue
            if isinstance(val, list):
                result.update(val)
            else:
                result.add(val)
        return sorted(result) if result else list(range(7))

    @staticmethod
    def parse_bool(raw: str) -> bool:
        return raw.strip().lower() in ("true", "1", "yes", "on", "enabled")

    @staticmethod
    def normalize_position(pos: str) -> str:
        try:
            parts = pos.strip().split(":")
            if len(parts) == 1:
                parts = ["00", "00", parts[0]]
            elif len(parts) == 2:
                parts = ["00"] + parts
            h, m, s = parts
            return f"{int(h):02d}:{int(m):02d}:{int(float(s)):02d}"
        except Exception:
            return "00:00:00"

    @staticmethod
    def _sanitize_bitrate(raw: str, default: str) -> str:
        raw = raw.strip()
        if re.fullmatch(r"\d+[kKmM]?", raw):
            return raw.lower()
        return default

    @classmethod
    def load(cls) -> "List[StreamConfig]":
        if not CSV_FILE.exists():
            cls.create_template()
            raise FileNotFoundError(
                f"streams.csv not found → template created at:\n"
                f"  {CSV_FILE}\n"
                f"Edit it with your stream details, then restart HydraCast."
            )

        configs: List[StreamConfig] = []
        errors:  List[str]         = []

        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("streams.csv appears to be empty.")

            for i, row in enumerate(reader, start=2):
                name = row.get("stream_name", "").strip()
                if not name:
                    errors.append(f"Row {i}: stream_name is empty — skipped.")
                    continue

                try:
                    port = int(row.get("port", "0").strip())
                    if not (1024 <= port <= 65535):
                        raise ValueError("out of range")
                except Exception:
                    errors.append(
                        f"Row {i} ({name}): invalid port '{row.get('port')}' — skipped."
                    )
                    continue

                file_path = Path(row.get("file_path", "").strip())
                weekdays  = cls.parse_weekdays(row.get("weekdays", "ALL"))
                start_pos = cls.normalize_position(row.get("start_position", "00:00:00"))
                enabled   = cls.parse_bool(row.get("enabled", "true"))
                vid_br    = cls._sanitize_bitrate(row.get("video_bitrate", "2500k"), "2500k")
                aud_br    = cls._sanitize_bitrate(row.get("audio_bitrate", "128k"),  "128k")
                hls_en    = cls.parse_bool(row.get("hls_enabled", "false"))

                configs.append(StreamConfig(
                    name=name,
                    port=port,
                    file_path=file_path,
                    weekdays=weekdays,
                    start_position=start_pos,
                    enabled=enabled,
                    row_index=i - 2,
                    video_bitrate=vid_br,
                    audio_bitrate=aud_br,
                    hls_enabled=hls_en,
                ))

        for e in errors:
            logging.warning("CSV: %s", e)

        seen: Dict[int, str] = {}
        for c in configs:
            if c.port in seen:
                raise ValueError(
                    f"Duplicate port {c.port}: '{c.name}' and '{seen[c.port]}'."
                )
            seen[c.port] = c.name

        if not configs:
            raise ValueError("No valid streams found in streams.csv.")

        return configs


# =============================================================================
# MEDIAMTX YAML CONFIG  (v1.9.x-compatible)
# =============================================================================
class MediaMTXConfig:
    """
    Generates a MediaMTX v1.9.x YAML config.

    Fields removed from v1.0 (caused "json: unknown field" errors in v1.9.x):
      ✘ rtspEncryption  — dropped in v1.x; plain RTSP is implicit default
      ✘ hls: no         — replaced by hlsDisable: yes
      ✘ webrtc: no      — replaced by webrtcDisable: yes
      ✘ srt: no         — replaced by srtDisable: yes
    """

    @staticmethod
    def write(state: StreamState) -> Path:
        cfg   = state.config
        port  = cfg.port
        log_f = (LOGS_DIR / f"mediamtx_{port}.log").resolve()
        cfg_f = CONFIGS_DIR / f"mediamtx_{port}.yml"
        addr  = LISTEN_ADDR

        # Optional HLS section
        if cfg.hls_enabled:
            proto_section = (
                f"hlsAddress: {addr}:{cfg.hls_port}\n"
                f"hlsAlwaysRemux: yes\n"
                f"hlsSegmentCount: 3\n"
                f"hlsSegmentDuration: 2s\n"
                f"hlsAllowOrigin: \"*\"\n"
                f"\nwebrtcDisable: yes\n"
                f"srtDisable: yes\n"
                f"\npaths:\n"
                f"  live:\n"
                f"    source: publisher\n"
            )
        else:
            proto_section = (
                f"hlsDisable: yes\n"
                f"webrtcDisable: yes\n"
                f"srtDisable: yes\n"
                f"\npaths:\n"
                f"  live: {{}}\n"
            )

        yaml_text = (
            f"# HydraCast v{APP_VER} — {cfg.name} (:{port})\n"
            f"logLevel: error\n"
            f"logDestinations: [file]\n"
            f"logFile: {str(log_f).replace(chr(92), '/')}\n"
            f"\n"
            f"# RTSP — plain (no encryption; default in MediaMTX v1.x)\n"
            f"rtspAddress: {addr}:{port}\n"
            f"readTimeout: 15s\n"
            f"writeTimeout: 15s\n"
            f"writeQueueSize: 1024\n"
            f"udpMaxPayloadSize: 1472\n"
            f"\n"
            f"{proto_section}"
        )

        cfg_f.write_text(yaml_text, encoding="utf-8")
        return cfg_f


# =============================================================================
# FFPROBE — get video duration
# =============================================================================
def probe_duration(file_path: Path) -> float:
    try:
        r = subprocess.run(
            [FFPROBE_PATH, "-v", "quiet",
             "-show_entries", "format=duration",
             "-of", "csv=p=0", str(file_path)],
            capture_output=True, text=True, timeout=20,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


# =============================================================================
# LOG BUFFER  (ring buffer shown in TUI)
# =============================================================================
class LogBuffer:

    def __init__(self, capacity: int = 600) -> None:
        self._entries: List[Tuple[str, str]] = []
        self._lock = threading.Lock()
        self._cap  = capacity

    def add(self, msg: str, level: str = "INFO") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._entries.append((f"[{ts}] {msg}", level))
            if len(self._entries) > self._cap:
                self._entries.pop(0)

    def last(self, n: int = 9) -> "List[Tuple[str, str]]":
        with self._lock:
            return list(self._entries[-n:])


# =============================================================================
# STREAM WORKER  (one per stream — manages MediaMTX + FFmpeg)
# =============================================================================
class StreamWorker:
    MAX_AUTO_RESTARTS = 8
    BACKOFF           = [5, 10, 20, 40, 60, 120, 120, 120]
    MTX_READY_TIMEOUT = 10.0   # seconds to wait for MediaMTX port to bind

    _FFMPEG_PROGRESS_RE = re.compile(r"^(\w+)=(.+)$")

    def __init__(self, state: StreamState, glog: LogBuffer) -> None:
        self.state = state
        self.glog  = glog
        self._stop = threading.Event()

    def _log(self, msg: str, level: str = "INFO") -> None:
        full = f"[{self.state.config.name}] {msg}"
        self.state.log_add(full)
        self.glog.add(full, level)
        logging.log(
            logging.WARNING if level == "WARN" else
            (logging.ERROR if level == "ERROR" else logging.INFO),
            full,
        )

    # ── public API ────────────────────────────────────────────────────────────
    def start(self) -> bool:
        cfg = self.state.config
        self._stop.clear()

        if not cfg.file_path.exists():
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"File not found: {cfg.file_path}"
            self._log(self.state.error_msg, "ERROR")
            return False

        self.state.status = StreamStatus.STARTING

        if self.state.duration == 0.0:
            self.state.duration = probe_duration(cfg.file_path)

        # ── Kill any orphan already holding this port ─────────────────────────
        if _port_in_use(cfg.port):
            self._log(f"Port {cfg.port} occupied — killing orphan …", "WARN")
            _kill_orphan_on_port(cfg.port)
            time.sleep(0.8)
            if _port_in_use(cfg.port):
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = f"Port {cfg.port} still in use after orphan kill"
                self._log(self.state.error_msg, "ERROR")
                return False

        # Write MediaMTX YAML (v1.9.x-safe, no deprecated fields)
        mtx_cfg = MediaMTXConfig.write(self.state)

        if not self._start_mediamtx(mtx_cfg):
            return False

        # ── Wait until MediaMTX is *actually* listening ───────────────────────
        self._log(f"Waiting for MediaMTX to bind :{cfg.port} …")
        if not _wait_for_port(cfg.port, timeout=self.MTX_READY_TIMEOUT):
            self._log(
                f"MediaMTX did not bind :{cfg.port} within "
                f"{self.MTX_READY_TIMEOUT:.0f}s — aborting.", "ERROR"
            )
            self._kill_mediamtx()
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX port-bind timeout (:{cfg.port})"
            return False

        if not self._start_ffmpeg():
            self._kill_mediamtx()
            return False

        self.state.status     = StreamStatus.LIVE
        self.state.started_at = datetime.now()
        self._log(f"Live → {cfg.rtsp_url}")
        if cfg.hls_enabled:
            self._log(f"HLS  → {cfg.hls_url}")

        threading.Thread(
            target=self._monitor, daemon=True, name=f"mon-{cfg.port}"
        ).start()
        return True

    def stop(self) -> None:
        self._stop.set()
        self._kill_ffmpeg()
        time.sleep(0.4)
        self._kill_mediamtx()
        self.state.status      = StreamStatus.STOPPED
        self.state.progress    = 0.0
        self.state.current_pos = 0.0
        self.state.fps         = 0.0
        self.state.bitrate     = "—"
        self.state.speed       = "—"
        self._log("Stream stopped.")

    def restart(self) -> None:
        self._log("Restarting …")
        self.stop()
        time.sleep(0.8)
        self.state.restart_count += 1
        self.start()

    # ── launchers ─────────────────────────────────────────────────────────────
    def _start_mediamtx(self, cfg_file: Path) -> bool:
        log_f = LOGS_DIR / f"mediamtx_{self.state.config.port}.log"
        try:
            with open(log_f, "a") as lf:
                kw: Dict[str, Any] = dict(stdout=lf, stderr=lf)
                if IS_WIN:
                    kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[assignment]
                proc = subprocess.Popen([str(MEDIAMTX_BIN), str(cfg_file)], **kw)
            self.state.mtx_proc = proc
            self._log(f"MediaMTX PID {proc.pid} on :{self.state.config.port}")
            return True
        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR")
            return False

    def _start_ffmpeg(self) -> bool:
        cfg = self.state.config
        cmd = [
            str(FFMPEG_PATH),
            "-hide_banner", "-loglevel", "error",
            "-re",
            "-ss", str(int(cfg.start_seconds)),
            "-stream_loop", "-1",
            "-i", str(cfg.file_path),
            # Video: H.264 baseline (max client compatibility)
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", cfg.video_bitrate,
            "-pix_fmt", "yuv420p",
            "-g", "50",
            # Audio: AAC stereo
            "-c:a", "aac",
            "-b:a", cfg.audio_bitrate,
            "-ar", "44100",
            "-ac", "2",
            # Progress to stdout
            "-progress", "pipe:1",
            "-nostats",
            # Push to MediaMTX on loopback (always 127.0.0.1)
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            f"rtsp://127.0.0.1:{cfg.port}/live",
        ]
        try:
            kw: Dict[str, Any] = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            if IS_WIN:
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[assignment]
            proc = subprocess.Popen(cmd, **kw)
            self.state.ffmpeg_proc = proc

            if IS_LINUX and CPU_COUNT > 1:
                try:
                    core = cfg.row_index % CPU_COUNT
                    psutil.Process(proc.pid).cpu_affinity([core])
                    self._log(f"FFmpeg PID {proc.pid} → CPU core {core}")
                except Exception:
                    self._log(f"FFmpeg PID {proc.pid} (no affinity)")
            else:
                self._log(f"FFmpeg PID {proc.pid}")

            return True
        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"FFmpeg launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR")
            return False

    # ── progress monitor ──────────────────────────────────────────────────────
    def _monitor(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc is None:
            return

        buf: Dict[str, str] = {}

        while not self._stop.is_set():
            if proc.poll() is not None:
                break
            try:
                line = proc.stdout.readline()  # type: ignore[union-attr]
                if not line:
                    time.sleep(0.05)
                    continue
                m = self._FFMPEG_PROGRESS_RE.match(line.strip())
                if not m:
                    continue
                k, v = m.group(1), m.group(2).strip()
                buf[k] = v
                if k == "progress":
                    self._apply_progress(buf)
                    buf = {}
            except Exception:
                time.sleep(0.05)

        if not self._stop.is_set():
            ret = proc.returncode if proc.returncode is not None else -1
            stderr_txt = ""
            try:
                if proc.stderr:
                    stderr_txt = proc.stderr.read(400)
            except Exception:
                pass
            if ret in (0, 255):
                self.state.status = StreamStatus.STOPPED
                self._log(f"FFmpeg exited normally (code {ret}).")
            else:
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = stderr_txt[:200].strip() or f"FFmpeg exited code {ret}"
                self._log(self.state.error_msg, "ERROR")
                self._auto_restart()

    def _apply_progress(self, data: Dict[str, str]) -> None:
        try:
            out_us = int(data.get("out_time_us", "0"))
            if out_us > 0 and self.state.duration > 0:
                pos          = (out_us / 1_000_000.0) % self.state.duration
                self.state.current_pos = pos
                self.state.loop_count  = int(out_us / 1_000_000.0 // self.state.duration)
                self.state.progress    = min(99.9, pos / self.state.duration * 100.0)
            fps_raw = data.get("fps", "0")
            self.state.fps     = float(fps_raw) if fps_raw not in ("", "N/A") else 0.0
            self.state.bitrate = data.get("bitrate", "—").replace("kbits/s", "kb/s") or "—"
            self.state.speed   = data.get("speed", "—").strip() or "—"
        except Exception:
            pass

    def _auto_restart(self) -> None:
        n = self.state.restart_count
        if n >= self.MAX_AUTO_RESTARTS:
            self._log(f"Max auto-restarts ({self.MAX_AUTO_RESTARTS}) reached — giving up.", "ERROR")
            return
        delay = self.BACKOFF[min(n, len(self.BACKOFF) - 1)]
        self._log(f"Auto-restart #{n + 1} in {delay}s …", "WARN")
        for _ in range(delay * 10):
            if self._stop.is_set():
                return
            time.sleep(0.1)
        if not self._stop.is_set():
            self.state.restart_count += 1
            self._kill_mediamtx()
            self.start()

    # ── killers ───────────────────────────────────────────────────────────────
    def _kill_ffmpeg(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass
        self.state.ffmpeg_proc = None

    def _kill_mediamtx(self) -> None:
        proc = self.state.mtx_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass
        self.state.mtx_proc = None


# =============================================================================
# STREAM MANAGER
# =============================================================================
class StreamManager:

    def __init__(self, configs: "List[StreamConfig]", glog: LogBuffer) -> None:
        self.states:   List[StreamState]       = [StreamState(config=c) for c in configs]
        self._workers: Dict[str, StreamWorker] = {}
        self._glog    = glog
        self._running = False
        self._sched_t: Optional[threading.Thread] = None

    def _worker(self, state: StreamState) -> StreamWorker:
        if state.config.name not in self._workers:
            self._workers[state.config.name] = StreamWorker(state, self._glog)
        return self._workers[state.config.name]

    def start_stream(self, state: StreamState) -> None:
        if state.status in (StreamStatus.LIVE, StreamStatus.STARTING):
            return
        w = self._worker(state)
        threading.Thread(target=w.start, daemon=True,
                         name=f"start-{state.config.port}").start()

    def stop_stream(self, state: StreamState) -> None:
        w = self._workers.get(state.config.name)
        if w:
            threading.Thread(target=w.stop, daemon=True,
                             name=f"stop-{state.config.port}").start()
        else:
            state.status = StreamStatus.STOPPED

    def restart_stream(self, state: StreamState) -> None:
        w = self._worker(state)
        threading.Thread(target=w.restart, daemon=True,
                         name=f"rst-{state.config.port}").start()

    def start_all(self) -> None:
        for s in self.states:
            if not s.config.enabled:
                s.status = StreamStatus.DISABLED
            elif s.config.is_scheduled_today():
                self.start_stream(s)
            else:
                s.status = StreamStatus.SCHEDULED

    def stop_all(self) -> None:
        for s in self.states:
            self.stop_stream(s)

    def _scheduler_loop(self) -> None:
        while self._running:
            for s in self.states:
                if not s.config.enabled:
                    s.status = StreamStatus.DISABLED
                    continue
                should_run = s.config.is_scheduled_today()
                is_active  = s.status in (StreamStatus.LIVE, StreamStatus.STARTING)
                if should_run and not is_active:
                    self._glog.add(f"[{s.config.name}] Scheduler: starting.", "INFO")
                    self.start_stream(s)
                elif not should_run and is_active:
                    self._glog.add(f"[{s.config.name}] Scheduler: stopping (off-schedule).", "INFO")
                    self.stop_stream(s)
                elif not should_run and not is_active:
                    if s.status not in (StreamStatus.SCHEDULED, StreamStatus.DISABLED):
                        s.status = StreamStatus.SCHEDULED
            for _ in range(600):
                if not self._running:
                    return
                time.sleep(0.1)

    def run_scheduler(self) -> None:
        self._running = True
        self._sched_t = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="scheduler"
        )
        self._sched_t.start()

    def shutdown(self) -> None:
        self._running = False
        self.stop_all()
        deadline = time.time() + 10
        while time.time() < deadline:
            if not any(s.status in (StreamStatus.LIVE, StreamStatus.STARTING)
                       for s in self.states):
                break
            time.sleep(0.2)

    def export_urls(self, path: Optional[Path] = None) -> Path:
        """Write all stream URLs to a text file and return its path."""
        out = path or (BASE_DIR / "stream_urls.txt")
        lines = [
            f"# HydraCast {APP_VER} — Stream URLs",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for s in self.states:
            cfg = s.config
            lines += [
                f"[{cfg.name}]",
                f"  RTSP (local)    : {cfg.rtsp_url}",
                f"  RTSP (external) : {cfg.rtsp_url_external}",
            ]
            if cfg.hls_enabled:
                lines.append(f"  HLS             : {cfg.hls_url}")
            lines.append("")
        out.write_text("\n".join(lines), encoding="utf-8")
        return out


# =============================================================================
# TUI  (Rich-based terminal interface)
# =============================================================================
BANNER_TEXT = """\
[bright_cyan]  ██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗  ██████╗ █████╗ ███████╗████████╗[/]
[bright_cyan]  ██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝[/]
[bright_cyan]  ███████║ ╚████╔╝ ██║  ██║██████╔╝███████║██║     ███████║███████╗   ██║   [/]
[cyan]  ██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║██║     ██╔══██║╚════██║   ██║   [/]
[cyan]  ██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║╚██████╗██║  ██║███████║   ██║   [/]
[dim cyan]  ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   [/]"""


class TUI:
    def __init__(self, manager: StreamManager, glog: LogBuffer) -> None:
        self.manager  = manager
        self.glog     = glog
        self.selected = 0

    @staticmethod
    def _progress_bar(pct: float, width: int = 22) -> Text:
        if pct <= 0:
            t = Text()
            t.append("─" * width, style="dim white")
            t.append("   0.0%", style="dim white")
            return t
        filled = max(1, round(pct / 100 * width))
        empty  = width - filled
        t = Text()
        for i in range(filled):
            frac  = i / max(1, width)
            style = CG if frac < 0.55 else (CY if frac < 0.80 else CM)
            t.append("█", style=style)
        t.append("░" * empty, style="dim white")
        label_col = CM if pct >= 80 else (CY if pct >= 55 else CG)
        t.append(f"  {pct:5.1f}%", style=f"bold {label_col}")
        return t

    def _streams_table(self) -> Table:
        tbl = Table(
            box=box.SIMPLE_HEAD, border_style="bright_black",
            header_style=f"bold {CW}", expand=True, padding=(0, 1), show_edge=True,
        )
        tbl.add_column("#",        style=CD,          width=3,      no_wrap=True)
        tbl.add_column("STREAM",   style=CW,          min_width=14, no_wrap=True)
        tbl.add_column("PORT",     style=CC,          width=6,      no_wrap=True)
        tbl.add_column("SCHEDULE", style=CW,          width=11,     no_wrap=True)
        tbl.add_column("STATUS",                      width=11,     no_wrap=True)
        tbl.add_column("PROGRESS",                    min_width=30, no_wrap=True)
        tbl.add_column("TIME",     style=CD,          width=14,     no_wrap=True)
        tbl.add_column("FPS",      style=CD,          width=5,      no_wrap=True)
        tbl.add_column("LOOP",     style=CD,          width=6,      no_wrap=True)
        tbl.add_column("RTSP URL", style="dim cyan",  min_width=22, no_wrap=True)

        for i, st in enumerate(self.manager.states):
            cfg = st.config
            s   = st.status

            stat_t = Text()
            if s == StreamStatus.ERROR and st.error_msg:
                stat_t.append(" ● ", style=CR)
                stat_t.append("ERROR", style=f"bold {CR}")
            else:
                stat_t.append(f" {s.dot} ", style=s.color)
                stat_t.append(s.label, style=f"bold {s.color}")

            row_style    = "on grey11" if i == self.selected else ""
            name_display = f"▶ {cfg.name}" if i == self.selected else f"  {cfg.name}"
            if cfg.hls_enabled:
                name_display += " [HLS]"

            tbl.add_row(
                str(i + 1),
                name_display,
                str(cfg.port),
                cfg.weekdays_display(),
                stat_t,
                self._progress_bar(st.progress),
                st.format_pos(),
                f"{st.fps:.0f}" if st.fps > 0 else "—",
                f"×{st.loop_count}" if st.loop_count > 0 else "—",
                cfg.rtsp_url,
                style=row_style,
            )

        return tbl

    def _system_panel(self) -> Panel:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()

        live_n  = sum(1 for s in self.manager.states if s.status == StreamStatus.LIVE)
        err_n   = sum(1 for s in self.manager.states if s.status == StreamStatus.ERROR)
        sched_n = sum(1 for s in self.manager.states if s.status == StreamStatus.SCHEDULED)

        t = Text()
        t.append("CPU  ", style=CD); t.append_text(self._progress_bar(cpu, width=14)); t.append("\n")
        t.append("MEM  ", style=CD); t.append_text(self._progress_bar(mem.percent, width=14)); t.append("\n\n")
        t.append("Cores  ", style=CD); t.append(str(CPU_COUNT), style=CC)
        t.append("  |  Total  ", style=CD); t.append(str(len(self.manager.states)), style=CW)
        t.append("\n")
        t.append("LIVE   ", style=CD); t.append(str(live_n), style=CG)
        t.append("   SCHED  ", style=CD); t.append(str(sched_n), style=CC)
        t.append("   ERR  ", style=CD); t.append(str(err_n), style=(CR if err_n else CD))
        t.append("\n\n")
        t.append(f"  LAN: {_local_ip()}", style=CD); t.append("\n")
        t.append(datetime.now().strftime("  %a  %Y-%m-%d  %H:%M:%S"), style=CD)

        return Panel(t, title=f"[bold {CW}]SYSTEM[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0, 1))

    def _log_panel(self) -> Panel:
        entries = self.glog.last(9)
        t = Text()
        colors = {"INFO": CW, "WARN": CY, "ERROR": CR}
        for msg, lvl in entries:
            t.append(msg + "\n", style=colors.get(lvl, CW))
        return Panel(t, title=f"[bold {CW}]EVENT LOG[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0, 1))

    @staticmethod
    def _hotkeys() -> Text:
        t = Text(justify="center")
        for k, v in [
            ("↑↓/1-9", "Select"), ("R", "Restart"), ("S", "Stop"), ("T", "Start"),
            ("A", "Start All"),   ("X", "Stop All"), ("L", "Reload CSV"),
            ("U", "Export URLs"), ("Q", "Quit"),
        ]:
            t.append(f" [{k}]", style=f"bold {CC}")
            t.append(f" {v} ", style=CD)
        return t

    def render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="banner",  size=8),
            Layout(name="streams", ratio=1),
            Layout(name="bottom",  size=13),
            Layout(name="keys",    size=3),
        )

        banner_txt  = Text.from_markup(BANNER_TEXT)
        sub = Text(
            f"  Multi-Stream RTSP Weekly Scheduler  ·  v{APP_VER}  ·  {APP_AUTHOR}  ·  {APP_GITHUB}",
            style="dim white", justify="center",
        )
        banner_full = Text()
        banner_full.append_text(banner_txt)
        banner_full.append("\n")
        banner_full.append_text(sub)
        layout["banner"].update(Align.center(banner_full, vertical="middle"))

        layout["streams"].update(
            Panel(
                self._streams_table(),
                title=(f"[bold {CW}]STREAMS[/]  "
                       f"[dim]({len(self.manager.states)} configured)[/]"),
                border_style=CC, box=box.ROUNDED, padding=(0, 0),
            )
        )

        layout["bottom"].split_row(
            Layout(self._system_panel(), name="sys", ratio=1),
            Layout(self._log_panel(),    name="log", ratio=3),
        )

        layout["keys"].update(
            Panel(
                Align.center(self._hotkeys(), vertical="middle"),
                border_style="bright_black", box=box.SIMPLE, padding=(0, 0),
            )
        )
        return layout


# =============================================================================
# KEYBOARD HANDLER  (cross-platform, non-blocking)
# =============================================================================
class KeyboardHandler:

    def __init__(self) -> None:
        self._q: "queue.Queue[str]" = queue.Queue()
        self._running = False
        self._t: Optional[threading.Thread] = None

    def start(self) -> None:
        self._running = True
        self._t = threading.Thread(
            target=(self._win_loop if IS_WIN else self._unix_loop),
            daemon=True, name="keyboard",
        )
        self._t.start()

    def stop(self) -> None:
        self._running = False

    def get(self) -> Optional[str]:
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def _win_loop(self) -> None:
        import msvcrt  # type: ignore
        while self._running:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    ch2 = msvcrt.getch()
                    mapping = {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}
                    self._q.put(mapping.get(ch2, ""))
                else:
                    try:
                        self._q.put(ch.decode("utf-8").upper())
                    except Exception:
                        pass
            time.sleep(0.04)

    def _unix_loop(self) -> None:
        import tty, termios, select  # type: ignore
        fd = sys.stdin.fileno()
        try:
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            while self._running:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not r:
                    continue
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r2:
                        seq = sys.stdin.read(2)
                        mapping = {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}
                        self._q.put(mapping.get(seq, "ESC"))
                    else:
                        self._q.put("ESC")
                else:
                    self._q.put(ch.upper())
        except Exception:
            pass
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass


# =============================================================================
# MAIN
# =============================================================================
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="hydracast",
        description=f"{APP_NAME} v{APP_VER} — Multi-Stream RTSP Weekly Scheduler",
    )
    p.add_argument(
        "--no-firewall", action="store_true",
        help="Skip automatic firewall port-opening.",
    )
    p.add_argument(
        "--listen", metavar="IP", default="0.0.0.0",
        help="IP address for MediaMTX to bind on (default: 0.0.0.0 = all interfaces).",
    )
    p.add_argument(
        "--list-ports", action="store_true",
        help="Print which ports would be opened in the firewall, then exit.",
    )
    p.add_argument(
        "--export-urls", action="store_true",
        help="Write stream_urls.txt at startup with all RTSP/HLS URLs.",
    )
    return p.parse_args()


def _preflight(console: Console) -> "List[StreamConfig]":
    global FFMPEG_PATH, FFPROBE_PATH

    console.rule(f"[{CC}]{APP_NAME} v{APP_VER}[/]  Pre-flight checks")
    console.print()
    console.print(f"[{CD}]  OS        : {platform.system()} {platform.release()} ({ARCH_KEY})[/]")
    console.print(f"[{CD}]  Python    : {sys.version.split()[0]}[/]")
    console.print(f"[{CD}]  CPU cores : {CPU_COUNT}[/]")
    console.print(f"[{CD}]  LAN IP    : {_local_ip()}[/]")
    console.print(f"[{CD}]  Bind addr : {LISTEN_ADDR}[/]")
    console.print()

    if not DependencyManager.download_mediamtx(console):
        console.print(f"[{CR}]✘  Cannot continue without MediaMTX.[/]")
        sys.exit(1)

    ffmpeg = DependencyManager.check_ffmpeg()
    if not ffmpeg:
        console.print(
            f"[{CR}]✘  FFmpeg not found in PATH or bin/[/]\n"
            f"[{CY}]   Install it first:[/]\n"
            f"       Linux  : sudo apt install ffmpeg   |   sudo dnf install ffmpeg\n"
            f"       Windows: https://www.gyan.dev/ffmpeg/builds/\n"
            f"       macOS  : brew install ffmpeg\n"
            f"       Then place ffmpeg(.exe) + ffprobe(.exe) in PATH or in bin/."
        )
        sys.exit(1)
    FFMPEG_PATH = ffmpeg
    console.print(f"[{CG}]✔  FFmpeg  : {FFMPEG_PATH}[/]")

    ffprobe = DependencyManager.check_ffprobe()
    if ffprobe:
        FFPROBE_PATH = ffprobe
    console.print(f"[{CG}]✔  FFprobe : {FFPROBE_PATH}[/]")

    try:
        configs = CSVManager.load()
    except FileNotFoundError as exc:
        console.print(f"\n[{CY}]⚠  {exc}[/]")
        sys.exit(0)
    except Exception as exc:
        console.print(f"[{CR}]✘  CSV error: {exc}[/]")
        sys.exit(1)

    console.print(f"[{CG}]✔  Loaded {len(configs)} stream(s) from streams.csv[/]")

    # Firewall
    enabled_ports = [c.port for c in configs if c.enabled]
    if enabled_ports:
        console.print()
        FirewallManager.open_ports(enabled_ports, console)

    console.print()
    time.sleep(0.6)
    return configs


def main() -> None:
    global NO_FIREWALL, LISTEN_ADDR

    args = _parse_args()
    NO_FIREWALL = args.no_firewall
    LISTEN_ADDR = args.listen

    console = Console(force_terminal=True, highlight=False)

    # --list-ports fast exit
    if args.list_ports:
        try:
            cfgs = CSVManager.load()
        except Exception as exc:
            console.print(f"[{CR}]✘  {exc}[/]")
            sys.exit(1)
        console.print(f"[{CC}]Ports that would be opened in the firewall:[/]")
        for c in cfgs:
            if c.enabled:
                hls_note = f"  + HLS :{c.hls_port}" if c.hls_enabled else ""
                console.print(f"  {c.name:20s}  TCP :{c.port}{hls_note}")
        sys.exit(0)

    configs = _preflight(console)

    logging.basicConfig(
        filename=LOGS_DIR / "hydracast.log",
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    glog    = LogBuffer()
    manager = StreamManager(configs, glog)
    tui     = TUI(manager, glog)
    kb      = KeyboardHandler()

    _shutdown = threading.Event()

    def _sig_handler(sig: int, _frame: Any) -> None:
        _shutdown.set()

    signal.signal(signal.SIGINT,  _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    glog.add(f"{APP_NAME} v{APP_VER} started — {len(configs)} streams configured.")
    manager.start_all()
    manager.run_scheduler()
    kb.start()

    if args.export_urls:
        url_file = manager.export_urls()
        glog.add(f"Stream URLs exported → {url_file.name}", "INFO")

    n = len(manager.states)

    with Live(
        tui.render(),
        console=console,
        refresh_per_second=2,
        screen=True,
        transient=False,
    ) as live:
        while not _shutdown.is_set():
            key = kb.get()
            if key:
                sel   = tui.selected
                state = manager.states[sel] if manager.states else None

                if key in ("Q", "ESC"):
                    _shutdown.set()
                    break
                elif key in ("UP", "K"):
                    tui.selected = max(0, sel - 1)
                elif key in ("DOWN", "J"):
                    tui.selected = min(n - 1, sel + 1)
                elif key.isdigit():
                    idx = int(key) - 1
                    if 0 <= idx < n:
                        tui.selected = idx
                elif key == "R" and state:
                    glog.add(f"Manual restart: {state.config.name}")
                    manager.restart_stream(state)
                elif key == "S" and state:
                    glog.add(f"Manual stop: {state.config.name}")
                    manager.stop_stream(state)
                elif key == "T" and state:
                    glog.add(f"Manual start: {state.config.name}")
                    manager.start_stream(state)
                elif key == "A":
                    glog.add("Manual start-all triggered.")
                    manager.start_all()
                elif key == "X":
                    glog.add("Manual stop-all triggered.")
                    manager.stop_all()
                elif key == "L":
                    try:
                        new_cfgs = CSVManager.load()
                        glog.add(f"CSV reloaded: {len(new_cfgs)} streams found.", "INFO")
                    except Exception as exc:
                        glog.add(f"CSV reload error: {exc}", "ERROR")
                elif key == "U":
                    try:
                        url_file = manager.export_urls()
                        glog.add(f"URLs exported → {url_file.name}", "INFO")
                    except Exception as exc:
                        glog.add(f"URL export error: {exc}", "ERROR")

            live.update(tui.render())
            time.sleep(0.45)

    kb.stop()
    console.clear()
    console.print(f"\n[{CY}]⏳  Stopping all streams … please wait.[/]")
    manager.shutdown()
    for f in CONFIGS_DIR.glob("mediamtx_*.yml"):
        try:
            f.unlink()
        except Exception:
            pass
    console.print(f"[{CG}]✔  HydraCast stopped cleanly. Goodbye.[/]\n")


if __name__ == "__main__":
    main()
