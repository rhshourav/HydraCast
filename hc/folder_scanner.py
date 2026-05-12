"""
hc/folder_scanner.py — Folder scanner with _day_-tag detection, today-aware
priority sorting, and streaming only today's (+ untagged) files first.

Day detection rule: the weekday abbreviation / full name must be wrapped by
underscores on both sides, e.g.  episode_01_thu_.mp4  or  news_MONDAY_final.mkv.
Case is ignored during matching, but the original casing is preserved in the
file name.

TODAY-AWARE STREAMING RULE
──────────────────────────
When a folder is scanned HydraCast compares each file's day-tag against the
current calendar weekday (Monday = 0 … Sunday = 6).

  1. Files tagged for TODAY  — sorted by the chosen sort_mode, placed FIRST.
  2. Files with no day-tag   — sorted by the chosen sort_mode, placed SECOND.
  3. Files tagged for OTHER days — sorted day-order then sort_mode, placed LAST.

This means a folder containing:

    news_mon_.mp4  news_tue_.mp4  news_wed_.mp4  intro.mp4

…on a Tuesday will stream in the order:
    news_tue_.mp4  →  intro.mp4  →  news_mon_.mp4  →  news_wed_.mp4  …

Conflict resolution within the same bucket: sort_mode applies; alphabetical
order is the final tiebreaker so results are always deterministic.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hc.constants import DAY_ABBR, SUPPORTED_EXTS
from hc.models import PlaylistItem

# ---------------------------------------------------------------------------
# Day detection
# ---------------------------------------------------------------------------
# Pattern requires underscores on BOTH sides so "thursday" inside a longer word
# like "thunderstorm" is never matched.
_DAY_RE = re.compile(
    r'_('
    r'monday|tuesday|wednesday|thursday|friday|saturday|sunday'
    r'|mon|tue|wed|thu|fri|sat|sun'
    r')_',
    re.IGNORECASE,
)

_DAY_INDEX: Dict[str, int] = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Human-readable day names for logging / UI.
_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def detect_day(filename: str) -> Optional[int]:
    """
    Return 0–6 (Mon–Sun) if *filename* contains _dayname_, else None.
    Only the FIRST match is used if multiple day tags appear.
    """
    m = _DAY_RE.search(filename)
    return _DAY_INDEX.get(m.group(1).lower()) if m else None


def today_weekday() -> int:
    """Return today's weekday index: Monday = 0, Sunday = 6."""
    return date.today().weekday()


# ---------------------------------------------------------------------------
# Numerical key helper
# ---------------------------------------------------------------------------
def _leading_number(name: str) -> int:
    """Return the first integer found in *name*, or 999_999 if none."""
    nums = re.findall(r"\d+", name)
    return int(nums[0]) if nums else 999_999


