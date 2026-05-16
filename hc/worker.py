"""
hc/worker.py  —  LogBuffer, media probe helpers, and StreamWorker.

FIXES (v5.1.0):
  • _auto_restart() now guards against _stop flag being set — prevents
    the stream re-appearing after a manual Stop (S key).
  • _monitor() checks _stop before calling _auto_restart so that a stop()
    that races the FFmpeg exit no longer triggers an unwanted restart.
  • stop() sets _stop BEFORE saving resume position and killing processes,
    so any concurrent monitor thread sees the flag immediately.
  • restart() clears _stop only after stop() completes, preventing the
    monitor from sneaking in an auto-restart during the gap.
  • Folder scanner re-scan on every start — newly uploaded files are picked
    up automatically without needing a manual CSV reload.
  • _do_start() returns False cleanly if playlist is empty after folder scan.
  • seek_start_pos initialised to 0.0 in StreamState to avoid AttributeError.
"""
from __future__ import annotations

import json
import os
import logging
import random
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

from hc.constants import (
    CPU_COUNT, FFMPEG_PATH, FFPROBE_PATH, IS_LINUX, IS_WIN,
    LOGS_DIR, MEDIAMTX_BIN,
)
from hc.mediamtx_cfg import MediaMTXConfig
from hc.models import OneShotEvent, PlaylistItem, StreamState, StreamStatus
from hc.utils import _fmt_duration, _kill_orphan_on_port, _port_in_use, _wait_for_port, _wait_for_rtsp

log = logging.getLogger(__name__)


# =============================================================================
# LOG BUFFER
# =============================================================================
class LogBuffer:
    def __init__(self, capacity: int = 1200) -> None:
        self._entries: List[Tuple[str, str]] = []
        self._lock = threading.Lock()
        self._cap  = capacity

    def add(self, msg: str, level: str = "INFO") -> None:
        ts = __import__("datetime").datetime.now().strftime("%H:%M:%S")
        entry = (f"[{ts}] {msg}", level)
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._cap:
                self._entries.pop(0)
        py_level = (
            logging.ERROR   if level == "ERROR" else
            logging.WARNING if level == "WARN"  else
            logging.INFO
        )
        log.log(py_level, "%s", msg)

    def last(self, n: int = 9) -> List[Tuple[str, str]]:
        with self._lock:
            return list(self._entries[-n:])

    def all(self) -> List[Tuple[str, str]]:
        with self._lock:
            return list(self._entries)

    def filtered(self, level: Optional[str] = None,
                 stream: Optional[str] = None,
                 n: int = 500) -> List[Tuple[str, str]]:
        with self._lock:
            entries = list(self._entries)
        if stream:
            entries = [(m, l) for m, l in entries if f"[{stream}]" in m]
        if level and level != "ALL":
            entries = [(m, l) for m, l in entries if l == level]
        return entries[-n:]


# =============================================================================
# MEDIA PROBE HELPERS
# =============================================================================
def probe_duration(file_path: Path) -> float:
    """Return duration in seconds (0 on failure)."""
    log.debug("Probing duration: %s", file_path)
    if not file_path.exists():
        log.warning("probe_duration: file does not exist: %s", file_path)
        return 0.0
    try:
        r = subprocess.run(
            [FFPROBE_PATH(), "-v", "quiet",
             "-show_entries", "format=duration",
             "-of", "csv=p=0", str(file_path)],
            capture_output=True, text=True, timeout=20,
        )
        dur = float(r.stdout.strip())
        log.debug("Duration of %s → %.2f s", file_path.name, dur)
        return dur
    except subprocess.TimeoutExpired:
        log.error("probe_duration: ffprobe timeout on %s", file_path)
        return 0.0
    except ValueError:
        log.warning("probe_duration: could not parse output for %s", file_path)
        return 0.0
    except Exception as exc:
        log.error("probe_duration: unexpected error for %s: %s", file_path, exc)
        return 0.0


