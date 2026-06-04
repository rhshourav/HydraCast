"""
hc/models.py  —  Core dataclasses and enums.

v6.2.1 patch (bug fixes)
─────────────────────────
• StreamConfig gains a __post_init__ that enforces compliance_resync_interval
  ≥ 60.0 s at construction time (Bug 4 fix).  Previously only _monitor()
  clamped this at runtime via max(60.0, cfg.compliance_resync_interval).

• StreamState gains four new properly-declared dataclass fields (Bug 7 fix):
    seek_start_pos        float          = 0.0
    buffering             bool           = False
    restarting            bool           = False
    active_oneshot_event  Optional[object] = None
  These were previously injected dynamically by StreamWorker.__init__ via
  hasattr guards.  Declaring them as fields makes them visible to type
  checkers, introspection, and code that reads StreamState before a worker
  is attached.  The hasattr guards in StreamWorker.__init__ remain harmless.

v6.2 changes vs v6.1
─────────────────────
• New module-level constant CAMERA_PROTOCOL_DEFAULTS: default ports per
  protocol (rtsp, rtmp, http, srt, udp).

• New dataclass CameraConfig (added before StreamConfig):
  Represents a named camera with credentials, protocol, and source type.
  Provides .url and .url_masked properties for URL construction.
  Handles rtsp, rtmp, http, srt, udp network protocols and usb/dshow local
  devices. SRT uses query-string format; UDP/SRT ignore auth fields.

• StreamConfig gains three hybrid source-switching fields:
    source_mode     str            = "playlist"   # "playlist"|"camera"|"hybrid"
    camera_id       Optional[str]  = None         # references CameraConfig.camera_id
    camera_windows  List[Dict]     = []           # schedule windows for hybrid mode

• StreamState gains two source-switching state fields:
    active_source   str            = "playlist"   # current live source
    source_override Optional[str]  = None         # manual override; None = follow schedule

Everything else is unchanged from v6.1.
"""
from __future__ import annotations

import threading
import time as _time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from hc.constants import DAY_ABBR, LISTEN_ADDR, WEEKDAY_MAP


# =============================================================================
# MODULE-LEVEL CONSTANTS
# =============================================================================

CAMERA_PROTOCOL_DEFAULTS: Dict[str, int] = {
    "rtsp": 554,
    "rtmp": 1935,
    "http": 80,
    "srt":  9000,
    "udp":  1234,
}


# =============================================================================
# ENUMS
# =============================================================================
class StreamStatus(Enum):
    STOPPED   = ("●", "dim white",      "STOPPED")
    STARTING  = ("◌", "yellow",         "STARTING")
    LIVE      = ("●", "bright_green",   "LIVE")
    SCHEDULED = ("◷", "bright_cyan",    "SCHED")
    ERROR     = ("●", "bright_red",     "ERROR")
    DISABLED  = ("⊘", "dim",            "DISABLED")
    ONESHOT   = ("◈", "bright_magenta", "ONESHOT")

    @property
    def dot(self)   -> str: return self.value[0]
    @property
    def color(self) -> str: return self.value[1]
    @property
    def label(self) -> str: return self.value[2]


# =============================================================================
# DATACLASSES
# =============================================================================
@dataclass
class OneShotEvent:
    event_id:    str
    stream_name: str
    file_path:   Path
    play_at:     datetime
    post_action: str  = ""      # "" = return to compliance stream after event
    played:      bool = False
    start_pos:   str  = "00:00:00"
    loop_count:  int  = 0       # 0 = play once; -1 = loop indefinitely; N>0 = N extra loops


@dataclass
class PlaylistItem:
    file_path:      Path
    start_position: str = "00:00:00"
    weight:         int = 1
    priority:       int = 999   # lower = plays earlier


