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
#  Version : 4.0.0
#  GitHub  : https://github.com/rhshourav/HydraCast
#  License : MIT
#
#  v4.0 changelog
#  ─────────────
#  NEW      Complete Web UI redesign — production-grade dark glassmorphism aesthetic
#  NEW      Animated progress bars (larger, click-to-seek, live drag-seek)
#  NEW      Live HLS/RTSP preview panel inside seek modal
#  NEW      Multi-video playlist manager — drag-to-reorder, priority system
#  NEW      Upload fixed: root dir is script's directory, multi-subdir support
#  NEW      Playlist priority column (#N) in CSV and editor
#  NEW      Stream detail modal with live stats refresh
#  NEW      Keyboard shortcuts overlay in Web UI
#  FIXED    All v3.1 seek/race-condition fixes retained
#  IMPROVED Security headers, path-traversal guard, upload size cap
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
import random
import hashlib
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

if sys.version_info < (3, 8):
    sys.exit("HydraCast requires Python 3.8 or newer.")

# ── Bootstrap ─────────────────────────────────────────────────────────────────
def _bootstrap() -> None:
    import importlib
    needed = {"rich": "rich>=13.0", "psutil": "psutil>=5.9"}
    missing = [pkg for mod, pkg in needed.items() if not importlib.util.find_spec(mod)]
    if not missing:
        return
    print(f"[HydraCast] Installing: {', '.join(missing)} …")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", *missing, "-q"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
from rich.prompt import Prompt
from rich import box
import psutil

# =============================================================================
# CONSTANTS & PATHS
# =============================================================================
APP_NAME   = "HydraCast"
APP_VER    = "4.0.0"
APP_AUTHOR = "rhshourav"
APP_GITHUB = "https://github.com/rhshourav/HydraCast"

IS_WIN   = platform.system() == "Windows"
IS_MAC   = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
OS_KEY   = "windows" if IS_WIN else "linux"
ARCH_KEY = platform.machine()
CPU_COUNT = max(1, multiprocessing.cpu_count())

BASE_DIR    = Path(__file__).parent.resolve()
BIN_DIR     = BASE_DIR / "bin"
CONFIGS_DIR = BASE_DIR / "configs"
LOGS_DIR    = BASE_DIR / "logs"
MEDIA_DIR   = BASE_DIR / "media"       # root upload dir = script folder/media
CSV_FILE    = BASE_DIR / "streams.csv"
EVENTS_FILE = BASE_DIR / "events.csv"
WEB_PORT    = 8080
UPLOAD_MAX_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB

for _d in (BIN_DIR, CONFIGS_DIR, LOGS_DIR, MEDIA_DIR):
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

FFMPEG_BIN_NAME  = "ffmpeg.exe"  if IS_WIN else "ffmpeg"
FFPROBE_BIN_NAME = "ffprobe.exe" if IS_WIN else "ffprobe"
FFMPEG_PATH:  str = FFMPEG_BIN_NAME
FFPROBE_PATH: str = FFPROBE_BIN_NAME

WEEKDAY_MAP: Dict[str, Any] = {
    "mon": 0, "monday": 0, "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2, "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4, "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
    "all": list(range(7)), "everyday": list(range(7)),
    "weekdays": list(range(5)), "weekends": [5, 6],
}
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

SUPPORTED_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".ts", ".m2ts", ".flv",
    ".wmv", ".webm", ".mpg", ".mpeg", ".m4v", ".3gp", ".ogv",
    ".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a",
}

CG = "bright_green"; CR = "bright_red"; CY = "yellow"
CC = "bright_cyan";  CW = "white";       CD = "dim white"
CM = "bright_magenta"; CB = "bright_blue"

NO_FIREWALL  = False
LISTEN_ADDR  = "0.0.0.0"
_MANAGER: Optional["StreamManager"] = None


# =============================================================================
# DATA MODELS
# =============================================================================
class StreamStatus(Enum):
    STOPPED   = ("●", "dim white",     "STOPPED")
    STARTING  = ("◌", "yellow",        "STARTING")
    LIVE      = ("●", "bright_green",  "LIVE")
    SCHEDULED = ("◷", "bright_cyan",   "SCHED")
    ERROR     = ("●", "bright_red",    "ERROR")
    DISABLED  = ("⊘", "dim",           "DISABLED")
    ONESHOT   = ("◈", "bright_magenta","ONESHOT")

    @property
    def dot(self)   -> str: return self.value[0]
    @property
    def color(self) -> str: return self.value[1]
    @property
    def label(self) -> str: return self.value[2]


@dataclass
class OneShotEvent:
    event_id:    str
    stream_name: str
    file_path:   Path
    play_at:     datetime
    post_action: str
    played:      bool = False
    start_pos:   str  = "00:00:00"


@dataclass
class PlaylistItem:
    file_path:      Path
    start_position: str = "00:00:00"
    weight:         int = 1
    priority:       int = 999   # lower = plays earlier


@dataclass
class StreamConfig:
    name:           str
    port:           int
    playlist:       List[PlaylistItem]
    weekdays:       List[int]
    enabled:        bool
    shuffle:        bool  = False
    stream_path:    str   = ""
    video_bitrate:  str   = "2500k"
    audio_bitrate:  str   = "128k"
    hls_enabled:    bool  = False
    row_index:      int   = 0

    @property
    def rtsp_path(self) -> str:
        return self.stream_path if self.stream_path else "stream"

    @property
    def rtsp_url(self) -> str:
        return f"rtsp://127.0.0.1:{self.port}/{self.rtsp_path}"

    @property
    def rtsp_url_external(self) -> str:
        ip = LISTEN_ADDR if LISTEN_ADDR != "0.0.0.0" else _local_ip()
        return f"rtsp://{ip}:{self.port}/{self.rtsp_path}"

    @property
    def hls_port(self) -> int:
        return self.port + 10000

    @property
    def hls_url(self) -> str:
        ip = LISTEN_ADDR if LISTEN_ADDR != "0.0.0.0" else _local_ip()
        return f"http://{ip}:{self.hls_port}/{self.rtsp_path}/index.m3u8"

    def is_scheduled_today(self) -> bool:
        return datetime.now().weekday() in self.weekdays

    def weekdays_display(self) -> str:
        if set(self.weekdays) == set(range(7)):  return "ALL"
        if set(self.weekdays) == set(range(5)):  return "Weekdays"
        if set(self.weekdays) == {5, 6}:         return "Weekends"
        return "|".join(DAY_ABBR[d] for d in sorted(self.weekdays))

    def playlist_display(self) -> str:
        n = len(self.playlist)
        if n == 0:   return "[no files]"
        if n == 1:   return self.playlist[0].file_path.name
        return f"{self.playlist[0].file_path.name} (+{n-1} more)"

    def sorted_playlist(self) -> List[PlaylistItem]:
        """Return playlist sorted by priority (ascending)."""
        return sorted(self.playlist, key=lambda x: (x.priority, str(x.file_path)))


