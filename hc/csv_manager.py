"""
hc/csv_manager.py  —  Load / save streams.csv and events.csv.

Changes vs v5.0.0:
  • CSV_COLUMNS extended with compliance_enabled, compliance_start,
    compliance_loop (backward-compatible: old CSVs without these columns
    silently default to False / "06:00:00" / False).
  • StreamConfig.compliance_* fields are persisted in save().

v5.1 changes:
  • load() auto-detects folder sources: if a playlist item's path is a
    directory, cfg.folder_source is set and scan_folder() builds the
    initial playlist.  This means you can put a plain folder path in
    streams.csv (no @position/#priority decorators needed).
"""
from __future__ import annotations

import csv
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from hc.constants import CSV_FILE, EVENTS_FILE, WEEKDAY_MAP
from hc.models import OneShotEvent, PlaylistItem, StreamConfig

# ── Column headers ─────────────────────────────────────────────────────────────
CSV_COLUMNS = [
    "stream_name", "port", "files", "weekdays", "enabled",
    "shuffle", "stream_path", "video_bitrate", "audio_bitrate", "hls_enabled",
    # Compliance fields (optional – old CSVs without these columns are fine)
    "compliance_enabled", "compliance_start", "compliance_loop",
]

# NOTE: template ports spaced ≥ 10 apart so RTP/RTCP companion ports never collide.
CSV_TEMPLATE_ROWS = [
    ["Stream_1", "8554", "/path/to/video.mp4@00:00:00#1",
     "ALL", "true", "false", "stream", "2500k", "128k", "false",
     "false", "06:00:00", "false"],
    ["Stream_2", "8564", "/path/to/a.mp4@00:05:00#1;/path/to/b.mkv@00:00:00#2",
     "Mon|Wed|Fri", "true", "false", "ch2", "4000k", "192k", "false",
     "false", "06:00:00", "false"],
    ["Stream_3", "8574", "/media/demo.mp4@00:00:00#1",
     "Sat|Sun", "false", "true", "ch3", "1500k", "128k", "false",
     "false", "06:00:00", "false"],
    ["Stream_4", "8584", "/media/show.mp4@00:00:00#1",
     "Weekdays", "true", "false", "ch4", "2500k", "128k", "true",
     "false", "06:00:00", "false"],
    # Folder-source example — put a directory path in the files column:
    # ["Stream_5", "8594", "/media/my_shows_folder",
    #  "ALL", "true", "false", "ch5", "2500k", "128k", "false",
    #  "false", "06:00:00", "false"],
]

EVENTS_COLUMNS = ["event_id", "stream_name", "file_path", "play_at", "post_action", "start_pos"]


