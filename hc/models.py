"""
hc/models.py  —  Core dataclasses and enums.

Changes vs v5.0.0:
  • StreamConfig: three new compliance fields (compliance_enabled,
    compliance_start, compliance_loop).
  • StreamState:  initial_offset field for per-start ±offset feature.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from hc.constants import DAY_ABBR, LISTEN_ADDR


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

    # ── Folder-source tracking ───────────────────────────────────────────────
    # Set when the CSV entry points to a directory.  Preserved across restarts
    # so the folder is always re-scanned for new/removed files on every start.
    folder_source: Optional[Path] = None

    # ── Compliance / broadcast-sync fields ────────────────────────────────────
    # When compliance_enabled is True the stream calculates the correct seek
    # offset so it matches a continuous linear broadcast that started at
    # compliance_start each day.
    compliance_enabled: bool = False
    compliance_start:   str  = "06:00:00"   # HH:MM:SS wall-clock broadcast start
    compliance_loop:    bool = False         # seek within loops for short videos

    # ── Derived properties ────────────────────────────────────────────────────
    @property
    def rtsp_path(self) -> str:
        """Return the stream path segment, or empty string if none (root mount)."""
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

    def is_scheduled_today(self) -> bool:
        return datetime.now().weekday() in self.weekdays

    def weekdays_display(self) -> str:
        if set(self.weekdays) == set(range(7)):  return "ALL"
        if set(self.weekdays) == set(range(5)):  return "Weekdays"
        if set(self.weekdays) == {5, 6}:         return "Weekends"
        return "|".join(DAY_ABBR[d] for d in sorted(self.weekdays))

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
    # Per-start ±time offset applied once at the very next start (cleared after use)
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
        """Returns remaining seconds; 0 if duration unknown."""
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
