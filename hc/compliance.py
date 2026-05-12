"""
hc/compliance.py — Broadcast compliance mode: calculate the correct seek offset.

Compliance mode assumes a video (typically 24 h long) is broadcast starting at
a fixed time of day every day (default 06:00:00).  When HydraCast starts (or
the stream is restarted), this module calculates *where in the video playback
should begin* so that what viewers see matches what a continuous linear
broadcast would be showing right now.

Example:
    Video is 24 h long.  Broadcast start = 06:00.  Current time = 14:30.
    Elapsed since 06:00 → 8 h 30 min → 30 600 s.
    Seek position = 30 600 s into the video.

For videos shorter than 24 h, loop_calculation controls whether the module
calculates the position within the current loop (True) or just starts from 0
(False, the safe default).

All times are local system time.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Tuple

log = logging.getLogger(__name__)

# Default broadcast start for compliance mode
DEFAULT_COMPLIANCE_START = "06:00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_hms(t: str) -> time:
    """Parse 'HH:MM:SS' or 'HH:MM' into a ``datetime.time``."""
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
# Public API
# ---------------------------------------------------------------------------

def calculate_compliance_offset(
    video_duration: float,
    broadcast_start: str = DEFAULT_COMPLIANCE_START,
    loop_calculation: bool = False,
) -> Tuple[float, str]:
    """
    Return ``(seek_seconds, human_readable_explanation)``.

    Parameters
    ----------
    video_duration:
        Total duration of the video in seconds.  Pass 0 if unknown.
    broadcast_start:
        Wall-clock time when the broadcast "day" begins, e.g. ``"06:00:00"``.
    loop_calculation:
        If ``True``, compute the offset even for videos shorter than 24 h by
        modulo-wrapping elapsed time.  If ``False`` (default), short videos
        just start from 0.
    """
    now = datetime.now()
    start_t = _parse_hms(broadcast_start)
    start_dt = now.replace(
        hour=start_t.hour, minute=start_t.minute, second=start_t.second,
        microsecond=0,
    )

    # If today's broadcast hasn't started yet, use yesterday's slot.
    if now < start_dt:
        start_dt -= timedelta(days=1)

    elapsed = (now - start_dt).total_seconds()

    if video_duration <= 0:
        explanation = (
            "Compliance: video duration unknown — starting from 00:00:00."
        )
        log.info(explanation)
        return 0.0, explanation

    is_long_form = video_duration >= 86400          # 24 h or more

    if is_long_form or loop_calculation:
        seek = elapsed % video_duration
        loop_n = int(elapsed // video_duration)
        explanation = (
            f"Compliance [{broadcast_start}]: "
            f"elapsed {_fmt(elapsed)} since broadcast start → "
            f"loop #{loop_n}, seek to {_fmt(seek)} "
            f"(video {_fmt(video_duration)} long)"
        )
        log.info(explanation)
        return seek, explanation
    else:
        explanation = (
            f"Compliance [{broadcast_start}]: "
            f"video {_fmt(video_duration)} < 24 h and loop_calculation=False — "
            f"starting from 00:00:00.  Enable loop_calculation to seek within loops."
        )
        log.info(explanation)
        return 0.0, explanation