@dataclass
class StreamState:
    config:           StreamConfig
    status:           StreamStatus              = StreamStatus.STOPPED
    mtx_proc:         Optional[subprocess.Popen] = None
    ffmpeg_proc:      Optional[subprocess.Popen] = None
    progress:         float                     = 0.0
    current_pos:      float                     = 0.0
    duration:         float                     = 0.0
    loop_count:       int                       = 0
    fps:              float                     = 0.0
    bitrate:          str                       = "—"
    speed:            str                       = "—"
    error_msg:        str                       = ""
    started_at:       Optional[datetime]        = None
    restart_count:    int                       = 0
    playlist_index:   int                       = 0
    playlist_order:   List[int]                 = field(default_factory=list)
    seek_target:      Optional[float]           = None
    oneshot_active:   bool                      = False
    log:              List[str]                 = field(default_factory=list)
    _lock:            threading.Lock            = field(default_factory=threading.Lock)

    def log_add(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.log.append(f"[{ts}] {msg}")
            if len(self.log) > 400:
                self.log.pop(0)

    def format_pos(self) -> str:
        def _f(s: float) -> str:
            s = int(max(0, s))
            return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
        if self.duration > 0:
            return f"{_f(self.current_pos)} / {_f(self.duration)}"
        return "—"

    def current_file(self) -> Optional[Path]:
        if not self.config.playlist:
            return None
        idx = self.playlist_order[self.playlist_index] if self.playlist_order else 0
        try:
            return self.config.playlist[idx].file_path
        except IndexError:
            return None


# =============================================================================
# UTILITY HELPERS
# =============================================================================
def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _wait_for_port(port: int, host: str = "127.0.0.1",
                   timeout: float = 10.0, interval: float = 0.25) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(port, "127.0.0.1"):
            return True
        if host not in ("127.0.0.1", "0.0.0.0") and _port_in_use(port, host):
            return True
        time.sleep(interval)
    return False


def _kill_orphan_on_port(port: int) -> None:
    try:
        for conn in psutil.net_connections("tcp"):
            if conn.laddr.port == port and conn.status in ("LISTEN", "ESTABLISHED"):
                if conn.pid:
                    try:
                        psutil.Process(conn.pid).terminate()
                    except Exception:
                        pass
    except Exception:
        pass


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_duration(s: float) -> str:
    s = int(max(0, s))
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


def _safe_path(p: Path, root: Path) -> Optional[Path]:
    """Return resolved path only if it is inside root; else None."""
    try:
        resolved = p.resolve()
        root_resolved = root.resolve()
        resolved.relative_to(root_resolved)
        return resolved
    except (ValueError, RuntimeError):
        return None


# =============================================================================
# FIREWALL MANAGER
# =============================================================================
class FirewallManager:
    _linux_tool: Optional[str] = None

    @classmethod
    def open_ports(cls, ports: List[int], console: Console) -> None:
        if NO_FIREWALL:
            console.print(f"[{CD}]ℹ  Firewall config skipped (--no-firewall).[/]")
            return
        if IS_WIN:     cls._windows(ports, console)
        elif IS_LINUX: cls._linux(ports, console)
        elif IS_MAC:
            console.print(f"[{CY}]⚠  macOS: manually allow TCP {', '.join(map(str, ports))} in Firewall settings.[/]")

    @classmethod
    def _windows(cls, ports: List[int], console: Console) -> None:
        if not cls._is_admin_win():
            console.print(f"[{CY}]⚠  Not Administrator — manually open TCP {', '.join(map(str, ports))}[/]")
            return
        opened = []
        for port in ports:
            rule = f"HydraCast RTSP {port}"
            exists = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule}"],
                capture_output=True, text=True)
            if "No rules match" not in exists.stdout and exists.returncode == 0:
                continue
            r = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule}", "dir=in", "action=allow", "protocol=TCP", f"localport={port}"],
                capture_output=True, text=True)
            if r.returncode == 0:
                opened.append(port)
        if opened:
            console.print(f"[{CG}]✔  Firewall (netsh): opened TCP {', '.join(map(str, opened))}[/]")

    @staticmethod
    def _is_admin_win() -> bool:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @classmethod
    def _linux(cls, ports: List[int], console: Console) -> None:
        if os.geteuid() != 0:
            console.print(f"[{CY}]⚠  Not root — run: sudo ufw allow <port>/tcp[/]")
            return
        tool = cls._detect_linux_tool()
        if tool == "ufw":         cls._ufw(ports, console)
        elif tool == "firewalld": cls._firewalld(ports, console)
        elif tool == "iptables":  cls._iptables(ports, console)

    @classmethod
    def _detect_linux_tool(cls) -> Optional[str]:
        if cls._linux_tool: return cls._linux_tool
        for binary, key in [("ufw","ufw"),("firewall-cmd","firewalld"),("iptables","iptables")]:
            if shutil.which(binary):
                cls._linux_tool = key; return key
        return None

    @classmethod
    def _ufw(cls, ports: List[int], console: Console) -> None:
        opened = []
        for port in ports:
            r = subprocess.run(["ufw","allow",f"{port}/tcp"], capture_output=True, text=True)
            if r.returncode == 0: opened.append(port)
        if opened:
            console.print(f"[{CG}]✔  Firewall (ufw): allowed TCP {', '.join(map(str, opened))}[/]")

    @classmethod
    def _firewalld(cls, ports: List[int], console: Console) -> None:
        for port in ports:
            subprocess.run(["firewall-cmd","--permanent","--add-port",f"{port}/tcp"], capture_output=True)
        subprocess.run(["firewall-cmd","--reload"], capture_output=True)
        console.print(f"[{CG}]✔  Firewall (firewalld): added TCP {', '.join(map(str, ports))}[/]")

    @classmethod
    def _iptables(cls, ports: List[int], console: Console) -> None:
        opened = []
        for port in ports:
            already = subprocess.run(
                ["iptables","-C","INPUT","-p","tcp","--dport",str(port),"-j","ACCEPT"],
                capture_output=True)
            if already.returncode == 0: continue
            r = subprocess.run(
                ["iptables","-I","INPUT","-p","tcp","--dport",str(port),"-j","ACCEPT"],
                capture_output=True, text=True)
            if r.returncode == 0: opened.append(port)
        if opened:
            console.print(f"[{CG}]✔  Firewall (iptables): opened TCP {', '.join(map(str, opened))}[/]")


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
        if local.exists(): return str(local)
        return None

    @classmethod
    def check_ffmpeg(cls)  -> Optional[str]: return cls._find_binary(FFMPEG_BIN_NAME)
    @classmethod
    def check_ffprobe(cls) -> Optional[str]: return cls._find_binary(FFPROBE_BIN_NAME)

    @staticmethod
    def _pick_mediamtx_url() -> Optional[str]:
        key = (OS_KEY, ARCH_KEY)
        if key in MEDIAMTX_URLS: return MEDIAMTX_URLS[key]
        for (os_, _), url in MEDIAMTX_URLS.items():
            if os_ == OS_KEY: return url
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
            def _progress(bn, bs, ts):
                if ts <= 0: return
                pct = min(100, bn*bs*100//ts)
                print(f"\r  [{'█'*(pct//5)}{'░'*(20-pct//5)}] {pct:3d}%", end="", flush=True)
            urllib.request.urlretrieve(url, archive, reporthook=_progress); print()
        except Exception as exc:
            console.print(f"\n[{CR}]✘  Download failed: {exc}[/]"); return False
        try:
            if archive.suffix in (".gz", ".tgz") or archive.name.endswith(".tar.gz"):
                with tarfile.open(archive, "r:gz") as tf:
                    for m in tf.getmembers():
                        if Path(m.name).name in ("mediamtx","mediamtx.exe") and m.isfile():
                            m.name = MEDIAMTX_BIN.name; tf.extract(m, BIN_DIR); break
            elif archive.suffix == ".zip":
                with zipfile.ZipFile(archive) as zf:
                    for name in zf.namelist():
                        if Path(name).name.lower().startswith("mediamtx"):
                            MEDIAMTX_BIN.write_bytes(zf.read(name)); break
            archive.unlink(missing_ok=True)
        except Exception as exc:
            console.print(f"[{CR}]✘  Extraction failed: {exc}[/]"); return False
        if not IS_WIN:
            MEDIAMTX_BIN.chmod(MEDIAMTX_BIN.stat().st_mode | stat.S_IEXEC)
        console.print(f"[{CG}]✔  MediaMTX installed → {MEDIAMTX_BIN}[/]")
        return True


# =============================================================================
# CSV / EVENTS MANAGER
# =============================================================================
CSV_COLUMNS = [
    "stream_name","port","files","weekdays","enabled",
    "shuffle","stream_path","video_bitrate","audio_bitrate","hls_enabled",
]

CSV_TEMPLATE_ROWS = [
    ["Stream_1","8554","/path/to/video.mp4@00:00:00#1","ALL","true","false","stream","2500k","128k","false"],
    ["Stream_2","8555","/path/to/a.mp4@00:05:00#1;/path/to/b.mkv@00:00:00#2","Mon|Wed|Fri","true","false","ch2","4000k","192k","false"],
    ["Stream_3","8556","/media/demo.mp4@00:00:00#1","Sat|Sun","false","true","ch3","1500k","128k","false"],
    ["Stream_4","8557","/media/show.mp4@00:00:00#1","Weekdays","true","false","ch4","2500k","128k","true"],
]

EVENTS_COLUMNS = ["event_id","stream_name","file_path","play_at","post_action","start_pos"]


class CSVManager:

    @staticmethod
    def create_template() -> None:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(CSV_COLUMNS); w.writerows(CSV_TEMPLATE_ROWS)

    @staticmethod
    def parse_weekdays(raw: str) -> List[int]:
        result: set = set()
        for part in re.split(r"[|,;/\s]+", raw.strip()):
            part = part.strip().lower()
            val = WEEKDAY_MAP.get(part)
            if val is None: continue
            if isinstance(val, list): result.update(val)
            else: result.add(val)
        return sorted(result) if result else list(range(7))

    @staticmethod
    def parse_bool(raw: str) -> bool:
        return raw.strip().lower() in ("true","1","yes","on","enabled")

    @staticmethod
    def normalize_position(pos: str) -> str:
        try:
            parts = pos.strip().split(":")
            if len(parts) == 1: parts = ["00","00",parts[0]]
            elif len(parts) == 2: parts = ["00"] + parts
            h, m, s = parts
            return f"{int(h):02d}:{int(m):02d}:{int(float(s)):02d}"
        except Exception:
            return "00:00:00"

    @staticmethod
    def _sanitize_bitrate(raw: str, default: str) -> str:
        raw = raw.strip()
        return raw.lower() if re.fullmatch(r"\d+[kKmM]?", raw) else default

    @staticmethod
    def parse_files(raw: str) -> List[PlaylistItem]:
        """
        Format: path@HH:MM:SS#priority;path@HH:MM:SS#priority
        Priority (#N) is optional, defaults to 999.
        """
        items: List[PlaylistItem] = []
        for part in raw.split(";"):
            part = part.strip()
            if not part: continue
            priority = 999
            # parse priority suffix #N
            if "#" in part:
                main, pri_str = part.rsplit("#", 1)
                part = main.strip()
                try: priority = int(pri_str.strip())
                except ValueError: pass
            if "@" in part:
                path_str, pos = part.rsplit("@", 1)
                path_str = path_str.strip(); pos = pos.strip()
            else:
                path_str = part; pos = "00:00:00"
            try:
                parts = pos.split(":")
                if len(parts) == 1: parts = ["00","00",parts[0]]
                elif len(parts) == 2: parts = ["00"] + parts
                h, m, s = parts
                pos = f"{int(h):02d}:{int(m):02d}:{int(float(s)):02d}"
            except Exception:
                pos = "00:00:00"
            items.append(PlaylistItem(
                file_path=Path(path_str),
                start_position=pos,
                priority=priority,
            ))
        return items

    @classmethod
    def load(cls) -> "List[StreamConfig]":
        if not CSV_FILE.exists():
            cls.create_template()
            raise FileNotFoundError(
                f"streams.csv not found → template created at:\n  {CSV_FILE}\n"
                "Edit it with your stream details, then restart HydraCast."
            )
        configs: List[StreamConfig] = []
        errors:  List[str]          = []
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("streams.csv appears to be empty.")
            for i, row in enumerate(reader, start=2):
                name = row.get("stream_name","").strip()
                if not name: errors.append(f"Row {i}: empty name — skipped."); continue
                try:
                    port = int(row.get("port","0").strip())
                    if not (1024 <= port <= 65535): raise ValueError("out of range")
                except Exception:
                    errors.append(f"Row {i} ({name}): invalid port — skipped."); continue
                playlist = cls.parse_files(row.get("files","").strip())
                if not playlist:
                    errors.append(f"Row {i} ({name}): no files — skipped."); continue
                weekdays  = cls.parse_weekdays(row.get("weekdays","ALL"))
                enabled   = cls.parse_bool(row.get("enabled","true"))
                shuffle   = cls.parse_bool(row.get("shuffle","false"))
                spath     = row.get("stream_path","stream").strip() or "stream"
                vid_br    = cls._sanitize_bitrate(row.get("video_bitrate","2500k"),"2500k")
                aud_br    = cls._sanitize_bitrate(row.get("audio_bitrate","128k"), "128k")
                hls_en    = cls.parse_bool(row.get("hls_enabled","false"))
                # Sort playlist by priority
                sorted_pl = sorted(playlist, key=lambda x: x.priority)
                configs.append(StreamConfig(
                    name=name, port=port, playlist=sorted_pl,
                    weekdays=weekdays, enabled=enabled, shuffle=shuffle,
                    stream_path=spath, video_bitrate=vid_br, audio_bitrate=aud_br,
                    hls_enabled=hls_en, row_index=i-2,
                ))
        for e in errors: logging.warning("CSV: %s", e)
        seen: Dict[int,str] = {}
        for c in configs:
            if c.port in seen:
                raise ValueError(f"Duplicate port {c.port}: '{c.name}' and '{seen[c.port]}'.")
            seen[c.port] = c.name
        if not configs: raise ValueError("No valid streams in streams.csv.")
        return configs

    @classmethod
    def save(cls, configs: "List[StreamConfig]") -> None:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(CSV_COLUMNS)
            for c in configs:
                files_str = ";".join(
                    f"{item.file_path}@{item.start_position}#{item.priority}"
                    for item in c.playlist
                )
                w.writerow([
                    c.name, c.port, files_str,
                    c.weekdays_display().replace("ALL","all"),
                    str(c.enabled).lower(), str(c.shuffle).lower(),
                    c.stream_path, c.video_bitrate, c.audio_bitrate,
                    str(c.hls_enabled).lower(),
                ])

    @classmethod
    def load_events(cls) -> List[OneShotEvent]:
        if not EVENTS_FILE.exists(): return []
        events = []
        with open(EVENTS_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    events.append(OneShotEvent(
                        event_id=row["event_id"].strip(),
                        stream_name=row["stream_name"].strip(),
                        file_path=Path(row["file_path"].strip()),
                        play_at=datetime.strptime(row["play_at"].strip(), "%Y-%m-%d %H:%M:%S"),
                        post_action=row.get("post_action","resume").strip(),
                        played=cls.parse_bool(row.get("played","false")),
                        start_pos=row.get("start_pos","00:00:00").strip(),
                    ))
                except Exception as exc:
                    logging.warning("Events CSV row error: %s", exc)
        return events

    @classmethod
    def save_events(cls, events: List[OneShotEvent]) -> None:
        with open(EVENTS_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(EVENTS_COLUMNS + ["played"])
            for e in events:
                w.writerow([
                    e.event_id, e.stream_name, str(e.file_path),
                    e.play_at.strftime("%Y-%m-%d %H:%M:%S"),
                    e.post_action, e.start_pos, str(e.played).lower(),
                ])

    @classmethod
    def add_event(cls, events: List[OneShotEvent], e: OneShotEvent) -> None:
        events.append(e); cls.save_events(events)

    @classmethod
    def mark_event_played(cls, events: List[OneShotEvent], event_id: str) -> None:
        for e in events:
            if e.event_id == event_id: e.played = True
        cls.save_events(events)


# =============================================================================
# MEDIAMTX CONFIG
# =============================================================================
class MediaMTXConfig:
    @staticmethod
    def _purge_stale(port: int) -> None:
        stale = CONFIGS_DIR / f"mediamtx_{port}.yml"
        try: stale.unlink(missing_ok=True)
        except Exception: pass

    @staticmethod
    def write(state: "StreamState") -> Path:
        cfg   = state.config
        port  = cfg.port
        spath = cfg.rtsp_path
        log_f = (LOGS_DIR / f"mediamtx_{port}.log").resolve()
        cfg_f = CONFIGS_DIR / f"mediamtx_{port}.yml"
        addr  = LISTEN_ADDR

        MediaMTXConfig._purge_stale(port)

        if cfg.hls_enabled:
            proto_section = (
                f"hls: true\n"
                f"hlsAddress: {addr}:{cfg.hls_port}\n"
                f"hlsAlwaysRemux: yes\n"
                f"hlsSegmentCount: 3\n"
                f"hlsSegmentDuration: 2s\n"
                f"hlsAllowOrigin: \"*\"\n"
                f"webrtc: false\n"
                f"srt: false\n"
                f"\npaths:\n"
                f"  {spath}:\n"
                f"    source: publisher\n"
            )
        else:
            proto_section = (
                f"hls: false\n"
                f"webrtc: false\n"
                f"srt: false\n"
                f"\npaths:\n"
                f"  {spath}: {{}}\n"
            )

        yaml_text = (
            f"# HydraCast v{APP_VER} — {cfg.name} (:{port})\n"
            f"logLevel: error\n"
            f"logDestinations: [file]\n"
            f"logFile: {str(log_f).replace(chr(92), '/')}\n"
            f"\n"
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
# FFPROBE
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


def probe_metadata(file_path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "duration": 0.0, "size": 0, "video_codec": "", "audio_codec": "",
        "width": 0, "height": 0, "fps": "", "bitrate": 0,
    }
    try:
        meta["size"] = file_path.stat().st_size
    except Exception:
        pass
    try:
        r = subprocess.run(
            [FFPROBE_PATH, "-v", "quiet",
             "-print_format", "json",
             "-show_streams", "-show_format", str(file_path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        meta["duration"] = float(fmt.get("duration", 0))
        meta["bitrate"]  = int(float(fmt.get("bit_rate", 0)))
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and not meta["video_codec"]:
                meta["video_codec"] = s.get("codec_name","")
                meta["width"]       = s.get("width", 0)
                meta["height"]      = s.get("height", 0)
                r_fps               = s.get("r_frame_rate","0/1")
                try:
                    n, d = r_fps.split("/"); meta["fps"] = f"{int(n)//int(d)}" if int(d) else ""
                except Exception: pass
            elif s.get("codec_type") == "audio" and not meta["audio_codec"]:
                meta["audio_codec"] = s.get("codec_name","")
    except Exception:
        pass
    return meta


# =============================================================================
# LOG BUFFER
# =============================================================================
class LogBuffer:
    def __init__(self, capacity: int = 1200) -> None:
        self._entries: List[Tuple[str, str]] = []
        self._lock = threading.Lock()
        self._cap  = capacity

    def add(self, msg: str, level: str = "INFO") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._entries.append((f"[{ts}] {msg}", level))
            if len(self._entries) > self._cap: self._entries.pop(0)

    def last(self, n: int = 9) -> "List[Tuple[str, str]]":
        with self._lock: return list(self._entries[-n:])

    def all(self) -> "List[Tuple[str, str]]":
        with self._lock: return list(self._entries)

    def filtered(self, level: Optional[str] = None,
                 stream: Optional[str] = None,
                 n: int = 500) -> "List[Tuple[str, str]]":
        with self._lock:
            entries = list(self._entries)
        if stream:
            entries = [(m, l) for m, l in entries if f"[{stream}]" in m]
        if level and level != "ALL":
            entries = [(m, l) for m, l in entries if l == level]
        return entries[-n:]


# =============================================================================
# STREAM WORKER  —  v3.1 FIXES RETAINED
# =============================================================================
class StreamWorker:
    MAX_AUTO_RESTARTS = 8
    BACKOFF           = [5, 10, 20, 40, 60, 120, 120, 120]
    MTX_READY_TIMEOUT = 13.0

    _FFMPEG_PROGRESS_RE = re.compile(r"^(\w+)=(.+)$")

    def __init__(self, state: StreamState, glog: LogBuffer) -> None:
        self.state  = state
        self.glog   = glog
        self._stop  = threading.Event()
        self._seeking    = threading.Event()
        self._start_lock = threading.Lock()

    def _log(self, msg: str, level: str = "INFO") -> None:
        full = f"[{self.state.config.name}] {msg}"
        self.state.log_add(full); self.glog.add(full, level)
        logging.log(
            logging.WARNING if level == "WARN" else
            (logging.ERROR if level == "ERROR" else logging.INFO), full)

    def _build_order(self) -> List[int]:
        n = len(self.state.config.playlist)
        order = list(range(n))
        if self.state.config.shuffle: random.shuffle(order)
        return order

    def _current_item(self) -> Optional[PlaylistItem]:
        pl = self.state.config.playlist
        if not pl: return None
        if not self.state.playlist_order:
            self.state.playlist_order = self._build_order()
        idx = self.state.playlist_order[self.state.playlist_index % len(self.state.playlist_order)]
        return pl[idx]

    def _advance_playlist(self) -> None:
        self.state.playlist_index += 1
        if self.state.playlist_index >= len(self.state.playlist_order):
            self.state.playlist_index = 0
            self.state.loop_count    += 1
            if self.state.config.shuffle:
                self.state.playlist_order = self._build_order()

    def start(self, seek_override: Optional[float] = None) -> bool:
        if not self._start_lock.acquire(blocking=False):
            self._log("start() already in progress — skipping duplicate call.", "WARN")
            return False
        try:
            return self._do_start(seek_override)
        finally:
            self._start_lock.release()

    def _do_start(self, seek_override: Optional[float] = None) -> bool:
        cfg = self.state.config
        self._stop.clear()

        if not cfg.playlist:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = "No files in playlist"
            return False

        item = self._current_item()
        if item is None or not item.file_path.exists():
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"File not found: {item.file_path if item else '?'}"
            self._log(self.state.error_msg, "ERROR")
            return False

        self.state.status   = StreamStatus.STARTING
        self.state.duration = probe_duration(item.file_path)

        seek_pos = seek_override
        if seek_pos is None:
            pos_str = item.start_position
            try:
                h, m, s = pos_str.split(":"); seek_pos = int(h)*3600 + int(m)*60 + float(s)
            except Exception:
                seek_pos = 0.0

        if _port_in_use(cfg.port):
            self._log(f"Port {cfg.port} occupied — killing orphan …", "WARN")
            _kill_orphan_on_port(cfg.port); time.sleep(0.8)
            if _port_in_use(cfg.port):
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = f"Port {cfg.port} still in use"
                self._log(self.state.error_msg, "ERROR")
                return False

        mtx_cfg = MediaMTXConfig.write(self.state)
        if not self._start_mediamtx(mtx_cfg): return False

        self._log(f"Waiting for MediaMTX :{cfg.port} …")
        if not _wait_for_port(cfg.port, timeout=self.MTX_READY_TIMEOUT):
            self._log(f"MediaMTX port-bind timeout :{cfg.port}", "ERROR")
            self._kill_mediamtx()
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX timeout (:{cfg.port})"
            return False

        if not self._start_ffmpeg(item, seek_pos):
            self._kill_mediamtx(); return False

        self.state.status      = StreamStatus.LIVE
        self.state.started_at  = datetime.now()
        self.state.restart_count = 0
        self._log(f"Live → {cfg.rtsp_url}")
        if cfg.hls_enabled: self._log(f"HLS → {cfg.hls_url}")

        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{cfg.port}").start()
        return True

    def stop(self) -> None:
        self._stop.set()
        self._kill_ffmpeg(); time.sleep(1.0); self._kill_mediamtx()
        self.state.status      = StreamStatus.STOPPED
        self.state.progress    = 0.0
        self.state.current_pos = 0.0
        self.state.fps         = 0.0
        self.state.bitrate     = "—"
        self.state.speed       = "—"
        self._log("Stream stopped.")

    def restart(self, seek: Optional[float] = None) -> None:
        self._log("Restarting …")
        self.stop(); time.sleep(0.8)
        self.start(seek_override=seek)

    def seek(self, seconds: float) -> None:
        self._seeking.set()
        self._log(f"Seeking to {_fmt_duration(seconds)} …")
        self._kill_ffmpeg()
        time.sleep(0.4)
        item = self._current_item()
        if item is None:
            self._seeking.clear(); return
        self.state.duration = probe_duration(item.file_path)
        self._start_ffmpeg(item, max(0.0, seconds))
        self._seeking.clear()
        self.state.status = StreamStatus.LIVE
        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{self.state.config.port}").start()

    def skip_to_next(self) -> None:
        """Skip to next file in playlist."""
        self._seeking.set()
        self._advance_playlist()
        self._kill_ffmpeg()
        time.sleep(0.3)
        item = self._current_item()
        if item is None:
            self._seeking.clear(); return
        self.state.duration = probe_duration(item.file_path)
        try:
            h, m, s = item.start_position.split(":")
            spos = int(h)*3600 + int(m)*60 + float(s)
        except Exception:
            spos = 0.0
        self._start_ffmpeg(item, spos)
        self._seeking.clear()
        self.state.status = StreamStatus.LIVE
        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{self.state.config.port}").start()

    def play_oneshot(self, event: OneShotEvent) -> None:
        self._log(f"One-shot event: {event.file_path.name}", "INFO")
        self.state.oneshot_active = True
        self._kill_ffmpeg(); time.sleep(0.3)

        try:
            h, m, s = event.start_pos.split(":")
            seek_secs = int(h)*3600 + int(m)*60 + float(s)
        except Exception:
            seek_secs = 0.0

        item = PlaylistItem(file_path=event.file_path, start_position=event.start_pos)
        self.state.duration = probe_duration(item.file_path)
        self._start_ffmpeg(item, seek_secs)

        def _after() -> None:
            proc = self.state.ffmpeg_proc
            if proc:
                while not self._stop.is_set() and proc.poll() is None:
                    time.sleep(0.5)
            self.state.oneshot_active = False
            if self._stop.is_set(): return
            if event.post_action == "stop":
                self.stop()
            elif event.post_action == "black":
                self._play_black()
            else:
                item2 = self._current_item()
                if item2:
                    self._start_ffmpeg(item2, 0.0)
                    threading.Thread(target=self._monitor, daemon=True,
                                     name=f"mon-{self.state.config.port}").start()

        threading.Thread(target=_after, daemon=True,
                         name=f"oneshot-{self.state.config.port}").start()

    def _play_black(self) -> None:
        cfg = self.state.config
        cmd = [
            str(FFMPEG_PATH), "-hide_banner", "-loglevel", "error",
            "-re",
            "-f", "lavfi", "-i", "color=black:size=1280x720:rate=25",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", cfg.video_bitrate, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", cfg.audio_bitrate,
            "-f", "rtsp", "-rtsp_transport", "tcp",
            f"rtsp://127.0.0.1:{cfg.port}/{cfg.rtsp_path}",
        ]
        try:
            kw: Dict[str,Any] = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if IS_WIN: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.state.ffmpeg_proc = subprocess.Popen(cmd, **kw)
        except Exception as exc:
            self._log(f"Black screen launch failed: {exc}", "ERROR")

    def _start_mediamtx(self, cfg_file: Path) -> bool:
        log_f = LOGS_DIR / f"mediamtx_{self.state.config.port}.log"
        try:
            with open(log_f, "a") as lf:
                kw: Dict[str,Any] = dict(stdout=lf, stderr=subprocess.PIPE)
                if IS_WIN: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                proc = subprocess.Popen([str(MEDIAMTX_BIN), str(cfg_file)], **kw)
            self.state.mtx_proc = proc
            self._log(f"MediaMTX PID {proc.pid} on :{self.state.config.port}")
            time.sleep(0.5)
            if proc.poll() is not None:
                stderr_out = (proc.stderr.read() or b"").decode(errors="replace").strip()
                msg = f"MediaMTX exited immediately (code {proc.returncode})"
                if stderr_out: msg += f": {stderr_out[:300]}"
                self.state.status = StreamStatus.ERROR
                self.state.error_msg = msg; self._log(msg, "ERROR"); return False

            def _drain(p):
                try:
                    for raw in p.stderr:
                        line = raw.decode(errors="replace").strip() if isinstance(raw,bytes) else raw.strip()
                        if line: logging.warning("MTX stderr [%d]: %s", p.pid, line)
                except Exception: pass
            threading.Thread(target=_drain, args=(proc,), daemon=True).start()
            return True
        except Exception as exc:
            self.state.status = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR"); return False

    def _start_ffmpeg(self, item: PlaylistItem, seek_pos: float) -> bool:
        cfg = self.state.config
        loop_flag = ["-stream_loop", "-1"] if len(cfg.playlist) == 1 else []
        cmd = [
            str(FFMPEG_PATH), "-hide_banner", "-loglevel", "error",
            "-re",
            "-ss", str(int(seek_pos)),
            *loop_flag,
            "-i", str(item.file_path),
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", cfg.video_bitrate, "-pix_fmt", "yuv420p", "-g", "50",
            "-c:a", "aac", "-b:a", cfg.audio_bitrate, "-ar", "44100", "-ac", "2",
            "-progress", "pipe:1", "-nostats",
            "-f", "rtsp", "-rtsp_transport", "tcp",
            f"rtsp://127.0.0.1:{cfg.port}/{cfg.rtsp_path}",
        ]
        try:
            kw: Dict[str,Any] = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, bufsize=1)
            if IS_WIN: kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(cmd, **kw)
            self.state.ffmpeg_proc = proc
            if IS_LINUX and CPU_COUNT > 1:
                try:
                    core = cfg.row_index % CPU_COUNT
                    psutil.Process(proc.pid).cpu_affinity([core])
                    self._log(f"FFmpeg PID {proc.pid} → core {core}")
                except Exception:
                    self._log(f"FFmpeg PID {proc.pid}")
            else:
                self._log(f"FFmpeg PID {proc.pid}")
            return True
        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"FFmpeg launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR"); return False

    def _monitor(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc is None: return
        my_proc = proc
        buf: Dict[str,str] = {}

        while not self._stop.is_set():
            if my_proc.poll() is not None: break
            if self.state.ffmpeg_proc is not my_proc: return
            try:
                line = my_proc.stdout.readline()
                if not line: time.sleep(0.05); continue
                m = self._FFMPEG_PROGRESS_RE.match(line.strip())
                if not m: continue
                k, v = m.group(1), m.group(2).strip()
                buf[k] = v
                if k == "progress": self._apply_progress(buf); buf = {}
            except Exception:
                time.sleep(0.05)

        if self._stop.is_set():                   return
        if self._seeking.is_set():                return
        if self.state.ffmpeg_proc is not my_proc: return

        if not self.state.oneshot_active and len(self.state.config.playlist) > 1:
            self._advance_playlist()
            next_item = self._current_item()
            if next_item and next_item.file_path.exists():
                self.state.duration = probe_duration(next_item.file_path)
                try:
                    h, m, s = next_item.start_position.split(":")
                    spos = int(h)*3600 + int(m)*60 + float(s)
                except Exception:
                    spos = 0.0
                time.sleep(0.2)
                self._start_ffmpeg(next_item, spos)
                threading.Thread(target=self._monitor, daemon=True,
                                 name=f"mon-{self.state.config.port}").start()
                return

        ret = my_proc.returncode if my_proc.returncode is not None else -1
        stderr_txt = ""
        try:
            if my_proc.stderr: stderr_txt = my_proc.stderr.read(400)
        except Exception: pass

        if ret in (0, 255):
            self.state.status = StreamStatus.STOPPED
            self._log(f"FFmpeg exited normally (code {ret}).")
        else:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = stderr_txt[:200].strip() or f"FFmpeg exited code {ret}"
            self._log(self.state.error_msg, "ERROR")
            self._auto_restart()

    def _apply_progress(self, data: Dict[str,str]) -> None:
        try:
            out_us = int(data.get("out_time_us","0"))
            if out_us > 0 and self.state.duration > 0:
                pos = (out_us / 1_000_000.0) % self.state.duration
                self.state.current_pos = pos
                self.state.progress    = min(99.9, pos / self.state.duration * 100.0)
            fps_raw = data.get("fps","0")
            self.state.fps     = float(fps_raw) if fps_raw not in ("","N/A") else 0.0
            self.state.bitrate = data.get("bitrate","—").replace("kbits/s","kb/s") or "—"
            self.state.speed   = data.get("speed","—").strip() or "—"
        except Exception: pass

    def _auto_restart(self) -> None:
        if self._seeking.is_set():
            self._log("Skipping auto-restart: seek in progress.", "WARN")
            return
        n = self.state.restart_count
        if n >= self.MAX_AUTO_RESTARTS:
            self._log(f"Max auto-restarts ({self.MAX_AUTO_RESTARTS}) reached.", "ERROR")
            return
        delay = self.BACKOFF[min(n, len(self.BACKOFF)-1)]
        self._log(f"Auto-restart #{n+1} in {delay}s …", "WARN")
        for _ in range(delay*10):
            if self._stop.is_set() or self._seeking.is_set(): return
            time.sleep(0.1)
        if not self._stop.is_set() and not self._seeking.is_set():
            self.state.restart_count += 1
            self._kill_mediamtx()
            time.sleep(0.3)
            self.start()

    def _kill_ffmpeg(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc and proc.poll() is None:
            try: proc.terminate(); proc.wait(timeout=6)
            except subprocess.TimeoutExpired: proc.kill()
            except Exception: pass
        self.state.ffmpeg_proc = None

    def _kill_mediamtx(self) -> None:
        proc = self.state.mtx_proc
        if proc and proc.poll() is None:
            try: proc.terminate(); proc.wait(timeout=6)
            except subprocess.TimeoutExpired: proc.kill()
            except Exception: pass
        self.state.mtx_proc = None


# =============================================================================
# STREAM MANAGER
# =============================================================================
class StreamManager:

    def __init__(self, configs: List[StreamConfig], glog: LogBuffer) -> None:
        self.states:   List[StreamState]          = [StreamState(config=c) for c in configs]
        self._workers: Dict[str, StreamWorker]    = {}
        self._glog    = glog
        self._running = False
        self._sched_t: Optional[threading.Thread] = None
        self.events:   List[OneShotEvent]         = CSVManager.load_events()
        self._event_t: Optional[threading.Thread] = None

    def _worker(self, state: StreamState) -> StreamWorker:
        if state.config.name not in self._workers:
            self._workers[state.config.name] = StreamWorker(state, self._glog)
        return self._workers[state.config.name]

    def start_stream(self, state: StreamState) -> None:
        if state.status in (StreamStatus.LIVE, StreamStatus.STARTING): return
        state.playlist_index = 0
        state.playlist_order = []
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

    def seek_stream(self, state: StreamState, seconds: float) -> None:
        if state.status != StreamStatus.LIVE: return
        w = self._workers.get(state.config.name)
        if w:
            threading.Thread(target=lambda: w.seek(seconds), daemon=True,
                             name=f"seek-{state.config.port}").start()

    def skip_next(self, state: StreamState) -> None:
        w = self._workers.get(state.config.name)
        if w:
            threading.Thread(target=w.skip_to_next, daemon=True,
                             name=f"skip-{state.config.port}").start()

    def start_all(self) -> None:
        for s in self.states:
            if not s.config.enabled:           s.status = StreamStatus.DISABLED
            elif s.config.is_scheduled_today(): self.start_stream(s)
            else:                               s.status = StreamStatus.SCHEDULED

    def stop_all(self) -> None:
        for s in self.states: self.stop_stream(s)

    def _scheduler_loop(self) -> None:
        while self._running:
            for s in self.states:
                if not s.config.enabled: s.status = StreamStatus.DISABLED; continue
                should = s.config.is_scheduled_today()
                active = s.status in (StreamStatus.LIVE, StreamStatus.STARTING)
                if should and not active:
                    self._glog.add(f"[{s.config.name}] Scheduler: starting.", "INFO")
                    self.start_stream(s)
                elif not should and active:
                    self._glog.add(f"[{s.config.name}] Scheduler: stopping.", "INFO")
                    self.stop_stream(s)
                elif not should and not active:
                    if s.status not in (StreamStatus.SCHEDULED, StreamStatus.DISABLED):
                        s.status = StreamStatus.SCHEDULED
            for _ in range(600):
                if not self._running: return
                time.sleep(0.1)

    def _event_loop(self) -> None:
        while self._running:
            now = datetime.now()
            for ev in self.events:
                if ev.played: continue
                delta = (ev.play_at - now).total_seconds()
                if -10 <= delta <= 5:
                    for s in self.states:
                        if s.config.name == ev.stream_name:
                            w = self._workers.get(s.config.name)
                            if w:
                                ev.played = True
                                CSVManager.mark_event_played(self.events, ev.event_id)
                                self._glog.add(f"[{s.config.name}] Firing one-shot: {ev.file_path.name}", "INFO")
                                threading.Thread(target=lambda w=w, ev=ev: w.play_oneshot(ev),
                                                 daemon=True).start()
                            break
            for _ in range(50):
                if not self._running: return
                time.sleep(0.1)

    def run_scheduler(self) -> None:
        self._running = True
        self._sched_t = threading.Thread(target=self._scheduler_loop, daemon=True, name="scheduler")
        self._sched_t.start()
        self._event_t = threading.Thread(target=self._event_loop, daemon=True, name="eventloop")
        self._event_t.start()

    def shutdown(self) -> None:
        self._running = False
        self.stop_all()
        deadline = time.time() + 10
        while time.time() < deadline:
            if not any(s.status in (StreamStatus.LIVE, StreamStatus.STARTING) for s in self.states):
                break
            time.sleep(0.2)

    def get_state(self, name: str) -> Optional[StreamState]:
        for s in self.states:
            if s.config.name == name: return s
        return None

    def export_urls(self, path: Optional[Path] = None) -> Path:
        out = path or (BASE_DIR / "stream_urls.txt")
        lines = [f"# HydraCast {APP_VER} — Stream URLs",
                 f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for s in self.states:
            cfg = s.config
            lines += [f"[{cfg.name}]",
                      f"  RTSP (local)    : {cfg.rtsp_url}",
                      f"  RTSP (external) : {cfg.rtsp_url_external}"]
            if cfg.hls_enabled: lines.append(f"  HLS             : {cfg.hls_url}")
            lines.append("")
        out.write_text("\n".join(lines), encoding="utf-8"); return out


# =============================================================================
# WEB UI HTML  —  v4.0 Production Redesign
# =============================================================================
_WEB_MANAGER: Optional[StreamManager] = None

_HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HydraCast — Stream Manager</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root{
  --bg:       #03070d;
  --bg2:      #060c14;
  --bg3:      #0a121d;
  --bg4:      #0f1c2a;
  --bg5:      #162435;
  --border:   #162030;
  --border2:  #1e3040;
  --text:     #ddeeff;
  --muted:    #4a6a88;
  --faint:    #0c1824;
  --green:    #39e07a;
  --red:      #ff5a6e;
  --yellow:   #f7c35f;
  --blue:     #3eb8fa;
  --purple:   #a87efa;
  --cyan:     #1ee8cc;
  --orange:   #ff8a4c;
  --teal:     #1ecfc7;
  --pink:     #f06aaa;
  --green-g:  rgba(57,224,122,.07);
  --red-g:    rgba(255,90,110,.07);
  --blue-g:   rgba(62,184,250,.07);
  --yellow-g: rgba(247,195,95,.07);
  --purple-g: rgba(168,126,250,.07);
  --r:10px; --rs:6px; --rxs:4px;
  --font:'Syne',system-ui,sans-serif;
  --mono:'IBM Plex Mono','JetBrains Mono',monospace;
  --shadow: 0 8px 32px rgba(0,0,0,.6);
  --glow-b: 0 0 24px rgba(62,184,250,.18);
  --glow-g: 0 0 24px rgba(57,224,122,.18);
}
[data-theme="light"]{
  --bg:       #f0f5fb;
  --bg2:      #ffffff;
  --bg3:      #e8eef7;
  --bg4:      #dce5f0;
  --bg5:      #ccd6e8;
  --border:   #bfcfdf;
  --border2:  #a8bdd0;
  --text:     #0a1928;
  --muted:    #5878a0;
  --faint:    #e0eaf5;
  --green:    #1aaa55;
  --red:      #d83050;
  --yellow:   #b87a00;
  --blue:     #0a7fd4;
  --purple:   #6840c0;
  --cyan:     #0898a8;
  --orange:   #c05818;
  --teal:     #088890;
  --pink:     #b03870;
  --green-g:  rgba(26,170,85,.1);
  --red-g:    rgba(216,48,80,.08);
  --blue-g:   rgba(10,127,212,.08);
  --yellow-g: rgba(184,122,0,.08);
  --purple-g: rgba(104,64,192,.08);
  --shadow:   0 2px 16px rgba(10,30,70,.1);
  --glow-b:   0 0 12px rgba(10,127,212,.12);
  --glow-g:   0 0 12px rgba(26,170,85,.12);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  background:var(--bg);color:var(--text);
  font:14px/1.6 var(--font);min-height:100vh;overflow-x:hidden;
  transition:background .35s,color .2s;
  background-image:
    radial-gradient(ellipse 80% 50% at 100% 0%,rgba(62,184,250,.05) 0%,transparent 55%),
    radial-gradient(ellipse 50% 70% at 0% 100%,rgba(168,126,250,.04) 0%,transparent 55%),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Crect width='60' height='60' fill='none'/%3E%3Cpath d='M0 60L60 0M-10 10L10-10M50 70L70 50' stroke='rgba(62,184,250,.03)' stroke-width='1'/%3E%3C/svg%3E");
}
[data-theme="light"] body,body[data-theme="light"]{
  background-image:
    radial-gradient(ellipse 80% 50% at 100% 0%,rgba(10,127,212,.04) 0%,transparent 60%),
    radial-gradient(ellipse 50% 70% at 0% 100%,rgba(104,64,192,.03) 0%,transparent 60%);
}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg2)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--muted)}

/* ── HEADER ─────────────────────────────── */
header{
  height:58px;background:rgba(6,12,20,.92);backdrop-filter:blur(24px);
  border-bottom:1px solid var(--border2);
  display:flex;align-items:center;gap:16px;padding:0 26px;
  position:sticky;top:0;z-index:100;
  box-shadow:0 1px 0 rgba(62,184,250,.06),0 8px 32px rgba(0,0,0,.5);
  transition:background .35s,border-color .2s,box-shadow .2s;
}
[data-theme="light"] header{
  background:rgba(255,255,255,.94);
  box-shadow:0 1px 0 rgba(10,127,212,.08),0 4px 20px rgba(10,30,80,.1);
}
.logo-wrap{display:flex;align-items:center;gap:10px;text-decoration:none}
.logo-badge{
  width:34px;height:34px;border-radius:9px;
  background:linear-gradient(135deg,#0b2a52,#0a4a6e);
  border:1px solid rgba(62,184,250,.3);
  display:grid;place-items:center;font-size:18px;
  box-shadow:0 0 16px rgba(62,184,250,.25),inset 0 1px 0 rgba(255,255,255,.08);
  animation:logo-pulse 4s ease-in-out infinite;
}
@keyframes logo-pulse{0%,100%{box-shadow:0 0 16px rgba(62,184,250,.25),inset 0 1px 0 rgba(255,255,255,.08)}
  50%{box-shadow:0 0 28px rgba(62,184,250,.45),inset 0 1px 0 rgba(255,255,255,.12)}}
.logo-text{font-size:20px;font-weight:800;color:var(--blue);letter-spacing:.08em;font-family:var(--mono)}
.logo-ver{font-size:10px;color:var(--muted);font-family:var(--mono);
  background:var(--bg4);border:1px solid var(--border2);padding:1px 7px;border-radius:10px}
.hdr-stats{display:flex;gap:20px;margin-left:10px;align-items:center}
.hdr-stat{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--muted);font-family:var(--mono)}
.hdr-stat .v{color:var(--text);font-weight:700}
[data-theme="light"] .hdr-stat{color:var(--muted)}
[data-theme="light"] .hdr-stat .v{color:var(--text)}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--green);
  box-shadow:0 0 8px var(--green);animation:blink 2s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.85)}}
nav{
  display:flex;gap:1px;margin-left:auto;
  background:var(--bg3);border:1px solid var(--border2);
  border-radius:9px;padding:3px;
}
nav button{
  background:none;border:none;border-radius:7px;
  color:var(--muted);padding:6px 15px;cursor:pointer;font-size:12px;font-weight:600;
  transition:all .2s;letter-spacing:.03em;font-family:var(--font);white-space:nowrap;
}
nav button.active{background:var(--blue-g);color:var(--blue);box-shadow:inset 0 0 0 1px rgba(62,184,250,.3)}
nav button:hover:not(.active){background:rgba(255,255,255,.04);color:var(--text)}
[data-theme="light"] nav button:hover:not(.active){background:rgba(0,0,0,.04);color:var(--text)}
/* ── THEME TOGGLE ─────────────────────── */
.theme-btn{
  width:32px;height:32px;border-radius:8px;border:1px solid var(--border2);
  background:var(--bg3);cursor:pointer;display:grid;place-items:center;
  font-size:15px;transition:all .2s;flex-shrink:0;color:var(--text);
}
.theme-btn:hover{border-color:var(--blue);background:var(--blue-g);transform:scale(1.08)}

/* ── LAYOUT ─────────────────────────────── */
.container{max-width:1540px;margin:0 auto;padding:22px 26px}
.tab-content{display:none;animation:fadeUp .22s ease both}
.tab-content.active{display:block}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}

