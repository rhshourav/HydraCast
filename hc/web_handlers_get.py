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

from hc.constants import APP_VER, BASE_DIR, MEDIA_DIR, SUPPORTED_EXTS, get_web_port
from hc.utils import _fmt_duration, _fmt_size, _local_ip

log = logging.getLogger(__name__)


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
                "hls_url":        cfg.hls_url if cfg.hls_enabled else "",
                "shuffle":        cfg.shuffle,
                "playlist_count": len(cfg.playlist),
                "enabled":        cfg.enabled,
                "error_msg":      st.error_msg,
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
        import json as _json
        path = BASE_DIR() / "mail_config.json"
        try:
            if path.exists():
                cfg = _json.loads(path.read_text(encoding="utf-8"))
                if "password" in cfg and cfg["password"]:
                    cfg["password"] = "••••••••"
                from hc.mailer import get_oauth2_flow_status
                status = get_oauth2_flow_status()
                cfg["oauth2_token_exists"] = status["token_exists"]
                try:
                    from hc.mailer import get_microsoft_oauth2_status
                    ms_status = get_microsoft_oauth2_status(cfg)
                    cfg["ms_token_exists"] = ms_status.get("token_exists", False)
                except Exception:
                    cfg["ms_token_exists"] = False
                self._json(cfg)
            else:
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
        try:
            from hc.mailer import get_oauth2_flow_status
            self._json(get_oauth2_flow_status())
        except Exception as exc:
            self._json({"status": "error", "error": str(exc), "token_exists": False})

    def _get_ms_oauth2_status(self) -> None:
        try:
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
