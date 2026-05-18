"""
hc/constants.py  —  All global constants and directory paths.

v6.2 changes
────────────
• apply_cli_args(args) helper: call it from main.py after argparse.parse_args()
  to wire --web-port / --port, --listen, --ssl-cert, --ssl-key, --no-firewall
  into the shared _flags dict in one place.
• WEB_PORT default changed to 443 (HTTPS); WebServer auto-generates a
  self-signed cert when ssl/cert.pem + ssl/key.pem are absent.
• validate_port() utility used by both CLI and the TUI port-change prompt.

v6.0 / v6.1 changes kept below.
"""
from __future__ import annotations

import multiprocessing
import platform
from pathlib import Path
from typing import Dict, Optional

# ── App metadata ──────────────────────────────────────────────────────────────
APP_NAME   = "HydraCast"
APP_VER    = "6.2.0"
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
_dirs: Dict[str, Path] = {}

def set_base_dir(script_path: Path) -> None:
    """Called once from main.py after __file__ is known."""
    base = script_path.parent.resolve()
    _dirs["BASE"]    = base
    _dirs["BIN"]     = base / "bin"
    _dirs["CONFIG"]  = base / "config"
    _dirs["CONFIGS"] = base / "configs"
    _dirs["LOGS"]    = base / "logs"
    _dirs["MEDIA"]   = base / "media"
    _dirs["SSL"]     = base / "ssl"
    _dirs["STREAMS_JSON"] = base / "config" / "streams.json"
    _dirs["EVENTS_JSON"]  = base / "config" / "events.json"
    # Legacy paths — migration helpers only
    _dirs["CSV"]        = base / "streams.csv"
    _dirs["EVENTS_CSV"] = base / "events.csv"
    for key in ("BIN", "CONFIG", "CONFIGS", "LOGS", "MEDIA", "SSL"):
        _dirs[key].mkdir(parents=True, exist_ok=True)


# ── Path accessors ─────────────────────────────────────────────────────────────
def _require(key: str) -> Path:
    if key not in _dirs:
        raise RuntimeError(
            f"{key} was accessed before set_base_dir(). "
            "Ensure main.py calls set_base_dir(Path(__file__)) at startup."
        )
    return _dirs[key]

def BASE_DIR()       -> Path: return _require("BASE")
def BIN_DIR()        -> Path: return _require("BIN")
def CONFIG_DIR()     -> Path: return _require("CONFIG")
def CONFIGS_DIR()    -> Path: return _require("CONFIGS")
def LOGS_DIR()       -> Path: return _require("LOGS")
def MEDIA_DIR()      -> Path: return _require("MEDIA")
def SSL_DIR()        -> Path: return _require("SSL")
def SSL_CERT()       -> Path: return _require("SSL") / "cert.pem"
def SSL_KEY()        -> Path: return _require("SSL") / "key.pem"
def STREAMS_JSON()   -> Path: return _require("STREAMS_JSON")
def EVENTS_FILE()    -> Path: return _require("EVENTS_JSON")
def CSV_FILE()       -> Path: return _require("CSV")
def EVENTS_CSV()     -> Path: return _require("EVENTS_CSV")

# ── Web / upload ──────────────────────────────────────────────────────────────
# Default is 443 (HTTPS).  WebServer will auto-generate a self-signed cert when
# ssl/cert.pem + ssl/key.pem are absent.  Override with --web-port 8080 for
# plain HTTP (no cert required).
WEB_PORT         = 443
UPLOAD_MAX_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB

# ── MediaMTX ──────────────────────────────────────────────────────────────────
from typing import Tuple  # noqa: E402
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

_bins: Dict[str, str] = {
    "ffmpeg":  FFMPEG_BIN_NAME,
    "ffprobe": FFPROBE_BIN_NAME,
}

def FFMPEG_PATH()  -> str: return _bins["ffmpeg"]
def FFPROBE_PATH() -> str: return _bins["ffprobe"]
def set_ffmpeg(p: str)  -> None: _bins["ffmpeg"]  = p
def set_ffprobe(p: str) -> None: _bins["ffprobe"] = p

# ── Web port defaults ─────────────────────────────────────────────────────────
# HTTPS port: 443  (main Web UI, TLS)
# HTTP  port:  80  (redirect-only — bounces plain-HTTP visitors to HTTPS)
# Set either to 0 to disable that listener entirely.
HTTP_REDIRECT_PORT = 80

# ── Runtime flags (set from CLI args or TUI prompt) ───────────────────────────
_flags: Dict[str, object] = {
    "no_firewall": False,
    "listen_addr": "0.0.0.0",
    "web_port":    WEB_PORT,
    "http_port":   HTTP_REDIRECT_PORT,
    "ssl_cert":    None,
    "ssl_key":     None,
}