/* ── PANEL ───────────────────────────────── */
.panel{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);
  margin-bottom:18px;overflow:hidden;
  box-shadow:0 2px 20px rgba(0,0,0,.35);
  transition:border-color .25s,box-shadow .25s;
}
.panel:hover{border-color:var(--border2);box-shadow:0 4px 32px rgba(0,0,0,.5)}
.panel-hdr{
  background:linear-gradient(90deg,var(--bg3) 0%,var(--bg2) 60%);
  padding:14px 22px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:12px;
}
.panel-title{font-size:13px;font-weight:700;color:var(--text);letter-spacing:.04em}
.panel-sub{font-size:10.5px;color:var(--muted);font-family:var(--mono);margin-left:6px}
.panel-body{padding:20px}

/* ── TABLE ───────────────────────────────── */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{
  text-align:left;padding:11px 14px;color:var(--muted);font-weight:600;font-size:10px;
  border-bottom:1px solid var(--border2);text-transform:uppercase;letter-spacing:.1em;
  font-family:var(--mono);white-space:nowrap;background:var(--bg3);
  transition:color .2s;
}
[data-theme="light"] th{background:var(--bg3)}
td{padding:12px 14px;border-bottom:1px solid var(--faint);font-size:12.5px;vertical-align:middle}
[data-theme="light"] td{border-bottom-color:var(--border)}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .12s}
tbody tr:hover td{background:rgba(62,184,250,.025)}
tbody tr.row-live td:first-child{border-left:2px solid var(--green)}

/* ── BADGES ─────────────────────────────── */
.badge{
  display:inline-flex;align-items:center;gap:5px;
  padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;
  letter-spacing:.07em;font-family:var(--mono);white-space:nowrap;
}
.bdot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.badge-LIVE{background:rgba(57,224,122,.1);color:var(--green);border:1px solid rgba(57,224,122,.3)}
.badge-LIVE .bdot{background:var(--green);box-shadow:0 0 5px var(--green);animation:blink 2s ease-in-out infinite}
.badge-STOPPED{background:rgba(74,106,136,.06);color:var(--muted);border:1px solid var(--border)}
.badge-ERROR{background:rgba(255,90,110,.1);color:var(--red);border:1px solid rgba(255,90,110,.3)}
.badge-SCHED{background:var(--blue-g);color:var(--blue);border:1px solid rgba(62,184,250,.25)}
.badge-DISABLED{background:rgba(74,106,136,.04);color:var(--muted);border:1px dashed var(--border)}
.badge-STARTING{background:var(--yellow-g);color:var(--yellow);border:1px solid rgba(247,195,95,.3)}
.badge-ONESHOT{background:var(--purple-g);color:var(--purple);border:1px solid rgba(168,126,250,.3)}

/* ── BUTTONS ─────────────────────────────── */
.btn{
  display:inline-flex;align-items:center;gap:5px;padding:7px 15px;
  border-radius:var(--rs);border:1px solid var(--border2);
  cursor:pointer;font-size:11.5px;font-weight:700;
  background:var(--bg4);color:var(--text);
  transition:all .18s;white-space:nowrap;letter-spacing:.03em;font-family:var(--font);
}
.btn:hover{border-color:var(--blue);color:var(--blue);background:var(--blue-g);box-shadow:var(--glow-b)}
.btn:active{transform:scale(.96)}
.btn-sm{padding:4px 11px;font-size:10.5px;border-radius:var(--rxs)}
.btn-xs{padding:2px 8px;font-size:10px;border-radius:var(--rxs)}
.btn-danger{color:var(--red);border-color:rgba(255,90,110,.3);background:var(--red-g)}
.btn-danger:hover{border-color:var(--red);box-shadow:0 0 16px rgba(255,90,110,.2)}
.btn-success{color:var(--green);border-color:rgba(57,224,122,.3);background:var(--green-g)}
.btn-success:hover{border-color:var(--green);box-shadow:var(--glow-g)}
.btn-primary{background:rgba(62,184,250,.1);border-color:rgba(62,184,250,.4);color:var(--blue)}
.btn-primary:hover{background:var(--blue);color:#fff;border-color:var(--blue)}
[data-theme="light"] .btn-primary:hover{color:#fff}

/* ── FORM ─────────────────────────────────── */
input,select,textarea{
  background:var(--bg3);border:1px solid var(--border2);border-radius:var(--rs);
  color:var(--text);padding:8px 12px;font-size:12.5px;width:100%;outline:none;
  font-family:var(--font);transition:all .2s;
}
input:focus,select:focus,textarea:focus{
  border-color:var(--blue);background:var(--bg4);
  box-shadow:0 0 0 3px rgba(62,184,250,.1);
}
label{font-size:10.5px;color:var(--muted);margin-bottom:5px;display:block;
  letter-spacing:.06em;text-transform:uppercase;font-family:var(--mono)}
.form-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:14px}
.form-group{display:flex;flex-direction:column}
.form-hint{font-size:10px;color:var(--muted);margin-top:4px;font-family:var(--mono)}
.checkbox-row{display:flex;align-items:center;gap:7px;cursor:pointer}
.checkbox-row input[type=checkbox]{width:auto;accent-color:var(--blue);cursor:pointer}
.checkbox-row span{font-size:12.5px;color:var(--text);font-family:var(--font);
  text-transform:none;letter-spacing:0;margin:0}

/* ── PROGRESS BARS (bigger & interactive) ── */
.prog-wrap{min-width:220px}
.prog-track{
  height:14px;background:var(--bg5);border-radius:7px;
  border:1px solid rgba(255,255,255,.04);overflow:hidden;cursor:pointer;
  position:relative;transition:box-shadow .2s;
}
.prog-track:hover{box-shadow:0 0 0 2px rgba(62,184,250,.35)}
.prog-track.live:hover .prog-fill{filter:brightness(1.2)}
.prog-fill{
  height:100%;border-radius:7px;
  transition:width .8s cubic-bezier(.25,.46,.45,.94);
  position:relative;overflow:hidden;
}
.prog-fill::before{
  content:'';position:absolute;top:0;left:-100%;width:50%;height:100%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.15),transparent);
  animation:shimmer 2.5s infinite;
}
.prog-fill::after{
  content:'';position:absolute;right:0;top:2px;bottom:2px;
  width:3px;background:rgba(255,255,255,.75);border-radius:2px;
  box-shadow:0 0 6px rgba(255,255,255,.4);
}
@keyframes shimmer{to{left:200%}}
.prog-labels{
  display:flex;justify-content:space-between;align-items:center;
  font-size:10px;font-family:var(--mono);color:var(--muted);margin-top:4px;
}
.prog-pct{font-weight:700;color:var(--text)}
/* Inline seek slider */
.seek-slider-wrap{margin-top:6px;display:flex;align-items:center;gap:7px}
input[type=range]{
  -webkit-appearance:none;appearance:none;flex:1;
  height:4px;background:var(--bg5);border-radius:2px;
  outline:none;border:none;padding:0;cursor:pointer;
}
input[type=range]::-webkit-slider-thumb{
  -webkit-appearance:none;width:14px;height:14px;border-radius:50%;
  background:var(--blue);cursor:pointer;
  box-shadow:0 0 8px rgba(62,184,250,.6);transition:transform .1s,box-shadow .15s;
}
input[type=range]::-webkit-slider-thumb:hover{transform:scale(1.4);box-shadow:0 0 16px rgba(62,184,250,.9)}
input[type=range]::-moz-range-thumb{width:14px;height:14px;border:none;border-radius:50%;background:var(--blue);cursor:pointer}

