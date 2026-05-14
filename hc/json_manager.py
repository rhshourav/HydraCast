"""
hc/json_manager.py  —  Replaces csv_manager.py entirely.

v6.1 additions vs v6.0
───────────────────────
• compliance_alert_enabled serialised/deserialised (default True).

v6.0 fixes (kept)
─────────────────
• _config_dir() uses CONFIG_DIR() (→ <base>/config/).
• load() returns [] on first run.
• weekdays always normalised to List[int].
• compliance_loop default fixed to False.
• stream_path defaults to "".
"""
from __future__ import annotations

import json
import logging
import re as _re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hc.constants import CONFIG_DIR, WEEKDAY_MAP
from hc.folder_scanner import SortMode, scan_folder
from hc.models import OneShotEvent, PlaylistItem, StreamConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config-directory helpers
# ---------------------------------------------------------------------------

def _config_dir() -> Path:
    d = CONFIG_DIR()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _streams_path() -> Path:
    return _config_dir() / "streams.json"


def _events_path() -> Path:
    return _config_dir() / "events.json"


# ---------------------------------------------------------------------------
# JSON Manager
# ---------------------------------------------------------------------------

class JSONManager:
    """Handles loading/saving StreamConfig and OneShotEvent lists to JSON."""

    @classmethod
    def load(cls) -> List[StreamConfig]:
        p = _streams_path()
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return [cls._to_config(d) for d in data]
        except Exception as exc:
            log.error("Failed to load streams.json: %s", exc)
            return []

    @classmethod
    def save(cls, configs: List[StreamConfig]) -> None:
        p = _streams_path()
        data = [cls._from_config(c) for c in configs]
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def _to_config(cls, d: Dict[str, Any]) -> StreamConfig:
        # Default playlist setup
        playlist_raw = d.get("playlist", [])
        playlist = [
            PlaylistItem(
                file_path=Path(item["file_path"]),
                duration=item.get("duration", 0.0)
            ) for item in playlist_raw
        ]

        # Normalise weekdays to List[int]
        wd = d.get("weekdays", [0,1,2,3,4,5,6])
        if isinstance(wd, str):
            # parse "0,1,2" or "mon,tue"
            wd_list = []
            for part in _re.split(r"[,\s]+", wd.lower()):
                if part.isdigit():
                    wd_list.append(int(part))
                elif part in WEEKDAY_MAP:
                    wd_list.append(WEEKDAY_MAP[part])
            wd = sorted(list(set(wd_list)))

        return StreamConfig(
            name                     = d.get("name", "Unnamed"),
            stream_path              = d.get("stream_path", ""),
            folder_source            = Path(d["folder_source"]) if d.get("folder_source") else None,
            sort_mode                = SortMode(d.get("sort_mode", "name_asc")),
            playlist                 = playlist,
            shuffle                  = d.get("shuffle", False),
            loop                     = d.get("loop", True),
            rtsp_port                = d.get("rtsp_port", 8554),
            rtp_port_base            = d.get("rtp_port_base", 8000),
            hls_enabled              = d.get("hls_enabled", False),
            compliance_enabled       = d.get("compliance_enabled", False),
            compliance_loop          = d.get("compliance_loop", False),
            compliance_alert_enabled = d.get("compliance_alert_enabled", True),
            weekdays                 = wd,
        )

    @classmethod
    def _from_config(cls, c: StreamConfig) -> Dict[str, Any]:
        return {
            "name":                     c.name,
            "stream_path":              c.stream_path,
            "folder_source":            str(c.folder_source) if c.folder_source else "",
            "sort_mode":                c.sort_mode.value,
            "shuffle":                  c.shuffle,
            "loop":                     c.loop,
            "rtsp_port":                c.rtsp_port,
            "rtp_port_base":            c.rtp_port_base,
            "hls_enabled":              c.hls_enabled,
            "compliance_enabled":       c.compliance_enabled,
            "compliance_loop":          c.compliance_loop,
            "compliance_alert_enabled": c.compliance_alert_enabled,
            "weekdays":                 c.weekdays,
            "playlist": [
                {"file_path": str(item.file_path), "duration": item.duration}
                for item in c.playlist
            ],
        }

    # ── Events ────────────────────────────────────────────────────────────────

    @classmethod
    def load_events(cls) -> List[OneShotEvent]:
        p = _events_path()
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            events = []
            for d in data:
                try:
                    be_str = d.get("broadcast_end")
                    ev = OneShotEvent(
                        event_id    = d.get("event_id", str(uuid.uuid4())),
                        stream_name = d["stream_name"],
                        file_path   = Path(d["file_path"]),
                        play_at     = datetime.fromisoformat(d["play_at"]),
                        played      = d.get("played", False),
                        loop_count  = d.get("loop_count", 0),
                        broadcast_end = datetime.fromisoformat(be_str) if be_str else None
                    )
                    events.append(ev)
                except (KeyError, ValueError):
                    continue
            return events
        except Exception as exc:
            log.error("Failed to load events.json: %s", exc)
            return []

    @classmethod
    def save_events(cls, events: List[OneShotEvent]) -> None:
        cls._save_events(events)

    @classmethod
    def _save_events(cls, events: List[OneShotEvent]) -> None:
        p = _events_path()
        data = []
        # Only persist events that are in the future OR were played recently 
        # (e.g. within the last hour) to keep the file clean.
        now = datetime.now().timestamp()
        for ev in events:
            # If it's a one-off that already played long ago, skip it
            if ev.played and (now - ev.play_at.timestamp()) > 3600:
                continue
            
            d = {
                "event_id":    ev.event_id,
                "stream_name": ev.stream_name,
                "file_path":   str(ev.file_path),
                "play_at":     ev.play_at.isoformat(),
                "played":      ev.played,
                "loop_count":  getattr(ev, "loop_count", 0),
            }
            # broadcast_end is optional; persist only when present
            be = getattr(ev, "broadcast_end", None)
            if be is not None:
                d["broadcast_end"] = be.isoformat()
            data.append(d)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def mark_event_played(cls, events: List[OneShotEvent], event_id: str) -> None:
        for ev in events:
            if ev.event_id == event_id:
                ev.played = True
                break
        cls._save_events(events)

    @classmethod
    def add_event(
        cls,
        events: List[OneShotEvent],
        stream_name: str,
        file_path: Path,
        play_at: datetime,
        broadcast_end: Optional[datetime] = None,
        loop_count: int = 0,
    ) -> OneShotEvent:
        ev = OneShotEvent(
            event_id    = str(uuid.uuid4()),
            stream_name = stream_name,
            file_path   = file_path,
            play_at     = play_at,
            played      = False,
            loop_count  = loop_count,
        )
        if broadcast_end is not None:
            ev.broadcast_end = broadcast_end
        events.append(ev)
        cls._save_events(events)
        return ev
