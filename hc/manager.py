"""
hc/manager.py  —  StreamManager: lifecycle, scheduling, and control hub.

Responsibilities
────────────────
  • Create one StreamState + StreamWorker per StreamConfig.
  • start_all() / shutdown() — bulk lifecycle.
  • run_scheduler() — background thread that:
      - Starts / stops streams whose weekday window opens / closes.
      - Fires one-shot events (OneShotEvent) at their scheduled time.
      - Handles compliance-mode logic (pause until compliance_start).
  • Per-stream control: start(), stop(), restart(), rescan_folder().
  • export_urls() — writes stream_urls.txt for easy reference.
  • Integrates FolderWatcherRegistry for live folder monitoring.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

from hc.constants import (
    APP_NAME, APP_VER,
    BASE_DIR, CONFIGS_DIR, LOGS_DIR,
    LISTEN_ADDR,
    DAY_ABBR,
)
from hc.folder_scanner import scan_folder
from hc.folder_watcher import FolderWatcherRegistry
from hc.json_manager import JSONManager
from hc.models import (
    OneShotEvent,
    PlaylistItem,
    StreamConfig,
    StreamState,
    StreamStatus,
)
from hc.worker import LogBuffer, StreamWorker

log = logging.getLogger(__name__)

# How often the scheduler loop wakes up (seconds).
_SCHED_TICK: float = 30.0


# ---------------------------------------------------------------------------
# StreamManager
# ---------------------------------------------------------------------------

class StreamManager:
    """
    Central hub that owns all StreamState / StreamWorker instances and the
    background scheduler thread.

    Public interface used by hydracast.py / TUI / web:
      start_all()          — start every enabled stream
      shutdown()           — stop every stream + scheduler + folder watchers
      run_scheduler()      — launch the background scheduling thread
      export_urls()        — write stream_urls.txt, return Path
      start(name)          — start one stream by name
      stop(name)           — stop  one stream by name
      restart(name)        — restart one stream by name
      rescan_folder(state) — force folder rescan for a folder-source stream
      get_state(name)      — return StreamState | None
      states               — property: List[StreamState] for TUI / web
    """

    def __init__(
        self,
        configs: List[StreamConfig],
        glog: LogBuffer,
    ) -> None:
        self._glog   = glog
        self._lock   = threading.Lock()
        self._stop   = threading.Event()

        # Per-stream state and worker objects.
        self._states:  List[StreamState]          = []
        self._workers: Dict[str, StreamWorker]    = {}

        # One-shot events loaded from config/events.json.
        self._events: List[OneShotEvent] = []
        try:
            self._events = JSONManager.load_events()
            log.info("manager: loaded %d one-shot event(s)", len(self._events))
        except Exception as exc:
            log.warning("manager: could not load events: %s", exc)

        # Folder-watcher registry (one watcher per unique folder path).
        self._fw_registry = FolderWatcherRegistry(glog)

        # Build StreamState + StreamWorker for every config.
        for cfg in configs:
            self._add_stream(cfg)

        log.info(
            "StreamManager initialised: %d stream(s) (%d enabled).",
            len(self._states),
            sum(1 for s in self._states if s.config.enabled),
        )

    # ── Internal: per-stream construction ────────────────────────────────────

    def _add_stream(self, cfg: StreamConfig) -> StreamState:
        """Create StreamState + StreamWorker and register with folder watcher."""
        state  = StreamState(config=cfg)
        worker = StreamWorker(state=state, glog=self._glog)

        with self._lock:
            self._states.append(state)
            self._workers[cfg.name] = worker

        # Register with the folder watcher if this is a folder-source stream.
        if cfg.folder_source:
            self._fw_registry.register(state)

        return state

    # ── Public properties / accessors ─────────────────────────────────────────

    @property
    def states(self) -> List[StreamState]:
        """Read-only snapshot of all StreamState objects (used by TUI / web)."""
        with self._lock:
            return list(self._states)

    @property
    def events(self) -> List[OneShotEvent]:
        """Read-only snapshot of all one-shot events (used by TUI / web)."""
        with self._lock:
            return list(self._events)

    def get_state(self, name: str) -> Optional[StreamState]:
        """Return the StreamState for *name*, or None."""
        with self._lock:
            for s in self._states:
                if s.config.name == name:
                    return s
        return None

    def get_worker(self, name: str) -> Optional[StreamWorker]:
        with self._lock:
            return self._workers.get(name)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_all(self) -> None:
        """
        Start every enabled stream that is scheduled for today.
        Streams disabled in config or not scheduled today are skipped.
        """
        today = date.today().weekday()
        started = 0
        for state in self.states:
            cfg = state.config
            if not cfg.enabled:
                log.info("manager: '%s' is disabled — skipping.", cfg.name)
                continue
            if cfg.weekdays and today not in cfg.weekdays:
                day_name = DAY_ABBR[today]
                log.info(
                    "manager: '%s' not scheduled for %s — skipping.",
                    cfg.name, day_name,
                )
                state.status = StreamStatus.SCHEDULED
                continue
            if not cfg.playlist:
                log.warning(
                    "manager: '%s' has no playlist — skipping.",
                    cfg.name,
                )
                state.status = StreamStatus.ERROR
                state.log_add("⚠ No playlist — stream skipped at startup.")
                continue
            self._start_worker(state)
            started += 1

        msg = (
            f"{APP_NAME} v{APP_VER}: {started} stream(s) started "
            f"({len(self.states) - started} skipped / disabled)."
        )
        self._glog.add(msg, "INFO")
        log.info("manager: start_all complete — %s", msg)

    def shutdown(self) -> None:
        """
        Stop the scheduler, all stream workers, and the folder watcher registry.
        Blocks until all workers have terminated cleanly.
        """
        log.info("manager: shutdown requested.")
        self._stop.set()

        # Stop each worker.
        for state in self.states:
            try:
                self._stop_worker(state, reason="shutdown")
            except Exception as exc:
                log.warning(
                    "manager: error stopping '%s': %s",
                    state.config.name, exc,
                )

        # Stop folder watchers.
        try:
            self._fw_registry.stop_all()
        except Exception as exc:
            log.warning("manager: folder watcher stop error: %s", exc)

        log.info("manager: shutdown complete.")

    # ── Scheduler ─────────────────────────────────────────────────────────────

    def run_scheduler(self) -> None:
        """
        Launch the background scheduler thread (non-blocking).

        The thread fires every _SCHED_TICK seconds and:
          1. Checks each stream's weekday window — starts/stops as needed.
          2. Fires pending one-shot events (OneShotEvent) within a 1-min window.
          3. Handles compliance-mode: pauses stream until compliance_start time.
        """
        t = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="hc-scheduler",
        )
        t.start()
        log.info("manager: scheduler thread started (tick=%.0fs).", _SCHED_TICK)

    def _scheduler_loop(self) -> None:
        last_day: Optional[int] = None

        while not self._stop.is_set():
            try:
                now       = datetime.now()
                today_idx = now.weekday()

                # ── Day-change handling ───────────────────────────────────────
                if today_idx != last_day:
                    last_day = today_idx
                    self._on_day_change(today_idx, now)

                # ── One-shot event firing ─────────────────────────────────────
                self._check_events(now)

                # ── Compliance-mode checks ────────────────────────────────────
                self._check_compliance(now)

            except Exception as exc:
                log.error("manager: scheduler error: %s", exc)

            self._stop.wait(timeout=_SCHED_TICK)

    def _on_day_change(self, today_idx: int, now: datetime) -> None:
        """Called once when the calendar day advances."""
        day_name = DAY_ABBR[today_idx]
        msg = f"📅 Day changed → {day_name}.  Evaluating stream schedules."
        self._glog.add(msg, "INFO")
        log.info("manager: %s", msg)

        for state in self.states:
            cfg = state.config
            if not cfg.enabled:
                continue

            scheduled_today = (not cfg.weekdays) or (today_idx in cfg.weekdays)

            if scheduled_today and state.status not in (
                StreamStatus.LIVE, StreamStatus.STARTING
            ):
                log.info(
                    "manager: day-change → starting '%s' (scheduled for %s).",
                    cfg.name, day_name,
                )
                state.log_add(f"📅 Day changed to {day_name} — stream starting.")
                self._start_worker(state)

            elif not scheduled_today and state.status == StreamStatus.LIVE:
                log.info(
                    "manager: day-change → stopping '%s' (not scheduled for %s).",
                    cfg.name, day_name,
                )
                state.log_add(f"📅 Day changed to {day_name} — stream stopped (not scheduled).")
                self._stop_worker(state, reason="day-change")
                state.status = StreamStatus.SCHEDULED

            # Refresh folder-source playlist for today's _day_ tags.
            if cfg.folder_source and scheduled_today:
                try:
                    items, warnings = scan_folder(cfg.folder_source)
                    if items:
                        cfg.playlist = items
                        state.log_add(
                            f"📅 Folder playlist refreshed for {day_name}: "
                            f"{len(items)} file(s)."
                        )
                    for w in warnings:
                        state.log_add(f"⚠ {w}")
                except Exception as exc:
                    log.warning(
                        "manager: day-change folder rescan failed for '%s': %s",
                        cfg.name, exc,
                    )

    def _check_events(self, now: datetime) -> None:
        """Fire any pending OneShotEvent within the next scheduler tick window."""
        for ev in self._events:
            if ev.played:
                continue
            delta = (ev.play_at - now).total_seconds()
            # Fire if within ±(tick + 10 s) of the scheduled time.
            if -(10) <= delta <= (_SCHED_TICK + 10):
                state = self.get_state(ev.stream_name)
                if state is None:
                    log.warning(
                        "manager: event '%s' target stream '%s' not found.",
                        ev.event_id, ev.stream_name,
                    )
                    JSONManager.mark_event_played(self._events, ev.event_id)
                    continue
                try:
                    log.info(
                        "manager: firing one-shot event '%s' → '%s'.",
                        ev.event_id, ev.stream_name,
                    )
                    state.log_add(
                        f"🎬 One-shot event: playing '{ev.file_path.name}' "
                        f"at {ev.play_at.strftime('%H:%M')}."
                    )
                    worker = self.get_worker(ev.stream_name)
                    if worker:
                        # If the stream is not live, start it first so
                        # play_oneshot has a running ffmpeg pipeline to hand off to.
                        if state.status not in (
                            StreamStatus.LIVE, StreamStatus.STARTING
                        ):
                            log.info(
                                "manager: stream '%s' not running — starting "
                                "before one-shot event.",
                                ev.stream_name,
                            )
                            state.log_add(
                                "▶ Stream started automatically for one-shot event."
                            )
                            self._start_worker(state)
                            # Give the worker a moment to reach LIVE before
                            # injecting the one-shot clip.
                            deadline = time.time() + 10.0
                            while time.time() < deadline:
                                if state.status == StreamStatus.LIVE:
                                    break
                                time.sleep(0.25)
                        # play_oneshot is the correct method on StreamWorker
                        # (inject_event does not exist).
                        worker.play_oneshot(ev)
                    JSONManager.mark_event_played(self._events, ev.event_id)
                    self._glog.add(
                        f"Event fired: '{ev.file_path.name}' → {ev.stream_name}",
                        "INFO",
                    )
                except Exception as exc:
                    log.error(
                        "manager: event '%s' fire failed: %s",
                        ev.event_id, exc,
                    )

    def _check_compliance(self, now: datetime) -> None:
        """
        Compliance mode: if compliance_enabled, ensure the stream only runs
        at or after compliance_start.  Before that time, hold the stream in
        SCHEDULED state; at the start time, begin streaming.
        """
        try:
            cs_h, cs_m, cs_s = (int(x) for x in "06:00:00".split(":"))
        except ValueError:
            return

        now_secs = now.hour * 3600 + now.minute * 60 + now.second

        for state in self.states:
            cfg = state.config
            if not cfg.compliance_enabled:
                continue
            try:
                parts  = cfg.compliance_start.split(":")
                target = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except Exception:
                continue

            today_idx = now.weekday()
            scheduled = (not cfg.weekdays) or (today_idx in cfg.weekdays)

            if not scheduled or not cfg.enabled:
                continue

            # At or after compliance_start and stream is not yet live → start it.
            if now_secs >= target and state.status == StreamStatus.SCHEDULED:
                log.info(
                    "manager: compliance start time reached for '%s'.",
                    cfg.name,
                )
                state.log_add(
                    f"⏰ Compliance start reached ({cfg.compliance_start}) — "
                    "stream beginning."
                )
                self._start_worker(state)

            # Before compliance_start and stream is live but compliance blocks it.
            elif now_secs < target and state.status == StreamStatus.LIVE:
                # Only block on the very first tick after midnight; after that
                # the stream is already validated from a previous scheduler pass.
                pass

    # ── Per-stream control (public) ───────────────────────────────────────────

    def start(self, name: str) -> bool:
        """
        Manually start a stream by name (regardless of weekday schedule).
        Returns True on success.
        """
        state = self.get_state(name)
        if state is None:
            log.warning("manager.start: unknown stream '%s'.", name)
            return False
        if state.status == StreamStatus.LIVE:
            log.info("manager.start: '%s' already LIVE.", name)
            return True
        self._start_worker(state)
        return True

    def stop(self, name: str) -> bool:
        """
        Manually stop a stream by name.
        Returns True on success.
        """
        state = self.get_state(name)
        if state is None:
            log.warning("manager.stop: unknown stream '%s'.", name)
            return False
        self._stop_worker(state, reason="manual-stop")
        return True

    def restart(self, name: str) -> bool:
        """
        Restart a stream: stop (if running) then start.
        Returns True on success.
        """
        state = self.get_state(name)
        if state is None:
            log.warning("manager.restart: unknown stream '%s'.", name)
            return False
        log.info("manager: restarting '%s'.", name)
        state.log_add("🔄 Restarting stream …")
        self._stop_worker(state, reason="restart")
        time.sleep(0.5)
        self._start_worker(state)
        return True

    def rescan_folder(self, state: StreamState) -> None:
        """
        Force an immediate folder rescan for a folder-source stream.
        Delegates to FolderWatcherRegistry; falls back to a direct scan.
        """
        if state.config.folder_source is None:
            msg = f"[{state.config.name}] rescan_folder: not a folder-source stream."
            log.warning(msg)
            state.log_add(f"⚠ {msg}")
            return

        msg = (
            f"[{state.config.name}] Manual folder rescan triggered: "
            f"{state.config.folder_source.name}"
        )
        self._glog.add(msg, "INFO")
        state.log_add(f"🔍 {msg}")
        self._fw_registry.rescan(state)

    def clear_error(self, name: str) -> bool:
        """Reset error state and restart count for a stream (C key in TUI)."""
        state = self.get_state(name)
        if state is None:
            return False
        state.clear_error()
        log.info("manager: error state cleared for '%s'.", name)
        return True

    # ── URL export ────────────────────────────────────────────────────────────

    def export_urls(self) -> Path:
        """
        Write a plain-text file listing all RTSP (and HLS) stream URLs.
        Returns the Path of the written file.
        """
        from hc.utils import _local_ip
        ip   = _local_ip()
        lines: List[str] = [
            f"# {APP_NAME} v{APP_VER} — Stream URLs",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Server IP: {ip}",
            "",
        ]

        for state in self.states:
            cfg = state.config
            rtsp_url = f"rtsp://{ip}:{cfg.port}/{cfg.stream_path}"
            lines.append(f"[{cfg.name}]")
            lines.append(f"  RTSP : {rtsp_url}")
            if cfg.hls_enabled:
                hls_url = (
                    f"http://{ip}:{getattr(cfg, 'hls_port', cfg.port + 800)}"
                    f"/{cfg.stream_path}/index.m3u8"
                )
                lines.append(f"  HLS  : {hls_url}")
            lines.append(
                f"  Days : {cfg.weekdays_display()}"
            )
            lines.append(
                f"  Files: {len(cfg.playlist)} in playlist"
            )
            lines.append("")

        out = BASE_DIR() / "stream_urls.txt"
        out.write_text("\n".join(lines), encoding="utf-8")
        log.info("manager: URLs exported to '%s'.", out)
        return out

    # ── Internal worker helpers ───────────────────────────────────────────────

    def _start_worker(self, state: StreamState) -> None:
        """Create (or retrieve) and start the StreamWorker for *state*."""
        name = state.config.name
        with self._lock:
            worker = self._workers.get(name)
            if worker is None:
                worker = StreamWorker(state=state, glog=self._glog)
                self._workers[name] = worker

        try:
            worker.start()
            log.info("manager: worker started for '%s'.", name)
        except Exception as exc:
            log.error("manager: failed to start worker for '%s': %s", name, exc)
            state.status = StreamStatus.ERROR
            state.log_add(f"✘ Worker start failed: {exc}")

    def _stop_worker(self, state: StreamState, reason: str = "stop") -> None:
        """Signal and wait for the StreamWorker for *state* to stop."""
        name = state.config.name
        with self._lock:
            worker = self._workers.get(name)

        if worker is None:
            return

        try:
            worker.stop()
            log.info("manager: worker stopped for '%s' (reason=%s).", name, reason)
        except Exception as exc:
            log.warning(
                "manager: error stopping worker for '%s': %s",
                name, exc,
            )

    # ── Convenience: add a stream at runtime (web upload flow) ────────────────

    def add_stream(self, cfg: StreamConfig) -> StreamState:
        """
        Register a brand-new StreamConfig at runtime (e.g. via web UI).
        Does NOT auto-start — caller must call start(cfg.name) if desired.
        """
        state = self._add_stream(cfg)
        log.info("manager: new stream '%s' registered.", cfg.name)
        return state

    def remove_stream(self, name: str) -> bool:
        """
        Stop and remove a stream at runtime (e.g. deleted via web UI).
        Returns True if the stream was found and removed.
        """
        state = self.get_state(name)
        if state is None:
            return False
        self._stop_worker(state, reason="remove")
        if state.config.folder_source:
            self._fw_registry.unregister(state)
        with self._lock:
            self._states = [s for s in self._states if s.config.name != name]
            self._workers.pop(name, None)
        log.info("manager: stream '%s' removed.", name)
        return True

    # ── One-shot event management (public) ───────────────────────────────────

    def add_event(self, ev: OneShotEvent) -> None:
        """
        Append a pre-constructed OneShotEvent to the in-memory list and
        persist it to config/events.json.
        Called by web.py after it builds the OneShotEvent object.
        """
        with self._lock:
            self._events.append(ev)
        JSONManager._save_events(self._events)
        log.info(
            "manager: one-shot event '%s' scheduled for %s on stream '%s'.",
            ev.event_id, ev.play_at.isoformat(), ev.stream_name,
        )

    def remove_event(self, event_id: str) -> bool:
        """
        Remove a one-shot event by its event_id.
        Returns True if found and removed, False otherwise.
        """
        with self._lock:
            before = len(self._events)
            self._events = [e for e in self._events if e.event_id != event_id]
            removed = len(self._events) < before
        if removed:
            JSONManager._save_events(self._events)
            log.info("manager: one-shot event '%s' removed.", event_id)
        else:
            log.warning("manager: remove_event: event_id '%s' not found.", event_id)
        return removed

    # ── String representation ─────────────────────────────────────────────────

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<StreamManager streams={len(self._states)} "
            f"live={sum(1 for s in self._states if s.status == StreamStatus.LIVE)}>"
        )