/* ── STREAM NAME / RTSP CHIP ─────────────── */
.stream-link{
  font-weight:800;font-size:13px;color:var(--blue);cursor:pointer;
  transition:color .15s,text-shadow .15s;display:block;letter-spacing:.02em;
}
.stream-link:hover{color:var(--cyan);text-shadow:0 0 10px rgba(30,232,204,.4)}
.tag-pill{
  font-size:9px;font-weight:700;letter-spacing:.07em;font-family:var(--mono);
  padding:1px 7px;border-radius:10px;vertical-align:middle;display:inline-block;margin-top:2px;
}
.t-hls{background:rgba(255,138,76,.1);color:var(--orange);border:1px solid rgba(255,138,76,.25)}
.t-shuf{background:var(--purple-g);color:var(--purple);border:1px solid rgba(168,126,250,.25)}
.t-multi{background:var(--blue-g);color:var(--blue);border:1px solid rgba(62,184,250,.25)}
.rtsp-chip{
  display:inline-block;font-family:var(--mono);font-size:10px;color:var(--cyan);
  background:rgba(30,232,204,.05);padding:3px 9px;border-radius:4px;
  cursor:pointer;border:1px solid rgba(30,232,204,.15);
  user-select:all;word-break:break-all;transition:.15s;max-width:280px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle;
}
.rtsp-chip:hover{background:rgba(30,232,204,.12);border-color:var(--cyan)}
.mono{font-family:var(--mono);font-size:11px}

/* ── UPLOAD ─────────────────────────────── */
.drop-zone{
  border:2px dashed var(--border2);border-radius:var(--r);
  padding:52px 40px;text-align:center;color:var(--muted);cursor:pointer;
  transition:all .25s;position:relative;overflow:hidden;
}
.drop-zone::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at center,rgba(62,184,250,.05) 0%,transparent 70%);
  opacity:0;transition:.3s;pointer-events:none;
}
.drop-zone:hover::before,.drop-zone.drag-over::before{opacity:1}
.drop-zone:hover,.drop-zone.drag-over{border-color:var(--blue);color:var(--blue)}
.drop-icon{font-size:56px;display:block;margin-bottom:14px;transition:.3s}
.drop-zone:hover .drop-icon{transform:scale(1.12) translateY(-5px)}
.file-list{list-style:none;margin-top:16px}
.file-list li{
  display:flex;align-items:center;gap:10px;padding:10px 14px;
  background:var(--bg3);border-radius:var(--rs);margin-bottom:6px;font-size:12px;
  border:1px solid var(--border);animation:slideIn .2s ease;
}
@keyframes slideIn{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}
.ubar{height:4px;background:var(--bg);border-radius:2px;flex:1;overflow:hidden;min-width:80px}
.ubar-fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan));border-radius:2px;transition:width .2s}

/* ── NOTIFICATIONS ─────────────────────── */
.notify{
  position:fixed;bottom:24px;right:24px;padding:13px 20px;
  border-radius:var(--rs);font-size:13px;font-weight:700;z-index:9999;
  transform:translateY(110px);opacity:0;
  transition:all .3s cubic-bezier(.34,1.56,.64,1);
  box-shadow:0 12px 40px rgba(0,0,0,.7);max-width:400px;
}
.notify.show{transform:translateY(0);opacity:1}
.notify.ok{background:#071a0d;border:1px solid rgba(57,224,122,.5);color:var(--green)}
.notify.err{background:#1a0709;border:1px solid rgba(255,90,110,.5);color:var(--red)}
.notify.info{background:#071320;border:1px solid rgba(62,184,250,.5);color:var(--blue)}

/* ── MODALS ──────────────────────────────── */
.modal-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(0,0,0,.85);backdrop-filter:blur(12px);
  z-index:200;align-items:center;justify-content:center;
}
.modal-overlay.open{display:flex;animation:fadeUp .18s ease}
.modal{
  background:var(--bg2);border:1px solid var(--border2);border-radius:13px;
  padding:28px;max-width:96vw;max-height:94vh;
  overflow-y:auto;box-shadow:0 30px 90px rgba(0,0,0,.8);
  animation:modalIn .22s cubic-bezier(.34,1.1,.64,1);
}
@keyframes modalIn{from{opacity:0;transform:scale(.94) translateY(16px)}to{opacity:1;transform:none}}
.modal h3{font-size:18px;margin-bottom:20px;color:var(--text);font-weight:800;
  display:flex;align-items:center;justify-content:space-between}
.modal-close{cursor:pointer;color:var(--muted);font-size:22px;line-height:1;
  transition:.15s;padding:2px 7px;border-radius:5px}
.modal-close:hover{color:var(--red);background:var(--red-g)}

/* ── DETAIL MODAL GRID ─────────────────── */
.detail-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:9px;margin-bottom:18px}
.detail-card{background:var(--bg3);border-radius:var(--rs);padding:11px 14px;border:1px solid var(--border)}
.detail-card .dk{font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;font-family:var(--mono)}
.detail-card .dv{font-size:14px;font-weight:700;font-family:var(--mono)}
.section-label{
  font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);font-family:var(--mono);
  display:flex;align-items:center;gap:10px;margin-bottom:11px;
}
.section-label::after{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--border2),transparent)}

/* ── LOG BOX ─────────────────────────────── */
.log-box{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--rs);
  padding:12px 14px;max-height:260px;overflow-y:auto;
  font-family:var(--mono);font-size:11px;line-height:1.8;
}
.ll{padding:0;border-bottom:1px solid var(--faint)}
.ll:last-child{border-bottom:none}
.li{color:var(--text)}.lw{color:var(--yellow)}.le{color:var(--red)}

/* ── PLAYLIST ITEMS (drag reorder) ──────── */
.plist-item{
  display:flex;align-items:center;gap:10px;padding:9px 13px;
  background:var(--bg3);border-radius:var(--rs);margin-bottom:5px;
  border:1px solid var(--border);cursor:grab;transition:all .15s;user-select:none;
}
.plist-item:hover{border-color:var(--border2);background:var(--bg4)}
.plist-item.current{border-color:var(--green);background:rgba(57,224,122,.05)}
.plist-item.dragging{opacity:.3;border-style:dashed;cursor:grabbing}
.plist-item.drag-target{border-color:var(--blue);border-style:dashed;background:var(--blue-g)}
.drag-handle{color:var(--muted);font-size:15px;cursor:grab;flex-shrink:0}
.pi-num{color:var(--muted);font-family:var(--mono);width:22px;font-size:10.5px;flex-shrink:0}
.pi-prio{
  font-size:9.5px;font-weight:700;font-family:var(--mono);padding:1px 8px;
  background:var(--purple-g);color:var(--purple);border:1px solid rgba(168,126,250,.3);border-radius:10px;
}

/* ── SEEK VIDEO PREVIEW ─────────────────── */
.seek-preview-box{
  background:var(--bg);border:1px solid var(--border2);border-radius:var(--rs);
  overflow:hidden;margin-top:14px;aspect-ratio:16/9;max-height:180px;position:relative;
}
.seek-preview-box video{width:100%;height:100%;object-fit:contain;background:#000}
.seek-preview-label{
  position:absolute;bottom:0;left:0;right:0;
  background:linear-gradient(transparent,rgba(0,0,0,.85));
  font-size:10.5px;font-family:var(--mono);color:var(--cyan);
  padding:6px 10px;text-align:center;
}

/* ── LOG CONTROLS ─────────────────────── */
.log-controls{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap;align-items:center}
.log-chip{
  padding:4px 13px;border-radius:20px;font-size:10px;font-weight:700;cursor:pointer;
  border:1px solid var(--border2);background:var(--bg4);color:var(--muted);
  transition:.15s;letter-spacing:.07em;font-family:var(--mono);
}
.log-chip.a-ALL{background:var(--bg5);color:var(--text);border-color:var(--border2)}
.log-chip.a-INFO{background:var(--blue-g);color:var(--blue);border-color:rgba(62,184,250,.3)}
.log-chip.a-WARN{background:var(--yellow-g);color:var(--yellow);border-color:rgba(247,195,95,.3)}
.log-chip.a-ERROR{background:var(--red-g);color:var(--red);border-color:rgba(255,90,110,.3)}

/* ── EDITOR CARD ─────────────────────── */
.ed-card{background:var(--bg3);border:1px solid var(--border2);border-radius:var(--r);padding:18px;margin-bottom:16px;transition:.2s}
.ed-card:hover{border-color:var(--border2);box-shadow:0 4px 24px rgba(0,0,0,.3)}
.ed-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:13px;border-bottom:1px solid var(--border)}
.ed-name{font-size:15px;font-weight:800;color:var(--blue);font-family:var(--mono)}

