"""
hc/csv_manager.py  —  Load / save streams (JSON) and events (JSON).

v6.0 changes
────────────
• All config lives under  <base>/config/
    streams → config/streams.json   (was streams.json beside the script)
    events  → config/events.json    (was events.csv — now fully JSON)
• Class renamed to ConfigManager; CSVManager is kept as an alias so
  existing call-sites in manager.py / web.py / hydracast.py need no changes.
• One-shot legacy migrations:
    streams.csv          → config/streams.json
    streams.json (root)  → config/streams.json
    events.csv           → config/events.json

Why JSON for events?
────────────────────
CSV rows break when file_path contains commas or semicolons.
JSON carries all fields as typed values — no delimiter collisions and no
custom escaping needed.

JSON event format (array of objects):
  [
    {
      "event_id":    "uuid-...",
      "stream_name": "Stream_1",
      "file_path":   "/media/clip.mp4",
      "play_at":     "2024-06-01 10:00:00",
      "post_action": "resume",
      "start_pos":   "00:00:00",
      "played":      false
    },
    ...
  ]
"""
from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from hc.constants import (
    CONFIG_DIR, CSV_FILE, EVENTS_CSV, EVENTS_FILE, STREAMS_JSON,
    WEEKDAY_MAP,
)
from hc.models import OneShotEvent, PlaylistItem, StreamConfig


# ── JSON template written when no config file exists ──────────────────────────
_JSON_TEMPLATE: List[dict] = [
    {
        "stream_name": "Stream_1",
        "port": 8554,
        "files": "/path/to/video.mp4@00:00:00#1",
        "weekdays": "ALL",
        "enabled": True,
        "shuffle": False,
        "stream_path": "stream",
        "video_bitrate": "2500k",
        "audio_bitrate": "128k",
        "hls_enabled": False,
        "compliance_enabled": False,
        "compliance_start": "06:00:00",
        "compliance_loop": False,
    },
    {
        "stream_name": "Stream_2",
        "port": 8564,
        "files": "/path/to/a.mp4@00:05:00#1;/path/to/b.mkv@00:00:00#2",
        "weekdays": "Mon|Wed|Fri",
        "enabled": True,
        "shuffle": False,
        "stream_path": "ch2",
        "video_bitrate": "4000k",
        "audio_bitrate": "192k",
        "hls_enabled": False,
        "compliance_enabled": False,
        "compliance_start": "06:00:00",
        "compliance_loop": False,
    },
]


