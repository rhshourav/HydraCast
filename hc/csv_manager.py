"""
hc/csv_manager.py  —  Load / save streams.csv and events.csv.
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
]

# NOTE: template ports spaced ≥ 10 apart so RTP/RTCP companion ports never collide.
CSV_TEMPLATE_ROWS = [
    ["Stream_1", "8554", "/path/to/video.mp4@00:00:00#1",
     "ALL", "true", "false", "stream", "2500k", "128k", "false"],
    ["Stream_2", "8564", "/path/to/a.mp4@00:05:00#1;/path/to/b.mkv@00:00:00#2",
     "Mon|Wed|Fri", "true", "false", "ch2", "4000k", "192k", "false"],
    ["Stream_3", "8574", "/media/demo.mp4@00:00:00#1",
     "Sat|Sun", "false", "true", "ch3", "1500k", "128k", "false"],
    ["Stream_4", "8584", "/media/show.mp4@00:00:00#1",
     "Weekdays", "true", "false", "ch4", "2500k", "128k", "true"],
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
    def parse_files(raw: str) -> List[PlaylistItem]:
        """
        Format: path@HH:MM:SS#priority;path@HH:MM:SS#priority …
        Priority (#N) is optional, defaults to 999.
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
            items.append(PlaylistItem(
                file_path=Path(path_str),
                start_position=pos,
                priority=priority,
            ))
        return items

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
                sorted_pl = sorted(playlist, key=lambda x: x.priority)
                configs.append(StreamConfig(
                    name=name, port=port, playlist=sorted_pl,
                    weekdays=weekdays, enabled=enabled, shuffle=shuffle,
                    stream_path=spath, video_bitrate=vid_br,
                    audio_bitrate=aud_br, hls_enabled=hls_en,
                    row_index=i - 2,
                ))

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

        # ── Port-gap warning (recommended ≥ 10 apart for RTP/RTCP companion ports)
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