/* ── LIGHT MODE OVERRIDES ──────────── */
[data-theme="light"] .panel{box-shadow:0 1px 8px rgba(10,30,80,.08)}
[data-theme="light"] .panel:hover{box-shadow:0 4px 20px rgba(10,30,80,.13)}
[data-theme="light"] tbody tr:hover td{background:rgba(10,127,212,.04)}
[data-theme="light"] tbody tr.row-live td:first-child{border-left:2px solid var(--green)}
[data-theme="light"] .notify.ok{background:#e6f9ee;border-color:rgba(26,170,85,.5);color:var(--green)}
[data-theme="light"] .notify.err{background:#fde8ec;border-color:rgba(216,48,80,.5);color:var(--red)}
[data-theme="light"] .notify.info{background:#e6f2fc;border-color:rgba(10,127,212,.5);color:var(--blue)}
[data-theme="light"] .modal{box-shadow:0 8px 40px rgba(10,30,80,.2)}
[data-theme="light"] .modal-overlay{background:rgba(20,40,70,.6)}
[data-theme="light"] .log-box{border-color:var(--border2)}
[data-theme="light"] .rtsp-chip{background:rgba(10,127,212,.06);border-color:rgba(10,127,212,.18);color:var(--blue)}
[data-theme="light"] .rtsp-chip:hover{background:rgba(10,127,212,.12);border-color:var(--blue)}
[data-theme="light"] .drop-zone{border-color:var(--border2)}
[data-theme="light"] .drop-zone:hover,[data-theme="light"] .drop-zone.drag-over{border-color:var(--blue)}
[data-theme="light"] input:focus,[data-theme="light"] select:focus,[data-theme="light"] textarea:focus{box-shadow:0 0 0 3px rgba(10,127,212,.12)}
[data-theme="light"] .btn:hover{box-shadow:0 0 12px rgba(10,127,212,.15)}
[data-theme="light"] .stream-link{color:var(--blue)}
[data-theme="light"] .stream-link:hover{color:var(--cyan);text-shadow:none}
[data-theme="light"] .prog-track{border-color:rgba(0,0,0,.08)}
[data-theme="light"] .prog-track:hover{box-shadow:0 0 0 2px rgba(10,127,212,.3)}

/* ── RESPONSIVE ──────────────────────── */
@media(max-width:900px){
  .form-row{grid-template-columns:1fr 1fr}
  .detail-grid{grid-template-columns:1fr 1fr}
  .hdr-stats{display:none}
}
@media(max-width:600px){
  .form-row{grid-template-columns:1fr}
  .container{padding:12px 14px}
  .modal{padding:18px}
  nav button{padding:5px 8px;font-size:11px}
}
</style>
</head>
<body>

<header>
  <div class="logo-wrap">
    <div class="logo-badge">🐉</div>
    <span class="logo-text">HydraCast</span>
    <span class="logo-ver">v4.0</span>
  </div>
  <div class="hdr-stats" id="hstats">
    <div class="hdr-stat"><div class="live-dot"></div> <span id="h-live">0</span>&nbsp;Live</div>
    <div class="hdr-stat">CPU&nbsp;<span class="v" id="h-cpu">—</span></div>
    <div class="hdr-stat">RAM&nbsp;<span class="v" id="h-ram">—</span></div>
    <div class="hdr-stat">Disk&nbsp;<span class="v" id="h-disk">—</span></div>
    <div class="hdr-stat mono" id="h-time">—</div>
  </div>
  <button class="theme-btn" id="theme-btn" onclick="toggleTheme()" title="Toggle light/dark mode">🌙</button>
  <nav>
    <button class="active" onclick="showTab('streams')">Streams</button>
    <button onclick="showTab('upload')">Upload</button>
    <button onclick="showTab('library')">Library</button>
    <button onclick="showTab('editor')">Config</button>
    <button onclick="showTab('events')">Scheduler</button>
    <button onclick="showTab('logs')">Logs</button>
  </nav>
</header>

<div class="container">

<!-- ══ STREAMS ══════════════════════════════ -->
<div id="tab-streams" class="tab-content active">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Live Streams</span>
      <span style="margin-left:auto;display:flex;gap:7px;align-items:center">
        <button class="btn btn-sm btn-success" onclick="api('start_all')">▶ All</button>
        <button class="btn btn-sm btn-danger"  onclick="api('stop_all')">■ All</button>
        <button class="btn btn-sm" onclick="loadStreams()">↻</button>
        <label class="checkbox-row" style="margin:0">
          <input type="checkbox" id="auto-refresh" checked onchange="toggleAuto(this.checked)">
          <span>Auto</span>
        </label>
      </span>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>#</th><th>Stream</th><th>Port</th><th>Schedule</th>
          <th>Status</th><th>Progress &amp; Seek</th>
          <th>Position</th><th>FPS</th><th>URL</th><th>Actions</th>
        </tr></thead>
        <tbody id="stbl"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ UPLOAD ════════════════════════════════ -->
<div id="tab-upload" class="tab-content">
  <div class="panel">
    <div class="panel-hdr"><span class="panel-title">Upload Media Files</span>
      <span class="panel-sub">Saved to: <span id="upload-root-label" style="color:var(--cyan)">…/media/</span></span>
    </div>
    <div class="panel-body">
      <div class="drop-zone" id="drop-zone" onclick="document.getElementById('finput').click()">
        <span class="drop-icon">📼</span>
        <p style="font-size:17px;font-weight:800;margin-bottom:9px">Drop files here or click to browse</p>
        <p style="font-size:12px">MP4 · MKV · AVI · MOV · TS · FLV · WEBM · MP3 · AAC · FLAC · WAV · and more</p>
        <p style="font-size:10.5px;color:var(--muted);margin-top:8px;font-family:var(--mono)">Max 10 GB per file</p>
        <input type="file" id="finput" multiple style="display:none"
               accept="video/*,audio/*,.mkv,.ts,.m2ts,.flv,.webm"
               onchange="handleFiles(this.files)">
      </div>
      <ul class="file-list" id="upload-list"></ul>
      <div style="margin-top:18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span style="font-size:12.5px;color:var(--muted);white-space:nowrap">Upload to subfolder:</span>
        <select id="upload-subdir" style="flex:1;min-width:200px;width:auto"></select>
        <button class="btn btn-sm" onclick="createSubdir()">+ New Folder</button>
      </div>
    </div>
  </div>
</div>

<!-- ══ LIBRARY ════════════════════════════════ -->
<div id="tab-library" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Media Library</span>
      <span style="margin-left:auto;display:flex;gap:7px;align-items:center">
        <input type="text" id="lib-search" placeholder="Search…"
               style="width:210px;height:30px;padding:4px 10px" oninput="filterLib()">
        <select id="lib-sort" style="width:140px;height:30px;padding:2px 8px" onchange="filterLib()">
          <option value="name">Sort: Name</option>
          <option value="size">Sort: Size</option>
          <option value="dur">Sort: Duration</option>
        </select>
        <button class="btn btn-sm" onclick="loadLibrary()">↻</button>
      </span>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Filename</th><th>Duration</th><th>Size</th>
          <th>Codec</th><th>Resolution</th><th>FPS</th><th>Actions</th>
        </tr></thead>
        <tbody id="libtbl"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ CONFIG EDITOR ════════════════════════ -->
<div id="tab-editor" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Stream Configuration</span>
      <span class="panel-sub">Changes saved to streams.csv — restart to apply</span>
      <span style="margin-left:auto;display:flex;gap:7px">
        <button class="btn btn-sm btn-primary" onclick="saveCSV()">💾 Save Config</button>
        <button class="btn btn-sm" onclick="addEditorRow()">+ Add Stream</button>
      </span>
    </div>
    <div class="panel-body" id="editor-body"></div>
  </div>
</div>

<!-- ══ SCHEDULER ════════════════════════════ -->
<div id="tab-events" class="tab-content">
  <div class="panel">
    <div class="panel-hdr"><span class="panel-title">Schedule One-Shot Event</span></div>
    <div class="panel-body">
      <div class="form-row">
        <div class="form-group"><label>Stream</label><select id="evt-stream"></select></div>
        <div class="form-group"><label>Video File</label><select id="evt-file"></select></div>
        <div class="form-group"><label>Play At (local time)</label>
          <input type="datetime-local" id="evt-dt"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Start Position in File</label>
          <input type="text" id="evt-startpos" placeholder="00:00:00" value="00:00:00"></div>
        <div class="form-group"><label>After Playback</label>
          <select id="evt-post">
            <option value="resume">Resume normal playlist</option>
            <option value="stop">Stop stream</option>
            <option value="black">Show black screen</option>
          </select></div>
        <div class="form-group" style="justify-content:flex-end">
          <button class="btn btn-primary" style="margin-top:auto" onclick="schedEvent()">📅 Schedule</button>
        </div>
      </div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Scheduled Events</span>
      <span style="margin-left:auto;display:flex;gap:7px">
        <button class="btn btn-sm btn-danger" onclick="clearPlayed()">🗑 Clear Played</button>
        <button class="btn btn-sm" onclick="loadEvents()">↻</button>
      </span>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Stream</th><th>File</th><th>Play At</th>
          <th>Countdown</th><th>After</th><th>Status</th><th></th>
        </tr></thead>
        <tbody id="evtbl"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ LOGS ════════════════════════════════ -->
<div id="tab-logs" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Event Log</span>
      <span style="margin-left:auto;display:flex;gap:8px;align-items:center">
        <select id="log-stream-sel" style="width:160px;height:28px;padding:2px 8px" onchange="loadLogs()">
          <option value="">All Streams</option>
        </select>
        <button class="btn btn-sm" onclick="loadLogs()">↻</button>
        <label class="checkbox-row" style="margin:0">
          <input type="checkbox" id="log-autoscroll" checked>
          <span>Auto-scroll</span>
        </label>
      </span>
    </div>
    <div class="panel-body">
      <div class="log-controls">
        <span style="font-size:11px;color:var(--muted)">Level:</span>
        <span class="log-chip a-ALL" data-lv="ALL"   onclick="setLogLv('ALL')">ALL</span>
        <span class="log-chip" data-lv="INFO"  onclick="setLogLv('INFO')">INFO</span>
        <span class="log-chip" data-lv="WARN"  onclick="setLogLv('WARN')">WARN</span>
        <span class="log-chip" data-lv="ERROR" onclick="setLogLv('ERROR')">ERROR</span>
        <input type="text" id="log-search" placeholder="Search…"
               style="width:230px;height:28px;padding:3px 10px;margin-left:auto" oninput="renderLogs()">
      </div>
      <div id="log-box" class="log-box"></div>
    </div>
  </div>
</div>

</div><!-- /container -->

<!-- ══ DETAIL MODAL ═════════════════════ -->
<div class="modal-overlay" id="detail-modal">
  <div class="modal" style="width:720px">
    <h3>
      <span id="dm-title">Stream Detail</span>
      <span class="modal-close" onclick="closeModal('detail-modal')">✕</span>
    </h3>
    <div id="dm-body"></div>
    <div style="display:flex;gap:8px;margin-top:20px;justify-content:flex-end;flex-wrap:wrap">
      <button class="btn btn-success btn-sm" id="dm-start">▶ Start</button>
      <button class="btn btn-danger btn-sm"  id="dm-stop">■ Stop</button>
      <button class="btn btn-sm"             id="dm-rst">↺ Restart</button>
      <button class="btn btn-sm"             id="dm-skip" title="Skip to next file in playlist">⏭ Skip</button>
      <button class="btn" onclick="closeModal('detail-modal')">Close</button>
    </div>
  </div>
</div>

<!-- ══ SEEK MODAL ════════════════════════ -->
<div class="modal-overlay" id="seek-modal">
  <div class="modal" style="width:520px">
    <h3>
      <span>⏩ Seek — <span id="sk-name"></span></span>
      <span class="modal-close" onclick="closeSeekModal()">✕</span>
    </h3>
    <div class="form-group" style="margin-bottom:14px">
      <label>Jump to timestamp (HH:MM:SS or seconds)</label>
      <input type="text" id="sk-input" placeholder="00:45:30"
             onkeydown="if(event.key==='Enter')doSeek()">
    </div>
    <label>Or use the slider</label>
    <div class="seek-slider-wrap" style="margin-bottom:4px;margin-top:6px">
      <span class="mono" id="sk-cur" style="min-width:64px">00:00:00</span>
      <input type="range" id="sk-slider" min="0" max="100" value="0"
             oninput="skSliderInput(this.value)">
      <span class="mono" id="sk-dur" style="min-width:64px;text-align:right">--</span>
    </div>
    <!-- Live HLS video preview -->
    <div id="sk-preview" class="seek-preview-box" style="display:none">
      <video id="sk-video" muted playsinline autoplay></video>
      <div class="seek-preview-label">🔴 Live HLS Preview</div>
    </div>
    <div style="display:flex;gap:8px;margin-top:20px;justify-content:flex-end">
      <button class="btn" onclick="closeSeekModal()">Cancel</button>
      <button class="btn btn-primary" onclick="doSeek()">Seek to Position</button>
    </div>
  </div>
</div>

<!-- ══ PLAYLIST PRIORITY MODAL ══════════ -->
<div class="modal-overlay" id="prio-modal">
  <div class="modal" style="width:580px">
    <h3>
      <span>🎯 Playlist Order — <span id="pm-name"></span></span>
      <span class="modal-close" onclick="closeModal('prio-modal')">✕</span>
    </h3>
    <p style="font-size:12px;color:var(--muted);margin-bottom:16px">
      Drag items to reorder. Lower priority number = plays first. Click "Apply" then "Save Config" to persist changes.
    </p>
    <div id="pm-list" style="background:var(--bg);border:1px solid var(--border);border-radius:var(--rs);padding:10px;max-height:360px;overflow-y:auto"></div>
    <div style="display:flex;gap:8px;margin-top:20px;justify-content:flex-end">
      <button class="btn" onclick="closeModal('prio-modal')">Cancel</button>
      <button class="btn btn-primary" onclick="applyPriority()">Apply Order</button>
    </div>
  </div>
</div>

<div class="notify" id="notify"></div>

<script>
// ════════════════════════════════════════════════════════════
// STATE
// ════════════════════════════════════════════════════════════
let streamData=[],libData=[],logEntries=[],logLv='ALL';
let seekTarget=null,seekDuration=0,seekHls='';
let autoRefresh=true,refreshTimer=null;
let editorRows=[],prioStreamName=null,prioOrigFiles=[];
let dragSrc=null;

// ════════════════════════════════════════════════════════════
// UTILS
// ════════════════════════════════════════════════════════════
function fmtSecs(s){
  s=Math.max(0,Math.floor(+s));
  return [Math.floor(s/3600),Math.floor((s%3600)/60),s%60]
    .map(n=>String(n).padStart(2,'0')).join(':');
}
function fmtBytes(n){
  if(n<1024)return n+' B';
  if(n<1048576)return (n/1024).toFixed(1)+' KB';
  if(n<1073741824)return (n/1048576).toFixed(1)+' MB';
  return (n/1073741824).toFixed(2)+' GB';
}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
let _notifyTm;
function notify(msg,type='ok'){
  const el=document.getElementById('notify');
  el.textContent=msg;el.className='notify '+type+' show';
  clearTimeout(_notifyTm);_notifyTm=setTimeout(()=>el.classList.remove('show'),type==='err'?5000:3000);
}
function closeModal(id){document.getElementById(id).classList.remove('open')}
function openModal(id){document.getElementById(id).classList.add('open')}
document.querySelectorAll('.modal-overlay').forEach(el=>{
  el.addEventListener('click',e=>{if(e.target===el)el.classList.remove('open')});
});

// ════════════════════════════════════════════════════════════
// TABS
// ════════════════════════════════════════════════════════════
const TAB_LABELS={streams:'Streams',upload:'Upload',library:'Library',
                  editor:'Config',events:'Scheduler',logs:'Logs'};
function showTab(name){
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  document.querySelectorAll('nav button').forEach(btn=>{
    if(btn.textContent.trim()===TAB_LABELS[name])btn.classList.add('active');
  });
  if(name==='streams')      loadStreams();
  else if(name==='library') loadLibrary();
  else if(name==='editor')  loadEditor();
  else if(name==='events'){loadEvents();loadEvtForm();}
  else if(name==='logs')    loadLogs();
  else if(name==='upload')  loadSubdirs();
}

// ════════════════════════════════════════════════════════════
// API
// ════════════════════════════════════════════════════════════
async function api(action,data={}){
  try{
    const r=await fetch('/api/'+action,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    const j=await r.json();
    if(j.ok){notify(j.msg||'Done ✓');loadStreams();}
    else notify(j.msg||'Error','err');
    return j;
  }catch(e){notify('Request failed: '+e,'err');}
}

// ════════════════════════════════════════════════════════════
// HEADER STATS
// ════════════════════════════════════════════════════════════
async function updateHdrStats(){
  try{
    const[sd,st]=await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/system_stats').then(r=>r.json()),
    ]);
    streamData=sd;
    document.getElementById('h-live').textContent=sd.filter(s=>s.status==='LIVE').length;
    document.getElementById('h-cpu').textContent=st.cpu+'%';
    document.getElementById('h-ram').textContent=st.mem_percent+'%';
    document.getElementById('h-disk').textContent=st.disk_percent+'%';
  }catch(_){}
}

// ════════════════════════════════════════════════════════════
// AUTO REFRESH
// ════════════════════════════════════════════════════════════
function toggleAuto(on){
  autoRefresh=on;
  if(on)startRefresh();else clearInterval(refreshTimer);
}
function startRefresh(){
  clearInterval(refreshTimer);
  refreshTimer=setInterval(()=>{loadStreams();updateHdrStats();},2500);
}

// ════════════════════════════════════════════════════════════
// STREAMS TABLE
// ════════════════════════════════════════════════════════════
async function loadStreams(){
  try{
    const r=await fetch('/api/streams');
    streamData=await r.json();
    renderStreams();
  }catch(e){}
}

function _buildStreamRow(s,i){
  const pct=(+s.progress).toFixed(1);
  const fc=s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
  const live=s.status==='LIVE';
  const nf=s.playlist_count||1;
  return `
<tr class="${live?'row-live':''}" data-stream="${esc(s.name)}">
  <td class="mono" style="color:var(--muted);font-size:11px">${i+1}</td>
  <td>
    <div class="stream-link" onclick="openDetail('${esc(s.name)}')">${esc(s.name)}</div>
    <div style="display:flex;gap:4px;margin-top:3px;flex-wrap:wrap">
      ${s.shuffle?'<span class="tag-pill t-shuf">SHUFFLE</span>':''}
      ${s.hls_url?'<span class="tag-pill t-hls">HLS</span>':''}
      ${nf>1?'<span class="tag-pill t-multi">×'+nf+' files</span>':''}
    </div>
  </td>
  <td><code class="mono" style="color:var(--cyan)">:${s.port}</code></td>
  <td style="color:var(--muted);font-size:11.5px;white-space:nowrap">${esc(s.weekdays)}</td>
  <td data-cell="status"><span class="badge badge-${esc(s.status)}"><div class="bdot"></div>${esc(s.status)}</span></td>
  <td style="min-width:240px">
    <div class="prog-wrap">
      <div class="prog-track ${live?'live':''}"
           ${live?`onclick="barClick(event,'${esc(s.name)}',${s.duration})" title="Click to seek"`:''}
           style="cursor:${live?'crosshair':'default'}">
        <div class="prog-fill" data-cell="fill" style="width:${pct}%;background:${fc}"></div>
      </div>
      <div class="prog-labels">
        <span data-cell="pos-start">${live?esc((s.position||'').split('/')[0].trim()||'--'):'--'}</span>
        <span class="prog-pct" data-cell="pct">${pct}%</span>
        <span data-cell="pos-end">${live?esc((s.position||'').split('/')[1]||'--'):'--'}</span>
      </div>
    </div>
    ${live?`
    <div class="seek-slider-wrap">
      <span class="mono" style="font-size:10px;min-width:52px" data-cell="sl-start">${esc((s.position||'').split('/')[0].trim()||'--')}</span>
      <input type="range" min="0" max="${Math.max(1,Math.floor(s.duration))}"
             value="${Math.floor(s.current_secs)}"
             data-cell="slider" data-stream="${esc(s.name)}" data-dur="${Math.floor(s.duration)}"
             title="Drag to seek"
             oninput="this.previousElementSibling.textContent=fmtSecs(this.value)"
             onchange="inlineSeek('${esc(s.name)}',+this.value)">
      <span class="mono" style="font-size:10px;min-width:52px;text-align:right" data-cell="sl-end">${esc((s.position||'').split('/')[1]||'--')}</span>
    </div>`:''}
  </td>
  <td class="mono pos-cell" style="color:var(--muted);font-size:11px;white-space:nowrap">${esc(s.position||'--')}</td>
  <td class="mono" style="color:var(--muted)">${s.fps>0?Math.round(s.fps):'--'}</td>
  <td>
    <span class="rtsp-chip" onclick="copyURL('${esc(s.rtsp_url)}')" title="Click to copy">${esc(s.rtsp_url)}</span>
    ${s.hls_url?`<br><span class="rtsp-chip" style="color:var(--orange);margin-top:3px" onclick="copyURL('${esc(s.hls_url)}')">HLS</span>`:''}
  </td>
  <td style="white-space:nowrap">
    <div style="display:flex;gap:3px;flex-wrap:wrap">
      <button class="btn btn-xs btn-success" onclick="api('start',{name:'${esc(s.name)}'})" title="Start">▶</button>
      <button class="btn btn-xs btn-danger"  onclick="api('stop',{name:'${esc(s.name)}'})"  title="Stop">■</button>
      <button class="btn btn-xs" onclick="api('restart',{name:'${esc(s.name)}'})" title="Restart">↺</button>
      <button class="btn btn-xs" onclick="openSeek('${esc(s.name)}',${s.duration},${s.current_secs},'${esc(s.hls_url||'')}')" title="Seek">⏩</button>
      ${nf>1?`<button class="btn btn-xs" onclick="openPrio('${esc(s.name)}')" title="Playlist order">🎯</button>`:''}
      ${live&&nf>1?`<button class="btn btn-xs" onclick="api('skip_next',{name:'${esc(s.name)}'})" title="Skip to next">⏭</button>`:''}
    </div>
  </td>
</tr>`;
}

function renderStreams(){
  const tb=document.getElementById('stbl');
  const nameKey=streamData.map(s=>s.name).join('\x00');

  // Full rebuild when stream list changes
  if(tb.dataset.nameKey!==nameKey){
    tb.dataset.nameKey=nameKey;
    tb.innerHTML=streamData.map((s,i)=>_buildStreamRow(s,i)).join('');
    return;
  }

  // In-place update — keeps slider thumb position while user drags
  const activeSlider=document.activeElement?.dataset?.stream;
  streamData.forEach((s,i)=>{
    const row=tb.querySelector(`tr[data-stream="${CSS.escape(s.name)}"]`);
    if(!row)return;
    const pct=(+s.progress).toFixed(1);
    const fc=s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
    const live=s.status==='LIVE';
    const pos=(s.position||'');
    const posStart=pos.split('/')[0]?.trim()||'--';
    const posEnd=pos.split('/')[1]?.trim()||'--';

    // Update row class
    row.className=live?'row-live':'';

    // Status badge
    const sc=row.querySelector('[data-cell="status"]');
    if(sc)sc.innerHTML=`<span class="badge badge-${esc(s.status)}"><div class="bdot"></div>${esc(s.status)}</span>`;

    // Progress fill & labels
    const fill=row.querySelector('[data-cell="fill"]');
    if(fill){fill.style.width=pct+'%';fill.style.background=fc;}
    const pctEl=row.querySelector('[data-cell="pct"]');
    if(pctEl)pctEl.textContent=pct+'%';
    const ps=row.querySelector('[data-cell="pos-start"]');
    if(ps)ps.textContent=live?posStart:'--';
    const pe=row.querySelector('[data-cell="pos-end"]');
    if(pe)pe.textContent=live?posEnd:'--';

    // Seek slider — skip if user is actively dragging this stream's slider
    if(s.name!==activeSlider){
      const sl=row.querySelector('[data-cell="slider"]');
      if(sl){
        sl.value=Math.floor(s.current_secs);
        sl.max=Math.max(1,Math.floor(s.duration));
        const slStart=row.querySelector('[data-cell="sl-start"]');
        const slEnd=row.querySelector('[data-cell="sl-end"]');
        if(slStart)slStart.textContent=posStart;
        if(slEnd)slEnd.textContent=posEnd;
      }
    }

    // Position cell
    const posCell=row.querySelector('.pos-cell');
    if(posCell)posCell.textContent=s.position||'--';
  });
}
function copyURL(url){navigator.clipboard.writeText(url).then(()=>notify('Copied ✓','info'));}
function barClick(e,name,dur){
  if(dur<=0)return;
  const rect=e.currentTarget.getBoundingClientRect();
  const pct=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));
  const secs=Math.floor(pct*dur);
  api('seek',{name,seconds:secs}).then(()=>setTimeout(loadStreams,600));
}
function inlineSeek(name,secs){
  api('seek',{name,seconds:secs}).then(()=>setTimeout(loadStreams,600));
}

// ════════════════════════════════════════════════════════════
// STREAM DETAIL MODAL
// ════════════════════════════════════════════════════════════
async function openDetail(name){
  try{
    const d=await fetch('/api/stream_detail?name='+encodeURIComponent(name)).then(r=>r.json());
    if(d.error){notify(d.error,'err');return;}
    document.getElementById('dm-title').textContent=d.name;
    document.getElementById('dm-start').onclick=()=>{api('start',{name:d.name});closeModal('detail-modal');};
    document.getElementById('dm-stop' ).onclick=()=>{api('stop',{name:d.name});closeModal('detail-modal');};
    document.getElementById('dm-rst'  ).onclick=()=>{api('restart',{name:d.name});closeModal('detail-modal');};
    document.getElementById('dm-skip' ).onclick=()=>{api('skip_next',{name:d.name});closeModal('detail-modal');};
    const pct=(+d.progress).toFixed(1);
    const fc=d.progress>80?'var(--red)':d.progress>55?'var(--yellow)':'var(--green)';
    const isLive=d.status==='LIVE';
    const plHtml=(d.playlist||[]).map((p,i)=>`
      <div class="plist-item ${p.current?'current':''}">
        <span style="font-size:11px;color:var(--muted);width:20px">${i+1}</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px" title="${esc(p.path)}">${esc(p.file)}</span>
        <span class="mono" style="color:var(--muted);font-size:10px">${esc(p.start)}</span>
        <span class="pi-prio">P${p.priority}</span>
        ${p.current?'<span style="color:var(--green);font-size:10px;font-weight:700">▶ NOW</span>':''}
        ${!p.exists?'<span style="color:var(--red);font-size:10px">✗ MISSING</span>':''}
      </div>`).join('');
    const logHtml=(d.log||[]).slice(-50).map(line=>{
      const lv=/error/i.test(line)?'e':/warn|restart/i.test(line)?'w':'i';
      return `<div class="ll l${lv}">${esc(line)}</div>`;
    }).join('');
    document.getElementById('dm-body').innerHTML=`
      <div class="detail-grid">
        <div class="detail-card"><div class="dk">Status</div><div class="dv"><span class="badge badge-${esc(d.status)}"><div class="bdot"></div>${esc(d.status)}</span></div></div>
        <div class="detail-card"><div class="dk">Port</div><div class="dv" style="color:var(--cyan)">:${d.port}</div></div>
        <div class="detail-card"><div class="dk">Video BR</div><div class="dv">${esc(d.video_bitrate)}</div></div>
        <div class="detail-card"><div class="dk">Audio BR</div><div class="dv">${esc(d.audio_bitrate)}</div></div>
        <div class="detail-card"><div class="dk">Schedule</div><div class="dv" style="font-size:11px">${esc(d.weekdays)}</div></div>
        <div class="detail-card"><div class="dk">Restarts</div><div class="dv" style="color:${d.restart_count>0?'var(--yellow)':'var(--green)'}">${d.restart_count}</div></div>
        <div class="detail-card"><div class="dk">Loops</div><div class="dv">${d.loop_count}</div></div>
        <div class="detail-card"><div class="dk">Speed</div><div class="dv">${esc(d.speed||'--')}</div></div>
      </div>
      ${d.error_msg?`<div style="background:var(--red-g);border:1px solid rgba(255,90,110,.3);border-radius:var(--rs);padding:10px 14px;font-size:11px;color:var(--red);margin-bottom:16px;font-family:var(--mono)">${esc(d.error_msg)}</div>`:''}
      <div class="section-label">Progress</div>
      <div class="prog-wrap" style="margin-bottom:14px">
        <div class="prog-track ${isLive?'live':''}"
             ${isLive?`onclick="barClick(event,'${esc(d.name)}',${d.duration})" title="Click to seek"`:''}
             style="cursor:${isLive?'crosshair':'default'}">
          <div class="prog-fill" style="width:${pct}%;background:${fc}"></div>
        </div>
        <div class="prog-labels">
          <span class="mono">${fmtSecs(d.current_pos)}</span>
          <span class="prog-pct">${pct}%</span>
          <span class="mono">${fmtSecs(d.duration)}</span>
        </div>
      </div>
      ${isLive&&d.duration>0?`
      <div class="seek-slider-wrap" style="margin-bottom:18px">
        <span class="mono" style="font-size:10px;min-width:64px">${fmtSecs(d.current_pos)}</span>
        <input type="range" min="0" max="${Math.floor(d.duration)}" value="${Math.floor(d.current_pos)}"
               oninput="this.previousElementSibling.textContent=fmtSecs(this.value)"
               onchange="api('seek',{name:'${esc(d.name)}',seconds:+this.value})">
        <span class="mono" style="font-size:10px;min-width:64px;text-align:right">${fmtSecs(d.duration)}</span>
      </div>`:''}
      <div class="section-label">Playlist — ${(d.playlist||[]).length} file${(d.playlist||[]).length!==1?'s':''}</div>
      <div style="margin-bottom:18px">${plHtml||'<span style="color:var(--muted)">No files</span>'}</div>
      <div class="section-label">Recent Log</div>
      <div class="log-box">${logHtml||'<span style="color:var(--muted)">No entries</span>'}</div>
      ${d.rtsp_url?`
      <div style="margin-top:16px">
        <div class="section-label">Stream URLs</div>
        <div style="display:flex;flex-direction:column;gap:5px">
          <span class="rtsp-chip" onclick="copyURL('${esc(d.rtsp_url)}')" title="Copy RTSP URL">${esc(d.rtsp_url)}</span>
          ${d.hls_url?`<span class="rtsp-chip" style="color:var(--orange)" onclick="copyURL('${esc(d.hls_url)}')" title="Copy HLS URL">${esc(d.hls_url)}</span>`:''}
        </div>
      </div>`:''}
    `;
    openModal('detail-modal');
  }catch(e){notify('Failed to load detail','err');}
}