class CSVManager:

    # ── Template ──────────────────────────────────────────────────────────────
    @staticmethod
    def create_template() -> None:
        with open(CSV_FILE(), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_COLUMNS)
            w.writerows(CSV_TEMPLATE_ROWS)

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
    def parse_bool(raw: str) -> bool:
        return raw.strip().lower() in ("true", "1", "yes", "on", "enabled")

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
        raw = raw.strip()
        return raw.lower() if re.fullmatch(r"\d+[kKmM]?", raw) else default

    @staticmethod
    def _sanitize_hms(raw: str) -> str:
        """Validate HH:MM:SS string; return '06:00:00' if invalid."""
        raw = raw.strip()
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
            # Resolve relative paths against MEDIA_DIR.
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
        """
        If *any* playlist item points to a directory, treat the config as a
        folder-source stream:
          1. Set cfg.folder_source to that directory.
          2. Replace cfg.playlist with the result of scan_folder().
          3. Log a warning for any issues found.

        This is called once per config during load() so the worker and TUI
        see a fully populated playlist immediately at startup.
        """
        folder: Path | None = None
        for item in config.playlist:
            if item.file_path.is_dir():
                folder = item.file_path
                break

        if folder is None:
            return  # regular file-list stream — nothing to do

        config.folder_source = folder
        try:
            from hc.folder_scanner import scan_folder
            items, warnings = scan_folder(folder)
            if items:
                config.playlist = items
                logging.info(
                    "CSV [%s]: folder-source '%s' → %d file(s)",
                    config.name, folder.name, len(items),
                )
            else:
                logging.warning(
                    "CSV [%s]: folder-source '%s' is empty or has no supported files.",
                    config.name, folder,
                )
            for w in warnings:
                logging.warning("CSV [%s]: %s", config.name, w)
        except Exception as exc:
            logging.error(
                "CSV [%s]: folder scan failed for '%s': %s",
                config.name, folder, exc,
            )

    # ── Load / save streams ───────────────────────────────────────────────────
    @classmethod
    def load(cls) -> List[StreamConfig]:
        if not CSV_FILE().exists():
            cls.create_template()
            raise FileNotFoundError(
                f"streams.csv not found → template created at:\n  {CSV_FILE()}\n"
                "Edit it with your stream details, then restart HydraCast."
            )
        configs: List[StreamConfig] = []
        errors:  List[str]          = []
        with open(CSV_FILE(), newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("streams.csv appears to be empty.")
            for i, row in enumerate(reader, start=2):
                name = row.get("stream_name", "").strip()
                if not name:
                    errors.append(f"Row {i}: empty name — skipped.")
                    continue
                try:
                    port = int(row.get("port", "0").strip())
                    if not (1024 <= port <= 65535):
                        raise ValueError("out of range")
                except Exception:
                    errors.append(f"Row {i} ({name}): invalid port — skipped.")
                    continue
                playlist = cls.parse_files(row.get("files", "").strip())
                if not playlist:
                    errors.append(f"Row {i} ({name}): no files — skipped.")
                    continue
                weekdays = cls.parse_weekdays(row.get("weekdays", "ALL"))
                enabled  = cls.parse_bool(row.get("enabled", "true"))
                shuffle  = cls.parse_bool(row.get("shuffle", "false"))
                spath    = row.get("stream_path", "stream").strip() or "stream"
                vid_br   = cls._sanitize_bitrate(row.get("video_bitrate", "2500k"), "2500k")
                aud_br   = cls._sanitize_bitrate(row.get("audio_bitrate", "128k"), "128k")
                hls_en   = cls.parse_bool(row.get("hls_enabled", "false"))

                # Compliance fields — optional, default to disabled
                comp_en    = cls.parse_bool(row.get("compliance_enabled", "false"))
                comp_start = cls._sanitize_hms(row.get("compliance_start", "06:00:00"))
                comp_loop  = cls.parse_bool(row.get("compliance_loop", "false"))

                sorted_pl = sorted(playlist, key=lambda x: x.priority)
                cfg = StreamConfig(
                    name=name, port=port, playlist=sorted_pl,
                    weekdays=weekdays, enabled=enabled, shuffle=shuffle,
                    stream_path=spath, video_bitrate=vid_br,
                    audio_bitrate=aud_br, hls_enabled=hls_en,
                    row_index=i - 2,
                    compliance_enabled=comp_en,
                    compliance_start=comp_start,
                    compliance_loop=comp_loop,
                )

                # ── Folder-source auto-detection ──────────────────────────────
                # If the path in the files column is a directory, replace the
                # playlist with the scanned contents and set folder_source.
                cls._resolve_folder_source(cfg)

                configs.append(cfg)

        for e in errors:
            logging.warning("CSV: %s", e)

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
                    "CSV: Ports %d (%s) and %d (%s) are only %d apart — "
                    "RTP/RTCP companion ports may collide. "
                    "Recommended gap is ≥10 (e.g. 8554, 8564, 8574 …).",
                    p1, n1, p2, n2, p2 - p1,
                )

        if not configs:
            raise ValueError("No valid streams in streams.csv.")
        return configs

    @classmethod
    def save(cls, configs: List[StreamConfig]) -> None:
        with open(CSV_FILE(), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_COLUMNS)
            for c in configs:
                # For folder-source streams, save the folder path directly.
                if c.folder_source and c.folder_source.is_dir():
                    files_str = str(c.folder_source)
                else:
                    files_str = ";".join(
                        f"{item.file_path}@{item.start_position}#{item.priority}"
                        for item in c.playlist
                    )
                w.writerow([
                    c.name, c.port, files_str,
                    c.weekdays_display().replace("ALL", "all"),
                    str(c.enabled).lower(), str(c.shuffle).lower(),
                    c.stream_path, c.video_bitrate, c.audio_bitrate,
                    str(c.hls_enabled).lower(),
                    str(c.compliance_enabled).lower(),
                    c.compliance_start,
                    str(c.compliance_loop).lower(),
                ])

    # ── Load / save events ────────────────────────────────────────────────────
    @classmethod
    def load_events(cls) -> List[OneShotEvent]:
        if not EVENTS_FILE().exists():
            return []
        events: List[OneShotEvent] = []
        with open(EVENTS_FILE(), newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    events.append(OneShotEvent(
                        event_id=row["event_id"].strip(),
                        stream_name=row["stream_name"].strip(),
                        file_path=Path(row["file_path"].strip()),
                        play_at=datetime.strptime(
                            row["play_at"].strip(), "%Y-%m-%d %H:%M:%S"),
                        post_action=row.get("post_action", "resume").strip(),
                        played=cls.parse_bool(row.get("played", "false")),
                        start_pos=row.get("start_pos", "00:00:00").strip(),
                    ))
                except Exception as exc:
                    logging.warning("Events CSV row error: %s", exc)
        return events

    @classmethod
    def save_events(cls, events: List[OneShotEvent]) -> None:
        with open(EVENTS_FILE(), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(EVENTS_COLUMNS + ["played"])
            for e in events:
                w.writerow([
                    e.event_id, e.stream_name, str(e.file_path),
                    e.play_at.strftime("%Y-%m-%d %H:%M:%S"),
                    e.post_action, e.start_pos, str(e.played).lower(),
                ])

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
