"""
hc/compliance.py — Broadcast compliance mode (v2).

NEW in v2
─────────
• Day-tagged file selection: scans the playlist for a file whose name contains
  _monday_ / _mon_ (etc.) matching today's weekday, then falls back to the
  first untagged file, then to whatever is first in the playlist.

• Accurate seek offset ("When video starts" mode):
    broadcast_start = 06:00  →  video position 00:00:00
    current time    = 10:00  →  seek to 04:00:00  (4-hour delay)
  Works for 24-h videos and, when loop_calculation=True, for shorter videos
  by wrapping elapsed time with modulo.

• Post-event resume: call calculate_compliance_offset_after_event() after a
  one-shot event finishes to get the correct seek position for the compliance
  file that should resume.

• Compliance alert: if compliance_enabled is True and the seek calculation
  fails or the required day-tagged file is missing, an error string is
  returned so the Web UI can surface it.

All times are local system time.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

DEFAULT_COMPLIANCE_START = "06:00:00"

# ---------------------------------------------------------------------------
# Weekday detection (mirrors folder_scanner logic)
# ---------------------------------------------------------------------------
_DAY_RE = re.compile(
    r'_('
    r'monday|tuesday|wednesday|thursday|friday|saturday|sunday'
    r'|mon|tue|wed|thu|fri|sat|sun'
    r')_',
    re.IGNORECASE,
)
_DAY_INDEX = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _detect_day(filename: str) -> Optional[int]:
    """Return 0–6 (Mon–Sun) if *filename* embeds a _dayname_ tag, else None."""
    m = _DAY_RE.search(filename)
    return _DAY_INDEX.get(m.group(1).lower()) if m else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_hms(t: str) -> time:
    """Parse 'HH:MM:SS' or 'HH:MM' into datetime.time."""
    parts = t.strip().split(":")
    try:
        if len(parts) == 3:
            return time(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) == 2:
            return time(int(parts[0]), int(parts[1]))
    except (ValueError, OverflowError):
        pass
    log.warning("compliance: could not parse time '%s', defaulting to 06:00", t)
    return time(6, 0)


def _fmt(seconds: float) -> str:
    s = int(max(0.0, seconds))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


# ---------------------------------------------------------------------------
# Day-tagged file selection
# ---------------------------------------------------------------------------

def select_compliance_file(
    playlist,           # List[PlaylistItem]
    today_override: Optional[int] = None,
) -> Tuple[Optional[object], Optional[str]]:
    """
    Choose the best PlaylistItem for today's compliance broadcast.

    Selection priority:
      1. File whose name contains _today's_weekday_  (e.g. _tue_ on Tuesday)
      2. First file with NO day tag
      3. First file in the playlist regardless of tag

    Returns (item, error_string).
    error_string is non-None when no suitable file was found or when the
    today-tagged file is missing from disk (compliance alert).
    """
    if not playlist:
        return None, "Compliance: playlist is empty — cannot select a file."

    today = today_override if today_override is not None else datetime.now().weekday()
    today_name = _DAY_NAMES[today]

    today_files  = [it for it in playlist if _detect_day(it.file_path.name) == today]
    untagged     = [it for it in playlist if _detect_day(it.file_path.name) is None]

    if today_files:
        chosen = today_files[0]
        if not chosen.file_path.exists():
            err = (
                f"Compliance: today's file '{chosen.file_path.name}' "
                f"({today_name}) is missing from disk."
            )
            log.error(err)
            return chosen, err
        log.info(
            "compliance: selected today's (%s) file '%s'",
            today_name, chosen.file_path.name,
        )
        return chosen, None

    if untagged:
        chosen = untagged[0]
        warn = (
            f"Compliance: no file tagged for today ({today_name}); "
            f"using untagged file '{chosen.file_path.name}'."
        )
        log.warning(warn)
        return chosen, warn

    # Last resort: first file in playlist
    chosen = playlist[0]
    warn = (
        f"Compliance: no today-tagged or untagged file found; "
        f"falling back to '{chosen.file_path.name}'."
    )
    log.warning(warn)
    return chosen, warn


# ---------------------------------------------------------------------------
# Seek offset calculation
# ---------------------------------------------------------------------------

def calculate_compliance_offset(
    video_duration: float,
    broadcast_start: str = DEFAULT_COMPLIANCE_START,
    loop_calculation: bool = False,
    reference_time: Optional[datetime] = None,
) -> Tuple[float, str]:
    """
    Return (seek_seconds, human_readable_explanation).

    "When video starts" semantics
    ──────────────────────────────
    broadcast_start is the wall-clock time that maps to position 00:00:00 in
    the video.  If the current time is T hours after broadcast_start, the
    stream should seek to T hours into the video.

    Parameters
    ----------
    video_duration:
        Total duration of the video in seconds.  Pass 0 if unknown.
    broadcast_start:
        Wall-clock time that equals video position 00:00:00 (e.g. "06:00:00").
    loop_calculation:
        If True, wrap elapsed time modulo video_duration (for videos < 24 h).
    reference_time:
        Override "now" — used by post-event resume to inject the time at which
        the compliance file should resume.
    """
    now = reference_time or datetime.now()
    start_t = _parse_hms(broadcast_start)
    start_dt = now.replace(
        hour=start_t.hour, minute=start_t.minute, second=start_t.second,
        microsecond=0,
    )

    # If today's broadcast slot hasn't started yet, use yesterday's.
    if now < start_dt:
        start_dt -= timedelta(days=1)

    elapsed = (now - start_dt).total_seconds()

    if video_duration <= 0:
        explanation = "Compliance: video duration unknown — starting from 00:00:00."
        log.info(explanation)
        return 0.0, explanation

    is_long_form = video_duration >= 86400  # 24 h or more

    if is_long_form or loop_calculation:
        seek = elapsed % video_duration
        loop_n = int(elapsed // video_duration)
        explanation = (
            f"Compliance [{broadcast_start}]: "
            f"elapsed {_fmt(elapsed)} → loop #{loop_n}, seek to {_fmt(seek)} "
            f"(video {_fmt(video_duration)})"
        )
        log.info(explanation)
        return seek, explanation

    # Short video, loop_calculation=False
    explanation = (
        f"Compliance [{broadcast_start}]: "
        f"video {_fmt(video_duration)} < 24 h and loop_calculation=False — "
        f"starting from 00:00:00.  Enable loop_calculation to seek within loops."
    )
    log.info(explanation)
    return 0.0, explanation


# ---------------------------------------------------------------------------
# Post-event resume
# ---------------------------------------------------------------------------

def calculate_compliance_offset_after_event(
    event_end_time: datetime,
    video_duration: float,
    broadcast_start: str = DEFAULT_COMPLIANCE_START,
    loop_calculation: bool = False,
) -> Tuple[float, str]:
    """
    After a one-shot event finishes, compute the correct seek position so the
    compliance video resumes at exactly the right point as if it had been
    running continuously.

    Pass the datetime at which the event ended as *event_end_time*.
    The calculation is identical to calculate_compliance_offset but uses
    event_end_time as the reference instead of datetime.now().
    """
    seek, explanation = calculate_compliance_offset(
        video_duration=video_duration,
        broadcast_start=broadcast_start,
        loop_calculation=loop_calculation,
        reference_time=event_end_time,
    )
    resume_explanation = (
        f"Post-event resume at {event_end_time.strftime('%H:%M:%S')}: {explanation}"
    )
    log.info(resume_explanation)
    return seek, resume_explanation


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def check_compliance_drift(
    current_pos: float,
    video_duration: float,
    broadcast_start: str = DEFAULT_COMPLIANCE_START,
    loop_calculation: bool = False,
    drift_threshold: float = 30.0,
    reference_time: Optional[datetime] = None,
) -> Tuple[bool, float, float]:
    """
    Compare the current playback position against where compliance says it
    should be and decide whether a hard resync is warranted.

    Parameters
    ----------
    current_pos:
        Current FFmpeg playback position in seconds (from StreamState.current_pos).
    video_duration:
        Total duration of the compliance video in seconds.
    broadcast_start:
        Wall-clock time that equals video position 00:00:00.
    loop_calculation:
        Passed through to calculate_compliance_offset unchanged.
    drift_threshold:
        Maximum tolerated drift in seconds before a resync is recommended.
    reference_time:
        Override "now" — useful for unit tests.

    Returns
    -------
    (should_resync, drift_seconds, expected_pos)

    should_resync:
        True when abs(drift) > drift_threshold.
    drift_seconds:
        current_pos − expected_pos.  Positive means the stream is ahead of
        schedule; negative means it is behind.
    expected_pos:
        The correct seek target right now.
    """
    if video_duration <= 0:
        log.debug("check_compliance_drift: video_duration unknown — skip check")
        return False, 0.0, 0.0

    expected_pos, _ = calculate_compliance_offset(
        video_duration=video_duration,
        broadcast_start=broadcast_start,
        loop_calculation=loop_calculation,
        reference_time=reference_time,
    )
    drift = current_pos - expected_pos
    should_resync = abs(drift) > drift_threshold
    log.debug(
        "compliance drift: current=%.1fs expected=%.1fs drift=%+.1fs "
        "threshold=%.1fs resync=%s",
        current_pos, expected_pos, drift, drift_threshold, should_resync,
    )
    return should_resync, drift, expected_pos


# ---------------------------------------------------------------------------
# Full compliance start helper (combines file selection + seek offset)
# ---------------------------------------------------------------------------

def prepare_compliance_start(
    playlist,
    broadcast_start: str = DEFAULT_COMPLIANCE_START,
    loop_calculation: bool = False,
    video_duration: float = 0.0,
    reference_time: Optional[datetime] = None,
) -> Tuple[Optional[object], float, str, Optional[str]]:
    """
    One-stop helper used by the worker when starting a compliance stream.

    Returns
    -------
    (playlist_item, seek_seconds, explanation, alert_message)

    alert_message is None on success; non-None when the Web UI should show a
    compliance error banner (e.g. missing day-tagged file).
    """
    item, file_error = select_compliance_file(playlist)
    if item is None:
        return None, 0.0, "No file available.", file_error

    seek, seek_explanation = calculate_compliance_offset(
        video_duration=video_duration,
        broadcast_start=broadcast_start,
        loop_calculation=loop_calculation,
        reference_time=reference_time,
    )

    alert = file_error  # propagate file-level warnings as alerts
    return item, seek, seek_explanation, alert
