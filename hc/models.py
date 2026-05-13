"""
hc/models.py  —  Core dataclasses and enums.
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
    post_action: str  = ""
    played:      bool = False
    start_pos:   str  = "00:00:00"


@dataclass
class PlaylistItem:
    file_path:      Path
    start_position: str = "00:00:00"
    weight:         int = 1
    priority:       int = 999


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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _int_weekdays(self) -> List[int]:
        """
        Always return weekdays as List[int] regardless of how they are stored.
        Handles legacy str abbreviations (e.g. "mon") transparently.
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
        """Stream path segment; empty string means root mount (rtsp://ip:port/)."""
        return self.stream_path.strip("/") if self.stream_path else ""

    @property
    def rtsp_url(self) -> str:
        path = f"/{self.rtsp_path}" if self.rtsp_path else ""
        return f"rtsp://127.0.0.1:{self.port}{path}"

    @property
    def rtsp_url_external(self) -> str:
        from hc.utils import _local_ip
        ip = LISTEN_ADDR() if LISTEN_ADDR() != "0.0.0.0" else _local_ip()
        path = f"/{self.rtsp_path}" if self.rtsp_path else ""
        return f"rtsp://{ip}:{self.port}{path}"

    @property
    def hls_port(self) -> int:
        return self.port + 10000

    @property
    def hls_url(self) -> str:
        from hc.utils import _local_ip
        ip = LISTEN_ADDR() if LISTEN_ADDR() != "0.0.0.0" else _local_ip()
        path = f"/{self.rtsp_path}" if self.rtsp_path else ""
        return f"http://{ip}:{self.hls_port}{path}/index.m3u8"

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
