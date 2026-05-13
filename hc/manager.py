"""
hc/manager.py  —  StreamManager: orchestrates workers, scheduler, event loop.

v6.0 fix
─────────
• Replaced `from hc.csv_manager import CSVManager` with JSONManager.
  csv_manager.py was removed in v6.0; the old import caused an immediate
  ImportError on startup, preventing the app from loading at all.

  Call-site mapping (old → new):
    CSVManager.load_events()             → JSONManager.load_events()
    CSVManager.load()                    → JSONManager.load()
    CSVManager.save(configs)             → JSONManager.save(configs)
    CSVManager.mark_event_played(...)    → JSONManager.mark_event_played(...)

v5.1 additions:
  • FolderWatcherRegistry — live folder monitoring for folder-source streams.
  • rescan_folder(state)  — force immediate folder rescan (TUI F key).
  • clear_error(state)    — clear ERROR status and reset restart counter (TUI C key).
  • reload_csv()          — hot-reload streams.json without restarting LIVE streams
                            (TUI L key).

v5.2 additions (Web UI stream management):
  • add_stream(config)    — add a new stream at runtime and persist to JSON.
  • remove_stream(name)   — stop and remove a stream at runtime and persist to JSON.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from hc.json_manager import JSONManager          # ← was csv_manager.CSVManager
from hc.folder_watcher import FolderWatcherRegistry
from hc.models import OneShotEvent, StreamConfig, StreamState, StreamStatus
from hc.worker import LogBuffer, StreamWorker


class StreamManager:

    def __init__(self, configs: List[StreamConfig], glog: LogBuffer) -> None:
        self.states:   List[StreamState]        = [StreamState(config=c) for c in configs]
        self._workers: Dict[str, StreamWorker]  = {}
        self._glog    = glog
        self._running = False
        self._sched_t: Optional[threading.Thread] = None
        self._event_t: Optional[threading.Thread] = None
        self.events:   List[OneShotEvent]         = JSONManager.load_events()
        # Live folder watcher pool — one watcher thread per unique folder path.
        self._fw_registry = FolderWatcherRegistry(glog)

    # ── Worker factory ────────────────────────────────────────────────────────
    def _worker(self, state: StreamState) -> StreamWorker:
        if state.config.name not in self._workers:
            self._workers[state.config.name] = StreamWorker(state, self._glog)
        return self._workers[state.config.name]

    # ── Stream control ────────────────────────────────────────────────────────
    def start_stream(self, state: StreamState) -> None:
        if state.status in (StreamStatus.LIVE, StreamStatus.STARTING):
            return
        state.playlist_index = 0
        state.playlist_order = []
        # Register/refresh the folder watcher whenever a stream starts.
        if state.config.folder_source:
            self._fw_registry.register(state)
        w = self._worker(state)
        threading.Thread(target=w.start, daemon=True,
                         name=f"start-{state.config.port}").start()

    def stop_stream(self, state: StreamState) -> None:
        w = self._workers.get(state.config.name)
        if w:
            threading.Thread(target=w.stop, daemon=True,
                             name=f"stop-{state.config.port}").start()
        else:
            state.status = StreamStatus.STOPPED

    def restart_stream(self, state: StreamState) -> None:
        w = self._worker(state)
        threading.Thread(target=w.restart, daemon=True,
                         name=f"rst-{state.config.port}").start()

    def seek_stream(self, state: StreamState, seconds: float) -> None:
        if state.status != StreamStatus.LIVE:
            return
        w = self._workers.get(state.config.name)
        if w:
            threading.Thread(target=lambda: w.seek(seconds), daemon=True,
                             name=f"seek-{state.config.port}").start()

    def skip_next(self, state: StreamState) -> None:
        w = self._workers.get(state.config.name)
        if w:
            threading.Thread(target=w.skip_to_next, daemon=True,
                             name=f"skip-{state.config.port}").start()

    def start_all(self) -> None:
        for s in self.states:
            if not s.config.enabled:
                s.status = StreamStatus.DISABLED
            elif s.config.is_scheduled_today():
                self.start_stream(s)
            else:
                if s.config.folder_source:
                    self._fw_registry.register(s)
                s.status = StreamStatus.SCHEDULED

    def stop_all(self) -> None:
        for s in self.states:
            self.stop_stream(s)

    # ── Add / remove streams at runtime (Web UI) ──────────────────────────────
    def add_stream(self, config: StreamConfig) -> None:
        """
        Add a new stream config to the in-memory list and persist to
        streams.json.  The stream is created in STOPPED state; the Web UI
        can start it immediately via the start action.
        """
        # Guard against duplicates (name and port).
        for s in self.states:
            if s.config.name == config.name:
                raise ValueError(f"Stream '{config.name}' already exists.")
            if s.config.port == config.port:
                raise ValueError(
                    f"Port {config.port} is already used by '{s.config.name}'."
                )
        new_state = StreamState(config=config)
        self.states.append(new_state)
        if config.folder_source:
            self._fw_registry.register(new_state)
        # Persist
        JSONManager.save([s.config for s in self.states])
        logging.info(
            "Stream added: '%s' (port %d)", config.name, config.port
        )
        self._glog.add(
            f"[{config.name}] Stream added via Web UI (port {config.port}).",
            "INFO",
        )

    def remove_stream(self, name: str) -> None:
        """
        Stop a stream (if running) and remove it from the in-memory list,
        then persist to streams.json.  Raises ValueError if not found.
        """
        state = self.get_state(name)
        if state is None:
            raise ValueError(f"Stream '{name}' not found.")

        # Stop gracefully if active.
        if state.status in (StreamStatus.LIVE, StreamStatus.STARTING):
            w = self._workers.get(name)
            if w:
                w.stop()   # blocking stop so the port is released cleanly

        # Deregister folder watcher.
        try:
            self._fw_registry.unregister(state)
        except Exception:
            pass

        self.states  = [s for s in self.states if s.config.name != name]
        self._workers.pop(name, None)

        # Persist
        JSONManager.save([s.config for s in self.states])
        logging.info("Stream removed: '%s'", name)
        self._glog.add(f"[{name}] Stream removed via Web UI.", "INFO")

    # ── Folder rescan (TUI F key) ─────────────────────────────────────────────
    def rescan_folder(self, state: StreamState) -> None:
        """
        Force an immediate folder rescan for *state*.

        • If the stream has a folder_source, the watcher triggers a full
          rescan and updates cfg.playlist in-place.
        • If no folder_source is set but the first playlist entry is a
          directory, it is promoted to folder_source first.
        • Safe to call while the stream is LIVE — the updated playlist is
          picked up when the worker advances to the next file.
        """
        cfg = state.config

        # Auto-promote if folder_source not yet set.
        if cfg.folder_source is None:
            if cfg.playlist and cfg.playlist[0].file_path.is_dir():
                cfg.folder_source = cfg.playlist[0].file_path
                self._glog.add(
                    f"[{cfg.name}] Promoted folder_source: {cfg.folder_source.name}",
                    "INFO",
                )
            else:
                self._glog.add(
                    f"[{cfg.name}] rescan_folder: not a folder-source stream.",
                    "WARN",
                )
                return

        # Ensure a watcher is running for this folder.
        self._fw_registry.register(state)
        # Trigger the rescan.
        self._fw_registry.rescan(state)
        self._glog.add(
            f"[{cfg.name}] Folder rescan triggered: {cfg.folder_source.name}", "INFO"
        )

    # ── Clear error (TUI C key) ───────────────────────────────────────────────
    def clear_error(self, state: StreamState) -> None:
        """
        Clear an ERROR state and reset the restart counter so the auto-restart
        back-off starts fresh.  Does not restart the stream automatically.
        """
        state.error_msg    = ""
        state.restart_count = 0
        if state.status == StreamStatus.ERROR:
            state.status = StreamStatus.STOPPED
        msg = f"[{state.config.name}] Error cleared — ready to restart."
        state.log_add(msg)
        self._glog.add(msg, "INFO")

    # ── Hot JSON reload (TUI L key) ───────────────────────────────────────────
    def reload_csv(self) -> None:
        """
        Re-read streams.json and update in-memory config without restarting
        any currently-LIVE or STARTING streams.

        Fields updated for ALL streams (safe while running):
          weekdays, enabled, shuffle, video_bitrate, audio_bitrate,
          compliance_enabled, compliance_start, compliance_loop

        Fields updated only for STOPPED / SCHEDULED / ERROR streams:
          playlist, stream_path, hls_enabled, folder_source

        New streams (names that appear in the JSON but not in memory) are
        appended.  Streams removed from the JSON are left running until they
        stop naturally; they are then marked DISABLED.
        """
        try:
            new_configs: List[StreamConfig] = JSONManager.load()
        except Exception as exc:
            self._glog.add(f"reload_csv failed: {exc}", "ERROR")
            return

        new_by_name: Dict[str, StreamConfig] = {c.name: c for c in new_configs}
        existing_names = {s.config.name for s in self.states}

        updated = 0
        for state in self.states:
            nc = new_by_name.get(state.config.name)
            if nc is None:
                # Stream removed from JSON — mark disabled when it stops.
                continue

            cfg = state.config
            is_active = state.status in (StreamStatus.LIVE, StreamStatus.STARTING)

            # Always-safe field updates.
            cfg.weekdays             = nc.weekdays
            cfg.enabled              = nc.enabled
            cfg.shuffle              = nc.shuffle
            cfg.video_bitrate        = nc.video_bitrate
            cfg.audio_bitrate        = nc.audio_bitrate
            cfg.compliance_enabled   = nc.compliance_enabled
            cfg.compliance_start     = nc.compliance_start
            cfg.compliance_loop      = nc.compliance_loop

            # Destructive field updates — only apply when stream is idle.
            if not is_active:
                cfg.playlist      = nc.playlist
                cfg.stream_path   = nc.stream_path
                cfg.hls_enabled   = nc.hls_enabled
                # Update folder_source and re-register watcher if it changed.
                if nc.folder_source != cfg.folder_source:
                    cfg.folder_source = nc.folder_source
                    if cfg.folder_source:
                        self._fw_registry.register(state)

            updated += 1

        # Append genuinely new streams.
        added = 0
        for name, nc in new_by_name.items():
            if name not in existing_names:
                new_state = StreamState(config=nc)
                self.states.append(new_state)
                self._fw_registry.register(new_state)
                added += 1

        msg = f"streams.json reloaded — {updated} updated, {added} new."
        self._glog.add(msg, "INFO")
        logging.info(msg)

    # ── Scheduler loop ────────────────────────────────────────────────────────
    def _scheduler_loop(self) -> None:
        while self._running:
            for s in self.states:
                if not s.config.enabled:
                    s.status = StreamStatus.DISABLED
                    continue
                should = s.config.is_scheduled_today()
                active = s.status in (StreamStatus.LIVE, StreamStatus.STARTING)
                if should and not active:
                    self._glog.add(f"[{s.config.name}] Scheduler: starting.", "INFO")
                    self.start_stream(s)
                elif not should and active:
                    self._glog.add(f"[{s.config.name}] Scheduler: stopping.", "INFO")
                    self.stop_stream(s)
                elif not should and not active:
                    if s.status not in (StreamStatus.SCHEDULED, StreamStatus.DISABLED):
                        s.status = StreamStatus.SCHEDULED
            for _ in range(600):
                if not self._running:
                    return
                time.sleep(0.1)

    # ── One-shot event loop ───────────────────────────────────────────────────
    def _event_loop(self) -> None:
        while self._running:
            now = datetime.now()
            for ev in self.events:
                if ev.played:
                    continue
                delta = (ev.play_at - now).total_seconds()
                if -10 <= delta <= 5:
                    for s in self.states:
                        if s.config.name == ev.stream_name:
                            w = self._workers.get(s.config.name)
                            if w:
                                ev.played = True
                                JSONManager.mark_event_played(
                                    self.events, ev.event_id)
                                self._glog.add(
                                    f"[{s.config.name}] Firing one-shot: "
                                    f"{ev.file_path.name}", "INFO")
                                threading.Thread(
                                    target=lambda w=w, ev=ev: w.play_oneshot(ev),
                                    daemon=True,
                                ).start()
                            break
            for _ in range(50):
                if not self._running:
                    return
                time.sleep(0.1)

    def run_scheduler(self) -> None:
        self._running = True
        self._sched_t = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="scheduler")
        self._sched_t.start()
        self._event_t = threading.Thread(
            target=self._event_loop, daemon=True, name="eventloop")
        self._event_t.start()

    def shutdown(self) -> None:
        self._running = False
        self.stop_all()
        self._fw_registry.stop_all()
        deadline = time.time() + 12
        while time.time() < deadline:
            if not any(
                s.status in (StreamStatus.LIVE, StreamStatus.STARTING)
                for s in self.states
            ):
                break
            time.sleep(0.2)

    # ── Queries ───────────────────────────────────────────────────────────────
    def get_state(self, name: str) -> Optional[StreamState]:
        for s in self.states:
            if s.config.name == name:
                return s
        return None

    def export_urls(self, path: Optional[Path] = None) -> Path:
        from hc.constants import APP_VER, BASE_DIR
        from hc.utils import _local_ip
        out = path or (BASE_DIR() / "stream_urls.txt")
        lines = [
            f"# HydraCast {APP_VER} — Stream URLs",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for s in self.states:
            cfg = s.config
            lines += [
                f"[{cfg.name}]",
                f"  RTSP (local)    : {cfg.rtsp_url}",
                f"  RTSP (external) : {cfg.rtsp_url_external}",
            ]
            if cfg.hls_enabled:
                lines.append(f"  HLS             : {cfg.hls_url}")
            lines.append("")
        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    # ── Health summary ────────────────────────────────────────────────────────
    def health_summary(self) -> dict:
        return {
            "total":     len(self.states),
            "live":      sum(1 for s in self.states if s.status == StreamStatus.LIVE),
            "stopped":   sum(1 for s in self.states if s.status == StreamStatus.STOPPED),
            "error":     sum(1 for s in self.states if s.status == StreamStatus.ERROR),
            "scheduled": sum(1 for s in self.states if s.status == StreamStatus.SCHEDULED),
            "disabled":  sum(1 for s in self.states if s.status == StreamStatus.DISABLED),
        }
