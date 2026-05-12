"""
hc/folder_scanner.py — Folder scanner with _day_-tag detection and priority sorting.

Day detection rule: the weekday abbreviation / full name must be wrapped by
underscores on both sides, e.g.  episode_01_thu_.mp4  or  news_MONDAY_final.mkv.
Case is ignored during matching, but the original casing is preserved in the
file name.

Conflict resolution within the same day-bucket (or within untagged files):
the chosen sort_mode applies; alphabetical order is the final tiebreaker so
results are always deterministic.
"""
from __future__ import annotations

import re
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


def detect_day(filename: str) -> Optional[int]:
    """
    Return 0–6 (Mon–Sun) if *filename* contains _dayname_, else None.
    Only the FIRST match is used if multiple day tags appear.
    """
    m = _DAY_RE.search(filename)
    return _DAY_INDEX.get(m.group(1).lower()) if m else None


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
    DAY_FWD   = "day_fwd"   # Mon → Sun (day-tagged first, then untagged)
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
        DAY_FWD:   "By Weekday    Mon → Sun  (untagged at end)",
        DAY_REV:   "By Weekday    Sun → Mon  (untagged at end)",
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

    * Day-tagged files (_mon_, _thu_, …) are grouped by weekday.
    * Within each weekday group — and within the untagged group — files are
      ordered according to *sort_mode*.
    * Alphabetical order is always the final tiebreaker so the result is
      deterministic.
    * Priorities are assigned 1, 2, 3 … in the final order.
    * Untagged files are placed after all tagged files with a warning.
    """
    if not folder.is_dir():
        return [], [f"'{folder}' is not a directory."]

    raw_files: List[Path] = sorted(
        [f for f in folder.iterdir()
         if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS],
        key=lambda p: p.name.lower(),          # stable base order
    )

    if not raw_files:
        return [], [f"No supported media files found in '{folder}'."]

    warnings: List[str] = []

    # Split into tagged buckets (0–6) and untagged
    buckets: Dict[int, List[Path]] = {d: [] for d in range(7)}
    untagged: List[Path] = []

    for fp in raw_files:
        day = detect_day(fp.name)
        if day is not None:
            buckets[day].append(fp)
        else:
            untagged.append(fp)

    if untagged:
        names_preview = ", ".join(p.name for p in untagged[:4])
        if len(untagged) > 4:
            names_preview += f" … (+{len(untagged) - 4} more)"
        warnings.append(
            f"⚠  {len(untagged)} file(s) have no _day_ tag — "
            f"assigned to ALL days (added last with warning): {names_preview}"
        )

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
        # DAY_FWD / DAY_REV — within each bucket we fall back to alpha
        return (name,)

    # Build ordered file list
    ordered: List[Tuple[Optional[int], Path]] = []

    if sort_mode in (SortMode.DAY_FWD, SortMode.DAY_REV):
        day_order = range(7) if sort_mode == SortMode.DAY_FWD else range(6, -1, -1)
        for d in day_order:
            for fp in sorted(buckets[d], key=_sort_key):
                ordered.append((d, fp))
        for fp in sorted(untagged, key=_sort_key):
            ordered.append((None, fp))
    else:
        # All files together; day-tagged ones sorted before untagged (stable)
        all_tagged = [fp for bucket in buckets.values() for fp in bucket]
        for fp in sorted(all_tagged, key=_sort_key):
            ordered.append((detect_day(fp.name), fp))
        for fp in sorted(untagged, key=_sort_key):
            ordered.append((None, fp))

    # Assign priorities 1 … N
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

    for d in range(7):
        per_day[d].extend(all_day)

    return items, warnings, per_day
