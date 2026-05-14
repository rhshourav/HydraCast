"""
hc/web_handler.py  —  WebHandler: the HTTP request handler for HydraCast.

Architecture
────────────
WebHandler is assembled from three mixins:

  _FileManagerMixin   (hc.web_filemanager)
      GET  /api/files          – directory listing
      POST file_rename / file_delete / file_delete_dir / file_move / file_copy

  _PostHandlersMixin  (hc.web_handlers_post, i.e. the file you have as
                       web_handler.py in your repo — rename it)
      POST _dispatch()  – all stream-control, config, event, mail, backup actions

  WebHandler          (this file)
      do_GET  – routes all GET /api/* and the SPA root
      do_POST – reads body, routes to upload or _dispatch
      _json   – send a JSON response
      log_message – suppress noisy access log

The GET handler also exposes the two new compliance fields added in models v6.1:
  compliance_resync_interval   (seconds, default 7200)
  compliance_drift_threshold   (seconds, default 30)
and adds a POST action:
  compliance_resync            – immediately seek a live stream to its correct
                                 compliance position (calls worker.compliance_resync)
"""
from __future__ import annotations

import json
import logging
import time as _time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from hc.constants import APP_VER, MEDIA_DIR, SUPPORTED_EXTS
from hc.utils import _safe_path
from hc.web_filemanager import _FileManagerMixin
from hc.web_handlers_post import _PostHandlersMixin

log = logging.getLogger(__name__)

# Security headers applied to every response
_SEC_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "same-origin",
}

# Manager reference – set externally via:  import hc.web; hc.web._WEB_MANAGER = mgr
_WEB_MANAGER: Any = None

# Flat library cache (read/written by _get_library / _invalidate_lib_cache)
_lib_cache:     Any   = None
_lib_cache_ts:  float = 0.0
_LIB_CACHE_TTL: float = 30.0

# Global log buffer – set by hydracast.py after startup
_GLOG: Any = None


# =============================================================================
# WebHandler
# =============================================================================

