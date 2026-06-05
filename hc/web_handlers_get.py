"""
hc/web_handlers_get.py  —  All HTTP GET handler methods for WebHandler.

Mixed into WebHandler in web.py.  Every method here is a bound method
that can call self._json() / self._send() and read _WEB_MANAGER.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from hc.constants import APP_VER, BASE_DIR, CONFIG_DIR, MEDIA_DIR, SUPPORTED_EXTS, get_web_port, get_auto_start
from hc.utils import _fmt_duration, _fmt_size, _local_ip

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HLS proxy URL helper (imported from web_handler to keep the definition DRY)
# ---------------------------------------------------------------------------
def _hls_proxy_url(cfg) -> str:
    """
    Return the proxied HLS URL for use in the Web UI.

    Routes all HLS traffic through /hls/<port>/<stream_path>/index.m3u8 on
    the Web UI's own HTTPS origin so the browser never makes a plain-HTTP
    mixed-content request to MediaMTX's HLS port directly.
    """
    if not cfg.hls_enabled:
        return ""
    spath = (cfg.rtsp_path or cfg.stream_path or "stream").strip("/")
    return f"/hls/{cfg.hls_port}/{spath}/index.m3u8"



def _clean_error_msg(msg):
    """Convert raw FFmpeg stderr into a short human-readable string."""
    if not msg:
        return None
    _PATTERNS = [
        ("Broken pipe",                        "Stream ended (broken pipe) — auto-restarting"),
        ("Connection refused",                 "RTSP connection refused — MediaMTX not ready"),
        ("Connection timed out",               "RTSP connection timed out"),
        ("No such file",                       "Media file not found"),
        ("Invalid data",                       "Invalid media file or codec error"),
        ("Error muxing",                       "Muxer error — stream restarting"),
        ("Task finished with error code: -32", "Broken pipe — stream restarting"),
        ("Error opening",                      "Could not open media file"),
        ("Conversion failed",                  "FFmpeg conversion failed"),
        ("Out of memory",                      "Out of memory"),
    ]
    for fragment, friendly in _PATTERNS:
        if fragment.lower() in msg.lower():
            return friendly
    import re as _re
    cleaned = _re.sub(r'\[[\w#/.:@ 0-9]+\]\s*', '', msg)
    lines = [l.strip() for l in cleaned.strip().splitlines() if l.strip()]
    return (lines[-1][:120] if lines else "FFmpeg error (see logs)")


# ---------------------------------------------------------------------------
# Library cache (module-level so it survives handler instantiation cycles)
# ---------------------------------------------------------------------------
_LIB_CACHE:    Optional[List[Dict[str, Any]]] = None
_LIB_CACHE_TS: float = 0.0

import threading as _threading
_LIB_LOCK = _threading.Lock()


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


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class _GetHandlersMixin:
    """Mixed into WebHandler — all HTTP GET route handlers."""

    def _get_health(self) -> None:
        from hc.web import _WEB_MANAGER
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
        from hc.web import _WEB_MANAGER
        mgr = _WEB_MANAGER
        if not mgr:
            self._json([])
            return
        result = []
        for st in mgr.states:
            cfg = st.config
            # Determine the currently-playing file name for display
            cur_file: Optional[str] = None
            active_event_name: Optional[str] = None
            if st.oneshot_active:
                # During a one-shot event the playlist index still points to
                # the compliance/playlist file; the event file is stored on
                # the active_oneshot_event attribute set in play_oneshot().
                ev = getattr(st, "active_oneshot_event", None)
                if ev is not None:
                    active_event_name = ev.file_path.name
            else:
                cf = st.current_file()
                if cf is not None:
                    cur_file = cf.name

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
                "hls_url":        _hls_proxy_url(cfg),
                "shuffle":        cfg.shuffle,
                "playlist_count": len(cfg.playlist),
                "enabled":        cfg.enabled,
                "error_msg":      _clean_error_msg(st.error_msg) if st.status.label != "LIVE" else None,
                "loop_count":     st.loop_count,
                "restart_count":  st.restart_count,
                "bitrate":        st.bitrate,
                "speed":          st.speed,
                "app_ver":        APP_VER,
                # ── Oneshot / event state ─────────────────────────────────
                "oneshot_active": st.oneshot_active,
                "active_event":   active_event_name,
                "current_file":   cur_file,
                # Compliance alert (non-None = show banner in UI)
                "compliance_alert": st.compliance_alert,
                # ── Hybrid source switching (graceful fallback for older models) ──
                "source_mode":    getattr(cfg, "source_mode",   "file"),
                "active_source":  getattr(st,  "active_source", "file"),
            })
        self._json(result)

    def _get_streams_config(self) -> None:
        from hc.web import _WEB_MANAGER
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
                "compliance_enabled":   cfg.compliance_enabled,
                "compliance_start":     cfg.compliance_start,
                "compliance_loop":      cfg.compliance_loop,
                # ── Hybrid source switching (graceful fallback for older models) ──
                "source_mode":    getattr(cfg, "source_mode",    "file"),
                "camera_id":      getattr(cfg, "camera_id",      None),
                "camera_windows": getattr(cfg, "camera_windows", []),
            })
        self._json(result)

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
        from hc.web import _WEB_MANAGER
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
                "played":        ev.played,
            })
        self._json(result)

    def _get_logs(self, qs: Dict[str, Any]) -> None:
        from hc.web import _WEB_MANAGER
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
                "auto_start":   get_auto_start(),
            })
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _get_stream_detail(self, qs: Dict[str, Any]) -> None:
        from hc.web import _WEB_MANAGER
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
            "hls_url":       _hls_proxy_url(cfg),
            "weekdays":      cfg.weekdays_display(),
            "status":        st.status.label,
            "progress":      st.progress,
            "current_pos":   st.current_pos,
            "duration":      st.duration,
            "position":      st.format_pos(),
            "fps":           st.fps,
            "loop_count":    st.loop_count,
            "restart_count": st.restart_count,
            "error_msg":     _clean_error_msg(st.error_msg) if st.status.label != "LIVE" else None,
            "playlist":      playlist,
            "log":           log_snap,
            "started_at":    st.started_at.isoformat() if st.started_at else None,
        })

    def _get_stream_view(self, qs: Dict[str, Any]) -> None:
        from hc.web import _WEB_MANAGER
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
        # RTSP-first: when HLS is not enabled, viewer URL should default to RTSP
        hls_url = _hls_proxy_url(cfg)
        self._json({
            "name":          cfg.name,
            "status":        st.status.label,
            "rtsp_url":      cfg.rtsp_url_external,
            "hls_url":       hls_url,
            "current_pos":   st.current_pos,
            "duration":      st.duration,
            "progress":      st.progress,
            # ── Hybrid source switching (graceful fallback for older models) ──
            "source_mode":   getattr(cfg, "source_mode",   "file"),
            "active_source": getattr(st,  "active_source", "file"),
        })

    def _get_cameras(self) -> None:
        """GET /api/cameras — returns the full camera registry (passwords masked).

        BUG FIX: JSONManager.load_cameras() may not exist in older builds.
        Use getattr() to detect it safely and return an empty list when absent,
        rather than crashing with AttributeError → 500 → "Failed to fetch".
        """
        try:
            from hc.json_manager import JSONManager
            load_fn = getattr(JSONManager, "load_cameras", None)
            cameras = load_fn() if load_fn is not None else []
            result = []
            for cam in cameras:
                result.append({
                    "camera_id":   cam.camera_id,
                    "name":        cam.name,
                    "protocol":    cam.protocol,
                    "host":        cam.host,
                    "port":        cam.port,
                    "path":        cam.path,
                    "username":    cam.username,
                    # Never send the real password to the browser — mask it
                    "password":    "••••••••" if cam.password else "",
                    "source_type": cam.source_type,
                    "enabled":     cam.enabled,
                    "notes":       cam.notes,
                    "url_masked":  cam.url_masked,
                    "url_display": cam.url_masked,
                })
            self._json(result)
        except Exception as exc:
            log.error("_get_cameras error: %s", exc)
            self._json({"error": str(exc)}, 500)

    def _get_holidays(self, qs: Dict[str, Any]) -> None:
        """GET /api/holidays — delegate to _CalendarHandlersMixin with safe fallback.

        BUG FIX: If the calendar mixin's _get_holidays crashes (missing holidays
        package, bad country code, etc.) the UI spins forever on "loading".
        This override calls super() and catches any exception, returning an empty
        but valid payload so the UI renders instead of hanging.
        """
        try:
            # _CalendarHandlersMixin is later in the MRO; call it via super().
            super()._get_holidays(qs)
        except AttributeError:
            # Calendar mixin not present in this build — return safe empty payload.
            year = datetime.now().year
            self._json({
                "holidays": [],
                "custom":   [],
                "country":  "",
                "year":     year,
            })
        except Exception as exc:
            log.error("_get_holidays error: %s", exc)
            year = datetime.now().year
            self._json({
                "holidays": [],
                "custom":   [],
                "country":  "",
                "year":     year,
                "error":    str(exc),
            })

    def _get_mail_config(self) -> None:
        import json as _json
        # mail_config.hcf lives in CONFIG_DIR (which may be %APPDATA%\HydraCast\config
        # when the exe is installed under Program Files).  Never use BASE_DIR here.
        path = CONFIG_DIR() / "mail_config.hcf"
        try:
            if path.exists():
                cfg = _json.loads(path.read_text(encoding="utf-8"))
                # Mask secrets before sending to the browser
                if "client_secret" in cfg and cfg["client_secret"]:
                    cfg["client_secret"] = "••••••••"
                if "password" in cfg and cfg["password"]:
                    cfg["password"] = "••••••••"
                # Optional: OAuth2 status (functions may not exist in all builds)
                try:
                    from hc.mailer import get_oauth2_flow_status
                    status = get_oauth2_flow_status()
                    cfg["oauth2_token_exists"] = status["token_exists"]
                except (ImportError, AttributeError):
                    cfg["oauth2_token_exists"] = False
                try:
                    from hc.mailer import get_microsoft_oauth2_status
                    ms_status = get_microsoft_oauth2_status(cfg)
                    cfg["ms_token_exists"] = ms_status.get("token_exists", False)
                except (ImportError, AttributeError):
                    cfg["ms_token_exists"] = False
                self._json(cfg)
            else:
                self._json({
                    "enabled": False,
                    "tenant_id": "", "client_id": "", "client_secret": "",
                    "from_addr": "", "to_addrs": [],
                    "on_error": True, "on_stop": True, "cooldown_secs": 300,
                    "oauth2_token_exists": False, "ms_token_exists": False,
                })
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _get_gmail_oauth2_status(self) -> None:
        try:
            from hc.mailer import get_oauth2_flow_status
            self._json(get_oauth2_flow_status())
        except (ImportError, AttributeError):
            self._json({"status": "unsupported", "token_exists": False})
        except Exception as exc:
            self._json({"status": "error", "error": str(exc), "token_exists": False})

    def _get_ms_oauth2_status(self) -> None:
        try:
            import json as _json
            cfg: dict = {}
            try:
                # Use CONFIG_DIR — never BASE_DIR — so this works under Program Files.
                cfg = _json.loads(
                    (CONFIG_DIR() / "mail_config.hcf").read_text(encoding="utf-8")
                )
            except Exception:
                pass
            from hc.mailer import get_microsoft_oauth2_status
            self._json(get_microsoft_oauth2_status(cfg))
        except (ImportError, AttributeError):
            self._json({"status": "unsupported", "token_exists": False})
        except Exception as exc:
            self._json({"status": "error", "error": str(exc), "token_exists": False})
