"""
hc/json_manager.py  —  Replaces csv_manager.py entirely.

All persistent configuration is stored as JSON files inside the /config/
directory (resolved relative to the HydraCast base directory):

    config/streams.json   — stream definitions  (was streams.csv)
    config/events.json    — one-shot events      (was events.csv)

Fixes vs original
─────────────────
• _config_dir() uses CONFIG_DIR() (→ <base>/config/) not CONFIGS_DIR()
  (→ <base>/configs/ — the MediaMTX YAML folder).
• load() returns [] on first run instead of raising FileNotFoundError.
• weekdays always normalised to List[int] (0=Mon…6=Sun).
• compliance_loop default fixed from "" to False.
• stream_path defaults to "" so root-mount streams work correctly.
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
    """
    Return (and create if absent) <base>/config/ — user-facing JSON files.
    NOTE: CONFIGS_DIR() points to <base>/configs/ (MediaMTX YAMLs) — different!
    """
    d = CONFIG_DIR()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _streams_path() -> Path:
    return _config_dir() / "streams.json"


def _events_path() -> Path:
    return _config_dir() / "events.json"


# ---------------------------------------------------------------------------
# Weekday normalisation
# ---------------------------------------------------------------------------

def _normalise_weekdays(raw) -> List[int]:
    """
    Accept weekdays in any form; always return List[int] (0=Mon...6=Sun).
      List[int]  -> unchanged
      List[str]  -> ["mon","wed"] -> [0, 2]
      str        -> "mon|wed" / "all" / "weekdays" / "weekends"
      empty/None -> all 7 days
    """
    if not raw and raw != 0:
        return list(range(7))

    if isinstance(raw, list):
        result: List[int] = []
        for item in raw:
            if isinstance(item, int):
                result.append(item)
            else:
                key = str(item).strip().lower()
                val = WEEKDAY_MAP.get(key)
                if isinstance(val, list):
                    result.extend(val)
                elif isinstance(val, int):
                    result.append(val)
        seen: set = set()
        return [x for x in result if not (x in seen or seen.add(x))]

    raw_s = str(raw).strip().lower()
    if raw_s in ("all", "everyday", ""):
        return list(range(7))
    if raw_s == "weekdays":
        return list(range(5))
    if raw_s == "weekends":
        return [5, 6]

    result2: List[int] = []
    for part in _re.split(r"[|,\s]+", raw_s):
        part = part.strip()
        val = WEEKDAY_MAP.get(part)
        if isinstance(val, list):
            result2.extend(val)
        elif isinstance(val, int):
            result2.append(val)
    seen2: set = set()
    deduped = [x for x in result2 if not (x in seen2 or seen2.add(x))]
    return deduped if deduped else list(range(7))


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
        "stream_path":        cfg.stream_path or "",
        "enabled":            cfg.enabled,
        "weekdays":           _normalise_weekdays(cfg.weekdays),
        "shuffle":            cfg.shuffle,
        "video_bitrate":      cfg.video_bitrate,
        "audio_bitrate":      cfg.audio_bitrate,
        "hls_enabled":        cfg.hls_enabled,
        "compliance_enabled": cfg.compliance_enabled,
        "compliance_start":   cfg.compliance_start,
        "compliance_loop":    bool(cfg.compliance_loop),
        "folder_source":      str(cfg.folder_source) if cfg.folder_source else None,
        "playlist": (
            _playlist_to_json(cfg.playlist) if not cfg.folder_source else []
        ),
    }


def _config_from_dict(d: Dict[str, Any]) -> Optional[StreamConfig]:
    try:
        folder_source: Optional[Path] = None
        playlist: List[PlaylistItem] = []

        if d.get("folder_source"):
            folder_source = Path(d["folder_source"])
            items, warnings = scan_folder(folder_source, SortMode.ALPHA_FWD)
            for w in warnings:
                log.warning("json_manager: %s", w)
            playlist = items
        elif d.get("playlist"):
            playlist = _playlist_from_json(d["playlist"])

        raw_loop = d.get("compliance_loop", False)
        compliance_loop = bool(raw_loop) if raw_loop != "" else False

        return StreamConfig(
            name               = d["name"],
            port               = int(d["port"]),
            stream_path        = d.get("stream_path", "") or "",
            enabled            = bool(d.get("enabled", True)),
            weekdays           = _normalise_weekdays(d.get("weekdays", [])),
            shuffle            = bool(d.get("shuffle", False)),
            video_bitrate      = d.get("video_bitrate", "2500k"),
            audio_bitrate      = d.get("audio_bitrate", "128k"),
            hls_enabled        = bool(d.get("hls_enabled", False)),
            compliance_enabled = bool(d.get("compliance_enabled", False)),
            compliance_start   = d.get("compliance_start", "06:00:00"),
            compliance_loop    = compliance_loop,
            folder_source      = folder_source,
            playlist           = playlist,
        )
    except Exception as exc:
        log.error(
            "json_manager: cannot parse stream entry %s — %s",
            d.get("name", "?"), exc,
        )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class JSONManager:

    @classmethod
    def load(cls) -> List[StreamConfig]:
        """
        Load stream configs from config/streams.json.
        Returns [] on first run (no file yet) so the app starts in web-only mode.
        """
        p = _streams_path()
        if not p.exists():
            log.info("json_manager: no streams.json yet — starting with empty config.")
            return []

        try:
            text = p.read_text(encoding="utf-8").strip()
            if not text:
                # File exists but is empty — likely a crash-truncated write.
                # Rename it so the user keeps a copy, then start fresh.
                _backup = p.with_suffix(".json.bak")
                try:
                    p.rename(_backup)
                except Exception:
                    p.unlink(missing_ok=True)
                log.warning(
                    "json_manager: streams.json was empty (crash-truncated?). "
                    "Renamed to streams.json.bak and starting with empty config."
                )
                return []
            raw: List[Dict[str, Any]] = json.loads(text)
        except json.JSONDecodeError as exc:
            # File is non-empty but not valid JSON — back it up and continue.
            _backup = p.with_suffix(".json.bak")
            try:
                p.rename(_backup)
            except Exception:
                p.unlink(missing_ok=True)
            log.warning(
                "json_manager: streams.json contained invalid JSON (%s). "
                "Renamed to streams.json.bak and starting with empty config.",
                exc,
            )
            return []

        configs: List[StreamConfig] = []
        for entry in raw:
            cfg = _config_from_dict(entry)
            if cfg is not None:
                configs.append(cfg)

        log.info("json_manager: loaded %d stream(s) from '%s'", len(configs), p)
        return configs

    @classmethod
    def save(cls, configs: List[StreamConfig]) -> None:
        p = _streams_path()
        data = [_config_to_dict(c) for c in configs]
        text = json.dumps(data, indent=2, ensure_ascii=False)
        # Atomic write: write to a sibling temp file then rename so a crash
        # mid-write never leaves streams.json empty or partially written.
        tmp = p.with_suffix(".json.tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(p)          # atomic on POSIX; near-atomic on Windows
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        log.info("json_manager: saved %d stream(s) to '%s'", len(configs), p)

    @classmethod
    def load_events(cls) -> List[OneShotEvent]:
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
                log.warning("json_manager: skipping bad event %s — %s", r, exc)
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