@dataclass
class CameraConfig:
    camera_id:   str          # UUID, e.g. "a1b2c3d4-..."
    name:        str          # human label, e.g. "Front Door"
    protocol:    str          # "rtsp" | "rtmp" | "http" | "srt" | "udp"
    host:        str          # IP or hostname, e.g. "192.168.1.50"
    port:        int          # custom port, e.g. 554 (RTSP default), 80, 1935, etc.
    path:        str          # stream path, e.g. "/live" or "/cam/1/stream"
    username:    str  = ""    # optional — empty string means no auth
    password:    str  = ""    # optional — stored in plaintext locally; stripped from backups
    source_type: str  = "rtsp"  # "rtsp" | "usb" | "dshow" — determines FFmpeg input method
    enabled:     bool = True
    notes:       str  = ""

    @property
    def url(self) -> str:
        """
        Build the full source URL from components.
        For usb/dshow source_type, returns the raw host string (device path / dshow name).
        For srt protocol, uses query-string format: srt://host:port?streamid=path
        For udp protocol, ignores auth fields: udp://host:port
        For other network protocols, builds: protocol://[user:pass@]host:port/path
        """
        if self.source_type in ("usb", "dshow"):
            return self.host   # e.g. "/dev/video0" or "My Capture Card"
        if self.protocol == "srt":
            path = self.path.lstrip("/")
            return f"srt://{self.host}:{self.port}?streamid={path}"
        if self.protocol == "udp":
            return f"udp://{self.host}:{self.port}"
        auth = f"{self.username}:{self.password}@" if self.username else ""
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        return f"{self.protocol}://{auth}{self.host}:{self.port}{path}"

    @property
    def url_masked(self) -> str:
        """Same as url but with password replaced by '***' — safe for logs and UI display."""
        if self.source_type in ("usb", "dshow"):
            return self.host
        if self.protocol == "srt":
            path = self.path.lstrip("/")
            return f"srt://{self.host}:{self.port}?streamid={path}"
        if self.protocol == "udp":
            return f"udp://{self.host}:{self.port}"
        auth = f"{self.username}:***@" if self.username else ""
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        return f"{self.protocol}://{auth}{self.host}:{self.port}{path}"


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
    folder_source:  Optional[Path] = None

    # ── Compliance settings ───────────────────────────────────────────────────
    compliance_enabled:         bool  = False
    compliance_start:           str   = "06:00:00"   # broadcast start time
    compliance_loop:            bool  = False         # loop seek for short videos
    compliance_alert_enabled:   bool  = True          # show Web UI banner on error
    # How often (seconds) the background thread re-checks the seek position.
    # Minimum enforced at 60 s; default 2 hours.
    compliance_resync_interval: float = 7200.0
    # Maximum tolerated drift (seconds) before a hard resync is triggered.
    # 0 = always resync on every periodic check regardless of drift.
    compliance_drift_threshold: float = 30.0

    # ── Hybrid source switching ───────────────────────────────────────────────
    source_mode:     str           = "playlist"  # "playlist" | "camera" | "hybrid"
    camera_id:       Optional[str] = None        # references CameraConfig.camera_id
    camera_windows:  List[Dict]    = field(default_factory=list)
    # camera_windows entry format:
    #   {"weekdays": [0,1,2,3,4], "start": "09:00:00", "end": "17:00:00"}
    # Multiple windows per stream are allowed.
    # Outside all windows → playlist plays (in hybrid mode).

    # ── Weekday helpers ───────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        # Bug 4 fix: enforce the documented 60 s minimum for
        # compliance_resync_interval at the data layer.  The comment on the
        # field says "Minimum enforced at 60 s" but previously only _monitor()
        # clamped the value at runtime (max(60.0, cfg.compliance_resync_interval)).
        # A user who sets 0 or a very small value via the JSON/UI would see the
        # monitor clamp it, but code that reads the field directly (tests,
        # introspection, API serialisation) would see the unvalidated value.
        # Enforcing it here makes the constraint visible at construction time
        # and removes the footgun for future callers.
        if self.compliance_resync_interval < 60.0:
            self.compliance_resync_interval = 60.0

    def _int_weekdays(self) -> List[int]:
        result: List[int] = []
        for d in self.weekdays:
            if isinstance(d, int):
                result.append(d)
            else:
                val = WEEKDAY_MAP.get(str(d).strip().lower())
                if isinstance(val, list):
                    result.extend(val)
                elif isinstance(val, int):
                    result.append(val)
        return result

    # ── URL / path properties ─────────────────────────────────────────────────

    @property
    def rtsp_path(self) -> str:
        """
        RTSP stream path segment — always non-empty.
        Returns the configured stream_path (slashes stripped) or "stream".
        """
        if self.stream_path:
            return self.stream_path.strip("/")
        return "stream"

    @property
    def rtsp_url(self) -> str:
        return f"rtsp://127.0.0.1:{self.port}/{self.rtsp_path}"

    @property
    def rtsp_url_external(self) -> str:
        from hc.utils import _local_ip
        ip = LISTEN_ADDR() if LISTEN_ADDR() != "0.0.0.0" else _local_ip()
        return f"rtsp://{ip}:{self.port}/{self.rtsp_path}"

    @property
    def hls_port(self) -> int:
        # RTSP uses an odd port (e.g. 8555); HLS sits on the next (even) port.
        # Using port+1 keeps RTSP and HLS adjacent and avoids the 10000-offset
        # clash with unrelated services.
        return self.port + 1

    @property
    def hls_url(self) -> str:
        from hc.utils import _local_ip
        ip = LISTEN_ADDR() if LISTEN_ADDR() != "0.0.0.0" else _local_ip()
        return f"http://{ip}:{self.hls_port}/{self.rtsp_path}/index.m3u8"

    # ── Schedule helpers ──────────────────────────────────────────────────────

    def is_scheduled_today(self) -> bool:
        return datetime.now().weekday() in self._int_weekdays()

    def weekdays_display(self) -> str:
        days = self._int_weekdays()
        day_set = set(days)
        if day_set == set(range(7)): return "ALL"
        if day_set == set(range(5)): return "Weekdays"
        if day_set == {5, 6}:        return "Weekends"
        if not days:                 return "—"
        return "|".join(DAY_ABBR[d] for d in sorted(day_set))

    def playlist_display(self) -> str:
        n = len(self.playlist)
        if n == 0:  return "[no files]"
        if n == 1:  return self.playlist[0].file_path.name
        return f"{self.playlist[0].file_path.name} (+{n-1} more)"

    def sorted_playlist(self) -> List[PlaylistItem]:
        return sorted(self.playlist, key=lambda x: (x.priority, str(x.file_path)))


