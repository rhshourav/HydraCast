"""
hc/models.py  —  Core dataclasses and enums.

v6.1 changes vs v6.0
─────────────────────
• StreamConfig gains compliance_alert_enabled (bool, default True).
  When True (and compliance_enabled is True), the Web UI will surface
  compliance errors as a pulsing side-banner every 10 seconds until the
  operator acknowledges or disables alerts in Settings.

• StreamState gains compliance_alert (Optional[str]) — the last compliance
  error message to display in the Web UI — and compliance_alert_ts (float)
  timestamp of when it was set.

Everything else is unchanged from v6.0.
"""
from __future__ import annotations

import threading
import time as _time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from hc.constants import DAY_ABBR, LISTEN_ADDR, WEEKDAY_MAP


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

    # ── Weekday helpers ───────────────────────────────────────────────────────

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
        return self.port + 10000

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
    initial_offset:   float                      = 0.0
    log:              List[str]                  = field(default_factory=list)
    _lock:            threading.Lock             = field(default_factory=threading.Lock)

    # ── Compliance alert state (Web UI banner) ────────────────────────────────
    compliance_alert:          Optional[str]  = None   # current error message
    compliance_alert_ts:       float          = 0.0    # epoch time when alert was set
    # Epoch time of the last periodic drift check (0 = never checked).
    compliance_last_check_ts:  float          = 0.0

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
