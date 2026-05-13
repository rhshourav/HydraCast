"""
hc/models.py  —  Core dataclasses and enums.

v6.0 fixes vs new broken version
──────────────────────────────────
• rtsp_path   restored to return "stream" when stream_path is empty (old behaviour).
              The new version returned "" which caused FFmpeg to push to
              rtsp://127.0.0.1:<port>/  (empty path) while rtsp_url / rtsp_url_external
              still showed /stream — a silent mismatch that broke all streams.
• rtsp_url / rtsp_url_external / hls_url now all derive from rtsp_path so they
  are always consistent with the URL FFmpeg actually pushes to.
• mediamtx_cfg.py companion fix: spath = cfg.rtsp_path (no "~all" fallback needed
  because rtsp_path is always non-empty).

Kept from new version
─────────────────────
• WEEKDAY_MAP import + _int_weekdays() for robust weekday normalisation
• clear_error() helper on StreamState
• OneShotEvent.post_action has a default value of "" (backward-compatible)
• All compliance fields, folder_source, initial_offset retained
"""
from __future__ import annotations

import threading
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
    post_action: str  = ""      # default "" makes it optional (was required in v5)
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
    folder_source:  Optional[Path] = None
    compliance_enabled: bool = False
    compliance_start:   str  = "06:00:00"
    compliance_loop:    bool = False

    # ── Weekday helpers ───────────────────────────────────────────────────────

    def _int_weekdays(self) -> List[int]:
        """
        Always return weekdays as List[int] regardless of stored format.
        Handles legacy str abbreviations ("mon", "tue" …) transparently.
        """
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

        • If stream_path is configured (e.g. "news") → returns "news"
          (leading/trailing slashes stripped so the caller never gets "//news").
        • If stream_path is empty / unset → returns "stream" (legacy default).

        This value is used verbatim in the FFmpeg push URL:
            rtsp://127.0.0.1:<port>/<rtsp_path>
        and in the MediaMTX YAML paths block:
            paths:
              <rtsp_path>: {}

        IMPORTANT: do NOT return "" here.  worker.py line 774 inlines this
        directly into the FFmpeg command.  An empty string produces
        rtsp://127.0.0.1:<port>/  which MediaMTX v1.9.1 does not accept
        reliably (its ~all wildcard does not catch the bare root path).
        """
        if self.stream_path:
            return self.stream_path.strip("/")
        return "stream"

    @property
    def rtsp_url(self) -> str:
        """Internal RTSP URL (loopback) — what FFmpeg pushes to."""
        return f"rtsp://127.0.0.1:{self.port}/{self.rtsp_path}"

    @property
    def rtsp_url_external(self) -> str:
        """External RTSP URL shown to the operator / web UI."""
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
    mtx_proc:         object                     = None   # subprocess.Popen
    ffmpeg_proc:      object                     = None   # subprocess.Popen
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

    def log_add(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.log.append(f"[{ts}] {msg}")
            if len(self.log) > 400:
                self.log.pop(0)

    def clear_error(self) -> None:
        """Reset error state and auto-restart counter (e.g. after operator intervention)."""
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