// ════════════════════════════════════════════════════════════
// SEEK MODAL  (with live HLS video preview)
// ════════════════════════════════════════════════════════════
function openSeek(name,dur,curSecs,hlsUrl){
  seekTarget=name;seekDuration=dur;seekHls=hlsUrl||'';
  document.getElementById('sk-name').textContent=name;
  document.getElementById('sk-input').value='';
  const sl=document.getElementById('sk-slider');
  sl.max=Math.floor(dur);sl.value=Math.floor(curSecs);
  document.getElementById('sk-cur').textContent=fmtSecs(curSecs);
  document.getElementById('sk-dur').textContent=fmtSecs(dur);
  const prev=document.getElementById('sk-preview');
  const vid=document.getElementById('sk-video');
  if(hlsUrl){
    prev.style.display='block';
    vid.src=hlsUrl;
    try{vid.play();}catch(_){}
  }else{
    prev.style.display='none';vid.src='';
  }
  openModal('seek-modal');
  setTimeout(()=>document.getElementById('sk-input').focus(),80);
}
function closeSeekModal(){
  const vid=document.getElementById('sk-video');
  vid.pause();vid.src='';
  closeModal('seek-modal');
}
function skSliderInput(v){
  document.getElementById('sk-cur').textContent=fmtSecs(v);
}
function doSeek(){
  let secs;
  const txt=document.getElementById('sk-input').value.trim();
  if(txt){
    const p=txt.split(':').map(Number);
    secs=p.length===3?p[0]*3600+p[1]*60+p[2]:p.length===2?p[0]*60+p[1]:+p[0];
    if(isNaN(secs)||secs<0){notify('Invalid time format','err');return;}
  }else{
    secs=+document.getElementById('sk-slider').value;
  }
  if(secs>seekDuration&&seekDuration>0){notify('Position beyond duration','err');return;}
  api('seek',{name:seekTarget,seconds:secs});
  closeSeekModal();
}

// ════════════════════════════════════════════════════════════
// PRIORITY / PLAYLIST REORDER MODAL
// ════════════════════════════════════════════════════════════
async function openPrio(name){
  try{
    const d=await fetch('/api/stream_detail?name='+encodeURIComponent(name)).then(r=>r.json());
    if(d.error){notify(d.error,'err');return;}
    prioStreamName=name;
    prioOrigFiles=d.playlist||[];
    document.getElementById('pm-name').textContent=name;
    const list=document.getElementById('pm-list');
    list.innerHTML=prioOrigFiles.map((p,i)=>`
      <div class="plist-item" draggable="true" data-idx="${i}" data-path="${esc(p.path)}" data-start="${esc(p.start)}" data-priority="${p.priority}">
        <span class="drag-handle" title="Drag to reorder">⠿</span>
        <span class="pi-num">${i+1}</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px"
              title="${esc(p.path)}">${esc(p.file)}</span>
        <span class="mono" style="color:var(--muted);font-size:10px">${esc(p.start)}</span>
        <span class="pi-prio" contenteditable="true" style="min-width:30px;cursor:text"
              title="Edit priority number">${p.priority}</span>
        ${p.current?'<span style="color:var(--green);font-size:10px">▶ NOW</span>':''}
        ${!p.exists?'<span style="color:var(--red);font-size:10px">✗ MISSING</span>':''}
      </div>`).join('');
    setupDragDrop(list);
    openModal('prio-modal');
  }catch(e){notify('Failed to load playlist','err');}
}

function setupDragDrop(container){
  let src=null;
  container.querySelectorAll('.plist-item').forEach(el=>{
    el.addEventListener('dragstart',e=>{
      src=el;el.classList.add('dragging');e.dataTransfer.effectAllowed='move';
    });
    el.addEventListener('dragend',()=>{
      el.classList.remove('dragging');
      container.querySelectorAll('.plist-item').forEach(x=>x.classList.remove('drag-target'));
    });
    el.addEventListener('dragover',e=>{
      e.preventDefault();
      container.querySelectorAll('.plist-item').forEach(x=>x.classList.remove('drag-target'));
      el.classList.add('drag-target');
    });
    el.addEventListener('drop',e=>{
      e.preventDefault();
      if(!src||src===el)return;
      const items=[...container.querySelectorAll('.plist-item')];
      const si=items.indexOf(src),di=items.indexOf(el);
      if(si<di)el.after(src);else el.before(src);
      container.querySelectorAll('.plist-item').forEach((x,j)=>{
        x.dataset.idx=j;x.querySelector('.pi-num').textContent=j+1;
      });
      container.querySelectorAll('.plist-item').forEach(x=>x.classList.remove('drag-target'));
    });
  });
}

function applyPriority(){
  if(!prioStreamName)return;
  const items=[...document.getElementById('pm-list').querySelectorAll('.plist-item')];
  const newFiles=items.map((el,i)=>{
    const path=el.dataset.path;
    const start=el.dataset.start;
    const priEl=el.querySelector('.pi-prio');
    const pri=parseInt(priEl?.textContent?.trim()||String(i+1))||i+1;
    return `${path}@${start}#${pri}`;
  });
  // Update editorRows if loaded, otherwise just notify
  const idx=editorRows.findIndex(r=>r.name===prioStreamName);
  if(idx>=0){
    editorRows[idx].files=newFiles.join(';');
    renderEditor();
    notify('Playlist order updated — click Save Config to persist');
  }else{
    notify('Open Config tab first, then reorder','info');
  }
  closeModal('prio-modal');
}

// ════════════════════════════════════════════════════════════
// UPLOAD
// ════════════════════════════════════════════════════════════
const dz=document.getElementById('drop-zone');
dz.addEventListener('dragover',e=>{e.preventDefault();dz.classList.add('drag-over')});
dz.addEventListener('dragleave',()=>dz.classList.remove('drag-over'));
dz.addEventListener('drop',e=>{e.preventDefault();dz.classList.remove('drag-over');handleFiles(e.dataTransfer.files)});
const MAX_UP=10*1024*1024*1024;

function handleFiles(files){Array.from(files).forEach(uploadFile);}

function uploadFile(file){
  if(file.size>MAX_UP){notify(file.name+': exceeds 10 GB limit','err');return;}
  const key='f'+Math.random().toString(36).slice(2,8);
  const subdir=document.getElementById('upload-subdir').value;
  const li=document.createElement('li');
  li.innerHTML=`
    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(file.name)}</span>
    <span class="mono" style="color:var(--muted)">${fmtBytes(file.size)}</span>
    <div class="ubar"><div class="ubar-fill" id="ub-${key}" style="width:0"></div></div>
    <span id="up-${key}" class="mono" style="color:var(--muted);min-width:36px;text-align:right">0%</span>`;
  document.getElementById('upload-list').appendChild(li);
  const fd=new FormData();fd.append('file',file);fd.append('subdir',subdir);
  const xhr=new XMLHttpRequest();
  xhr.upload.onprogress=e=>{
    if(!e.lengthComputable)return;
    const pct=Math.round(e.loaded/e.total*100);
    const b=document.getElementById('ub-'+key),p=document.getElementById('up-'+key);
    if(b)b.style.width=pct+'%';if(p)p.textContent=pct+'%';
  };
  xhr.onload=()=>{
    const p=document.getElementById('up-'+key);
    try{
      const j=JSON.parse(xhr.responseText);
      if(xhr.status===200&&j.ok){if(p){p.textContent='✓';p.style.color='var(--green)';}notify(file.name+' uploaded ✓');}
      else{if(p){p.textContent='✗';p.style.color='var(--red)';}notify('Upload failed: '+(j.msg||file.name),'err');}
    }catch(_){if(p){p.textContent='✗';p.style.color='var(--red)';}notify('Upload error','err');}
  };
  xhr.onerror=()=>notify('Network error: '+file.name,'err');
  xhr.open('POST','/api/upload');xhr.send(fd);
}

async function loadSubdirs(){
  try{
    const data=await fetch('/api/subdirs').then(r=>r.json());
    const sel=document.getElementById('upload-subdir');
    sel.innerHTML='<option value="">/ (media root)</option>';
    (data.dirs||[]).filter(d=>d).forEach(d=>{
      const o=document.createElement('option');o.value=d;o.textContent=d;sel.appendChild(o);
    });
    if(data.root_label){
      document.getElementById('upload-root-label').textContent=data.root_label;
    }
  }catch(_){}
}

