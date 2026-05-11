"""
hc/worker.py  —  LogBuffer, media probe helpers, and StreamWorker.
"""
from __future__ import annotations

import json
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
from hc.utils import _fmt_duration, _kill_orphan_on_port, _port_in_use, _wait_for_port


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
        with self._lock:
            self._entries.append((f"[{ts}] {msg}", level))
            if len(self._entries) > self._cap:
                self._entries.pop(0)

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
    try:
        r = subprocess.run(
            [FFPROBE_PATH(), "-v", "quiet",
             "-show_entries", "format=duration",
             "-of", "csv=p=0", str(file_path)],
            capture_output=True, text=True, timeout=20,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def probe_metadata(file_path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "duration": 0.0, "size": 0, "video_codec": "", "audio_codec": "",
        "width": 0, "height": 0, "fps": "", "bitrate": 0,
    }
    try:
        meta["size"] = file_path.stat().st_size
    except Exception:
        pass
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
    except Exception:
        pass
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
    except Exception:
        pass
    return None


# =============================================================================
# STREAM WORKER
# =============================================================================
class StreamWorker:
    MAX_AUTO_RESTARTS = 8
    BACKOFF           = [5, 10, 20, 40, 60, 120, 120, 120]
    MTX_READY_TIMEOUT = 13.0

    _FFMPEG_PROGRESS_RE = re.compile(r"^(\w+)=(.+)$")

    def __init__(self, state: StreamState, glog: LogBuffer) -> None:
        self.state       = state
        self.glog        = glog
        self._stop       = threading.Event()
        self._seeking    = threading.Event()
        self._start_lock = threading.Lock()

    # ── Logging ───────────────────────────────────────────────────────────────
    def _log(self, msg: str, level: str = "INFO") -> None:
        full = f"[{self.state.config.name}] {msg}"
        self.state.log_add(full)
        self.glog.add(full, level)
        logging.log(
            logging.WARNING if level == "WARN" else
            (logging.ERROR if level == "ERROR" else logging.INFO), full
        )

    # ── Playlist helpers ──────────────────────────────────────────────────────
    def _build_order(self) -> List[int]:
        n     = len(self.state.config.playlist)
        order = list(range(n))
        if self.state.config.shuffle:
            random.shuffle(order)
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
        self.state.playlist_index += 1
        if self.state.playlist_index >= len(self.state.playlist_order):
            self.state.playlist_index = 0
            self.state.loop_count    += 1
            if self.state.config.shuffle:
                self.state.playlist_order = self._build_order()

    # ── Public API ────────────────────────────────────────────────────────────
    def start(self, seek_override: Optional[float] = None) -> bool:
        if not self._start_lock.acquire(blocking=False):
            self._log("start() already in progress — skipping duplicate call.", "WARN")
            return False
        try:
            return self._do_start(seek_override)
        finally:
            self._start_lock.release()

    def stop(self) -> None:
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
        self._log("Stream stopped.")

    def restart(self, seek: Optional[float] = None) -> None:
        self._log("Restarting …")
        self.stop()
        time.sleep(0.8)
        self.start(seek_override=seek)

    def seek(self, seconds: float) -> None:
        self._seeking.set()
        self._log(f"Seeking to {_fmt_duration(seconds)} …")
        self._kill_ffmpeg()
        time.sleep(0.4)
        item = self._current_item()
        if item is None:
            self._seeking.clear()
            return
        self.state.duration = probe_duration(item.file_path)
        self._start_ffmpeg(item, max(0.0, seconds))
        self._seeking.clear()
        self.state.status = StreamStatus.LIVE
        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{self.state.config.port}").start()

    def skip_to_next(self) -> None:
        self._seeking.set()
        self._advance_playlist()
        self._kill_ffmpeg()
        time.sleep(0.3)
        item = self._current_item()
        if item is None:
            self._seeking.clear()
            return
        self.state.duration = probe_duration(item.file_path)
        try:
            h, m, s = item.start_position.split(":")
            spos = int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            spos = 0.0
        self._start_ffmpeg(item, spos)
        self._seeking.clear()
        self.state.status = StreamStatus.LIVE
        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{self.state.config.port}").start()

    def play_oneshot(self, event: OneShotEvent) -> None:
        self._log(f"One-shot event: {event.file_path.name}", "INFO")
        self.state.oneshot_active = True
        self._kill_ffmpeg()
        time.sleep(0.3)
        try:
            h, m, s = event.start_pos.split(":")
            seek_secs = int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            seek_secs = 0.0
        item = PlaylistItem(file_path=event.file_path, start_position=event.start_pos)
        self.state.duration = probe_duration(item.file_path)
        self._start_ffmpeg(item, seek_secs)

        def _after() -> None:
            proc = self.state.ffmpeg_proc
            if proc:
                while not self._stop.is_set() and proc.poll() is None:
                    time.sleep(0.5)
            self.state.oneshot_active = False
            if self._stop.is_set():
                return
            if event.post_action == "stop":
                self.stop()
            elif event.post_action == "black":
                self._play_black()
            else:
                item2 = self._current_item()
                if item2:
                    self._start_ffmpeg(item2, 0.0)
                    threading.Thread(target=self._monitor, daemon=True,
                                     name=f"mon-{self.state.config.port}").start()

        threading.Thread(target=_after, daemon=True,
                         name=f"oneshot-{self.state.config.port}").start()

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _do_start(self, seek_override: Optional[float] = None) -> bool:
        cfg = self.state.config
        self._stop.clear()

        if not cfg.playlist:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = "No files in playlist"
            return False

        item = self._current_item()
        if item is None or not item.file_path.exists():
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = (
                f"File not found: {item.file_path if item else '?'}"
            )
            self._log(self.state.error_msg, "ERROR")
            return False

        self.state.status   = StreamStatus.STARTING
        self.state.duration = probe_duration(item.file_path)

        seek_pos = seek_override
        if seek_pos is None:
            pos_str = item.start_position
            try:
                h, m, s  = pos_str.split(":")
                seek_pos = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                seek_pos = 0.0

        if _port_in_use(cfg.port):
            self._log(f"Port {cfg.port} occupied — killing orphan …", "WARN")
            _kill_orphan_on_port(cfg.port)
            time.sleep(0.8)
            if _port_in_use(cfg.port):
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = f"Port {cfg.port} still in use"
                self._log(self.state.error_msg, "ERROR")
                return False

        mtx_cfg = MediaMTXConfig.write(self.state)
        if not self._start_mediamtx(mtx_cfg):
            return False

        self._log(f"Waiting for MediaMTX :{cfg.port} …")
        if not _wait_for_port(cfg.port, timeout=self.MTX_READY_TIMEOUT):
            self._log(f"MediaMTX port-bind timeout :{cfg.port}", "ERROR")
            self._kill_mediamtx()
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX timeout (:{cfg.port})"
            return False

        if not self._start_ffmpeg(item, seek_pos):
            self._kill_mediamtx()
            return False

        self.state.status        = StreamStatus.LIVE
        self.state.started_at    = __import__("datetime").datetime.now()
        self.state.restart_count = 0
        self._log(f"Live → {cfg.rtsp_url}")
        if cfg.hls_enabled:
            self._log(f"HLS  → {cfg.hls_url}")

        threading.Thread(target=self._monitor, daemon=True,
                         name=f"mon-{cfg.port}").start()
        return True

    def _start_mediamtx(self, cfg_file: Path) -> bool:
        log_f = LOGS_DIR() / f"mediamtx_{self.state.config.port}.log"
        try:
            with open(log_f, "a") as lf:
                kw: Dict[str, Any] = dict(stdout=lf, stderr=subprocess.PIPE)
                if IS_WIN:
                    kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                proc = subprocess.Popen(
                    [str(MEDIAMTX_BIN()), str(cfg_file)], **kw)
            self.state.mtx_proc = proc
            self._log(f"MediaMTX PID {proc.pid} on :{self.state.config.port}")

            # Wait up to 1.5 s for stable startup
            deadline = time.time() + 1.5
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            if proc.poll() is not None:
                stderr_out = b""
                try:
                    stderr_out = proc.stderr.read() or b""
                except Exception:
                    pass
                stderr_txt = stderr_out.decode(errors="replace").strip()

                log_tail = ""
                try:
                    with open(log_f) as lf2:
                        lines = lf2.readlines()
                        log_tail = "".join(lines[-8:]).strip()
                except Exception:
                    pass

                detail = stderr_txt or log_tail or "(no output captured)"
                # Helpful hint for the common RTP even-port requirement
                if "rtp port must be even" in detail.lower():
                    detail += (
                        " → HydraCast v5 computes even RTP ports automatically. "
                        "If you see this, your port may be oddly spaced — "
                        "try using an even RTSP base port (e.g. 8554, 8564 …)."
                    )
                msg = (
                    f"MediaMTX exited immediately (code {proc.returncode}). "
                    f"Hint: {detail[:500]}"
                )
                self.state.status    = StreamStatus.ERROR
                self.state.error_msg = msg
                self._log(msg, "ERROR")
                return False

            def _drain(p: subprocess.Popen) -> None:
                try:
                    for raw in p.stderr:
                        line = (
                            raw.decode(errors="replace") if isinstance(raw, bytes) else raw
                        ).strip()
                        if line:
                            logging.warning("MTX stderr [%d]: %s", p.pid, line)
                except Exception:
                    pass

            threading.Thread(target=_drain, args=(proc,), daemon=True).start()
            return True

        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"MediaMTX launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR")
            return False

    def _start_ffmpeg(self, item: PlaylistItem, seek_pos: float) -> bool:
        cfg       = self.state.config
        loop_flag = ["-stream_loop", "-1"] if len(cfg.playlist) == 1 else []
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
            f"rtsp://127.0.0.1:{cfg.port}/{cfg.rtsp_path}",
        ]
        try:
            kw: Dict[str, Any] = dict(
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
            if IS_WIN:
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(cmd, **kw)
            self.state.ffmpeg_proc = proc

            if IS_LINUX and CPU_COUNT > 1:
                try:
                    core = cfg.row_index % CPU_COUNT
                    psutil.Process(proc.pid).cpu_affinity([core])
                    self._log(f"FFmpeg PID {proc.pid} → core {core}")
                except Exception:
                    self._log(f"FFmpeg PID {proc.pid}")
            else:
                self._log(f"FFmpeg PID {proc.pid}")
            return True
        except Exception as exc:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = f"FFmpeg launch failed: {exc}"
            self._log(self.state.error_msg, "ERROR")
            return False

    def _play_black(self) -> None:
        cfg = self.state.config
        cmd = [
            str(FFMPEG_PATH()), "-hide_banner", "-loglevel", "error", "-re",
            "-f", "lavfi", "-i", "color=black:size=1280x720:rate=25",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", cfg.video_bitrate, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", cfg.audio_bitrate,
            "-f", "rtsp", "-rtsp_transport", "tcp",
            f"rtsp://127.0.0.1:{cfg.port}/{cfg.rtsp_path}",
        ]
        try:
            kw: Dict[str, Any] = dict(
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if IS_WIN:
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.state.ffmpeg_proc = subprocess.Popen(cmd, **kw)
        except Exception as exc:
            self._log(f"Black screen launch failed: {exc}", "ERROR")

    def _monitor(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc is None:
            return
        my_proc = proc
        buf: Dict[str, str] = {}

        while not self._stop.is_set():
            if my_proc.poll() is not None:
                break
            if self.state.ffmpeg_proc is not my_proc:
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
            except Exception:
                time.sleep(0.05)

        if self._stop.is_set():                    return
        if self._seeking.is_set():                 return
        if self.state.ffmpeg_proc is not my_proc:  return

        # Advance to next playlist item
        if (not self.state.oneshot_active
                and len(self.state.config.playlist) > 1):
            self._advance_playlist()
            next_item = self._current_item()
            if next_item and next_item.file_path.exists():
                self.state.duration = probe_duration(next_item.file_path)
                try:
                    h, m, s = next_item.start_position.split(":")
                    spos    = int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    spos = 0.0
                time.sleep(0.2)
                self._start_ffmpeg(next_item, spos)
                threading.Thread(target=self._monitor, daemon=True,
                                 name=f"mon-{self.state.config.port}").start()
                return

        ret = my_proc.returncode if my_proc.returncode is not None else -1
        stderr_txt = ""
        try:
            if my_proc.stderr:
                stderr_txt = my_proc.stderr.read(400)
        except Exception:
            pass

        if ret in (0, 255):
            self.state.status = StreamStatus.STOPPED
            self._log(f"FFmpeg exited normally (code {ret}).")
        else:
            self.state.status    = StreamStatus.ERROR
            self.state.error_msg = (
                stderr_txt[:200].strip() or f"FFmpeg exited code {ret}"
            )
            self._log(self.state.error_msg, "ERROR")
            self._auto_restart()

    def _apply_progress(self, data: Dict[str, str]) -> None:
        try:
            out_us = int(data.get("out_time_us", "0"))
            if out_us > 0 and self.state.duration > 0:
                pos = (out_us / 1_000_000.0) % self.state.duration
                self.state.current_pos = pos
                self.state.progress    = min(99.9, pos / self.state.duration * 100.0)
            fps_raw = data.get("fps", "0")
            self.state.fps     = (
                float(fps_raw) if fps_raw not in ("", "N/A") else 0.0
            )
            self.state.bitrate = (
                data.get("bitrate", "—").replace("kbits/s", "kb/s") or "—"
            )
            self.state.speed   = data.get("speed", "—").strip() or "—"
        except Exception:
            pass

    def _auto_restart(self) -> None:
        if self._seeking.is_set():
            self._log("Skipping auto-restart: seek in progress.", "WARN")
            return
        n = self.state.restart_count
        if n >= self.MAX_AUTO_RESTARTS:
            self._log(
                f"Max auto-restarts ({self.MAX_AUTO_RESTARTS}) reached — "
                "giving up. Check your file paths and stream config.",
                "ERROR",
            )
            return
        delay = self.BACKOFF[min(n, len(self.BACKOFF) - 1)]
        self._log(f"Auto-restart #{n+1} in {delay}s …", "WARN")
        for _ in range(delay * 10):
            if self._stop.is_set() or self._seeking.is_set():
                return
            time.sleep(0.1)
        if not self._stop.is_set() and not self._seeking.is_set():
            self.state.restart_count += 1
            self._kill_mediamtx()
            time.sleep(0.3)
            self.start()

    def _kill_ffmpeg(self) -> None:
        proc = self.state.ffmpeg_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass
        self.state.ffmpeg_proc = None

    def _kill_mediamtx(self) -> None:
        proc = self.state.mtx_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass
        self.state.mtx_proc = None
