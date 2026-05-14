"""hc/web_csvmanager.py  —  CSVManager compatibility shim for HydraCast Web UI.

This shim exposes the subset of the old CSVManager API used by web.py so
no call-sites in WebHandler._dispatch need to change.
"""
from __future__ import annotations

import re as _re

from hc.json_manager import JSONManager
from hc.models import PlaylistItem

class CSVManager:
    """Shim that exposes the subset of the old CSVManager API used by web.py."""

    # ── Persist (delegate straight to JSONManager) ────────────────────────────
    @staticmethod
    def save(configs) -> None:
        JSONManager.save(configs)

    @staticmethod
    def save_events(events) -> None:
        JSONManager._save_events(events)

    @staticmethod
    def add_event(events, ev) -> None:
        """Append *ev* (already-constructed OneShotEvent) and persist."""
        events.append(ev)
        JSONManager._save_events(events)

    # ── Parsing helpers ───────────────────────────────────────────────────────
    @staticmethod
    def parse_files(raw: str):
        """
        Parse a semicolon-or-newline separated list of file entries.
        Each entry: path[@HH:MM:SS][#priority]
        Returns a list of PlaylistItem.
        """
        from hc.models import PlaylistItem
        from pathlib import Path as _Path
        items = []
        for part in _re.split(r"[;\n]+", raw):
            part = part.strip()
            if not part:
                continue
            priority = 0
            if "#" in part:
                part, pri_s = part.rsplit("#", 1)
                try:
                    priority = int(pri_s.strip())
                except ValueError:
                    pass
            start = "00:00:00"
            if "@" in part:
                part, start = part.rsplit("@", 1)
                start = start.strip()
                if not _re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", start):
                    start = "00:00:00"
            fp = _Path(part.strip())
            items.append(PlaylistItem(
                file_path=fp,
                start_position=start,
                priority=priority,
            ))
        return items

    @staticmethod
    def parse_weekdays(raw: str):
        """
        Convert a weekday string to a list of abbreviations, e.g.
        'mon|wed|fri' → ['mon','wed','fri'],  'all' → ['mon','tue',…,'sun'].
        """
        from hc.constants import WEEKDAY_MAP, DAY_ABBR
        raw = raw.strip().lower()
        if raw in ("all", "everyday", ""):
            return [d.lower() for d in DAY_ABBR]
        if raw == "weekdays":
            return ["mon", "tue", "wed", "thu", "fri"]
        if raw == "weekends":
            return ["sat", "sun"]
        result = []
        for part in _re.split(r"[|,\s]+", raw):
            part = part.strip()
            if part in WEEKDAY_MAP:
                idx = WEEKDAY_MAP[part]
                if isinstance(idx, list):
                    result.extend(DAY_ABBR[i].lower() for i in idx)
                else:
                    result.append(DAY_ABBR[idx].lower())
        # deduplicate while preserving order
        seen = set()
        deduped = []
        for d in result:
            if d not in seen:
                seen.add(d)
                deduped.append(d)
        return deduped or [d.lower() for d in DAY_ABBR]

    @staticmethod
    def _sanitize_bitrate(value: str, fallback: str) -> str:
        value = value.strip()
        if _re.fullmatch(r"\d+[kKmM]?", value):
            return value.lower()
        return fallback

    @staticmethod
    def _sanitize_hms(value: str) -> str:
        value = value.strip()
        if _re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", value):
            return value
        return "00:00:00"

# Module-level manager reference (set by hydracast.py)
