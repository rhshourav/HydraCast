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
#  Version : 3.1.0
#  GitHub  : https://github.com/rhshourav/HydraCast
#  License : MIT
#
#  v3.1 changelog (fixes over v3.0)
#  ─────────────────────────────────
#  FIXED    Seek race condition: _seeking Event flag prevents _monitor()
#           from triggering auto-restart when FFmpeg is killed intentionally
#           for a seek operation → no more phantom auto-restart loops
#  FIXED    _start_lock prevents concurrent start() calls colliding
#  FIXED    _monitor() captures proc reference; ignores exits from replaced procs
#  FIXED    restart_count resets to 0 on a clean successful start
#  FIXED    SyntaxWarning: \W → \\W in Python strings containing JS regex
#  FIXED    Multiple MediaMTX instances: _auto_restart kills existing before spawn
#  IMPROVED Web UI: inline seek slider per stream, stream detail modal,
#           system stats panel, per-level log filtering, security headers,
#           upload size cap, path-traversal guard, rate-limit headers
#  NEW      GET /api/system_stats — CPU / RAM / disk
#  NEW      GET /api/stream_detail?name=X — full state + playlist + log tail
#  NEW      GET /api/logs with ?level=INFO&stream=X&n=200 filter params
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

# ── Python guard ──────────────────────────────────────────────────────────────
if sys.version_info < (3, 8):
    sys.exit("HydraCast requires Python 3.8 or newer.")

# ── Bootstrap ─────────────────────────────────────────────────────────────────
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
APP_VER    = "3.1.0"
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
MEDIA_DIR   = BASE_DIR / "media"
CSV_FILE    = BASE_DIR / "streams.csv"
EVENTS_FILE = BASE_DIR / "events.csv"
WEB_PORT    = 8080
UPLOAD_MAX_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB hard cap

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

# Rich colours
CG = "bright_green"; CR = "bright_red"; CY = "yellow"
CC = "bright_cyan";  CW = "white";       CD = "dim white"
CM = "bright_magenta"; CB = "bright_blue"

NO_FIREWALL = False
LISTEN_ADDR = "0.0.0.0"
_MANAGER: Optional["StreamManager"] = None


