"""
hc/manager.py  —  StreamManager: orchestrates workers, scheduler, event loop.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from hc.csv_manager import CSVManager
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
        self.events:   List[OneShotEvent]         = CSVManager.load_events()

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
                s.status = StreamStatus.SCHEDULED

    def stop_all(self) -> None:
        for s in self.states:
            self.stop_stream(s)

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
                                CSVManager.mark_event_played(
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