class ConfigManager:
    """
    Manages persistent configuration for HydraCast.

    All files live under  <base>/config/:
      • config/streams.json  — stream definitions
      • config/events.json   — one-shot scheduled events

    Legacy migration (runs once, silently):
      • <base>/streams.csv       → config/streams.json
      • <base>/streams.json      → config/streams.json   (old root location)
      • <base>/events.csv        → config/events.json
    """

    # ── Template ──────────────────────────────────────────────────────────────
    @staticmethod
    def create_template() -> None:
        dst = STREAMS_JSON()
        dst.write_text(
            json.dumps(_JSON_TEMPLATE, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Parsers ───────────────────────────────────────────────────────────────
    @staticmethod
    def parse_weekdays(raw: str) -> List[int]:
        result: set = set()
        for part in re.split(r"[|,;/\s]+", raw.strip()):
            part = part.strip().lower()
            val = WEEKDAY_MAP.get(part)
            if val is None:
                continue
            if isinstance(val, list):
                result.update(val)
            else:
                result.add(val)
        return sorted(result) if result else list(range(7))

    @staticmethod
    def parse_bool(raw) -> bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("true", "1", "yes", "on", "enabled")

    @staticmethod
    def normalize_position(pos: str) -> str:
        try:
            parts = pos.strip().split(":")
            if len(parts) == 1:   parts = ["00", "00", parts[0]]
            elif len(parts) == 2: parts = ["00"] + parts
            h, m, s = parts
            return f"{int(h):02d}:{int(m):02d}:{int(float(s)):02d}"
        except Exception:
            return "00:00:00"

    @staticmethod
    def _sanitize_bitrate(raw: str, default: str) -> str:
        raw = str(raw).strip()
        return raw.lower() if re.fullmatch(r"\d+[kKmM]?", raw) else default

    @staticmethod
    def _sanitize_hms(raw: str) -> str:
        """Validate HH:MM:SS string; return '06:00:00' if invalid."""
        raw = str(raw).strip()
        if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", raw):
            parts = raw.split(":")
            if len(parts) == 2:
                raw = raw + ":00"
            return raw
        return "06:00:00"

    @staticmethod
    def parse_files(raw: str) -> List[PlaylistItem]:
        """
        Format: path@HH:MM:SS#priority;path@HH:MM:SS#priority …
        Priority (#N) is optional, defaults to 999.
        A bare directory path (no @ or #) is also accepted — folder-source
        detection is handled downstream in load().
        """
        items: List[PlaylistItem] = []
        for part in re.split(r"[;\n]+", raw):
            part = part.strip()
            if not part:
                continue
            priority = 999
            if "#" in part:
                hsh = part.rfind("#")
                at  = part.rfind("@")
                if hsh > at:
                    try:
                        priority = int(part[hsh + 1:].strip())
                    except ValueError:
                        pass
                    part = part[:hsh].strip()
            if "@" in part:
                path_str, pos = part.rsplit("@", 1)
                path_str = path_str.strip()
                pos      = pos.strip()
            else:
                path_str = part
                pos      = "00:00:00"
            try:
                p = pos.split(":")
                if len(p) == 1:   p = ["00", "00", p[0]]
                elif len(p) == 2: p = ["00"] + p
                h, m, s = p
                pos = f"{int(h):02d}:{int(m):02d}:{int(float(s)):02d}"
            except Exception:
                pos = "00:00:00"
            raw_p = Path(path_str)
            if not raw_p.is_absolute():
                try:
                    from hc.constants import MEDIA_DIR
                    candidate = MEDIA_DIR() / raw_p
                    if candidate.exists():
                        raw_p = candidate
                except Exception:
                    pass
            items.append(PlaylistItem(
                file_path=raw_p,
                start_position=pos,
                priority=priority,
            ))
        return items

    # ── Folder-source detection ───────────────────────────────────────────────
    @staticmethod
    def _resolve_folder_source(config: StreamConfig) -> None:
        folder: Path | None = None
        for item in config.playlist:
            if item.file_path.is_dir():
                folder = item.file_path
                break

        if folder is None:
            return

        config.folder_source = folder
        try:
            from hc.folder_scanner import scan_folder
            items, warnings = scan_folder(folder)
            if items:
                config.playlist = items
                logging.info(
                    "JSON [%s]: folder-source '%s' → %d file(s) (today's + untagged)",
                    config.name, folder.name, len(items),
                )
            else:
                logging.warning(
                    "JSON [%s]: folder-source '%s' is empty or has no supported files.",
                    config.name, folder,
                )
            for w in warnings:
                logging.warning("JSON [%s]: %s", config.name, w)
        except Exception as exc:
            logging.error(
                "JSON [%s]: folder scan failed for '%s': %s",
                config.name, folder, exc,
            )

    # ── Migration helpers ─────────────────────────────────────────────────────
    @classmethod
    def _migrate_streams_to_config(cls) -> bool:
        """
        Look for streams config in legacy locations (root streams.csv or root
        streams.json) and migrate to config/streams.json.
        Returns True if a migration was performed.
        """
        dst = STREAMS_JSON()
        if dst.exists():
            return False  # already in the right place

        # Try root streams.json first (intermediate location from v5.x)
        root_json = CSV_FILE().with_name("streams.json")
        if root_json.exists():
            try:
                dst.write_bytes(root_json.read_bytes())
                bak = root_json.with_suffix(".json.bak")
                root_json.rename(bak)
                logging.info(
                    "Migrated streams.json (root) → config/streams.json. "
                    "Old file renamed to %s", bak.name,
                )
                return True
            except Exception as exc:
                logging.error("streams.json (root) → config/ migration failed: %s", exc)

        # Fallback: try legacy streams.csv
        old_csv = CSV_FILE()
        if old_csv.exists():
            try:
                rows: List[dict] = []
                with open(old_csv, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        name = row.get("stream_name", "").strip()
                        if not name:
                            continue
                        rows.append({
                            "stream_name":       name,
                            "port":              int(row.get("port", "8554").strip()),
                            "files":             row.get("files", "").strip(),
                            "weekdays":          row.get("weekdays", "ALL").strip(),
                            "enabled":           row.get("enabled", "true").strip().lower(),
                            "shuffle":           row.get("shuffle", "false").strip().lower(),
                            "stream_path":       row.get("stream_path", "stream").strip() or "stream",
                            "video_bitrate":     row.get("video_bitrate", "2500k").strip(),
                            "audio_bitrate":     row.get("audio_bitrate", "128k").strip(),
                            "hls_enabled":       row.get("hls_enabled", "false").strip().lower(),
                            "compliance_enabled": row.get("compliance_enabled", "false").strip().lower(),
                            "compliance_start":  row.get("compliance_start", "06:00:00").strip(),
                            "compliance_loop":   row.get("compliance_loop", "false").strip().lower(),
                        })
                dst.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
                bak = old_csv.with_suffix(".csv.bak")
                old_csv.rename(bak)
                logging.info(
                    "Migrated streams.csv → config/streams.json (%d stream(s)). "
                    "Old file renamed to %s", len(rows), bak.name,
                )
                return True
            except Exception as exc:
                logging.error("streams.csv → config/ migration failed: %s", exc)

        return False

    @classmethod
    def _migrate_events_to_json(cls) -> bool:
        """
        Migrate events.csv (root) → config/events.json if needed.
        Returns True if a migration was performed.
        """
        dst = EVENTS_FILE()
        if dst.exists():
            return False

        old_csv = EVENTS_CSV()
        if not old_csv.exists():
            return False

        try:
            events: List[dict] = []
            with open(old_csv, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        events.append({
                            "event_id":    row.get("event_id", "").strip(),
                            "stream_name": row.get("stream_name", "").strip(),
                            "file_path":   row.get("file_path", "").strip(),
                            "play_at":     row.get("play_at", "").strip(),
                            "post_action": row.get("post_action", "resume").strip(),
                            "start_pos":   row.get("start_pos", "00:00:00").strip(),
                            "played":      row.get("played", "false").strip().lower() in ("true", "1"),
                        })
                    except Exception as exc:
                        logging.warning("events.csv migration: skipping row: %s", exc)
            dst.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
            bak = old_csv.with_suffix(".csv.bak")
            old_csv.rename(bak)
            logging.info(
                "Migrated events.csv → config/events.json (%d event(s)). "
                "Old file renamed to %s", len(events), bak.name,
            )
            return True
        except Exception as exc:
            logging.error("events.csv → config/events.json migration failed: %s", exc)
            return False

    # ── Load / save streams ───────────────────────────────────────────────────
    @classmethod
    def load(cls) -> List[StreamConfig]:
        dst = STREAMS_JSON()

        # Auto-migrate from any legacy location.
        if not dst.exists():
            cls._migrate_streams_to_config()

        if not dst.exists():
            cls.create_template()
            raise FileNotFoundError(
                f"config/streams.json not found → template created at:\n  {dst}\n"
                "Edit it with your stream details, then restart HydraCast."
            )

        try:
            raw_rows = json.loads(dst.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"config/streams.json is not valid JSON: {exc}") from exc

        if not isinstance(raw_rows, list):
            raise ValueError("config/streams.json must contain a JSON array at the top level.")

        configs: List[StreamConfig] = []
        errors:  List[str]          = []

        for i, row in enumerate(raw_rows, start=1):
            name = str(row.get("stream_name", "")).strip()
            if not name:
                errors.append(f"Entry {i}: empty stream_name — skipped.")
                continue
            try:
                port = int(row.get("port", 0))
                if not (1024 <= port <= 65535):
                    raise ValueError("out of range")
            except Exception:
                errors.append(f"Entry {i} ({name}): invalid port — skipped.")
                continue

            playlist = cls.parse_files(str(row.get("files", "")).strip())
            if not playlist:
                errors.append(f"Entry {i} ({name}): no files — skipped.")
                continue

            weekdays = cls.parse_weekdays(str(row.get("weekdays", "ALL")))
            enabled  = cls.parse_bool(row.get("enabled", True))
            shuffle  = cls.parse_bool(row.get("shuffle", False))
            spath    = str(row.get("stream_path", "stream")).strip() or "stream"
            vid_br   = cls._sanitize_bitrate(str(row.get("video_bitrate",  "2500k")), "2500k")
            aud_br   = cls._sanitize_bitrate(str(row.get("audio_bitrate",  "128k")),  "128k")
            hls_en   = cls.parse_bool(row.get("hls_enabled", False))

            comp_en    = cls.parse_bool(row.get("compliance_enabled", False))
            comp_start = cls._sanitize_hms(str(row.get("compliance_start", "06:00:00")))
            comp_loop  = cls.parse_bool(row.get("compliance_loop", False))

            sorted_pl = sorted(playlist, key=lambda x: x.priority)
            cfg = StreamConfig(
                name=name, port=port, playlist=sorted_pl,
                weekdays=weekdays, enabled=enabled, shuffle=shuffle,
                stream_path=spath, video_bitrate=vid_br,
                audio_bitrate=aud_br, hls_enabled=hls_en,
                row_index=i - 1,
                compliance_enabled=comp_en,
                compliance_start=comp_start,
                compliance_loop=comp_loop,
            )
            cls._resolve_folder_source(cfg)
            configs.append(cfg)

        for e in errors:
            logging.warning("JSON: %s", e)

        # ── Duplicate port check ──────────────────────────────────────────────
        seen: Dict[int, str] = {}
        for c in configs:
            if c.port in seen:
                raise ValueError(
                    f"Duplicate port {c.port}: '{c.name}' and '{seen[c.port]}'."
                )
            seen[c.port] = c.name

        # ── Port-gap warning ──────────────────────────────────────────────────
        sorted_ports = sorted((c.port, c.name) for c in configs)
        for j in range(len(sorted_ports) - 1):
            p1, n1 = sorted_ports[j]
            p2, n2 = sorted_ports[j + 1]
            if p2 - p1 < 10:
                logging.warning(
                    "JSON: Ports %d (%s) and %d (%s) are only %d apart — "
                    "RTP/RTCP companion ports may collide. "
                    "Recommended gap is ≥10 (e.g. 8554, 8564, 8574 …).",
                    p1, n1, p2, n2, p2 - p1,
                )

        if not configs:
            logging.warning(
                "JSON: No valid streams in config/streams.json — "
                "starting in web-only mode. "
                "Use the Web UI → Configure tab to add streams."
            )
        return configs

    @classmethod
    def save(cls, configs: List[StreamConfig]) -> None:
        rows: List[dict] = []
        for c in configs:
            if c.folder_source and c.folder_source.is_dir():
                files_str = str(c.folder_source)
            else:
                files_str = ";".join(
                    f"{item.file_path}@{item.start_position}#{item.priority}"
                    for item in c.playlist
                )
            rows.append({
                "stream_name":        c.name,
                "port":               c.port,
                "files":              files_str,
                "weekdays":           c.weekdays_display().replace("ALL", "all"),
                "enabled":            c.enabled,
                "shuffle":            c.shuffle,
                "stream_path":        c.stream_path,
                "video_bitrate":      c.video_bitrate,
                "audio_bitrate":      c.audio_bitrate,
                "hls_enabled":        c.hls_enabled,
                "compliance_enabled": c.compliance_enabled,
                "compliance_start":   c.compliance_start,
                "compliance_loop":    c.compliance_loop,
            })
        STREAMS_JSON().write_text(
            json.dumps(rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Load / save events (now fully JSON) ───────────────────────────────────
    @classmethod
    def load_events(cls) -> List[OneShotEvent]:
        # One-shot migration from legacy events.csv if needed.
        cls._migrate_events_to_json()

        dst = EVENTS_FILE()
        if not dst.exists():
            return []

        try:
            raw = json.loads(dst.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("config/events.json load error: %s", exc)
            return []

        if not isinstance(raw, list):
            logging.warning("config/events.json: expected a JSON array — returning empty.")
            return []

        events: List[OneShotEvent] = []
        for row in raw:
            try:
                events.append(OneShotEvent(
                    event_id=str(row["event_id"]).strip(),
                    stream_name=str(row["stream_name"]).strip(),
                    file_path=Path(str(row["file_path"]).strip()),
                    play_at=datetime.strptime(
                        str(row["play_at"]).strip(), "%Y-%m-%d %H:%M:%S"),
                    post_action=str(row.get("post_action", "resume")).strip(),
                    played=bool(row.get("played", False)),
                    start_pos=str(row.get("start_pos", "00:00:00")).strip(),
                ))
            except Exception as exc:
                logging.warning("config/events.json row error: %s — row: %s", exc, row)
        return events

    @classmethod
    def save_events(cls, events: List[OneShotEvent]) -> None:
        rows = [
            {
                "event_id":    e.event_id,
                "stream_name": e.stream_name,
                "file_path":   str(e.file_path),
                "play_at":     e.play_at.strftime("%Y-%m-%d %H:%M:%S"),
                "post_action": e.post_action,
                "start_pos":   e.start_pos,
                "played":      e.played,
            }
            for e in events
        ]
        EVENTS_FILE().write_text(
            json.dumps(rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def add_event(cls, events: List[OneShotEvent], e: OneShotEvent) -> None:
        events.append(e)
        cls.save_events(events)

    @classmethod
    def mark_event_played(cls, events: List[OneShotEvent], event_id: str) -> None:
        for e in events:
            if e.event_id == event_id:
                e.played = True
        cls.save_events(events)


# ── Backward-compatible alias ─────────────────────────────────────────────────
CSVManager = ConfigManager