def NO_FIREWALL()    -> bool: return bool(_flags["no_firewall"])
def LISTEN_ADDR()    -> str:  return str(_flags["listen_addr"])
def get_web_port()   -> int:  return int(_flags["web_port"])
def get_http_port()  -> int:  return int(_flags["http_port"])
def get_ssl_cert() -> "Optional[str]": return _flags["ssl_cert"]  # type: ignore[return-value]
def get_ssl_key()  -> "Optional[str]": return _flags["ssl_key"]   # type: ignore[return-value]
def set_no_firewall(v: bool)  -> None: _flags["no_firewall"] = v
def set_listen_addr(v: str)   -> None: _flags["listen_addr"] = v
def set_web_port(v: int)      -> None: _flags["web_port"]    = int(v)
def set_http_port(v: int)     -> None: _flags["http_port"]   = int(v)
def set_ssl_cert(v: str)      -> None: _flags["ssl_cert"]    = v
def set_ssl_key(v: str)       -> None: _flags["ssl_key"]     = v


# ── Port validation ───────────────────────────────────────────────────────────

def validate_port(value: int) -> int:
    """
    Return *value* if it is a valid TCP port (1–65535).
    Raises ValueError with a human-readable message otherwise.
    Used by both argparse (type=validate_port) and the TUI port-change prompt.
    """
    try:
        p = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{value}' is not an integer.")
    if not (1 <= p <= 65535):
        raise ValueError(f"Port {p} is out of range (1–65535).")
    return p


# ── CLI argument wiring ───────────────────────────────────────────────────────

def build_arg_parser():
    """
    Return a pre-configured argparse.ArgumentParser for HydraCast.

    Usage in main.py
    ────────────────
        from hc.constants import build_arg_parser, apply_cli_args, set_base_dir
        from pathlib import Path

        parser = build_arg_parser()
        args   = parser.parse_args()
        set_base_dir(Path(__file__))
        apply_cli_args(args)
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="hydracast",
        description="HydraCast — Multi-Stream RTSP Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  hydracast.py                              # HTTPS :443 + HTTP→HTTPS redirect :80\n"
            "  hydracast.py --web-port 8443             # HTTPS on :8443, redirect on :80\n"
            "  hydracast.py --http-port 8080            # redirect listener on :8080 instead\n"
            "  hydracast.py --http-port 0               # disable the HTTP redirect listener\n"
            "  hydracast.py --listen 192.168.1.10       # bind to specific interface\n"
            "  hydracast.py --ssl-cert /etc/ssl/cert.pem --ssl-key /etc/ssl/key.pem\n"
            "  hydracast.py --no-firewall               # skip OS firewall rule setup\n"
        ),
    )

    parser.add_argument(
        "--web-port", "--port", "-p",
        dest="web_port",
        metavar="PORT",
        type=validate_port,
        default=None,
        help=(
            f"TCP port for the HTTPS Web UI (default: {WEB_PORT}). "
            "Auto-generates a self-signed cert when none is present. "
            "Ports below 1024 typically require elevated privileges."
        ),
    )
    parser.add_argument(
        "--http-port",
        dest="http_port",
        metavar="PORT",
        type=validate_port,
        default=None,
        help=(
            f"TCP port for the plain-HTTP redirect listener (default: {HTTP_REDIRECT_PORT}). "
            "Visitors on this port are automatically redirected to HTTPS. "
            "Set to 0 to disable the HTTP redirect listener entirely. "
            "Only active when SSL is enabled."
        ),
    )
    parser.add_argument(
        "--listen", "--bind",
        dest="listen_addr",
        metavar="ADDR",
        default="0.0.0.0",
        help="IP address to bind (default: 0.0.0.0 — all interfaces).",
    )
    parser.add_argument(
        "--ssl-cert",
        dest="ssl_cert",
        metavar="PATH",
        default=None,
        help="Path to SSL/TLS certificate (.pem). Auto-detected from ssl/cert.pem.",
    )
    parser.add_argument(
        "--ssl-key",
        dest="ssl_key",
        metavar="PATH",
        default=None,
        help="Path to SSL/TLS private key (.pem). Auto-detected from ssl/key.pem.",
    )
    parser.add_argument(
        "--no-firewall",
        dest="no_firewall",
        action="store_true",
        default=False,
        help="Skip automatic OS firewall rule setup.",
    )
    return parser


def apply_cli_args(args) -> None:
    """
    Push parsed argparse namespace values into the shared _flags dict.

    Call this once from main.py immediately after argparse.parse_args()
    and before any module reads get_web_port() / LISTEN_ADDR() etc.

        args = build_arg_parser().parse_args()
        apply_cli_args(args)
    """
    if args.web_port is not None:
        set_web_port(args.web_port)
    if getattr(args, "http_port", None) is not None:
        set_http_port(args.http_port)
    set_listen_addr(args.listen_addr)
    if args.ssl_cert:
        set_ssl_cert(args.ssl_cert)
    if args.ssl_key:
        set_ssl_key(args.ssl_key)
    set_no_firewall(args.no_firewall)


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
