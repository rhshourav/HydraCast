"""
hc/manager.py  —  StreamManager: orchestrates workers, scheduler, event loop.

v6.0 fixes
──────────
• Replaced csv_manager.CSVManager import with json_manager.JSONManager.
• Added all methods that web.py calls but were missing from this class:
    start(name)              — start stream by name (web.py uses name, not state)
    stop(name)               — stop stream by name
    restart(name)            — restart stream by name
    get_worker(name)         — return the StreamWorker for a stream
    add_event(ev)            — append a pre-built OneShotEvent and persist
    remove_event(ev_id)      — remove one event by id, return True/False
    remove_events(id_set)    — bulk-remove events by id set, return count
    fire_event_now(ev_id)    — immediately trigger a scheduled event
    reload_from_configs(...) — replace in-memory state from a new config list

v5.2 additions (Web UI stream management):
  • add_stream(config)    — add a new stream at runtime and persist to JSON.
  • remove_stream(name)   — stop and remove a stream at runtime and persist to JSON.

v5.1 additions:
  • FolderWatcherRegistry — live folder monitoring for folder-source streams.
  • rescan_folder(state)  — force immediate folder rescan (TUI F key).
  • clear_error(state)    — clear ERROR status and reset restart counter (TUI C key).
  • reload_csv()          — hot-reload streams.json without restarting LIVE streams.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from hc.json_manager import JSONManager
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
        self._fw_registry = FolderWatcherRegistry(glog)

    # ── Worker factory ─────────────────────────────────────────────────────────
    def _worker(self, state: StreamState) -> StreamWorker:
        if state.config.name not in self._workers:
            self._workers[state.config.name] = StreamWorker(state, self._glog)
        return self._workers[state.config.name]

    def get_worker(self, name: str) -> Optional[StreamWorker]:
        """Return the StreamWorker for *name*, or None if not found."""
        return self._workers.get(name)

    # ── Name-based control API (used by web.py) ────────────────────────────────
    def start(self, name: str) -> None:
        """Start stream by name."""
        st = self.get_state(name)
        if st:
            self.start_stream(st)

    def stop(self, name: str) -> None:
        """Stop stream by name."""
        st = self.get_state(name)
        if st:
            self.stop_stream(st)

    def restart(self, name: str) -> None:
        """Restart stream by name."""
        st = self.get_state(name)
        if st:
            self.restart_stream(st)

    # ── State-based control API (used internally / TUI) ───────────────────────
    def start_stream(self, state: StreamState) -> None:
        if state.status in (StreamStatus.LIVE, StreamStatus.STARTING):
            return
        state.playlist_index = 0
        state.playlist_order = []
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

    # ── Event management (web.py API) ─────────────────────────────────────────
    def add_event(self, ev: OneShotEvent) -> None:
        """Append a pre-built OneShotEvent and persist it."""
        self.events.append(ev)
        JSONManager._save_events(self.events)
        self._glog.add(
            f"[{ev.stream_name}] Event scheduled: {ev.file_path.name} "
            f"@ {ev.play_at.strftime('%Y-%m-%d %H:%M')}",
            "INFO",
        )

    def remove_event(self, ev_id: str) -> bool:
        """Remove a single event by id. Returns True if found and removed."""
        before = len(self.events)
        self.events = [e for e in self.events if e.event_id != ev_id]
        if len(self.events) < before:
            JSONManager._save_events(self.events)
            return True
        return False

    def remove_events(self, id_set: Set[str]) -> int:
        """Bulk-remove events by id set. Returns count removed."""
        before = len(self.events)
        self.events = [e for e in self.events if e.event_id not in id_set]
        removed = before - len(self.events)
        if removed:
            JSONManager._save_events(self.events)
        return removed

    def fire_event_now(self, ev_id: str) -> bool:
        """Immediately trigger a scheduled event. Returns True if fired."""
        ev = next((e for e in self.events if e.event_id == ev_id), None)
        if ev is None:
            return False
        for s in self.states:
            if s.config.name == ev.stream_name:
                w = self._workers.get(s.config.name)
                if w:
                    ev.played = True
                    JSONManager.mark_event_played(self.events, ev_id)
                    self._glog.add(
                        f"[{s.config.name}] Manual fire: {ev.file_path.name}", "INFO"
                    )
                    threading.Thread(
                        target=lambda w=w, ev=ev: w.play_oneshot(ev),
                        daemon=True,
                    ).start()
                    return True
        return False

    # ── Add / remove streams at runtime (web.py) ──────────────────────────────
    def add_stream(self, config: StreamConfig) -> None:
        """Add a new stream and persist. Raises ValueError on duplicates."""
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
        JSONManager.save([s.config for s in self.states])
        logging.info("Stream added: '%s' (port %d)", config.name, config.port)
        self._glog.add(
            f"[{config.name}] Stream added via Web UI (port {config.port}).", "INFO"
        )

    def remove_stream(self, name: str) -> None:
        """Stop and remove a stream. Raises ValueError if not found."""
        state = self.get_state(name)
        if state is None:
            raise ValueError(f"Stream '{name}' not found.")
        if state.status in (StreamStatus.LIVE, StreamStatus.STARTING):
            w = self._workers.get(name)
            if w:
                w.stop()
        try:
            self._fw_registry.unregister(state)
        except Exception:
            pass
        self.states  = [s for s in self.states if s.config.name != name]
        self._workers.pop(name, None)
        JSONManager.save([s.config for s in self.states])
        logging.info("Stream removed: '%s'", name)
        self._glog.add(f"[{name}] Stream removed via Web UI.", "INFO")

    # ── Reload from config list (used by backup/restore in web.py) ────────────
    def reload_from_configs(self, new_configs: List[StreamConfig]) -> None:
        """
        Replace in-memory stream state from a freshly loaded config list.
        LIVE streams whose name still appears keep their running workers.
        """
        new_by_name      = {c.name: c for c in new_configs}
        existing_by_name = {s.config.name: s for s in self.states}

        # Stop streams removed from the new config.
        for name, state in existing_by_name.items():
            if name not in new_by_name:
                if state.status in (StreamStatus.LIVE, StreamStatus.STARTING):
                    w = self._workers.get(name)
                    if w:
                        w.stop()
                self._workers.pop(name, None)

        new_states: List[StreamState] = []
        for cfg in new_configs:
            existing = existing_by_name.get(cfg.name)
            if existing:
                existing.config = cfg
                new_states.append(existing)
            else:
                new_states.append(StreamState(config=cfg))

        self.states = new_states
        self._glog.add(
            f"Manager reloaded: {len(new_configs)} stream(s) from restore.", "INFO"
        )

    # ── Folder rescan (TUI F key) ─────────────────────────────────────────────
    def rescan_folder(self, state: StreamState) -> None:
        cfg = state.config
        if cfg.folder_source is None:
            if cfg.playlist and cfg.playlist[0].file_path.is_dir():
                cfg.folder_source = cfg.playlist[0].file_path
                self._glog.add(
                    f"[{cfg.name}] Promoted folder_source: {cfg.folder_source.name}",
                    "INFO",
                )
            else:
                self._glog.add(
                    f"[{cfg.name}] rescan_folder: not a folder-source stream.", "WARN"
                )
                return
        self._fw_registry.register(state)
        self._fw_registry.rescan(state)
        self._glog.add(
            f"[{cfg.name}] Folder rescan triggered: {cfg.folder_source.name}", "INFO"
        )

    # ── Clear error (TUI C key) ───────────────────────────────────────────────
    def clear_error(self, state: StreamState) -> None:
        state.error_msg     = ""
        state.restart_count = 0
        if state.status == StreamStatus.ERROR:
            state.status = StreamStatus.STOPPED
        msg = f"[{state.config.name}] Error cleared — ready to restart."
        state.log_add(msg)
        self._glog.add(msg, "INFO")

    # ── Hot JSON reload (TUI L key) ───────────────────────────────────────────
    def reload_csv(self) -> None:
        """Re-read streams.json and update in-memory config without disrupting LIVE streams."""
        try:
            new_configs: List[StreamConfig] = JSONManager.load()
        except Exception as exc:
            self._glog.add(f"reload_csv failed: {exc}", "ERROR")
            return

        new_by_name:    Dict[str, StreamConfig] = {c.name: c for c in new_configs}
        existing_names: Set[str]                = {s.config.name for s in self.states}

        updated = 0
        for state in self.states:
            nc = new_by_name.get(state.config.name)
            if nc is None:
                continue
            cfg       = state.config
            is_active = state.status in (StreamStatus.LIVE, StreamStatus.STARTING)
            cfg.weekdays           = nc.weekdays
            cfg.enabled            = nc.enabled
            cfg.shuffle            = nc.shuffle
            cfg.video_bitrate      = nc.video_bitrate
            cfg.audio_bitrate      = nc.audio_bitrate
            cfg.compliance_enabled = nc.compliance_enabled
            cfg.compliance_start   = nc.compliance_start
            cfg.compliance_loop    = nc.compliance_loop
            if not is_active:
                cfg.playlist    = nc.playlist
                cfg.stream_path = nc.stream_path
                cfg.hls_enabled = nc.hls_enabled
                if nc.folder_source != cfg.folder_source:
                    cfg.folder_source = nc.folder_source
                    if cfg.folder_source:
                        self._fw_registry.register(state)
            updated += 1

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
                                JSONManager.mark_event_played(self.events, ev.event_id)
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

    def health_summary(self) -> dict:
        return {
            "total":     len(self.states),
            "live":      sum(1 for s in self.states if s.status == StreamStatus.LIVE),
            "stopped":   sum(1 for s in self.states if s.status == StreamStatus.STOPPED),
            "error":     sum(1 for s in self.states if s.status == StreamStatus.ERROR),
            "scheduled": sum(1 for s in self.states if s.status == StreamStatus.SCHEDULED),
            "disabled":  sum(1 for s in self.states if s.status == StreamStatus.DISABLED),
        }
