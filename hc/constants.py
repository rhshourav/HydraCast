"""
hc/constants.py  —  All global constants and directory paths.

v6.3 changes
────────────
• Multi-root media support: get_media_roots() / set_media_roots() / add_media_root()
  / remove_media_root() manage an ordered list of media root directories.
  The default <base>/media is always the primary root.  Roots are persisted to
  config/media_roots.hcf and loaded automatically on startup.
• load_media_roots() / save_media_roots() — called once from main.py after
  set_base_dir(); the Web UI and TUI write through save_media_roots() so the
  list survives restarts.
• Backup/restore includes the roots list via the "media_roots" key.


"""
from __future__ import annotations

import multiprocessing
import os
import platform
from pathlib import Path
from typing import Dict, List, Optional

# ── App metadata ──────────────────────────────────────────────────────────────
APP_NAME   = "HydraCast"
APP_VER    = "6.5.0"
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


def _resolve_writable_base(install_base: Path) -> Path:
    """
    Return the root that should hold all mutable runtime data.

    Strategy (Windows only):
      1. Try creating a sentinel file inside *install_base*.  If it succeeds
         the directory is writable (e.g. a developer run or a portable install)
         so we keep using it.
      2. Otherwise fall back to %APPDATA%\\HydraCast so the app works
         correctly when installed under C:\\Program Files without UAC every
         single launch.

    On Linux / macOS the install dir is always returned as-is; the OS
    permission model (home-dir installs, venv, sudo) handles this naturally.
    """
    if not IS_WIN:
        return install_base

    sentinel = install_base / ".hc_write_test"
    try:
        sentinel.mkdir(parents=True, exist_ok=True)
        probe = sentinel / "probe"
        probe.touch()
        probe.unlink()
        sentinel.rmdir()
        return install_base          # writable — use it directly
    except PermissionError:
        pass

    # Install dir is read-only (typical Program Files scenario).
    # Redirect to %APPDATA%\HydraCast which is always user-writable.
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME

    # Absolute last resort — should never reach here on a normal Windows install.
    return install_base


def set_base_dir(script_path: Path) -> None:
    """Called once from main.py after __file__ is known."""
    base = script_path.parent.resolve()
    _dirs["BASE"] = base

    # Writable base may differ from the install base when the exe lives in a
    # protected directory such as C:\\Program Files\\HydraCast.
    wb = _resolve_writable_base(base)
    _dirs["WRITABLE_BASE"] = wb

    _dirs["BIN"]    = wb / "bin"
    _dirs["CONFIG"] = wb / "config"
    _dirs["LOGS"]   = wb / "logs"
    _dirs["MEDIA"]  = wb / "media"
    _dirs["SSL"]    = wb / "ssl"
    _dirs["STREAMS_JSON"] = wb / "config" / "streams.hcf"
    _dirs["EVENTS_JSON"]  = wb / "config" / "events.hcf"
    _dirs["CAMERAS_JSON"] = wb / "config" / "cameras.hcf"
    # Legacy paths — migration helpers only
    _dirs["CSV"]        = wb / "streams.csv"
    _dirs["EVENTS_CSV"] = wb / "events.csv"
    for key in ("BIN", "CONFIG", "LOGS", "MEDIA", "SSL"):
        _dirs[key].mkdir(parents=True, exist_ok=True)



# ── Path accessors ─────────────────────────────────────────────────────────────
def _require(key: str) -> Path:
    if key not in _dirs:
        raise RuntimeError(
            f"{key} was accessed before set_base_dir(). "
            "Ensure main.py calls set_base_dir(Path(__file__)) at startup."
        )
    return _dirs[key]

def BASE_DIR()          -> Path: return _require("BASE")
def WRITABLE_BASE_DIR() -> Path: return _require("WRITABLE_BASE")
def BIN_DIR()           -> Path: return _require("BIN")
def CONFIG_DIR()     -> Path: return _require("CONFIG")
def CONFIGS_DIR()    -> Path: return _require("CONFIG")
def LOGS_DIR()       -> Path: return _require("LOGS")
def MEDIA_DIR()      -> Path: return _require("MEDIA")
def SSL_DIR()        -> Path: return _require("SSL")
def SSL_CERT()       -> Path: return _require("SSL") / "cert.pem"
def SSL_KEY()        -> Path: return _require("SSL") / "key.pem"
def STREAMS_JSON()   -> Path: return _require("STREAMS_JSON")
def EVENTS_FILE()    -> Path: return _require("EVENTS_JSON")
def CAMERAS_FILE()   -> Path: return _require("CAMERAS_JSON")
def CSV_FILE()       -> Path: return _require("CSV")
def EVENTS_CSV()     -> Path: return _require("EVENTS_CSV")


