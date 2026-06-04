"""hc/web_handler.py  —  WebHandler and supporting helpers for HydraCast Web UI."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import psutil

from hc.constants import (
    APP_VER, BASE_DIR, MEDIA_DIR, SUPPORTED_EXTS, UPLOAD_MAX_BYTES,
    get_web_port, get_media_roots, add_media_root, remove_media_root, set_media_roots,
    get_web_port,
)
from hc.json_manager import JSONManager
from hc.models import OneShotEvent, PlaylistItem, StreamConfig, StreamStatus
from hc.utils import _fmt_duration, _fmt_size, _local_ip, _safe_path
from hc.web_html import _HTML
from hc.web_csvmanager import CSVManager
from hc import APP_NAME as _APP_NAME, APP_VER as _APP_VER_INIT
from hc.web_access_log import log_access as _log_access

# Pre-render the HTML template with APP_NAME from hc/__init__.py
_HTML_RENDERED = _HTML.replace("__APP_NAME__", _APP_NAME).replace("__APP_VER__", _APP_VER_INIT)

log = logging.getLogger(__name__)

# Module-level manager reference (set by hydracast.py)
_WEB_MANAGER = None


# =============================================================================
# MULTI-ROOT PATH HELPERS
# =============================================================================

def _safe_in_root(target: Path, root: Path) -> Optional[Path]:
    """
    Return resolved *target* if it sits inside *root*; None otherwise.
    Works for any root directory, not just MEDIA_DIR().
    """
    try:
        resolved_target = target.resolve()
        resolved_root   = root.resolve()
        resolved_target.relative_to(resolved_root)
        return resolved_target
    except (ValueError, OSError):
        return None


def _safe_in_any_root(target: Path) -> Optional[Path]:
    """
    Return resolved *target* if it sits inside ANY configured media root.
    Use instead of _safe_path(p, MEDIA_DIR()) for multi-root support.
    """
    try:
        resolved = target.resolve()
    except OSError:
        return None
    for root in get_media_roots():
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    return None


def _decode_upload_subdir(subdir: str) -> Optional[Path]:
    """
    Resolve an upload subdir value to an absolute directory path.

    Accepts two formats:
      "@N/rel/path"  — multi-root encoded (root N, relative sub-path)
      "@N"           — root N itself
      "rel/path"     — legacy: relative to MEDIA_DIR() root 0
      ""             — MEDIA_DIR() (default root)

    Returns the absolute directory Path, or None if invalid/outside roots.
    """
    from hc.web_filemanager import _decode_root
    roots = get_media_roots()
    if not roots:
        return None

    subdir = subdir.strip()
    if not subdir:
        return roots[0].resolve()

    if subdir.startswith("@"):
        decoded = _decode_root(subdir)
        if decoded is None:
            return None
        _, root_dir, rel_within = decoded
        resolved_root = root_dir.resolve()
        if rel_within:
            target = resolved_root / rel_within
            return _safe_in_root(target, resolved_root)
        return resolved_root
    else:
        # Legacy bare relative path → root 0 (MEDIA_DIR)
        root = roots[0].resolve()
        target = root / subdir
        return _safe_in_root(target, root)

def _decode_fm_path_to_absolute(raw: str) -> Optional[Path]:
    """
    Convert any path string the frontend may send into a real absolute Path.

    Accepts:
      "@N/rel/path"  — multi-root encoded (from _get_files / file-manager)
      "@N"           — a root directory itself
      "/abs/path"    — already absolute (legacy or direct entry)
      "rel/path"     — relative, resolved against root-0 (MEDIA_DIR)

    Returns the resolved absolute Path (confirmed inside a valid media root),
    or None if the path is invalid, escapes a root, or cannot be resolved.

    This is the single conversion point that fixes the
    "Folder/file not found: '@2/21.211'" class of errors where the frontend
    sends @N/rel encoded paths and the backend was calling Path() on them
    directly.
    """
    if not raw:
        return None
    raw = raw.strip()

    # Strip any @start_position or #priority suffixes that _plToStr appends
    # (e.g. "@2/21.211/file.mp4@00:01:00#2") before doing path decode.
    # Strategy: walk from the end, stripping a trailing #priority first, then
    # a trailing @HH:MM:SS start-position, being careful NOT to strip the
    # root-index @N prefix which always appears at the start.
    import re as _re
    # Strip trailing #priority
    raw = _re.sub(r'#\d+$', '', raw).strip()
    # Strip trailing @HH:MM:SS start-position  (NOT the @N prefix at start)
    raw = _re.sub(r'@\d{1,2}:\d{2}:\d{2}$', '', raw).strip()

    # ── @N / @N/rel encoded path (from file-manager) ─────────────────────────
    if raw.startswith("@"):
        from hc.web_filemanager import _decode_root, _safe_in_root as _fm_sir
        decoded = _decode_root(raw)
        if decoded is None:
            return None
        _, root_dir, rel_within = decoded
        try:
            resolved_root = root_dir.resolve()
        except Exception:
            resolved_root = root_dir
        if rel_within:
            target = resolved_root / rel_within
            return _fm_sir(target, resolved_root)
        return resolved_root if resolved_root.exists() else None

    # ── Absolute path ─────────────────────────────────────────────────────────
    p = Path(raw)
    if p.is_absolute():
        return _safe_in_any_root(p)

    # ── Relative path → root-0 fallback ──────────────────────────────────────
    roots = get_media_roots()
    if roots:
        candidate = roots[0].resolve() / raw
        return _safe_in_any_root(candidate)
    return None


# =============================================================================
# SECURITY HEADERS
# =============================================================================
_SEC_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options":        "SAMEORIGIN",
    "Cache-Control":          "no-store",
}


# =============================================================================
# LIBRARY CACHE
# =============================================================================
_LIB_CACHE:    Optional[List[Dict[str, Any]]] = None
_LIB_CACHE_TS: float = 0.0
_LIB_LOCK = threading.Lock()

def _get_library_cached() -> List[Dict[str, Any]]:
    from hc.worker import probe_metadata
    global _LIB_CACHE, _LIB_CACHE_TS
    with _LIB_LOCK:
        if _LIB_CACHE is not None and (time.time() - _LIB_CACHE_TS) < 60.0:
            return _LIB_CACHE
    result: List[Dict[str, Any]] = []
    roots = get_media_roots()
    for root in roots:
        if not root.is_dir():
            continue
        for ext in SUPPORTED_EXTS:
            for f in root.rglob(f"*{ext}"):
                try:
                    meta = probe_metadata(f)
                    try:
                        rel = str(f.relative_to(root))
                    except ValueError:
                        rel = str(f)
                    result.append({
                        "path":          rel,
                        "full_path":     str(f),
                        "root":          str(root),
                        "size":          _fmt_size(meta["size"]),
                        "size_bytes":    meta["size"],
                        "duration":      _fmt_duration(meta["duration"]) if meta["duration"] else "—",
                        "duration_secs": meta["duration"],
                        "video_codec":   meta["video_codec"],
                        "audio_codec":   meta["audio_codec"],
                        "width":         meta["width"],
                        "height":        meta["height"],
                        "fps":           meta["fps"],
                        "bitrate":       meta["bitrate"],
                    })
                except Exception:
                    pass
    # Deduplicate by full_path (overlapping/symlinked roots)
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for item in result:
        if item["full_path"] not in seen:
            seen.add(item["full_path"])
            deduped.append(item)
    deduped.sort(key=lambda x: x["path"])
    with _LIB_LOCK:
        _LIB_CACHE    = deduped
        _LIB_CACHE_TS = time.time()
    return deduped

def _invalidate_lib_cache() -> None:
    global _LIB_CACHE, _LIB_CACHE_TS
    with _LIB_LOCK:
        _LIB_CACHE = None; _LIB_CACHE_TS = 0.0




def _notify_folder_upload(upload_dir: Path) -> None:
    """
    After a successful upload into *upload_dir*, walk all active streams that
    have a folder_source.  If the stream's folder_source is *upload_dir* or
    any parent of *upload_dir*, invalidate its in-memory playlist so that the
    next start/restart picks up the new files automatically.

    This does NOT restart the stream — it only marks the playlist as stale so
    the worker's folder-rescan logic runs on the very next _do_start().
    """
    mgr = _WEB_MANAGER
    if mgr is None:
        return
    try:
        upload_resolved = upload_dir.resolve()
        for st in mgr.states:
            cfg = st.config
            if cfg.folder_source is None:
                continue
            try:
                folder_resolved = cfg.folder_source.resolve()
            except Exception:
                continue
            # Match if upload landed in the folder or a subfolder of it.
            try:
                upload_resolved.relative_to(folder_resolved)
                is_related = True
            except ValueError:
                is_related = (folder_resolved == upload_resolved)
            if not is_related:
                continue
            # Trigger a rescan immediately (non-blocking)
            import threading as _thr
            from hc.folder_scanner import scan_folder
            def _rescan(cfg=cfg, folder=folder_resolved):
                try:
                    items, warnings = scan_folder(folder)
                    if items:
                        cfg.playlist = items
                        log.info(
                            "web upload: refreshed playlist for '%s' "
                            "(%d files from %s)",
                            cfg.name, len(items), folder.name,
                        )
                    for w in warnings:
                        log.warning("web upload folder scan: %s", w)
                except Exception as exc:
                    log.warning(
                        "web upload: folder rescan for '%s' failed: %s",
                        cfg.name, exc,
                    )
            _thr.Thread(target=_rescan, daemon=True,
                        name=f"upload-rescan-{cfg.name}").start()
    except Exception as exc:
        log.debug("_notify_folder_upload error: %s", exc)

def _get_next_in_queue(st, cfg, n=2):
    """
    Return the next *n* playlist file names after the currently playing item.

    Uses playlist_order (which reflects compliance pinning and shuffle state)
    so the sequence shown always matches what will actually play next.

    Weekday ordering
    ────────────────
    For any playlist whose files carry day-tags (_MON_, _TUE_, … _SUN_),
    the remaining items are re-sorted by their day-of-week distance from
    today so the UI always shows the true broadcast week ahead:
      today=THU → +1=FRI, +2=SAT, +3=SUN, +4=MON, +5=TUE, +6=WED

    This applies regardless of whether compliance mode is enabled.  Without
    this sort, a folder scan that returns files alphabetically would show
    the wrong sequence (_MON_ +1, _TUE_ +2) when today is Thursday.

    Shuffle streams keep their random walk order (shuffled playlists never
    have meaningful day-tags).  Untagged files always sort to the end.
    """
    import re as _re
    from datetime import datetime as _dt

    playlist = cfg.playlist
    if not playlist:
        return []
    order = getattr(st, "playlist_order", None) or list(range(len(playlist)))
    idx   = getattr(st, "playlist_index", 0) or 0

    # Collect ALL remaining items in walk order (wraps around).
    remaining = []
    for offset in range(1, len(order)):
        next_ord_idx = (idx + offset) % len(order)
        pl_idx = order[next_ord_idx]
        try:
            remaining.append(playlist[pl_idx].file_path.name)
        except (IndexError, AttributeError):
            pass

    # Re-order by weekday distance from today whenever the playlist contains
    # day-tagged files (works for both compliance and non-compliance streams).
    # Shuffle streams are excluded — their intentional random order must be
    # preserved, and shuffled playlists don't use day-tags.
    _DAY_TAG = {
        "MON": 0, "TUE": 1, "WED": 2, "THU": 3,
        "FRI": 4, "SAT": 5, "SUN": 6,
    }
    _DAY_RE = _re.compile(r'_(MON|TUE|WED|THU|FRI|SAT|SUN)_', _re.IGNORECASE)

    _is_shuffled = getattr(cfg, "shuffle", False)

    if not _is_shuffled and len(remaining) > 1:
        # Check if at least one remaining file has a day-tag.
        _has_day_tags = any(_DAY_RE.search(f) for f in remaining)

        if _has_day_tags:
            today = _dt.now().weekday()  # 0=Mon … 6=Sun

            def _day_distance(filename: str) -> int:
                """
                Days forward from today until this file's tagged weekday.
                Returns 7 for same-day (next cycle, plays last among tagged)
                and 7+pos for untagged files so they always trail tagged ones.
                """
                m = _DAY_RE.search(filename)
                if not m:
                    return 7 + len(remaining)
                file_day = _DAY_TAG.get(m.group(1).upper(), 7)
                dist = (file_day - today) % 7
                # dist == 0 means same weekday as today → put at end of tagged
                return dist if dist > 0 else 7

            remaining.sort(key=_day_distance)

    return remaining[:n]



def _active_event_name(st, cfg, mgr) -> Optional[str]:
    """
    Return the filename the UI should display as the 'active event' label.

    Logic (evaluated in order):

    1.  If oneshot IS active AND current_file is already populated
        -> return None (the file name is already visible via current_file; no
           need to duplicate it in active_event).

    2.  If oneshot IS active AND current_file is None
        -> the worker does not expose the oneshot path through current_file().
           Fall back: look for the in-flight event for this stream.
           - First try events where ev.played is False (event fired but worker
             has not yet marked it done).
           - If none found (worker marks played=True on trigger, not on finish),
             take the most recently fired event (highest play_at, played=True).

    3.  No oneshot active
        -> show the next pending (unplayed) event name, or - if current_file is
           also None during a brief post-event resume transition - show the
           most recently played event name as a transient placeholder.
    """
    oneshot_active = bool(getattr(st, "oneshot_active", False))
    stream_events = [ev for ev in mgr.events if ev.stream_name == cfg.name]

    if oneshot_active:
        # During a oneshot, current_file() returns the playlist/compliance file
        # (the playlist index never advances during a oneshot), NOT the oneshot
        # file.  Never call it here — go straight to active_oneshot_event which
        # play_oneshot() sets to the exact event being played right now.
        active_ev = getattr(st, "active_oneshot_event", None)
        if active_ev is not None:
            return active_ev.file_path.name
        # Fallback: active_oneshot_event not yet set or already cleared —
        # take the most recently fired event (highest play_at, played=True).
        played_events = sorted(
            (ev for ev in stream_events if ev.played),
            key=lambda e: e.play_at,
            reverse=True,
        )
        return played_events[0].file_path.name if played_events else None

    # No oneshot active — need current_file only for the non-oneshot cases below.
    cf_raw = (
        st.current_file()
        if callable(getattr(st, "current_file", None))
        else getattr(st, "current_file", None)
    )

    # No oneshot active -- show next pending event.
    pending = next(
        (ev.file_path.name for ev in stream_events if not ev.played),
        None,
    )
    if pending:
        return pending
    # If current_file is also None (brief resume transition), use the last
    # played event as a transient placeholder so the card isn't blank.
    if not cf_raw:
        played_events = sorted(
            (ev for ev in stream_events if ev.played),
            key=lambda e: e.play_at,
            reverse=True,
        )
        return played_events[0].file_path.name if played_events else None
    return None


# =============================================================================
# REQUEST HANDLER
# =============================================================================
from hc.web_filemanager import _FileManagerMixin   # provides _get_files, _handle_file_op
from hc.web_handlers_calendar import _CalendarHandlersMixin

class WebHandler(_CalendarHandlersMixin, _FileManagerMixin, BaseHTTPRequestHandler):

    def log_message(self, *args: Any) -> None:
        pass  # access logging is done in _send() via hc.web_access_log

    def _send(self, code: int, body: Union[str, bytes], ct: str = "application/json") -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in _SEC_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        # ── Structured access log (IP · method · path · status · bytes) ──────
        try:
            _log_access(self, code, len(body))
        except Exception:
            pass

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data, default=str), "application/json")

    def _serve_static(self, url_path: str) -> None:
        """
        Serve a static file from <BASE_DIR>/static/ or <BASE_DIR>/resources/.
        Supports: .png .jpg .jpeg .gif .webp .svg .ico .css .js
        Place logo at <BASE_DIR>/resources/logo.png — it will be served as /resources/logo.png.
        Any file under <BASE_DIR>/static/ is served as /static/<filename>.
        """
        _MIME = {
            ".png":  "image/png",
            ".jpg":  "image/jpeg", ".jpeg": "image/jpeg",
            ".gif":  "image/gif",
            ".webp": "image/webp",
            ".svg":  "image/svg+xml",
            ".ico":  "image/x-icon",
            ".css":  "text/css",
            ".js":   "application/javascript",
        }
        # Resolve file on disk
        name = url_path.lstrip("/")                     # e.g. "resources/logo.png" or "static/x.png"
        candidate = BASE_DIR() / name
        if not candidate.exists() or not candidate.is_file():
            self._send(404, b"Not Found", "text/plain")
            return
        # Safety: must stay inside BASE_DIR
        try:
            candidate.resolve().relative_to(BASE_DIR().resolve())
        except ValueError:
            self._send(403, b"Forbidden", "text/plain")
            return
        ext  = candidate.suffix.lower()
        mime = _MIME.get(ext, "application/octet-stream")
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",   mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control",  "public, max-age=86400")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"
        qs     = parse_qs(parsed.query)

        routes: Dict[str, Any] = {
            "/":                   lambda: self._send(200, _HTML_RENDERED, "text/html; charset=utf-8"),
            "/index.html":         lambda: self._send(200, _HTML_RENDERED, "text/html; charset=utf-8"),
            "/health":             self._get_health,
            "/api/streams":        self._get_streams,
            "/api/streams_config": self._get_streams_config,
            "/api/library":        self._get_library,
            "/api/subdirs":        self._get_subdirs,
            "/api/media_roots":    self._get_media_roots,
            "/api/files":          lambda: self._get_files(qs),
            "/api/events":         self._get_events,
            "/api/holidays":        lambda: self._get_holidays(qs),
            "/api/holidays/custom": self._get_holidays_custom,
            "/api/settings":        self._get_settings,
            "/api/settings/schema": self._get_settings_schema,
            "/api/logs":           lambda: self._get_logs(qs),
            "/api/system_stats":   self._get_system_stats,
            "/api/stream_detail":  lambda: self._get_stream_detail(qs),
            "/api/stream_view":    lambda: self._get_stream_view(qs),
            "/api/check_port":     lambda: self._get_check_port(qs),
            "/api/suggest_port":   lambda: self._get_suggest_port(qs),
            "/api/urls_csv":               lambda: self._get_urls_csv(qs),
            "/api/mail_config":              self._get_mail_config,
            "/api/upload/status":            lambda: self._get_upload_status(qs),
        }

        handler = routes.get(path)
        if handler:
            try:
                handler()
            except Exception as exc:
                log.error("WebHandler GET %s: %s", path, exc)
                self._json({"error": "internal server error"}, 500)
        elif path.startswith("/static/") or path.startswith("/resources/") or path == "/favicon.ico":
            self._serve_static(path)
        else:
            self._send(404, b"Not Found", "text/plain")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        ct   = self.headers.get("Content-Type", "")

        # ── Chunked upload endpoints ──────────────────────────────────────────
        if path == "/api/upload/init":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw)
            except Exception:
                self._json({"ok": False, "msg": "Invalid JSON"}, 400); return
            from hc.web_upload import handle_upload_init
            # Pass self so handler can extract real client IP and log it.
            resp, code = handle_upload_init(data, handler=self)
            self._json(resp, code)
            return

        if path == "/api/upload/chunk":
            try:
                cl = int(self.headers.get("Content-Length", 0))
                if cl > UPLOAD_MAX_BYTES:
                    self._json({"ok": False, "msg": "Chunk too large"}, 413); return
                raw_body = self.rfile.read(cl)
            except Exception as exc:
                self._json({"ok": False, "msg": f"Read error: {exc}"}, 500); return
            from hc.web_upload import handle_upload_chunk
            resp, code = handle_upload_chunk(raw_body, ct, handler=self)
            self._json(resp, code)
            return

        if path == "/api/upload/finalize":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw)
            except Exception:
                self._json({"ok": False, "msg": "Invalid JSON"}, 400); return
            from hc.web_upload import handle_upload_finalize
            resp, code = handle_upload_finalize(data, handler=self)
            self._json(resp, code)
            return

        if path == "/api/upload/abort":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw)
            except Exception:
                self._json({"ok": False, "msg": "Invalid JSON"}, 400); return
            sid = str(data.get("session_id", "")).strip()
            if sid:
                from hc.web_upload import handle_upload_abort
                resp, code = handle_upload_abort(sid, handler=self)
                self._json(resp, code)
            else:
                self._json({"ok": True})
            return

        # ── Legacy single-shot upload (multipart/form-data catch-all) ────────
        if "multipart/form-data" in ct:
            try:
                self._handle_upload()
            except Exception as exc:
                log.error("Upload error: %s", exc)
                self._json({"ok": False, "msg": f"Upload error: {exc}"}, 500)
            return

        length = int(self.headers.get("Content-Length", 0))
        if length > 4 * 1024 * 1024:
            self._json({"ok": False, "msg": "Request body too large"}, 413)
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data: Dict[str, Any] = json.loads(raw)
        except Exception:
            self._json({"ok": False, "msg": "Invalid JSON"}, 400)
            return

        # The calendar React component posts to /api/action with the real
        # action name inside the JSON body ({"action": "delete_event", ...}).
        # All other callers post to /api/<action_name> directly.
        if path == "/api/action":
            action = str(data.pop("action", "")).strip()
        else:
            action = path.replace("/api/", "").strip("/")
        try:
            self._dispatch(action, data)
        except Exception as exc:
            log.error("WebHandler POST %s: %s", path, exc)
            self._json({"ok": False, "msg": f"Internal error: {exc}"}, 500)

    # ── GET handlers ────────────────────────────────────────────────────────
    def _get_health(self) -> None:
        mgr = _WEB_MANAGER
        if mgr is None:
            self._json({"status": "starting", "ready": False}, 503)
            return
        self._json({
            "status":    "ok",
            "ready":     True,
            "timestamp": datetime.now().isoformat(),
            "streams":   [{"name": s.config.name, "status": s.status.label} for s in mgr.states],
        })

    def _get_streams(self) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json([])
            return
        result = []
        for st in mgr.states:
            cfg = st.config
            result.append({
                "name":           cfg.name,
                "port":           cfg.port,
                "weekdays":       cfg.weekdays_display(),
                "status":         st.status.label,
                "progress":       st.progress,
                "position":       st.format_pos(),
                "current_secs":   st.current_pos,
                "duration":       st.duration,
                "time_remaining": st.time_remaining(),
                "fps":            st.fps,
                "rtsp_url":       cfg.rtsp_url_external,
                "hls_url":        cfg.hls_url if cfg.hls_enabled else "",
                "shuffle":        cfg.shuffle,
                "playlist_count": len(cfg.playlist),
                "enabled":        cfg.enabled,
                "error_msg":      st.error_msg,
                "loop_count":     st.loop_count,
                "restart_count":  st.restart_count,
                "bitrate":        st.bitrate,
                "video_bitrate":  cfg.video_bitrate,
                "audio_bitrate":  cfg.audio_bitrate,
                "speed":          st.speed,
                "app_ver":        APP_VER,
                # Whether a one-shot event is actively playing right now
                "oneshot_active": bool(getattr(st, "oneshot_active", False)),
                # current_file() returns the full Path of what FFmpeg is playing.
                # We expose only the filename (.name). Works for both playlist and oneshot.
                # When a one-shot event is active the playlist index still points to the
                # compliance/playlist file — suppress current_file so the UI always
                # shows active_event (the actual oneshot filename) instead.
                "current_file":   (
                    None
                    if bool(getattr(st, "oneshot_active", False))
                    else (
                        Path(cf).name
                        if (cf := (
                            st.current_file()
                            if callable(getattr(st, "current_file", None))
                            else getattr(st, "current_file", None)
                        )) else None
                    )
                ),
                # active_event: the filename to display when current_file is unavailable.
                #
                # Three cases:
                #  A) oneshot IS active, current_file is populated → active_event=None
                #     (current_file already shows what's playing, no need to duplicate)
                #  B) oneshot IS active, current_file is None → worker doesn't expose
                #     the oneshot path via current_file(); use active_event as the
                #     fallback so the UI always has a name to show.
                #     Look for the in-flight event (unplayed first, then most recently
                #     played, depending on when the worker sets ev.played).
                #  C) no oneshot active → show next pending event, or last-played name
                #     if current_file is also None (brief resume transition).
                "active_event":   _active_event_name(st, cfg, mgr),
                # active_event during oneshot = active_oneshot_event.file_path.name
                # (set directly by play_oneshot(); never derived from current_file
                #  which always points to the playlist/compliance file, not the event).
                "next_in_queue":  _get_next_in_queue(st, cfg, n=2),
                # Compliance alert (v2)
                "compliance_enabled":       cfg.compliance_enabled,
                "compliance_alert":         getattr(st, "compliance_alert", None),
                "compliance_alert_enabled": getattr(cfg, "compliance_alert_enabled", True),
                # True while _start_ffmpeg_with_retry is absorbing transient broken-pipe
                # / 400 Bad Request failures.  Web UI renders a BUFFERING badge instead
                # of STARTING during the retry window (v5.3.7).
                "buffering":      getattr(st, "buffering", False),
            })
        self._json(result)

    def _get_streams_config(self) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json([])
            return
        result = []
        for st in mgr.states:
            cfg = st.config
            result.append({
                "name":          cfg.name,
                "port":          cfg.port,
                "files":         ";".join(
                    f"{i.file_path}@{i.start_position}#{i.priority}"
                    for i in cfg.playlist),
                "weekdays":      cfg.weekdays_display(),
                "enabled":       cfg.enabled,
                "shuffle":       cfg.shuffle,
                "stream_path":   cfg.stream_path,
                "video_bitrate": cfg.video_bitrate,
                "audio_bitrate": cfg.audio_bitrate,
                "hls_enabled":          cfg.hls_enabled,
                # Compliance fields (v5.0.6+)
                "compliance_enabled":       cfg.compliance_enabled,
                "compliance_start":         cfg.compliance_start,
                "compliance_loop":          cfg.compliance_loop,
                "compliance_alert_enabled": getattr(cfg, "compliance_alert_enabled", True),
            })
        self._json(result)

    def _get_urls_csv(self, qs: Dict[str, Any]) -> None:
        """
        Download a CSV of all stream URLs.

        Query params:
          include_files=1   also emit a 'filenames' column with each stream's
                            playlist file names (pipe-separated).

        Columns always present:
          name, ip, port, stream_path, rtsp_url, hls_url, status, enabled

        Optional column (include_files=1):
          filenames   — pipe-separated list of playlist file basenames

        FIX: All row-building and CSV serialisation now happens BEFORE
        send_response() is called.  This prevents the double-header
        corruption that caused "Failed - Network error" in the browser
        download manager: if anything throws while building the payload
        the do_GET exception handler can still send a clean JSON 500.
        """
        import io, csv as _csv
        from hc.utils import _local_ip

        include_files = qs.get("include_files", ["0"])[0] == "1"
        lan_ip        = _local_ip()
        mgr           = _WEB_MANAGER

        fieldnames = ["name", "ip", "port", "stream_path",
                      "rtsp_url", "hls_url", "status", "enabled"]
        if include_files:
            fieldnames.append("filenames")

        rows = []
        if mgr:
            for st in mgr.states:
                cfg = st.config
                row: Dict[str, Any] = {
                    "name":        cfg.name,
                    "ip":          lan_ip,
                    "port":        cfg.port,
                    "stream_path": cfg.stream_path or "",
                    "rtsp_url":    cfg.rtsp_url_external,
                    "hls_url":     cfg.hls_url if cfg.hls_enabled else "",
                    "status":      st.status.label,
                    "enabled":     "yes" if cfg.enabled else "no",
                }
                if include_files:
                    row["filenames"] = "|".join(
                        item.file_path.name for item in cfg.playlist
                    )
                rows.append(row)

        # ── Serialise to CSV bytes BEFORE touching the socket ────────────
        # Any exception raised here will be caught by do_GET's try/except
        # and a clean JSON 500 will be returned — no partial/corrupt HTTP
        # response is possible because send_response() hasn't been called yet.
        buf = io.StringIO()
        writer = _csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        body = buf.getvalue().encode("utf-8")

        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"hydracast_urls_{ts}.csv"

        # ── Send response — nothing below this point may raise ───────────
        self.send_response(200)
        self.send_header("Content-Type",        "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Content-Length",      str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in _SEC_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        log.info("URL CSV downloaded: %s (%d stream(s), files=%s)",
                 fname, len(rows), include_files)

    def _get_library(self) -> None:
        self._json(_get_library_cached())

    def _get_subdirs(self) -> None:
        from hc.web_filemanager import _encode_path
        dirs: List[Dict] = []
        roots = get_media_roots()
        for root_idx, root in enumerate(roots):
            if not root.is_dir():
                continue
            for d in sorted(root.rglob("*")):
                if d.is_dir():
                    try:
                        rel = str(d.relative_to(root))
                        if rel:
                            encoded = _encode_path(root_idx, rel)
                            label = rel if root_idx == 0 else f"[{root.name}] {rel}"
                            dirs.append({"path": encoded, "label": label})
                    except ValueError:
                        pass
        self._json({
            "dirs":       dirs,
            "root_label": str(MEDIA_DIR()),
            "roots":      [str(r) for r in roots],
        })

    def _get_media_roots(self) -> None:
        """Return the list of configured media root directories."""
        roots = get_media_roots()
        self._json({
            "roots":   [str(r) for r in roots],
            "default": str(MEDIA_DIR()),
        })

    def _get_events(self) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json([])
            return
        now = datetime.now()
        result = []
        for ev in sorted(mgr.events, key=lambda e: e.play_at):
            diff = (ev.play_at - now).total_seconds()
            entry: Dict[str, Any] = {
                "event_id":      ev.event_id,
                "stream_name":   ev.stream_name,
                "file_name":     ev.file_path.name,
                "file_path":     str(ev.file_path),
                "play_at":       ev.play_at.strftime("%Y-%m-%d %H:%M:%S"),
                "play_at_iso":   ev.play_at.isoformat(),
                "seconds_until": round(diff),
                "post_action":   getattr(ev, "post_action",  "resume") or "resume",
                "start_pos":     getattr(ev, "start_pos",    "00:00:00") or "00:00:00",
                "end_pos":       getattr(ev, "end_pos",      ""),
                "loop_count":    getattr(ev, "loop_count",   0),
                "comment":       getattr(ev, "comment",      "") or "",
                "played":        ev.played,
            }
            be = getattr(ev, "broadcast_end", None)
            if be is not None:
                entry["broadcast_end"] = be.isoformat()
            result.append(entry)
        self._json(result)

    # _get_holidays is intentionally NOT defined here.
    # The implementation in _CalendarHandlersMixin (web_handlers_calendar.py)
    # is the authoritative one: it merges library holidays with custom holidays
    # from disk and uses a disk cache for offline/restart resilience.
    # Defining it here again would shadow that version and break custom holidays.

    def _get_settings(self) -> None:
        """Return persisted app settings as a flat dict (backwards-compatible)."""
        from hc.web_settings_manager import load_settings
        try:
            self._json(load_settings())
        except Exception as exc:
            log.error("_get_settings: %s", exc)
            self._json({"error": str(exc)}, 500)

    def _get_settings_schema(self) -> None:
        """
        GET /api/settings/schema

        Return settings structured for the UI:
          {
            "groups":  ["appearance", "regional", "notifications", "system"],
            "schema":  { <key>: { group, type, label, description, default, options? } },
            "values":  { <key>: <current_value> }
          }
        The UI iterates ``groups`` for tabs, uses ``schema`` to auto-build
        form controls, and populates them from ``values``.
        """
        from hc.web_settings_manager import load_settings_grouped
        try:
            self._json(load_settings_grouped())
        except Exception as exc:
            log.error("_get_settings_schema: %s", exc)
            self._json({"error": str(exc)}, 500)

    def _get_logs(self, qs: Dict[str, Any]) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json({"entries": []})
            return
        level  = qs.get("level",  ["ALL"])[0].upper()
        stream = qs.get("stream", [""])[0].strip()
        try:
            n = min(1000, int(qs.get("n", ["500"])[0]))
        except ValueError:
            n = 500
        if level not in ("ALL", "INFO", "WARN", "ERROR"):
            level = "ALL"
        entries = mgr._glog.filtered(
            level=None if level == "ALL" else level,
            stream=stream or None, n=n,
        )
        self._json({"entries": entries})

    def _get_system_stats(self) -> None:
        try:
            cpu  = psutil.cpu_percent(interval=0.1)
            mem  = psutil.virtual_memory()
            disk = psutil.disk_usage(str(BASE_DIR()))

            # ── Guardian status (non-blocking — 0.5 s timeout) ────────────────
            from hc.watchdog import fetch_guardian_status
            guardian = fetch_guardian_status(timeout=0.5) or {
                "guardian_version": None,
                "target_pid":       None,
                "restart_count":    0,
                "heartbeat_ok":     False,
                "heartbeat_age_s":  None,
                "last_crash_reason":"guardian not running",
                "crash_log_tail":   [],
                "file_warnings":    {},
                "stopping":         False,
            }

            self._json({
                "cpu":          round(cpu, 1),
                "mem_percent":  round(mem.percent, 1),
                "mem_used":     _fmt_size(mem.used),
                "mem_total":    _fmt_size(mem.total),
                "disk_percent": round(disk.percent, 1),
                "disk_used":    _fmt_size(disk.used),
                "disk_total":   _fmt_size(disk.total),
                "web_port":     get_web_port(),
                "lan_ip":       _local_ip(),
                # Guardian card — rendered by the Web UI
                "guardian":     guardian,
            })
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _get_stream_detail(self, qs: Dict[str, Any]) -> None:
        name = qs.get("name", [""])[0].strip()
        mgr  = _WEB_MANAGER
        if not mgr or not name:
            self._json({"error": "bad request"}, 400)
            return
        st = mgr.get_state(name)
        if not st:
            self._json({"error": "not found"}, 404)
            return
        cfg = st.config
        with st._lock:
            log_snap = list(st.log[-80:])
        cur_real = st.playlist_order[st.playlist_index] if st.playlist_order else 0
        # Build a mapping: real playlist index → 1-based play sequence number.
        # playlist_order is a list whose positions are sequence slots (0, 1, 2…)
        # and whose values are real cfg.playlist indices.
        # Inverting it gives: real_index → sequence_position (1-based for the UI).
        order = st.playlist_order if st.playlist_order else list(range(len(cfg.playlist)))
        order_pos = {real_idx: seq + 1 for seq, real_idx in enumerate(order)}
        playlist = []
        for i, item in enumerate(cfg.playlist):
            playlist.append({
                "file":     item.file_path.name,
                "path":     str(item.file_path),
                "start":    item.start_position,
                "priority": item.priority,
                "sequence": order_pos.get(i, i + 1),  # 1-based play position
                "exists":   item.file_path.exists(),
                "current":  (i == cur_real),
            })
        self._json({
            "name":          cfg.name,
            "port":          cfg.port,
            "rtsp_url":      cfg.rtsp_url_external,
            "hls_url":       cfg.hls_url if cfg.hls_enabled else "",
            "weekdays":      cfg.weekdays_display(),
            "status":        st.status.label,
            "progress":      st.progress,
            "current_pos":   st.current_pos,
            "duration":      st.duration,
            "position":      st.format_pos(),
            "fps":           st.fps,
            "loop_count":    st.loop_count,
            "restart_count": st.restart_count,
            "error_msg":     st.error_msg,
            "playlist":      playlist,
            "log":           log_snap,
            "started_at":    st.started_at.isoformat() if st.started_at else None,
        })

    def _get_stream_view(self, qs: Dict[str, Any]) -> None:
        name = qs.get("name", [""])[0].strip()
        mgr  = _WEB_MANAGER
        if not mgr or not name:
            self._json({"error": "bad request"}, 400)
            return
        st = mgr.get_state(name)
        if not st:
            self._json({"error": "not found"}, 404)
            return
        cfg = st.config
        oneshot_active = bool(getattr(st, "oneshot_active", False))
        _cf_raw = (
            None  # suppress playlist path during oneshot
            if oneshot_active
            else (
                st.current_file()
                if callable(getattr(st, "current_file", None))
                else getattr(st, "current_file", None)
            )
        )
        self._json({
            "name":           cfg.name,
            "status":         st.status.label,
            "rtsp_url":       cfg.rtsp_url_external,
            "hls_url":        cfg.hls_url if cfg.hls_enabled else "",
            "current_pos":    st.current_pos,
            "duration":       st.duration,
            "progress":       st.progress,
            "oneshot_active": oneshot_active,
            "current_file":   Path(_cf_raw).name if _cf_raw else None,
            # Uses the same helper as _get_streams so both endpoints are consistent.
            "active_event":   _active_event_name(st, cfg, mgr),
        })

    def _get_mail_config(self) -> None:
        """Return the current mail_config.hcf contents (client_secret redacted)."""
        from hc.constants import CONFIG_DIR
        import json as _json
        path = CONFIG_DIR() / "mail_config.hcf"
        _DEFAULTS = {
            "enabled": False,
            "tenant_id": "", "client_id": "", "client_secret": "",
            "from_addr": "", "to_addrs": [],
            "on_error": True, "on_stop": True, "cooldown_secs": 300,
        }
        try:
            if path.exists():
                cfg = _json.loads(path.read_text(encoding="utf-8"))
                # Redact the secret so it never crosses the wire in plain text.
                if cfg.get("client_secret"):
                    cfg["client_secret"] = "••••••••"
                self._json(cfg)
            else:
                self._json(_DEFAULTS)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _get_check_port(self, qs: Dict[str, Any]) -> None:
        """
        GET /api/check_port?port=30121

        Check whether a proposed RTSP base port is safe to use.

        Validates:
          1. Port is in range 1024–65534.
          2. Port is ODD  (HydraCast convention: RTSP=odd, HLS=port+1=even).
          3. All four derived ports are free from any existing process:
               RTSP = port   HLS = port+1   RTP = port+2* (bumped even)
               RTCP = RTP+1
          4. Firewall rules do not appear to block the RTSP port
             (Windows: netsh advfirewall; Linux: iptables / ufw).

        Returns JSON:
          {
            "ok": true/false,      // overall safe to use
            "port": 30121,
            "hls_port": 30122,
            "rtp_port": 30124,
            "rtcp_port": 30125,
            "odd_ok": true,        // port is odd
            "ports": {             // per-port status
              "30121": {"free": true,  "process": null},
              "30122": {"free": false, "process": "nginx (pid 1234)"},
              ...
            },
            "firewall": {
              "checked": true,
              "blocked": false,
              "detail": "No blocking rule found"
            },
            "warnings": ["…"],     // non-fatal advisories
            "errors":   ["…"]      // fatal blockers (ok=false)
          }
        """
        import socket as _socket
        import subprocess as _sp
        import sys as _sys

        try:
            raw = qs.get("port", [""])[0].strip()
            if not raw:
                self._json({"ok": False, "errors": ["Port parameter is required"]})
                return
            port = int(raw)
        except (ValueError, TypeError):
            self._json({"ok": False, "errors": ["Port must be an integer"]})
            return

        errors: list   = []
        warnings: list = []

        # ── 1. Range check ────────────────────────────────────────────────────
        if not (1024 <= port <= 65534):
            self._json({"ok": False,
                        "errors": [f"Port {port} is out of range (1024–65534)"]})
            return

        # ── 2. Odd check ──────────────────────────────────────────────────────
        odd_ok = (port % 2 != 0)
        if not odd_ok:
            errors.append(
                f"Port {port} is even. HydraCast requires an ODD RTSP base port "
                f"(HLS will use the adjacent even port {port + 1})."
            )

        # Derive companion ports
        hls_port  = port + 1
        rtp_base  = port + 2
        if rtp_base % 2 != 0:
            rtp_base += 1
        rtcp_port = rtp_base + 1

        all_ports = {
            port:      "RTSP",
            hls_port:  "HLS",
            rtp_base:  "RTP",
            rtcp_port: "RTCP",
        }

        # ── 3. Process occupancy check ────────────────────────────────────────
        def _process_on_port(p: int):
            """Return 'name (pid NNN)' if any process holds TCP or UDP port p."""
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if conn.laddr and conn.laddr.port == p:
                        pid = conn.pid
                        if pid:
                            try:
                                proc = psutil.Process(pid)
                                return f"{proc.name()} (pid {pid})"
                            except psutil.NoSuchProcess:
                                return f"pid {pid} (exited)"
                        return "unknown process"
            except Exception:
                pass
            return None

        port_status: Dict[str, Any] = {}
        for p, label in all_ports.items():
            occupant = _process_on_port(p)
            free     = (occupant is None)
            port_status[str(p)] = {
                "label":   label,
                "free":    free,
                "process": occupant,
            }
            if not free:
                errors.append(
                    f"{label} port {p} is already in use by {occupant}."
                )

        # ── 4. Firewall probe ─────────────────────────────────────────────────
        firewall: Dict[str, Any] = {"checked": False, "blocked": False, "detail": ""}

        try:
            is_win   = _sys.platform.startswith("win")
            is_linux = _sys.platform.startswith("linux")

            if is_win:
                # netsh advfirewall: list inbound rules that mention this port
                r = _sp.run(
                    ["netsh", "advfirewall", "firewall", "show", "rule",
                     "name=all", "dir=in", "verbose"],
                    capture_output=True, text=True, timeout=8,
                )
                out = r.stdout.lower()
                port_str = str(port)
                # Simple heuristic: look for a "block" rule that mentions our port
                blocked = False
                for line in out.splitlines():
                    if port_str in line and "block" in line:
                        blocked = True
                        break
                firewall = {
                    "checked": True,
                    "blocked": blocked,
                    "detail":  (
                        f"Windows Firewall: blocking inbound rule found for port {port}."
                        if blocked else
                        "Windows Firewall: no explicit blocking rule found for this port."
                    ),
                }
                if blocked:
                    warnings.append(
                        f"Windows Firewall may block inbound traffic on port {port}. "
                        "Add an Allow rule or disable the block rule."
                    )

            elif is_linux:
                # Try ufw first, then iptables
                ufw_ok = False
                try:
                    r2 = _sp.run(
                        ["ufw", "status", "verbose"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if r2.returncode == 0:
                        out2 = r2.stdout.lower()
                        ufw_ok = True
                        # If ufw is active and port is not listed as ALLOW
                        if "status: active" in out2:
                            allowed = str(port) in out2 and "allow" in out2
                            # Coarse check: if port not mentioned at all, may be blocked
                            port_mentioned = str(port) in out2
                            if not port_mentioned:
                                warnings.append(
                                    f"ufw is active but port {port} has no explicit ALLOW rule. "
                                    "Add with: sudo ufw allow {port}/tcp".format(port=port)
                                )
                            firewall = {
                                "checked": True,
                                "blocked": False,
                                "detail":  (
                                    f"ufw is active; port {port} appears allowed."
                                    if port_mentioned else
                                    f"ufw is active; no ALLOW rule found for port {port}."
                                ),
                            }
                except FileNotFoundError:
                    pass

                if not ufw_ok:
                    # Fall back to iptables -L
                    try:
                        r3 = _sp.run(
                            ["iptables", "-L", "INPUT", "-n", "--line-numbers"],
                            capture_output=True, text=True, timeout=5,
                        )
                        out3 = r3.stdout.lower()
                        drop_or_reject = (
                            f"dpt:{port}" in out3
                            and ("drop" in out3 or "reject" in out3)
                        )
                        firewall = {
                            "checked": True,
                            "blocked": drop_or_reject,
                            "detail":  (
                                f"iptables: DROP/REJECT rule found for port {port}."
                                if drop_or_reject else
                                f"iptables: no DROP/REJECT rule found for port {port}."
                            ),
                        }
                        if drop_or_reject:
                            warnings.append(
                                f"iptables has a DROP/REJECT rule for port {port}. "
                                "Run: sudo iptables -I INPUT -p tcp --dport {p} -j ACCEPT"
                                .format(p=port)
                            )
                    except Exception:
                        firewall = {
                            "checked": False,
                            "blocked": False,
                            "detail":  "iptables check failed (permission denied or not installed).",
                        }
            else:
                firewall = {
                    "checked": False,
                    "blocked": False,
                    "detail":  "Firewall check not supported on this OS.",
                }
        except Exception as exc:
            firewall = {
                "checked": False,
                "blocked": False,
                "detail":  f"Firewall check error: {exc}",
            }

        if firewall.get("blocked"):
            errors.append(firewall["detail"])

        ok = len(errors) == 0
        self._json({
            "ok":        ok,
            "port":      port,
            "hls_port":  hls_port,
            "rtp_port":  rtp_base,
            "rtcp_port": rtcp_port,
            "odd_ok":    odd_ok,
            "ports":     port_status,
            "firewall":  firewall,
            "warnings":  warnings,
            "errors":    errors,
        })

    def _get_suggest_port(self, qs: Dict[str, Any]) -> None:
        """
        GET /api/suggest_port?from=30121

        Scan odd ports starting from ``from`` (inclusive, must be odd;
        bumped +1 if even) and return the first port where all four
        derived ports (RTSP, HLS, RTP, RTCP) are completely free.

        Returns JSON:
          {
            "port": 30121,         // suggested free odd port (or null if none found)
            "searched": 50         // how many candidates were checked
          }
        """
        import socket as _socket

        try:
            raw  = qs.get("from", ["30121"])[0].strip()
            base = int(raw) if raw else 30121
        except (ValueError, TypeError):
            base = 30121

        # Clamp and make odd
        base = max(1025, min(base, 65520))
        if base % 2 == 0:
            base += 1

        def _port_free(p: int) -> bool:
            """True if no process is bound to TCP or UDP port p."""
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if conn.laddr and conn.laddr.port == p:
                        return False
            except Exception:
                pass
            # Double-check with a quick socket bind attempt
            for kind in (_socket.SOCK_STREAM, _socket.SOCK_DGRAM):
                try:
                    s = _socket.socket(_socket.AF_INET, kind)
                    s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
                    s.bind(("", p))
                    s.close()
                except OSError:
                    return False
            return True

        def _all_free(rtsp: int) -> bool:
            hls  = rtsp + 1
            rtp  = rtsp + 2
            if rtp % 2 != 0:
                rtp += 1
            rtcp = rtp + 1
            return all(_port_free(p) for p in (rtsp, hls, rtp, rtcp))

        searched = 0
        candidate = base
        found: Optional[int] = None
        while candidate <= 65520 and searched < 200:
            searched += 1
            if _all_free(candidate):
                found = candidate
                break
            candidate += 2   # always stay odd

        self._json({"port": found, "searched": searched})

    def _get_upload_status(self, qs: Dict[str, Any]) -> None:
        """GET /api/upload/status?session_id=X  — chunked upload progress + resume info."""
        from hc.web_upload import handle_upload_status
        session_id = qs.get("session_id", [""])[0].strip()
        resp, code = handle_upload_status(session_id)
        self._json(resp, code)

    # ── POST dispatch ────────────────────────────────────────────────────────
    def _dispatch(self, action: str, data: Dict[str, Any]) -> None:
        # File-manager actions are handled by _FileManagerMixin
        _FILE_OPS = {"file_mkdir", "file_rename", "file_delete", "file_delete_dir", "file_move", "file_copy"}
        if action in _FILE_OPS:
            self._handle_file_op(action, data)
            return

        mgr = _WEB_MANAGER
        if not mgr:
            self._json({"ok": False, "msg": "Manager not ready"})
            return

        if action == "start":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                mgr.start(st.config.name)
                self._json({"ok": True, "msg": f"Starting {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "stop":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                mgr.stop(st.config.name)
                self._json({"ok": True, "msg": f"Stopping {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "restart":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                mgr.restart(st.config.name)
                self._json({"ok": True, "msg": f"Restarting {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "start_all":
            mgr.start_all()
            self._json({"ok": True, "msg": "Starting all streams"})

        elif action == "stop_all":
            for _st in mgr.states:
                try:
                    mgr.stop(_st.config.name)
                except Exception:
                    pass
            self._json({"ok": True, "msg": "Stopped all streams"})

        elif action == "restart_all":
            for st in mgr.states:
                try:
                    mgr.restart(st.config.name)
                except Exception:
                    pass
            self._json({"ok": True, "msg": "Restarting all streams"})

        elif action == "restart_process":
            import os as _os, threading as _thr
            if mgr is not None:
                for st in mgr.states:
                    try:
                        mgr.stop(st.config.name)
                    except Exception:
                        pass
            self._json({"ok": True, "msg": "Restarting process…"})
            def _do_exec():
                import time as _t
                _t.sleep(0.8)
                log.info("restart_process: calling os._exit(1) — Guardian will relaunch.")
                _os._exit(1)
            _thr.Thread(target=_do_exec, daemon=False,
                        name="hc-restart-process").start()

        elif action == "skip_next":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                _w = mgr.get_worker(st.config.name)
                if _w: _w.skip_to_next()
                self._json({"ok": True, "msg": f"Skipping in {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "seek":
            st = mgr.get_state(str(data.get("name", "")))
            try:
                secs = float(data.get("seconds", 0))
                if secs < 0:
                    raise ValueError("negative")
            except (TypeError, ValueError):
                self._json({"ok": False, "msg": "Invalid seek position"})
                return
            if st:
                _w = mgr.get_worker(st.config.name)
                if _w: _w.seek(secs)
                self._json({"ok": True, "msg": f"Seeking to {_fmt_duration(secs)}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "update_config":
            # Update a single stream's mutable config fields
            try:
                name_s = str(data.get("name", "")).strip()
                if not name_s:
                    self._json({"ok": False, "msg": "Missing stream name"})
                    return
                st = mgr.get_state(name_s)
                if not st:
                    self._json({"ok": False, "msg": "Stream not found"})
                    return
                cfg = st.config
                # Port
                new_port = int(data.get("port", cfg.port))
                if not (1024 <= new_port <= 65534):
                    raise ValueError(f"Port {new_port} out of range (1024–65534)")
                if new_port % 2 == 0:
                    raise ValueError(
                        f"Port {new_port} is even. HydraCast requires an ODD RTSP port "
                        f"(HLS will use port {new_port + 1})."
                    )
                cfg.port = new_port
                # Stream path
                sp = str(data.get("stream_path", cfg.stream_path)).strip()
                if sp:
                    cfg.stream_path = sp
                # Bitrates
                vbr = str(data.get("video_bitrate", "")).strip()
                if vbr:
                    cfg.video_bitrate = CSVManager._sanitize_bitrate(vbr, cfg.video_bitrate)
                abr = str(data.get("audio_bitrate", "")).strip()
                if abr:
                    cfg.audio_bitrate = CSVManager._sanitize_bitrate(abr, cfg.audio_bitrate)
                # Booleans
                cfg.shuffle     = bool(data.get("shuffle",     cfg.shuffle))
                cfg.enabled     = bool(data.get("enabled",     cfg.enabled))
                cfg.hls_enabled = bool(data.get("hls_enabled", cfg.hls_enabled))
                # Compliance fields
                if "compliance_enabled" in data:
                    cfg.compliance_enabled = bool(data["compliance_enabled"])
                if "compliance_start" in data:
                    raw_cs = str(data["compliance_start"]).strip()
                    cfg.compliance_start = CSVManager._sanitize_hms(raw_cs)
                if "compliance_loop" in data:
                    cfg.compliance_loop = bool(data["compliance_loop"])
                # Weekdays
                if "weekdays" in data:
                    cfg.weekdays = CSVManager.parse_weekdays(str(data["weekdays"]))
                # Playlist source: folder_source takes priority over file list
                folder_source_raw = str(data.get("folder_source") or "").strip()
                raw_files = str(data.get("files", "")).strip()
                if folder_source_raw:
                    from hc.folder_scanner import scan_folder, SortMode
                    folder_source = _decode_fm_path_to_absolute(folder_source_raw)
                    if folder_source is None or not folder_source.is_dir():
                        raise ValueError(f"Folder not found or access denied: '{folder_source_raw}'")
                    playlist, warnings = scan_folder(folder_source, SortMode.ALPHA_FWD)
                    for w in warnings:
                        log.warning("update_config folder scan: %s", w)
                    if not playlist:
                        raise ValueError(f"No supported media files found in '{folder_source_raw}'")
                    cfg.playlist      = playlist
                    cfg.folder_source = folder_source
                elif raw_files:
                    raw_files = raw_files.replace("\n", ";")
                    # Decode any @N/rel encoded paths to real absolute paths
                    decoded_parts = []
                    for tok in raw_files.split(";"):
                        tok = tok.strip()
                        if not tok:
                            continue
                        # Preserve @start and #priority suffixes
                        import re as _re2
                        m_pri   = _re2.search(r'#(\d+)$', tok)
                        m_start = _re2.search(r'@(\d{1,2}:\d{2}:\d{2})$', tok.split('#')[0])
                        pri_sfx   = f"#{m_pri.group(1)}"   if m_pri   else ""
                        start_sfx = f"@{m_start.group(1)}" if m_start else ""
                        path_part = _re2.sub(r'@\d{1,2}:\d{2}:\d{2}$', '', _re2.sub(r'#\d+$', '', tok)).strip()
                        abs_p = _decode_fm_path_to_absolute(path_part)
                        if abs_p is not None:
                            decoded_parts.append(f"{abs_p}{start_sfx}{pri_sfx}")
                        else:
                            decoded_parts.append(tok)  # pass through; parse_files will reject
                    parsed = CSVManager.parse_files(";".join(decoded_parts))
                    if parsed:
                        cfg.playlist      = parsed
                        cfg.folder_source = None
                # Persist
                all_cfgs = [s.config for s in mgr.states]
                CSVManager.save(all_cfgs)
                self._json({"ok": True, "msg": f"Config updated for {name_s}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "save_config":
            try:
                streams_data = data.get("streams", [])
                if not isinstance(streams_data, list):
                    raise ValueError("streams must be a list")
                configs: List[StreamConfig] = []
                for row in streams_data:
                    name_s = str(row.get("name", "")).strip()
                    if not name_s or len(name_s) > 64:
                        raise ValueError(f"Invalid stream name: '{name_s}'")
                    port = int(row.get("port", 0))
                    if not (1024 <= port <= 65535):
                        raise ValueError(f"Port {port} out of range")
                    raw_files = str(row.get("files", "")).replace("\n", ";")
                    playlist  = CSVManager.parse_files(raw_files)
                    configs.append(StreamConfig(
                        name=name_s, port=port, playlist=playlist,
                        weekdays=CSVManager.parse_weekdays(str(row.get("weekdays", "all"))),
                        enabled=bool(row.get("enabled", True)),
                        shuffle=bool(row.get("shuffle", False)),
                        stream_path=str(row.get("stream_path", "stream")).strip() or "stream",
                        video_bitrate=CSVManager._sanitize_bitrate(str(row.get("video_bitrate", "2500k")), "2500k"),
                        audio_bitrate=CSVManager._sanitize_bitrate(str(row.get("audio_bitrate", "128k")), "128k"),
                        hls_enabled=bool(row.get("hls_enabled", False)),
                        compliance_enabled=bool(row.get("compliance_enabled", False)),
                        compliance_start=CSVManager._sanitize_hms(str(row.get("compliance_start", "06:00:00"))),
                        compliance_loop=bool(row.get("compliance_loop", False)),
                    ))
                ports = [c.port for c in configs]
                if len(set(ports)) != len(ports):
                    raise ValueError("Duplicate port numbers")
                CSVManager.save(configs)
                self._json({"ok": True, "msg": "Config saved. Restart HydraCast to apply."})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "add_event":
            try:
                stream_name = str(data.get("stream_name", "")).strip()
                file_path   = str(data.get("file_path",   "")).strip()
                play_at     = str(data.get("play_at",     "")).strip()
                start_pos   = str(data.get("start_pos",   "00:00:00")).strip()
                end_pos     = str(data.get("end_pos",     "")).strip()
                post_action = str(data.get("post_action", "resume")).strip()
                notes       = str(data.get("notes", "")).strip()[:200]
                if post_action not in ("resume", "stop", "black"):
                    post_action = "resume"
                if not re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", start_pos):
                    start_pos = "00:00:00"
                # end_pos is optional; validate if provided
                if end_pos and not re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", end_pos):
                    end_pos = ""
                if not stream_name:
                    raise ValueError("Stream name is required")
                if mgr.get_state(stream_name) is None:
                    raise ValueError(f"Stream '{stream_name}' not found")
                dt = None
                for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt = datetime.strptime(play_at, fmt); break
                    except ValueError:
                        continue
                if dt is None:
                    raise ValueError("Invalid datetime format")
                fp = _decode_fm_path_to_absolute(file_path)
                if fp is None:
                    fp_bare = Path(file_path)
                    if fp_bare.is_absolute() and fp_bare.exists():
                        fp = fp_bare
                    else:
                        raise ValueError("File not found or path outside any media root")
                ev_id = hashlib.md5(
                    f"{stream_name}{play_at}{file_path}".encode()
                ).hexdigest()[:8]
                # Guard: reject exact duplicate (same stream+time+file)
                if any(e.event_id == ev_id for e in mgr.events):
                    raise ValueError("An identical event is already scheduled")
                ev_kwargs = dict(
                    event_id    = ev_id,
                    stream_name = stream_name,
                    file_path   = fp,
                    play_at     = dt,
                    post_action = post_action,
                    start_pos   = start_pos,
                )
                # end_pos is stored as attribute if OneShotEvent supports it
                ev = OneShotEvent(**ev_kwargs)
                if end_pos:
                    try:
                        ev.end_pos = end_pos
                    except AttributeError:
                        pass
                mgr.add_event(ev)
                self._json({"ok": True, "msg": f"Event scheduled for {dt.strftime('%Y-%m-%d %H:%M')}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "delete_event":
            ev_id = str(data.get("event_id", "")).strip()
            if not ev_id:
                self._json({"ok": False, "msg": "Missing event_id"})
                return
            removed = mgr.remove_event(ev_id)
            self._json({"ok": removed, "msg": "Event deleted" if removed else "Event not found"})

        elif action == "update_event":
            try:
                ev_id = str(data.get("event_id", "")).strip()
                if not ev_id:
                    raise ValueError("Missing event_id")
                ev = next((e for e in mgr.events if e.event_id == ev_id), None)
                if ev is None:
                    raise ValueError(f"Event '{ev_id}' not found")
                if ev.played:
                    raise ValueError("Cannot edit an already-played event")
                if "stream_name" in data:
                    sn = str(data["stream_name"]).strip()
                    if mgr.get_state(sn) is None:
                        raise ValueError(f"Stream '{sn}' not found")
                    ev.stream_name = sn
                if "file_path" in data:
                    fp = _decode_fm_path_to_absolute(str(data["file_path"]).strip())
                    if fp is None:
                        fp_bare = Path(str(data["file_path"]).strip())
                        if fp_bare.is_absolute() and fp_bare.exists():
                            fp = fp_bare
                        else:
                            raise ValueError("File not found or path outside any media root")
                    ev.file_path = fp
                if "play_at" in data:
                    play_at_s = str(data["play_at"]).strip()
                    dt = None
                    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            dt = datetime.strptime(play_at_s, fmt); break
                        except ValueError:
                            continue
                    if dt is None:
                        raise ValueError("Invalid datetime format")
                    if dt <= datetime.now():
                        raise ValueError("Cannot reschedule an event to the past")
                    ev.play_at = dt
                if "post_action" in data:
                    ev.post_action = str(data["post_action"]).strip()
                if "start_pos" in data:
                    sp = str(data["start_pos"]).strip()
                    ev.start_pos = sp if re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", sp) else "00:00:00"
                if "loop_count" in data:
                    ev.loop_count = int(data["loop_count"])
                JSONManager._save_events(mgr.events)
                self._json({"ok": True, "msg": "Event updated"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "schedule_event":
            try:
                stream_name = str(data.get("stream_name", "")).strip()
                file_path   = str(data.get("file_path",   "")).strip()
                play_at     = str(data.get("play_at",     "")).strip()
                post_action = str(data.get("post_action", "resume")).strip()
                start_pos   = str(data.get("start_pos",   "00:00:00")).strip()
                loop_count  = int(data.get("loop_count",  0))
                if not re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", start_pos):
                    start_pos = "00:00:00"
                if not stream_name:
                    raise ValueError("Stream name is required")
                if mgr.get_state(stream_name) is None:
                    raise ValueError(f"Stream '{stream_name}' not found")
                dt = None
                for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt = datetime.strptime(play_at, fmt); break
                    except ValueError:
                        continue
                if dt is None:
                    raise ValueError("Invalid datetime format")
                if dt <= datetime.now():
                    raise ValueError("Cannot schedule an event in the past")
                fp = _decode_fm_path_to_absolute(file_path)
                if fp is None:
                    fp_bare = Path(file_path)
                    if fp_bare.is_absolute() and fp_bare.exists():
                        fp = fp_bare
                    else:
                        raise ValueError("File not found or path outside any media root")
                ev_id = hashlib.md5(
                    f"{stream_name}{play_at}{file_path}".encode()
                ).hexdigest()[:8]
                if any(e.event_id == ev_id for e in mgr.events):
                    raise ValueError("An identical event is already scheduled")
                ev = OneShotEvent(
                    event_id    = ev_id,
                    stream_name = stream_name,
                    file_path   = fp,
                    play_at     = dt,
                    post_action = post_action,
                    start_pos   = start_pos,
                    loop_count  = loop_count,
                )
                mgr.add_event(ev)
                self._json({"ok": True, "msg": f"Event scheduled for {dt.strftime('%Y-%m-%d %H:%M')}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "create_stream":
            try:
                name_s = str(data.get("name", "")).strip()
                if not name_s or len(name_s) > 64:
                    raise ValueError(f"Invalid stream name: '{name_s}'")
                if not re.fullmatch(r"[\w\-. ]+", name_s):
                    raise ValueError(
                        "Stream name may only contain letters, numbers, "
                        "spaces, hyphens, dots and underscores."
                    )
                port = int(data.get("port", 0))
                if not (1024 <= port <= 65534):
                    raise ValueError(f"Port {port} out of range (1024–65534).")
                if port % 2 == 0:
                    raise ValueError(
                        f"Port {port} is even. HydraCast requires an ODD RTSP port "
                        f"(HLS will use the adjacent even port {port + 1}). "
                        f"Try port {port + 1} or use the Check Port button."
                    )

                # Stream path — empty string means root mount (IP:Port/)
                stream_path = str(data.get("stream_path", "")).strip()

                # Playlist source: folder_source overrides file list
                folder_source_raw = str(data.get("folder_source") or "").strip()
                folder_source = None
                playlist: "List[PlaylistItem]" = []
                if folder_source_raw:
                    from hc.folder_scanner import scan_folder, SortMode
                    folder_source = _decode_fm_path_to_absolute(folder_source_raw)
                    if folder_source is None or not folder_source.is_dir():
                        raise ValueError(f"Folder not found or access denied: '{folder_source_raw}'")
                    playlist, warnings = scan_folder(folder_source, SortMode.ALPHA_FWD)
                    for w in warnings:
                        log.warning("create_stream folder scan: %s", w)
                    if not playlist:
                        raise ValueError(f"No supported media files found in '{folder_source_raw}'")
                else:
                    raw_files = str(data.get("files", "")).strip().replace("\n", ";")
                    # Decode any @N/rel encoded paths to real absolute paths
                    import re as _re3
                    decoded_parts2 = []
                    for tok in raw_files.split(";"):
                        tok = tok.strip()
                        if not tok:
                            continue
                        m_pri2   = _re3.search(r'#(\d+)$', tok)
                        m_start2 = _re3.search(r'@(\d{1,2}:\d{2}:\d{2})$', tok.split('#')[0])
                        pri_sfx2   = f"#{m_pri2.group(1)}"   if m_pri2   else ""
                        start_sfx2 = f"@{m_start2.group(1)}" if m_start2 else ""
                        path_part2 = _re3.sub(r'@\d{1,2}:\d{2}:\d{2}$', '', _re3.sub(r'#\d+$', '', tok)).strip()
                        abs_p2 = _decode_fm_path_to_absolute(path_part2)
                        if abs_p2 is not None:
                            decoded_parts2.append(f"{abs_p2}{start_sfx2}{pri_sfx2}")
                        else:
                            decoded_parts2.append(tok)
                    playlist = CSVManager.parse_files(";".join(decoded_parts2))
                    if not playlist:
                        raise ValueError("At least one valid file path is required.")

                # Compliance
                comp_start = CSVManager._sanitize_hms(
                    str(data.get("compliance_start", "06:00:00")))

                cfg = StreamConfig(
                    name=name_s,
                    port=port,
                    playlist=playlist,
                    weekdays=CSVManager.parse_weekdays(str(data.get("weekdays", "all"))),
                    enabled=bool(data.get("enabled", True)),
                    shuffle=bool(data.get("shuffle", False)),
                    stream_path=stream_path,
                    video_bitrate=CSVManager._sanitize_bitrate(
                        str(data.get("video_bitrate", "2500k")), "2500k"),
                    audio_bitrate=CSVManager._sanitize_bitrate(
                        str(data.get("audio_bitrate", "128k")), "128k"),
                    hls_enabled=bool(data.get("hls_enabled", False)),
                    folder_source=folder_source,
                    compliance_enabled=bool(data.get("compliance_enabled", False)),
                    compliance_start=comp_start,
                    compliance_loop=bool(data.get("compliance_loop", False)),
                )
                mgr.add_stream(cfg)
                path_label = f"/{stream_path}" if stream_path else "/"
                self._json({
                    "ok":  True,
                    "msg": f"Stream '{name_s}' created on port {port} (path: {path_label}). "
                           "You can start it now from the Configure tab.",
                })
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "delete_stream":
            try:
                name_s = str(data.get("name", "")).strip()
                if not name_s:
                    raise ValueError("Missing stream name.")
                mgr.remove_stream(name_s)
                self._json({"ok": True, "msg": f"Stream '{name_s}' deleted."})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "delete_played_events":
            ids = data.get("event_ids", [])
            if not isinstance(ids, list):
                self._json({"ok": False, "msg": "event_ids must be a list"})
                return
            id_set = set(str(i).strip() for i in ids)
            count = mgr.remove_events(id_set)
            self._json({"ok": True, "msg": f"Removed {count} event(s)"})

        elif action == "clear_played_events":
            # Remove ALL events that have already been played
            played_ids = {ev.event_id for ev in mgr.events if ev.played}
            if not played_ids:
                self._json({"ok": True, "msg": "No played events to clear"})
                return
            count = mgr.remove_events(played_ids)
            self._json({"ok": True, "msg": f"Cleared {count} played event(s)"})

        elif action == "fire_event_now":
            ev_id = str(data.get("event_id", "")).strip()
            if not ev_id:
                self._json({"ok": False, "msg": "Missing event_id"})
                return
            ok = mgr.fire_event_now(ev_id)
            self._json({"ok": ok, "msg": "Event fired" if ok else "Event not found or stream not running"})

        elif action == "cancel_event":
            name = str(data.get("name", "")).strip()
            st = mgr.get_state(name)
            if not st:
                self._json({"ok": False, "msg": f"Stream '{name}' not found"})
                return
            if not st.oneshot_active:
                self._json({"ok": False, "msg": "No event is currently running on this stream"})
                return
            w = mgr.get_worker(name)
            if not w:
                self._json({"ok": False, "msg": "Worker not found"})
                return
            threading.Thread(
                target=w.cancel_oneshot, daemon=True,
                name=f"cancel-event-{st.config.port}",
            ).start()
            self._json({"ok": True, "msg": f"Event cancelled — resuming on '{name}'"})

        elif action == "delete_file":
            raw_path = str(data.get("path", "")).strip()
            if not raw_path:
                self._json({"ok": False, "msg": "Missing path"})
                return
            p    = Path(raw_path)
            safe = _safe_in_any_root(p)
            if safe is None or not safe.is_file():
                self._json({"ok": False, "msg": "File not in any media root or not found"})
                return
            try:
                safe.unlink()
                _invalidate_lib_cache()
                self._json({"ok": True, "msg": f"Deleted {safe.name}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "create_subdir":
            # Accept either:
            #   {name: "@N/rel/path/newfolder"}  — fully encoded path
            #   {parent: "@N/rel/path", name: "newfolder"}  — parent + leaf name
            raw_name   = str(data.get("name",   "")).strip()
            raw_parent = str(data.get("parent", "")).strip()

            if not raw_name or ".." in raw_name:
                self._json({"ok": False, "msg": "Invalid folder name"})
                return

            from hc.web_filemanager import _resolve_fm_path, _decode_root, _encode_path

            if raw_parent:
                # Resolve parent first, then append the leaf folder name
                leaf = re.sub(r'[/\\<>"|?*\x00]', "_", raw_name.lstrip("/\\"))
                if not leaf:
                    self._json({"ok": False, "msg": "Invalid folder name"})
                    return

                if raw_parent == "" or raw_parent == "/":
                    # Root of default media dir
                    dest_dir = _safe_in_root(MEDIA_DIR() / leaf, MEDIA_DIR())
                else:
                    resolved = _resolve_fm_path(raw_parent)
                    if resolved is None:
                        self._json({"ok": False, "msg": "Parent path not found or access denied"})
                        return
                    root_dir, parent_abs = resolved
                    if not parent_abs.is_dir():
                        self._json({"ok": False, "msg": "Parent is not a directory"})
                        return
                    candidate = parent_abs / leaf
                    dest_dir = _safe_in_root(candidate, root_dir)

                if dest_dir is None:
                    self._json({"ok": False, "msg": "Path traversal denied"})
                    return

            elif raw_name.startswith("@"):
                # Fully encoded @N/rel/newfolder
                # Split off the last segment as the new leaf name
                parts = raw_name.rsplit("/", 1)
                if len(parts) == 2:
                    parent_enc, leaf = parts[0], parts[1]
                else:
                    # e.g. "@0" with no slash — create a dir directly inside root 0
                    parent_enc, leaf = raw_name, ""

                leaf = re.sub(r'[/\\<>"|?*\x00]', "_", leaf)

                if parent_enc:
                    decoded = _decode_root(parent_enc)
                    if decoded is None:
                        self._json({"ok": False, "msg": "Invalid encoded path"})
                        return
                    _, root_dir, rel_within = decoded
                    try:
                        root_dir = root_dir.resolve()
                    except Exception:
                        pass
                    parent_abs = root_dir / rel_within if rel_within else root_dir
                    if not leaf:
                        self._json({"ok": False, "msg": "Folder name is required"})
                        return
                    candidate = parent_abs / leaf
                    dest_dir  = _safe_in_root(candidate, root_dir)
                else:
                    dest_dir = None

                if dest_dir is None:
                    self._json({"ok": False, "msg": "Path traversal denied"})
                    return

            else:
                # Plain name — create inside MEDIA_DIR
                safe_name = re.sub(r'[/\\<>"|?*\x00]', "_", raw_name)
                dest_dir  = _safe_in_root(MEDIA_DIR() / safe_name, MEDIA_DIR())
                if dest_dir is None:
                    self._json({"ok": False, "msg": "Path traversal denied"})
                    return

            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                self._json({"ok": True, "msg": f"Created: {dest_dir.name}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "save_mail_config":
            try:
                from hc.constants import CONFIG_DIR
                import json as _json
                to_addrs  = data.get("to_addrs", [])
                if not isinstance(to_addrs, list) or not to_addrs:
                    raise ValueError("to_addrs must be a non-empty list")
                path = CONFIG_DIR() / "mail_config.hcf"
                # Preserve the stored client_secret if the client sent the redaction placeholder
                client_secret = str(data.get("client_secret", ""))
                if client_secret in ("••••••••", ""):
                    try:
                        existing = _json.loads(path.read_text(encoding="utf-8"))
                        client_secret = existing.get("client_secret", "")
                    except Exception:
                        client_secret = ""
                cfg = {
                    "enabled":       bool(data.get("enabled", False)),
                    "tenant_id":     str(data.get("tenant_id", "")).strip(),
                    "client_id":     str(data.get("client_id", "")).strip(),
                    "client_secret": client_secret,
                    "from_addr":     str(data.get("from_addr", "")).strip(),
                    "to_addrs":      [str(a).strip() for a in to_addrs if str(a).strip()],
                    "on_error":      bool(data.get("on_error", True)),
                    "on_stop":       bool(data.get("on_stop", True)),
                    "cooldown_secs": max(0, int(data.get("cooldown_secs", 300))),
                }
                path.write_text(_json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
                log.info("mail_config.hcf updated via Web UI (tenant=%s enabled=%s)",
                         cfg["tenant_id"][:8] or "—", cfg["enabled"])
                self._json({"ok": True, "msg": "mail_config.hcf saved"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "test_mail_alert":
            try:
                to_addr = str(data.get("to_addr", "")).strip() or None
                from hc.mailer import test_alert
                ok, err = test_alert(to_addr)
                if ok:
                    self._json({"ok": True,  "msg": "Test email sent — check your inbox."})
                else:
                    self._json({"ok": False, "msg": err or "Test failed — check server logs."})
            except Exception as exc:
                self._json({"ok": False, "msg": f"Test error: {exc}"})

        elif action == "reset_everything":
            self._handle_reset_everything(data)

        elif action == "backup":
            self._handle_backup(data)

        elif action == "restore":
            self._handle_restore(data)

        elif action == "save_media_roots":
            self._handle_save_media_roots(data)

        elif action == "holidays/custom":
            # POST /api/holidays/custom — add a user-defined holiday.
            # _dispatch only receives the already-parsed `data` dict, not the
            # original raw bytes.  Re-serialise so _post_holidays_custom can
            # parse it the same way regardless of call path.
            import json as _json
            self._post_holidays_custom(_json.dumps(data).encode("utf-8"))

        elif action == "settings":
            # POST /api/settings — persist settings; accepts flat or grouped payload.
            # Flat:    { "accent_color": "#b87333", "holiday_country": "US", … }
            # Grouped: { "appearance": { "accent_color": "#b87333" }, … }
            from hc.web_settings_manager import save_settings, load_settings_grouped
            try:
                if not isinstance(data, dict):
                    self._json({"error": "Request body must be a JSON object."}, 400)
                    return
                save_settings(data)
                # Return the full grouped payload so the UI can refresh in one round-trip
                self._json(load_settings_grouped())
            except Exception as exc:
                log.error("POST /api/settings: %s", exc)
                self._json({"error": str(exc)}, 500)

        elif action == "reset_settings":
            # POST /api/reset_settings — wipe persisted settings and return factory defaults.
            from hc.web_settings_manager import reset_settings
            try:
                defaults = reset_settings()
                log.info("App settings reset to factory defaults via Web UI")
                self._json({"ok": True, "msg": "Settings reset to factory defaults.", "values": defaults})
            except Exception as exc:
                log.error("POST /api/reset_settings: %s", exc)
                self._json({"ok": False, "msg": str(exc)})

        elif action == "events/bulk":
            # POST /api/events/bulk — create one OneShotEvent per stream entry
            mgr = _WEB_MANAGER
            if mgr is None:
                self._json({"error": "Manager not ready — try again shortly."}, 503)
                return
            try:
                play_at_str: str = data["play_at"]
                streams_raw = data["streams"]
                if not isinstance(streams_raw, list) or not streams_raw:
                    raise ValueError("'streams' must be a non-empty list.")
                play_at = datetime.fromisoformat(play_at_str)
            except (KeyError, ValueError) as exc:
                self._json({"error": f"Bad payload: {exc}"}, 400)
                return

            # Optional broadcast end time
            broadcast_end = None
            be_str = data.get("broadcast_end", "")
            if be_str:
                try:
                    broadcast_end = datetime.fromisoformat(be_str)
                    if broadcast_end <= play_at:
                        log.warning("events/bulk: broadcast_end not after play_at — ignored")
                        broadcast_end = None
                except ValueError:
                    log.warning("events/bulk: invalid broadcast_end %r — ignored", be_str)

            bulk_comment: str = str(data.get("comment", "")).strip()[:500]

            created = []
            errors  = []
            for item in streams_raw:
                stream_name = item.get("stream_name", "").strip()
                file_path_s = item.get("file_path",   "").strip()
                if not stream_name or not file_path_s:
                    errors.append({"stream_name": stream_name or "?",
                                   "error": "stream_name and file_path are required."})
                    continue
                if mgr.get_state(stream_name) is None:
                    errors.append({"stream_name": stream_name,
                                   "error": f"Stream '{stream_name}' not found."})
                    log.warning("events/bulk: unknown stream: %s", stream_name)
                    continue
                try:
                    ev = JSONManager.add_event(
                        mgr.events,
                        stream_name   = stream_name,
                        file_path     = Path(file_path_s),
                        play_at       = play_at,
                        broadcast_end = broadcast_end,
                    )
                    if bulk_comment:
                        try:
                            ev.comment = bulk_comment
                            JSONManager._save_events(mgr.events)
                        except AttributeError:
                            pass
                    ev_dict = {
                        "event_id":    ev.event_id,
                        "stream_name": ev.stream_name,
                        "file_path":   str(ev.file_path),
                        "play_at":     ev.play_at.isoformat(),
                    }
                    if broadcast_end is not None:
                        ev_dict["broadcast_end"] = broadcast_end.isoformat()
                    created.append(ev_dict)
                    log.info("events/bulk: created event stream=%s file=%s at=%s",
                             stream_name, file_path_s, play_at.isoformat())
                except Exception as exc:
                    errors.append({"stream_name": stream_name, "error": str(exc)})
                    log.error("events/bulk: failed stream=%s: %s", stream_name, exc)

            status = 400 if not created else (207 if errors else 200)
            self._json({"created": created, "errors": errors}, status)

        elif action == "open_firewall":
            # POST /api/open_firewall  {"ports": [8555, 8556, 8558, 8559]}
            # Attempt to open the given TCP ports in the system firewall.
            # Returns {ok, msg, opened, failed, platform, elevated}
            import sys as _sys
            raw_ports = data.get("ports", [])
            try:
                ports_to_open = [int(p) for p in raw_ports if 0 < int(p) < 65536]
            except (TypeError, ValueError):
                self._json({"ok": False, "msg": "Invalid ports list"}); return
            if not ports_to_open:
                self._json({"ok": False, "msg": "No valid ports provided"}); return

            platform = _sys.platform
            opened: list = []
            failed: list = []
            elevated = False
            msg = ""

            try:
                if platform.startswith("win"):
                    import ctypes
                    elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
                    if not elevated:
                        self._json({
                            "ok": False,
                            "msg": "Administrator privileges required to modify Windows Firewall.",
                            "platform": "windows",
                            "elevated": False,
                            "hint": "Re-launch HydraCast as Administrator to auto-open ports.",
                        }); return
                    import subprocess as _sp
                    for p in ports_to_open:
                        rule = f"HydraCast Port {p}"
                        # Check if already exists
                        chk = _sp.run(
                            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule}"],
                            capture_output=True, text=True,
                        )
                        if "No rules match" not in chk.stdout and chk.returncode == 0:
                            opened.append(p)  # already open
                            continue
                        r = _sp.run(
                            ["netsh", "advfirewall", "firewall", "add", "rule",
                             f"name={rule}", "dir=in", "action=allow",
                             "protocol=TCP", f"localport={p}"],
                            capture_output=True, text=True,
                        )
                        if r.returncode == 0:
                            opened.append(p)
                        else:
                            failed.append({"port": p, "error": r.stderr.strip() or "netsh error"})
                    msg = (
                        f"Opened {len(opened)} port(s) via Windows Firewall (netsh)."
                        if opened else "No ports were opened."
                    )

                elif platform.startswith("linux"):
                    import os as _os, subprocess as _sp
                    elevated = (_os.geteuid() == 0)
                    if not elevated:
                        self._json({
                            "ok": False,
                            "msg": "Root privileges required to modify Linux firewall.",
                            "platform": "linux",
                            "elevated": False,
                            "hint": "Run HydraCast as root, or manually open ports with:\n"
                                    + "\n".join(f"  sudo ufw allow {p}/tcp" for p in ports_to_open),
                        }); return
                    import shutil as _sh
                    if _sh.which("ufw"):
                        for p in ports_to_open:
                            r = _sp.run(["ufw", "allow", f"{p}/tcp"], capture_output=True, text=True)
                            (opened if r.returncode == 0 else failed).append(
                                p if r.returncode == 0 else {"port": p, "error": r.stderr.strip()}
                            )
                        _sp.run(["ufw", "--force", "enable"], capture_output=True)
                        msg = f"Opened {len(opened)} port(s) via ufw."
                    elif _sh.which("firewall-cmd"):
                        for p in ports_to_open:
                            r = _sp.run(
                                ["firewall-cmd", "--permanent", "--add-port", f"{p}/tcp"],
                                capture_output=True, text=True,
                            )
                            (opened if r.returncode == 0 else failed).append(
                                p if r.returncode == 0 else {"port": p, "error": r.stderr.strip()}
                            )
                        _sp.run(["firewall-cmd", "--reload"], capture_output=True)
                        msg = f"Opened {len(opened)} port(s) via firewalld."
                    elif _sh.which("iptables"):
                        for p in ports_to_open:
                            chk = _sp.run(
                                ["iptables", "-C", "INPUT", "-p", "tcp", "--dport", str(p), "-j", "ACCEPT"],
                                capture_output=True,
                            )
                            if chk.returncode == 0:
                                opened.append(p); continue
                            r = _sp.run(
                                ["iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(p), "-j", "ACCEPT"],
                                capture_output=True, text=True,
                            )
                            (opened if r.returncode == 0 else failed).append(
                                p if r.returncode == 0 else {"port": p, "error": r.stderr.strip()}
                            )
                        msg = f"Opened {len(opened)} port(s) via iptables."
                    else:
                        self._json({
                            "ok": False,
                            "msg": "No supported firewall tool found (ufw / firewall-cmd / iptables).",
                            "platform": "linux",
                            "elevated": elevated,
                        }); return

                else:
                    self._json({
                        "ok": False,
                        "msg": "Automatic firewall configuration is not supported on this OS. "
                               "Please open the required ports manually.",
                        "platform": platform,
                        "elevated": False,
                    }); return

            except Exception as exc:
                log.error("open_firewall error: %s", exc)
                self._json({"ok": False, "msg": f"Firewall error: {exc}"}); return

            ok = len(opened) > 0 and len(failed) == 0
            log.info("open_firewall: opened=%s failed=%s", opened, failed)
            self._json({
                "ok":       ok,
                "msg":      msg,
                "opened":   opened,
                "failed":   failed,
                "platform": platform,
                "elevated": elevated,
            })

        elif action == "reset":
            self._handle_reset(data)

        else:
            self._json({"ok": False, "msg": f"Unknown action: {action}"}, 404)

    def _handle_reset(self, data: Dict[str, Any]) -> None:
        """
        POST /api/reset  { "confirm": true }

        1. Stop every running stream.
        2. Delete every file inside config/.
        3. Clear all in-memory state.
        4. Send HTTP response so the browser gets a reply.
        5. os._exit(1) — kills the process so the Guardian detects the exit
           and relaunches hydracast_bg.exe with the original arguments.

        Why os._exit(1) and not Popen/execv:
        ──────────────────────────────────────
        This method runs on a web-handler thread inside hydracast_bg.exe.
        sys.exit(0) raises SystemExit which hydracast_bg._run_hydracast_once()
        catches — the outer process stays alive and the Guardian never fires.
        subprocess.Popen([sys.executable]+sys.argv) on a frozen build doubles
        the exe path ("hydracast_bg.exe hydracast_bg.exe …") and fails
        silently.  os._exit(1) kills the whole process instantly; the Guardian
        detects the exit-code-0, treats it as an intentional restart, and
        relaunches the correct binary.
        """
        import os as _os, sys as _sys, threading as _thr

        if not data.get("confirm"):
            self._json({"ok": False, "msg": "confirm=true required"}, 400)
            return

        mgr     = _WEB_MANAGER
        stopped: List[str] = []
        wiped:   List[str] = []
        errors:  List[str] = []

        # ── 1. Force-stop all running streams ────────────────────────────────
        import time as _time
        if mgr is not None:
            for st in list(getattr(mgr, "states", [])):
                try:
                    worker = mgr.get_worker(st.config.name)
                    if worker is not None:
                        try:
                            worker.kill()
                        except Exception:
                            pass
                    mgr.stop(st.config.name)
                    stopped.append(st.config.name)
                except Exception as exc:
                    errors.append(f"stop {st.config.name}: {exc}")

        _time.sleep(0.4)

        # ── 2. Wipe every file AND subdirectory in config/ ───────────────────
        from hc.constants import CONFIG_DIR as _CFG_DIR
        import shutil as _shutil
        cfg_dir = _CFG_DIR()
        try:
            for p in sorted(cfg_dir.iterdir()):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                        wiped.append(p.name)
                    elif p.is_dir():
                        _shutil.rmtree(p, ignore_errors=False)
                        wiped.append(p.name + "/")
                except Exception as exc:
                    errors.append(f"delete {p.name}: {exc}")
                    log.error("reset: could not delete '%s': %s", p.name, exc)
        except Exception as exc:
            errors.append(f"config dir: {exc}")
            log.error("reset: config dir error: %s", exc)

        # ── 3. Clear in-memory state ──────────────────────────────────────────
        try:
            from hc.web_settings_manager import reset_settings
            reset_settings()
        except Exception:
            pass

        try:
            set_media_roots([])
            _invalidate_lib_cache()
        except Exception:
            pass

        if mgr is not None:
            try:
                mgr.reload_from_configs([])
            except Exception:
                pass
            try:
                mgr.events = []
            except Exception:
                pass

        log.info("reset: wiped [%s] stopped [%s]%s",
                 ", ".join(wiped) or "none",
                 ", ".join(stopped) or "none",
                 f" errors: {'; '.join(errors)}" if errors else "")

        # ── 4. Respond before os._exit kills the socket ───────────────────────
        self._json({
            "ok":      True,
            "msg":     "Reset complete — restarting server…",
            "wiped":   wiped,
            "stopped": stopped,
            "errors":  errors,
        })

        # ── 5. Kill process — Guardian detects exit and relaunches ────────────
        def _do_reset_restart():
            import time as _t
            _t.sleep(0.8)
            log.info("reset: calling os._exit(1) — Guardian will relaunch.")
            _os._exit(1)

        _thr.Thread(target=_do_reset_restart, daemon=False,
                    name="hc-factory-reset").start()

    # ── Multipart upload (legacy single-shot, kept for backward-compat) ────────
    def _handle_upload(self) -> None:
        from hc.web_access_log import _real_ip
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > UPLOAD_MAX_BYTES:
                self._json({"ok": False, "msg": "File exceeds 10 GB limit"}, 413)
                return

            client_ip = _real_ip(self)
            ct = self.headers.get("Content-Type", "")
            boundary: Optional[bytes] = None
            for part in ct.split(";"):
                p = part.strip()
                if p.lower().startswith("boundary="):
                    boundary = p[9:].strip('"').encode("latin-1")
                    break
            if not boundary:
                self._json({"ok": False, "msg": "Missing boundary"})
                return

            raw = self.rfile.read(cl)
            sep = b"--" + boundary

            file_bytes: Optional[bytes] = None
            file_name:  Optional[str]   = None
            subdir = ""

            for seg in raw.split(sep):
                seg = seg.lstrip(b"\r\n")
                if not seg or seg.startswith(b"--"):
                    continue
                if b"\r\n\r\n" not in seg:
                    continue
                hdr_raw, body = seg.split(b"\r\n\r\n", 1)
                if body.endswith(b"\r\n"):
                    body = body[:-2]
                hdr_str = hdr_raw.decode("utf-8", errors="replace")
                cd_line = next(
                    (ln for ln in hdr_str.splitlines()
                     if ln.lower().startswith("content-disposition:")),
                    "",
                )
                field_name = fname = ""
                for tok in cd_line.split(";"):
                    tok = tok.strip()
                    if tok.startswith("name="):
                        field_name = tok[5:].strip('"')
                    elif tok.startswith("filename="):
                        fname = tok[9:].strip('"')
                if field_name == "file" and fname:
                    file_bytes = body
                    file_name  = fname
                elif field_name == "subdir":
                    subdir = body.decode("utf-8", errors="replace").strip().lstrip("/\\")

            if file_bytes is None or not file_name:
                self._json({"ok": False, "msg": "No file field found"})
                return

            subdir_raw  = re.sub(r'\.\.', '_', subdir)
            dest_dir = _decode_upload_subdir(subdir_raw)
            if dest_dir is None:
                self._json({"ok": False, "msg": "Invalid upload directory"})
                return

            fname_clean = Path(file_name).name
            ext         = Path(fname_clean).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                self._json({"ok": False, "msg": f"Unsupported extension: {ext}"})
                return

            safe_name = re.sub(r'[^\w.\-]', '_', fname_clean)
            if not safe_name or safe_name.startswith('.'):
                self._json({"ok": False, "msg": "Invalid filename"})
                return

            dest_dir.mkdir(parents=True, exist_ok=True)

            dest     = dest_dir / safe_name
            tmp_path = dest.with_suffix(dest.suffix + ".tmp")
            try:
                tmp_path.write_bytes(file_bytes)
                tmp_path.rename(dest)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

            _invalidate_lib_cache()
            import logging as _lg
            _lg.getLogger("hc.upload_audit").info(
                "LEGACY UPLOAD  ip=%-15s  file=%-40s  size=%d B",
                client_ip, safe_name, len(file_bytes),
            )
            log.info("Upload saved: %s (ip=%s)", dest, client_ip)
            # ── Notify folder-source streams about the new file ──
            _notify_folder_upload(dest_dir)
            self._json({"ok": True, "msg": f"Saved: {safe_name}"})
        except Exception as exc:
            log.error("Upload error: %s", exc)
            self._json({"ok": False, "msg": f"Upload error: {exc}"}, 500)

    # ── Media roots management ────────────────────────────────────────────────
    def _handle_save_media_roots(self, data: Dict[str, Any]) -> None:
        """
        POST action: save_media_roots
        Body: { "roots": ["/path/a", "/path/b"] }

        Replaces the extra media roots list.  The default MEDIA_DIR is always
        kept as the first root and cannot be removed.  Invalidates the library
        cache so the new roots are reflected immediately in the Web UI.
        """
        from pathlib import Path as _Path
        try:
            raw_roots = data.get("roots", [])
            if not isinstance(raw_roots, list):
                self._json({"ok": False, "msg": "'roots' must be a list of path strings"})
                return
            new_roots: List[Path] = []
            errors: List[str] = []
            for r in raw_roots:
                p = _Path(str(r).strip())
                if not p.is_absolute():
                    errors.append(f"'{p}' is not an absolute path — skipped")
                    continue
                if not p.exists():
                    errors.append(f"'{p}' does not exist — skipped")
                    continue
                if not p.is_dir():
                    errors.append(f"'{p}' is not a directory — skipped")
                    continue
                new_roots.append(p)
            set_media_roots(new_roots)
            _invalidate_lib_cache()
            roots_now = get_media_roots()
            log.info(
                "media_roots updated: %d root(s) total%s",
                len(roots_now),
                f" | warnings: {'; '.join(errors)}" if errors else "",
            )
            self._json({
                "ok":       True,
                "roots":    [str(r) for r in roots_now],
                "warnings": errors,
                "msg":      (
                    f"Media roots updated: {len(roots_now)} root(s) active."
                    + (f" Warnings: {'; '.join(errors)}." if errors else "")
                ),
            })
        except Exception as exc:
            log.error("save_media_roots error: %s", exc)
            self._json({"ok": False, "msg": f"Error: {exc}"}, 500)

    # ── Factory reset ────────────────────────────────────────────────────────
    def _handle_reset_everything(self, data: Dict[str, Any]) -> None:
        """
        POST action: reset_everything
        Body (all optional):
          {
            "confirm":        true,          // must be true — safety gate
            "backup_first":   true,          // if true, write a .hc backup before wiping
            "keep_mail":      false,         // if true, preserve mail_config.hcf
            "keep_media_roots": false,       // if true, preserve media_roots.hcf
          }

        Wipes every HydraCast config file, stops all streams, clears in-memory
        state, and resets application settings to factory defaults.  The backup
        (if requested) is returned as a downloadable .hc file; otherwise a JSON
        ``{"ok": true, …}`` response is sent.

        Config files removed:
          streams.hcf, events.hcf, resume_positions.hcf, app_settings.hcf
          + optionally: mail_config.hcf, media_roots.hcf
        """
        import json as _json
        from hc.constants import CONFIG_DIR
        from hc.web_settings_manager import reset_settings

        # ── Safety gate ───────────────────────────────────────────────────────
        if not data.get("confirm"):
            self._json({
                "ok":  False,
                "msg": "Reset aborted: 'confirm' must be true.",
            }, 400)
            return

        backup_first    = bool(data.get("backup_first",    True))
        keep_mail       = bool(data.get("keep_mail",       False))
        keep_media_roots = bool(data.get("keep_media_roots", False))

        cfg_dir = CONFIG_DIR()
        mgr     = _WEB_MANAGER

        try:
            # ── 1. Optional pre-reset backup ──────────────────────────────────
            # Build the backup payload in memory so we can send it later if
            # the caller set backup_first; otherwise we discard it.
            backup_payload: Dict[str, Any] = {
                "format":  "hydracast_backup",
                "version": APP_VER,
                "created": datetime.now().isoformat(timespec="seconds"),
                "note":    "Pre-reset automatic backup",
            }
            for fname, key in [
                ("streams.hcf",          "streams"),
                ("events.hcf",           "events"),
                ("mail_config.hcf",      "mail_config"),
                ("resume_positions.hcf", "resume_positions"),
                ("app_settings.hcf",     "app_settings"),
                ("media_roots.hcf",      "media_roots"),
            ]:
                p = cfg_dir / fname
                try:
                    backup_payload[key] = (
                        _json.loads(p.read_text(encoding="utf-8")) if p.exists() else
                        ([] if key in ("streams", "events", "media_roots") else {})
                    )
                except Exception:
                    backup_payload[key] = [] if key in ("streams", "events", "media_roots") else {}

            # ── 2. Stop all streams ───────────────────────────────────────────
            stopped: List[str] = []
            if mgr is not None:
                for st in list(mgr.states):
                    try:
                        mgr.stop(st.config.name)
                        stopped.append(st.config.name)
                    except Exception as exc:
                        log.warning("reset_everything: could not stop '%s': %s",
                                    st.config.name, exc)

            # ── 3. Delete config files ────────────────────────────────────────
            _FILES_TO_WIPE = [
                "streams.hcf",
                "events.hcf",
                "resume_positions.hcf",
                "app_settings.hcf",
            ]
            if not keep_mail:
                _FILES_TO_WIPE.append("mail_config.hcf")
            if not keep_media_roots:
                _FILES_TO_WIPE.append("media_roots.hcf")

            wiped: List[str] = []
            wipe_errors: List[str] = []
            for fname in _FILES_TO_WIPE:
                p = cfg_dir / fname
                try:
                    p.unlink(missing_ok=True)
                    wiped.append(fname)
                except Exception as exc:
                    wipe_errors.append(f"{fname}: {exc}")
                    log.error("reset_everything: failed to delete '%s': %s", fname, exc)

            # ── 4. Reset in-memory state ──────────────────────────────────────
            # App settings → factory defaults
            reset_settings()

            # Clear media roots if wiped
            if not keep_media_roots:
                try:
                    from hc.constants import set_media_roots
                    set_media_roots([])
                    _invalidate_lib_cache()
                except Exception as exc:
                    log.warning("reset_everything: could not reset media_roots: %s", exc)

            # Reload manager from now-empty config
            if mgr is not None:
                try:
                    from hc.json_manager import JSONManager
                    mgr.reload_from_configs([])
                except AttributeError:
                    pass  # manager version without reload_from_configs
                except Exception as exc:
                    log.warning("reset_everything: manager reload failed: %s", exc)
                # Clear events
                try:
                    mgr.events = []
                except Exception:
                    pass

            log.info(
                "reset_everything: wiped %s | stopped streams: %s%s",
                ", ".join(wiped),
                ", ".join(stopped) or "none",
                f" | errors: {'; '.join(wipe_errors)}" if wipe_errors else "",
            )

            # ── 5. Return ─────────────────────────────────────────────────────
            if backup_first:
                # Send the pre-reset backup as a downloadable file
                body  = _json.dumps(backup_payload, indent=2, ensure_ascii=False).encode("utf-8")
                ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = f"hydracast_pre_reset_backup_{ts}.hc"
                self.send_response(200)
                self.send_header("Content-Type",        "application/json")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Content-Length",      str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                # Embed reset result in a response header the UI can read
                summary = (
                    f"wiped={','.join(wiped)};"
                    f"stopped={len(stopped)};"
                    f"errors={len(wipe_errors)}"
                )
                self.send_header("X-Reset-Summary", summary)
                for k, v in _SEC_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                log.info("reset_everything: pre-reset backup sent (%d bytes)", len(body))
            else:
                self._json({
                    "ok":          True,
                    "msg":         (
                        f"Factory reset complete. "
                        f"Wiped: {', '.join(wiped)}. "
                        f"Stopped streams: {len(stopped)}."
                        + (f" Errors: {'; '.join(wipe_errors)}." if wipe_errors else "")
                    ),
                    "wiped":       wiped,
                    "stopped":     stopped,
                    "errors":      wipe_errors,
                    "kept": (
                        (["mail_config.hcf"] if keep_mail else []) +
                        (["media_roots.hcf"] if keep_media_roots else [])
                    ),
                })

        except Exception as exc:
            log.error("reset_everything error: %s", exc)
            self._json({"ok": False, "msg": f"Reset error: {exc}"}, 500)

    # ── Backup ───────────────────────────────────────────────────────────────
    def _handle_backup(self, include: Dict[str, Any]) -> None:
        """
        Build a plain-JSON .hc backup and send it as a downloadable file.

        *include* is a dict with boolean flags controlling which sections to
        include in the archive.  All default to True:

          streams       — streams.hcf  (stream configs)
          events        — events.hcf   (one-shot scheduled events)
          mail          — mail_config.hcf (password is ALWAYS redacted)
          resume        — resume_positions.hcf
          app_settings  — app_settings.hcf (appearance / regional /
                           notifications / system settings)
          media_roots   — media_roots.hcf (extra media root directories)

        The resulting file can be re-imported via the restore action or via
        the factory-reset flow (reset_everything with backup_first=true).
        """
        import json as _json
        from hc.constants import BASE_DIR, CONFIG_DIR

        try:
            payload: Dict[str, Any] = {
                "format":  "hydracast_backup",
                "version": APP_VER,
                "created": datetime.now().isoformat(timespec="seconds"),
            }

            # ── Streams ─────────────────────────────────────────────────────
            if include.get("streams", True):
                p = CONFIG_DIR() / "streams.hcf"
                try:
                    payload["streams"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else []
                except Exception:
                    payload["streams"] = []

            # ── Events ──────────────────────────────────────────────────────
            if include.get("events", True):
                p = CONFIG_DIR() / "events.hcf"
                try:
                    payload["events"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else []
                except Exception:
                    payload["events"] = []

            # ── Mail config (password redacted for safety) ───────────────────
            if include.get("mail", True):
                p = CONFIG_DIR() / "mail_config.hcf"
                try:
                    if p.exists():
                        mc = _json.loads(p.read_text(encoding="utf-8"))
                        # Redact password — restore will leave it blank
                        mc.pop("password", None)
                        payload["mail_config"] = mc
                    else:
                        payload["mail_config"] = {}
                except Exception:
                    payload["mail_config"] = {}

            # ── Resume positions ────────────────────────────────────────────
            if include.get("resume", True):
                p = CONFIG_DIR() / "resume_positions.hcf"
                try:
                    payload["resume_positions"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else {}
                except Exception:
                    payload["resume_positions"] = {}

            # ── App settings (holiday country, UI prefs persisted server-side) ──
            if include.get("app_settings", True):
                p = CONFIG_DIR() / "app_settings.hcf"
                try:
                    payload["app_settings"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else {}
                except Exception:
                    payload["app_settings"] = {}

            # ── Media roots (extra user-defined root directories) ────────────
            if include.get("media_roots", True):
                p = CONFIG_DIR() / "media_roots.hcf"
                try:
                    payload["media_roots"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else []
                except Exception:
                    payload["media_roots"] = []


            body = _json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"hydracast_backup_{ts}.hc"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            for k, v in _SEC_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            log.info("Backup downloaded: %s (%d bytes)", fname, len(body))

        except Exception as exc:
            log.error("Backup error: %s", exc)
            self._json({"ok": False, "msg": f"Backup error: {exc}"}, 500)

    # ── Restore ──────────────────────────────────────────────────────────────
    def _handle_restore(self, payload: Dict[str, Any]) -> None:
        """
        Restore from a .hc backup payload.  Writes config files back to disk
        then restarts all streams so changes take effect immediately.
        """
        import json as _json
        from hc.constants import BASE_DIR, CONFIG_DIR

        try:
            if payload.get("format") != "hydracast_backup":
                self._json({"ok": False, "msg": "Not a valid HydraCast backup file"})
                return

            restored: list[str] = []
            failed:   list[str] = []

            # ── Streams ─────────────────────────────────────────────────────
            if "streams" in payload:
                try:
                    p = CONFIG_DIR() / "streams.hcf"
                    if not isinstance(payload["streams"], list):
                        raise ValueError("streams must be a list")
                    p.write_text(
                        _json.dumps(payload["streams"], indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    restored.append("streams")
                    log.info("restore: streams.hcf written (%d streams)",
                             len(payload["streams"]))
                except Exception as exc:
                    failed.append(f"streams: {exc}")
                    log.error("restore: streams section failed: %s", exc)

            # ── Events ──────────────────────────────────────────────────────
            if "events" in payload:
                try:
                    p = CONFIG_DIR() / "events.hcf"
                    if not isinstance(payload["events"], list):
                        raise ValueError("events must be a list")
                    p.write_text(
                        _json.dumps(payload["events"], indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    restored.append("events")
                except Exception as exc:
                    failed.append(f"events: {exc}")
                    log.error("restore: events section failed: %s", exc)

            # ── Mail config (password intentionally absent — user must re-enter) ──
            if "mail_config" in payload:
                try:
                    p = CONFIG_DIR() / "mail_config.hcf"
                    existing: Dict[str, Any] = {}
                    try:
                        if p.exists():
                            existing = _json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                    mc = dict(payload["mail_config"])
                    # Preserve the stored password if restore doesn't include one
                    if "password" not in mc and "password" in existing:
                        mc["password"] = existing["password"]
                    p.write_text(
                        _json.dumps(mc, indent=4, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    restored.append("mail_config")
                except Exception as exc:
                    failed.append(f"mail_config: {exc}")
                    log.error("restore: mail_config section failed: %s", exc)

            # ── Resume positions ────────────────────────────────────────────
            if "resume_positions" in payload:
                try:
                    p = CONFIG_DIR() / "resume_positions.hcf"
                    if not isinstance(payload["resume_positions"], dict):
                        raise ValueError("resume_positions must be an object")
                    p.write_text(
                        _json.dumps(payload["resume_positions"], indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    restored.append("resume_positions")
                except Exception as exc:
                    failed.append(f"resume_positions: {exc}")
                    log.error("restore: resume_positions section failed: %s", exc)

            # ── App settings ────────────────────────────────────────────────
            if "app_settings" in payload:
                try:
                    from hc.web_settings_manager import save_settings
                    if not isinstance(payload["app_settings"], dict):
                        raise ValueError("app_settings must be an object")
                    save_settings(payload["app_settings"])
                    restored.append("app_settings")
                    log.info("restore: app_settings written (%d key(s))",
                             len(payload["app_settings"]))
                except Exception as exc:
                    failed.append(f"app_settings: {exc}")
                    log.error("restore: app_settings section failed: %s", exc)

            # ── Media roots ──────────────────────────────────────────────────
            if "media_roots" in payload:
                try:
                    if not isinstance(payload["media_roots"], list):
                        raise ValueError("media_roots must be a list")
                    new_roots = [Path(r) for r in payload["media_roots"] if r]
                    set_media_roots(new_roots)
                    _invalidate_lib_cache()
                    restored.append("media_roots")
                    log.info("restore: media_roots updated (%d extra root(s))",
                             len(new_roots))
                except Exception as exc:
                    failed.append(f"media_roots: {exc}")
                    log.error("restore: media_roots section failed: %s", exc)


            # ── Reload manager state ─────────────────────────────────────────
            mgr = _WEB_MANAGER
            if mgr and "streams" in restored:
                try:
                    from hc.json_manager import JSONManager
                    new_configs = JSONManager.load()
                    mgr.reload_from_configs(new_configs)
                    log.info("restore: manager reloaded with %d stream(s)", len(new_configs))
                except AttributeError:
                    for st in list(mgr.states):
                        try:
                            mgr.restart(st.config.name)
                        except Exception:
                            pass
                except Exception as exc:
                    log.warning("restore: manager reload failed: %s — streams not restarted", exc)

            if "events" in restored and mgr:
                try:
                    from hc.json_manager import JSONManager
                    mgr.events = JSONManager.load_events()
                except Exception:
                    pass

            log.info("restore: completed — restored: %s%s",
                     ", ".join(restored),
                     f" | FAILED: {', '.join(failed)}" if failed else "")

            if not restored and failed:
                self._json({"ok": False,
                            "msg": f"Restore failed: {'; '.join(failed)}",
                            "restored": [], "failed": failed})
            else:
                msg = f"Restored: {', '.join(restored)}."
                if failed:
                    msg += f" Warnings: {'; '.join(failed)}."
                else:
                    msg += " Streams reloaded."
                self._json({
                    "ok":       True,
                    "msg":      msg,
                    "restored": restored,
                    "failed":   failed,
                })

        except Exception as exc:
            log.error("Restore error: %s", exc)
            self._json({"ok": False, "msg": f"Restore error: {exc}"}, 500)

    # ── PUT handler ──────────────────────────────────────────────────────────
    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            if path == "/api/holidays/custom":
                self._put_holidays_custom(raw)
            else:
                self._send(404, b"Not Found", "text/plain")
        except Exception as exc:
            log.error("WebHandler PUT %s: %s", path, exc)
            self._json({"error": "internal server error"}, 500)

    # ── DELETE handler ───────────────────────────────────────────────────────
    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            if path == "/api/holidays/custom":
                self._delete_holidays_custom(raw)
            elif path == "/api/holidays/cache":
                self._delete_holidays_cache(raw)
            else:
                self._send(404, b"Not Found", "text/plain")
        except Exception as exc:
            log.error("WebHandler DELETE %s: %s", path, exc)
            self._json({"error": "internal server error"}, 500)