# ---------------------------------------------------------------------------
# Sort modes
# ---------------------------------------------------------------------------
class SortMode:
    ALPHA_FWD = "alpha_fwd"
    ALPHA_REV = "alpha_rev"
    NUM_FWD   = "num_fwd"
    NUM_REV   = "num_rev"
    DAY_FWD   = "day_fwd"   # Mon → Sun  (today-tagged first, then untagged)
    DAY_REV   = "day_rev"   # Sun → Mon
    DATE_FWD  = "date_fwd"  # oldest → newest
    DATE_REV  = "date_rev"  # newest → oldest

    ALL: List[str] = [
        ALPHA_FWD, ALPHA_REV, NUM_FWD, NUM_REV,
        DAY_FWD, DAY_REV, DATE_FWD, DATE_REV,
    ]
    LABELS: Dict[str, str] = {
        ALPHA_FWD: "Alphabetical  A → Z",
        ALPHA_REV: "Alphabetical  Z → A",
        NUM_FWD:   "Numerical     0 → 9  (embedded episode numbers)",
        NUM_REV:   "Numerical     9 → 0",
        DAY_FWD:   "By Weekday    Mon → Sun  (today first, untagged second)",
        DAY_REV:   "By Weekday    Sun → Mon  (today first, untagged second)",
        DATE_FWD:  "By File Date  oldest → newest",
        DATE_REV:  "By File Date  newest → oldest",
    }


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------
def scan_folder(
    folder: Path,
    sort_mode: str = SortMode.ALPHA_FWD,
) -> Tuple[List[PlaylistItem], List[str]]:
    """
    Scan *folder* for supported media files and return
    ``(playlist_items, warnings)``.

    TODAY-AWARE ordering (always applied regardless of sort_mode):
      Tier 1 — files tagged for today's weekday
      Tier 2 — files with no day-tag
      Tier 3 — files tagged for other weekdays (in weekday order)

    Within each tier the chosen *sort_mode* is applied; alphabetical name is
    always the final tiebreaker so results are fully deterministic.

    Priorities are assigned 1, 2, 3 … in the final order.
    """
    if not folder.is_dir():
        return [], [f"'{folder}' is not a directory."]

    raw_files: List[Path] = sorted(
        [f for f in folder.iterdir()
         if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS],
        key=lambda p: p.name.lower(),   # stable base order
    )

    if not raw_files:
        return [], [f"No supported media files found in '{folder}'."]

    today = today_weekday()
    warnings: List[str] = []

    # ── Bucket files ──────────────────────────────────────────────────────────
    today_files:   List[Path] = []          # tier 1: tagged today
    untagged:      List[Path] = []          # tier 2: no tag
    other_buckets: Dict[int, List[Path]] = {d: [] for d in range(7)}  # tier 3

    for fp in raw_files:
        day = detect_day(fp.name)
        if day is None:
            untagged.append(fp)
        elif day == today:
            today_files.append(fp)
        else:
            other_buckets[day].append(fp)

    # ── Warnings ──────────────────────────────────────────────────────────────
    if untagged:
        names_preview = ", ".join(p.name for p in untagged[:4])
        if len(untagged) > 4:
            names_preview += f" … (+{len(untagged) - 4} more)"
        warnings.append(
            f"⚠  {len(untagged)} file(s) have no _day_ tag — "
            f"streamed after today's ({_DAY_NAMES[today]}) files: {names_preview}"
        )

    if today_files:
        warnings.append(
            f"ℹ  {len(today_files)} file(s) tagged for today "
            f"({_DAY_NAMES[today]}) — placed first in playlist."
        )

    # ── Sort key builder ──────────────────────────────────────────────────────
    def _sort_key(fp: Path):
        """Primary sort key using *sort_mode*; alpha name is always tiebreaker."""
        name = fp.name.lower()
        mtime = 0.0
        try:
            mtime = fp.stat().st_mtime
        except OSError:
            pass
        if sort_mode == SortMode.ALPHA_FWD:
            return (name,)
        if sort_mode == SortMode.ALPHA_REV:
            return (tuple(-ord(c) for c in name),)
        if sort_mode == SortMode.NUM_FWD:
            return (_leading_number(name), name)
        if sort_mode == SortMode.NUM_REV:
            return (-_leading_number(name), name)
        if sort_mode == SortMode.DATE_FWD:
            return (mtime, name)
        if sort_mode == SortMode.DATE_REV:
            return (-mtime, name)
        # DAY_FWD / DAY_REV — within each bucket fall back to alpha
        return (name,)

    # ── Assemble ordered list (today → untagged → others) ────────────────────
    ordered: List[Tuple[Optional[int], Path]] = []

    # Tier 1: today's files
    for fp in sorted(today_files, key=_sort_key):
        ordered.append((today, fp))

    # Tier 2: untagged files
    for fp in sorted(untagged, key=_sort_key):
        ordered.append((None, fp))

    # Tier 3: other weekday files
    if sort_mode == SortMode.DAY_REV:
        # Sun → Mon order for the "other" bucket, wrapping around today
        other_day_order = [
            d for d in range(6, -1, -1) if d != today
        ]
    else:
        # Default: Mon → Sun, skipping today
        other_day_order = [
            d for d in range(7) if d != today
        ]

    for d in other_day_order:
        for fp in sorted(other_buckets[d], key=_sort_key):
            ordered.append((d, fp))

    # ── Assign priorities 1 … N ───────────────────────────────────────────────
    items: List[PlaylistItem] = [
        PlaylistItem(file_path=fp, start_position="00:00:00", priority=i + 1)
        for i, (_, fp) in enumerate(ordered)
    ]

    return items, warnings


def scan_folder_interactive(
    folder: Path,
    sort_mode: str = SortMode.ALPHA_FWD,
) -> Tuple[List[PlaylistItem], List[str], Dict[int, List[PlaylistItem]]]:
    """
    Extended scan that also returns a per-weekday breakdown (useful for TUI
    preview).  Untagged files appear in every weekday bucket.

    Returns ``(all_items, warnings, per_day_map)`` where *per_day_map* maps
    0–6 to the list of items that should play on that day (tagged + untagged).

    The master *all_items* list is always today-aware (today's tagged files
    first, then untagged, then other days).
    """
    items, warnings = scan_folder(folder, sort_mode)

    per_day: Dict[int, List[PlaylistItem]] = {d: [] for d in range(7)}
    all_day: List[PlaylistItem] = []

    for item in items:
        day = detect_day(item.file_path.name)
        if day is not None:
            per_day[day].append(item)
        else:
            all_day.append(item)

    # Untagged files appear in every day's bucket.
    for d in range(7):
        per_day[d].extend(all_day)

    return items, warnings, per_day
