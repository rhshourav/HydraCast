"""
hc/folder_watcher.py  —  Live folder monitor for folder-source streams.

Polls each stream's folder_source on a background thread.  When files are
added or removed, the in-memory playlist is updated immediately so the next
file the worker advances to is always current.

Design choices:
  • Pure stdlib — no inotify / FSEvents / ReadDirectoryChanges dependency.
  • One watcher thread per folder; multiple streams sharing the same folder
    share a single watcher to avoid redundant scans.
  • Playlist updates are thread-safe (cfg.playlist is replaced atomically).
  • A manual rescan can be forced at any time via FolderWatcher.rescan_now().
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from hc.constants import SUPPORTED_EXTS
from hc.folder_scanner import SortMode, scan_folder
from hc.models import PlaylistItem, StreamConfig, StreamState, StreamStatus

log = logging.getLogger(__name__)

# How often (seconds) to check each folder for changes.
POLL_INTERVAL: float = 15.0

# A snapshot is the frozenset of (resolved_path, mtime_ns) pairs.
_Snapshot = FrozenSet[Tuple[Path, int]]


def _snapshot(folder: Path) -> _Snapshot:
    """Capture the current set of supported media files in *folder*."""
    try:
        result: Set[Tuple[Path, int]] = set()
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
                try:
                    mtime = f.stat().st_mtime_ns
                except OSError:
                    mtime = 0
                result.add((f.resolve(), mtime))
        return frozenset(result)
    except Exception as exc:
        log.warning("folder_watcher: snapshot error for '%s': %s", folder, exc)
        return frozenset()


def _file_names(snap: _Snapshot) -> Set[str]:
    return {p.name for p, _ in snap}


class FolderWatcher:
    """
    Watches a single folder and keeps the playlist of all associated
    StreamConfig objects in sync.

    Usage::

        watcher = FolderWatcher(folder_path, poll_interval=15.0)
        watcher.attach(state)   # register a StreamState whose cfg.folder_source == folder
        watcher.start()
        …
        watcher.stop()
    """

    def __init__(
        self,
        folder: Path,
        glog,  # LogBuffer
        poll_interval: float = POLL_INTERVAL,
    ) -> None:
        self.folder        = folder
        self._glog         = glog
        self._interval     = poll_interval
        self._states:  List[StreamState] = []
        self._stop     = threading.Event()
        self._lock     = threading.Lock()
        self._snapshot: _Snapshot = frozenset()
        self._thread: Optional[threading.Thread] = None

    # ── Registration ──────────────────────────────────────────────────────────
    def attach(self, state: StreamState) -> None:
        with self._lock:
            if state not in self._states:
                self._states.append(state)

    def detach(self, state: StreamState) -> None:
        with self._lock:
            self._states = [s for s in self._states if s is not state]

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def start(self) -> None:
        self._stop.clear()
        self._snapshot = _snapshot(self.folder)
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name=f"fw-{self.folder.name}",
        )
        self._thread.start()
        log.info("folder_watcher: started for '%s'", self.folder)

    def stop(self) -> None:
        self._stop.set()

    # ── Public: manual trigger ────────────────────────────────────────────────
    def rescan_now(self) -> None:
        """Force an immediate rescan (e.g. called by manager.rescan_folder)."""
        self._check_and_update(force=True)

    # ── Internal ──────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        # Break the sleep into short chunks so stop() is responsive.
        ticks_per_interval = max(1, int(self._interval / 0.5))
        tick = 0
        while not self._stop.is_set():
            time.sleep(0.5)
            tick += 1
            if tick >= ticks_per_interval:
                tick = 0
                self._check_and_update()

    def _check_and_update(self, force: bool = False) -> None:
        new_snap = _snapshot(self.folder)
        if not force and new_snap == self._snapshot:
            return                          # nothing changed

        old_names = _file_names(self._snapshot)
        new_names = _file_names(new_snap)
        added   = new_names - old_names
        removed = old_names - new_names
        self._snapshot = new_snap

        if not added and not removed:
            # Only mtimes changed (file modified in-place) — rebuild playlist
            # so duration probes are refreshed, but skip noisy logging.
            self._rebuild_playlists(quiet=True)
            return

        label = f"[FolderWatcher:{self.folder.name}]"

        if added:
            names_str = ", ".join(sorted(added)[:5])
            suffix = f" (+{len(added)-5} more)" if len(added) > 5 else ""
            msg = f"{label} {len(added)} file(s) added: {names_str}{suffix}"
            log.info(msg)
            self._glog.add(msg, "INFO")
            with self._lock:
                for st in self._states:
                    st.log_add(msg)

        if removed:
            names_str = ", ".join(sorted(removed)[:5])
            suffix = f" (+{len(removed)-5} more)" if len(removed) > 5 else ""
            msg = f"{label} {len(removed)} file(s) removed: {names_str}{suffix}"
            log.warning(msg)
            self._glog.add(msg, "WARN")
            with self._lock:
                for st in self._states:
                    st.log_add(msg)
                    # Warn if the currently-playing file was removed.
                    current = st.current_file()
                    if current and current.name in removed:
                        warn = (
                            f"{label} Currently-playing file '{current.name}' "
                            "was removed from disk — stream will error when it ends."
                        )
                        self._glog.add(warn, "WARN")
                        st.log_add(warn)

        self._rebuild_playlists(quiet=False)

    def _rebuild_playlists(self, quiet: bool) -> None:
        """
        Re-run scan_folder and update cfg.playlist for every attached stream.
        Only stopped/errored streams get an immediate playlist swap; LIVE
        streams get the new playlist silently so it takes effect on next file.
        """
        try:
            items, warnings = scan_folder(self.folder)
        except Exception as exc:
            log.error("folder_watcher: scan_folder failed: %s", exc)
            return

        if not items:
            return

        with self._lock:
            states_snapshot = list(self._states)

        for st in states_snapshot:
            old_count = len(st.config.playlist)
            st.config.playlist = items          # atomic replace (CPython GIL)
            if not quiet:
                msg = (
                    f"[{st.config.name}] Playlist updated: "
                    f"{len(items)} file(s) (was {old_count})"
                )
                log.info(msg)
                st.log_add(msg)

        for w in warnings:
            log.warning("folder_watcher: %s", w)


# =============================================================================
# MANAGER REGISTRY  (one watcher per unique folder path)
# =============================================================================
class FolderWatcherRegistry:
    """
    Manages a pool of FolderWatcher instances keyed by resolved folder path.
    The StreamManager owns a single registry instance.
    """

    def __init__(self, glog, poll_interval: float = POLL_INTERVAL) -> None:
        self._glog          = glog
        self._interval      = poll_interval
        self._watchers: Dict[Path, FolderWatcher] = {}
        self._lock      = threading.Lock()

    def register(self, state: StreamState) -> None:
        """
        Register *state* with its folder watcher.  If no watcher exists yet
        for the folder a new one is created and started.
        Does nothing if the stream is not a folder-source stream.
        """
        folder = state.config.folder_source
        if folder is None:
            return
        resolved = folder.resolve()
        with self._lock:
            if resolved not in self._watchers:
                watcher = FolderWatcher(resolved, self._glog, self._interval)
                watcher.attach(state)
                watcher.start()
                self._watchers[resolved] = watcher
                log.info("FolderWatcherRegistry: new watcher for '%s'", resolved)
            else:
                self._watchers[resolved].attach(state)

    def unregister(self, state: StreamState) -> None:
        folder = state.config.folder_source
        if folder is None:
            return
        resolved = folder.resolve()
        with self._lock:
            w = self._watchers.get(resolved)
            if w:
                w.detach(state)

    def rescan(self, state: StreamState) -> None:
        """Force an immediate rescan for *state*'s folder."""
        folder = state.config.folder_source
        if folder is None:
            log.warning("rescan: '%s' has no folder_source", state.config.name)
            return
        resolved = folder.resolve()
        with self._lock:
            w = self._watchers.get(resolved)
        if w:
            w.rescan_now()
        else:
            # No watcher yet — run a one-shot scan and update the playlist.
            try:
                items, warnings = scan_folder(resolved)
                if items:
                    state.config.playlist = items
                    log.info(
                        "rescan (one-shot): '%s' → %d files",
                        state.config.name, len(items),
                    )
                for warn in warnings:
                    log.warning("rescan: %s", warn)
            except Exception as exc:
                log.error("rescan failed for '%s': %s", state.config.name, exc)

    def stop_all(self) -> None:
        with self._lock:
            for w in self._watchers.values():
                w.stop()
            self._watchers.clear()