async function createSubdir(){
  const name=prompt('New folder name (no special characters):');
  if(!name||!name.trim())return;
  if(/[\/\\<>"|?*\x00]/.test(name)||name.includes('..')){notify('Invalid folder name','err');return;}
  const r=await api('create_subdir',{name:name.trim()});
  if(r&&r.ok)loadSubdirs();
}

// ════════════════════════════════════════════════════════════
// LIBRARY
// ════════════════════════════════════════════════════════════
async function loadLibrary(){
  const tb=document.getElementById('libtbl');
  tb.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:28px">Loading…</td></tr>';
  try{
    libData=await fetch('/api/library').then(r=>r.json());
    filterLib();
  }catch(e){tb.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--red);padding:28px">Failed to load library</td></tr>';}
}
function filterLib(){
  const q=document.getElementById('lib-search').value.toLowerCase();
  const srt=document.getElementById('lib-sort').value;
  let data=libData.filter(f=>f.path.toLowerCase().includes(q));
  if(srt==='size')data.sort((a,b)=>b.size_bytes-a.size_bytes);
  else if(srt==='dur')data.sort((a,b)=>b.duration_secs-a.duration_secs);
  else data.sort((a,b)=>a.path.localeCompare(b.path));
  renderLib(data);
}
function renderLib(data){
  const tb=document.getElementById('libtbl');
  if(!data.length){tb.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:28px">No files found.</td></tr>';return;}
  tb.innerHTML=data.map(f=>`
<tr>
  <td class="mono" style="word-break:break-all;font-size:11px;max-width:340px" title="${esc(f.full_path)}">${esc(f.path)}</td>
  <td class="mono" style="white-space:nowrap;color:var(--cyan)">${esc(f.duration)||'--'}</td>
  <td class="mono" style="white-space:nowrap;color:var(--muted)">${esc(f.size)||'--'}</td>
  <td style="font-size:11.5px;color:var(--muted)">${esc(f.video_codec)||'--'}</td>
  <td style="font-size:11.5px;color:var(--muted)">${f.width&&f.height?f.width+'×'+f.height:'--'}</td>
  <td style="font-size:11.5px;color:var(--muted)">${f.fps?f.fps+' fps':'--'}</td>
  <td style="white-space:nowrap">
    <button class="btn btn-xs" onclick="copyURL('${esc(f.full_path)}')" title="Copy path">📋</button>
    <button class="btn btn-xs btn-danger" onclick="delFile('${esc(f.full_path)}')" title="Delete">🗑</button>
  </td>
</tr>`).join('');
}
async function delFile(path){
  if(!confirm('Permanently delete?\n'+path))return;
  const r=await api('delete_file',{path});
  if(r&&r.ok)loadLibrary();
}

// ════════════════════════════════════════════════════════════
// CONFIG EDITOR
// ════════════════════════════════════════════════════════════
async function loadEditor(){
  try{
    editorRows=await fetch('/api/streams_config').then(r=>r.json());
    renderEditor();
  }catch(e){notify('Failed to load config','err');}
}
function renderEditor(){
  const c=document.getElementById('editor-body');
  if(!editorRows.length){c.innerHTML='<p style="color:var(--muted);text-align:center;padding:28px">No streams configured. Click "+ Add Stream" to start.</p>';return;}
  c.innerHTML=editorRows.map((row,idx)=>`
<div class="ed-card">
  <div class="ed-head">
    <span class="ed-name">${esc(row.name)}</span>
    <div style="display:flex;gap:6px">
      ${(row.files||'').split(';').filter(f=>f.trim()).length>1
        ?`<button class="btn btn-sm" onclick="openPrioForEditor(${idx})" title="Reorder playlist">🎯 Reorder</button>`:''}
      <button class="btn btn-sm btn-danger" onclick="removeEdRow(${idx})">✕ Remove</button>
    </div>
  </div>
  <div class="form-row">
    <div class="form-group"><label>Name</label>
      <input value="${esc(row.name)}" oninput="editorRows[${idx}].name=this.value.trim()"></div>
    <div class="form-group"><label>Port</label>
      <input type="number" min="1024" max="65535" value="${row.port}" onchange="editorRows[${idx}].port=+this.value"></div>
    <div class="form-group"><label>RTSP Path</label>
      <input value="${esc(row.stream_path||'stream')}" onchange="editorRows[${idx}].stream_path=this.value.trim()"></div>
    <div class="form-group"><label>Weekdays</label>
      <input value="${esc(row.weekdays||'all')}" onchange="editorRows[${idx}].weekdays=this.value.trim()">
      <span class="form-hint">all | mon|wed|fri | weekdays | weekends</span></div>
  </div>
  <div class="form-row">
    <div class="form-group"><label>Video Bitrate</label>
      <input value="${esc(row.video_bitrate||'2500k')}" onchange="editorRows[${idx}].video_bitrate=this.value.trim()"></div>
    <div class="form-group"><label>Audio Bitrate</label>
      <input value="${esc(row.audio_bitrate||'128k')}" onchange="editorRows[${idx}].audio_bitrate=this.value.trim()"></div>
    <div class="form-group"><label>Options</label>
      <div style="display:flex;gap:18px;margin-top:10px;flex-wrap:wrap">
        <label class="checkbox-row"><input type="checkbox" ${row.enabled?'checked':''} onchange="editorRows[${idx}].enabled=this.checked"><span>Enabled</span></label>
        <label class="checkbox-row"><input type="checkbox" ${row.shuffle?'checked':''} onchange="editorRows[${idx}].shuffle=this.checked"><span>Shuffle</span></label>
        <label class="checkbox-row"><input type="checkbox" ${row.hls_enabled?'checked':''} onchange="editorRows[${idx}].hls_enabled=this.checked"><span>HLS</span></label>
      </div></div>
  </div>
  <div class="form-group">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
      <label style="margin:0">Playlist Files</label>
      <span class="form-hint">Format: /path/file.mp4@HH:MM:SS#priority  (one per line, ; or newline separated)</span>
    </div>
    <textarea rows="4" style="font-family:var(--mono);font-size:11px;resize:vertical"
      oninput="editorRows[${idx}].files=this.value">${esc((row.files||'').split(';').join('\n'))}</textarea>
    <span class="form-hint">Example: /media/intro.mp4@00:00:00#1 &nbsp;|&nbsp; /media/main.mp4@00:00:00#2 &nbsp;|&nbsp; lower # plays first</span>
  </div>
</div>`).join('');
}
function addEditorRow(){
  editorRows.push({name:'NewStream',port:8560,files:'',weekdays:'all',
    enabled:true,shuffle:false,stream_path:'stream',
    video_bitrate:'2500k',audio_bitrate:'128k',hls_enabled:false});
  renderEditor();
  document.getElementById('editor-body').lastElementChild?.scrollIntoView({behavior:'smooth'});
}
function removeEdRow(idx){
  if(!confirm('Remove stream "'+editorRows[idx].name+'"?'))return;
  editorRows.splice(idx,1);renderEditor();
}
function openPrioForEditor(idx){
  prioStreamName=editorRows[idx].name;
  prioOrigFiles=(editorRows[idx].files||'').split(';').filter(f=>f.trim()).map((f,i)=>{
    const hsh=f.lastIndexOf('#'),at=f.lastIndexOf('@');
    const pri=hsh>at?parseInt(f.slice(hsh+1))||i+1:i+1;
    const withoutPri=hsh>at?f.slice(0,hsh):f;
    const path=at>0?withoutPri.slice(0,at):withoutPri;
    const start=at>0?withoutPri.slice(at+1):'00:00:00';
    return{file:path.split('/').pop()||path,path:path.trim(),start:start.trim(),priority:pri,exists:true,current:false};
  });
  document.getElementById('pm-name').textContent=prioStreamName;
  const list=document.getElementById('pm-list');
  list.innerHTML=prioOrigFiles.map((p,i)=>`
    <div class="plist-item" draggable="true" data-idx="${i}" data-path="${esc(p.path)}" data-start="${esc(p.start)}" data-priority="${p.priority}">
      <span class="drag-handle">⠿</span>
      <span class="pi-num">${i+1}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px">${esc(p.file)}</span>
      <span class="mono" style="color:var(--muted);font-size:10px">${esc(p.start)}</span>
      <span class="pi-prio" contenteditable="true" title="Edit priority">${p.priority}</span>
    </div>`).join('');
  setupDragDrop(list);
  openModal('prio-modal');
}
async function saveCSV(){
  const rows=editorRows.map(r=>({...r,files:(r.files||'').replace(/\n+/g,';').replace(/;+/g,';').trim()}));
  const ports=rows.map(r=>r.port);
  if(new Set(ports).size!==ports.length){notify('Duplicate port numbers detected!','err');return;}
  const names=rows.map(r=>r.name);
  if(new Set(names).size!==names.length){notify('Duplicate stream names detected!','err');return;}
  const res=await api('save_config',{streams:rows});
  if(res&&res.ok)loadEditor();
}

// ════════════════════════════════════════════════════════════
// EVENTS / SCHEDULER
// ════════════════════════════════════════════════════════════
async function loadEvtForm(){
  try{
    const[streams,lib]=await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/library').then(r=>r.json()),
    ]);
    document.getElementById('evt-stream').innerHTML=streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)} (:${s.port})</option>`).join('');
    document.getElementById('evt-file').innerHTML=lib.map(f=>`<option value="${esc(f.full_path)}">${esc(f.path)}</option>`).join('');
    const dt=new Date(Date.now()+5*60000);
    document.getElementById('evt-dt').value=new Date(dt-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);
    const sel=document.getElementById('log-stream-sel');
    sel.innerHTML='<option value="">All Streams</option>'+streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
  }catch(_){}
}
async function schedEvent(){
  const stream=document.getElementById('evt-stream').value;
  const file=document.getElementById('evt-file').value;
  const dt=document.getElementById('evt-dt').value;
  const pos=document.getElementById('evt-startpos').value||'00:00:00';
  const post=document.getElementById('evt-post').value;
  if(!stream||!file||!dt){notify('Fill all required fields','err');return;}
  if(!/^\d{2}:\d{2}:\d{2}$/.test(pos)){notify('Start position must be HH:MM:SS','err');return;}
  await api('add_event',{stream_name:stream,file_path:file,play_at:dt,start_pos:pos,post_action:post});
  loadEvents();
}
async function loadEvents(){
  try{
    const data=await fetch('/api/events').then(r=>r.json());
    const now=Date.now();
    const tb=document.getElementById('evtbl');
    tb.innerHTML=data.map(ev=>{
      const pa=new Date(ev.play_at.replace(' ','T'));
      const d=((pa-now)/1000).toFixed(0);
      const cd=ev.played?'--':d>0?`in ${Math.floor(d/60)}m ${d%60}s`:`${Math.abs(d)}s ago`;
      return `<tr>
        <td style="font-weight:700;color:var(--blue)">${esc(ev.stream_name)}</td>
        <td class="mono" style="font-size:11px">${esc(ev.file_name)}</td>
        <td class="mono" style="font-size:11px;white-space:nowrap">${esc(ev.play_at)}</td>
        <td class="mono" style="font-size:11px;color:${d>0?'var(--yellow)':'var(--muted)'}">${cd}</td>
        <td style="font-size:11.5px">${esc(ev.post_action)}</td>
        <td><span class="badge ${ev.played?'badge-STOPPED':'badge-SCHED'}"><div class="bdot"></div>${ev.played?'Played':'Pending'}</span></td>
        <td><button class="btn btn-xs btn-danger" onclick="delEvent('${esc(ev.event_id)}')">✕</button></td>
      </tr>`;
    }).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:28px">No events scheduled.</td></tr>';
  }catch(_){}
}
async function delEvent(id){
  if(!confirm('Delete this event?'))return;
  const r=await api('delete_event',{event_id:id});
  if(r&&r.ok)loadEvents();
}
async function clearPlayed(){
  if(!confirm('Remove all played events?'))return;
  const r=await fetch('/api/events').then(r=>r.json());
  for(const id of r.filter(e=>e.played).map(e=>e.event_id))
    await fetch('/api/delete_event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:id})});
  loadEvents();
}

// ════════════════════════════════════════════════════════════
// LOGS
// ════════════════════════════════════════════════════════════
function setLogLv(lv){
  logLv=lv;
  document.querySelectorAll('.log-chip').forEach(c=>{
    c.className='log-chip'+(c.dataset.lv===lv?' a-'+lv:'');
  });
  renderLogs();
}
async function loadLogs(){
  try{
    const stream=document.getElementById('log-stream-sel').value;
    const data=await fetch(`/api/logs?level=${logLv}&stream=${encodeURIComponent(stream)}&n=600`).then(r=>r.json());
    logEntries=data.entries||[];
    renderLogs();
  }catch(_){}
}
function renderLogs(){
  const q=(document.getElementById('log-search').value||'').toLowerCase();
  const el=document.getElementById('log-box');
  el.innerHTML=logEntries
    .filter(([m])=>!q||m.toLowerCase().includes(q))
    .slice().reverse()
    .map(([m,lv])=>`<div class="ll l${lv==='ERROR'?'e':lv==='WARN'?'w':'i'}">${esc(m)}</div>`)
    .join('')||'<span style="color:var(--muted)">No log entries.</span>';
  if(document.getElementById('log-autoscroll').checked)el.scrollTop=0;
}

// ════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════
// ════════════════════════════════════════════════════════════
// THEME TOGGLE
// ════════════════════════════════════════════════════════════
function toggleTheme(){
  const root=document.documentElement;
  const isLight=root.dataset.theme==='light';
  root.dataset.theme=isLight?'dark':'light';
  document.getElementById('theme-btn').textContent=isLight?'🌙':'☀️';
  try{localStorage.setItem('hc-theme',root.dataset.theme);}catch(_){}
}
(function(){
  try{
    const saved=localStorage.getItem('hc-theme');
    if(saved){
      document.documentElement.dataset.theme=saved;
      const btn=document.getElementById('theme-btn');
      if(btn)btn.textContent=saved==='light'?'☀️':'🌙';
    }
  }catch(_){}
})();

loadStreams();
updateHdrStats();
startRefresh();
setInterval(updateHdrStats,5000);
setInterval(()=>{
  if(document.getElementById('tab-events').classList.contains('active'))loadEvents();
  if(document.getElementById('tab-logs').classList.contains('active'))loadLogs();
},8000);
setInterval(()=>{
  const now=new Date();
  const el=document.getElementById('h-time');
  if(el)el.textContent=[now.getHours(),now.getMinutes(),now.getSeconds()].map(n=>String(n).padStart(2,'0')).join(':');
},1000);
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT')return;
  if(e.key==='Escape')document.querySelectorAll('.modal-overlay.open').forEach(m=>m.classList.remove('open'));
  if(e.key==='r'||e.key==='R')loadStreams();
});
</script>
</body>
</html>"""


# =============================================================================
# SECURITY HEADERS
# =============================================================================
_SEC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options":        "SAMEORIGIN",
    "X-XSS-Protection":       "1; mode=block",
    "Referrer-Policy":        "strict-origin",
    "Cache-Control":          "no-store",
}


# =============================================================================
# WEB REQUEST HANDLER
# =============================================================================
class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def _send(self, code: int, body: Union[str, bytes], ct: str = "application/json") -> None:
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in _SEC_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data, default=str), "application/json")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send(200, _HTML_PAGE, "text/html; charset=utf-8")
        elif path == "/api/streams":        self._get_streams()
        elif path == "/api/streams_config": self._get_streams_config()
        elif path == "/api/library":        self._get_library()
        elif path == "/api/subdirs":        self._get_subdirs()
        elif path == "/api/events":         self._get_events()
        elif path == "/api/logs":           self._get_logs(qs)
        elif path == "/api/system_stats":   self._get_system_stats()
        elif path == "/api/stream_detail":  self._get_stream_detail(qs)
        else:
            self._send(404, b"Not Found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        ct   = self.headers.get("Content-Type","")

        if "multipart/form-data" in ct:
            self._handle_upload()
            return

        length = int(self.headers.get("Content-Length", 0))
        if length > 2 * 1024 * 1024:
            self._json({"ok": False, "msg": "Request body too large"}, 413)
            return
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
        except Exception:
            self._json({"ok": False, "msg": "Invalid JSON"}, 400)
            return

        action = path.replace("/api/","").strip("/")
        self._dispatch(action, data)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────
    def _get_streams(self) -> None:
        if not _WEB_MANAGER: self._json([]); return
        result = []
        for st in _WEB_MANAGER.states:
            cfg = st.config
            result.append({
                "name":           cfg.name,
                "port":           cfg.port,
                "weekdays":       cfg.weekdays_display(),
                "status":         st.status.label,
                "progress":       st.progress,
                "position":       st.format_pos(),
                "current_secs":   st.current_pos,
                "duration":       st.duration,
                "fps":            st.fps,
                "rtsp_url":       cfg.rtsp_url_external,
                "hls_url":        cfg.hls_url if cfg.hls_enabled else "",
                "shuffle":        cfg.shuffle,
                "playlist_count": len(cfg.playlist),
                "playlist":       cfg.playlist_display(),
                "enabled":        cfg.enabled,
            })
        self._json(result)

    def _get_streams_config(self) -> None:
        if not _WEB_MANAGER: self._json([]); return
        result = []
        for st in _WEB_MANAGER.states:
            cfg = st.config
            result.append({
                "name":          cfg.name,
                "port":          cfg.port,
                "files":         ";".join(
                    f"{i.file_path}@{i.start_position}#{i.priority}"
                    for i in cfg.playlist),
                "weekdays":      cfg.weekdays_display(),
                "enabled":       cfg.enabled,
                "shuffle":       cfg.shuffle,
                "stream_path":   cfg.stream_path,
                "video_bitrate": cfg.video_bitrate,
                "audio_bitrate": cfg.audio_bitrate,
                "hls_enabled":   cfg.hls_enabled,
            })
        self._json(result)

    def _get_library(self) -> None:
        result = []
        for ext in SUPPORTED_EXTS:
            for f in MEDIA_DIR.rglob(f"*{ext}"):
                try:
                    meta = probe_metadata(f)
                    result.append({
                        "path":          str(f.relative_to(MEDIA_DIR)),
                        "full_path":     str(f),
                        "size":          _fmt_size(meta["size"]),
                        "size_bytes":    meta["size"],
                        "duration":      _fmt_duration(meta["duration"]) if meta["duration"] else "—",
                        "duration_secs": meta["duration"],
                        "video_codec":   meta["video_codec"],
                        "audio_codec":   meta["audio_codec"],
                        "width":         meta["width"],
                        "height":        meta["height"],
                        "fps":           meta["fps"],
                        "bitrate":       meta["bitrate"],
                    })
                except Exception:
                    pass
        self._json(sorted(result, key=lambda x: x["path"]))

    def _get_subdirs(self) -> None:
        dirs = []
        for d in MEDIA_DIR.rglob("*"):
            if d.is_dir():
                rel = str(d.relative_to(MEDIA_DIR))
                if rel: dirs.append(rel)
        self._json({"dirs": sorted(set(dirs)), "root_label": str(MEDIA_DIR)})

    def _get_events(self) -> None:
        if not _WEB_MANAGER: self._json([]); return
        result = []
        for ev in _WEB_MANAGER.events:
            result.append({
                "event_id":    ev.event_id,
                "stream_name": ev.stream_name,
                "file_name":   ev.file_path.name,
                "play_at":     ev.play_at.strftime("%Y-%m-%d %H:%M:%S"),
                "post_action": ev.post_action,
                "played":      ev.played,
            })
        self._json(result)

    def _get_logs(self, qs: Dict) -> None:
        if not _WEB_MANAGER: self._json({"entries": []}); return
        level  = qs.get("level",  ["ALL"])[0].upper()
        stream = qs.get("stream", [""])[0].strip()
        try:
            n = min(1000, int(qs.get("n", ["500"])[0]))
        except ValueError:
            n = 500
        if level not in ("ALL","INFO","WARN","ERROR"): level = "ALL"
        entries = _WEB_MANAGER._glog.filtered(
            level=None if level=="ALL" else level,
            stream=stream or None, n=n)
        self._json({"entries": entries})

    def _get_system_stats(self) -> None:
        try:
            cpu  = psutil.cpu_percent(interval=0.15)
            mem  = psutil.virtual_memory()
            disk = psutil.disk_usage(str(BASE_DIR))
            self._json({
                "cpu":          round(cpu, 1),
                "mem_percent":  round(mem.percent, 1),
                "mem_used":     _fmt_size(mem.used),
                "mem_total":    _fmt_size(mem.total),
                "disk_percent": round(disk.percent, 1),
                "disk_used":    _fmt_size(disk.used),
                "disk_total":   _fmt_size(disk.total),
            })
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _get_stream_detail(self, qs: Dict) -> None:
        name = qs.get("name", [""])[0].strip()
        if not _WEB_MANAGER or not name:
            self._json({"error": "bad request"}, 400); return
        st = _WEB_MANAGER.get_state(name)
        if not st:
            self._json({"error": "not found"}, 404); return
        cfg = st.config
        with st._lock:
            log_snap = list(st.log[-80:])
        cur_real = st.playlist_order[st.playlist_index] if st.playlist_order else 0
        playlist = []
        for i, item in enumerate(cfg.playlist):
            playlist.append({
                "file":     item.file_path.name,
                "path":     str(item.file_path),
                "start":    item.start_position,
                "priority": item.priority,
                "exists":   item.file_path.exists(),
                "current":  (i == cur_real),
            })
        self._json({
            "name":          cfg.name,
            "port":          cfg.port,
            "rtsp_url":      cfg.rtsp_url_external,
            "hls_url":       cfg.hls_url if cfg.hls_enabled else "",
            "weekdays":      cfg.weekdays_display(),
            "shuffle":       cfg.shuffle,
            "video_bitrate": cfg.video_bitrate,
            "audio_bitrate": cfg.audio_bitrate,
            "hls_enabled":   cfg.hls_enabled,
            "status":        st.status.label,
            "progress":      st.progress,
            "current_pos":   st.current_pos,
            "duration":      st.duration,
            "position":      st.format_pos(),
            "fps":           st.fps,
            "bitrate":       st.bitrate,
            "speed":         st.speed,
            "loop_count":    st.loop_count,
            "restart_count": st.restart_count,
            "error_msg":     st.error_msg,
            "playlist":      playlist,
            "log":           log_snap,
            "started_at":    st.started_at.isoformat() if st.started_at else None,
        })

    # ── POST dispatch ─────────────────────────────────────────
    def _dispatch(self, action: str, data: Dict) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json({"ok": False, "msg": "Manager not ready"}); return

        if action == "start":
            st = mgr.get_state(str(data.get("name","")))
            if st: mgr.start_stream(st); self._json({"ok": True, "msg": f"Starting {st.config.name}"})
            else:  self._json({"ok": False, "msg": "Stream not found"})

        elif action == "stop":
            st = mgr.get_state(str(data.get("name","")))
            if st: mgr.stop_stream(st); self._json({"ok": True, "msg": f"Stopping {st.config.name}"})
            else:  self._json({"ok": False, "msg": "Stream not found"})

        elif action == "restart":
            st = mgr.get_state(str(data.get("name","")))
            if st: mgr.restart_stream(st); self._json({"ok": True, "msg": f"Restarting {st.config.name}"})
            else:  self._json({"ok": False, "msg": "Stream not found"})

        elif action == "start_all":
            mgr.start_all(); self._json({"ok": True, "msg": "Starting all streams"})

        elif action == "stop_all":
            mgr.stop_all(); self._json({"ok": True, "msg": "Stopped all streams"})

        elif action == "skip_next":
            st = mgr.get_state(str(data.get("name","")))
            if st:
                mgr.skip_next(st)
                self._json({"ok": True, "msg": f"Skipping to next file in {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "seek":
            st = mgr.get_state(str(data.get("name","")))
            try:
                secs = float(data.get("seconds", 0))
                if secs < 0: raise ValueError("negative")
            except (TypeError, ValueError):
                self._json({"ok": False, "msg": "Invalid seek position"}); return
            if st:
                mgr.seek_stream(st, secs)
                self._json({"ok": True, "msg": f"Seeking to {_fmt_duration(secs)}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "save_config":
            try:
                streams_data = data.get("streams", [])
                if not isinstance(streams_data, list):
                    raise ValueError("streams must be a list")
                configs: List[StreamConfig] = []
                for row in streams_data:
                    name = str(row.get("name","")).strip()
                    if not name or len(name) > 64:
                        raise ValueError(f"Invalid stream name: '{name}'")
                    port = int(row.get("port", 0))
                    if not (1024 <= port <= 65535):
                        raise ValueError(f"Port {port} out of range")
                    raw_files = str(row.get("files","")).replace("\n",";")
                    playlist = CSVManager.parse_files(raw_files)
                    configs.append(StreamConfig(
                        name=name, port=port, playlist=playlist,
                        weekdays=CSVManager.parse_weekdays(str(row.get("weekdays","all"))),
                        enabled=bool(row.get("enabled", True)),
                        shuffle=bool(row.get("shuffle", False)),
                        stream_path=str(row.get("stream_path","stream")).strip() or "stream",
                        video_bitrate=CSVManager._sanitize_bitrate(
                            str(row.get("video_bitrate","2500k")), "2500k"),
                        audio_bitrate=CSVManager._sanitize_bitrate(
                            str(row.get("audio_bitrate","128k")), "128k"),
                        hls_enabled=bool(row.get("hls_enabled", False)),
                    ))
                ports = [c.port for c in configs]
                if len(set(ports)) != len(ports):
                    raise ValueError("Duplicate port numbers detected")
                names = [c.name for c in configs]
                if len(set(names)) != len(names):
                    raise ValueError("Duplicate stream names detected")
                CSVManager.save(configs)
                self._json({"ok": True, "msg": "Config saved. Restart HydraCast to apply."})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "add_event":
            try:
                stream_name = str(data.get("stream_name","")).strip()
                file_path   = str(data.get("file_path","")).strip()
                play_at     = str(data.get("play_at","")).strip()
                start_pos   = str(data.get("start_pos","00:00:00")).strip()
                post_action = str(data.get("post_action","resume")).strip()

                if post_action not in ("resume","stop","black"):
                    post_action = "resume"
                if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", start_pos):
                    start_pos = "00:00:00"

                dt = None
                for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt = datetime.strptime(play_at, fmt); break
                    except ValueError:
                        continue
                if dt is None:
                    raise ValueError("Invalid datetime format")

                fp = Path(file_path)
                safe = _safe_path(fp, MEDIA_DIR)
                if safe is None and not fp.exists():
                    raise ValueError("File not found or path unsafe")

                ev = OneShotEvent(
                    event_id=hashlib.md5(
                        f"{stream_name}{play_at}{file_path}".encode()
                    ).hexdigest()[:8],
                    stream_name=stream_name,
                    file_path=fp,
                    play_at=dt,
                    post_action=post_action,
                    start_pos=start_pos,
                )
                CSVManager.add_event(mgr.events, ev)
                self._json({"ok": True, "msg": "Event scheduled"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "delete_event":
            ev_id = str(data.get("event_id","")).strip()
            if not ev_id:
                self._json({"ok": False, "msg": "Missing event_id"}); return
            mgr.events = [e for e in mgr.events if e.event_id != ev_id]
            CSVManager.save_events(mgr.events)
            self._json({"ok": True, "msg": "Event deleted"})

        elif action == "delete_file":
            raw_path = str(data.get("path","")).strip()
            if not raw_path:
                self._json({"ok": False, "msg": "Missing path"}); return
            p    = Path(raw_path)
            safe = _safe_path(p, MEDIA_DIR)
            if safe is None or not safe.is_file():
                self._json({"ok": False, "msg": "File not in media directory or not found"}); return
            try:
                safe.unlink()
                self._json({"ok": True, "msg": f"Deleted {safe.name}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "create_subdir":
            raw = str(data.get("name","")).strip()
            if not raw or re.search(r'[/\\<>"|?*\x00]', raw) or ".." in raw:
                self._json({"ok": False, "msg": "Invalid folder name"}); return
            target = MEDIA_DIR / raw
            safe   = _safe_path(target, MEDIA_DIR)
            if safe is None:
                self._json({"ok": False, "msg": "Path traversal denied"}); return
            try:
                safe.mkdir(parents=True, exist_ok=True)
                self._json({"ok": True, "msg": f"Created folder: {raw}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        else:
            self._json({"ok": False, "msg": f"Unknown action: {action}"}, 404)

    def _handle_upload(self) -> None:
        """Parse multipart/form-data without deprecated cgi module (works on Python 3.13+)."""
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > UPLOAD_MAX_BYTES:
                self._json({"ok": False, "msg": "File exceeds 10 GB server limit"}, 413)
                return

            ct = self.headers.get("Content-Type", "")
            boundary: Optional[bytes] = None
            for part in ct.split(";"):
                p = part.strip()
                if p.lower().startswith("boundary="):
                    boundary = p[9:].strip('"').encode("latin-1")
                    break

            if not boundary:
                self._json({"ok": False, "msg": "Missing multipart boundary"}); return

            # Read the entire request body.  For huge files the 10 GB cap above
            # already guards against pathological clients; typical uploads are fine.
            raw = self.rfile.read(cl)

            sep = b"--" + boundary
            file_bytes: Optional[bytes] = None
            file_name:  Optional[str]   = None
            subdir = ""

            for seg in raw.split(sep):
                seg = seg.lstrip(b"\r\n")
                if not seg or seg.startswith(b"--"):
                    continue
                if b"\r\n\r\n" not in seg:
                    continue

                hdr_raw, body = seg.split(b"\r\n\r\n", 1)
                if body.endswith(b"\r\n"):
                    body = body[:-2]

                hdr_str = hdr_raw.decode("utf-8", errors="replace")
                cd_line = next(
                    (ln for ln in hdr_str.splitlines()
                     if ln.lower().startswith("content-disposition:")),
                    ""
                )

                field_name = fname = ""
                for tok in cd_line.split(";"):
                    tok = tok.strip()
                    if tok.startswith("name="):
                        field_name = tok[5:].strip('"')
                    elif tok.startswith("filename="):
                        fname = tok[9:].strip('"')

                if field_name == "file" and fname:
                    file_bytes = body
                    file_name  = fname
                elif field_name == "subdir":
                    subdir = body.decode("utf-8", errors="replace").strip().lstrip("/\\")

            if file_bytes is None or not file_name:
                self._json({"ok": False, "msg": "No file field found in request"}); return

            # Sanitize subdir — no traversal
            subdir = re.sub(r'[/\\<>"|?*\x00]', '_', subdir)[:128]
            subdir = re.sub(r'\.\.',            '_', subdir)

            fname_clean = Path(file_name).name
            ext         = Path(fname_clean).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                self._json({"ok": False, "msg": f"Unsupported file extension: {ext}"}); return

            safe_name = re.sub(r'[^\w.\-]', '_', fname_clean)
            if not safe_name or safe_name.startswith('.'):
                self._json({"ok": False, "msg": "Invalid filename"}); return

            dest_dir = (MEDIA_DIR / subdir) if subdir else MEDIA_DIR
            safe_dir = _safe_path(dest_dir, MEDIA_DIR)
            if safe_dir is None:
                self._json({"ok": False, "msg": "Invalid upload directory"}); return
            safe_dir.mkdir(parents=True, exist_ok=True)

            dest = safe_dir / safe_name
            with open(dest, "wb") as out:
                out.write(file_bytes)

            self._json({"ok": True, "msg": f"Saved: {safe_name} → {str(dest.relative_to(BASE_DIR))}"})
        except Exception as exc:
            self._json({"ok": False, "msg": f"Upload error: {exc}"}, 500)


# =============================================================================
# WEB SERVER
# =============================================================================
class WebServer:
    def __init__(self, port: int = WEB_PORT) -> None:
        self._port   = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        try:
            self._server = HTTPServer(("0.0.0.0", self._port), WebHandler)
            self._server.socket.setsockopt(
                __import__('socket').SOL_SOCKET,
                __import__('socket').SO_REUSEADDR, 1)
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True, name="webui")
            self._thread.start()
            logging.info("Web UI running on http://0.0.0.0:%d", self._port)
        except Exception as exc:
            logging.error("Web UI failed to start: %s", exc)

    def stop(self) -> None:
        if self._server:
            try: self._server.shutdown()
            except Exception: pass


# =============================================================================
# TUI
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
            t = Text(); t.append("─"*width, style="dim white"); t.append("   0.0%", style="dim white"); return t
        filled = max(1, round(pct/100*width)); empty = width - filled
        t = Text()
        for i in range(filled):
            frac = i/max(1,width)
            t.append("█", style=CG if frac<.55 else (CY if frac<.80 else CM))
        t.append("░"*empty, style="dim white")
        lc = CM if pct>=80 else (CY if pct>=55 else CG)
        t.append(f"  {pct:5.1f}%", style=f"bold {lc}")
        return t

    def _streams_table(self) -> Table:
        tbl = Table(box=box.SIMPLE_HEAD, border_style="bright_black",
                    header_style=f"bold {CW}", expand=True, padding=(0,1), show_edge=True)
        tbl.add_column("#",        style=CD,  width=3,  no_wrap=True)
        tbl.add_column("STREAM",   style=CW,  min_width=14, no_wrap=True)
        tbl.add_column("PORT",     style=CC,  width=6,  no_wrap=True)
        tbl.add_column("FILES",    style=CD,  width=7,  no_wrap=True)
        tbl.add_column("SCHEDULE", style=CW,  width=11, no_wrap=True)
        tbl.add_column("STATUS",              width=11, no_wrap=True)
        tbl.add_column("PROGRESS",            min_width=30, no_wrap=True)
        tbl.add_column("TIME",     style=CD,  width=14, no_wrap=True)
        tbl.add_column("FPS",      style=CD,  width=5,  no_wrap=True)
        tbl.add_column("LOOP",     style=CD,  width=6,  no_wrap=True)
        tbl.add_column("RTSP URL", style="dim cyan", min_width=22, no_wrap=True)

        for i, st in enumerate(self.manager.states):
            cfg = st.config; s = st.status
            stat_t = Text()
            if s == StreamStatus.ERROR and st.error_msg:
                stat_t.append(" ● ", style=CR); stat_t.append("ERROR", style=f"bold {CR}")
            else:
                stat_t.append(f" {s.dot} ", style=s.color); stat_t.append(s.label, style=f"bold {s.color}")
            row_style    = "on grey11" if i == self.selected else ""
            name_display = f"▶ {cfg.name}" if i == self.selected else f"  {cfg.name}"
            if cfg.shuffle:     name_display += " ⧖"
            if cfg.hls_enabled: name_display += " [H]"
            n_files = len(cfg.playlist)
            tbl.add_row(
                str(i+1), name_display, str(cfg.port),
                f"×{n_files}" if n_files > 1 else "1",
                cfg.weekdays_display(), stat_t,
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
        pending = sum(1 for e in self.manager.events if not e.played)
        t = Text()
        t.append("CPU  ", style=CD); t.append_text(self._progress_bar(cpu, 14)); t.append("\n")
        t.append("MEM  ", style=CD); t.append_text(self._progress_bar(mem.percent, 14)); t.append("\n\n")
        t.append("Cores  ", style=CD); t.append(str(CPU_COUNT), style=CC)
        t.append("  |  Streams  ", style=CD); t.append(str(len(self.manager.states)), style=CW); t.append("\n")
        t.append("LIVE   ", style=CD); t.append(str(live_n), style=CG)
        t.append("   SCHED  ", style=CD); t.append(str(sched_n), style=CC)
        t.append("   ERR  ", style=CD); t.append(str(err_n), style=(CR if err_n else CD))
        t.append("\n")
        t.append("Events ", style=CD); t.append(str(pending), style=CM); t.append(" pending\n\n")
        t.append(f"  LAN: {_local_ip()}", style=CD); t.append("\n")
        t.append(f"  Web: http://{_local_ip()}:{WEB_PORT}", style="dim cyan"); t.append("\n")
        t.append(datetime.now().strftime("  %a  %Y-%m-%d  %H:%M:%S"), style=CD)
        return Panel(t, title=f"[bold {CW}]SYSTEM[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0,1))

    def _log_panel(self) -> Panel:
        entries = self.glog.last(9)
        t = Text()
        colors = {"INFO": CW, "WARN": CY, "ERROR": CR}
        for msg, lvl in entries:
            t.append(msg+"\n", style=colors.get(lvl, CW))
        return Panel(t, title=f"[bold {CW}]EVENT LOG[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0,1))

    @staticmethod
    def _hotkeys() -> Text:
        t = Text(justify="center")
        for k, v in [
            ("↑↓/1-9","Select"),("R","Restart"),("S","Stop"),("T","Start"),
            ("A","All Start"),("X","All Stop"),("N","Skip Next"),
            ("←→","Seek ±10s"),("Shift←→","Seek ±60s"),
            ("G","Goto time"),("L","Reload CSV"),("U","Export URLs"),("Q","Quit"),
        ]:
            t.append(f" [{k}]", style=f"bold {CC}"); t.append(f" {v} ", style=CD)
        return t

    def render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="banner",  size=8),
            Layout(name="streams", ratio=1),
            Layout(name="bottom",  size=14),
            Layout(name="keys",    size=3),
        )
        banner_txt = Text.from_markup(BANNER_TEXT)
        sub = Text(
            f"  Multi-Stream RTSP Scheduler  ·  v{APP_VER}  ·  {APP_AUTHOR}  ·  "
            f"Web UI → http://{_local_ip()}:{WEB_PORT}",
            style="dim white", justify="center",
        )
        bf = Text(); bf.append_text(banner_txt); bf.append("\n"); bf.append_text(sub)
        layout["banner"].update(Align.center(bf, vertical="middle"))
        layout["streams"].update(Panel(
            self._streams_table(),
            title=(f"[bold {CW}]STREAMS[/]  [dim]({len(self.manager.states)} configured)[/]"),
            border_style=CC, box=box.ROUNDED, padding=(0,0),
        ))
        layout["bottom"].split_row(
            Layout(self._system_panel(), name="sys", ratio=1),
            Layout(self._log_panel(),    name="log", ratio=3),
        )
        layout["keys"].update(Panel(
            Align.center(self._hotkeys(), vertical="middle"),
            border_style="bright_black", box=box.SIMPLE, padding=(0,0),
        ))
        return layout


# =============================================================================
# KEYBOARD HANDLER
# =============================================================================
class KeyboardHandler:
    def __init__(self) -> None:
        self._q: "queue.Queue[str]" = queue.Queue()
        self._running = False

    def start(self) -> None:
        self._running = True
        threading.Thread(
            target=(self._win_loop if IS_WIN else self._unix_loop),
            daemon=True, name="keyboard",
        ).start()

    def stop(self) -> None: self._running = False

    def get(self) -> Optional[str]:
        try: return self._q.get_nowait()
        except queue.Empty: return None

    def _win_loop(self) -> None:
        import msvcrt
        while self._running:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    ch2 = msvcrt.getch()
                    mapping = {b"H":"UP", b"P":"DOWN", b"K":"LEFT", b"M":"RIGHT",
                               b"s":"SHIFTLEFT", b"t":"SHIFTRIGHT"}
                    self._q.put(mapping.get(ch2,""))
                else:
                    try: self._q.put(ch.decode("utf-8").upper())
                    except Exception: pass
            time.sleep(0.04)

    def _unix_loop(self) -> None:
        import tty, termios, select
        fd = sys.stdin.fileno()
        try:
            old = termios.tcgetattr(fd); tty.setcbreak(fd)
            while self._running:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not r: continue
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r2:
                        seq = sys.stdin.read(2)
                        if seq in ("[1", "[2"):
                            r3, _, _ = select.select([sys.stdin], [], [], 0.05)
                            if r3:
                                more = sys.stdin.read(4)
                                if "D" in more: self._q.put("SHIFTLEFT")
                                elif "C" in more: self._q.put("SHIFTRIGHT")
                                continue
                        mapping = {"[A":"UP","[B":"DOWN","[C":"RIGHT","[D":"LEFT"}
                        self._q.put(mapping.get(seq,"ESC"))
                    else:
                        self._q.put("ESC")
                else:
                    self._q.put(ch.upper())
        except Exception: pass
        finally:
            try: termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception: pass


# =============================================================================
# SEEK PROMPT (TUI)
# =============================================================================
def do_seek_prompt(manager: StreamManager, state: StreamState, console: Console) -> None:
    try:
        ts = Prompt.ask(
            f"\n[{CC}]Seek [{state.config.name}] to (HH:MM:SS or seconds)[/{CC}]",
            console=console, default="00:00:00",
        )
        parts = ts.strip().split(":")
        if len(parts) == 3:
            h, m, s = parts; secs = int(h)*3600 + int(m)*60 + float(s)
        elif len(parts) == 2:
            m, s = parts; secs = int(m)*60 + float(s)
        else:
            secs = float(parts[0])
        manager.seek_stream(state, max(0.0, secs))
    except Exception:
        pass


# =============================================================================
# PRE-FLIGHT & MAIN
# =============================================================================
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="hydracast",
        description=f"{APP_NAME} v{APP_VER} — Multi-Stream RTSP Weekly Scheduler")
    p.add_argument("--no-firewall", action="store_true",
                   help="Skip automatic firewall port-opening.")
    p.add_argument("--listen", metavar="IP", default="0.0.0.0",
                   help="IP address for MediaMTX to bind on.")
    p.add_argument("--web-port", type=int, default=WEB_PORT,
                   help=f"Web UI port (default: {WEB_PORT})")
    p.add_argument("--no-web", action="store_true",
                   help="Disable the embedded web UI.")
    p.add_argument("--list-ports", action="store_true",
                   help="Print ports that would be opened, then exit.")
    p.add_argument("--export-urls", action="store_true",
                   help="Write stream_urls.txt at startup.")
    return p.parse_args()


def _preflight(console: Console) -> List[StreamConfig]:
    global FFMPEG_PATH, FFPROBE_PATH

    console.rule(f"[{CC}]{APP_NAME} v{APP_VER}[/]  Pre-flight checks")
    console.print()

    for f in CONFIGS_DIR.glob("mediamtx_*.yml"):
        try: f.unlink()
        except Exception: pass

    console.print(f"[{CD}]  OS        : {platform.system()} {platform.release()} ({ARCH_KEY})[/]")
    console.print(f"[{CD}]  Python    : {sys.version.split()[0]}[/]")
    console.print(f"[{CD}]  CPU cores : {CPU_COUNT}[/]")
    console.print(f"[{CD}]  LAN IP    : {_local_ip()}[/]")
    console.print(f"[{CD}]  Bind addr : {LISTEN_ADDR}[/]")
    console.print(f"[{CD}]  Base dir  : {BASE_DIR}[/]")
    console.print(f"[{CD}]  Media dir : {MEDIA_DIR}[/]")
    console.print()

    if not DependencyManager.download_mediamtx(console):
        console.print(f"[{CR}]✘  Cannot continue without MediaMTX.[/]"); sys.exit(1)

    ffmpeg = DependencyManager.check_ffmpeg()
    if not ffmpeg:
        console.print(
            f"[{CR}]✘  FFmpeg not found in PATH or bin/[/]\n"
            f"[{CY}]   Linux  : sudo apt install ffmpeg\n"
            f"   Windows: https://www.gyan.dev/ffmpeg/builds/\n"
            f"   macOS  : brew install ffmpeg[/]"
        )
        sys.exit(1)
    FFMPEG_PATH = ffmpeg
    console.print(f"[{CG}]✔  FFmpeg  : {FFMPEG_PATH}[/]")

    ffprobe = DependencyManager.check_ffprobe()
    if ffprobe: FFPROBE_PATH = ffprobe
    console.print(f"[{CG}]✔  FFprobe : {FFPROBE_PATH}[/]")

    try:
        configs = CSVManager.load()
    except FileNotFoundError as exc:
        console.print(f"\n[{CY}]⚠  {exc}[/]"); sys.exit(0)
    except Exception as exc:
        console.print(f"[{CR}]✘  CSV error: {exc}[/]"); sys.exit(1)

    console.print(f"[{CG}]✔  Loaded {len(configs)} stream(s) from streams.csv[/]")

    enabled_ports = [c.port for c in configs if c.enabled]
    if enabled_ports:
        console.print()
        FirewallManager.open_ports(enabled_ports, console)

    console.print()
    time.sleep(0.6)
    return configs


def main() -> None:
    global NO_FIREWALL, LISTEN_ADDR, WEB_PORT, _WEB_MANAGER

    args        = _parse_args()
    NO_FIREWALL = args.no_firewall
    LISTEN_ADDR = args.listen
    WEB_PORT    = args.web_port

    console = Console(force_terminal=True, highlight=False)

    if args.list_ports:
        try: cfgs = CSVManager.load()
        except Exception as exc: console.print(f"[{CR}]✘  {exc}[/]"); sys.exit(1)
        console.print(f"[{CC}]Ports that would be opened:[/]")
        for c in cfgs:
            if c.enabled:
                hls = f"  + HLS :{c.hls_port}" if c.hls_enabled else ""
                console.print(f"  {c.name:20s}  TCP :{c.port}{hls}")
        sys.exit(0)

    configs = _preflight(console)

    logging.basicConfig(
        filename=LOGS_DIR / "hydracast.log", level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    glog    = LogBuffer()
    manager = StreamManager(configs, glog)
    _WEB_MANAGER = manager

    tui = TUI(manager, glog)
    kb  = KeyboardHandler()

    _shutdown = threading.Event()
    def _sig(sig, _f): _shutdown.set()
    signal.signal(signal.SIGINT,  _sig)
    signal.signal(signal.SIGTERM, _sig)

    glog.add(f"{APP_NAME} v{APP_VER} started — {len(configs)} streams configured.")
    manager.start_all()
    manager.run_scheduler()
    kb.start()

    if args.export_urls:
        url_file = manager.export_urls()
        glog.add(f"Stream URLs exported → {url_file.name}")

    web: Optional[WebServer] = None
    if not args.no_web:
        web = WebServer(WEB_PORT)
        web.start()
        glog.add(f"Web UI → http://{_local_ip()}:{WEB_PORT}", "INFO")

    n = len(manager.states)

    with Live(tui.render(), console=console, refresh_per_second=2,
              screen=True, transient=False) as live:
        while not _shutdown.is_set():
            key = kb.get()
            if key:
                sel   = tui.selected
                state = manager.states[sel] if manager.states else None

                if key in ("Q", "ESC"):
                    _shutdown.set(); break
                elif key in ("UP", "K"):
                    tui.selected = max(0, sel-1)
                elif key in ("DOWN", "J"):
                    tui.selected = min(n-1, sel+1)
                elif key.isdigit():
                    idx = int(key)-1
                    if 0 <= idx < n: tui.selected = idx
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
                    glog.add("Start-all triggered."); manager.start_all()
                elif key == "X":
                    glog.add("Stop-all triggered."); manager.stop_all()
                elif key == "N" and state:
                    glog.add(f"Skip next: {state.config.name}")
                    manager.skip_next(state)
                elif key == "RIGHT" and state:
                    if state.status == StreamStatus.LIVE:
                        manager.seek_stream(state, state.current_pos + 10.0)
                        glog.add(f"Seek +10s → {state.config.name}")
                elif key == "LEFT" and state:
                    if state.status == StreamStatus.LIVE:
                        manager.seek_stream(state, max(0.0, state.current_pos - 10.0))
                        glog.add(f"Seek -10s → {state.config.name}")
                elif key == "SHIFTRIGHT" and state:
                    if state.status == StreamStatus.LIVE:
                        manager.seek_stream(state, state.current_pos + 60.0)
                        glog.add(f"Seek +60s → {state.config.name}")
                elif key == "SHIFTLEFT" and state:
                    if state.status == StreamStatus.LIVE:
                        manager.seek_stream(state, max(0.0, state.current_pos - 60.0))
                        glog.add(f"Seek -60s → {state.config.name}")
                elif key == "G" and state:
                    live.stop()
                    do_seek_prompt(manager, state, console)
                    live.start()
                elif key == "L":
                    try:
                        new_cfgs = CSVManager.load()
                        glog.add(f"CSV reloaded: {len(new_cfgs)} streams.", "INFO")
                    except Exception as exc:
                        glog.add(f"CSV reload error: {exc}", "ERROR")
                elif key == "U":
                    try:
                        url_file = manager.export_urls()
                        glog.add(f"URLs exported → {url_file.name}")
                    except Exception as exc:
                        glog.add(f"URL export error: {exc}", "ERROR")

            live.update(tui.render())
            time.sleep(0.45)

    kb.stop()
    console.clear()
    console.print(f"\n[{CY}]⏳  Stopping all streams … please wait.[/]")
    manager.shutdown()
    if web: web.stop()
    for f in CONFIGS_DIR.glob("mediamtx_*.yml"):
        try: f.unlink()
        except Exception: pass
    console.print(f"[{CG}]✔  HydraCast stopped cleanly. Goodbye.[/]\n")


if __name__ == "__main__":
    main()
