"""
hc/manager.py  —  StreamManager: orchestrates workers, scheduler, event loop.

v6.3 changes
─────────────
• start_all() stagger changed from "groups of 4 × 400 ms" to a true
  per-stream 2-second gap.  Each stream thread is spawned 2 s after the
  previous one, so the UI shows streams coming up one-by-one rather than
  in bursts.  The hard port-binding serialisation is still handled by the
  _RECONNECT_SEM in worker.py; this delay is purely the visible stagger.

v6.2 changes
─────────────
• start_stream() gains a `fresh_start` parameter (default False).
  Only a fresh_start=True call resets playlist_index/order to 0 — manual
  Start button, start_all(), and event-loop auto-starts pass True.
  Scheduler loop restarts (start_stream called because stream stopped
  unexpectedly) and _auto_restart() in worker.py pass the default False
  so playlist sequencing is preserved across restarts.

• start_all() staggers stream launches in groups of 4 with a 400 ms pause
  between groups (superseded in v6.3 — see above).


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

log = logging.getLogger(__name__)


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
        return self._workers.get(name)

    # ── Name-based control API (used by web.py) ────────────────────────────────
    def start(self, name: str) -> None:
        st = self.get_state(name)
        if st:
            self.start_stream(st, fresh_start=True)

    def stop(self, name: str) -> None:
        st = self.get_state(name)
        if st:
            self.stop_stream(st)

    def restart(self, name: str) -> None:
        st = self.get_state(name)
        if st:
            self.restart_stream(st)

    # ── State-based control API (used internally / TUI) ───────────────────────
    def start_stream(self, state: StreamState, fresh_start: bool = False) -> None:
        if state.status in (StreamStatus.LIVE, StreamStatus.STARTING, StreamStatus.ONESHOT):
            return
        # Block while _after() owns the resume cycle.  state.resuming is set
        # synchronously by play_oneshot() before _after() spawns its thread,
        # so this guard fires even if the scheduler races _after() on the same
        # clock tick.  Without this the scheduler sees status=ERROR (from the
        # Broken Pipe FFmpeg gets when _cycle_mediamtx kills MediaMTX) and
        # calls start_stream(), which races _cycle_mediamtx and corrupts ports.
        if state.resuming:
            return
        # Bug 9 fix: block while _auto_restart() is in its backoff countdown.
        # _auto_restart() sets status = STOPPED/ERROR but restarting = True.
        # The scheduler fires every 60 s and sees active=False, then calls
        # start_stream() — which races the _auto_restart() thread's _do_start()
        # call.  The _start_lock prevents two _do_start() calls from running
        # simultaneously but the second one blocks for 20 s then proceeds,
        # potentially starting a duplicate stream after _auto_restart() already
        # succeeded.  Returning early here avoids that race entirely.
        if getattr(state, "restarting", False):
            return
        # Only reset playlist position on an explicit fresh start (e.g. manual
        # Start button press, first launch).  Auto-restarts triggered by the
        # scheduler, _auto_restart(), or a broken-pipe loop must NOT reset to
        # index 0 — that breaks multi-file playlist sequencing by always
        # replaying the first file instead of continuing from where we left off.
        if fresh_start:
            state.playlist_index = 0
            state.playlist_order = []
        # Clear any stale initial_offset from a previous compliance start —
        # _apply_compliance_start() below will set it correctly if needed.
        state.initial_offset = 0.0

        # Compliance: select today's file and set initial seek offset
        if state.config.compliance_enabled:
            self._apply_compliance_start(state)

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
        # ── Staggered launch (v6.3) ───────────────────────────────────────────
        # Each stream is started with a 2-second gap between launches.
        #
        # Why 2 s per stream (not the old 4-streams-then-400 ms group model):
        #   • The slow-preset encoder is more CPU-intensive than ultrafast; the
        #     OS needs a bit more time for each MediaMTX + FFmpeg pair to settle.
        #   • The _do_start() boot-jitter (port % 20 × 0.25 s, up to 4 s) and
        #     the _RECONNECT_SEM (limit 4 concurrent launches) already handle the
        #     hard port-binding serialisation.  This outer delay is simply a
        #     human-visible "one stream at a time" stagger so the UI shows
        #     streams coming up gradually rather than all at once.
        #   • 2 s × 22 streams = 44 s total, well within the scheduler's 70 s
        #     initial delay before it starts watching for stopped streams.
        #
        # start_stream() spawns a daemon thread, so the sleep here does NOT
        # block the thread that already started — it only spaces out when each
        # new thread is born.
        for i, s in enumerate(self.states):
            if not s.config.enabled:
                s.status = StreamStatus.DISABLED
            elif s.config.is_scheduled_today():
                self.start_stream(s, fresh_start=True)
                # 2 s between each stream start so launches are clearly
                # sequential.  The semaphore in _do_start() handles the hard
                # port-binding cap; this delay is the visible stagger.
                if i < len(self.states) - 1:
                    time.sleep(2.0)
            else:
                if s.config.folder_source:
                    self._fw_registry.register(s)
                s.status = StreamStatus.SCHEDULED

    def stop_all(self) -> None:
        for s in self.states:
            self.stop_stream(s)

    # ── Compliance helpers ────────────────────────────────────────────────────

    def _apply_compliance_start(
        self,
        state: StreamState,
        reference_time: Optional[datetime] = None,
    ) -> None:
        """
        Select the correct day-tagged file, compute the seek offset, and
        inject both into *state* so the worker starts at the right position.
        Sets a compliance alert if anything goes wrong.
        """
        from hc.compliance import prepare_compliance_start

        cfg = state.config
        try:
            item, seek, explanation, alert = prepare_compliance_start(
                playlist        = cfg.playlist,
                broadcast_start = cfg.compliance_start,
                loop_calculation= cfg.compliance_loop,
                video_duration  = state.duration,   # 0 on first start — OK
                reference_time  = reference_time,
            )
        except Exception as exc:
            alert = f"Compliance error: {exc}"
            log.error("[%s] %s", cfg.name, alert)
            if cfg.compliance_alert_enabled:
                state.set_compliance_alert(alert)
            return

        if alert and cfg.compliance_alert_enabled:
            state.set_compliance_alert(alert)
        elif not alert:
            state.clear_compliance_alert()

        if item is not None:
            # Pin the playlist to the selected item so the worker starts here.
            try:
                idx = cfg.playlist.index(item)
                state.playlist_index = idx
            except ValueError:
                pass

        if seek > 0:
            state.initial_offset = seek
            state.seek_target    = seek
            log.info("[%s] Compliance seek: %s", cfg.name, explanation)

    def _resume_compliance(
        self,
        state: StreamState,
        event_end_time: datetime,
    ) -> None:
        """
        Called after a one-shot event finishes.  Reselects the compliance file
        for today and seeks to the correct position as of *event_end_time*.
        """
        from hc.compliance import (
            select_compliance_file,
            calculate_compliance_offset_after_event,
        )

        cfg = state.config
        if not cfg.compliance_enabled:
            return

        item, file_error = select_compliance_file(cfg.playlist)
        if item is not None:
            try:
                idx = cfg.playlist.index(item)
                state.playlist_index = idx
            except ValueError:
                pass

        seek, explanation = calculate_compliance_offset_after_event(
            event_end_time  = event_end_time,
            video_duration  = state.duration,
            broadcast_start = cfg.compliance_start,
            loop_calculation= cfg.compliance_loop,
        )

        alert = file_error
        if alert and cfg.compliance_alert_enabled:
            state.set_compliance_alert(alert)
        elif not alert:
            state.clear_compliance_alert()

        if seek > 0:
            state.seek_target = seek
            log.info("[%s] Post-event compliance resume: %s", cfg.name, explanation)

        # Ask the worker to restart from the new position
        w = self._workers.get(cfg.name)
        if w:
            threading.Thread(
                target=w.restart, daemon=True,
                name=f"comp-resume-{cfg.port}",
            ).start()

    # ── Event management (web.py API) ─────────────────────────────────────────
    def add_event(self, ev: OneShotEvent) -> None:
        self.events.append(ev)
        JSONManager._save_events(self.events)
        self._glog.add(
            f"[{ev.stream_name}] Event scheduled: {ev.file_path.name} "
            f"@ {ev.play_at.strftime('%Y-%m-%d %H:%M')}",
            "INFO",
        )

    def remove_event(self, ev_id: str) -> bool:
        before = len(self.events)
        self.events = [e for e in self.events if e.event_id != ev_id]
        if len(self.events) < before:
            JSONManager._save_events(self.events)
            return True
        return False

    def remove_events(self, id_set: Set[str]) -> int:
        before = len(self.events)
        self.events = [e for e in self.events if e.event_id not in id_set]
        removed = before - len(self.events)
        if removed:
            JSONManager._save_events(self.events)
        return removed

    def fire_event_now(self, ev_id: str) -> bool:
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

    # ── Stream CRUD (web.py) ──────────────────────────────────────────────────
    def add_stream(self, config: StreamConfig) -> StreamState:
        state = StreamState(config=config)
        self.states.append(state)
        if config.folder_source:
            self._fw_registry.register(state)
        JSONManager.save([s.config for s in self.states])
        self._glog.add(f"[{config.name}] Stream added.", "INFO")
        return state

    def remove_stream(self, name: str) -> bool:
        st = self.get_state(name)
        if st is None:
            return False
        self.stop_stream(st)
        self._fw_registry.unregister(st)
        self.states = [s for s in self.states if s.config.name != name]
        self._workers.pop(name, None)
        JSONManager.save([s.config for s in self.states])
        self._glog.add(f"[{name}] Stream removed.", "INFO")
        return True

    def reload_from_configs(self, new_configs: List[StreamConfig]) -> None:
        new_by_name = {c.name: c for c in new_configs}
        for state in self.states:
            nc = new_by_name.get(state.config.name)
            if nc is None:
                continue
            is_active = state.status in (StreamStatus.LIVE, StreamStatus.STARTING)
            cfg = state.config
            cfg.weekdays                = nc.weekdays
            cfg.enabled                 = nc.enabled
            cfg.shuffle                 = nc.shuffle
            cfg.video_bitrate           = nc.video_bitrate
            cfg.audio_bitrate           = nc.audio_bitrate
            cfg.compliance_enabled      = nc.compliance_enabled
            cfg.compliance_start        = nc.compliance_start
            cfg.compliance_loop         = nc.compliance_loop
            cfg.compliance_alert_enabled= nc.compliance_alert_enabled
            if not is_active:
                cfg.playlist    = nc.playlist
                cfg.stream_path = nc.stream_path
                cfg.hls_enabled = nc.hls_enabled
                if nc.folder_source != cfg.folder_source:
                    cfg.folder_source = nc.folder_source
                    if cfg.folder_source:
                        self._fw_registry.register(state)

        existing = {s.config.name for s in self.states}
        for name, nc in new_by_name.items():
            if name not in existing:
                ns = StreamState(config=nc)
                self.states.append(ns)
                self._fw_registry.register(ns)

    # ── Folder utilities ──────────────────────────────────────────────────────
    def rescan_folder(self, state: StreamState) -> None:
        cfg = state.config
        if cfg.folder_source is None:
            if cfg.playlist and cfg.playlist[0].file_path.is_dir():
                cfg.folder_source = cfg.playlist[0].file_path
            else:
                self._glog.add(f"[{cfg.name}] rescan_folder: not a folder-source stream.", "WARN")
                return
        self._fw_registry.register(state)
        self._fw_registry.rescan(state)
        self._glog.add(f"[{cfg.name}] Folder rescan triggered: {cfg.folder_source.name}", "INFO")

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
        try:
            new_configs: List[StreamConfig] = JSONManager.load()
        except Exception as exc:
            self._glog.add(f"reload_csv failed: {exc}", "ERROR")
            return
        self.reload_from_configs(new_configs)
        self._glog.add("streams.json reloaded.", "INFO")

    # ── Scheduler loop ────────────────────────────────────────────────────────
    def _scheduler_loop(self) -> None:
        # Cold-start race fix: the scheduler's first iteration must not fire
        # until start_all() has finished launching all streams.  start_all()
        # staggers 22 streams in groups of 4 × 400 ms ≈ 2.2 s, but _do_start()
        # adds up to 4.75 s of per-stream boot jitter on top of that.  The
        # worst-case time for the last stream to call _start_mediamtx() is
        # approximately 4.75 s + the time to pass through the semaphore (up to
        # 3 × 11 s ≈ 33 s in a fully-serialised cold start).  A 70 s initial
        # sleep safely clears that window.  After the first tick the loop
        # returns to its normal 60 s cadence.
        #
        # Without this delay the scheduler fires at t=0, sees every stream as
        # status=STOPPED (threads are still inside _do_start()), and calls
        # start_stream() for every stream simultaneously — completely bypassing
        # the stagger in start_all() and the boot jitter in _do_start(), which
        # is exactly the storm that produces the "listen udp4: bind: Only one
        # usage of each socket address" errors at cold start.
        _initial_delay_ticks = 700  # 70 s × 10 ticks/s
        for _ in range(_initial_delay_ticks):
            if not self._running:
                return
            time.sleep(0.1)

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
        # Track events currently being played so we can detect completion.
        # NOTE: ev.played is set to True at FIRE time (to prevent re-firing),
        # NOT at completion time. Completion/resume is handled entirely by the
        # _after() callback inside StreamWorker.play_oneshot(). Calling
        # _resume_compliance() from here races with _cycle_mediamtx() inside
        # play_oneshot() — both try to kill/restart MediaMTX simultaneously,
        # which causes MediaMTX to exit immediately (code 1, no log output)
        # because the port is momentarily double-bound.
        _playing: Dict[str, datetime] = {}  # event_id → fired_at (tracking only)
        # Track events that are due but whose stream isn't live yet, so we
        # can retry them once the stream comes up (up to 5 minutes late).
        _pending: Dict[str, datetime] = {}  # event_id → first_due_at

        while self._running:
            now = datetime.now()

            for ev in self.events:
                if ev.played:
                    # Clean up tracking only — do NOT call _resume_compliance()
                    # here. play_oneshot()._after() already handles resume
                    # (compliance seek + MediaMTX cycle + FFmpeg restart).
                    # Calling w.restart() here while _cycle_mediamtx() is still
                    # running in the oneshot thread causes MediaMTX to be killed
                    # and restarted twice simultaneously, corrupting the port state.
                    _playing.pop(ev.event_id, None)
                    _pending.pop(ev.event_id, None)
                    continue

                delta = (ev.play_at - now).total_seconds()

                # Mark event as pending (due) once we're within 5 s of play_at.
                # Keep retrying for up to 5 minutes in case the stream starts late.
                if delta <= 5:
                    if ev.event_id not in _pending:
                        if delta >= -300:
                            # Due within the last 5 minutes — enter pending queue.
                            _pending[ev.event_id] = now
                        else:
                            # More than 5 minutes overdue and never entered pending
                            # (e.g. app was offline when it was supposed to fire).
                            # Mark played so it doesn't fire stale.
                            ev.played = True
                            JSONManager.mark_event_played(self.events, ev.event_id)
                            self._glog.add(
                                f"[{ev.stream_name}] Skipping stale event "
                                f"({ev.file_path.name}, "
                                f"{abs(int(delta))//60}m overdue).",
                                "WARN",
                            )
                            continue

                if ev.event_id not in _pending:
                    continue  # Not due yet

                # Event is pending — try to fire it
                first_due = _pending[ev.event_id]
                overdue_secs = (now - first_due).total_seconds()

                for s in self.states:
                    if s.config.name != ev.stream_name:
                        continue

                    w = self._workers.get(s.config.name)
                    stream_live = s.status in (StreamStatus.LIVE, StreamStatus.ONESHOT)

                    if not stream_live:
                        # Stream isn't live — auto-start it so the event can fire
                        if overdue_secs < 30:
                            # Give it up to 30 s for the stream to come up
                            if s.status not in (StreamStatus.STARTING,):
                                self._glog.add(
                                    f"[{s.config.name}] Event due but stream not live "
                                    f"— auto-starting for event: {ev.file_path.name}",
                                    "WARN",
                                )
                                self.start_stream(s)
                        elif overdue_secs < 300:
                            # Still waiting for stream — log once per minute
                            if int(overdue_secs) % 60 < 5:
                                self._glog.add(
                                    f"[{s.config.name}] Waiting for stream to start "
                                    f"before firing event ({int(overdue_secs)}s elapsed).",
                                    "WARN",
                                )
                        else:
                            # 5-minute timeout — give up
                            ev.played = True
                            _pending.pop(ev.event_id, None)
                            JSONManager.mark_event_played(self.events, ev.event_id)
                            self._glog.add(
                                f"[{s.config.name}] Event timed out — stream never "
                                f"came live in 5 min: {ev.file_path.name}",
                                "ERROR",
                            )
                        break

                    # Stream is live — fire the event
                    if w is None:
                        w = self._worker(s)

                    ev.played = True
                    _playing[ev.event_id] = now
                    _pending.pop(ev.event_id, None)
                    JSONManager.mark_event_played(self.events, ev.event_id)
                    self._glog.add(
                        f"[{s.config.name}] Firing one-shot: "
                        f"{ev.file_path.name}", "INFO")
                    threading.Thread(
                        target=lambda w=w, ev=ev: w.play_oneshot(ev),
                        daemon=True,
                        name=f"oneshot-fire-{s.config.port}",
                    ).start()
                    break

            for _ in range(10):   # 1-second tick (was 5 s) — don't miss narrow windows
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