class WebHandler(_FileManagerMixin, _PostHandlersMixin, BaseHTTPRequestHandler):
    """HTTP request handler for the HydraCast Web UI."""

    # ── Boilerplate ───────────────────────────────────────────────────────────

    def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore[override]
        """Suppress the default per-request stdout log."""
        pass

    def _json(self, obj: Any, code: int = 200) -> None:
        """Serialise *obj* to JSON and send it."""
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in _SEC_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── OPTIONS (CORS pre-flight) ─────────────────────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # =========================================================================
    # GET
    # =========================================================================

    def do_GET(self) -> None:  # noqa: C901
        from hc.web import _WEB_MANAGER, _SEC_HEADERS as _WS  # type: ignore
        from hc.web_html import _HTML  # type: ignore

        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"
        qs     = parse_qs(parsed.query)

        # ── SPA root ──────────────────────────────────────────────────────────
        if path in ("/", "/index.html"):
            body = _HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for k, v in _SEC_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        mgr = _WEB_MANAGER

        # ── /api/streams  (live status) ───────────────────────────────────────
        if path == "/api/streams":
            if not mgr:
                self._json([])
                return
            out = []
            for st in mgr.states:
                cfg = st.config
                alert = None
                with st._lock:
                    alert = st.compliance_alert
                out.append({
                    "name":                     cfg.name,
                    "port":                     cfg.port,
                    "status":                   st.status.label,
                    "progress":                 round(st.progress, 1),
                    "current_pos":              st.format_pos(),
                    "duration":                 round(st.duration, 1),
                    "fps":                      round(st.fps, 1),
                    "bitrate":                  st.bitrate,
                    "speed":                    st.speed,
                    "error_msg":                st.error_msg,
                    "loop_count":               st.loop_count,
                    "restart_count":            st.restart_count,
                    "playlist_index":           st.playlist_index,
                    "current_file":             (st.current_file() or Path("")).name,
                    "rtsp_url":                 cfg.rtsp_url_external,
                    "hls_url":                  cfg.hls_url if cfg.hls_enabled else "",
                    "weekdays":                 cfg.weekdays_display(),
                    "enabled":                  cfg.enabled,
                    "compliance_enabled":       cfg.compliance_enabled,
                    "compliance_alert":         alert,
                    "compliance_alert_enabled": cfg.compliance_alert_enabled,
                    "oneshot_active":           st.oneshot_active,
                })
            self._json(out)
            return

        # ── /api/streams_config  (config editor data) ─────────────────────────
        if path == "/api/streams_config":
            if not mgr:
                self._json([])
                return
            out = []
            for st in mgr.states:
                cfg = st.config
                out.append({
                    "name":                       cfg.name,
                    "port":                       cfg.port,
                    "stream_path":                cfg.stream_path,
                    "video_bitrate":              cfg.video_bitrate,
                    "audio_bitrate":              cfg.audio_bitrate,
                    "shuffle":                    cfg.shuffle,
                    "enabled":                    cfg.enabled,
                    "hls_enabled":                cfg.hls_enabled,
                    "weekdays":                   cfg.weekdays_display(),
                    "folder_source":              str(cfg.folder_source) if cfg.folder_source else "",
                    "files":                      ";".join(
                                                      str(it.file_path)
                                                      for it in cfg.sorted_playlist()
                                                  ),
                    "playlist_count":             len(cfg.playlist),
                    "compliance_enabled":         cfg.compliance_enabled,
                    "compliance_start":           cfg.compliance_start,
                    "compliance_loop":            cfg.compliance_loop,
                    "compliance_alert_enabled":   cfg.compliance_alert_enabled,
                    # ── new in v6.1 ──────────────────────────────────────────
                    "compliance_resync_interval": cfg.compliance_resync_interval,
                    "compliance_drift_threshold": cfg.compliance_drift_threshold,
                })
            self._json(out)
            return

        # ── /api/files  (file manager) ────────────────────────────────────────
        if path == "/api/files":
            self._get_files(qs)
            return

        # ── /api/library  (flat media list for dropdowns) ────────────────────
        if path == "/api/library":
            self._get_library()
            return

        # ── /api/events ───────────────────────────────────────────────────────
        if path == "/api/events":
            if not mgr:
                self._json([])
                return
            now = _time.time()
            import datetime as _dt
            out = []
            for ev in sorted(mgr.events, key=lambda e: e.play_at):
                out.append({
                    "event_id":    ev.event_id,
                    "stream_name": ev.stream_name,
                    "file_path":   str(ev.file_path),
                    "file_name":   ev.file_path.name,
                    "play_at":     ev.play_at.isoformat(timespec="seconds"),
                    "post_action": ev.post_action,
                    "played":      ev.played,
                    "start_pos":   ev.start_pos,
                    "in_seconds":  max(0, (ev.play_at - _dt.datetime.now()).total_seconds()),
                })
            self._json(out)
            return

        # ── /api/log ──────────────────────────────────────────────────────────
        if path == "/api/log":
            from hc.web import _GLOG  # type: ignore
            level  = qs.get("level", ["ALL"])[0].upper()
            stream = qs.get("stream", [None])[0]
            n      = int(qs.get("n", ["500"])[0])
            entries = _GLOG.filtered(level=level, stream=stream, n=n) if _GLOG else []
            self._json([{"msg": m, "level": lv} for m, lv in entries])
            return

        # ── /api/mail_config ──────────────────────────────────────────────────
        if path == "/api/mail_config":
            self._get_mail_config()
            return

        # ── /api/thumbnail ────────────────────────────────────────────────────
        if path == "/api/thumbnail":
            self._get_thumbnail(qs)
            return

        # ── /api/version ──────────────────────────────────────────────────────
        if path == "/api/version":
            self._json({"version": APP_VER})
            return

        # ── 404 ───────────────────────────────────────────────────────────────
        self._json({"error": f"Not found: {path}"}, 404)

    # =========================================================================
    # Auxiliary GET helpers
    # =========================================================================

    def _get_library(self) -> None:
        """Return flat list of all media files in MEDIA_DIR for dropdowns."""
        from hc.web import _lib_cache, _lib_cache_ts, _LIB_CACHE_TTL  # type: ignore
        import hc.web as _web_mod  # type: ignore

        try:
            now = _time.time()
            if _lib_cache and (now - _lib_cache_ts) < _LIB_CACHE_TTL:
                self._json(_lib_cache)
                return

            media = MEDIA_DIR()
            items: List[Dict[str, Any]] = []
            for f in sorted(media.rglob("*")):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in SUPPORTED_EXTS:
                    continue
                try:
                    size_b = f.stat().st_size
                    size_s = _fmt_size(size_b)
                except OSError:
                    size_s = "?"
                items.append({
                    "path":  str(f.relative_to(media)),
                    "name":  f.name,
                    "size":  size_s,
                })

            _web_mod._lib_cache    = items
            _web_mod._lib_cache_ts = now
            self._json(items)
        except Exception as exc:
            log.error("_get_library error: %s", exc)
            self._json({"error": str(exc)}, 500)

    def _get_mail_config(self) -> None:
        """Return mail_config.json (password masked)."""
        import json as _json
        from hc.constants import BASE_DIR
        try:
            p = BASE_DIR() / "mail_config.json"
            if not p.exists():
                self._json({})
                return
            cfg = _json.loads(p.read_text(encoding="utf-8"))
            if cfg.get("password"):
                cfg["password"] = "••••••••"
            self._json(cfg)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _get_thumbnail(self, qs: Dict) -> None:
        """Return a PNG thumbnail for a media file."""
        from hc.worker import grab_thumbnail
        raw = qs.get("path", [""])[0].strip()
        if not raw:
            self._json({"error": "Missing path"}, 400)
            return
        media = MEDIA_DIR()
        safe  = _safe_path(media / raw, media)
        if safe is None or not safe.is_file():
            self._json({"error": "File not found"}, 404)
            return
        try:
            seek = float(qs.get("seek", ["5"])[0])
        except ValueError:
            seek = 5.0
        data = grab_thumbnail(safe, seek)
        if data is None:
            self._json({"error": "Thumbnail generation failed"}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=60")
        for k, v in _SEC_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # =========================================================================
    # POST
    # =========================================================================

    def do_POST(self) -> None:  # noqa: C901
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")

        # ── /api/upload ───────────────────────────────────────────────────────
        if path == "/api/upload":
            self._handle_upload()
            return

        # ── /api/backup ───────────────────────────────────────────────────────
        if path == "/api/backup":
            try:
                cl   = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(cl) if cl else b"{}"
                data = json.loads(body) if body.strip() else {}
            except Exception:
                data = {}
            self._handle_backup(data)
            return

        # ── /api/restore ──────────────────────────────────────────────────────
        if path == "/api/restore":
            try:
                cl      = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(cl))
            except Exception as exc:
                self._json({"ok": False, "msg": f"Invalid JSON: {exc}"}, 400)
                return
            self._handle_restore(payload)
            return

        # ── All other POSTs go through _dispatch ─────────────────────────────
        if path.startswith("/api/"):
            try:
                cl   = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(cl) if cl else b"{}"
                data: Dict[str, Any] = json.loads(body) if body.strip() else {}
            except json.JSONDecodeError as exc:
                self._json({"ok": False, "msg": f"Invalid JSON: {exc}"}, 400)
                return
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)}, 400)
                return

            action = data.get("action", "") or path.lstrip("/api/")
            # Also accept action in the URL path itself: POST /api/<action>
            if not action:
                action = path[5:].lstrip("/")

            # ── compliance_resync (new v6.1 action) ───────────────────────────
            if action == "compliance_resync":
                self._do_compliance_resync(data)
                return

            self._dispatch(action, data)
            return

        self._json({"error": "Not found"}, 404)

    # =========================================================================
    # compliance_resync POST action
    # =========================================================================

    def _do_compliance_resync(self, data: Dict[str, Any]) -> None:
        """
        POST {"action": "compliance_resync", "name": "<stream>"}

        Immediately seeks a live compliance stream to its correct broadcast
        position (calls StreamWorker.compliance_resync in a daemon thread).
        """
        from hc.web import _WEB_MANAGER  # type: ignore

        mgr = _WEB_MANAGER
        if not mgr:
            self._json({"ok": False, "msg": "Manager not ready"})
            return

        name = str(data.get("name", "")).strip()
        if not name:
            self._json({"ok": False, "msg": "Missing stream name"})
            return

        st = mgr.get_state(name)
        if not st:
            self._json({"ok": False, "msg": f"Stream '{name}' not found"})
            return

        if not st.config.compliance_enabled:
            self._json({"ok": False, "msg": "Compliance mode is not enabled for this stream"})
            return

        from hc.models import StreamStatus
        if st.status != StreamStatus.LIVE:
            self._json({"ok": False, "msg": f"Stream is not live (status: {st.status.label})"})
            return

        worker = mgr.get_worker(name)
        if not worker:
            self._json({"ok": False, "msg": "Worker not found for this stream"})
            return

        import threading as _thr
        _thr.Thread(
            target=worker.compliance_resync,
            daemon=True,
            name=f"comp-resync-{name}",
        ).start()

        self._json({"ok": True, "msg": f"Compliance resync initiated for '{name}'"})


# ── Utility used by _get_library ─────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ---------------------------------------------------------------------------
# Module-level helpers — exported by hc.web and imported by web_handlers_post
# ---------------------------------------------------------------------------

def _get_library_cached():
    """Return the current flat library cache list, or [] if not yet built."""
    import hc.web_handler as _self
    return _self._lib_cache or []


def _invalidate_lib_cache() -> None:
    """Bust the flat media-library cache so the next GET /api/library rebuilds it."""
    import hc.web_handler as _self
    _self._lib_cache    = None
    _self._lib_cache_ts = 0.0


def _notify_folder_upload(folder) -> None:
    """Called after a successful file upload; clears the library cache."""
    _invalidate_lib_cache()


def _get_next_in_queue():
    """Return the next queued playback item, or None (stub — extend as needed)."""
    return None