# =============================================================================
# DATA MODELS  (unchanged from v3.0)
# =============================================================================
class StreamStatus(Enum):
    STOPPED   = ("●", "dim white",    "STOPPED")
    STARTING  = ("◌", "yellow",       "STARTING")
    LIVE      = ("●", "bright_green", "LIVE")
    SCHEDULED = ("◷", "bright_cyan",  "SCHED")
    ERROR     = ("●", "bright_red",   "ERROR")
    DISABLED  = ("⊘", "dim",          "DISABLED")
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
            if len(self.log) > 300:
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
    """Return resolved path only if it is inside root; else None (path-traversal guard)."""
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
    ["Stream_1","8554","/path/to/video.mp4","ALL","true","false","stream","2500k","128k","false"],
    ["Stream_2","8555","/path/to/a.mp4@00:05:00;/path/to/b.mkv","Mon|Wed|Fri","true","false","ch2","4000k","192k","false"],
    ["Stream_3","8556","/media/demo.mp4","Sat|Sun","false","true","ch3","1500k","128k","false"],
    ["Stream_4","8557","/media/show.mp4","Weekdays","true","false","ch4","2500k","128k","true"],
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
        items: List[PlaylistItem] = []
        for part in raw.split(";"):
            part = part.strip()
            if not part: continue
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
            items.append(PlaylistItem(file_path=Path(path_str), start_position=pos))
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
                configs.append(StreamConfig(
                    name=name, port=port, playlist=playlist,
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
                    f"{item.file_path}@{item.start_position}" for item in c.playlist
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
# STREAM WORKER  —  v3.1 FIXED
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
        # ── v3.1 fixes ────────────────────────────────────────────────────────
        self._seeking    = threading.Event()   # set during seek; suppresses auto-restart
        self._start_lock = threading.Lock()    # prevents concurrent start() calls

    def _log(self, msg: str, level: str = "INFO") -> None:
        full = f"[{self.state.config.name}] {msg}"
        self.state.log_add(full); self.glog.add(full, level)
        logging.log(
            logging.WARNING if level == "WARN" else
            (logging.ERROR if level == "ERROR" else logging.INFO), full)

    # ── Playlist helpers ──────────────────────────────────────────────────────
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

    # ── Public API ────────────────────────────────────────────────────────────
    def start(self, seek_override: Optional[float] = None) -> bool:
        # FIX: _start_lock prevents two concurrent calls (e.g. manual + auto-restart)
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
        self.state.restart_count = 0   # FIX: reset on clean successful start
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
        """
        FIX v3.1: Sets _seeking BEFORE killing FFmpeg so _monitor() knows
        this is an intentional kill, not an error → no phantom auto-restart.
        """
        self._seeking.set()                              # ← signal BEFORE kill
        self._log(f"Seeking to {_fmt_duration(seconds)} …")
        self._kill_ffmpeg()
        time.sleep(0.4)
        item = self._current_item()
        if item is None:
            self._seeking.clear(); return
        self.state.duration = probe_duration(item.file_path)
        self._start_ffmpeg(item, max(0.0, seconds))
        self._seeking.clear()                            # ← clear AFTER new proc ready
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

    # ── launchers ─────────────────────────────────────────────────────────────
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

    # ── monitor ───────────────────────────────────────────────────────────────
    def _monitor(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc is None: return
        my_proc = proc                     # FIX: capture reference at start
        buf: Dict[str,str] = {}

        while not self._stop.is_set():
            if my_proc.poll() is not None: break
            # FIX: if seek replaced the proc, our job here is done
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

        # ── post-exit logic ───────────────────────────────────────────────────
        if self._stop.is_set():                   return   # deliberate stop
        if self._seeking.is_set():                return   # FIX: seek will handle it
        if self.state.ffmpeg_proc is not my_proc: return   # FIX: already replaced

        # Playlist advance for multi-file streams
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
        # FIX: don't auto-restart if a seek is in progress
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
            # FIX: kill existing MediaMTX before spawning a new one
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
# WEB UI  —  v3.1 enhanced HTML
#   NOTE: all JavaScript /regex/ patterns with backslash use \\  so Python
#   does not emit SyntaxWarning for invalid escape sequences.
# =============================================================================
_WEB_MANAGER: Optional[StreamManager] = None

# ─── The HTML is assembled from parts so Python escape issues are minimal ─────
_HTML_STYLE = """
<style>
:root{
  --bg:#0a0e14;--bg2:#0d1117;--bg3:#161b22;--bg4:#21262d;
  --border:#21262d;--border2:#30363d;
  --text:#cdd6f4;--muted:#6c7086;--faint:#313244;
  --green:#a6e3a1;--red:#f38ba8;--yellow:#f9e2af;
  --blue:#89b4fa;--purple:#cba6f7;--cyan:#89dceb;
  --orange:#fab387;--teal:#94e2d5;--pink:#f5c2e7;
  --green-dim:rgba(166,227,161,.12);--red-dim:rgba(243,139,168,.12);
  --blue-dim:rgba(137,180,250,.12);--yellow-dim:rgba(249,226,175,.12);
  --radius:8px;--radius-sm:5px;
  --font-mono:'JetBrains Mono','Cascadia Code','Fira Code',monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:13px/1.6 'Inter','Segoe UI',system-ui,sans-serif;min-height:100vh;overflow-x:hidden}

/* ── Layout ── */
.shell{display:grid;grid-template-rows:auto 1fr;min-height:100vh}
header{
  background:var(--bg2);border-bottom:1px solid var(--border2);
  padding:0 20px;height:52px;display:flex;align-items:center;gap:14px;
  position:sticky;top:0;z-index:50;
}
header .logo{font-size:20px;font-weight:700;color:var(--blue);letter-spacing:.04em;font-family:var(--font-mono)}
header .ver{color:var(--muted);font-size:11px;font-family:var(--font-mono)}
.hdr-stats{display:flex;gap:16px;margin-left:12px}
.hdr-stat{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}
.hdr-stat .val{color:var(--text);font-weight:600;font-family:var(--font-mono)}
.hdr-stat .dot{width:7px;height:7px;border-radius:50%;display:inline-block}
.dot-live{background:var(--green);box-shadow:0 0 6px var(--green)}
.dot-err{background:var(--red);box-shadow:0 0 6px var(--red)}
nav{display:flex;gap:2px;margin-left:auto}
nav button{
  background:none;border:none;border-radius:var(--radius-sm);
  color:var(--muted);padding:7px 13px;cursor:pointer;font-size:12px;
  font-weight:500;transition:.15s;letter-spacing:.02em;
}
nav button.active{background:var(--blue-dim);color:var(--blue)}
nav button:hover:not(.active){background:var(--faint);color:var(--text)}
.container{max-width:1340px;margin:0 auto;padding:18px 20px}

/* ── Panels ── */
.panel{background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);margin-bottom:16px;overflow:hidden}
.panel-hdr{
  background:var(--bg3);padding:10px 16px;font-weight:600;font-size:12px;
  border-bottom:1px solid var(--border2);display:flex;align-items:center;gap:8px;
  letter-spacing:.04em;text-transform:uppercase;color:var(--muted);
}
.panel-hdr .title{color:var(--text)}
.panel-body{padding:16px}

/* ── Tables ── */
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:8px 12px;color:var(--muted);font-weight:500;font-size:11px;
   border-bottom:1px solid var(--border2);text-transform:uppercase;letter-spacing:.06em}
td{padding:8px 12px;border-bottom:1px solid var(--border);font-size:12px;vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(255,255,255,.02)}

/* ── Badges ── */
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:.06em}
.badge::before{content:'●';font-size:8px}
.badge-LIVE{background:var(--green-dim);color:var(--green);border:1px solid rgba(166,227,161,.3)}
.badge-STOPPED{background:rgba(108,112,134,.08);color:var(--muted);border:1px solid var(--border2)}
.badge-ERROR{background:var(--red-dim);color:var(--red);border:1px solid rgba(243,139,168,.3)}
.badge-SCHED{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(137,180,250,.3)}
.badge-DISABLED{background:rgba(108,112,134,.05);color:var(--muted);border:1px dashed var(--border2)}
.badge-STARTING{background:var(--yellow-dim);color:var(--yellow);border:1px solid rgba(249,226,175,.3)}
.badge-ONESHOT{background:rgba(203,166,247,.12);color:var(--purple);border:1px solid rgba(203,166,247,.3)}

/* ── Buttons ── */
.btn{
  display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:var(--radius-sm);
  border:1px solid var(--border2);cursor:pointer;font-size:11px;font-weight:600;
  background:var(--bg4);color:var(--text);transition:.15s;white-space:nowrap;
  letter-spacing:.02em;font-family:inherit;
}
.btn:hover{border-color:var(--blue);color:var(--blue);background:var(--blue-dim)}
.btn-sm{padding:3px 9px;font-size:10px}
.btn-danger:hover{border-color:var(--red);color:var(--red);background:var(--red-dim)}
.btn-success:hover{border-color:var(--green);color:var(--green);background:var(--green-dim)}
.btn-primary{background:rgba(137,180,250,.15);border-color:rgba(137,180,250,.4);color:var(--blue)}
.btn-primary:hover{background:var(--blue);color:#0a0e14}

/* ── Form elements ── */
input,select,textarea{
  background:var(--bg3);border:1px solid var(--border2);border-radius:var(--radius-sm);
  color:var(--text);padding:7px 10px;font-size:12px;width:100%;outline:none;
  font-family:inherit;transition:.15s;
}
input:focus,select:focus,textarea:focus{border-color:var(--blue);background:var(--bg4)}
label{font-size:11px;color:var(--muted);margin-bottom:4px;display:block;letter-spacing:.03em}
.form-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:12px}
.form-group{display:flex;flex-direction:column}
.form-hint{font-size:10px;color:var(--muted);margin-top:3px}

/* ── Progress ── */
.progress-bar{height:5px;background:var(--bg4);border-radius:3px;overflow:hidden;flex:1;min-width:80px}
.progress-fill{height:100%;border-radius:3px;transition:.6s}

/* ── Range/Seek slider ── */
.seek-row{display:flex;align-items:center;gap:8px;margin-top:4px}
input[type=range]{
  -webkit-appearance:none;appearance:none;
  flex:1;height:3px;background:var(--bg4);border-radius:2px;
  outline:none;border:none;padding:0;cursor:pointer;
}
input[type=range]::-webkit-slider-thumb{
  -webkit-appearance:none;width:12px;height:12px;border-radius:50%;
  background:var(--blue);cursor:pointer;transition:.1s;
}
input[type=range]::-webkit-slider-thumb:hover{transform:scale(1.3)}
input[type=range]::-moz-range-thumb{width:12px;height:12px;border:none;border-radius:50%;background:var(--blue);cursor:pointer}

/* ── Mono values ── */
.mono{font-family:var(--font-mono);font-size:11px}
.rtsp-chip{
  font-family:var(--font-mono);font-size:10px;color:var(--cyan);
  background:rgba(137,220,235,.08);padding:2px 7px;border-radius:4px;
  cursor:pointer;border:1px solid rgba(137,220,235,.15);
  user-select:all;word-break:break-all;
}
.rtsp-chip:hover{background:rgba(137,220,235,.18);border-color:var(--cyan)}

/* ── Tabs ── */
.tab-content{display:none}.tab-content.active{display:block}

/* ── Upload ── */
.drop-zone{
  border:2px dashed var(--border2);border-radius:var(--radius);
  padding:36px;text-align:center;color:var(--muted);cursor:pointer;transition:.2s;
}
.drop-zone:hover,.drop-zone.drag-over{border-color:var(--blue);color:var(--blue);background:var(--blue-dim)}
.file-list{list-style:none;margin-top:12px}
.file-list li{
  display:flex;align-items:center;gap:10px;padding:7px 10px;
  background:var(--bg3);border-radius:var(--radius-sm);margin-bottom:5px;font-size:11px;
  border:1px solid var(--border);
}
.upload-bar{height:3px;background:var(--bg);border-radius:2px;flex:1;overflow:hidden}
.upload-fill{height:100%;background:var(--blue);transition:.2s}

/* ── Notifications ── */
.notify{
  position:fixed;bottom:20px;right:20px;padding:10px 16px;border-radius:var(--radius-sm);
  font-size:12px;font-weight:600;z-index:999;transform:translateY(80px);
  transition:.25s;box-shadow:0 4px 24px rgba(0,0,0,.5);
}
.notify.show{transform:translateY(0)}
.notify.ok{background:#1a2b1a;border:1px solid var(--green);color:var(--green)}
.notify.err{background:#2b1a1a;border:1px solid var(--red);color:var(--red)}
.notify.info{background:#1a1f2b;border:1px solid var(--blue);color:var(--blue)}

/* ── Modal ── */
.modal-overlay{
  display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);
  z-index:200;align-items:center;justify-content:center;
}
.modal-overlay.open{display:flex}
.modal{
  background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);
  padding:24px;width:640px;max-width:96vw;max-height:90vh;
  overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.6);
}
.modal h3{font-size:16px;margin-bottom:16px;color:var(--text)}
.modal-close{float:right;cursor:pointer;color:var(--muted);font-size:18px;line-height:1}
.modal-close:hover{color:var(--red)}

/* ── Stream detail ── */
.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.detail-item{background:var(--bg3);border-radius:var(--radius-sm);padding:8px 12px;border:1px solid var(--border)}
.detail-item .dk{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}
.detail-item .dv{font-size:13px;font-weight:600;font-family:var(--font-mono)}
.log-box{
  background:var(--bg);border:1px solid var(--border2);border-radius:var(--radius-sm);
  padding:10px;max-height:220px;overflow-y:auto;font-family:var(--font-mono);font-size:11px;
}
.log-box .log-info{color:var(--text)}
.log-box .log-warn{color:var(--yellow)}
.log-box .log-err{color:var(--red)}
.playlist-item{
  display:flex;align-items:center;gap:8px;padding:5px 10px;
  background:var(--bg3);border-radius:var(--radius-sm);margin-bottom:4px;font-size:11px;
  border:1px solid var(--border);
}
.playlist-item.current{border-color:var(--green);background:var(--green-dim)}
.playlist-item .pi-idx{color:var(--muted);font-family:var(--font-mono);width:20px}

/* ── Log panel ── */
.log-controls{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center}
.log-chip{
  padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;cursor:pointer;
  border:1px solid var(--border2);background:var(--bg4);color:var(--muted);transition:.15s;
  letter-spacing:.05em;
}
.log-chip.active-ALL{background:var(--bg4);color:var(--text);border-color:var(--border2)}
.log-chip.active-INFO{background:var(--blue-dim);color:var(--blue);border-color:rgba(137,180,250,.3)}
.log-chip.active-WARN{background:var(--yellow-dim);color:var(--yellow);border-color:rgba(249,226,175,.3)}
.log-chip.active-ERROR{background:var(--red-dim);color:var(--red);border-color:rgba(243,139,168,.3)}

/* ── Sys stats mini bar ── */
.sys-bar{display:flex;gap:4px;align-items:center}
.sys-seg{height:14px;border-radius:2px;transition:.4s}

/* ── Responsive ── */
@media(max-width:768px){
  .form-row{grid-template-columns:1fr}
  .detail-grid{grid-template-columns:1fr}
  .hdr-stats{display:none}
  nav button{padding:6px 8px;font-size:11px}
}
</style>
"""

_HTML_BODY = r"""
<div class="shell">
<header>
  <span style="font-size:22px">🐉</span>
  <span class="logo">HydraCast</span>
  <span class="ver">v3.1</span>
  <div class="hdr-stats" id="hdr-stats">
    <div class="hdr-stat"><span class="dot dot-live"></span>Live: <span class="val" id="h-live">—</span></div>
    <div class="hdr-stat">CPU: <span class="val" id="h-cpu">—</span></div>
    <div class="hdr-stat">RAM: <span class="val" id="h-ram">—</span></div>
    <div class="hdr-stat">Disk: <span class="val" id="h-disk">—</span></div>
    <div class="hdr-stat" id="h-time" style="font-family:var(--font-mono)">—</div>
  </div>
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

<!-- ══ STREAMS ══ -->
<div id="tab-streams" class="tab-content active">
  <div class="panel">
    <div class="panel-hdr">
      <span class="title">Live Streams</span>
      <span style="margin-left:auto;display:flex;gap:6px">
        <button class="btn btn-sm btn-success" onclick="api('start_all')">▶ All</button>
        <button class="btn btn-sm btn-danger"  onclick="api('stop_all')">■ All</button>
        <button class="btn btn-sm" onclick="loadStreams()">↻</button>
        <label style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--muted);margin:0;cursor:pointer">
          <input type="checkbox" id="auto-refresh" checked style="width:auto;cursor:pointer" onchange="toggleAutoRefresh(this.checked)">
          Auto
        </label>
      </span>
    </div>
    <div style="padding:0">
      <table>
        <thead><tr>
          <th>#</th><th>Stream</th><th>Port</th><th>Schedule</th>
          <th>Status</th><th colspan="2">Progress / Seek</th>
          <th>Time</th><th>FPS</th><th>RTSP URL</th><th>Actions</th>
        </tr></thead>
        <tbody id="streams-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ UPLOAD ══ -->
<div id="tab-upload" class="tab-content">
  <div class="panel">
    <div class="panel-hdr"><span class="title">Upload Media Files</span></div>
    <div class="panel-body">
      <div class="drop-zone" id="drop-zone" onclick="document.getElementById('file-input').click()">
        <div style="font-size:44px;margin-bottom:10px">📼</div>
        <p style="font-size:15px;font-weight:700;margin-bottom:6px">Drop files here or click to browse</p>
        <p style="font-size:11px;color:var(--muted)">MP4 · MKV · AVI · MOV · TS · FLV · WEBM · MP3 · AAC · FLAC · and all FFmpeg formats</p>
        <p style="font-size:10px;color:var(--muted);margin-top:6px">Max 10 GB per file</p>
        <input type="file" id="file-input" multiple style="display:none"
               accept="video/*,audio/*,.mkv,.ts,.m2ts,.flv,.webm"
               onchange="handleFiles(this.files)">
      </div>
      <ul class="file-list" id="upload-list"></ul>
      <div style="margin-top:14px;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <label style="display:inline;margin:0;white-space:nowrap;font-size:12px">Upload to:</label>
        <select id="upload-subdir" style="width:auto;flex:1;min-width:160px">
          <option value="">/ (media root)</option>
        </select>
        <button class="btn btn-sm" onclick="createSubdir()">+ New Folder</button>
      </div>
    </div>
  </div>
</div>

<!-- ══ LIBRARY ══ -->
<div id="tab-library" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="title">Media Library</span>
      <span style="margin-left:auto;display:flex;gap:6px;align-items:center">
        <input type="text" id="lib-search" placeholder="Search…"
               style="width:180px;height:28px;padding:4px 8px"
               oninput="filterLibrary()">
        <select id="lib-sort" style="width:120px;height:28px;padding:2px 6px" onchange="filterLibrary()">
          <option value="name">Sort: Name</option>
          <option value="size">Sort: Size</option>
          <option value="dur">Sort: Duration</option>
        </select>
        <button class="btn btn-sm" onclick="loadLibrary()">↻</button>
      </span>
    </div>
    <div style="padding:0">
      <table>
        <thead><tr>
          <th>Filename</th><th>Duration</th><th>Size</th>
          <th>Video</th><th>Resolution</th><th>FPS</th><th>Actions</th>
        </tr></thead>
        <tbody id="library-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ CONFIG EDITOR ══ -->
<div id="tab-editor" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="title">Stream Configuration</span>
      <span style="margin-left:auto;display:flex;gap:6px">
        <button class="btn btn-sm btn-primary" onclick="saveCSV()">💾 Save</button>
        <button class="btn btn-sm" onclick="addStreamRow()">+ Add</button>
      </span>
    </div>
    <div class="panel-body" id="editor-body"></div>
  </div>
</div>

<!-- ══ SCHEDULER ══ -->
<div id="tab-events" class="tab-content">
  <div class="panel">
    <div class="panel-hdr"><span class="title">Schedule One-Shot Event</span></div>
    <div class="panel-body">
      <div class="form-row">
        <div class="form-group">
          <label>Stream</label>
          <select id="evt-stream"></select>
        </div>
        <div class="form-group">
          <label>Video File</label>
          <select id="evt-file"></select>
        </div>
        <div class="form-group">
          <label>Play At (local time)</label>
          <input type="datetime-local" id="evt-datetime">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Start Position in File</label>
          <input type="text" id="evt-startpos" placeholder="00:00:00" value="00:00:00">
        </div>
        <div class="form-group">
          <label>After playback</label>
          <select id="evt-postaction">
            <option value="resume">Resume normal playlist</option>
            <option value="stop">Stop stream</option>
            <option value="black">Show black screen</option>
          </select>
        </div>
        <div class="form-group" style="justify-content:flex-end">
          <button class="btn btn-primary" style="margin-top:auto" onclick="scheduleEvent()">
            📅 Schedule
          </button>
        </div>
      </div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-hdr">
      <span class="title">Events</span>
      <span style="margin-left:auto;display:flex;gap:6px">
        <button class="btn btn-sm btn-danger" onclick="clearPlayedEvents()">🗑 Clear Played</button>
        <button class="btn btn-sm" onclick="loadEvents()">↻</button>
      </span>
    </div>
    <div style="padding:0">
      <table>
        <thead><tr>
          <th>Stream</th><th>File</th><th>Play At</th>
          <th>Countdown</th><th>After</th><th>Status</th><th>Actions</th>
        </tr></thead>
        <tbody id="events-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ LOGS ══ -->
<div id="tab-logs" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="title">Event Log</span>
      <span style="margin-left:auto;display:flex;gap:6px;align-items:center">
        <select id="log-stream-filter" style="width:140px;height:28px;padding:2px 6px" onchange="loadLogs()">
          <option value="">All Streams</option>
        </select>
        <button class="btn btn-sm" onclick="loadLogs()">↻</button>
        <label style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--muted);margin:0;cursor:pointer">
          <input type="checkbox" id="log-autoscroll" checked style="width:auto;cursor:pointer"> Auto-scroll
        </label>
      </span>
    </div>
    <div class="panel-body">
      <div class="log-controls">
        <span style="font-size:11px;color:var(--muted)">Filter:</span>
        <span class="log-chip active-ALL" data-level="ALL" onclick="setLogLevel('ALL')">ALL</span>
        <span class="log-chip" data-level="INFO" onclick="setLogLevel('INFO')">INFO</span>
        <span class="log-chip" data-level="WARN" onclick="setLogLevel('WARN')">WARN</span>
        <span class="log-chip" data-level="ERROR" onclick="setLogLevel('ERROR')">ERROR</span>
        <input type="text" id="log-search" placeholder="Search log…"
               style="width:200px;height:26px;padding:3px 8px;margin-left:auto" oninput="renderLogEntries()">
      </div>
      <div id="log-container" class="log-box"></div>
    </div>
  </div>
</div>

</div><!-- /container -->
</div><!-- /shell -->

<!-- ══ STREAM DETAIL MODAL ══ -->
<div class="modal-overlay" id="detail-modal">
  <div class="modal">
    <h3>
      <span id="detail-title">Stream Detail</span>
      <span class="modal-close" onclick="closeModal('detail-modal')">✕</span>
    </h3>
    <div id="detail-content"></div>
    <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
      <button class="btn btn-success btn-sm" id="detail-start" onclick="">▶ Start</button>
      <button class="btn btn-danger btn-sm"  id="detail-stop"  onclick="">■ Stop</button>
      <button class="btn btn-sm"             id="detail-rst"   onclick="">↺ Restart</button>
      <button class="btn" onclick="closeModal('detail-modal')">Close</button>
    </div>
  </div>
</div>

<!-- ══ SEEK MODAL ══ -->
<div class="modal-overlay" id="seek-modal">
  <div class="modal" style="width:440px">
    <h3>
      ⏩ Seek — <span id="seek-stream-name"></span>
      <span class="modal-close" onclick="closeModal('seek-modal')">✕</span>
    </h3>
    <div class="form-group" style="margin-bottom:12px">
      <label>Jump to timestamp (HH:MM:SS)</label>
      <input type="text" id="seek-input" placeholder="00:45:30"
             onkeydown="if(event.key==='Enter')doSeek()">
    </div>
    <label>Or drag slider</label>
    <div class="seek-row" style="margin-bottom:4px">
      <span class="mono" id="seek-slider-val" style="width:58px">00:00:00</span>
      <input type="range" id="seek-slider" min="0" max="100" value="0"
             oninput="seekSliderInput(this.value)">
      <span class="mono" id="seek-dur" style="width:58px;text-align:right">—</span>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
      <button class="btn" onclick="closeModal('seek-modal')">Cancel</button>
      <button class="btn btn-primary" onclick="doSeek()">Seek</button>
    </div>
  </div>
</div>

<div class="notify" id="notify"></div>
"""

_HTML_SCRIPT = r"""
<script>
// ════════════════════════════════════════════
// STATE
// ════════════════════════════════════════════
let streamData    = [];
let libraryData   = [];
let logEntries    = [];
let logLevel      = 'ALL';
let seekTarget    = null;
let seekDuration  = 0;
let autoRefresh   = true;
let refreshTimer  = null;
let editorRows    = [];

// ════════════════════════════════════════════
// UTILS
// ════════════════════════════════════════════
function fmtSecs(s) {
  s = Math.max(0, Math.floor(+s));
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}
function fmtBytes(n) {
  if (n<1024) return n+' B';
  if (n<1048576) return (n/1024).toFixed(1)+' KB';
  if (n<1073741824) return (n/1048576).toFixed(1)+' MB';
  return (n/1073741824).toFixed(2)+' GB';
}
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function notify(msg, type='ok') {
  const el = document.getElementById('notify');
  el.textContent = msg; el.className = 'notify '+type+' show';
  setTimeout(()=>el.classList.remove('show'), 3000);
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}
function openModal(id) {
  document.getElementById(id).classList.add('open');
}

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(el => {
  el.addEventListener('click', e => { if (e.target === el) el.classList.remove('open'); });
});

// ════════════════════════════════════════════
// TAB NAVIGATION
// ════════════════════════════════════════════
function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  const labels = {streams:'Streams',upload:'Upload',library:'Library',
                  editor:'Config',events:'Sched',logs:'Logs'};
  document.querySelectorAll('nav button').forEach(btn=>{
    if(btn.textContent.trim()===labels[name]) btn.classList.add('active');
  });
  if(name==='streams')  loadStreams();
  else if(name==='library') loadLibrary();
  else if(name==='editor')  loadEditor();
  else if(name==='events') { loadEvents(); loadEventFormData(); }
  else if(name==='logs')    loadLogs();
  else if(name==='upload')  loadSubdirs();
}

// ════════════════════════════════════════════
// API
// ════════════════════════════════════════════
async function api(action, data={}) {
  try {
    const r = await fetch('/api/'+action, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    const j = await r.json();
    if(j.ok) { notify(j.msg||'Done ✓'); loadStreams(); }
    else notify(j.msg||'Error', 'err');
    return j;
  } catch(e) { notify('Request failed: '+e,'err'); }
}

// ════════════════════════════════════════════
// HEADER STATS
// ════════════════════════════════════════════
async function updateHeaderStats() {
  try {
    const [sdata, stats] = await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/system_stats').then(r=>r.json()),
    ]);
    const live = sdata.filter(s=>s.status==='LIVE').length;
    document.getElementById('h-live').textContent  = live;
    document.getElementById('h-cpu').textContent   = stats.cpu+'%';
    document.getElementById('h-ram').textContent   = stats.mem_percent+'%';
    document.getElementById('h-disk').textContent  = stats.disk_percent+'%';
    const now = new Date();
    document.getElementById('h-time').textContent  =
      String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
  } catch(_){}
}

// ════════════════════════════════════════════
// STREAMS
// ════════════════════════════════════════════
function toggleAutoRefresh(on) {
  autoRefresh = on;
  if(on) startRefresh(); else clearInterval(refreshTimer);
}
function startRefresh() {
  clearInterval(refreshTimer);
  refreshTimer = setInterval(()=>{ loadStreams(); updateHeaderStats(); }, 3000);
}

async function loadStreams() {
  const r = await fetch('/api/streams');
  streamData = await r.json();
  renderStreams();
}

function renderStreams() {
  const tb = document.getElementById('streams-tbody');
  tb.innerHTML = streamData.map((s,i) => {
    const pct = s.progress.toFixed(1);
    const fillColor = s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
    const isLive = s.status==='LIVE';
    return `
<tr>
  <td class="mono" style="color:var(--muted)">${i+1}</td>
  <td>
    <strong style="cursor:pointer;color:var(--blue)" onclick="openDetail('${esc(s.name)}')"
            title="Click for details">${esc(s.name)}</strong>
    ${s.shuffle?'<span style="font-size:9px;color:var(--purple);margin-left:4px">⧖SHUFFLE</span>':''}
    ${s.hls_url?'<span style="font-size:9px;color:var(--orange);margin-left:4px">[HLS]</span>':''}
  </td>
  <td><code class="mono" style="color:var(--cyan)">${s.port}</code></td>
  <td style="color:var(--muted);font-size:11px">${esc(s.weekdays)}</td>
  <td><span class="badge badge-${esc(s.status)}">${esc(s.status)}</span></td>
  <td style="min-width:130px">
    <div style="display:flex;align-items:center;gap:6px">
      <div class="progress-bar">
        <div class="progress-fill" style="width:${pct}%;background:${fillColor}"></div>
      </div>
      <span class="mono" style="color:var(--muted);min-width:38px">${pct}%</span>
    </div>
    ${isLive?`
    <div class="seek-row" style="margin-top:3px">
      <span class="mono" style="font-size:10px;color:var(--muted);min-width:52px">${esc(s.position.split('/')[0]||'')}</span>
      <input type="range" min="0" max="${Math.max(1,Math.floor(s.duration))}"
             value="${Math.floor(s.current_secs)}"
             title="Drag to seek"
             data-stream="${esc(s.name)}"
             oninput="this.nextElementSibling.textContent=fmtSecs(this.value)"
             onchange="inlineSeek('${esc(s.name)}',+this.value)"
             style="flex:1">
      <span class="mono" style="font-size:10px;color:var(--muted);min-width:52px;text-align:right">${esc(s.position.split('/')[1]||'—')}</span>
    </div>`:''}
  </td>
  <td class="mono" style="color:var(--muted);font-size:11px;white-space:nowrap">${esc(s.position)}</td>
  <td class="mono" style="color:var(--muted)">${s.fps>0?Math.round(s.fps):'—'}</td>
  <td>
    <span class="rtsp-chip" onclick="copyURL('${esc(s.rtsp_url)}')" title="Click to copy RTSP URL">${esc(s.rtsp_url)}</span>
    ${s.hls_url?`<br><span class="rtsp-chip" style="color:var(--orange);margin-top:3px" onclick="copyURL('${esc(s.hls_url)}')" title="Copy HLS URL">HLS ↗</span>`:''}
  </td>
  <td style="white-space:nowrap">
    <button class="btn btn-sm btn-success" onclick="api('start',{name:'${esc(s.name)}'})">▶</button>
    <button class="btn btn-sm btn-danger"  onclick="api('stop', {name:'${esc(s.name)}'})">■</button>
    <button class="btn btn-sm"             onclick="api('restart',{name:'${esc(s.name)}'})">↺</button>
    <button class="btn btn-sm"             onclick="openSeek('${esc(s.name)}',${s.duration},${s.current_secs})" title="Seek">⏩</button>
  </td>
</tr>`;
  }).join('');
}

function copyURL(url) {
  navigator.clipboard.writeText(url).then(()=>notify('Copied ✓','info'));
}

function inlineSeek(name, secs) {
  api('seek', {name, seconds: secs}).then(()=>setTimeout(loadStreams, 500));
}

// ════════════════════════════════════════════
// STREAM DETAIL
// ════════════════════════════════════════════
async function openDetail(name) {
  const r = await fetch('/api/stream_detail?name='+encodeURIComponent(name));
  const d = await r.json();
  if(d.error){ notify(d.error,'err'); return; }

  document.getElementById('detail-title').textContent = d.name;
  document.getElementById('detail-start').onclick = ()=>{ api('start',{name:d.name}); closeModal('detail-modal'); };
  document.getElementById('detail-stop' ).onclick = ()=>{ api('stop', {name:d.name}); closeModal('detail-modal'); };
  document.getElementById('detail-rst'  ).onclick = ()=>{ api('restart',{name:d.name}); closeModal('detail-modal'); };

  const pct = d.progress.toFixed(1);
  const fillColor = d.progress>80?'var(--red)':d.progress>55?'var(--yellow)':'var(--green)';

  let playlist_html = d.playlist.map((p,i)=>`
    <div class="playlist-item ${p.current?'current':''}">
      <span class="pi-idx">${i+1}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(p.path)}">${esc(p.file)}</span>
      <span class="mono" style="color:var(--muted)">${esc(p.start)}</span>
      ${p.current?'<span style="color:var(--green);font-size:10px">▶ NOW</span>':''}
      ${!p.exists?'<span style="color:var(--red);font-size:10px">✗ MISSING</span>':''}
    </div>`).join('');

  let logs_html = d.log.slice(-40).map(line=>{
    const lv = line.includes(' ERROR ')||line.includes('] [Stream') ? (
      line.includes('Error')||line.includes('error')||line.includes('ERROR')?'err':'info'
    ) : line.includes('WARN')||line.includes('restart')?'warn':'info';
    return `<div class="log-${lv}">${esc(line)}</div>`;
  }).join('');

  document.getElementById('detail-content').innerHTML = `
    <div class="detail-grid">
      <div class="detail-item"><div class="dk">Status</div><div class="dv"><span class="badge badge-${esc(d.status)}">${esc(d.status)}</span></div></div>
      <div class="detail-item"><div class="dk">Port</div><div class="dv" style="color:var(--cyan)">:${d.port}</div></div>
      <div class="detail-item"><div class="dk">Video Bitrate</div><div class="dv">${esc(d.video_bitrate)}</div></div>
      <div class="detail-item"><div class="dk">Audio Bitrate</div><div class="dv">${esc(d.audio_bitrate)}</div></div>
      <div class="detail-item"><div class="dk">Schedule</div><div class="dv">${esc(d.weekdays)}</div></div>
      <div class="detail-item"><div class="dk">Restarts</div><div class="dv" style="color:${d.restart_count>0?'var(--yellow)':'var(--green)'}">${d.restart_count}</div></div>
      <div class="detail-item"><div class="dk">Loop Count</div><div class="dv">${d.loop_count}</div></div>
      <div class="detail-item"><div class="dk">FPS / Speed</div><div class="dv">${d.fps>0?Math.round(d.fps)+' fps':d.speed}</div></div>
    </div>
    ${d.error_msg?`<div style="background:var(--red-dim);border:1px solid rgba(243,139,168,.3);border-radius:var(--radius-sm);padding:8px 12px;font-size:11px;color:var(--red);margin-bottom:12px;font-family:var(--font-mono)">${esc(d.error_msg)}</div>`:''}
    <div style="margin-bottom:6px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em">Progress</div>
    <div class="seek-row" style="margin-bottom:14px">
      <span class="mono" style="font-size:11px;min-width:58px">${fmtSecs(d.current_pos)}</span>
      <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${fillColor}"></div></div>
      <span class="mono" style="font-size:11px;min-width:58px;text-align:right">${fmtSecs(d.duration)}</span>
    </div>
    <div style="margin-bottom:6px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em">Playlist (${d.playlist.length} file${d.playlist.length!==1?'s':''})</div>
    <div style="margin-bottom:14px">${playlist_html||'<span style="color:var(--muted)">No files</span>'}</div>
    <div style="margin-bottom:6px;display:flex;align-items:center;gap:8px">
      <span style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em">Recent Log</span>
      <button class="btn btn-sm" onclick="openDetail('${esc(d.name)}')">↻ Refresh</button>
    </div>
    <div class="log-box">${logs_html||'<span style="color:var(--muted)">No log entries</span>'}</div>
  `;
  openModal('detail-modal');
}

// ════════════════════════════════════════════
// SEEK MODAL
// ════════════════════════════════════════════
function openSeek(name, duration, currentSecs) {
  seekTarget = name; seekDuration = duration;
  document.getElementById('seek-stream-name').textContent = name;
  document.getElementById('seek-input').value = '';
  document.getElementById('seek-slider').max   = Math.floor(duration);
  document.getElementById('seek-slider').value = Math.floor(currentSecs);
  document.getElementById('seek-slider-val').textContent = fmtSecs(currentSecs);
  document.getElementById('seek-dur').textContent = fmtSecs(duration);
  openModal('seek-modal');
  document.getElementById('seek-input').focus();
}
function seekSliderInput(v) {
  document.getElementById('seek-slider-val').textContent = fmtSecs(v);
}
function doSeek() {
  let secs;
  const txt = document.getElementById('seek-input').value.trim();
  if(txt) {
    const parts = txt.split(':').map(Number);
    secs = parts.length===3 ? parts[0]*3600+parts[1]*60+parts[2]
         : parts.length===2 ? parts[0]*60+parts[1] : parts[0];
    if(isNaN(secs)||secs<0){ notify('Invalid time format','err'); return; }
  } else {
    secs = +document.getElementById('seek-slider').value;
  }
  if(secs>seekDuration&&seekDuration>0){ notify('Position beyond duration','err'); return; }
  api('seek',{name:seekTarget, seconds:secs});
  closeModal('seek-modal');
}

// ════════════════════════════════════════════
// UPLOAD
// ════════════════════════════════════════════
const dropZone = document.getElementById('drop-zone');
dropZone.addEventListener('dragover',  e=>{ e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', ()=>dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e=>{ e.preventDefault(); dropZone.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); });

const MAX_UPLOAD = 10 * 1024 * 1024 * 1024;

function handleFiles(files) { Array.from(files).forEach(uploadFile); }

function uploadFile(file) {
  if(file.size > MAX_UPLOAD){ notify(`${file.name}: exceeds 10 GB limit`,'err'); return; }
  const key = file.name.replace(/[^\w]/g,'_');
  const li  = document.createElement('li');
  li.id     = 'li-'+key;
  const subdir = document.getElementById('upload-subdir').value;
  li.innerHTML = `
    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(file.name)}</span>
    <span style="color:var(--muted);font-size:10px;white-space:nowrap">${fmtBytes(file.size)}</span>
    <div class="upload-bar"><div class="upload-fill" id="bar-${key}" style="width:0"></div></div>
    <span id="pct-${key}" style="font-size:10px;color:var(--muted);min-width:32px;text-align:right">0%</span>`;
  document.getElementById('upload-list').appendChild(li);

  const fd = new FormData(); fd.append('file',file); fd.append('subdir',subdir);
  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = e => {
    if(!e.lengthComputable) return;
    const pct = Math.round(e.loaded/e.total*100);
    const bar = document.getElementById('bar-'+key);
    const pctEl = document.getElementById('pct-'+key);
    if(bar) bar.style.width=pct+'%';
    if(pctEl) pctEl.textContent=pct+'%';
  };
  xhr.onload = () => {
    const pctEl = document.getElementById('pct-'+key);
    if(xhr.status===200){ if(pctEl){pctEl.textContent='✓';pctEl.style.color='var(--green)';}  notify(file.name+' uploaded ✓'); }
    else { if(pctEl){pctEl.textContent='✗';pctEl.style.color='var(--red)';}  notify('Upload failed: '+file.name,'err'); }
  };
  xhr.onerror = () => notify('Upload error: '+file.name,'err');
  xhr.open('POST','/api/upload'); xhr.send(fd);
}

async function loadSubdirs() {
  const r = await fetch('/api/subdirs');
  const data = await r.json();
  const sel = document.getElementById('upload-subdir');
  sel.innerHTML = '<option value="">/ (media root)</option>';
  data.dirs.filter(d=>d).forEach(d=>{ sel.innerHTML+=`<option value="${esc(d)}">${esc(d)}</option>`; });
}

async function createSubdir() {
  const name = prompt('New folder name:'); if(!name||!name.trim()) return;
  if(/[\/\\<>"|?*]/.test(name)){ notify('Invalid folder name','err'); return; }
  await api('create_subdir',{name:name.trim()});
  loadSubdirs();
}

// ════════════════════════════════════════════
// LIBRARY
// ════════════════════════════════════════════
async function loadLibrary() {
  document.getElementById('library-tbody').innerHTML =
    '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px">Loading…</td></tr>';
  const r = await fetch('/api/library');
  libraryData = await r.json();
  filterLibrary();
}

function filterLibrary() {
  const q   = document.getElementById('lib-search').value.toLowerCase();
  const srt = document.getElementById('lib-sort').value;
  let data  = libraryData.filter(f=>f.path.toLowerCase().includes(q));
  if(srt==='size') data.sort((a,b)=>b.size_bytes-a.size_bytes);
  else if(srt==='dur') data.sort((a,b)=>b.duration_secs-a.duration_secs);
  else data.sort((a,b)=>a.path.localeCompare(b.path));
  renderLibrary(data);
}

function renderLibrary(data) {
  const tb = document.getElementById('library-tbody');
  if(!data.length){ tb.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px">No files found.</td></tr>'; return; }
  tb.innerHTML = data.map(f=>`
<tr>
  <td class="mono" style="word-break:break-all;font-size:11px;max-width:300px">
    <span title="${esc(f.full_path)}">${esc(f.path)}</span>
  </td>
  <td class="mono" style="white-space:nowrap">${esc(f.duration)||'—'}</td>
  <td class="mono" style="white-space:nowrap">${esc(f.size)||'—'}</td>
  <td style="font-size:11px">${esc(f.video_codec)||'—'}</td>
  <td style="font-size:11px">${f.width&&f.height?f.width+'×'+f.height:'—'}</td>
  <td style="font-size:11px">${f.fps?f.fps+' fps':'—'}</td>
  <td style="white-space:nowrap">
    <button class="btn btn-sm" onclick="copyURL('${esc(f.full_path)}')" title="Copy path">📋</button>
    <button class="btn btn-sm btn-danger" onclick="deleteFile('${esc(f.full_path)}')">🗑</button>
  </td>
</tr>`).join('');
}

async function deleteFile(path) {
  if(!confirm('Permanently delete?\n'+path)) return;
  await api('delete_file',{path});
  loadLibrary();
}

// ════════════════════════════════════════════
// EDITOR
// ════════════════════════════════════════════
async function loadEditor() {
  const r = await fetch('/api/streams_config');
  editorRows = await r.json();
  renderEditor();
}

function renderEditor() {
  const c = document.getElementById('editor-body');
  c.innerHTML = editorRows.map((row,idx)=>`
<div style="background:var(--bg3);border:1px solid var(--border2);border-radius:var(--radius);padding:14px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <strong style="color:var(--blue);font-family:var(--font-mono)">${esc(row.name)}</strong>
    <button class="btn btn-sm btn-danger" onclick="removeStreamRow(${idx})">✕ Remove</button>
  </div>
  <div class="form-row">
    <div class="form-group"><label>Name</label>
      <input value="${esc(row.name)}" onchange="editorRows[${idx}].name=this.value.trim()"></div>
    <div class="form-group"><label>Port</label>
      <input type="number" min="1024" max="65535" value="${row.port}"
             onchange="editorRows[${idx}].port=+this.value"></div>
    <div class="form-group"><label>RTSP Path</label>
      <input value="${esc(row.stream_path||'stream')}" onchange="editorRows[${idx}].stream_path=this.value.trim()"></div>
    <div class="form-group"><label>Weekdays</label>
      <input value="${esc(row.weekdays||'all')}" onchange="editorRows[${idx}].weekdays=this.value.trim()">
      <span class="form-hint">all · mon|wed|fri · weekdays · weekends</span>
    </div>
  </div>
  <div class="form-row">
    <div class="form-group"><label>Video Bitrate</label>
      <input value="${esc(row.video_bitrate||'2500k')}" onchange="editorRows[${idx}].video_bitrate=this.value.trim()"></div>
    <div class="form-group"><label>Audio Bitrate</label>
      <input value="${esc(row.audio_bitrate||'128k')}"  onchange="editorRows[${idx}].audio_bitrate=this.value.trim()"></div>
    <div class="form-group">
      <label>Options</label>
      <div style="display:flex;gap:14px;margin-top:8px;flex-wrap:wrap">
        <label style="display:flex;align-items:center;gap:5px;color:var(--text);font-size:12px;margin:0;cursor:pointer">
          <input type="checkbox" ${row.enabled?'checked':''} onchange="editorRows[${idx}].enabled=this.checked" style="width:auto"> Enabled</label>
        <label style="display:flex;align-items:center;gap:5px;color:var(--text);font-size:12px;margin:0;cursor:pointer">
          <input type="checkbox" ${row.shuffle?'checked':''} onchange="editorRows[${idx}].shuffle=this.checked" style="width:auto"> Shuffle</label>
        <label style="display:flex;align-items:center;gap:5px;color:var(--text);font-size:12px;margin:0;cursor:pointer">
          <input type="checkbox" ${row.hls_enabled?'checked':''} onchange="editorRows[${idx}].hls_enabled=this.checked" style="width:auto"> HLS</label>
      </div>
    </div>
  </div>
  <div class="form-group">
    <label>Playlist Files (one per line · optionally with @HH:MM:SS start offset)</label>
    <textarea rows="3" style="margin-top:4px;font-family:var(--font-mono);font-size:11px"
      onchange="editorRows[${idx}].files=this.value">${esc((row.files||'').split(';').join('\n'))}</textarea>
    <span class="form-hint">Example: /media/intro.mp4@00:00:00</span>
  </div>
</div>`).join('');
}

function addStreamRow() {
  editorRows.push({name:'NewStream',port:8560,files:'',weekdays:'all',
    enabled:true,shuffle:false,stream_path:'stream',
    video_bitrate:'2500k',audio_bitrate:'128k',hls_enabled:false});
  renderEditor();
}
function removeStreamRow(idx) { editorRows.splice(idx,1); renderEditor(); }

async function saveCSV() {
  const rows = editorRows.map(r=>({
    ...r,
    files: (r.files||'').replace(/\n+/g,';').replace(/;+/g,';').trim()
  }));
  // Validate ports
  const ports = rows.map(r=>r.port);
  if(new Set(ports).size !== ports.length){ notify('Duplicate ports detected','err'); return; }
  const res = await api('save_config',{streams:rows});
  if(res&&res.ok) { notify('Saved ✓ — restart to apply'); loadEditor(); }
}

// ════════════════════════════════════════════
// EVENTS
// ════════════════════════════════════════════
async function loadEventFormData() {
  const [streams, lib] = await Promise.all([
    fetch('/api/streams').then(r=>r.json()),
    fetch('/api/library').then(r=>r.json()),
  ]);
  const sSel = document.getElementById('evt-stream');
  sSel.innerHTML = streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)} (:${s.port})</option>`).join('');
  const fSel = document.getElementById('evt-file');
  fSel.innerHTML = lib.map(f=>`<option value="${esc(f.full_path)}">${esc(f.path)}</option>`).join('');
  const dt = new Date(Date.now()+5*60000);
  document.getElementById('evt-datetime').value =
    new Date(dt-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);

  // Populate log stream filter
  const sel = document.getElementById('log-stream-filter');
  sel.innerHTML = '<option value="">All Streams</option>'+
    streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
}

async function scheduleEvent() {
  const stream = document.getElementById('evt-stream').value;
  const file   = document.getElementById('evt-file').value;
  const dt     = document.getElementById('evt-datetime').value;
  const pos    = document.getElementById('evt-startpos').value || '00:00:00';
  const post   = document.getElementById('evt-postaction').value;
  if(!stream||!file||!dt){ notify('Fill all required fields','err'); return; }
  // Validate start position format
  if(!/^\d{2}:\d{2}:\d{2}$/.test(pos)){ notify('Start position must be HH:MM:SS','err'); return; }
  await api('add_event',{stream_name:stream,file_path:file,play_at:dt,start_pos:pos,post_action:post});
  loadEvents();
}

async function loadEvents() {
  const r    = await fetch('/api/events');
  const data = await r.json();
  const now  = Date.now();
  const tb   = document.getElementById('events-tbody');
  tb.innerHTML = data.map(ev=>{
    const playAt = new Date(ev.play_at.replace(' ','T'));
    const delta  = ((playAt - now)/1000).toFixed(0);
    const countdown = ev.played ? '—' : delta>0 ? `in ${Math.floor(delta/60)}m ${delta%60}s` : `${Math.abs(delta)}s ago`;
    return `
<tr>
  <td>${esc(ev.stream_name)}</td>
  <td class="mono" style="font-size:11px">${esc(ev.file_name)}</td>
  <td class="mono" style="font-size:11px;white-space:nowrap">${esc(ev.play_at)}</td>
  <td class="mono" style="font-size:11px;color:${delta>0?'var(--yellow)':'var(--muted)'}">${countdown}</td>
  <td style="font-size:11px">${esc(ev.post_action)}</td>
  <td><span class="badge ${ev.played?'badge-STOPPED':'badge-SCHED'}">${ev.played?'Played':'Pending'}</span></td>
  <td><button class="btn btn-sm btn-danger" onclick="deleteEvent('${esc(ev.event_id)}')">✕</button></td>
</tr>`;
  }).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px">No events scheduled.</td></tr>';
}

async function deleteEvent(id) {
  if(!confirm('Delete this event?')) return;
  await api('delete_event',{event_id:id});
  loadEvents();
}

async function clearPlayedEvents() {
  if(!confirm('Remove all played events?')) return;
  const r    = await fetch('/api/events').then(r=>r.json());
  const played = r.filter(e=>e.played).map(e=>e.event_id);
  for(const id of played) await fetch('/api/delete_event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:id})});
  loadEvents();
}

// ════════════════════════════════════════════
// LOGS
// ════════════════════════════════════════════
function setLogLevel(level) {
  logLevel = level;
  document.querySelectorAll('.log-chip').forEach(c=>{
    c.className = 'log-chip'+(c.dataset.level===level?' active-'+level:'');
  });
  renderLogEntries();
}

async function loadLogs() {
  const stream = document.getElementById('log-stream-filter').value;
  const url = `/api/logs?level=${logLevel}&stream=${encodeURIComponent(stream)}&n=500`;
  const r   = await fetch(url);
  const data = await r.json();
  logEntries = data.entries;
  renderLogEntries();
}

function renderLogEntries() {
  const q     = (document.getElementById('log-search').value||'').toLowerCase();
  const colors = {INFO:'var(--text)',WARN:'var(--yellow)',ERROR:'var(--red)'};
  const el    = document.getElementById('log-container');
  const items = logEntries
    .filter(([msg])=> !q || msg.toLowerCase().includes(q))
    .slice().reverse()
    .map(([msg,lvl])=>`<div style="color:${colors[lvl]||'var(--text)'};padding:1px 0;border-bottom:1px solid var(--faint)">${esc(msg)}</div>`)
    .join('');
  el.innerHTML = items || '<span style="color:var(--muted)">No entries.</span>';
  if(document.getElementById('log-autoscroll').checked) el.scrollTop = 0;
}

// ════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════
loadStreams();
updateHeaderStats();
startRefresh();
setInterval(updateHeaderStats, 5000);
setInterval(()=>{
  if(document.getElementById('tab-events').classList.contains('active')) loadEvents();
  if(document.getElementById('tab-logs').classList.contains('active'))   loadLogs();
}, 8000);

// Clock
setInterval(()=>{
  const now = new Date();
  const el  = document.getElementById('h-time');
  if(el) el.textContent =
    String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0');
}, 1000);

// Keyboard shortcuts
document.addEventListener('keydown', e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA') return;
  if(e.key==='Escape'){
    document.querySelectorAll('.modal-overlay.open').forEach(m=>m.classList.remove('open'));
  }
});
</script>
"""

HTML_PAGE = (
    "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
    "<meta charset='UTF-8'>\n"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
    "<title>HydraCast Web UI</title>\n"
    + _HTML_STYLE
    + "</head>\n<body>\n"
    + _HTML_BODY
    + _HTML_SCRIPT
    + "\n</body>\n</html>"
)


# =============================================================================
# WEB HANDLER  —  v3.1: security headers, new endpoints, hardened upload
# =============================================================================
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options":        "SAMEORIGIN",
    "X-XSS-Protection":       "1; mode=block",
    "Referrer-Policy":        "strict-origin",
    "Cache-Control":          "no-store",
}


class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # suppress default access log

    def _send(self, code: int, body: Union[str, bytes], ct: str = "application/json") -> None:
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in _SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data, default=str), "application/json")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send(200, HTML_PAGE, "text/html; charset=utf-8")
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
        if length > 1 * 1024 * 1024:   # 1 MB max for JSON body
            self._json({"ok": False, "msg": "Request body too large"}, 413)
            return
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
        except Exception:
            self._json({"ok": False, "msg": "Invalid JSON"}, 400)
            return

        action = path.replace("/api/","")
        self._dispatch(action, data)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── GET endpoints ─────────────────────────────────────────────────────────
    def _get_streams(self) -> None:
        if not _WEB_MANAGER: self._json([]); return
        result = []
        for st in _WEB_MANAGER.states:
            cfg = st.config
            result.append({
                "name":        cfg.name,
                "port":        cfg.port,
                "weekdays":    cfg.weekdays_display(),
                "status":      st.status.label,
                "progress":    st.progress,
                "position":    st.format_pos(),
                "current_secs": st.current_pos,
                "duration":    st.duration,
                "fps":         st.fps,
                "rtsp_url":    cfg.rtsp_url_external,
                "hls_url":     cfg.hls_url if cfg.hls_enabled else "",
                "shuffle":     cfg.shuffle,
                "playlist":    cfg.playlist_display(),
                "enabled":     cfg.enabled,
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
                "files":         ";".join(f"{i.file_path}@{i.start_position}" for i in cfg.playlist),
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
                dirs.append(str(d.relative_to(MEDIA_DIR)))
        self._json({"dirs": sorted(set(dirs))})

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
        if level not in ("ALL", "INFO", "WARN", "ERROR"): level = "ALL"
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
            log_snap = list(st.log[-60:])
        # current playlist index
        cur_real = st.playlist_order[st.playlist_index] if st.playlist_order else 0
        playlist = []
        for i, item in enumerate(cfg.playlist):
            playlist.append({
                "file":    item.file_path.name,
                "path":    str(item.file_path),
                "start":   item.start_position,
                "exists":  item.file_path.exists(),
                "current": (i == cur_real),
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

    # ── POST dispatch ─────────────────────────────────────────────────────────
    def _dispatch(self, action: str, data: Dict) -> None:
        mgr = _WEB_MANAGER
        if not mgr: self._json({"ok": False, "msg": "Manager not ready"}); return

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
                        raise ValueError("Invalid stream name")
                    port = int(row.get("port", 0))
                    if not (1024 <= port <= 65535):
                        raise ValueError(f"Port {port} out of range")
                    playlist = CSVManager.parse_files(
                        str(row.get("files","")).replace("\n",";"))
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
                # Check for duplicate ports
                ports = [c.port for c in configs]
                if len(set(ports)) != len(ports):
                    raise ValueError("Duplicate port numbers")
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

                # Parse datetime from either "YYYY-MM-DDTHH:MM" or "YYYY-MM-DD HH:MM:SS"
                for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt = datetime.strptime(play_at, fmt); break
                    except ValueError:
                        continue
                else:
                    raise ValueError("Invalid datetime format")

                fp = Path(file_path)
                safe = _safe_path(fp, MEDIA_DIR)
                # Allow files outside MEDIA_DIR only if they exist (configured in CSV)
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
                self._json({"ok": False, "msg": "File not in media directory"}); return
            try:
                safe.unlink()
                self._json({"ok": True, "msg": f"Deleted {safe.name}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "create_subdir":
            raw  = str(data.get("name","")).strip()
            # Reject path-traversal attempts and shell-special chars
            if not raw or re.search(r'[/\\<>"|?*\x00]', raw) or ".." in raw:
                self._json({"ok": False, "msg": "Invalid folder name"}); return
            target = MEDIA_DIR / raw
            safe   = _safe_path(target, MEDIA_DIR)
            if safe is None:
                self._json({"ok": False, "msg": "Path traversal denied"}); return
            try:
                safe.mkdir(parents=True, exist_ok=True)
                self._json({"ok": True, "msg": f"Created: {raw}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        else:
            self._json({"ok": False, "msg": f"Unknown action: {action}"})

    def _handle_upload(self) -> None:
        import cgi
        try:
            # Check Content-Length before reading to enforce server-side cap
            cl = int(self.headers.get("Content-Length", 0))
            if cl > UPLOAD_MAX_BYTES:
                self._json({"ok": False, "msg": "File exceeds 10 GB server limit"}, 413)
                return

            env = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE":   self.headers["Content-Type"],
                "CONTENT_LENGTH": self.headers.get("Content-Length","0"),
            }
            form   = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                      environ=env, keep_blank_values=True)
            f_item = form["file"]
            subdir = str(form.getvalue("subdir","")).strip().replace("..","")

            # Validate file extension
            fname = Path(f_item.filename).name
            if not fname:
                self._json({"ok": False, "msg": "Empty filename"}); return
            ext = Path(fname).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                self._json({"ok": False, "msg": f"Unsupported extension: {ext}"}); return

            # Sanitize filename (no path separators or special chars)
            safe_name = re.sub(r'[^\w.\-]', '_', fname)
            if not safe_name or safe_name.startswith('.'):
                self._json({"ok": False, "msg": "Invalid filename"}); return

            dest_dir = MEDIA_DIR / subdir if subdir else MEDIA_DIR
            safe_dir = _safe_path(dest_dir, MEDIA_DIR)
            if safe_dir is None:
                self._json({"ok": False, "msg": "Invalid upload directory"}); return
            safe_dir.mkdir(parents=True, exist_ok=True)
            dest = safe_dir / safe_name
            dest.write_bytes(f_item.file.read())
            self._json({"ok": True, "msg": f"Saved: {safe_name}"})
        except Exception as exc:
            self._json({"ok": False, "msg": str(exc)}, 500)


class WebServer:
    def __init__(self, port: int = WEB_PORT) -> None:
        self._port   = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        try:
            self._server = HTTPServer(("0.0.0.0", self._port), WebHandler)
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True, name="webui")
            self._thread.start()
            logging.info("Web UI running on http://0.0.0.0:%d", self._port)
        except Exception as exc:
            logging.error("Web UI failed to start: %s", exc)

    def stop(self) -> None:
        if self._server: self._server.shutdown()


# =============================================================================
# TUI  (unchanged from v3.0 except version bump)
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
        tbl.add_column("#",        style=CD,         width=3,      no_wrap=True)
        tbl.add_column("STREAM",   style=CW,         min_width=14, no_wrap=True)
        tbl.add_column("PORT",     style=CC,         width=6,      no_wrap=True)
        tbl.add_column("FILES",    style=CD,         width=8,      no_wrap=True)
        tbl.add_column("SCHEDULE", style=CW,         width=11,     no_wrap=True)
        tbl.add_column("STATUS",                     width=11,     no_wrap=True)
        tbl.add_column("PROGRESS",                   min_width=30, no_wrap=True)
        tbl.add_column("TIME",     style=CD,         width=14,     no_wrap=True)
        tbl.add_column("FPS",      style=CD,         width=5,      no_wrap=True)
        tbl.add_column("LOOP",     style=CD,         width=6,      no_wrap=True)
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
            ("A","All Start"),("X","All Stop"),("←→","Seek ±10s"),
            ("Shift←→","Seek ±60s"),("G","Goto time"),
            ("L","Reload CSV"),("U","Export URLs"),("Q","Quit"),
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
# SEEK PROMPT  (TUI — blocking input)
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
