"""
hc/watchdog.py — Playlist watchdog: proactively checks the next queued file.

The watchdog runs in a background thread for every LIVE stream.  Every
CHECK_INTERVAL seconds it inspects the *next* file in the playlist queue.
If that file is missing or empty it logs an ERROR (visible in both the stream
log and the global event log) so the operator can act *before* the current
file finishes.

When the stream worker actually tries to advance to the missing file it will
call ``skip_missing_and_advance`` (also exported here) which tries the next-
next file — and so on — until a valid file is found or the playlist is
exhausted.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from hc.models import PlaylistItem, StreamState, StreamStatus

if TYPE_CHECKING:
    from hc.worker import LogBuffer

log = logging.getLogger(__name__)

CHECK_INTERVAL = 30.0          # seconds between watchdog polls
MIN_FILE_BYTES = 1024           # files smaller than this are treated as corrupt


class PlaylistWatchdog:
    """
    Background thread that warns early about a bad next-queued file.
    One instance per stream; started when the stream goes LIVE and stopped
    when it is stopped/restarted.
    """

    def __init__(self, state: StreamState, glog: "LogBuffer") -> None:
        self.state  = state
        self.glog   = glog
        self._stop  = threading.Event()
        self._t: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    def start(self) -> None:
        self._stop.clear()
        self._t = threading.Thread(
            target=self._loop, daemon=True,
            name=f"watchdog-{self.state.config.port}",
        )
        self._t.start()

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    def _log(self, msg: str, level: str = "INFO") -> None:
        full = f"[{self.state.config.name}][WD] {msg}"
        self.state.log_add(full)
        self.glog.add(full, level)

    def _next_playlist_item(self) -> Optional[PlaylistItem]:
        """Return the PlaylistItem *after* the current one, or None."""
        pl    = self.state.config.playlist
        order = self.state.playlist_order
        idx   = self.state.playlist_index

        if len(pl) <= 1 or not order:
            return None

        next_pos = (idx + 1) % len(order)
        try:
            return pl[order[next_pos]]
        except IndexError:
            return None

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self.state.status == StreamStatus.LIVE:
                item = self._next_playlist_item()
                if item is not None:
                    _check_file(item.file_path, self._log)
            for _ in range(int(CHECK_INTERVAL * 10)):
                if self._stop.is_set():
                    return
                time.sleep(0.1)


# ---------------------------------------------------------------------------
# Shared helper: validate a file
# ---------------------------------------------------------------------------

def _check_file(path: Path, log_fn) -> bool:
    """
    Return True if *path* is a valid, non-empty media file.
    Calls *log_fn* with an ERROR message if not.
    """
    if not path.exists():
        log_fn(f"Next queued file MISSING: '{path.name}'", "ERROR")
        return False
    try:
        size = path.stat().st_size
    except OSError as exc:
        log_fn(f"Next queued file unreadable: '{path.name}' — {exc}", "ERROR")
        return False
    if size < MIN_FILE_BYTES:
        log_fn(
            f"Next queued file too small ({size} B, likely corrupt): "
            f"'{path.name}'",
            "ERROR",
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Skip-bad-files helper — called from worker._monitor when advancing playlist
# ---------------------------------------------------------------------------

def find_next_valid_item(state: StreamState, log_fn) -> Optional[PlaylistItem]:
    """
    Starting from the item *after* the current playlist_index, walk forward
    until a valid file is found (up to one full loop of the playlist).

    Advances ``state.playlist_index`` in-place and returns the valid
    ``PlaylistItem``, or ``None`` if the entire playlist is unusable.
    """
    pl    = state.config.playlist
    order = state.playlist_order
    n     = len(order)

    if n == 0:
        return None

    for attempt in range(n):
        state.playlist_index = (state.playlist_index + 1) % n
        try:
            item = pl[order[state.playlist_index]]
        except IndexError:
            continue
        if _check_file(item.file_path, log_fn):
            return item
        log_fn(
            f"Skipping bad file [{attempt + 1}/{n}]: '{item.file_path.name}'",
            "WARN",
        )

    log_fn("All playlist files are missing or corrupt — cannot advance.", "ERROR")
    return None