def probe_metadata(file_path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "duration": 0.0, "size": 0, "video_codec": "", "audio_codec": "",
        "width": 0, "height": 0, "fps": "", "bitrate": 0,
    }
    try:
        meta["size"] = file_path.stat().st_size
    except Exception as exc:
        log.debug("probe_metadata: stat failed for %s: %s", file_path, exc)
    try:
        r = subprocess.run(
            [FFPROBE_PATH(), "-v", "quiet",
             "-print_format", "json",
             "-show_streams", "-show_format", str(file_path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
        fmt  = data.get("format", {})
        meta["duration"] = float(fmt.get("duration", 0))
        meta["bitrate"]  = int(float(fmt.get("bit_rate", 0)))
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and not meta["video_codec"]:
                meta["video_codec"] = s.get("codec_name", "")
                meta["width"]       = s.get("width", 0)
                meta["height"]      = s.get("height", 0)
                r_fps = s.get("r_frame_rate", "0/1")
                try:
                    num, den = r_fps.split("/")
                    meta["fps"] = f"{int(num)//int(den)}" if int(den) else ""
                except Exception:
                    pass
            elif s.get("codec_type") == "audio" and not meta["audio_codec"]:
                meta["audio_codec"] = s.get("codec_name", "")
    except Exception as exc:
        log.debug("probe_metadata: error for %s: %s", file_path, exc)
    return meta


def grab_thumbnail(file_path: Path, seek_secs: float = 5.0) -> Optional[bytes]:
    """Return raw PNG bytes of a single frame, or None on error."""
    try:
        r = subprocess.run(
            [FFMPEG_PATH(), "-hide_banner", "-loglevel", "error",
             "-ss", str(int(seek_secs)), "-i", str(file_path),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
    except Exception as exc:
        log.debug("grab_thumbnail failed for %s: %s", file_path, exc)
    return None


# =============================================================================
# STREAM WORKER
# =============================================================================
class StreamWorker:
    MAX_AUTO_RESTARTS = 8
    BACKOFF           = [5, 10, 20, 40, 60, 120, 120, 120]
    # Windows AV scanning / SmartScreen can add 20–30 s to MediaMTX startup;
    # give it extra headroom.  Linux/macOS keep the tighter bound.
    MTX_READY_TIMEOUT = 40.0 if IS_WIN else 20.0

    _FFMPEG_PROGRESS_RE = re.compile(r"^(\w+)=(.+)$")

    def __init__(self, state: StreamState, glog: LogBuffer) -> None:
        self.state       = state
        self.glog        = glog
        self._stop       = threading.Event()
        self._seeking    = threading.Event()
        self._start_lock = threading.Lock()
        # Ensure seek_start_pos always exists to prevent AttributeError
        if not hasattr(self.state, "seek_start_pos"):
            self.state.seek_start_pos = 0.0  # type: ignore[attr-defined]
        # Track the currently-playing one-shot event (for API exposure)
        if not hasattr(self.state, "active_oneshot_event"):
            self.state.active_oneshot_event = None  # type: ignore[attr-defined]

    # ── Internal logging ───────────────────────────────────────────────────────
    def _log(self, msg: str, level: str = "INFO") -> None:
        full = f"[{self.state.config.name}] {msg}"
        self.state.log_add(full)
        self.glog.add(full, level)

    # ── Playlist helpers ───────────────────────────────────────────────────────
    def _build_order(self) -> List[int]:
        n     = len(self.state.config.playlist)
        order = list(range(n))
        if self.state.config.shuffle:
            random.shuffle(order)
            self._log(f"Playlist shuffled: {order}")
        return order

    def _current_item(self) -> Optional[PlaylistItem]:
        pl = self.state.config.playlist
        if not pl:
            return None
        if not self.state.playlist_order:
            self.state.playlist_order = self._build_order()
        idx = self.state.playlist_order[
            self.state.playlist_index % len(self.state.playlist_order)]
        return pl[idx]

    def _advance_playlist(self) -> None:
        old_idx = self.state.playlist_index
        self.state.playlist_index += 1
        if self.state.playlist_index >= len(self.state.playlist_order):
            self.state.playlist_index = 0
            self.state.loop_count    += 1
            if self.state.config.shuffle:
                self.state.playlist_order = self._build_order()
            self._log(
                f"Playlist loop complete (loop #{self.state.loop_count}), "
                f"wrapping back to start."
            )
        else:
            self._log(
                f"Playlist advanced: item {old_idx+1} → {self.state.playlist_index+1}"
                f" of {len(self.state.playlist_order)}"
            )

    # ── Resume / position persistence ─────────────────────────────────────────
    def _save_resume_position(self) -> None:
        pos  = self.state.current_pos
        fp   = self.state.current_file()
        name = self.state.config.name
        if fp and pos > 5.0:
            try:
                from hc.resume_store import save_position
                save_position(name, fp, pos)
                self._log(
                    f"Resume position saved: {fp.name} @ "
                    f"{int(pos)//3600:02d}:{(int(pos)%3600)//60:02d}:{int(pos)%60:02d}"
                )
            except Exception as exc:
                self._log(f"Could not save resume position: {exc}", "WARN")

    # ── Public API ─────────────────────────────────────────────────────────────
    def start(self, seek_override: Optional[float] = None,
              initial_offset: float = 0.0) -> bool:
        if not self._start_lock.acquire(blocking=False):
            self._log("start() called while already in progress — skipped.", "WARN")
            return False
        try:
            # Clear stop flag only when we are actually starting
            self._stop.clear()
            return self._do_start(seek_override, initial_offset)
        finally:
            self._start_lock.release()

    def stop(self) -> None:
        self._log("Stop requested.")
        # ── Set stop flag FIRST so any concurrent monitor/auto-restart sees it ─
        self._stop.set()
        # ── Save resume position before killing FFmpeg ─────────────────────────
        if self.state.status == StreamStatus.LIVE:
            self._save_resume_position()
        self._kill_ffmpeg()
        time.sleep(1.0)
        self._kill_mediamtx()
        self.state.status      = StreamStatus.STOPPED
        self.state.progress    = 0.0
        self.state.current_pos = 0.0
        self.state.fps         = 0.0
        self.state.bitrate     = "—"
        self.state.speed       = "—"
        self._log("Stream stopped cleanly.")

    def restart(self, seek: Optional[float] = None) -> None:
        self._log("Restart requested.")
        # Acquire the start lock BEFORE stopping so the monitor thread's
        # _auto_restart cannot sneak in and call start() between stop() and
        # our own start() call.
        if not self._start_lock.acquire(timeout=15):
            self._log("Restart: could not acquire start lock in 15s — aborting.", "WARN")
            return
        try:
            # stop() sets _stop flag; we clear it only after stop() fully
            # completes, then call _do_start directly (lock already held).
            self._stop.set()
            self._kill_ffmpeg()
            time.sleep(1.0)
            self._kill_mediamtx()
            self.state.status      = StreamStatus.STOPPED
            self.state.progress    = 0.0
            self.state.current_pos = 0.0
            self.state.fps         = 0.0
            self.state.bitrate     = "—"
            self.state.speed       = "—"
            self._log("Stream stopped for restart.")
            time.sleep(0.5)
            # Clear stop flag now — we are intentionally restarting
            self._stop.clear()
            self._do_start(seek_override=seek)
        finally:
            self._start_lock.release()

    def seek(self, seconds: float) -> None:
        self._seeking.set()
        self._log(f"Seek requested → {_fmt_duration(seconds)}")
        self._kill_ffmpeg()
        time.sleep(0.4)
        item = self._current_item()
        if item is None:
            self._log("Seek aborted: no current playlist item.", "WARN")
            self._seeking.clear()
            return
        self.state.duration = probe_duration(item.file_path)
        self._start_ffmpeg_with_retry(item, max(0.0, seconds))
        self._seeking.clear()
        self.state.status = StreamStatus.LIVE
        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{self.state.config.port}").start()

    def skip_to_next(self) -> None:
        self._log("Skip-to-next requested.")
        self._seeking.set()
        self._advance_playlist()
        self._kill_ffmpeg()
        time.sleep(0.3)
        item = self._current_item()
        if item is None:
            self._log("Skip aborted: no next item.", "WARN")
            self._seeking.clear()
            return
        self.state.duration = probe_duration(item.file_path)
        try:
            h, m, s = item.start_position.split(":")
            spos = int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            spos = 0.0
        self._log(f"Skipping to: {item.file_path.name} @ {_fmt_duration(spos)}")
        self._start_ffmpeg_with_retry(item, spos)
        self._seeking.clear()
        self.state.status = StreamStatus.LIVE
        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{self.state.config.port}").start()

    # ── Compliance seek helpers ────────────────────────────────────────────────

    def compliance_resync(self) -> None:
        """
        Public: immediately seek to the correct compliance position right now.

        Called from:
          • Web UI when compliance mode is toggled ON for an already-live stream.
          • After a one-shot event ends and the compliance file resumes.

        No-ops if:
          • compliance is not enabled on the config, OR
          • the stream is not currently LIVE, OR
          • a stop or seek is already in progress.
        """
        cfg = self.state.config
        if not cfg.compliance_enabled:
            self._log("compliance_resync: compliance not enabled — skipped.", "WARN")
            return
        if self.state.status != StreamStatus.LIVE:
            self._log("compliance_resync: stream not live — skipped.", "WARN")
            return
        if self._stop.is_set() or self._seeking.is_set():
            self._log("compliance_resync: stop/seek already in progress — skipped.", "WARN")
            return
        try:
            from hc.compliance import calculate_compliance_offset
            seek_pos, expl = calculate_compliance_offset(
                video_duration=self.state.duration,
                broadcast_start=cfg.compliance_start,
                loop_calculation=cfg.compliance_loop,
            )
            self._log(f"Compliance immediate resync: {expl}")
        except Exception as exc:
            self._log(
                f"compliance_resync: offset calculation failed: {exc} — skipped", "WARN"
            )
            return
        # Stamp the check time BEFORE calling seek() so the new monitor thread
        # does not immediately re-trigger another check.
        self.state.compliance_last_check_ts = time.time()
        self.seek(seek_pos)

    def _compliance_check_and_resync(self) -> None:
        """
        Internal: measure drift against the configured threshold and, if the
        drift exceeds it, perform a hard resync via seek().

        Always runs in its own short-lived daemon thread (spawned from the
        _monitor() progress loop) so the FFmpeg readline loop is never blocked.
        """
        cfg = self.state.config
        # Re-check guards inside the thread; state may have changed since spawn.
        if (not cfg.compliance_enabled
                or self.state.duration <= 0
                or self._stop.is_set()
                or self._seeking.is_set()
                or self.state.oneshot_active):
            return
        try:
            from hc.compliance import check_compliance_drift
            should_resync, drift, expected = check_compliance_drift(
                current_pos=self.state.current_pos,
                video_duration=self.state.duration,
                broadcast_start=cfg.compliance_start,
                loop_calculation=cfg.compliance_loop,
                drift_threshold=cfg.compliance_drift_threshold,
            )
        except Exception as exc:
            self._log(f"_compliance_check_and_resync: drift check error: {exc}", "WARN")
            return

        if should_resync:
            self._log(
                f"Compliance drift {drift:+.1f}s exceeds threshold "
                f"{cfg.compliance_drift_threshold:.0f}s — "
                f"hard resync to {_fmt_duration(expected)}",
                "WARN",
            )
            # seek() will set _seeking, kill FFmpeg, and start a new monitor.
            # The current monitor thread will detect the seeking flag and exit.
            self.seek(expected)
        else:
            self._log(
                f"Compliance periodic check: drift {drift:+.1f}s within "
                f"threshold {cfg.compliance_drift_threshold:.0f}s — no resync needed."
            )

    def cancel_oneshot(self) -> None:
        """
        Cancel a running one-shot event and immediately resume the compliance
        file / playlist at the correct seek position.

        Called from the Web UI "Cancel Event" button.

        No-ops if no event is currently active.
        """
        if not self.state.oneshot_active:
            self._log("cancel_oneshot: no event active — skipped.", "WARN")
            return

        self._log("Cancelling one-shot event — resuming compliance/playlist.", "INFO")

        # Mark the cancel so _after() in the oneshot thread exits cleanly
        # without trying to resume on its own (we handle resume here instead).
        self.state.oneshot_active = False
        # Clear the stored event reference
        self.state.active_oneshot_event = None  # type: ignore[attr-defined]

        # Kill the event's FFmpeg process
        self._kill_ffmpeg()

        # Now resume: pick the right playlist item and compute compliance offset
        item = self._current_item()
        if item is None:
            self._log("cancel_oneshot: no playlist item to resume — stopping.", "WARN")
            self._kill_mediamtx()
            self.state.status = StreamStatus.STOPPED
            return

        self.state.duration = probe_duration(item.file_path)

        resume_pos = 0.0
        cfg = self.state.config
        if cfg.compliance_enabled:
            try:
                from hc.compliance import calculate_compliance_offset
                resume_pos, expl = calculate_compliance_offset(
                    video_duration=self.state.duration,
                    broadcast_start=cfg.compliance_start,
                    loop_calculation=cfg.compliance_loop,
                )
                self._log(f"Cancel-event compliance resync: {expl}")
                self.state.compliance_last_check_ts = time.time()
            except Exception as exc:
                self._log(
                    f"cancel_oneshot: compliance offset failed: {exc} — resuming from 00:00:00",
                    "WARN",
                )
        else:
            try:
                h, m, s = item.start_position.split(":")
                resume_pos = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                resume_pos = 0.0

        self._log(f"Resuming: {item.file_path.name} @ {_fmt_duration(resume_pos)}")

        # Cycle MediaMTX to clear the cancelled event's publisher session
        if not self._cycle_mediamtx():
            self._log("cancel_oneshot: MediaMTX cycle failed — triggering auto-restart.", "ERROR")
            self._auto_restart()
            return

        self._start_ffmpeg_with_retry(item, resume_pos)
        self.state.status = StreamStatus.LIVE
        threading.Thread(
            target=self._monitor, daemon=True,
            name=f"mon-{self.state.config.port}",
        ).start()

    def play_oneshot(self, event: OneShotEvent) -> None:
        self._log(f"One-shot event starting: {event.file_path.name}", "INFO")
        self.state.oneshot_active = True
        # Store the event so the API can expose the event file name
        self.state.active_oneshot_event = event  # type: ignore[attr-defined]
        self._kill_ffmpeg()

        try:
            h, m, s = event.start_pos.split(":")
            seek_secs = int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            seek_secs = 0.0

        # loop_count: -1 = infinite, 0 = once, N = N extra loops
        loop_count = getattr(event, "loop_count", 0)

        # Cycle MediaMTX to clear old publisher session; same reason as
        # playlist advance — without this the new push gets 400 Bad Request.
        if not self._cycle_mediamtx():
            self._log("One-shot: MediaMTX cycle failed — aborting.", "ERROR")
            self.state.oneshot_active = False
            self.state.active_oneshot_event = None  # type: ignore[attr-defined]
            # FFmpeg was already killed above; MediaMTX is in an unknown state.
            # Trigger auto-restart so the stream recovers rather than going silent.
            if not self._stop.is_set():
                self._log("One-shot: scheduling auto-restart to recover stream.", "WARN")
                threading.Thread(
                    target=self._auto_restart, daemon=True,
                    name=f"oneshot-recover-{self.state.config.port}",
                ).start()
            return

        item = PlaylistItem(file_path=event.file_path, start_position=event.start_pos)
        self.state.duration = probe_duration(item.file_path)

        # Apply compliance offset to the event file when compliance is enabled.
        # The event file is also a 24-hour broadcast video: position 00:00:00
        # maps to 06:00 wall-clock time.  At 12:00 the correct position is
        # 06:00:00; at 20:00 it is 14:00:00 — exactly the same logic as the
        # compliance file itself, so the broadcast stays in sync.
        cfg = self.state.config
        if cfg.compliance_enabled and self.state.duration > 0:
            try:
                from hc.compliance import calculate_compliance_offset
                compliance_seek, _expl_ev = calculate_compliance_offset(
                    video_duration=self.state.duration,
                    broadcast_start=cfg.compliance_start,
                    loop_calculation=cfg.compliance_loop,
                )
                seek_secs = compliance_seek
                self._log(f"One-shot compliance offset: {_expl_ev}")
            except Exception as _exc_ev:
                self._log(
                    f"One-shot compliance offset failed: {_exc_ev} "
                    "— using event start_pos",
                    "WARN",
                )

        # CRITICAL: pass oneshot=True so _start_ffmpeg never adds -stream_loop -1
        ok = self._start_ffmpeg_with_retry(item, seek_secs, oneshot=True, loop_count=loop_count)

        # Set ONESHOT status so the UI shows the event badge and progress bar.
        # Do this AFTER _start_ffmpeg_with_retry so the proc reference is stable.
        self.state.status = StreamStatus.ONESHOT

        # Capture the proc NOW (after retry loop settled) for _after().
        _oneshot_proc = self.state.ffmpeg_proc

        # Start monitor thread only if FFmpeg launched successfully.
        if ok and _oneshot_proc is not None:
            threading.Thread(
                target=self._monitor, daemon=True,
                name=f"mon-oneshot-{self.state.config.port}",
            ).start()

        def _after() -> None:
            # Wait on the exact proc that was launched — not whatever is
            # in self.state.ffmpeg_proc later (which may have been replaced).
            proc = _oneshot_proc
            if proc:
                while not self._stop.is_set() and proc.poll() is None:
                    time.sleep(0.5)
            # If cancel_oneshot() already cleared oneshot_active and started
            # resuming, do not interfere.  Also bail on a full stream stop.
            if not self.state.oneshot_active or self._stop.is_set():
                self.state.oneshot_active = False
                self.state.active_oneshot_event = None  # type: ignore[attr-defined]
                self.state.resuming = False
                return
            self.state.oneshot_active = False
            self.state.active_oneshot_event = None  # type: ignore[attr-defined]
            self._log(
                f"One-shot finished. Post-action: {event.post_action}", "INFO"
            )
            if event.post_action == "stop":
                self.state.resuming = False
                self.stop()
            elif event.post_action == "black":
                self.state.resuming = False
                self._play_black()
            else:
                item2 = self._current_item()
                if item2:
                    self._log(f"Resuming playlist: {item2.file_path.name}")
                    # Hold _seeking for the entire resume window.
                    # This blocks _auto_restart() (which checks _seeking) and
                    # compliance_resync() from interfering while _cycle_mediamtx
                    # kills + restarts MediaMTX.  Without this flag, the monitor
                    # thread's FFmpeg "Broken pipe" exit (caused by killing FFmpeg
                    # for the cycle) triggers _auto_restart(), which races
                    # _cycle_mediamtx() and corrupts the port state.
                    self._seeking.set()
                    try:
                        # Probe the duration before calculating the compliance offset.
                        self.state.duration = probe_duration(item2.file_path)
                        # Hard resync: same behaviour as the periodic check.
                        resume_spos = 0.0
                        if self.state.config.compliance_enabled:
                            try:
                                from hc.compliance import calculate_compliance_offset
                                resume_spos, _expl3 = calculate_compliance_offset(
                                    video_duration=self.state.duration,
                                    broadcast_start=self.state.config.compliance_start,
                                    loop_calculation=self.state.config.compliance_loop,
                                )
                                self._log(
                                    f"One-shot resume — compliance hard resync: {_expl3}"
                                )
                                self.state.compliance_last_check_ts = time.time()
                            except Exception as _exc3:
                                self._log(
                                    f"One-shot resume compliance offset failed: {_exc3} "
                                    "— resuming from 00:00:00",
                                    "WARN",
                                )
                        # Cycle MediaMTX again before resuming the playlist.
                        if self._cycle_mediamtx():
                            self._start_ffmpeg_with_retry(item2, resume_spos)
                            self.state.status = StreamStatus.LIVE
                            threading.Thread(target=self._monitor, daemon=True,
                                             name=f"mon-{self.state.config.port}").start()
                        else:
                            self._log("One-shot resume: MediaMTX cycle failed.", "ERROR")
                    finally:
                        # Always clear both flags so future seeks/restarts can proceed.
                        self.state.resuming = False
                        self._seeking.clear()

        # Mark resuming BEFORE spawning _after so the scheduler's start_stream()
        # guard sees it immediately, even if the scheduler tick races this line.
        self.state.resuming = True
        threading.Thread(target=_after, daemon=True,
                         name=f"oneshot-{self.state.config.port}").start()

    # ── Core startup ───────────────────────────────────────────────────────────
    def _do_start(self, seek_override: Optional[float] = None,
                  initial_offset: float = 0.0) -> bool:
        cfg = self.state.config
        # Do NOT clear _stop here — start() and restart() manage it.

        self._log(
            f"Starting stream | port={cfg.port} | path={cfg.rtsp_path} | "
            f"files={len(cfg.playlist)} | bitrate={cfg.video_bitrate}/{cfg.audio_bitrate}"
        )

        if not cfg.playlist:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = "No files in playlist"
            self._log(self.state.error_msg, "ERROR")
            return False

        item = self._current_item()
        if item is None:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = "Could not determine current playlist item"
            self._log(self.state.error_msg, "ERROR")
            return False

        self._log(f"Current file: {item.file_path}")

        # ── Folder-as-playlist resolution ─────────────────────────────────────
        resolved_path = item.file_path

        if not resolved_path.is_absolute() and not resolved_path.exists():
            try:
                from hc.constants import MEDIA_DIR
                candidate = MEDIA_DIR() / resolved_path
                if candidate.exists():
                    resolved_path = candidate
                    self._log(
                        f"Resolved relative path '{item.file_path}' "
                        f"→ '{resolved_path}'",
                        "INFO",
                    )
            except Exception as exc:
                self._log(
                    f"Could not resolve relative path against MEDIA_DIR: {exc}", "WARN"
                )

        # Use the remembered folder_source if present (ensures re-scan on restart).
        folder_root: Optional[Path] = cfg.folder_source
        if folder_root is None and resolved_path.is_dir():
            folder_root = resolved_path

        if folder_root is not None:
            self._log(
                f"Folder source detected — re-scanning for media files: {folder_root}",
                "INFO",
            )
            try:
                from hc.folder_scanner import scan_folder
                scanned_items, warnings = scan_folder(folder_root)
                for w in warnings:
                    self._log(f"Folder scanner: {w}", "WARN")
                if not scanned_items:
                    self.state.status    = StreamStatus.ERROR
                    self.state.error_msg = (
                        f"No supported media files in folder: {folder_root}"
                    )
                    self._log(self.state.error_msg, "ERROR")
                    return False

                # Persist folder_source so every future restart re-scans.
                cfg.folder_source = folder_root

                # Update in-memory playlist.  Preserve the current playlist
                # index so a restart after an error doesn't always replay the
                # first file — only reset to 0 on the very first start
                # (playlist_order is empty) or when the playlist shrank to
                # fewer items than the current index.
                old_count = len(cfg.playlist)
                cfg.playlist = scanned_items
                if not self.state.playlist_order:
                    # First start: build order fresh.
                    self.state.playlist_index = 0
                    self.state.playlist_order = self._build_order()
                else:
                    # Rebuild order (handles shuffle + new file count).
                    self.state.playlist_order = self._build_order()
                    # Clamp index to valid range.
                    self.state.playlist_index = (
                        self.state.playlist_index % len(self.state.playlist_order)
                    )

                item = self._current_item()
                if item is None:
                    self.state.status    = StreamStatus.ERROR
                    self.state.error_msg = (
                        "Folder scan succeeded but could not pick current item"
                    )
                    self._log(self.state.error_msg, "ERROR")
                    return False
                resolved_path = item.file_path
                self._log(
                    f"Folder scan: {len(scanned_items)} file(s) found "
                    f"(was {old_count}). Resuming with: {resolved_path.name}"
                )
            except Exception as exc:
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = f"Folder scan failed: {exc}"
                self._log(self.state.error_msg, "ERROR")
                return False

        if not resolved_path.exists():
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"File not found: {resolved_path}"
            self._log(self.state.error_msg, "ERROR")
            return False

        if not resolved_path.is_file():
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"Path is not a file: {resolved_path}"
            self._log(self.state.error_msg, "ERROR")
            return False

        # Re-point item to the resolved path so the rest of _do_start uses it.
        item = PlaylistItem(
            file_path=resolved_path,
            start_position=item.start_position,
            weight=item.weight,
            priority=item.priority,
        )

        self._log(f"File verified: {item.file_path.name} ({item.file_path.stat().st_size // 1024} KB)")
        self.state.status   = StreamStatus.STARTING
        self.state.duration = probe_duration(item.file_path)
        self._log(f"File duration: {_fmt_duration(self.state.duration)}")

        # ── Determine seek position ───────────────────────────────────────────
        if seek_override is not None:
            seek_pos = float(seek_override)
            self._log(f"Seek override supplied: {_fmt_duration(seek_pos)}")
            # seek_override takes full control — discard any injected initial_offset.
            self.state.initial_offset = 0.0
        elif cfg.compliance_enabled:
            try:
                from hc.compliance import calculate_compliance_offset
                seek_pos, expl = calculate_compliance_offset(
                    video_duration=self.state.duration,
                    broadcast_start=cfg.compliance_start,
                    loop_calculation=cfg.compliance_loop,
                )
                self._log(expl)
            except Exception as exc:
                self._log(f"Compliance offset calculation failed: {exc} — starting from 0", "WARN")
                seek_pos = 0.0
            # Compliance already computed the correct seek position — discard
            # any state.initial_offset injected by _apply_compliance_start() in
            # manager.py, which would otherwise be added on top and double the offset.
            self.state.initial_offset = 0.0
        else:
            seek_pos = 0.0
            try:
                from hc.resume_store import load_position, clear_position
                saved = load_position(cfg.name)
                if saved is not None:
                    saved_file = Path(saved["file_path"])
                    saved_pos  = float(saved.get("position", 0.0))
                    try:
                        paths_match = saved_file.resolve() == item.file_path.resolve()
                    except Exception:
                        paths_match = saved_file == item.file_path
                    if (paths_match
                            and saved_pos > 5.0
                            and (self.state.duration <= 0
                                 or saved_pos < self.state.duration - 2.0)):
                        seek_pos = saved_pos
                        self._log(
                            f"Resuming from saved position: {item.file_path.name} "
                            f"@ {_fmt_duration(seek_pos)} "
                            f"(saved {saved.get('saved_at', '?')})"
                        )
                        clear_position(cfg.name)
                    else:
                        if saved is not None:
                            self._log(
                                f"Saved resume position discarded "
                                f"(file mismatch or out-of-range): "
                                f"saved={saved_file.name} "
                                f"current={item.file_path.name} "
                                f"pos={saved_pos:.1f}s dur={self.state.duration:.1f}s",
                                "WARN",
                            )
                        pos_str = item.start_position
                        try:
                            h, m, s  = pos_str.split(":")
                            seek_pos = int(h) * 3600 + int(m) * 60 + float(s)
                        except Exception:
                            seek_pos = 0.0
                else:
                    pos_str = item.start_position
                    try:
                        h, m, s  = pos_str.split(":")
                        seek_pos = int(h) * 3600 + int(m) * 60 + float(s)
                    except Exception:
                        seek_pos = 0.0
            except Exception as exc:
                self._log(
                    f"Resume store lookup failed: {exc} — starting from CSV position",
                    "WARN",
                )
                pos_str = item.start_position
                try:
                    h, m, s  = pos_str.split(":")
                    seek_pos = int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    seek_pos = 0.0

        # Apply per-start offset
        combined_offset = initial_offset + self.state.initial_offset
        self.state.initial_offset = 0.0
        if combined_offset != 0.0:
            old_pos  = seek_pos
            seek_pos = max(0.0, seek_pos + combined_offset)
            self._log(
                f"Initial offset {combined_offset:+.0f}s applied: "
                f"{_fmt_duration(old_pos)} → {_fmt_duration(seek_pos)}"
            )

        if self.state.duration > 0:
            seek_pos = min(seek_pos, self.state.duration - 1.0)
        seek_pos = max(0.0, seek_pos)

        self._log(f"Start seek position: {_fmt_duration(seek_pos)}")

        # ── Port availability check ───────────────────────────────────────────
        self._log(f"Checking port {cfg.port} availability …")
        if _port_in_use(cfg.port):
            self._log(f"Port {cfg.port} is in use — attempting to kill orphan process.", "WARN")
            _kill_orphan_on_port(cfg.port)
            time.sleep(0.8)
            if _port_in_use(cfg.port):
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = f"Port {cfg.port} still in use after kill attempt"
                self._log(self.state.error_msg, "ERROR")
                return False
            self._log(f"Port {cfg.port} is now free.")
        else:
            self._log(f"Port {cfg.port} is free.")

        # ── Write MediaMTX config ─────────────────────────────────────────────
        self._log("Writing MediaMTX YAML config …")
        try:
            mtx_cfg = MediaMTXConfig.write(self.state)
            self._log(f"MediaMTX config written: {mtx_cfg}")
        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"Failed to write MediaMTX config: {exc}"
            self._log(self.state.error_msg, "ERROR")
            return False

        # ── Launch MediaMTX ───────────────────────────────────────────────────
        if not self._start_mediamtx(mtx_cfg):
            return False

        # Wait for MediaMTX RTSP handler to be fully ready.
        # _wait_for_port() only confirms TCP bind. On Windows, MediaMTX binds
        # the port ~500-800 ms before its RTSP handler is initialised; ffmpeg
        # connecting during that gap sends ANNOUNCE and gets 400 Bad Request.
        # _wait_for_rtsp() sends a real RTSP OPTIONS and waits for 200 OK.
        # Wait for MediaMTX RTSP handler to be fully ready.
        # _wait_for_port() only confirms TCP bind. On Windows, MediaMTX binds
        # the port ~500-800 ms before its RTSP handler is initialised; ffmpeg
        # connecting during that gap sends ANNOUNCE and gets 400 Bad Request.
        # _wait_for_rtsp() sends a real RTSP OPTIONS and waits for a response.
        self._log(f"Waiting for MediaMTX RTSP handler :{cfg.port} (timeout {self.MTX_READY_TIMEOUT:.0f}s) ...")
        _push_path = cfg.rtsp_path if cfg.rtsp_path else "stream"
        mtx_proc   = self.state.mtx_proc

        def _mtx_alive() -> bool:
            return mtx_proc is not None and mtx_proc.poll() is None

        if not _wait_for_rtsp(cfg.port, timeout=self.MTX_READY_TIMEOUT,
                               path=_push_path, check_alive=_mtx_alive):
            # Determine if MediaMTX crashed (process dead) or just didn't respond.
            proc_dead  = mtx_proc is not None and mtx_proc.poll() is not None
            crash_f    = getattr(mtx_proc, "_crash_f", None) if mtx_proc else None
            log_tail   = _tail_log(LOGS_DIR() / f"mediamtx_{cfg.port}.log", 12)
            crash_tail = _tail_log(crash_f, 20) if crash_f else ""
            detail     = crash_tail or log_tail or "No output in MediaMTX log file"

            if proc_dead:
                exit_code = mtx_proc.returncode
                self._log(
                    f"MediaMTX crashed during RTSP readiness probe "
                    f"(exit code {exit_code}). "
                    f"Log/crash output:\n{detail}\n"
                    f"HINT: Run '{MEDIAMTX_BIN()} {mtx_cfg}' in a terminal "
                    "to see the full error.",
                    "ERROR",
                )
            else:
                tcp_up = _port_in_use(cfg.port)
                hint = (
                    "HINT: Windows Firewall or Antivirus may be intercepting "
                    "RTSP on loopback (127.0.0.1). Try temporarily disabling "
                    "real-time protection or adding a firewall exception for "
                    f"TCP :{cfg.port}."
                    if IS_WIN and tcp_up else
                    f"HINT: MediaMTX TCP port {cfg.port} is NOT bound — "
                    "the process may have crashed after the stability check."
                    if not tcp_up else ""
                )
                self._log(
                    f"MediaMTX RTSP-ready timeout :{cfg.port} after "
                    f"{self.MTX_READY_TIMEOUT:.0f}s "
                    f"(MediaMTX {'alive' if tcp_up else 'not responding on TCP'}). "
                    f"Log output:\n{detail}"
                    + (f"\n{hint}" if hint else ""),
                    "ERROR",
                )
            self._kill_mediamtx()
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX timeout (:{cfg.port})"
            return False
        self._log(f"MediaMTX RTSP handler ready on :{cfg.port}")

        # ── Launch FFmpeg ─────────────────────────────────────────────────────
        if not self._start_ffmpeg_with_retry(item, seek_pos):
            self._kill_mediamtx()
            return False

        self.state.status        = StreamStatus.LIVE
        self.state.started_at    = __import__("datetime").datetime.now()
        self.state.restart_count = 0
        self.state.seek_start_pos = seek_pos  # type: ignore[attr-defined]
        self._log(f"✓ LIVE → {cfg.rtsp_url}")
        if cfg.hls_enabled:
            self._log(f"  HLS  → {cfg.hls_url}")

        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{cfg.port}").start()
        return True

    def _start_mediamtx(self, cfg_file: Path) -> bool:
        # mediamtx_NNN.log       — MediaMTX's own log (written by MediaMTX via YAML logFile:)
        # mediamtx_NNN_crash.log — Python captures stdout+stderr (Go panic traces etc.)
        #
        # Using SEPARATE files is critical on Windows.  When Python opens
        # mediamtx_NNN.log for writing AND MediaMTX also tries to open the same
        # path (as specified in the YAML logFile: field), Windows may raise a
        # FILE_SHARE_VIOLATION.  MediaMTX's Go runtime then crashes silently —
        # no log output, process exits 3-5 s after the stability check, and the
        # RTSP probe times out with a misleading "No output in log file" message.
        log_f   = LOGS_DIR() / f"mediamtx_{self.state.config.port}.log"
        crash_f = LOGS_DIR() / f"mediamtx_{self.state.config.port}_crash.log"
        name    = self.state.config.name
        port    = self.state.config.port

        self._log(f"Launching MediaMTX | config={cfg_file} | log={log_f}")

        # Truncate the YAML log before each launch so _tail_log() only returns
        # output from *this* run.  Without this, stale entries from the previous
        # MediaMTX instance (e.g. LL-HLS warnings) pollute the error tail and
        # hide the real cause of a startup failure (e.g. "address already in use").
        # This is safe: MediaMTX opens the file in append mode on startup, so
        # truncating it here does not conflict with the FILE_SHARE_VIOLATION fix
        # that keeps Python from opening log_f for writing simultaneously.
        try:
            log_f.write_text("", encoding="utf-8")
        except OSError:
            pass  # Non-fatal; stale log content is a cosmetic issue only.

        try:
            # Open the CRASH log OUTSIDE a with-block so the handle stays open
            # for the lifetime of the MediaMTX process.  Using a with-block
            # closes the fd before Popen returns on some Python/Windows versions,
            # which causes MediaMTX to fail immediately when it tries to write
            # its first log line — producing an empty log and a silent crash.
            #
            # We redirect stdout+stderr to the CRASH log (separate from logFile:)
            # so that Go panic traces are captured even when MediaMTX cannot open
            # its own log file.  On Windows especially, MediaMTX writes startup
            # errors to stderr rather than the YAML log file.
            try:
                lf = open(crash_f, "w", buffering=1)   # line-buffered
            except OSError as exc:
                self._log(
                    f"Cannot open MediaMTX crash-log '{crash_f}': {exc} — "
                    "falling back to DEVNULL",
                    "WARN",
                )
                lf = open(os.devnull, "w")

            kw: Dict[str, Any] = dict(stdout=lf, stderr=lf)
            if IS_WIN:
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(
                [str(MEDIAMTX_BIN()), str(cfg_file)], **kw
            )
            # Store the handle so we can close it when we kill MediaMTX.
            proc._log_fh   = lf       # type: ignore[attr-defined]
            proc._crash_f  = crash_f  # type: ignore[attr-defined]

            self.state.mtx_proc = proc
            self._log(f"MediaMTX spawned PID={proc.pid} on :{port}")

            # Wait up to 2 s for an early crash; stable processes survive this.
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            if proc.poll() is not None:
                # Flush and close the log handle so the file is readable.
                try:
                    lf.flush()
                    lf.close()
                except Exception:
                    pass

                # Check crash log first (Go panics go there); fall back to YAML log.
                log_tail = _tail_log(crash_f, 20) or _tail_log(log_f, 20)
                detail = log_tail or "(no output — MediaMTX may have crashed before opening its log)"

                hints = []
                dl = detail.lower()
                if "unknown field" in dl:
                    match = re.search(r'unknown field "([^"]+)"', detail)
                    bad_field = match.group(1) if match else "unknown"
                    hints.append(
                        f'MediaMTX config contains unsupported YAML field: "{bad_field}". '
                        f"This is a HydraCast bug — please report it."
                    )
                if "rtp port must be even" in dl:
                    hints.append(
                        "RTP port must be even (RFC 3550). "
                        "Try an even RTSP base port (e.g. 8554, 8564 …)."
                    )
                if "address already in use" in dl or "bind" in dl:
                    hints.append(
                        f"Port {port} (or its RTP/RTCP companion) is already in use. "
                        f"Check for another MediaMTX or RTSP service running on this port."
                    )
                if not detail.strip() or detail.startswith("(no output"):
                    hints.append(
                        "MediaMTX produced no log output. "
                        "Possible causes: log file path contains characters MediaMTX cannot open, "
                        "or the binary is blocked by antivirus / Windows Defender. "
                        f"Try running '{MEDIAMTX_BIN()} {cfg_file}' manually to see the error."
                    )

                hint_str = "  HINT: " + " | ".join(hints) if hints else ""
                msg = (
                    f"MediaMTX exited immediately (code {proc.returncode}). "
                    f"Log tail:\n{detail[:800]}"
                    f"\n{hint_str}"
                )
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = msg
                self._log(msg, "ERROR")
                return False

            self._log(f"MediaMTX running stably (PID={proc.pid})")
            return True

        except FileNotFoundError:
            msg = (
                f"MediaMTX binary not found: {MEDIAMTX_BIN()}. "
                f"Run HydraCast once normally so it can auto-download MediaMTX."
            )
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = msg
            self._log(msg, "ERROR")
            return False
        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR")
            return False

    def _start_ffmpeg(self, item: PlaylistItem, seek_pos: float,
                      oneshot: bool = False, loop_count: int = -1) -> bool:
        cfg = self.state.config
        # One-shot events must NEVER loop — the _after() thread waits for proc.poll()
        # and relies on FFmpeg exiting naturally after the file ends.
        # loop_count=-1 means infinite; 0 means play once (no loop); N>0 means N extra loops.
        if oneshot:
            loop_flag = []          # play exactly once, then exit
        elif loop_count == -1:
            loop_flag = ["-stream_loop", "-1"] if len(cfg.playlist) == 1 else []
        else:
            loop_flag = ["-stream_loop", str(loop_count)] if loop_count > 0 else []
        # When stream_path is empty, push to the concrete path "stream".
        # Never use a bare rtsp://host:port/ (trailing slash = path "/") —
        # MediaMTX v1.9.1 treats "/" differently from a named path and returns
        # 400 Bad Request. The YAML uses "~all" which accepts any named path.
        _push_path = cfg.rtsp_path if cfg.rtsp_path else "stream"
        _rtsp_target = f"rtsp://127.0.0.1:{cfg.port}/{_push_path}"
        cmd = [
            str(FFMPEG_PATH()), "-hide_banner", "-loglevel", "error",
            "-re",
            "-ss", str(int(seek_pos)),
            *loop_flag,
            "-i", str(item.file_path),
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", cfg.video_bitrate, "-pix_fmt", "yuv420p", "-g", "50",
            "-c:a", "aac", "-b:a", cfg.audio_bitrate, "-ar", "44100", "-ac", "2",
            "-progress", "pipe:1", "-nostats",
            "-f", "rtsp", "-rtsp_transport", "tcp",
            _rtsp_target,
        ]

        self.state.seek_start_pos = seek_pos  # type: ignore[attr-defined]

        self._log(
            f"Launching FFmpeg | file={item.file_path.name} | "
            f"seek={_fmt_duration(seek_pos)} | "
            f"vbr={cfg.video_bitrate} abr={cfg.audio_bitrate}"
        )
        log.debug("[%s] FFmpeg command: %s", cfg.name, " ".join(cmd))

        try:
            kw: Dict[str, Any] = dict(
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
            if IS_WIN:
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(cmd, **kw)
            self.state.ffmpeg_proc = proc

            # ── Drain stderr into a thread-safe buffer ────────────────────────
            # Without draining, the stderr pipe buffer fills up (~64 KB on Linux)
            # and FFmpeg blocks waiting to write its error output, causing hangs.
            # We store the last 2 KB so _start_ffmpeg_with_retry and _monitor
            # can both read it after the process exits.
            import collections
            stderr_buf: "collections.deque[str]" = collections.deque(maxlen=50)

            def _drain_stderr(p: subprocess.Popen, buf: "collections.deque[str]") -> None:
                try:
                    for raw in p.stderr:
                        line = (raw.decode(errors="replace") if isinstance(raw, bytes) else raw).rstrip()
                        if line:
                            buf.append(line)
                            log.debug("[%s] ffmpeg stderr: %s", cfg.name, line)
                except Exception:
                    pass

            drain_t = threading.Thread(
                target=_drain_stderr, args=(proc, stderr_buf),
                daemon=True, name=f"ffmpeg-err-{cfg.port}",
            )
            drain_t.start()
            # Attach buffer to proc so _start_ffmpeg_with_retry and _monitor
            # can retrieve the captured stderr text.
            proc._stderr_buf  = stderr_buf   # type: ignore[attr-defined]
            proc._stderr_drain = drain_t     # type: ignore[attr-defined]

            if IS_LINUX and CPU_COUNT > 1:
                try:
                    core = cfg.row_index % CPU_COUNT
                    psutil.Process(proc.pid).cpu_affinity([core])
                    self._log(f"FFmpeg PID={proc.pid} pinned to CPU core {core}")
                except Exception as exc:
                    self._log(f"FFmpeg PID={proc.pid} (CPU pin failed: {exc})")
            else:
                self._log(f"FFmpeg PID={proc.pid}")
            return True

        except FileNotFoundError:
            msg = (
                f"FFmpeg binary not found: {FFMPEG_PATH()}. "
                f"Install FFmpeg and ensure it is on your PATH."
            )
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = msg
            self._log(msg, "ERROR")
            return False
        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"FFmpeg launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR")
            return False

    def _start_ffmpeg_with_retry(
        self, item: PlaylistItem, seek_pos: float,
        max_retries: int = 6, retry_delay: float = 2.0,
        oneshot: bool = False, loop_count: int = -1,
    ) -> bool:
        """
        Launch FFmpeg and retry if MediaMTX returns 400 Bad Request.

        On Windows, MediaMTX's path handler registration is async and can lag
        behind the RTSP OPTIONS probe by 1-3 seconds.  We detect the 400 and
        retry with exponential backoff (2 s, 3 s, 4 s …) rather than a fixed
        delay, which self-corrects in 1-2 retries on Linux and 2-3 on Windows.

        stderr is captured by the drain thread in _start_ffmpeg into a deque
        attached to the process; we read from there instead of the pipe.
        """
        backoff = retry_delay
        for attempt in range(1, max_retries + 1):
            if not self._start_ffmpeg(item, seek_pos, oneshot=oneshot, loop_count=loop_count):
                return False  # binary/launch error — no point retrying

            proc = self.state.ffmpeg_proc
            if proc is None:
                return False

            # Give FFmpeg up to 4 s to either stabilise or fail fast with 400.
            # Using 4 s (up from 3) gives the path handler a bit more room on
            # slower Windows systems before we declare it failed.
            deadline = time.time() + 4.0
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            if proc.poll() is None:
                # Still running after 4 s — MediaMTX accepted the push.
                return True

            # FFmpeg exited — wait briefly for the drain thread to capture stderr.
            drain = getattr(proc, "_stderr_drain", None)
            if drain is not None:
                drain.join(timeout=1.0)

            # Read from the attached buffer filled by the drain thread.
            buf = getattr(proc, "_stderr_buf", None)
            stderr_txt = "\n".join(buf) if buf else ""

            self._log(
                f"FFmpeg exited early (attempt {attempt}/{max_retries}, "
                f"code={proc.returncode})"
                + (f": {stderr_txt[:200]}" if stderr_txt else ""),
                "WARN",
            )

            is_400 = (
                "400 Bad Request" in stderr_txt
                or "400 bad request" in stderr_txt.lower()
            )

            if is_400:
                if attempt < max_retries:
                    self._log(
                        f"FFmpeg got 400 Bad Request from MediaMTX "
                        f"(attempt {attempt}/{max_retries}) — "
                        f"retrying in {backoff:.1f}s …",
                        "WARN",
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 1.5, 10.0)   # exponential, cap at 10 s
                    continue
                else:
                    self._log(
                        f"FFmpeg got 400 Bad Request after {max_retries} attempts — "
                        "MediaMTX path still not ready. Triggering auto-restart.",
                        "ERROR",
                    )
                    self.state.status    = StreamStatus.ERROR
                    self.state.error_msg = "MediaMTX 400 Bad Request (path not ready)"
                    return False
            else:
                # Non-400 error: capture it and let the caller decide.
                if proc.returncode not in (None, 0, 255):
                    self.state.status    = StreamStatus.ERROR
                    self.state.error_msg = (
                        stderr_txt[:300].strip()
                        or f"FFmpeg exited with code {proc.returncode}"
                    )
                    self._log(self.state.error_msg, "ERROR")
                    return False
                # Code 0 / 255 on a fresh start means the file ended instantly
                # (e.g. seek beyond end).  Return True so the monitor can advance.
                return True

        return False

    def _play_black(self) -> None:
        cfg = self.state.config
        self._log("Starting black-screen feed …")
        _push_path = cfg.rtsp_path if cfg.rtsp_path else "stream"
        _rtsp_target = f"rtsp://127.0.0.1:{cfg.port}/{_push_path}"
        cmd = [
            str(FFMPEG_PATH()), "-hide_banner", "-loglevel", "error", "-re",
            "-f", "lavfi", "-i", "color=black:size=1280x720:rate=25",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", cfg.video_bitrate, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", cfg.audio_bitrate,
            "-f", "rtsp", "-rtsp_transport", "tcp",
            _rtsp_target,
        ]
        try:
            kw: Dict[str, Any] = dict(
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if IS_WIN:
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.state.ffmpeg_proc = subprocess.Popen(cmd, **kw)
            self._log(f"Black screen PID={self.state.ffmpeg_proc.pid}")
        except Exception as exc:
            self._log(f"Black screen launch failed: {exc}", "ERROR")

    def _monitor(self) -> None:
        """Read FFmpeg -progress pipe:1 output and update stream state."""
        proc = self.state.ffmpeg_proc
        if proc is None:
            self._log("Monitor: no FFmpeg process to monitor.", "WARN")
            return
        my_proc = proc
        buf: Dict[str, str] = {}
        self._log("Monitor thread started.")

        while not self._stop.is_set():
            if my_proc.poll() is not None:
                break
            if self.state.ffmpeg_proc is not my_proc:
                self._log("Monitor: FFmpeg process was replaced, exiting monitor.")
                return
            try:
                line = my_proc.stdout.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                m = self._FFMPEG_PROGRESS_RE.match(line.strip())
                if not m:
                    continue
                k, v = m.group(1), m.group(2).strip()
                buf[k] = v
                if k == "progress":
                    self._apply_progress(buf)
                    buf = {}
                    # ── Periodic compliance drift check ───────────────────
                    _cfg = self.state.config
                    if (
                        _cfg.compliance_enabled
                        and not self._seeking.is_set()
                        and not self.state.oneshot_active
                    ):
                        _now  = time.time()
                        _last = self.state.compliance_last_check_ts
                        if _last == 0.0:
                            # First progress report — initialise the clock
                            # without triggering an immediate resync.
                            self.state.compliance_last_check_ts = _now
                        elif _now - _last >= max(60.0, _cfg.compliance_resync_interval):
                            # Stamp BEFORE spawning so a slow thread can't
                            # double-fire before it finishes.
                            self.state.compliance_last_check_ts = _now
                            threading.Thread(
                                target=self._compliance_check_and_resync,
                                daemon=True,
                                name=f"comp-check-{_cfg.port}",
                            ).start()
            except Exception as exc:
                log.debug("[%s] Monitor readline error: %s", self.state.config.name, exc)
                time.sleep(0.05)

        # ── Determine why we exited the loop ──────────────────────────────────
        if self._stop.is_set():
            self._log("Monitor exiting: stop flag set.")
            return
        if self._seeking.is_set():
            self._log("Monitor exiting: seek in progress.")
            return
        if self.state.ffmpeg_proc is not my_proc:
            self._log("Monitor exiting: process was replaced.")
            return
        # During a one-shot event, _after() owns cleanup and resume.
        # The monitor's only job was to feed progress — exit silently.
        if self.state.oneshot_active:
            self._log("Monitor exiting: one-shot event active — _after() handles resume.")
            return

        ret = my_proc.returncode if my_proc.returncode is not None else -1

        # stderr is drained by the thread started in _start_ffmpeg into a
        # deque attached to the proc object.  Reading the pipe directly here
        # would return empty because the drain thread already consumed it.
        drain = getattr(my_proc, "_stderr_drain", None)
        if drain is not None:
            drain.join(timeout=1.0)
        buf = getattr(my_proc, "_stderr_buf", None)
        stderr_txt = "\n".join(buf) if buf else ""

        self._log(f"FFmpeg process exited with code {ret}.")
        if stderr_txt:
            self._log(f"FFmpeg stderr: {stderr_txt[:400]}", "WARN" if ret == 0 else "ERROR")

        # Save position on clean/normal exits only
        if ret in (0, 255):
            self._save_resume_position()
        else:
            self._log(
                f"Skipping resume save on error exit (code {ret}) "
                "to avoid overwriting a valid saved position.",
                "WARN",
            )

        # ── Advance playlist (multi-file, clean exits only) ─────────────────
        # Only advance on a clean exit (0 or 255).  On an error exit, let
        # _auto_restart handle recovery via a full _do_start — advancing
        # the playlist into a broken MediaMTX session just cascades failures.
        if (ret in (0, 255)
                and not self.state.oneshot_active
                and len(self.state.config.playlist) > 1):
            self._advance_playlist()
            next_item = self._current_item()

            if next_item and not next_item.file_path.exists():
                self._log(
                    f"Next file missing: '{next_item.file_path.name}' — "
                    "invoking watchdog skip …",
                    "ERROR",
                )
                try:
                    from hc.watchdog import find_next_valid_item
                    next_item = find_next_valid_item(self.state, self._log)
                except Exception as exc:
                    self._log(f"Watchdog skip error: {exc}", "ERROR")
                    next_item = None

            if next_item and next_item.file_path.exists():
                self._log(f"Advancing to next file: {next_item.file_path.name}")
                self.state.duration = probe_duration(next_item.file_path)
                try:
                    h, m, s = next_item.start_position.split(":")
                    spos    = int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    spos = 0.0
                # ── Compliance: recalculate seek offset on each file transition ──
                _cfg2 = self.state.config
                if _cfg2.compliance_enabled:
                    try:
                        from hc.compliance import calculate_compliance_offset
                        spos, _expl2 = calculate_compliance_offset(
                            video_duration=self.state.duration,
                            broadcast_start=_cfg2.compliance_start,
                            loop_calculation=_cfg2.compliance_loop,
                        )
                        self._log(f"Compliance file-transition seek: {_expl2}")
                        self.state.compliance_last_check_ts = time.time()
                    except Exception as _exc2:
                        self._log(
                            f"Compliance transition offset failed: {_exc2} — "
                            "using playlist start position",
                            "WARN",
                        )
                # Cycle MediaMTX to clear the old publisher session; a direct
                # _start_ffmpeg without cycling gets 400 Bad Request.
                if not self._cycle_mediamtx():
                    self._log(
                        "Playlist advance: MediaMTX cycle failed — "
                        "triggering auto-restart.",
                        "ERROR",
                    )
                    self._auto_restart()
                    return
                self._start_ffmpeg_with_retry(next_item, spos)
                threading.Thread(target=self._monitor, daemon=True,
                                 name=f"mon-{self.state.config.port}").start()
                return
            else:
                if next_item:
                    self._log(
                        "All next playlist files are missing or unreadable.", "ERROR"
                    )

        if ret in (0, 255):
            self.state.status = StreamStatus.STOPPED
            self._log(f"FFmpeg exited normally (code {ret}).")
            # Only alert if this was NOT a deliberate stop
            if not self._stop.is_set() and not self.state.oneshot_active:
                try:
                    from hc.mailer import send_stop_alert
                    send_stop_alert(
                        stream_name = self.state.config.name,
                        port        = self.state.config.port,
                        reason      = f"FFmpeg exited cleanly (code {ret}) — "
                                      "playlist finished or stream ended.",
                    )
                except Exception as _mail_exc:
                    log.debug("mailer hook error: %s", _mail_exc)
        else:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = (
                stderr_txt[:300].strip() or f"FFmpeg exited with code {ret}"
            )
            self._log(
                f"FFmpeg error (code {ret}): {self.state.error_msg}", "ERROR"
            )
            try:
                from hc.mailer import send_error_alert
                send_error_alert(
                    stream_name   = self.state.config.name,
                    port          = self.state.config.port,
                    error_msg     = self.state.error_msg,
                    exit_code     = ret,
                    stderr_snippet= stderr_txt[:300] if stderr_txt else "",
                )
            except Exception as _mail_exc:
                log.debug("mailer hook error: %s", _mail_exc)
            # Only auto-restart if the stop flag is NOT set
            if not self._stop.is_set():
                self._auto_restart()

    def _apply_progress(self, data: Dict[str, str]) -> None:
        try:
            out_us = int(data.get("out_time_us", "0"))
            if out_us > 0 and self.state.duration > 0:
                elapsed = out_us / 1_000_000.0
                seek_start = getattr(self.state, "seek_start_pos", 0.0)
                abs_pos = (seek_start + elapsed) % self.state.duration
                self.state.current_pos = abs_pos
                self.state.progress    = min(99.9, abs_pos / self.state.duration * 100.0)
            fps_raw = data.get("fps", "0")
            self.state.fps     = (
                float(fps_raw) if fps_raw not in ("", "N/A") else 0.0
            )
            self.state.bitrate = (
                data.get("bitrate", "—").replace("kbits/s", "kb/s") or "—"
            )
            self.state.speed   = data.get("speed", "—").strip() or "—"
        except Exception as exc:
            log.debug("[%s] _apply_progress error: %s", self.state.config.name, exc)

    def _auto_restart(self) -> None:
        # Guard: if stop was requested while we were preparing to restart, abort.
        if self._stop.is_set():
            self._log("Auto-restart skipped: stop flag is set.", "WARN")
            return
        if self._seeking.is_set():
            self._log("Auto-restart skipped: seek in progress.", "WARN")
            return
        n = self.state.restart_count
        if n >= self.MAX_AUTO_RESTARTS:
            self._log(
                f"Max auto-restarts ({self.MAX_AUTO_RESTARTS}) reached — "
                "giving up. Check file paths, ports, and FFmpeg/MediaMTX logs.",
                "ERROR",
            )
            return
        delay = self.BACKOFF[min(n, len(self.BACKOFF) - 1)]
        self._log(f"Auto-restart #{n+1} scheduled in {delay}s …", "WARN")
        for _ in range(delay * 10):
            # Abort countdown if stop is requested during the wait
            if self._stop.is_set() or self._seeking.is_set():
                self._log("Auto-restart cancelled during countdown.")
                return
            time.sleep(0.1)
        # Final check before actually restarting
        if self._stop.is_set() or self._seeking.is_set():
            self._log("Auto-restart cancelled (stop/seek set after countdown).")
            return
        self.state.restart_count += 1
        self._log(f"Auto-restart #{self.state.restart_count} starting …", "WARN")
        self._kill_mediamtx()
        time.sleep(0.3)
        if self._start_lock.acquire(timeout=20):
            try:
                if not self._stop.is_set():
                    self._do_start()
                else:
                    self._log("Auto-restart aborted: stop flag set before _do_start.", "WARN")
            finally:
                self._start_lock.release()
        else:
            self._log("Auto-restart: could not acquire start lock — skipping.", "WARN")

    def _cycle_mediamtx(self) -> bool:
        """
        Kill MediaMTX, rewrite its YAML, and restart it, then wait for the
        port to bind.  Returns True on success.

        This must be called every time ffmpeg switches to a new source file
        (playlist advance, one-shot events, seek).  MediaMTX holds publisher
        session state — SPS/PPS, codec parameters — tied to the previous push.
        If a new ffmpeg process connects without cycling MediaMTX first, it
        gets "Could not write header / 400 Bad Request" because the server
        rejects mismatched codec parameters from the new publisher.

        Windows UDP socket note
        ───────────────────────
        _port_in_use() is a TCP-only probe.  After killing MediaMTX the TCP
        RTSP port (e.g. 8554) releases quickly, but the companion UDP ports
        (RTP = port+2, RTCP = port+3, e.g. 8556/8557) may linger on Windows
        for 1–2 s after the process exits.  A new MediaMTX spawned before
        those UDP sockets are released immediately crashes with exit code 1:
          "listen udp4 0.0.0.0:8556: bind: Only one usage of each socket
           address (protocol/network address/port) is normally permitted."
        The settle delay after the TCP-free check is set to 2.5 s on Windows
        to cover this window; Linux releases sockets immediately (0.3 s).
        """
        cfg = self.state.config
        self._kill_mediamtx()

        # ── Wait for ALL MediaMTX ports to be released ────────────────────────
        # MediaMTX binds three port families:
        #   TCP  cfg.port        — RTSP control
        #   UDP  cfg.port + 2   — RTP  (must be even, see mediamtx_cfg.py)
        #   UDP  cfg.port + 3   — RTCP
        #   TCP  cfg.hls_port   — HLS  (when enabled)
        #
        # _port_in_use() is a TCP connect-probe — it cannot detect UDP sockets.
        # On Windows, UDP sockets linger for 1–3 s after the process exits,
        # so a new MediaMTX launched too soon crashes immediately with exit 1:
        #   "listen udp4 0.0.0.0:<rtp>: bind: Only one usage of each socket"
        #
        # Strategy:
        #   1. Try to bind the RTP UDP port ourselves.  If we can bind it, the
        #      OS has released it and it is safe to launch MediaMTX.
        #   2. Also poll TCP ports with _port_in_use() as before.
        #   3. On Windows add a minimum 3 s floor before even starting the probe
        #      because the process-exit → socket-release path is asynchronous.

        import socket as _socket

        rtp_port = cfg.port + 2
        if rtp_port % 2 != 0:
            rtp_port += 1

        _tcp_ports = [cfg.port]
        if cfg.hls_enabled:
            _tcp_ports.append(cfg.hls_port)

        def _udp_port_free(port: int) -> bool:
            """
            Return True if the UDP port is fully released by the OS.

            Deliberately does NOT set SO_REUSEADDR — on Windows that flag can
            allow a bind to succeed even when another process still owns the
            socket, producing a false "free" result and causing the subsequent
            MediaMTX bind to fail with "Only one usage of each socket address".
            Without the flag, a successful bind guarantees the port is free.
            """
            try:
                s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
                s.bind(("0.0.0.0", port))
                s.close()
                return True
            except OSError:
                return False

        # Minimum floor wait on Windows before probing — the socket release is
        # asynchronous and probing too early always returns "still in use".
        if IS_WIN:
            time.sleep(3.0)

        _deadline = time.time() + 8.0
        while time.time() < _deadline:
            tcp_free = all(not _port_in_use(p) for p in _tcp_ports)
            udp_free = _udp_port_free(rtp_port)
            if tcp_free and udp_free:
                # Both TCP and UDP are confirmed free.  Small extra settle for
                # any remaining kernel state on Windows before MediaMTX binds.
                if IS_WIN:
                    time.sleep(0.3)
                break
            time.sleep(0.2)
        else:
            # Timeout: force-kill any orphan still holding a port.
            for _p in _tcp_ports:
                if _port_in_use(_p):
                    self._log(
                        f"Port {_p} still in use after 8 s — force-killing orphan.", "WARN"
                    )
                    _kill_orphan_on_port(_p)
            if not _udp_port_free(rtp_port):
                self._log(
                    f"UDP RTP port {rtp_port} still in use after 8 s — "
                    "MediaMTX may crash on restart.", "WARN"
                )
            _settle2 = 2.0 if IS_WIN else 0.5
            time.sleep(_settle2)
        try:
            mtx_cfg = MediaMTXConfig.write(self.state)
        except Exception as exc:
            self._log(f"_cycle_mediamtx: failed to write MediaMTX config: {exc}", "ERROR")
            return False
        if not self._start_mediamtx(mtx_cfg):
            self._log("_cycle_mediamtx: MediaMTX failed to restart.", "ERROR")
            return False
        _push_path = cfg.rtsp_path if cfg.rtsp_path else "stream"
        mtx_proc2  = self.state.mtx_proc

        def _mtx_alive2() -> bool:
            return mtx_proc2 is not None and mtx_proc2.poll() is None

        if not _wait_for_rtsp(cfg.port, timeout=self.MTX_READY_TIMEOUT,
                               path=_push_path, check_alive=_mtx_alive2):
            self._log("_cycle_mediamtx: MediaMTX RTSP handler not ready on :{}.".format(cfg.port), "ERROR")
            self._kill_mediamtx()
            return False
        # Path probe confirmed — no extra settle delay needed.
        return True

    def _kill_ffmpeg(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc and proc.poll() is None:
            self._log(f"Killing FFmpeg PID={proc.pid}")
            try:
                proc.terminate()
                proc.wait(timeout=6)
                self._log(f"FFmpeg PID={proc.pid} terminated.")
            except subprocess.TimeoutExpired:
                self._log(f"FFmpeg PID={proc.pid} did not terminate in 6s, killing.", "WARN")
                proc.kill()
            except Exception as exc:
                self._log(f"FFmpeg kill error: {exc}", "WARN")
        self.state.ffmpeg_proc = None

    def _kill_mediamtx(self) -> None:
        proc = self.state.mtx_proc
        if proc and proc.poll() is None:
            self._log(f"Killing MediaMTX PID={proc.pid}")
            try:
                proc.terminate()
                proc.wait(timeout=6)
                self._log(f"MediaMTX PID={proc.pid} terminated.")
            except subprocess.TimeoutExpired:
                self._log(f"MediaMTX PID={proc.pid} did not terminate in 6s, killing.", "WARN")
                proc.kill()
            except Exception as exc:
                self._log(f"MediaMTX kill error: {exc}", "WARN")
        # Close the log file handle that was kept open for MediaMTX's lifetime.
        if proc is not None:
            lf = getattr(proc, "_log_fh", None)
            if lf is not None:
                try:
                    lf.flush()
                    lf.close()
                except Exception:
                    pass
        self.state.mtx_proc = None


# =============================================================================
# HELPER: read tail of a log file
# =============================================================================
def _tail_log(path: Path, n: int = 12) -> str:
    """Return the last *n* lines of a file as a single string."""
    try:
        if not path.exists() or path.stat().st_size == 0:
            return ""
        with open(path, errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:]).strip()
    except Exception as exc:
        log.debug("_tail_log failed for %s: %s", path, exc)
        return ""