# ── Multi-root media support ──────────────────────────────────────────────────
# The list is stored in config/media_roots.hcf.
# The default <base>/media is *always* treated as the primary root even when
# absent from the persisted list (get_media_roots() injects it automatically).
_media_roots: List[Path] = []
_media_roots_loaded: bool = False   # True once load_media_roots() has run


def _media_roots_file() -> Path:
    """Return path to config/media_roots.hcf (requires set_base_dir first)."""
    return _require("CONFIG") / "media_roots.hcf"


def load_media_roots() -> None:
    """
    Load extra media roots from config/media_roots.hcf.
    Call once from main.py after set_base_dir().  Missing file is fine —
    the in-memory list stays empty and get_media_roots() returns the default.
    """
    import json as _json
    global _media_roots, _media_roots_loaded
    _media_roots_loaded = True
    p = _media_roots_file()
    if not p.exists():
        _media_roots = []
        return
    try:
        raw = _json.loads(p.read_text(encoding="utf-8"))
        _media_roots = [Path(r) for r in raw if r]
    except Exception:
        _media_roots = []


def save_media_roots() -> None:
    """
    Persist the current _media_roots list to config/media_roots.hcf.
    Excludes the default MEDIA_DIR so it is re-injected dynamically on load.
    """
    import json as _json
    try:
        default = _require("MEDIA")
    except RuntimeError:
        return
    to_save = [str(r) for r in _media_roots if r.resolve() != default.resolve()]
    p = _media_roots_file()
    tmp = p.with_suffix(".hcf.tmp")
    try:
        tmp.write_text(_json.dumps(to_save, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def get_media_roots() -> List[Path]:
    """
    Return the ordered list of media root directories.
    The default MEDIA_DIR is always first.  Additional user-defined roots
    follow in the order they were added.
    Lazily calls load_media_roots() on first access so that os.execv
    restarts (which skip main.py initialisation) still see the full list.
    """
    global _media_roots_loaded
    if not _media_roots_loaded:
        try:
            load_media_roots()
        except Exception:
            _media_roots_loaded = True  # don't retry on persistent failure
    try:
        default = _require("MEDIA")
    except RuntimeError:
        return []
    seen: set[Path] = {default.resolve()}
    result: List[Path] = [default]
    for r in _media_roots:
        resolved = r.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(r)
    return result


def set_media_roots(roots: List[Path]) -> None:
    """
    Replace the extra roots list and persist to disk.
    The default MEDIA_DIR is always kept as the first root; duplicates removed.
    """
    try:
        default = _require("MEDIA")
    except RuntimeError:
        return
    seen: set[Path] = {default.resolve()}
    extras: List[Path] = []
    for r in roots:
        p = Path(r)
        res = p.resolve()
        if res not in seen:
            seen.add(res)
            extras.append(p)
    global _media_roots
    _media_roots = extras
    save_media_roots()


def add_media_root(path: Path) -> bool:
    """
    Add *path* as an extra media root.
    Returns True if added, False if already present or equals the default root.
    """
    try:
        default = _require("MEDIA")
    except RuntimeError:
        return False
    r = path.resolve()
    if r == default.resolve():
        return False
    for existing in _media_roots:
        if existing.resolve() == r:
            return False
    _media_roots.append(path)
    save_media_roots()
    return True


def remove_media_root(path: Path) -> bool:
    """
    Remove *path* from the extra roots list.
    The default MEDIA_DIR cannot be removed.
    Returns True if removed, False if not found.
    """
    global _media_roots
    r = path.resolve()
    before = len(_media_roots)
    _media_roots = [x for x in _media_roots if x.resolve() != r]
    if len(_media_roots) != before:
        save_media_roots()
        return True
    return False



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
    # When False: streams are NOT started automatically at launch or by the
    # scheduler.  The user must press Start in the Web UI.  One-shot events
    # will still auto-start a stopped stream so they can fire on time.
    "auto_start":  True,
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
def get_auto_start() -> bool:  return bool(_flags["auto_start"])
def set_auto_start(v: bool)  -> None: _flags["auto_start"] = bool(v)


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
    parser.add_argument(
        "--no-auto-start",
        dest="no_auto_start",
        action="store_true",
        default=False,
        help=(
            "Do not start streams automatically at launch or via the scheduler. "
            "Streams must be started manually from the Web UI. "
            "One-shot events will still auto-start a stopped stream so they fire on time."
        ),
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
    if getattr(args, "no_auto_start", False):
        set_auto_start(False)


# ── Weekdays ──────────────────────────────────────────────────────────────────
from typing import Any, Union  # noqa: E402
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
