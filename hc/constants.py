"""
hc/constants.py  —  All global constants and directory paths.

v6.0 changes
────────────
• CONFIG_DIR added: all user-facing config lives in  <base>/config/
• streams.json  now lives at  config/streams.json
• events.json   now lives at  config/events.json   (was events.csv)
• CSV_FILE()    kept for one-shot legacy migration only (streams.csv → config/streams.json)
• EVENTS_CSV()  kept for one-shot legacy migration only (events.csv  → config/events.json)
"""
from __future__ import annotations

import multiprocessing
import platform
from pathlib import Path
from typing import Dict, Tuple

# ── App metadata ──────────────────────────────────────────────────────────────
APP_NAME   = "HydraCast"
APP_VER    = "0.0.001"
APP_AUTHOR = "rhshourav"
APP_GITHUB = "https://github.com/rhshourav/HydraCast"

# ── Platform ──────────────────────────────────────────────────────────────────
IS_WIN   = platform.system() == "Windows"
IS_MAC   = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
OS_KEY   = "windows" if IS_WIN else "linux"
ARCH_KEY = platform.machine()
CPU_COUNT = max(1, multiprocessing.cpu_count())

# ── Directory layout ──────────────────────────────────────────────────────────
# BASE_DIR is set at runtime by main.py via set_base_dir(); default = cwd/..
# We expose a mutable dict so modules share the same reference.
_dirs: Dict[str, Path] = {}

def set_base_dir(script_path: Path) -> None:
    """Called once from main.py after __file__ is known."""
    base = script_path.parent.resolve()
    _dirs["BASE"]    = base
    _dirs["BIN"]     = base / "bin"
    _dirs["CONFIG"]  = base / "config"              # ← user-facing config dir (NEW)
    _dirs["CONFIGS"] = base / "configs"             # ← mediamtx generated YAMLs
    _dirs["LOGS"]    = base / "logs"
    _dirs["MEDIA"]   = base / "media"
    # Canonical config file locations inside config/
    _dirs["STREAMS_JSON"] = base / "config" / "streams.json"
    _dirs["EVENTS_JSON"]  = base / "config" / "events.json"
    # Legacy paths — kept ONLY for migration helpers (not created automatically)
    _dirs["CSV"]          = base / "streams.csv"       # old streams location
    _dirs["EVENTS_CSV"]   = base / "events.csv"        # old events location
    # Create required runtime dirs
    for key in ("BIN", "CONFIG", "CONFIGS", "LOGS", "MEDIA"):
        _dirs[key].mkdir(parents=True, exist_ok=True)

# ── Path accessors ─────────────────────────────────────────────────────────────
def BASE_DIR()       -> Path: return _dirs["BASE"]
def BIN_DIR()        -> Path: return _dirs["BIN"]
def CONFIG_DIR()     -> Path: return _dirs["CONFIG"]          # config/ folder
def CONFIGS_DIR()    -> Path: return _dirs["CONFIGS"]         # mediamtx yml folder
def LOGS_DIR()       -> Path: return _dirs["LOGS"]
def MEDIA_DIR()      -> Path: return _dirs["MEDIA"]
def STREAMS_JSON()   -> Path: return _dirs["STREAMS_JSON"]    # config/streams.json
def EVENTS_FILE()    -> Path: return _dirs["EVENTS_JSON"]     # config/events.json
# Legacy helpers (used only by migration code)
def CSV_FILE()       -> Path: return _dirs["CSV"]             # old streams.csv
def EVENTS_CSV()     -> Path: return _dirs["EVENTS_CSV"]      # old events.csv

# ── Web / upload ──────────────────────────────────────────────────────────────
WEB_PORT         = 80
UPLOAD_MAX_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB

# ── MediaMTX ──────────────────────────────────────────────────────────────────
MEDIAMTX_VER = "1.9.1"

def MEDIAMTX_BIN() -> Path:
    return BIN_DIR() / ("mediamtx.exe" if IS_WIN else "mediamtx")

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

# Resolved at pre-flight; mutable so _preflight can update them.
_bins: Dict[str, str] = {
    "ffmpeg":  FFMPEG_BIN_NAME,
    "ffprobe": FFPROBE_BIN_NAME,
}

def FFMPEG_PATH()  -> str: return _bins["ffmpeg"]
def FFPROBE_PATH() -> str: return _bins["ffprobe"]
def set_ffmpeg(p: str)  -> None: _bins["ffmpeg"]  = p
def set_ffprobe(p: str) -> None: _bins["ffprobe"] = p

# ── Runtime flags (set from CLI args) ─────────────────────────────────────────
_flags: Dict[str, object] = {
    "no_firewall": False,
    "listen_addr": "0.0.0.0",
    "web_port":    WEB_PORT,
}

def NO_FIREWALL()  -> bool: return bool(_flags["no_firewall"])
def LISTEN_ADDR()  -> str:  return str(_flags["listen_addr"])
def get_web_port() -> int:  return int(_flags["web_port"])
def set_no_firewall(v: bool)  -> None: _flags["no_firewall"] = v
def set_listen_addr(v: str)   -> None: _flags["listen_addr"] = v
def set_web_port(v: int)      -> None: _flags["web_port"]    = v

# ── Weekdays ──────────────────────────────────────────────────────────────────
from typing import Any, List, Union  # noqa: E402
WEEKDAY_MAP: Dict[str, Any] = {
    "mon": 0, "monday": 0, "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2, "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4, "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
    "all": list(range(7)), "everyday": list(range(7)),
    "weekdays": list(range(5)), "weekends": [5, 6],
}
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ── Media formats ─────────────────────────────────────────────────────────────
SUPPORTED_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".ts", ".m2ts", ".flv",
    ".wmv", ".webm", ".mpg", ".mpeg", ".m4v", ".3gp", ".ogv",
    ".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a",
}

# ── Rich colour shortcuts ──────────────────────────────────────────────────────
CG = "bright_green"; CR = "bright_red";  CY = "yellow"
CC = "bright_cyan";  CW = "white";        CD = "dim white"
CM = "bright_magenta"; CB = "bright_blue"
