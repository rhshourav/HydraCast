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
    get_web_port,
)
from hc.json_manager import JSONManager
from hc.models import OneShotEvent, PlaylistItem, StreamConfig, StreamStatus
from hc.utils import _fmt_duration, _fmt_size, _local_ip, _safe_path
from hc.web_html import _HTML
from hc.web_csvmanager import CSVManager

log = logging.getLogger(__name__)

# Module-level manager reference (set by hydracast.py)
_WEB_MANAGER = None

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
    for ext in SUPPORTED_EXTS:
        for f in MEDIA_DIR().rglob(f"*{ext}"):
            try:
                meta = probe_metadata(f)
                result.append({
                    "path":          str(f.relative_to(MEDIA_DIR())),
                    "full_path":     str(f),
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
    result.sort(key=lambda x: x["path"])
    with _LIB_LOCK:
        _LIB_CACHE    = result
        _LIB_CACHE_TS = time.time()
    return result

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
    """Return the next *n* playlist file names after the currently playing item."""
    playlist = cfg.playlist
    if not playlist:
        return []
    order = getattr(st, "playlist_order", None) or list(range(len(playlist)))
    idx   = getattr(st, "playlist_index", 0) or 0
    result = []
    for offset in range(1, n + 1):
        next_ord_idx = (idx + offset) % len(order)
        pl_idx = order[next_ord_idx]
        try:
            result.append(playlist[pl_idx].file_path.name)
        except (IndexError, AttributeError):
            pass
    return result


# =============================================================================
# REQUEST HANDLER
# =============================================================================
from hc.web_filemanager import _FileManagerMixin   # provides _get_files, _handle_file_op

class WebHandler(_FileManagerMixin, BaseHTTPRequestHandler):

    def log_message(self, *args: Any) -> None:
        pass  # suppress default access log

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

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data, default=str), "application/json")

    def _serve_static(self, url_path: str) -> None:
        """
        Serve a static file from <BASE_DIR>/static/ or BASE_DIR itself.
        Supports: .png .jpg .jpeg .gif .webp .svg .ico .css .js
        Place  resources/logo.png at <BASE_DIR>/ resources/logo.png  — it will be served as / resources/logo.png.
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
        name = url_path.lstrip("/")                     # e.g. " resources/logo.png" or "static/x.png"
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
            "/":                   lambda: self._send(200, _HTML, "text/html; charset=utf-8"),
            "/index.html":         lambda: self._send(200, _HTML, "text/html; charset=utf-8"),
            "/health":             self._get_health,
            "/api/streams":        self._get_streams,
            "/api/streams_config": self._get_streams_config,
            "/api/library":        self._get_library,
            "/api/subdirs":        self._get_subdirs,
            "/api/files":          lambda: self._get_files(qs),
            "/api/events":         self._get_events,
            "/api/holidays":       self._get_holidays,
            "/api/logs":           lambda: self._get_logs(qs),
            "/api/system_stats":   self._get_system_stats,
            "/api/stream_detail":  lambda: self._get_stream_detail(qs),
            "/api/stream_view":    lambda: self._get_stream_view(qs),
            "/api/urls_csv":               lambda: self._get_urls_csv(qs),
            "/api/mail_config":              self._get_mail_config,
            "/api/gmail_oauth2_status":      self._get_gmail_oauth2_status,
            "/api/microsoft_oauth2_status":  self._get_ms_oauth2_status,
            "/api/upload/status":            lambda: self._get_upload_status(qs),
        }

        handler = routes.get(path)
        if handler:
            try:
                handler()
            except Exception as exc:
                log.error("WebHandler GET %s: %s", path, exc)
                self._json({"error": "internal server error"}, 500)
        elif path.startswith("/static/") or path in ("/ resources/logo.png", "/favicon.ico"):
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
            resp, code = handle_upload_init(data)
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
            resp, code = handle_upload_chunk(raw_body, ct)
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
            resp, code = handle_upload_finalize(data)
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
                from hc.web_upload import _UPLOAD_MANAGER
                _UPLOAD_MANAGER.abort(sid)
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
                "current_file":   (
                    Path(cf).name
                    if (cf := (
                        st.current_file()
                        if callable(getattr(st, "current_file", None))
                        else getattr(st, "current_file", None)
                    )) else None
                ),
                # Next pending (not yet played) event for this stream.
                # Only populated when no oneshot is active; during oneshot,
                # current_file already shows the event file being played.
                "active_event":   next(
                    (ev.file_path.name for ev in mgr.events
                     if ev.stream_name == cfg.name and not ev.played),
                    None
                ) if not getattr(st, "oneshot_active", False) else None,
                # next 2 upcoming playlist items
                "next_in_queue":  _get_next_in_queue(st, cfg, n=2),
                # Compliance alert (v2)
                "compliance_enabled":       cfg.compliance_enabled,
                "compliance_alert":         getattr(st, "compliance_alert", None),
                "compliance_alert_enabled": getattr(cfg, "compliance_alert_enabled", True),
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

        buf = io.StringIO()
        writer = _csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        body = buf.getvalue().encode("utf-8")

        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"hydracast_urls_{ts}.csv"

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
        dirs = []
        for d in MEDIA_DIR().rglob("*"):
            if d.is_dir():
                rel = str(d.relative_to(MEDIA_DIR()))
                if rel:
                    dirs.append(rel)
        self._json({"dirs": sorted(set(dirs)), "root_label": str(MEDIA_DIR())})

    def _get_events(self) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json([])
            return
        now = datetime.now()
        result = []
        for ev in sorted(mgr.events, key=lambda e: e.play_at):
            diff = (ev.play_at - now).total_seconds()
            result.append({
                "event_id":      ev.event_id,
                "stream_name":   ev.stream_name,
                "file_name":     ev.file_path.name,
                "file_path":     str(ev.file_path),
                "play_at":       ev.play_at.strftime("%Y-%m-%d %H:%M:%S"),
                "play_at_iso":   ev.play_at.isoformat(),
                "seconds_until": round(diff),
                "post_action":   ev.post_action,
                "start_pos":     ev.start_pos if hasattr(ev, "start_pos") else "00:00:00",
                "end_pos":       ev.end_pos   if hasattr(ev, "end_pos")   else "",
                "played":        ev.played,
            })
        self._json(result)

    def _get_holidays(self) -> None:
        """Return Bangladesh public holidays for the current and next year."""
        try:
            import holidays as _hol
            year = datetime.now().year
            bd = _hol.Bangladesh(years=[year, year + 1])
            result = sorted(
                [{"date": str(d), "name": name} for d, name in bd.items()],
                key=lambda x: x["date"],
            )
            self._json(result)
        except ImportError:
            log.warning(
                "holidays package not installed — run: pip install holidays>=0.45"
            )
            self._json([])
        except Exception as exc:
            log.error("_get_holidays error: %s", exc)
            self._json([], 500)

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
        playlist = []
        for i, item in enumerate(cfg.playlist):
            playlist.append({
                "file":     item.file_path.name,
                "path":     str(item.file_path),
                "start":    item.start_position,
                "priority": item.priority,
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
        self._json({
            "name":        cfg.name,
            "status":      st.status.label,
            "rtsp_url":    cfg.rtsp_url_external,
            "hls_url":     cfg.hls_url if cfg.hls_enabled else "",
            "current_pos": st.current_pos,
            "duration":    st.duration,
            "progress":    st.progress,
        })

    def _get_mail_config(self) -> None:
        """Return the current mail_config.json contents (password redacted)."""
        from hc.constants import BASE_DIR
        import json as _json
        path = BASE_DIR() / "mail_config.json"
        try:
            if path.exists():
                cfg = _json.loads(path.read_text(encoding="utf-8"))
                # Redact the password so it never crosses the wire in plain text.
                if "password" in cfg and cfg["password"]:
                    cfg["password"] = "••••••••"
                # Tell the UI whether a Gmail token already exists
                from hc.mailer import get_oauth2_flow_status
                status = get_oauth2_flow_status()
                cfg["oauth2_token_exists"] = status["token_exists"]
                # Add Microsoft OAuth2 token status
                try:
                    from hc.mailer import get_microsoft_oauth2_status
                    ms_status = get_microsoft_oauth2_status(cfg)
                    cfg["ms_token_exists"] = ms_status.get("token_exists", False)
                except Exception:
                    cfg["ms_token_exists"] = False
                self._json(cfg)
            else:
                # Return template defaults so the form is pre-filled sensibly.
                self._json({
                    "enabled": False, "mode": "smtp",
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587, "use_tls": True,
                    "username": "", "password": "",
                    "from_addr": "", "to_addrs": [],
                    "on_error": True, "on_stop": True, "cooldown_secs": 300,
                    "ms_client_id": "", "ms_username": "",
                    "oauth2_token_exists": False, "ms_token_exists": False,
                })
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _get_gmail_oauth2_status(self) -> None:
        """Return the current OAuth2 flow status (polled by UI while auth is in progress)."""
        try:
            from hc.mailer import get_oauth2_flow_status
            self._json(get_oauth2_flow_status())
        except Exception as exc:
            self._json({"status": "error", "error": str(exc), "token_exists": False})

    def _get_ms_oauth2_status(self) -> None:
        """Return Microsoft OAuth2 device-code flow status and token presence."""
        try:
            from hc.constants import BASE_DIR
            import json as _json
            cfg: dict = {}
            try:
                cfg = _json.loads((BASE_DIR() / "mail_config.json").read_text(encoding="utf-8"))
            except Exception:
                pass
            from hc.mailer import get_microsoft_oauth2_status
            self._json(get_microsoft_oauth2_status(cfg))
        except Exception as exc:
            self._json({"status": "error", "error": str(exc), "token_exists": False})

    def _get_upload_status(self, qs: Dict[str, Any]) -> None:
        """GET /api/upload/status?session_id=X  — chunked upload progress."""
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
                if not (1024 <= new_port <= 65535):
                    raise ValueError(f"Port {new_port} out of range")
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
                # Playlist files (semicolon or newline separated)
                raw_files = str(data.get("files", "")).strip()
                if raw_files:
                    raw_files = raw_files.replace("\n", ";")
                    parsed = CSVManager.parse_files(raw_files)
                    if parsed:
                        cfg.playlist = parsed
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
                fp   = Path(file_path)
                safe = _safe_path(fp, MEDIA_DIR())
                if safe is None and not fp.exists():
                    raise ValueError("File not found or path outside media directory")
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
                if not (1024 <= port <= 65535):
                    raise ValueError(f"Port {port} out of range (1024-65535).")

                # Stream path — empty string means root mount (IP:Port/)
                stream_path = str(data.get("stream_path", "")).strip()

                # Playlist source: folder_source overrides file list
                folder_source_raw = str(data.get("folder_source") or "").strip()
                folder_source = None
                playlist: "List[PlaylistItem]" = []
                if folder_source_raw:
                    from hc.folder_scanner import scan_folder, SortMode
                    folder_source = Path(folder_source_raw)
                    if not folder_source.is_dir():
                        raise ValueError(f"Folder not found or not a directory: '{folder_source_raw}'")
                    playlist, warnings = scan_folder(folder_source, SortMode.ALPHA_FWD)
                    for w in warnings:
                        log.warning("create_stream folder scan: %s", w)
                    if not playlist:
                        raise ValueError(f"No supported media files found in '{folder_source_raw}'")
                else:
                    raw_files = str(data.get("files", "")).strip().replace("\n", ";")
                    playlist  = CSVManager.parse_files(raw_files)
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

        elif action == "fire_event_now":
            ev_id = str(data.get("event_id", "")).strip()
            if not ev_id:
                self._json({"ok": False, "msg": "Missing event_id"})
                return
            ok = mgr.fire_event_now(ev_id)
            self._json({"ok": ok, "msg": "Event fired" if ok else "Event not found or stream not running"})

        elif action == "delete_file":
            raw_path = str(data.get("path", "")).strip()
            if not raw_path:
                self._json({"ok": False, "msg": "Missing path"})
                return
            p    = Path(raw_path)
            safe = _safe_path(p, MEDIA_DIR())
            if safe is None or not safe.is_file():
                self._json({"ok": False, "msg": "File not in media dir or not found"})
                return
            try:
                safe.unlink()
                _invalidate_lib_cache()
                self._json({"ok": True, "msg": f"Deleted {safe.name}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "create_subdir":
            raw = str(data.get("name", "")).strip()
            if not raw or re.search(r'[/\\<>"|?*\x00]', raw) or ".." in raw:
                self._json({"ok": False, "msg": "Invalid folder name"})
                return
            target = MEDIA_DIR() / raw
            safe   = _safe_path(target, MEDIA_DIR())
            if safe is None:
                self._json({"ok": False, "msg": "Path traversal denied"})
                return
            try:
                safe.mkdir(parents=True, exist_ok=True)
                self._json({"ok": True, "msg": f"Created: {raw}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "save_mail_config":
            try:
                from hc.constants import BASE_DIR
                import json as _json
                mode      = str(data.get("mode", "smtp")).strip()
                to_addrs  = data.get("to_addrs", [])
                if not isinstance(to_addrs, list) or not to_addrs:
                    raise ValueError("to_addrs must be a non-empty list")
                smtp_port = int(data.get("smtp_port", 587))
                if not (1 <= smtp_port <= 65535):
                    raise ValueError(f"Invalid SMTP port: {smtp_port}")
                path = BASE_DIR() / "mail_config.json"
                # Preserve the stored password if the client sent the redaction placeholder
                password = str(data.get("password", ""))
                if password in ("••••••••", ""):
                    try:
                        existing = _json.loads(path.read_text(encoding="utf-8"))
                        password = existing.get("password", "")
                    except Exception:
                        password = ""
                cfg = {
                    "enabled":       bool(data.get("enabled", False)),
                    "mode":          mode,
                    "to_addrs":      [str(a).strip() for a in to_addrs if str(a).strip()],
                    "on_error":      bool(data.get("on_error", True)),
                    "on_stop":       bool(data.get("on_stop", True)),
                    "cooldown_secs": max(0, int(data.get("cooldown_secs", 300))),
                    # SMTP fields (kept even in OAuth2 mode so switching back works)
                    "smtp_host":     str(data.get("smtp_host", "")).strip(),
                    "smtp_port":     smtp_port,
                    "use_tls":       bool(data.get("use_tls", True)),
                    "username":      str(data.get("username", "")).strip(),
                    "password":      password,
                    "from_addr":     str(data.get("from_addr", "")).strip(),
                    # Microsoft OAuth2 fields
                    "ms_client_id":  str(data.get("ms_client_id", "")).strip(),
                    "ms_username":   str(data.get("ms_username", "")).strip(),
                }
                path.write_text(_json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
                log.info("mail_config.json updated via Web UI (mode=%s enabled=%s)", mode, cfg["enabled"])
                self._json({"ok": True, "msg": "mail_config.json saved"})
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

        elif action == "gmail_oauth2_start":
            try:
                from hc.mailer import start_gmail_oauth2_flow
                ok, msg = start_gmail_oauth2_flow()
                self._json({"ok": ok, "msg": msg})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "gmail_oauth2_revoke":
            try:
                from hc.mailer import revoke_gmail_token
                ok, msg = revoke_gmail_token()
                self._json({"ok": ok, "msg": msg})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "microsoft_oauth2_start":
            try:
                client_id = str(data.get("ms_client_id", "")).strip()
                if not client_id:
                    # Fall back to value already saved in mail_config.json
                    from hc.constants import BASE_DIR
                    import json as _json
                    try:
                        saved = _json.loads((BASE_DIR() / "mail_config.json").read_text("utf-8"))
                        client_id = saved.get("ms_client_id", "").strip()
                    except Exception:
                        pass
                if not client_id:
                    self._json({"ok": False, "msg": "Enter Application (Client) ID and save config first."})
                    return
                from hc.mailer import start_microsoft_oauth2_flow
                ok, instructions = start_microsoft_oauth2_flow(client_id)
                if ok:
                    from hc.mailer import _ms_flow_state  # type: ignore[attr-defined]
                    self._json({
                        "ok":              True,
                        "msg":             instructions,
                        "user_code":       _ms_flow_state.get("user_code", ""),
                        "verification_uri": _ms_flow_state.get("verification_uri", "https://microsoft.com/devicelogin"),
                    })
                else:
                    self._json({"ok": False, "msg": instructions})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "microsoft_oauth2_revoke":
            try:
                from hc.constants import BASE_DIR
                import json as _json
                cfg: dict = {}
                try:
                    cfg = _json.loads((BASE_DIR() / "mail_config.json").read_text("utf-8"))
                except Exception:
                    pass
                from hc.mailer import revoke_microsoft_token
                ok, msg = revoke_microsoft_token(cfg)
                self._json({"ok": ok, "msg": msg})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "backup":
            self._handle_backup(data)

        elif action == "restore":
            self._handle_restore(data)

        else:
            self._json({"ok": False, "msg": f"Unknown action: {action}"}, 404)

    # ── Multipart upload ─────────────────────────────────────────────────────
    def _handle_upload(self) -> None:
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > UPLOAD_MAX_BYTES:
                self._json({"ok": False, "msg": "File exceeds 10 GB limit"}, 413)
                return

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

            subdir      = re.sub(r'[/\\<>"|?*\x00]', '_', subdir)[:128]
            subdir      = re.sub(r'\.\.', '_', subdir)
            fname_clean = Path(file_name).name
            ext         = Path(fname_clean).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                self._json({"ok": False, "msg": f"Unsupported extension: {ext}"})
                return

            safe_name = re.sub(r'[^\w.\-]', '_', fname_clean)
            if not safe_name or safe_name.startswith('.'):
                self._json({"ok": False, "msg": "Invalid filename"})
                return

            dest_dir = (MEDIA_DIR() / subdir) if subdir else MEDIA_DIR()
            safe_dir = _safe_path(dest_dir, MEDIA_DIR())
            if safe_dir is None:
                self._json({"ok": False, "msg": "Invalid upload directory"})
                return
            safe_dir.mkdir(parents=True, exist_ok=True)

            dest     = safe_dir / safe_name
            tmp_path = dest.with_suffix(dest.suffix + ".tmp")
            try:
                tmp_path.write_bytes(file_bytes)
                tmp_path.rename(dest)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

            _invalidate_lib_cache()
            log.info("Upload saved: %s", dest)
            # ── Notify folder-source streams about the new file ──
            _notify_folder_upload(safe_dir)
            self._json({"ok": True, "msg": f"Saved: {safe_name}"})
        except Exception as exc:
            log.error("Upload error: %s", exc)
            self._json({"ok": False, "msg": f"Upload error: {exc}"}, 500)

    # ── Backup ───────────────────────────────────────────────────────────────
    def _handle_backup(self, include: Dict[str, Any]) -> None:
        """
        Build a plain-JSON .hc backup and send it as a downloadable file.
        *include* is a dict with boolean flags: streams, events, mail, resume.
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
                p = CONFIG_DIR() / "streams.json"
                try:
                    payload["streams"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else []
                except Exception:
                    payload["streams"] = []

            # ── Events ──────────────────────────────────────────────────────
            if include.get("events", True):
                p = CONFIG_DIR() / "events.json"
                try:
                    payload["events"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else []
                except Exception:
                    payload["events"] = []

            # ── Mail config (password redacted for safety) ───────────────────
            if include.get("mail", True):
                p = BASE_DIR() / "mail_config.json"
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
                p = BASE_DIR() / "resume_positions.json"
                try:
                    payload["resume_positions"] = _json.loads(
                        p.read_text(encoding="utf-8")) if p.exists() else {}
                except Exception:
                    payload["resume_positions"] = {}

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

            # ── Streams ─────────────────────────────────────────────────────
            if "streams" in payload:
                p = CONFIG_DIR() / "streams.json"
                p.write_text(
                    _json.dumps(payload["streams"], indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                restored.append("streams")
                log.info("restore: streams.json written (%d streams)",
                         len(payload["streams"]) if isinstance(payload["streams"], list) else 0)

            # ── Events ──────────────────────────────────────────────────────
            if "events" in payload:
                p = CONFIG_DIR() / "events.json"
                p.write_text(
                    _json.dumps(payload["events"], indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                restored.append("events")

            # ── Mail config (password intentionally absent — user must re-enter) ──
            if "mail_config" in payload:
                p = BASE_DIR() / "mail_config.json"
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

            # ── Resume positions ────────────────────────────────────────────
            if "resume_positions" in payload:
                p = BASE_DIR() / "resume_positions.json"
                p.write_text(
                    _json.dumps(payload["resume_positions"], indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                restored.append("resume_positions")

            # ── Reload manager state ─────────────────────────────────────────
            mgr = _WEB_MANAGER
            if mgr and "streams" in payload:
                try:
                    from hc.json_manager import JSONManager
                    new_configs = JSONManager.load()
                    mgr.reload_from_configs(new_configs)
                    log.info("restore: manager reloaded with %d stream(s)", len(new_configs))
                except AttributeError:
                    # reload_from_configs may not exist in older manager; do
                    # a best-effort restart_all instead.
                    for st in list(mgr.states):
                        try:
                            mgr.restart(st.config.name)
                        except Exception:
                            pass
                except Exception as exc:
                    log.warning("restore: manager reload failed: %s — streams not restarted", exc)

            if "events" in payload and mgr:
                try:
                    from hc.json_manager import JSONManager
                    mgr.events = JSONManager.load_events()
                except Exception:
                    pass

            log.info("restore: completed — restored: %s", ", ".join(restored))
            self._json({
                "ok":      True,
                "msg":     f"Restored: {', '.join(restored)}. Streams reloaded.",
                "restored": restored,
            })

        except Exception as exc:
            log.error("Restore error: %s", exc)
            self._json({"ok": False, "msg": f"Restore error: {exc}"}, 500)
