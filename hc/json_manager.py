"""
hc/json_manager.py  —  Replaces csv_manager.py entirely.

All persistent configuration is stored as JSON files inside the /config/
directory (resolved relative to the HydraCast base directory):

    config/streams.json   — stream definitions  (was streams.csv)
    config/events.json    — one-shot events      (was events.csv)

The public API is intentionally identical to the old CSVManager so that every
call-site in manager.py / hydracast.py only needs its import line updated.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hc.constants import CONFIGS_DIR
from hc.folder_scanner import SortMode, scan_folder
from hc.models import OneShotEvent, PlaylistItem, StreamConfig

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config-directory helpers
# ---------------------------------------------------------------------------

def _config_dir() -> Path:
    """
    Return (and create if absent) the /config sub-directory that lives next to
    the hc package.  CONFIGS_DIR() points to  <base>/config/  which already
    stores the per-stream MediaMTX YAML fragments, so we reuse the same root
    but keep our JSON files at the top level of that directory.
    """
    d = CONFIGS_DIR()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _streams_path() -> Path:
    return _config_dir() / "streams.json"


def _events_path() -> Path:
    return _config_dir() / "events.json"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _playlist_to_json(items: List[PlaylistItem]) -> List[Dict[str, Any]]:
    return [
        {
            "file_path":      str(item.file_path),
            "start_position": item.start_position,
            "priority":       item.priority,
        }
        for item in items
    ]


def _playlist_from_json(raw: List[Dict[str, Any]]) -> List[PlaylistItem]:
    out: List[PlaylistItem] = []
    for r in raw:
        try:
            out.append(
                PlaylistItem(
                    file_path=Path(r["file_path"]),
                    start_position=r.get("start_position", "00:00:00"),
                    priority=int(r.get("priority", 0)),
                )
            )
        except Exception as exc:
            log.warning("json_manager: skipping bad playlist entry %s — %s", r, exc)
    return out


def _config_to_dict(cfg: StreamConfig) -> Dict[str, Any]:
    return {
        "name":               cfg.name,
        "port":               cfg.port,
        "stream_path":        cfg.stream_path,
        "enabled":            cfg.enabled,
        "weekdays":           cfg.weekdays,          # e.g. ["mon","wed","fri"]
        "shuffle":            cfg.shuffle,
        "video_bitrate":      cfg.video_bitrate,
        "audio_bitrate":      cfg.audio_bitrate,
        "hls_enabled":        cfg.hls_enabled,
        "compliance_enabled": cfg.compliance_enabled,
        "compliance_start":   cfg.compliance_start,
        "compliance_loop":    cfg.compliance_loop,
        "folder_source":      str(cfg.folder_source) if cfg.folder_source else None,
        # Inline playlist only when there is no folder_source.
        "playlist":           (
            _playlist_to_json(cfg.playlist) if not cfg.folder_source else []
        ),
    }


def _config_from_dict(d: Dict[str, Any]) -> Optional[StreamConfig]:
    try:
        folder_source: Optional[Path] = None
        playlist:      List[PlaylistItem] = []

        if d.get("folder_source"):
            folder_source = Path(d["folder_source"])
            # Scan the folder immediately so the playlist is populated on load.
            items, warnings = scan_folder(folder_source, SortMode.ALPHA_FWD)
            for w in warnings:
                log.warning("json_manager: %s", w)
            playlist = items
        elif d.get("playlist"):
            playlist = _playlist_from_json(d["playlist"])

        return StreamConfig(
            name               = d["name"],
            port               = int(d["port"]),
            stream_path        = d.get("stream_path", d["name"]),
            enabled            = bool(d.get("enabled", True)),
            weekdays           = d.get("weekdays", []),
            shuffle            = bool(d.get("shuffle", False)),
            video_bitrate      = d.get("video_bitrate", "2000k"),
            audio_bitrate      = d.get("audio_bitrate", "128k"),
            hls_enabled        = bool(d.get("hls_enabled", False)),
            compliance_enabled = bool(d.get("compliance_enabled", False)),
            compliance_start   = d.get("compliance_start", "00:00:00"),
            compliance_loop    = d.get("compliance_loop", ""),
            folder_source      = folder_source,
            playlist           = playlist,
        )
    except Exception as exc:
        log.error("json_manager: cannot parse stream entry %s — %s", d.get("name", "?"), exc)
        return None


# ---------------------------------------------------------------------------
# Public API  (drop-in replacement for CSVManager)
# ---------------------------------------------------------------------------

class JSONManager:
    """
    Static helper class — all methods are classmethods so call-sites need no
    instance:  JSONManager.load(),  JSONManager.save(configs), …
    """

    # ── Streams ───────────────────────────────────────────────────────────────

    @classmethod
    def load(cls) -> List[StreamConfig]:
        """
        Load stream configurations from  config/streams.json.

        Raises FileNotFoundError when the file does not exist yet (first run),
        so the caller can show a friendly "no config" message.
        """
        p = _streams_path()
        if not p.exists():
            raise FileNotFoundError(
                f"No streams configuration found at '{p}'.\n"
                "Open the Web UI → Configure tab to create your first stream,\n"
                "or copy an existing streams.json into the config/ directory."
            )

        try:
            raw: List[Dict[str, Any]] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"streams.json is not valid JSON: {exc}") from exc

        configs: List[StreamConfig] = []
        for entry in raw:
            cfg = _config_from_dict(entry)
            if cfg is not None:
                configs.append(cfg)

        log.info("json_manager: loaded %d stream(s) from '%s'", len(configs), p)
        return configs

    @classmethod
    def save(cls, configs: List[StreamConfig]) -> None:
        """Persist *configs* to  config/streams.json  (pretty-printed)."""
        p = _streams_path()
        data = [_config_to_dict(c) for c in configs]
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("json_manager: saved %d stream(s) to '%s'", len(configs), p)

    # ── One-shot events ───────────────────────────────────────────────────────

    @classmethod
    def load_events(cls) -> List[OneShotEvent]:
        """Load one-shot events from  config/events.json.  Returns [] if absent."""
        p = _events_path()
        if not p.exists():
            return []

        try:
            raw: List[Dict[str, Any]] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.error("json_manager: events.json is not valid JSON: %s", exc)
            return []

        events: List[OneShotEvent] = []
        for r in raw:
            try:
                events.append(
                    OneShotEvent(
                        event_id    = r["event_id"],
                        stream_name = r["stream_name"],
                        file_path   = Path(r["file_path"]),
                        play_at     = datetime.fromisoformat(r["play_at"]),
                        played      = bool(r.get("played", False)),
                    )
                )
            except Exception as exc:
                log.warning("json_manager: skipping bad event entry %s — %s", r, exc)

        return events

    @classmethod
    def _save_events(cls, events: List[OneShotEvent]) -> None:
        p = _events_path()
        data = [
            {
                "event_id":    ev.event_id,
                "stream_name": ev.stream_name,
                "file_path":   str(ev.file_path),
                "play_at":     ev.play_at.isoformat(),
                "played":      ev.played,
            }
            for ev in events
        ]
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def mark_event_played(cls, events: List[OneShotEvent], event_id: str) -> None:
        """Mark *event_id* as played in both memory and  config/events.json."""
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
    ) -> OneShotEvent:
        """Create a new one-shot event, append it, and persist."""
        ev = OneShotEvent(
            event_id    = str(uuid.uuid4()),
            stream_name = stream_name,
            file_path   = file_path,
            play_at     = play_at,
            played      = False,
        )
        events.append(ev)
        cls._save_events(events)
        return ev