@dataclass
class StreamState:
    config:           StreamConfig
    status:           StreamStatus               = StreamStatus.STOPPED
    mtx_proc:         object                     = None
    ffmpeg_proc:      object                     = None
    progress:         float                      = 0.0
    current_pos:      float                      = 0.0
    duration:         float                      = 0.0
    loop_count:       int                        = 0
    fps:              float                      = 0.0
    bitrate:          str                        = "—"
    speed:            str                        = "—"
    error_msg:        str                        = ""
    started_at:       Optional[datetime]         = None
    restart_count:    int                        = 0
    playlist_index:   int                        = 0
    playlist_order:   List[int]                  = field(default_factory=list)
    seek_target:      Optional[float]            = None
    oneshot_active:   bool                       = False
    resuming:         bool                       = False  # True while _after() owns the resume cycle
    initial_offset:   float                      = 0.0
    log:              List[str]                  = field(default_factory=list)
    _lock:            threading.Lock             = field(default_factory=threading.Lock)

    # ── Compliance alert state (Web UI banner) ────────────────────────────────
    compliance_alert:          Optional[str]  = None   # current error message
    compliance_alert_ts:       float          = 0.0    # epoch time when alert was set
    # Epoch time of the last periodic drift check (0 = never checked).
    compliance_last_check_ts:  float          = 0.0

    # ── Source switching state ────────────────────────────────────────────────
    # active_source reflects the currently live source ("playlist" or "camera").
    # source_override is an in-memory manual override; intentionally not
    # persisted to disk — resets to None (follow schedule) on server restart.
    active_source:   str           = "playlist"  # "playlist" | "camera"
    source_override: Optional[str] = None        # manual override; None = follow schedule

    # ── Bug 7 fix: fields that were previously injected dynamically by ────────
    # StreamWorker.__init__ via hasattr guards.  Declaring them here as proper
    # dataclass fields makes them visible to type checkers, introspection, and
    # any code that reads StreamState before a StreamWorker is constructed.
    # The hasattr guards in StreamWorker.__init__ remain harmless (they now
    # always find the attribute already set to the default value).
    seek_start_pos:       float          = 0.0   # absolute position when FFmpeg was last seeked
    buffering:            bool           = False  # True while retrying transient EPIPE/400
    restarting:           bool           = False  # True during _auto_restart() countdown
    active_oneshot_event: Optional[object] = None  # currently playing OneShotEvent or None

    def set_compliance_alert(self, msg: Optional[str]) -> None:
        """Set (or clear) the compliance alert. Thread-safe."""
        with self._lock:
            self.compliance_alert    = msg
            self.compliance_alert_ts = _time.time() if msg else 0.0
        if msg:
            self.log_add(f"[COMPLIANCE ALERT] {msg}")

    def clear_compliance_alert(self) -> None:
        self.set_compliance_alert(None)

    # ── General helpers ───────────────────────────────────────────────────────

    def log_add(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.log.append(f"[{ts}] {msg}")
            if len(self.log) > 400:
                self.log.pop(0)

    def clear_error(self) -> None:
        self.error_msg     = ""
        self.restart_count = 0
        if self.status == StreamStatus.ERROR:
            self.status = StreamStatus.STOPPED

    def format_pos(self) -> str:
        def _f(s: float) -> str:
            s = int(max(0, s))
            return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
        if self.duration > 0:
            return f"{_f(self.current_pos)} / {_f(self.duration)}"
        return "—"

    def time_remaining(self) -> float:
        if self.duration > 0 and self.current_pos > 0:
            return max(0.0, self.duration - self.current_pos)
        return 0.0

    def current_file(self) -> Optional[Path]:
        if not self.config.playlist:
            return None
        idx = self.playlist_order[self.playlist_index] if self.playlist_order else 0
        try:
            return self.config.playlist[idx].file_path
        except IndexError:
            return None
