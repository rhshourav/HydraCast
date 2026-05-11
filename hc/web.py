"""
hc/web.py  —  Web server, request handler, and embedded HTML UI (v5.0.1).

Fixes (v5.0.1):
  • Web port is now read lazily (get_web_port() call) so the header/banner
    always displays the correct port even when --web-port overrides the default.
  • SO_REUSEADDR set before HTTPServer.server_bind() via allow_reuse_address.
  • Upload handler streams the file directly to disk instead of buffering the
    entire multipart body in RAM — safe for 10 GB uploads.
  • Media library scanning is cached (60 s TTL) to avoid blocking every GET.
  • clearPlayed JS helper sends a single batch DELETE instead of N sequential
    awaits.
  • Minor: tightened Content-Security-Policy, removed unused imports.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

import psutil

from hc.constants import (
    APP_VER, BASE_DIR, MEDIA_DIR, SUPPORTED_EXTS, UPLOAD_MAX_BYTES,
    get_web_port,
)
from hc.csv_manager import CSVManager
from hc.models import OneShotEvent, PlaylistItem, StreamConfig, StreamStatus
from hc.utils import _fmt_duration, _fmt_size, _local_ip, _safe_path
from hc.worker import grab_thumbnail, probe_metadata

# ── Module-level manager reference (set by hydracast.py) ─────────────────────
_WEB_MANAGER: Optional[Any] = None   # StreamManager

# ── Library cache ─────────────────────────────────────────────────────────────
_LIB_CACHE:     Optional[List[Dict[str, Any]]] = None
_LIB_CACHE_TS:  float = 0.0
_LIB_CACHE_TTL: float = 60.0          # seconds
_LIB_LOCK = threading.Lock()


def _get_library_cached() -> List[Dict[str, Any]]:
    """Return a cached media-library scan, refreshing at most every 60 s."""
    global _LIB_CACHE, _LIB_CACHE_TS
    with _LIB_LOCK:
        if _LIB_CACHE is not None and (time.time() - _LIB_CACHE_TS) < _LIB_CACHE_TTL:
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
        _LIB_CACHE    = None
        _LIB_CACHE_TS = 0.0


# =============================================================================
# SECURITY HEADERS
# =============================================================================
_SEC_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options":  "nosniff",
    "X-Frame-Options":         "SAMEORIGIN",
    "X-XSS-Protection":        "1; mode=block",
    "Referrer-Policy":         "strict-origin",
    "Cache-Control":           "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    ),
}


# =============================================================================
# HTML PAGE  —  Full embedded UI
# =============================================================================
_HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HydraCast — Stream Manager</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root{
  --bg:#03070d;--bg2:#060c14;--bg3:#0a121d;--bg4:#0f1c2a;--bg5:#162435;
  --border:#162030;--border2:#1e3040;--text:#ddeeff;--muted:#4a6a88;--faint:#0c1824;
  --green:#39e07a;--red:#ff5a6e;--yellow:#f7c35f;--blue:#3eb8fa;--purple:#a87efa;
  --cyan:#1ee8cc;--orange:#ff8a4c;--teal:#1ecfc7;--pink:#f06aaa;
  --green-g:rgba(57,224,122,.07);--red-g:rgba(255,90,110,.07);
  --blue-g:rgba(62,184,250,.07);--yellow-g:rgba(247,195,95,.07);--purple-g:rgba(168,126,250,.07);
  --r:10px;--rs:6px;--rxs:4px;
  --font:'Syne',system-ui,sans-serif;--mono:'IBM Plex Mono','JetBrains Mono',monospace;
  --shadow:0 8px 32px rgba(0,0,0,.6);--glow-b:0 0 24px rgba(62,184,250,.18);--glow-g:0 0 24px rgba(57,224,122,.18);
}
[data-theme="light"]{
  --bg:#f0f5fb;--bg2:#ffffff;--bg3:#e8eef7;--bg4:#dce5f0;--bg5:#ccd6e8;
  --border:#bfcfdf;--border2:#a8bdd0;--text:#0a1928;--muted:#5878a0;--faint:#e0eaf5;
  --green:#1aaa55;--red:#d83050;--yellow:#b87a00;--blue:#0a7fd4;--purple:#6840c0;
  --cyan:#0898a8;--orange:#c05818;--teal:#088890;--pink:#b03870;
  --green-g:rgba(26,170,85,.1);--red-g:rgba(216,48,80,.08);--blue-g:rgba(10,127,212,.08);
  --yellow-g:rgba(184,122,0,.08);--purple-g:rgba(104,64,192,.08);
  --shadow:0 2px 16px rgba(10,30,70,.1);--glow-b:0 0 12px rgba(10,127,212,.12);--glow-g:0 0 12px rgba(26,170,85,.12);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  background:var(--bg);color:var(--text);font:14px/1.6 var(--font);
  min-height:100vh;overflow-x:hidden;transition:background .35s,color .2s;
  background-image:
    radial-gradient(ellipse 80% 50% at 100% 0%,rgba(62,184,250,.05) 0%,transparent 55%),
    radial-gradient(ellipse 50% 70% at 0% 100%,rgba(168,126,250,.04) 0%,transparent 55%);
}
[data-theme="light"] body{
  background-image:
    radial-gradient(ellipse 80% 50% at 100% 0%,rgba(10,127,212,.04) 0%,transparent 60%),
    radial-gradient(ellipse 50% 70% at 0% 100%,rgba(104,64,192,.03) 0%,transparent 60%);
}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg2)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--muted)}

/* ── HEADER ─────────────────────────────────────────────── */
header{
  height:58px;background:rgba(6,12,20,.92);backdrop-filter:blur(24px);
  border-bottom:1px solid var(--border2);
  display:flex;align-items:center;gap:16px;padding:0 26px;
  position:sticky;top:0;z-index:100;
  box-shadow:0 1px 0 rgba(62,184,250,.06),0 8px 32px rgba(0,0,0,.5);
}
[data-theme="light"] header{background:rgba(255,255,255,.94);box-shadow:0 1px 0 rgba(10,127,212,.08),0 4px 20px rgba(10,30,80,.1);}
.logo-wrap{display:flex;align-items:center;gap:10px;text-decoration:none}
.logo-badge{
  width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#1cb8e0,#4a7efa);font-size:18px;font-weight:800;color:#fff;
  box-shadow:0 0 12px rgba(62,184,250,.4);
}
.logo-name{font-weight:800;font-size:17px;letter-spacing:.04em;
  background:linear-gradient(90deg,var(--blue),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.logo-ver{font-size:10px;color:var(--muted);background:var(--bg3);border:1px solid var(--border);
  padding:1px 6px;border-radius:99px;font-family:var(--mono);align-self:flex-start;margin-top:4px;}
.hdr-stats{display:flex;gap:20px;margin-left:auto;align-items:center}
.hstat{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--muted)}
.hstat strong{color:var(--text);font-family:var(--mono)}
.hdr-time{font-family:var(--mono);font-size:12px;color:var(--muted);min-width:60px;text-align:right}
.hdr-acts{display:flex;gap:6px}
/* web-port pill in header */
.hdr-webport{font-family:var(--mono);font-size:11px;color:var(--cyan);
  background:rgba(30,232,204,.07);border:1px solid rgba(30,232,204,.2);
  padding:2px 8px;border-radius:99px;white-space:nowrap;}

/* ── NAVIGATION ─────────────────────────────────────────── */
nav{
  display:flex;gap:4px;padding:14px 26px 0;background:var(--bg);
  border-bottom:1px solid var(--border);position:sticky;top:58px;z-index:90;
  backdrop-filter:blur(12px);overflow-x:auto;
}
nav button{
  background:none;border:none;color:var(--muted);cursor:pointer;
  font:600 13px/1 var(--font);padding:9px 18px;border-radius:var(--rs) var(--rs) 0 0;
  border:1px solid transparent;border-bottom:none;transition:all .18s;
}
nav button:hover{color:var(--text);background:var(--bg3)}
nav button.active{color:var(--blue);background:var(--bg2);border-color:var(--border2);margin-bottom:-1px;padding-bottom:10px}

/* ── CONTAINER / PANELS ─────────────────────────────────── */
.container{max-width:1600px;margin:0 auto;padding:22px 26px 60px}
.tab-content{display:none}.tab-content.active{display:block}
.panel{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);margin-bottom:18px;overflow:hidden}
.panel-hdr{
  display:flex;align-items:center;gap:10px;padding:12px 18px;
  background:var(--bg3);border-bottom:1px solid var(--border);
}
.panel-title{font-weight:700;font-size:15px}
.panel-body{padding:18px}
.section-label{font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--muted);text-transform:uppercase;margin-bottom:8px}

/* ── BUTTONS ─────────────────────────────────────────────── */
.btn{
  background:var(--bg4);border:1px solid var(--border2);color:var(--text);cursor:pointer;
  font:600 12px/1 var(--font);padding:7px 14px;border-radius:var(--rs);transition:all .15s;
  display:inline-flex;align-items:center;gap:5px;white-space:nowrap;
}
.btn:hover{background:var(--bg5);border-color:var(--muted)}
.btn-primary{background:linear-gradient(135deg,rgba(62,184,250,.15),rgba(30,232,204,.1));border-color:rgba(62,184,250,.4);color:var(--blue)}
.btn-primary:hover{background:linear-gradient(135deg,rgba(62,184,250,.25),rgba(30,232,204,.18));border-color:var(--blue)}
.btn-success{background:rgba(57,224,122,.1);border-color:rgba(57,224,122,.3);color:var(--green)}
.btn-success:hover{background:rgba(57,224,122,.2);border-color:var(--green)}
.btn-danger{background:rgba(255,90,110,.1);border-color:rgba(255,90,110,.3);color:var(--red)}
.btn-danger:hover{background:rgba(255,90,110,.2);border-color:var(--red)}
.btn-sm{font-size:11px;padding:5px 10px}
.btn-xs{font-size:10px;padding:3px 8px;border-radius:var(--rxs)}
.btn-viewer{background:rgba(168,126,250,.1);border-color:rgba(168,126,250,.3);color:var(--purple)}
.btn-viewer:hover{background:rgba(168,126,250,.2);border-color:var(--purple)}

/* ── TABLES ──────────────────────────────────────────────── */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:9px 12px;font-size:10px;font-weight:700;letter-spacing:.08em;
  color:var(--muted);text-transform:uppercase;border-bottom:1px solid var(--border);
  background:var(--bg3);white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:hover td{background:var(--faint)}
tr.row-live td{background:rgba(57,224,122,.03)}
tr.row-live:hover td{background:rgba(57,224,122,.06)}
.mono{font-family:var(--mono)}

/* ── BADGES ──────────────────────────────────────────────── */
.badge{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:700;
  padding:3px 8px;border-radius:99px;letter-spacing:.06em}
.bdot{width:6px;height:6px;border-radius:50%;background:currentColor}
.badge-LIVE{background:rgba(57,224,122,.15);color:var(--green);border:1px solid rgba(57,224,122,.3)}
.badge-STOPPED{background:rgba(74,106,136,.12);color:var(--muted);border:1px solid rgba(74,106,136,.2)}
.badge-STARTING{background:rgba(247,195,95,.12);color:var(--yellow);border:1px solid rgba(247,195,95,.3);animation:pulse 1.5s ease-in-out infinite}
.badge-ERROR{background:rgba(255,90,110,.15);color:var(--red);border:1px solid rgba(255,90,110,.3)}
.badge-SCHED{background:rgba(62,184,250,.12);color:var(--blue);border:1px solid rgba(62,184,250,.25)}
.badge-DISABLED{background:rgba(50,50,70,.2);color:var(--muted);border:1px solid var(--border)}
.badge-ONESHOT{background:rgba(168,126,250,.12);color:var(--purple);border:1px solid rgba(168,126,250,.3)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.55}}

.tag-pill{font-size:9px;font-weight:700;letter-spacing:.07em;padding:2px 6px;border-radius:99px}
.t-shuf{background:rgba(247,195,95,.12);color:var(--yellow);border:1px solid rgba(247,195,95,.2)}
.t-hls{background:rgba(255,138,76,.12);color:var(--orange);border:1px solid rgba(255,138,76,.2)}
.t-multi{background:rgba(62,184,250,.1);color:var(--blue);border:1px solid rgba(62,184,250,.2)}

/* ── PROGRESS BAR ────────────────────────────────────────── */
.prog-wrap{display:flex;flex-direction:column;gap:3px;min-width:200px}
.prog-track{
  height:8px;background:var(--bg4);border-radius:99px;overflow:hidden;
  cursor:default;position:relative;border:1px solid var(--border);
}
.prog-track.live{cursor:crosshair}
.prog-track.live:hover{border-color:var(--muted)}
.prog-fill{height:100%;border-radius:99px;transition:width .6s ease,background .4s;min-width:2px}
.prog-labels{display:flex;justify-content:space-between;align-items:center;font-size:10px;font-family:var(--mono)}
.prog-pct{color:var(--muted);font-weight:600}
.prog-remaining{color:var(--yellow);font-size:10px;font-weight:600;font-family:var(--mono)}

/* ── INLINE SEEK SLIDER ──────────────────────────────────── */
.seek-slider-wrap{display:flex;align-items:center;gap:8px;margin-top:3px}
.seek-slider-wrap input[type=range]{
  flex:1;height:4px;accent-color:var(--blue);cursor:pointer;
  background:var(--bg4);border-radius:99px;
}

/* ── STREAM CARDS EXTRAS ─────────────────────────────────── */
.stream-link{font-weight:700;cursor:pointer;color:var(--text)}
.stream-link:hover{color:var(--blue);text-decoration:underline}
.rtsp-chip{
  display:inline-block;background:var(--bg4);border:1px solid var(--border);
  border-radius:var(--rxs);padding:2px 7px;font-size:10px;font-family:var(--mono);
  color:var(--cyan);cursor:pointer;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:260px;vertical-align:middle;
}
.rtsp-chip:hover{border-color:var(--cyan);background:var(--bg5)}

/* ── UPLOAD ──────────────────────────────────────────────── */
#drop-zone{
  border:2px dashed var(--border2);border-radius:var(--r);padding:40px;text-align:center;
  cursor:pointer;transition:all .2s;margin-bottom:16px;
}
#drop-zone:hover,#drop-zone.drag-over{border-color:var(--blue);background:var(--blue-g)}
#drop-zone p{color:var(--muted);font-size:13px;margin-top:8px}
#upload-list{list-style:none;display:flex;flex-direction:column;gap:5px;max-height:280px;overflow-y:auto}
#upload-list li{display:flex;align-items:center;gap:10px;background:var(--bg3);border-radius:var(--rs);padding:7px 12px;font-size:12px}
.ubar{flex:1;height:4px;background:var(--bg4);border-radius:99px;overflow:hidden}
.ubar-fill{height:100%;background:var(--blue);border-radius:99px;transition:width .3s}

/* ── FORM ────────────────────────────────────────────────── */
.form-row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.form-group{display:flex;flex-direction:column;gap:5px;flex:1;min-width:160px}
label{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
input[type=text],input[type=number],input[type=datetime-local],select,textarea{
  background:var(--bg3);border:1px solid var(--border2);color:var(--text);
  border-radius:var(--rs);padding:7px 10px;font:13px var(--font);width:100%;
  transition:border-color .15s;
}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--blue);background:var(--bg4)}
.form-hint{font-size:10px;color:var(--muted);font-family:var(--mono)}
.checkbox-row{display:flex;align-items:center;gap:6px;cursor:pointer;font-size:12px}
.checkbox-row input{width:auto;accent-color:var(--blue)}

/* ── LIBRARY TABLE ───────────────────────────────────────── */
#libtbl tr td:first-child{max-width:320px;word-break:break-all}

/* ── LOG BOX ─────────────────────────────────────────────── */
.log-box{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--rs);
  padding:10px;max-height:300px;overflow-y:auto;font:11px/1.7 var(--mono);
}
.ll{padding:1px 0}
.li{color:var(--text)}
.lw{color:var(--yellow)}
.le{color:var(--red);font-weight:600}
.log-controls{display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.log-chip{
  font-size:10px;font-weight:700;padding:3px 10px;border-radius:99px;cursor:pointer;
  background:var(--bg4);border:1px solid var(--border2);color:var(--muted);
}
.log-chip.a-ALL{border-color:var(--muted);color:var(--text)}
.log-chip.a-INFO{border-color:var(--blue);color:var(--blue);background:var(--blue-g)}
.log-chip.a-WARN{border-color:var(--yellow);color:var(--yellow);background:var(--yellow-g)}
.log-chip.a-ERROR{border-color:var(--red);color:var(--red);background:var(--red-g)}

/* ── MODALS ──────────────────────────────────────────────── */
.modal-overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.72);backdrop-filter:blur(6px);
  display:none;align-items:center;justify-content:center;z-index:1000;padding:20px;
}
.modal-overlay.open{display:flex}
.modal{
  background:var(--bg2);border:1px solid var(--border2);border-radius:var(--r);
  padding:26px;max-width:95vw;max-height:90vh;overflow-y:auto;width:100%;
  box-shadow:var(--shadow);position:relative;
}
.modal h3{display:flex;align-items:center;justify-content:space-between;
  font-size:16px;font-weight:700;margin-bottom:20px;color:var(--text)}
.modal-close{cursor:pointer;color:var(--muted);font-size:18px;line-height:1;padding:4px;border-radius:4px}
.modal-close:hover{color:var(--red);background:var(--red-g)}

/* ── DETAIL GRID ─────────────────────────────────────────── */
.detail-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;margin-bottom:16px}
.detail-card{background:var(--bg3);border:1px solid var(--border);border-radius:var(--rs);padding:10px 12px}
.dk{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}
.dv{font-size:14px;font-weight:700;font-family:var(--mono)}

/* ── PLAYLIST ITEMS ──────────────────────────────────────── */
.plist-item{
  display:flex;align-items:center;gap:8px;padding:8px 10px;
  background:var(--bg3);border:1px solid var(--border);border-radius:var(--rs);
  margin-bottom:6px;cursor:grab;
}
.plist-item.current{border-color:rgba(57,224,122,.4);background:rgba(57,224,122,.05)}
.plist-item.dragging{opacity:.5;border-style:dashed}
.plist-item.drag-target{border-color:var(--blue);background:var(--blue-g)}
.drag-handle{color:var(--muted);cursor:grab;font-size:16px;line-height:1}
.pi-num{font-size:11px;font-weight:700;color:var(--muted);min-width:20px;font-family:var(--mono)}
.pi-prio{
  font-size:10px;font-family:var(--mono);padding:2px 6px;
  background:var(--bg4);border:1px solid var(--border2);border-radius:var(--rxs);
  color:var(--purple);min-width:28px;text-align:center;
}

/* ── SEEK PREVIEW (HLS in-seek-modal) ───────────────────── */
.seek-preview-box{
  border:1px solid var(--border2);border-radius:var(--rs);
  overflow:hidden;background:#000;position:relative;margin-top:12px;
}
.seek-preview-box video{width:100%;max-height:220px;display:block}
.seek-preview-label{
  position:absolute;bottom:6px;right:8px;
  background:rgba(0,0,0,.7);color:var(--red);font-size:10px;
  font-weight:700;padding:2px 7px;border-radius:99px;letter-spacing:.06em;
}

/* ── STREAM VIEWER MODAL ─────────────────────────────────── */
.viewer-player{
  background:#000;border-radius:var(--rs);overflow:hidden;
  position:relative;aspect-ratio:16/9;max-height:50vh;
}
.viewer-player video{width:100%;height:100%;object-fit:contain}
.viewer-no-hls{
  background:var(--bg3);border:1px solid var(--border);border-radius:var(--rs);
  padding:24px 20px;text-align:center;color:var(--muted);font-size:13px;
}
.viewer-cmds{display:flex;flex-direction:column;gap:8px;margin-top:14px}
.viewer-cmd{
  display:flex;align-items:center;gap:10px;background:var(--bg3);
  border:1px solid var(--border);border-radius:var(--rs);padding:8px 12px;
}
.viewer-cmd-label{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;min-width:56px}
.viewer-cmd-code{flex:1;font-size:11px;font-family:var(--mono);color:var(--cyan);word-break:break-all;cursor:pointer}
.viewer-cmd-code:hover{color:var(--blue)}
.viewer-seek-bar{margin-top:14px}
.viewer-seek-bar .vsb-row{display:flex;align-items:center;gap:10px;font-size:11px;font-family:var(--mono)}
.viewer-seek-bar input[type=range]{flex:1;accent-color:var(--purple);height:5px}
.viewer-remaining{color:var(--yellow);font-weight:700}

/* ── CONFIG EDITOR ───────────────────────────────────────── */
.editor-card{
  background:var(--bg3);border:1px solid var(--border);border-radius:var(--r);
  padding:18px;margin-bottom:14px;position:relative;
}
.editor-card-hdr{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.editor-card-name{font-weight:700;font-size:14px}

/* ── NOTIFY TOAST ────────────────────────────────────────── */
.notify{
  position:fixed;bottom:24px;right:24px;z-index:9999;
  background:var(--bg3);border:1px solid var(--border2);border-radius:var(--rs);
  padding:10px 18px;font-size:13px;font-weight:600;
  transform:translateX(calc(100% + 40px));transition:transform .3s ease;
  max-width:380px;box-shadow:var(--shadow);
}
.notify.show{transform:translateX(0)}
.notify.err{border-color:rgba(255,90,110,.5);color:var(--red);background:var(--red-g)}
.notify.info{border-color:rgba(62,184,250,.4);color:var(--blue);background:var(--blue-g)}
</style>
</head>
<body>

<!-- ══ HEADER ════════════════════════════════ -->
<header>
  <a class="logo-wrap" href="/" title="HydraCast">
    <div class="logo-badge">H</div>
    <div>
      <div class="logo-name">HydraCast</div>
    </div>
    <span class="logo-ver" id="hc-ver"></span>
  </a>
  <div class="hdr-stats">
    <div class="hstat">🟢 <strong id="h-live">0</strong> LIVE</div>
    <div class="hstat">⚡ CPU <strong id="h-cpu">—</strong></div>
    <div class="hstat">🧠 RAM <strong id="h-ram">—</strong></div>
    <div class="hstat">💾 Disk <strong id="h-disk">—</strong></div>
    <!-- Web port pill: populated from /api/system_stats -->
    <span class="hdr-webport" id="h-webport" title="Web UI port"></span>
    <div class="hdr-time" id="h-time"></div>
  </div>
  <div class="hdr-acts">
    <button class="btn btn-sm" id="theme-btn" onclick="toggleTheme()" title="Toggle theme">🌙</button>
    <button class="btn btn-sm btn-success" onclick="api('start_all',{})">▶ All</button>
    <button class="btn btn-sm btn-danger"  onclick="api('stop_all',{})">■ All</button>
  </div>
</header>

<!-- ══ NAVIGATION ════════════════════════════ -->
<nav>
  <button onclick="showTab('streams')" class="active">Streams</button>
  <button onclick="showTab('upload')">Upload</button>
  <button onclick="showTab('library')">Library</button>
  <button onclick="showTab('editor')">Config</button>
  <button onclick="showTab('events')">Scheduler</button>
  <button onclick="showTab('logs')">Logs</button>
</nav>

<div class="container">

<!-- ══ STREAMS ════════════════════════════════ -->
<div id="tab-streams" class="tab-content active">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Live Streams</span>
      <span style="margin-left:auto;display:flex;gap:7px;align-items:center">
        <label class="checkbox-row" style="margin:0;font-size:11px">
          <input type="checkbox" id="auto-cb" checked onchange="toggleAuto(this.checked)">
          <span>Auto-refresh</span>
        </label>
        <button class="btn btn-sm" onclick="loadStreams()">↻ Refresh</button>
      </span>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>#</th><th>Name</th><th>Port</th><th>Schedule</th><th>Status</th>
          <th>Progress / Seek</th><th>Position</th><th>FPS</th>
          <th>Remaining</th><th>RTSP URL</th><th>Actions</th>
        </tr></thead>
        <tbody id="stbl"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ UPLOAD ═════════════════════════════════ -->
<div id="tab-upload" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Upload Media</span>
      <span class="form-hint" style="margin-left:auto" id="upload-root-label"></span>
    </div>
    <div class="panel-body">
      <div class="form-row" style="margin-bottom:14px">
        <div class="form-group" style="flex:0 0 auto;min-width:240px">
          <label>Upload to sub-folder</label>
          <select id="upload-subdir"></select>
        </div>
        <div class="form-group" style="justify-content:flex-end">
          <button class="btn btn-sm" onclick="createSubdir()" style="margin-top:auto">+ New folder</button>
        </div>
      </div>
      <div id="drop-zone" onclick="document.getElementById('file-pick').click()">
        <div style="font-size:36px">📁</div>
        <div style="font-weight:700;font-size:15px;margin-top:8px">Drop files here or click to browse</div>
        <p>Supported: MP4 MKV AVI MOV TS M2TS FLV WMV WEBM MPG M4V 3GP MP3 AAC FLAC WAV OGG</p>
        <p style="margin-top:4px;font-size:11px">Max file size: 10 GB</p>
      </div>
      <input type="file" id="file-pick" multiple accept="video/*,audio/*" style="display:none"
             onchange="handleFiles(this.files)">
      <ul id="upload-list"></ul>
    </div>
  </div>
</div>

<!-- ══ LIBRARY ════════════════════════════════ -->
<div id="tab-library" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Media Library</span>
      <span style="margin-left:auto;display:flex;gap:7px;align-items:center">
        <input type="text" id="lib-search" placeholder="Search…" style="width:200px;height:30px;padding:3px 10px" oninput="filterLib()">
        <select id="lib-sort" onchange="filterLib()" style="height:30px;padding:2px 8px">
          <option value="name">Sort: Name</option>
          <option value="size">Sort: Size</option>
          <option value="dur">Sort: Duration</option>
        </select>
        <button class="btn btn-sm" onclick="loadLibrary()">↻</button>
      </span>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Path</th><th>Duration</th><th>Size</th>
          <th>Video</th><th>Resolution</th><th>FPS</th><th>Actions</th>
        </tr></thead>
        <tbody id="libtbl"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ CONFIG EDITOR ══════════════════════════ -->
<div id="tab-editor" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Config Editor</span>
      <span style="margin-left:auto;display:flex;gap:7px">
        <button class="btn btn-sm btn-primary" onclick="addEditorRow()">+ Add Stream</button>
        <button class="btn btn-sm btn-success" onclick="saveCSV()">💾 Save Config</button>
        <button class="btn btn-sm" onclick="loadEditor()">↻</button>
      </span>
    </div>
    <div class="panel-body" id="editor-body"></div>
  </div>
</div>

<!-- ══ SCHEDULER ══════════════════════════════ -->
<div id="tab-events" class="tab-content">
  <div class="panel">
    <div class="panel-hdr"><span class="panel-title">Schedule One-Shot Event</span></div>
    <div class="panel-body">
      <div class="form-row">
        <div class="form-group"><label>Stream</label><select id="evt-stream"></select></div>
        <div class="form-group"><label>Video File</label><select id="evt-file"></select></div>
        <div class="form-group"><label>Play At (local time)</label>
          <input type="datetime-local" id="evt-dt"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Start Position</label>
          <input type="text" id="evt-startpos" placeholder="00:00:00" value="00:00:00"></div>
        <div class="form-group"><label>After Playback</label>
          <select id="evt-post">
            <option value="resume">Resume normal playlist</option>
            <option value="stop">Stop stream</option>
            <option value="black">Show black screen</option>
          </select></div>
        <div class="form-group" style="justify-content:flex-end">
          <button class="btn btn-primary" style="margin-top:auto" onclick="schedEvent()">📅 Schedule</button>
        </div>
      </div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Scheduled Events</span>
      <span style="margin-left:auto;display:flex;gap:7px">
        <button class="btn btn-sm btn-danger" onclick="clearPlayed()">🗑 Clear Played</button>
        <button class="btn btn-sm" onclick="loadEvents()">↻</button>
      </span>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Stream</th><th>File</th><th>Play At</th>
          <th>Countdown</th><th>After</th><th>Status</th><th></th>
        </tr></thead>
        <tbody id="evtbl"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ LOGS ════════════════════════════════ -->
<div id="tab-logs" class="tab-content">
  <div class="panel">
    <div class="panel-hdr">
      <span class="panel-title">Event Log</span>
      <span style="margin-left:auto;display:flex;gap:8px;align-items:center">
        <select id="log-stream-sel" style="width:160px;height:28px;padding:2px 8px" onchange="loadLogs()">
          <option value="">All Streams</option>
        </select>
        <button class="btn btn-sm" onclick="loadLogs()">↻</button>
        <label class="checkbox-row" style="margin:0">
          <input type="checkbox" id="log-autoscroll" checked>
          <span>Auto-scroll</span>
        </label>
      </span>
    </div>
    <div class="panel-body">
      <div class="log-controls">
        <span style="font-size:11px;color:var(--muted)">Level:</span>
        <span class="log-chip a-ALL" data-lv="ALL"   onclick="setLogLv('ALL')">ALL</span>
        <span class="log-chip" data-lv="INFO"  onclick="setLogLv('INFO')">INFO</span>
        <span class="log-chip" data-lv="WARN"  onclick="setLogLv('WARN')">WARN</span>
        <span class="log-chip" data-lv="ERROR" onclick="setLogLv('ERROR')">ERROR</span>
        <input type="text" id="log-search" placeholder="Search…"
               style="width:230px;height:28px;padding:3px 10px;margin-left:auto" oninput="renderLogs()">
      </div>
      <div id="log-box" class="log-box"></div>
    </div>
  </div>
</div>

</div><!-- /container -->

<!-- ══ DETAIL MODAL ══════════════════════════ -->
<div class="modal-overlay" id="detail-modal">
  <div class="modal" style="width:740px">
    <h3>
      <span id="dm-title">Stream Detail</span>
      <span class="modal-close" onclick="closeModal('detail-modal')">✕</span>
    </h3>
    <div id="dm-body"></div>
    <div style="display:flex;gap:8px;margin-top:20px;justify-content:flex-end;flex-wrap:wrap">
      <button class="btn btn-viewer btn-sm" id="dm-view">👁 Watch</button>
      <button class="btn btn-success btn-sm" id="dm-start">▶ Start</button>
      <button class="btn btn-danger btn-sm"  id="dm-stop">■ Stop</button>
      <button class="btn btn-sm"             id="dm-rst">↺ Restart</button>
      <button class="btn btn-sm"             id="dm-skip">⏭ Skip</button>
      <button class="btn" onclick="closeModal('detail-modal')">Close</button>
    </div>
  </div>
</div>

<!-- ══ SEEK MODAL ════════════════════════════ -->
<div class="modal-overlay" id="seek-modal">
  <div class="modal" style="width:520px">
    <h3>
      <span>⏩ Seek — <span id="sk-name"></span></span>
      <span class="modal-close" onclick="closeSeekModal()">✕</span>
    </h3>
    <div class="form-group" style="margin-bottom:14px">
      <label>Jump to timestamp (HH:MM:SS or seconds)</label>
      <input type="text" id="sk-input" placeholder="00:45:30"
             onkeydown="if(event.key==='Enter')doSeek()">
    </div>
    <label>Or drag the seek bar</label>
    <div class="seek-slider-wrap" style="margin-bottom:4px;margin-top:6px">
      <span class="mono" id="sk-cur" style="min-width:64px">00:00:00</span>
      <input type="range" id="sk-slider" min="0" max="100" value="0"
             oninput="skSliderInput(this.value)">
      <span class="mono" id="sk-dur" style="min-width:64px;text-align:right">--</span>
    </div>
    <div id="sk-preview" class="seek-preview-box" style="display:none">
      <video id="sk-video" muted playsinline autoplay></video>
      <div class="seek-preview-label">🔴 Live HLS Preview</div>
    </div>
    <div style="display:flex;gap:8px;margin-top:20px;justify-content:flex-end">
      <button class="btn" onclick="closeSeekModal()">Cancel</button>
      <button class="btn btn-primary" onclick="doSeek()">Seek to Position</button>
    </div>
  </div>
</div>

<!-- ══ VIEWER MODAL ══════════════════════════ -->
<div class="modal-overlay" id="viewer-modal">
  <div class="modal" style="width:800px">
    <h3>
      <span>👁 Watch — <span id="vm-title"></span></span>
      <span class="modal-close" onclick="closeViewer()">✕</span>
    </h3>
    <div id="vm-player-wrap"></div>
    <div class="viewer-seek-bar" id="vm-seek-bar" style="display:none">
      <div class="section-label" style="margin-top:14px">Live Position</div>
      <div class="vsb-row" style="margin-top:6px">
        <span class="mono" id="vm-cur">--:--:--</span>
        <input type="range" id="vm-slider" min="0" max="100" value="0"
               oninput="vmSliderInput(this.value)"
               onchange="vmSeek(+this.value)">
        <span class="mono" id="vm-dur">--:--:--</span>
        <span class="viewer-remaining" id="vm-rem"></span>
      </div>
      <div style="display:flex;gap:8px;justify-content:center;margin-top:10px">
        <button class="btn btn-sm" onclick="vmSeekRel(-30)">«−30s</button>
        <button class="btn btn-sm" onclick="vmSeekRel(-10)">«−10s</button>
        <button class="btn btn-sm" onclick="vmSeekRel(10)">+10s»</button>
        <button class="btn btn-sm" onclick="vmSeekRel(30)">+30s»</button>
      </div>
    </div>
    <div class="viewer-cmds" id="vm-cmds"></div>
    <div style="display:flex;gap:8px;margin-top:20px;justify-content:flex-end">
      <button class="btn btn-sm btn-success" id="vm-start-btn">▶ Start</button>
      <button class="btn btn-sm btn-danger"  id="vm-stop-btn">■ Stop</button>
      <button class="btn" onclick="closeViewer()">Close</button>
    </div>
  </div>
</div>

<!-- ══ PLAYLIST PRIORITY MODAL ═══════════════ -->
<div class="modal-overlay" id="prio-modal">
  <div class="modal" style="width:580px">
    <h3>
      <span>🎯 Playlist Order — <span id="pm-name"></span></span>
      <span class="modal-close" onclick="closeModal('prio-modal')">✕</span>
    </h3>
    <p style="font-size:12px;color:var(--muted);margin-bottom:16px">
      Drag to reorder · Lower priority # plays first · Click "Apply" then "Save Config" to persist.
    </p>
    <div id="pm-list" style="background:var(--bg);border:1px solid var(--border);border-radius:var(--rs);padding:10px;max-height:360px;overflow-y:auto"></div>
    <div style="display:flex;gap:8px;margin-top:20px;justify-content:flex-end">
      <button class="btn" onclick="closeModal('prio-modal')">Cancel</button>
      <button class="btn btn-primary" onclick="applyPriority()">Apply Order</button>
    </div>
  </div>
</div>

<div class="notify" id="notify"></div>

<!-- ══ HLS.js ════════════════════════════════ -->
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js"></script>

<script>
// ════════════════════════════════════════════════════════════
// STATE
// ════════════════════════════════════════════════════════════
let streamData=[],libData=[],logEntries=[],logLv='ALL';
let seekTarget=null,seekDuration=0,seekHls='';
let autoRefresh=true,refreshTimer=null;
let editorRows=[],prioStreamName=null,prioOrigFiles=[];
let vmStreamName=null,vmHlsObj=null,vmPollTimer=null;

// ════════════════════════════════════════════════════════════
// UTILS
// ════════════════════════════════════════════════════════════
function fmtSecs(s){
  s=Math.max(0,Math.floor(+s||0));
  return [Math.floor(s/3600),Math.floor((s%3600)/60),s%60]
    .map(n=>String(n).padStart(2,'0')).join(':');
}
function fmtRemaining(remSecs){
  if(remSecs<=0)return '';
  return '−'+fmtSecs(remSecs);
}
function fmtBytes(n){
  if(n<1024)return n+' B';
  if(n<1048576)return (n/1024).toFixed(1)+' KB';
  if(n<1073741824)return (n/1048576).toFixed(1)+' MB';
  return (n/1073741824).toFixed(2)+' GB';
}
function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
let _notifyTm;
function notify(msg,type='ok'){
  const el=document.getElementById('notify');
  el.textContent=msg;el.className='notify '+type+' show';
  clearTimeout(_notifyTm);_notifyTm=setTimeout(()=>el.classList.remove('show'),type==='err'?5000:3000);
}
function closeModal(id){document.getElementById(id).classList.remove('open')}
function openModal(id){document.getElementById(id).classList.add('open')}
document.querySelectorAll('.modal-overlay').forEach(el=>{
  el.addEventListener('click',e=>{if(e.target===el&&el.id!=='viewer-modal')el.classList.remove('open')});
});

// ════════════════════════════════════════════════════════════
// THEME
// ════════════════════════════════════════════════════════════
(function(){
  const saved=localStorage.getItem('hc-theme')||'dark';
  if(saved==='light')document.documentElement.dataset.theme='light';
  document.addEventListener('DOMContentLoaded',()=>{
    const btn=document.getElementById('theme-btn');
    if(btn)btn.textContent=saved==='light'?'🌙':'☀️';
  });
})();
function toggleTheme(){
  const root=document.documentElement;
  const isLight=root.dataset.theme==='light';
  root.dataset.theme=isLight?'dark':'light';
  document.getElementById('theme-btn').textContent=isLight?'☀️':'🌙';
  localStorage.setItem('hc-theme',isLight?'dark':'light');
}

// ════════════════════════════════════════════════════════════
// TABS
// ════════════════════════════════════════════════════════════
const TAB_LABELS={streams:'Streams',upload:'Upload',library:'Library',
                  editor:'Config',events:'Scheduler',logs:'Logs'};
function showTab(name){
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  document.querySelectorAll('nav button').forEach(btn=>{
    if(btn.textContent.trim()===TAB_LABELS[name])btn.classList.add('active');
  });
  if(name==='streams')      loadStreams();
  else if(name==='library') loadLibrary();
  else if(name==='editor')  loadEditor();
  else if(name==='events'){loadEvents();loadEvtForm();}
  else if(name==='logs')    loadLogs();
  else if(name==='upload')  loadSubdirs();
}

// ════════════════════════════════════════════════════════════
// API
// ════════════════════════════════════════════════════════════
async function api(action,data={}){
  try{
    const r=await fetch('/api/'+action,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    const j=await r.json();
    if(j.ok){notify(j.msg||'Done ✓');loadStreams();}
    else notify(j.msg||'Error','err');
    return j;
  }catch(e){notify('Request failed: '+e,'err');}
}

// ════════════════════════════════════════════════════════════
// HEADER STATS  —  web port now comes from system_stats
// ════════════════════════════════════════════════════════════
async function updateHdrStats(){
  try{
    const[sd,st]=await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/system_stats').then(r=>r.json()),
    ]);
    streamData=sd;
    const ver=sd[0]?.app_ver||'';
    const verEl=document.getElementById('hc-ver');
    if(verEl&&ver)verEl.textContent='v'+ver;
    document.getElementById('h-live').textContent=sd.filter(s=>s.status==='LIVE').length;
    document.getElementById('h-cpu').textContent=st.cpu+'%';
    document.getElementById('h-ram').textContent=st.mem_percent+'%';
    document.getElementById('h-disk').textContent=st.disk_percent+'%';
    // Show web port in header pill
    if(st.web_port){
      const portEl=document.getElementById('h-webport');
      if(portEl)portEl.textContent='Web :'+st.web_port;
    }
  }catch(_){}
}

// ════════════════════════════════════════════════════════════
// AUTO REFRESH
// ════════════════════════════════════════════════════════════
function toggleAuto(on){
  autoRefresh=on;
  if(on)startRefresh();else clearInterval(refreshTimer);
}
function startRefresh(){
  clearInterval(refreshTimer);
  refreshTimer=setInterval(()=>{loadStreams();updateHdrStats();},2500);
}

// ════════════════════════════════════════════════════════════
// STREAMS TABLE
// ════════════════════════════════════════════════════════════
async function loadStreams(){
  try{
    const r=await fetch('/api/streams');
    streamData=await r.json();
    renderStreams();
  }catch(e){}
}

function _buildStreamRow(s,i){
  const pct=(+s.progress).toFixed(1);
  const fc=s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
  const live=s.status==='LIVE';
  const nf=s.playlist_count||1;
  const rem=s.time_remaining>0?fmtRemaining(s.time_remaining):'';
  return `
<tr class="${live?'row-live':''}" data-stream="${esc(s.name)}">
  <td class="mono" style="color:var(--muted);font-size:11px">${i+1}</td>
  <td>
    <div class="stream-link" onclick="openDetail('${esc(s.name)}')">${esc(s.name)}</div>
    <div style="display:flex;gap:4px;margin-top:3px;flex-wrap:wrap">
      ${s.shuffle?'<span class="tag-pill t-shuf">SHUFFLE</span>':''}
      ${s.hls_url?'<span class="tag-pill t-hls">HLS</span>':''}
      ${nf>1?'<span class="tag-pill t-multi">×'+nf+' files</span>':''}
    </div>
  </td>
  <td><code class="mono" style="color:var(--cyan)">:${s.port}</code></td>
  <td style="color:var(--muted);font-size:11.5px;white-space:nowrap">${esc(s.weekdays)}</td>
  <td data-cell="status"><span class="badge badge-${esc(s.status)}"><div class="bdot"></div>${esc(s.status)}</span></td>
  <td style="min-width:240px">
    <div class="prog-wrap">
      <div class="prog-track ${live?'live':''}"
           ${live?`onclick="barClick(event,'${esc(s.name)}',${s.duration})" title="Click to seek"`:''}
           style="cursor:${live?'crosshair':'default'}">
        <div class="prog-fill" data-cell="fill" style="width:${pct}%;background:${fc}"></div>
      </div>
      <div class="prog-labels">
        <span data-cell="pos-start">${live?esc((s.position||'').split('/')[0].trim()||'--'):'--'}</span>
        <span class="prog-pct" data-cell="pct">${pct}%</span>
        <span data-cell="pos-end">${live?esc((s.position||'').split('/')[1]?.trim()||'--'):'--'}</span>
      </div>
    </div>
    ${live?`
    <div class="seek-slider-wrap">
      <span class="mono" style="font-size:10px;min-width:52px" data-cell="sl-start">${esc((s.position||'').split('/')[0].trim()||'--')}</span>
      <input type="range" min="0" max="${Math.max(1,Math.floor(s.duration))}"
             value="${Math.floor(s.current_secs)}"
             data-cell="slider" data-stream="${esc(s.name)}" data-dur="${Math.floor(s.duration)}"
             title="Drag to seek"
             oninput="this.previousElementSibling.textContent=fmtSecs(this.value)"
             onchange="inlineSeek('${esc(s.name)}',+this.value)">
      <span class="mono" style="font-size:10px;min-width:52px;text-align:right" data-cell="sl-end">${esc((s.position||'').split('/')[1]?.trim()||'--')}</span>
    </div>`:''}
  </td>
  <td class="mono pos-cell" style="color:var(--muted);font-size:11px;white-space:nowrap">${esc(s.position||'--')}</td>
  <td class="mono" style="color:var(--muted)">${s.fps>0?Math.round(s.fps):'--'}</td>
  <td class="mono" style="color:var(--yellow);white-space:nowrap" data-cell="rem">${esc(rem)}</td>
  <td>
    <span class="rtsp-chip" onclick="copyURL('${esc(s.rtsp_url)}')" title="Copy RTSP URL">${esc(s.rtsp_url)}</span>
    ${s.hls_url?`<br><span class="rtsp-chip" style="color:var(--orange);margin-top:3px" onclick="copyURL('${esc(s.hls_url)}')">HLS</span>`:''}
  </td>
  <td style="white-space:nowrap">
    <div style="display:flex;gap:3px;flex-wrap:wrap">
      <button class="btn btn-xs btn-viewer" onclick="openViewer('${esc(s.name)}')" title="Watch stream">👁</button>
      <button class="btn btn-xs btn-success" onclick="api('start',{name:'${esc(s.name)}'})" title="Start">▶</button>
      <button class="btn btn-xs btn-danger"  onclick="api('stop',{name:'${esc(s.name)}'})"  title="Stop">■</button>
      <button class="btn btn-xs" onclick="api('restart',{name:'${esc(s.name)}'})" title="Restart">↺</button>
      <button class="btn btn-xs" onclick="openSeek('${esc(s.name)}',${s.duration},${s.current_secs},'${esc(s.hls_url||'')}')" title="Seek">⏩</button>
      ${nf>1?`<button class="btn btn-xs" onclick="openPrio('${esc(s.name)}')" title="Playlist order">🎯</button>`:''}
      ${live&&nf>1?`<button class="btn btn-xs" onclick="api('skip_next',{name:'${esc(s.name)}'})" title="Skip to next">⏭</button>`:''}
    </div>
  </td>
</tr>`;
}

function renderStreams(){
  const tb=document.getElementById('stbl');
  const nameKey=streamData.map(s=>s.name).join('\x00');
  if(tb.dataset.nameKey!==nameKey){
    tb.dataset.nameKey=nameKey;
    tb.innerHTML=streamData.map((s,i)=>_buildStreamRow(s,i)).join('');
    return;
  }
  const activeSlider=document.activeElement?.dataset?.stream;
  streamData.forEach((s,i)=>{
    const row=tb.querySelector(`tr[data-stream="${CSS.escape(s.name)}"]`);
    if(!row)return;
    const pct=(+s.progress).toFixed(1);
    const fc=s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
    const live=s.status==='LIVE';
    const pos=(s.position||'');
    const posStart=pos.split('/')[0]?.trim()||'--';
    const posEnd=pos.split('/')[1]?.trim()||'--';
    const rem=s.time_remaining>0?fmtRemaining(s.time_remaining):'';
    row.className=live?'row-live':'';
    const sc=row.querySelector('[data-cell="status"]');
    if(sc)sc.innerHTML=`<span class="badge badge-${esc(s.status)}"><div class="bdot"></div>${esc(s.status)}</span>`;
    const fill=row.querySelector('[data-cell="fill"]');
    if(fill){fill.style.width=pct+'%';fill.style.background=fc;}
    const pctEl=row.querySelector('[data-cell="pct"]');
    if(pctEl)pctEl.textContent=pct+'%';
    const ps=row.querySelector('[data-cell="pos-start"]');
    if(ps)ps.textContent=live?posStart:'--';
    const pe=row.querySelector('[data-cell="pos-end"]');
    if(pe)pe.textContent=live?posEnd:'--';
    const remEl=row.querySelector('[data-cell="rem"]');
    if(remEl)remEl.textContent=rem;
    if(s.name!==activeSlider){
      const sl=row.querySelector('[data-cell="slider"]');
      if(sl){
        sl.value=Math.floor(s.current_secs);
        sl.max=Math.max(1,Math.floor(s.duration));
        const slStart=row.querySelector('[data-cell="sl-start"]');
        const slEnd=row.querySelector('[data-cell="sl-end"]');
        if(slStart)slStart.textContent=posStart;
        if(slEnd)slEnd.textContent=posEnd;
      }
    }
    const posCell=row.querySelector('.pos-cell');
    if(posCell)posCell.textContent=s.position||'--';
  });
}
function copyURL(url){navigator.clipboard.writeText(url).then(()=>notify('Copied ✓','info'));}
function barClick(e,name,dur){
  if(dur<=0)return;
  const rect=e.currentTarget.getBoundingClientRect();
  const pct=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));
  const secs=Math.floor(pct*dur);
  api('seek',{name,seconds:secs}).then(()=>setTimeout(loadStreams,600));
}
function inlineSeek(name,secs){
  api('seek',{name,seconds:secs}).then(()=>setTimeout(loadStreams,600));
}

// ════════════════════════════════════════════════════════════
// STREAM DETAIL MODAL
// ════════════════════════════════════════════════════════════
async function openDetail(name){
  try{
    const d=await fetch('/api/stream_detail?name='+encodeURIComponent(name)).then(r=>r.json());
    if(d.error){notify(d.error,'err');return;}
    document.getElementById('dm-title').textContent=d.name;
    document.getElementById('dm-start').onclick=()=>{api('start',{name:d.name});closeModal('detail-modal');};
    document.getElementById('dm-stop' ).onclick=()=>{api('stop',{name:d.name});closeModal('detail-modal');};
    document.getElementById('dm-rst'  ).onclick=()=>{api('restart',{name:d.name});closeModal('detail-modal');};
    document.getElementById('dm-skip' ).onclick=()=>{api('skip_next',{name:d.name});closeModal('detail-modal');};
    document.getElementById('dm-view' ).onclick=()=>{closeModal('detail-modal');openViewer(d.name);};
    const pct=(+d.progress).toFixed(1);
    const fc=d.progress>80?'var(--red)':d.progress>55?'var(--yellow)':'var(--green)';
    const isLive=d.status==='LIVE';
    const remSecs=d.duration>0&&d.current_pos>0?Math.max(0,d.duration-d.current_pos):0;
    const plHtml=(d.playlist||[]).map((p,i)=>`
      <div class="plist-item ${p.current?'current':''}">
        <span style="font-size:11px;color:var(--muted);width:20px">${i+1}</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px" title="${esc(p.path)}">${esc(p.file)}</span>
        <span class="mono" style="color:var(--muted);font-size:10px">${esc(p.start)}</span>
        <span class="pi-prio">P${p.priority}</span>
        ${p.current?'<span style="color:var(--green);font-size:10px;font-weight:700">▶ NOW</span>':''}
        ${!p.exists?'<span style="color:var(--red);font-size:10px">✗ MISSING</span>':''}
      </div>`).join('');
    const logHtml=(d.log||[]).slice(-50).map(line=>{
      const lv=/error/i.test(line)?'e':/warn|restart/i.test(line)?'w':'i';
      return `<div class="ll l${lv}">${esc(line)}</div>`;
    }).join('');
    document.getElementById('dm-body').innerHTML=`
      <div class="detail-grid">
        <div class="detail-card"><div class="dk">Status</div><div class="dv"><span class="badge badge-${esc(d.status)}"><div class="bdot"></div>${esc(d.status)}</span></div></div>
        <div class="detail-card"><div class="dk">Port</div><div class="dv" style="color:var(--cyan)">:${d.port}</div></div>
        <div class="detail-card"><div class="dk">Video BR</div><div class="dv">${esc(d.video_bitrate)}</div></div>
        <div class="detail-card"><div class="dk">Audio BR</div><div class="dv">${esc(d.audio_bitrate)}</div></div>
        <div class="detail-card"><div class="dk">Schedule</div><div class="dv" style="font-size:11px">${esc(d.weekdays)}</div></div>
        <div class="detail-card"><div class="dk">Restarts</div><div class="dv" style="color:${d.restart_count>0?'var(--yellow)':'var(--green)'}">×${d.restart_count}</div></div>
        <div class="detail-card"><div class="dk">Loops</div><div class="dv">×${d.loop_count}</div></div>
        <div class="detail-card"><div class="dk">Remaining</div><div class="dv" style="color:var(--yellow)">${remSecs>0?fmtSecs(remSecs):'—'}</div></div>
      </div>
      ${d.error_msg?`<div style="background:var(--red-g);border:1px solid rgba(255,90,110,.3);border-radius:var(--rs);padding:10px 14px;font-size:11px;color:var(--red);margin-bottom:16px;font-family:var(--mono)">${esc(d.error_msg)}</div>`:''}
      <div class="section-label">Progress</div>
      <div class="prog-wrap" style="margin-bottom:4px">
        <div class="prog-track ${isLive?'live':''}"
             ${isLive?`onclick="barClick(event,'${esc(d.name)}',${d.duration})" title="Click to seek"`:''}
             style="cursor:${isLive?'crosshair':'default'}">
          <div class="prog-fill" style="width:${pct}%;background:${fc}"></div>
        </div>
        <div class="prog-labels">
          <span class="mono">${fmtSecs(d.current_pos)}</span>
          <span class="prog-pct">${pct}%</span>
          <span class="mono">${fmtSecs(d.duration)}</span>
        </div>
      </div>
      ${remSecs>0?`<div style="font-size:11px;color:var(--yellow);font-family:var(--mono);text-align:right;margin-bottom:12px">${fmtRemaining(remSecs)} remaining</div>`:'<div style="margin-bottom:12px"></div>'}
      ${isLive&&d.duration>0?`
      <div class="seek-slider-wrap" style="margin-bottom:18px">
        <span class="mono" style="font-size:10px;min-width:64px">${fmtSecs(d.current_pos)}</span>
        <input type="range" min="0" max="${Math.floor(d.duration)}" value="${Math.floor(d.current_pos)}"
               oninput="this.previousElementSibling.textContent=fmtSecs(this.value)"
               onchange="api('seek',{name:'${esc(d.name)}',seconds:+this.value})">
        <span class="mono" style="font-size:10px;min-width:64px;text-align:right">${fmtSecs(d.duration)}</span>
      </div>`:''}
      <div class="section-label">Playlist — ${(d.playlist||[]).length} file${(d.playlist||[]).length!==1?'s':''}</div>
      <div style="margin-bottom:18px">${plHtml||'<span style="color:var(--muted)">No files</span>'}</div>
      <div class="section-label">Recent Log</div>
      <div class="log-box">${logHtml||'<span style="color:var(--muted)">No entries</span>'}</div>
      ${d.rtsp_url?`
      <div style="margin-top:16px">
        <div class="section-label">Stream URLs</div>
        <div style="display:flex;flex-direction:column;gap:5px">
          <span class="rtsp-chip" onclick="copyURL('${esc(d.rtsp_url)}')" title="Copy RTSP URL">${esc(d.rtsp_url)}</span>
          ${d.hls_url?`<span class="rtsp-chip" style="color:var(--orange)" onclick="copyURL('${esc(d.hls_url)}')" title="Copy HLS URL">${esc(d.hls_url)}</span>`:''}
        </div>
      </div>`:''}
    `;
    openModal('detail-modal');
  }catch(e){notify('Failed to load detail','err');}
}

// ════════════════════════════════════════════════════════════
// STREAM VIEWER MODAL
// ════════════════════════════════════════════════════════════
async function openViewer(name){
  try{
    const d=await fetch('/api/stream_view?name='+encodeURIComponent(name)).then(r=>r.json());
    if(d.error){notify(d.error,'err');return;}
    vmStreamName=name;
    document.getElementById('vm-title').textContent=name;
    document.getElementById('vm-start-btn').onclick=()=>api('start',{name});
    document.getElementById('vm-stop-btn').onclick=()=>api('stop',{name});
    const pw=document.getElementById('vm-player-wrap');
    pw.innerHTML='';
    if(d.hls_url&&typeof Hls!=='undefined'&&Hls.isSupported()){
      const box=document.createElement('div');
      box.className='viewer-player';
      const vid=document.createElement('video');
      vid.id='vm-video';vid.controls=true;vid.autoplay=false;vid.style.width='100%';vid.style.height='100%';
      box.appendChild(vid);pw.appendChild(box);
      if(vmHlsObj){vmHlsObj.destroy();vmHlsObj=null;}
      const hls=new Hls({lowLatencyMode:true,backBufferLength:30});
      hls.loadSource(d.hls_url);hls.attachMedia(vid);
      hls.on(Hls.Events.MANIFEST_PARSED,()=>{vid.play().catch(_=>{});});
      hls.on(Hls.Events.ERROR,(_,data)=>{if(data.fatal)notify('HLS error: '+data.type,'err');});
      vmHlsObj=hls;
    }else if(d.hls_url){
      const box=document.createElement('div');box.className='viewer-player';
      const vid=document.createElement('video');
      vid.src=d.hls_url;vid.controls=true;vid.autoplay=false;
      vid.style.width='100%';vid.style.height='100%';
      box.appendChild(vid);pw.appendChild(box);
    }else{
      pw.innerHTML=`<div class="viewer-no-hls">
        <div style="font-size:32px;margin-bottom:10px">📡</div>
        <div style="font-weight:700;font-size:15px;margin-bottom:6px">HLS not enabled for this stream</div>
        <div style="font-size:12px">Enable HLS in Config editor to get a browser-playable stream.<br>
        Use the RTSP URL below in VLC or ffplay.</div>
      </div>`;
    }
    const cmds=document.getElementById('vm-cmds');
    cmds.innerHTML=[
      {label:'RTSP URL',val:d.rtsp_url,color:'var(--cyan)'},
      d.hls_url?{label:'HLS URL',val:d.hls_url,color:'var(--orange)'}:null,
      {label:'VLC',val:`vlc ${d.rtsp_url}`,color:'var(--muted)'},
      {label:'ffplay',val:`ffplay -fflags nobuffer ${d.rtsp_url}`,color:'var(--muted)'},
    ].filter(Boolean).map(c=>`
      <div class="viewer-cmd">
        <span class="viewer-cmd-label">${esc(c.label)}</span>
        <span class="viewer-cmd-code" style="color:${c.color}" onclick="copyURL('${esc(c.val)}')" title="Click to copy">${esc(c.val)}</span>
        <button class="btn btn-xs" onclick="copyURL('${esc(c.val)}')">📋</button>
      </div>`).join('');
    const sb=document.getElementById('vm-seek-bar');
    if(d.status==='LIVE'&&d.duration>0){
      sb.style.display='block';
      const sl=document.getElementById('vm-slider');
      sl.max=Math.floor(d.duration);sl.value=Math.floor(d.current_pos);
      _vmUpdateSeekBar(d);
    }else{sb.style.display='none';}
    openModal('viewer-modal');
    _vmStartPoll();
  }catch(e){notify('Failed to open viewer','err');}
}
function _vmUpdateSeekBar(d){
  const sl=document.getElementById('vm-slider');
  if(document.activeElement!==sl){sl.value=Math.floor(d.current_pos);sl.max=Math.max(1,Math.floor(d.duration));}
  document.getElementById('vm-cur').textContent=fmtSecs(d.current_pos);
  document.getElementById('vm-dur').textContent=fmtSecs(d.duration);
  const rem=d.duration>0&&d.current_pos>0?Math.max(0,d.duration-d.current_pos):0;
  document.getElementById('vm-rem').textContent=rem>0?fmtRemaining(rem)+' left':'';
}
function _vmStartPoll(){
  clearInterval(vmPollTimer);
  vmPollTimer=setInterval(async()=>{
    if(!vmStreamName)return;
    if(!document.getElementById('viewer-modal').classList.contains('open')){clearInterval(vmPollTimer);return;}
    try{
      const d=await fetch('/api/stream_view?name='+encodeURIComponent(vmStreamName)).then(r=>r.json());
      if(d.error)return;
      const sb=document.getElementById('vm-seek-bar');
      if(d.status==='LIVE'&&d.duration>0){sb.style.display='block';_vmUpdateSeekBar(d);}
      else{sb.style.display='none';}
    }catch(_){}
  },1500);
}
function closeViewer(){
  clearInterval(vmPollTimer);
  if(vmHlsObj){vmHlsObj.destroy();vmHlsObj=null;}
  const vid=document.getElementById('vm-video');
  if(vid){vid.pause();vid.src='';}
  vmStreamName=null;closeModal('viewer-modal');
}
function vmSliderInput(v){
  document.getElementById('vm-cur').textContent=fmtSecs(v);
  const dur=+document.getElementById('vm-slider').max;
  const rem=Math.max(0,dur-v);
  document.getElementById('vm-rem').textContent=rem>0?fmtRemaining(rem)+' left':'';
}
function vmSeek(secs){if(!vmStreamName)return;api('seek',{name:vmStreamName,seconds:secs});}
function vmSeekRel(delta){
  const sl=document.getElementById('vm-slider');
  vmSeek(Math.max(0,Math.min(+sl.max,+sl.value+delta)));
}

// ════════════════════════════════════════════════════════════
// SEEK MODAL
// ════════════════════════════════════════════════════════════
function openSeek(name,dur,curSecs,hlsUrl){
  seekTarget=name;seekDuration=dur;seekHls=hlsUrl||'';
  document.getElementById('sk-name').textContent=name;
  document.getElementById('sk-input').value='';
  const sl=document.getElementById('sk-slider');
  sl.max=Math.floor(dur);sl.value=Math.floor(curSecs);
  document.getElementById('sk-cur').textContent=fmtSecs(curSecs);
  document.getElementById('sk-dur').textContent=fmtSecs(dur);
  const prev=document.getElementById('sk-preview');
  const vid=document.getElementById('sk-video');
  if(hlsUrl&&typeof Hls!=='undefined'&&Hls.isSupported()){
    prev.style.display='block';
    if(vid._hlsObj){vid._hlsObj.destroy();}
    const h=new Hls();h.loadSource(hlsUrl);h.attachMedia(vid);
    h.on(Hls.Events.MANIFEST_PARSED,()=>vid.play().catch(_=>{}));
    vid._hlsObj=h;
  }else if(hlsUrl){prev.style.display='block';vid.src=hlsUrl;vid.play().catch(_=>{});}
  else{prev.style.display='none';vid.src='';}
  openModal('seek-modal');
  setTimeout(()=>document.getElementById('sk-input').focus(),80);
}
function closeSeekModal(){
  const vid=document.getElementById('sk-video');
  if(vid._hlsObj){vid._hlsObj.destroy();vid._hlsObj=null;}
  vid.pause();vid.src='';closeModal('seek-modal');
}
function skSliderInput(v){document.getElementById('sk-cur').textContent=fmtSecs(v);}
function doSeek(){
  let secs;
  const txt=document.getElementById('sk-input').value.trim();
  if(txt){
    const p=txt.split(':').map(Number);
    secs=p.length===3?p[0]*3600+p[1]*60+p[2]:p.length===2?p[0]*60+p[1]:+p[0];
    if(isNaN(secs)||secs<0){notify('Invalid time format','err');return;}
  }else{secs=+document.getElementById('sk-slider').value;}
  if(secs>seekDuration&&seekDuration>0){notify('Position beyond duration','err');return;}
  api('seek',{name:seekTarget,seconds:secs});closeSeekModal();
}

// ════════════════════════════════════════════════════════════
// PRIORITY / PLAYLIST REORDER MODAL
// ════════════════════════════════════════════════════════════
async function openPrio(name){
  try{
    const d=await fetch('/api/stream_detail?name='+encodeURIComponent(name)).then(r=>r.json());
    if(d.error){notify(d.error,'err');return;}
    prioStreamName=name;prioOrigFiles=d.playlist||[];
    document.getElementById('pm-name').textContent=name;
    const list=document.getElementById('pm-list');
    list.innerHTML=prioOrigFiles.map((p,i)=>`
      <div class="plist-item" draggable="true" data-idx="${i}" data-path="${esc(p.path)}" data-start="${esc(p.start)}" data-priority="${p.priority}">
        <span class="drag-handle" title="Drag to reorder">⠿</span>
        <span class="pi-num">${i+1}</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px" title="${esc(p.path)}">${esc(p.file)}</span>
        <span class="mono" style="color:var(--muted);font-size:10px">${esc(p.start)}</span>
        <span class="pi-prio" contenteditable="true" title="Edit priority">${p.priority}</span>
        ${p.current?'<span style="color:var(--green);font-size:10px">▶ NOW</span>':''}
        ${!p.exists?'<span style="color:var(--red);font-size:10px">✗ MISSING</span>':''}
      </div>`).join('');
    setupDragDrop(list);openModal('prio-modal');
  }catch(e){notify('Failed to load playlist','err');}
}
function setupDragDrop(container){
  let src=null;
  container.querySelectorAll('.plist-item').forEach(el=>{
    el.addEventListener('dragstart',e=>{src=el;el.classList.add('dragging');e.dataTransfer.effectAllowed='move';});
    el.addEventListener('dragend',()=>{el.classList.remove('dragging');container.querySelectorAll('.plist-item').forEach(x=>x.classList.remove('drag-target'));});
    el.addEventListener('dragover',e=>{e.preventDefault();container.querySelectorAll('.plist-item').forEach(x=>x.classList.remove('drag-target'));el.classList.add('drag-target');});
    el.addEventListener('drop',e=>{
      e.preventDefault();if(!src||src===el)return;
      const items=[...container.querySelectorAll('.plist-item')];
      const si=items.indexOf(src),di=items.indexOf(el);
      if(si<di)el.after(src);else el.before(src);
      container.querySelectorAll('.plist-item').forEach((x,j)=>{x.dataset.idx=j;x.querySelector('.pi-num').textContent=j+1;});
      container.querySelectorAll('.plist-item').forEach(x=>x.classList.remove('drag-target'));
    });
  });
}
function applyPriority(){
  if(!prioStreamName)return;
  const items=[...document.getElementById('pm-list').querySelectorAll('.plist-item')];
  const newFiles=items.map((el,i)=>{
    const path=el.dataset.path,start=el.dataset.start;
    const priEl=el.querySelector('.pi-prio');
    const pri=parseInt(priEl?.textContent?.trim()||String(i+1))||i+1;
    return `${path}@${start}#${pri}`;
  });
  const idx=editorRows.findIndex(r=>r.name===prioStreamName);
  if(idx>=0){editorRows[idx].files=newFiles.join(';');renderEditor();notify('Playlist order updated — click Save Config to persist');}
  else{notify('Open Config tab first, then reorder','info');}
  closeModal('prio-modal');
}

// ════════════════════════════════════════════════════════════
// UPLOAD
// ════════════════════════════════════════════════════════════
const dz=document.getElementById('drop-zone');
dz.addEventListener('dragover',e=>{e.preventDefault();dz.classList.add('drag-over')});
dz.addEventListener('dragleave',()=>dz.classList.remove('drag-over'));
dz.addEventListener('drop',e=>{e.preventDefault();dz.classList.remove('drag-over');handleFiles(e.dataTransfer.files)});
const MAX_UP=10*1024*1024*1024;
function handleFiles(files){Array.from(files).forEach(uploadFile);}
function uploadFile(file){
  if(file.size>MAX_UP){notify(file.name+': exceeds 10 GB limit','err');return;}
  const key='f'+Math.random().toString(36).slice(2,8);
  const subdir=document.getElementById('upload-subdir').value;
  const li=document.createElement('li');
  li.innerHTML=`
    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(file.name)}</span>
    <span class="mono" style="color:var(--muted)">${fmtBytes(file.size)}</span>
    <div class="ubar"><div class="ubar-fill" id="ub-${key}" style="width:0"></div></div>
    <span id="up-${key}" class="mono" style="color:var(--muted);min-width:36px;text-align:right">0%</span>`;
  document.getElementById('upload-list').appendChild(li);
  const fd=new FormData();fd.append('file',file);fd.append('subdir',subdir);
  const xhr=new XMLHttpRequest();
  xhr.upload.onprogress=e=>{
    if(!e.lengthComputable)return;
    const pct=Math.round(e.loaded/e.total*100);
    const b=document.getElementById('ub-'+key),p=document.getElementById('up-'+key);
    if(b)b.style.width=pct+'%';if(p)p.textContent=pct+'%';
  };
  xhr.onload=()=>{
    const p=document.getElementById('up-'+key);
    try{
      const j=JSON.parse(xhr.responseText);
      if(xhr.status===200&&j.ok){if(p){p.textContent='✓';p.style.color='var(--green)';}notify(file.name+' uploaded ✓');}
      else{if(p){p.textContent='✗';p.style.color='var(--red)';}notify('Upload failed: '+(j.msg||file.name),'err');}
    }catch(_){if(p){p.textContent='✗';p.style.color='var(--red)';}notify('Upload error','err');}
  };
  xhr.onerror=()=>notify('Network error: '+file.name,'err');
  xhr.open('POST','/api/upload');xhr.send(fd);
}
async function loadSubdirs(){
  try{
    const data=await fetch('/api/subdirs').then(r=>r.json());
    const sel=document.getElementById('upload-subdir');
    sel.innerHTML='<option value="">/ (media root)</option>';
    (data.dirs||[]).filter(d=>d).forEach(d=>{
      const o=document.createElement('option');o.value=d;o.textContent=d;sel.appendChild(o);
    });
    if(data.root_label)document.getElementById('upload-root-label').textContent=data.root_label;
  }catch(_){}
}
async function createSubdir(){
  const name=prompt('New folder name (no special characters):');
  if(!name||!name.trim())return;
  if(/[\/\\<>"|?*\x00]/.test(name)||name.includes('..')){notify('Invalid folder name','err');return;}
  const r=await api('create_subdir',{name:name.trim()});
  if(r&&r.ok)loadSubdirs();
}

// ════════════════════════════════════════════════════════════
// LIBRARY
// ════════════════════════════════════════════════════════════
async function loadLibrary(){
  const tb=document.getElementById('libtbl');
  tb.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:28px">Loading…</td></tr>';
  try{libData=await fetch('/api/library').then(r=>r.json());filterLib();}
  catch(e){tb.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--red);padding:28px">Failed to load library</td></tr>';}
}
function filterLib(){
  const q=document.getElementById('lib-search').value.toLowerCase();
  const srt=document.getElementById('lib-sort').value;
  let data=libData.filter(f=>f.path.toLowerCase().includes(q));
  if(srt==='size')data.sort((a,b)=>b.size_bytes-a.size_bytes);
  else if(srt==='dur')data.sort((a,b)=>b.duration_secs-a.duration_secs);
  else data.sort((a,b)=>a.path.localeCompare(b.path));
  renderLib(data);
}
function renderLib(data){
  const tb=document.getElementById('libtbl');
  if(!data.length){tb.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:28px">No files found.</td></tr>';return;}
  tb.innerHTML=data.map(f=>`
<tr>
  <td class="mono" style="word-break:break-all;font-size:11px;max-width:340px" title="${esc(f.full_path)}">${esc(f.path)}</td>
  <td class="mono" style="white-space:nowrap;color:var(--cyan)">${esc(f.duration)||'--'}</td>
  <td class="mono" style="white-space:nowrap;color:var(--muted)">${esc(f.size)||'--'}</td>
  <td style="font-size:11.5px;color:var(--muted)">${esc(f.video_codec)||'--'}</td>
  <td style="font-size:11.5px;color:var(--muted)">${f.width&&f.height?f.width+'×'+f.height:'--'}</td>
  <td style="font-size:11.5px;color:var(--muted)">${f.fps?f.fps+' fps':'--'}</td>
  <td style="white-space:nowrap">
    <button class="btn btn-xs" onclick="copyURL('${esc(f.full_path)}')" title="Copy path">📋</button>
    <button class="btn btn-xs btn-danger" onclick="delFile('${esc(f.full_path)}')" title="Delete">🗑</button>
  </td>
</tr>`).join('');
}
async function delFile(path){
  if(!confirm('Permanently delete?\n'+path))return;
  const r=await api('delete_file',{path});
  if(r&&r.ok)loadLibrary();
}

// ════════════════════════════════════════════════════════════
// CONFIG EDITOR
// ════════════════════════════════════════════════════════════
async function loadEditor(){
  try{editorRows=await fetch('/api/streams_config').then(r=>r.json());renderEditor();}
  catch(e){notify('Failed to load config','err');}
}
function renderEditor(){
  const c=document.getElementById('editor-body');
  if(!editorRows.length){c.innerHTML='<p style="color:var(--muted);text-align:center;padding:28px">No streams configured. Click "+ Add Stream" to start.</p>';return;}
  c.innerHTML=editorRows.map((row,idx)=>`
  <div class="editor-card">
    <div class="editor-card-hdr">
      <span class="editor-card-name">${esc(row.name||'Stream '+(idx+1))}</span>
      <span style="margin-left:auto;display:flex;gap:6px">
        <button class="btn btn-xs" onclick="openPrioForEditor(${idx})" title="Reorder playlist">🎯 Order</button>
        <button class="btn btn-xs btn-danger" onclick="removeEdRow(${idx})">✕ Remove</button>
      </span>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>Stream Name</label>
        <input type="text" value="${esc(row.name||'')}" oninput="editorRows[${idx}].name=this.value;this.closest('.editor-card').querySelector('.editor-card-name').textContent=this.value||'(unnamed)'">
      </div>
      <div class="form-group" style="flex:0 0 120px">
        <label>RTSP Port</label>
        <input type="number" min="1024" max="65535" value="${row.port||8554}" oninput="editorRows[${idx}].port=+this.value">
      </div>
      <div class="form-group" style="flex:0 0 120px">
        <label>Stream Path</label>
        <input type="text" value="${esc(row.stream_path||'stream')}" oninput="editorRows[${idx}].stream_path=this.value">
      </div>
      <div class="form-group" style="flex:0 0 120px">
        <label>Weekdays</label>
        <input type="text" value="${esc(row.weekdays||'all')}" oninput="editorRows[${idx}].weekdays=this.value">
      </div>
      <div class="form-group" style="flex:0 0 100px">
        <label>Video BR</label>
        <input type="text" value="${esc(row.video_bitrate||'2500k')}" oninput="editorRows[${idx}].video_bitrate=this.value">
      </div>
      <div class="form-group" style="flex:0 0 100px">
        <label>Audio BR</label>
        <input type="text" value="${esc(row.audio_bitrate||'128k')}" oninput="editorRows[${idx}].audio_bitrate=this.value">
      </div>
    </div>
    <div class="form-row" style="gap:20px;margin-bottom:10px">
      <label class="checkbox-row"><input type="checkbox" ${row.enabled?'checked':''} onchange="editorRows[${idx}].enabled=this.checked"><span>Enabled</span></label>
      <label class="checkbox-row"><input type="checkbox" ${row.shuffle?'checked':''} onchange="editorRows[${idx}].shuffle=this.checked"><span>Shuffle</span></label>
      <label class="checkbox-row"><input type="checkbox" ${row.hls_enabled?'checked':''} onchange="editorRows[${idx}].hls_enabled=this.checked"><span>HLS enabled</span></label>
    </div>
    <div class="form-group">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
        <label style="margin:0">Playlist Files</label>
        <span class="form-hint">Format: /path/file.mp4@HH:MM:SS#priority  (one per line)</span>
      </div>
      <textarea rows="4" style="font-family:var(--mono);font-size:11px;resize:vertical"
        oninput="editorRows[${idx}].files=this.value">${esc((row.files||'').split(';').join('\n'))}</textarea>
    </div>
  </div>`).join('');
}
function addEditorRow(){
  editorRows.push({name:'NewStream',port:8560,files:'',weekdays:'all',
    enabled:true,shuffle:false,stream_path:'stream',
    video_bitrate:'2500k',audio_bitrate:'128k',hls_enabled:false});
  renderEditor();
  document.getElementById('editor-body').lastElementChild?.scrollIntoView({behavior:'smooth'});
}
function removeEdRow(idx){
  if(!confirm('Remove stream "'+editorRows[idx].name+'"?'))return;
  editorRows.splice(idx,1);renderEditor();
}
function openPrioForEditor(idx){
  prioStreamName=editorRows[idx].name;
  prioOrigFiles=(editorRows[idx].files||'').split(';').filter(f=>f.trim()).map((f,i)=>{
    const hsh=f.lastIndexOf('#'),at=f.lastIndexOf('@');
    const pri=hsh>at?parseInt(f.slice(hsh+1))||i+1:i+1;
    const withoutPri=hsh>at?f.slice(0,hsh):f;
    const path=at>0?withoutPri.slice(0,at):withoutPri;
    const start=at>0?withoutPri.slice(at+1):'00:00:00';
    return{file:path.split('/').pop()||path,path:path.trim(),start:start.trim(),priority:pri,exists:true,current:false};
  });
  document.getElementById('pm-name').textContent=prioStreamName;
  const list=document.getElementById('pm-list');
  list.innerHTML=prioOrigFiles.map((p,i)=>`
    <div class="plist-item" draggable="true" data-idx="${i}" data-path="${esc(p.path)}" data-start="${esc(p.start)}" data-priority="${p.priority}">
      <span class="drag-handle">⠿</span>
      <span class="pi-num">${i+1}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px">${esc(p.file)}</span>
      <span class="mono" style="color:var(--muted);font-size:10px">${esc(p.start)}</span>
      <span class="pi-prio" contenteditable="true">${p.priority}</span>
    </div>`).join('');
  setupDragDrop(list);openModal('prio-modal');
}
async function saveCSV(){
  const rows=editorRows.map(r=>({...r,files:(r.files||'').replace(/\n+/g,';').replace(/;+/g,';').trim()}));
  const ports=rows.map(r=>r.port);
  if(new Set(ports).size!==ports.length){notify('Duplicate port numbers detected!','err');return;}
  const names=rows.map(r=>r.name);
  if(new Set(names).size!==names.length){notify('Duplicate stream names detected!','err');return;}
  const res=await api('save_config',{streams:rows});
  if(res&&res.ok)loadEditor();
}

// ════════════════════════════════════════════════════════════
// EVENTS / SCHEDULER
// ════════════════════════════════════════════════════════════
async function loadEvtForm(){
  try{
    const[streams,lib]=await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/library').then(r=>r.json()),
    ]);
    document.getElementById('evt-stream').innerHTML=streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)} (:${s.port})</option>`).join('');
    document.getElementById('evt-file').innerHTML=lib.map(f=>`<option value="${esc(f.full_path)}">${esc(f.path)}</option>`).join('');
    const dt=new Date(Date.now()+5*60000);
    document.getElementById('evt-dt').value=new Date(dt-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);
    const sel=document.getElementById('log-stream-sel');
    sel.innerHTML='<option value="">All Streams</option>'+streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
  }catch(_){}
}
async function schedEvent(){
  const stream=document.getElementById('evt-stream').value;
  const file=document.getElementById('evt-file').value;
  const dt=document.getElementById('evt-dt').value;
  const pos=document.getElementById('evt-startpos').value||'00:00:00';
  const post=document.getElementById('evt-post').value;
  if(!stream||!file||!dt){notify('Fill all required fields','err');return;}
  if(!/^\d{2}:\d{2}:\d{2}$/.test(pos)){notify('Start position must be HH:MM:SS','err');return;}
  await api('add_event',{stream_name:stream,file_path:file,play_at:dt,start_pos:pos,post_action:post});
  loadEvents();
}
async function loadEvents(){
  try{
    const data=await fetch('/api/events').then(r=>r.json());
    const now=Date.now();
    const tb=document.getElementById('evtbl');
    tb.innerHTML=data.map(ev=>{
      const pa=new Date(ev.play_at.replace(' ','T'));
      const d=((pa-now)/1000).toFixed(0);
      const cd=ev.played?'--':d>0?`in ${Math.floor(d/60)}m ${d%60}s`:`${Math.abs(d)}s ago`;
      return `<tr>
        <td style="font-weight:700;color:var(--blue)">${esc(ev.stream_name)}</td>
        <td class="mono" style="font-size:11px">${esc(ev.file_name)}</td>
        <td class="mono" style="font-size:11px;white-space:nowrap">${esc(ev.play_at)}</td>
        <td class="mono" style="font-size:11px;color:${d>0?'var(--yellow)':'var(--muted)'}">${cd}</td>
        <td style="font-size:11.5px">${esc(ev.post_action)}</td>
        <td><span class="badge ${ev.played?'badge-STOPPED':'badge-SCHED'}"><div class="bdot"></div>${ev.played?'Played':'Pending'}</span></td>
        <td><button class="btn btn-xs btn-danger" onclick="delEvent('${esc(ev.event_id)}')">✕</button></td>
      </tr>`;
    }).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:28px">No events scheduled.</td></tr>';
  }catch(_){}
}
async function delEvent(id){
  if(!confirm('Delete this event?'))return;
  const r=await api('delete_event',{event_id:id});
  if(r&&r.ok)loadEvents();
}
// Batch-delete played events in a single API call instead of N sequential fetches
async function clearPlayed(){
  if(!confirm('Remove all played events?'))return;
  try{
    const evts=await fetch('/api/events').then(r=>r.json());
    const ids=evts.filter(e=>e.played).map(e=>e.event_id);
    if(!ids.length){notify('No played events to clear','info');return;}
    const r=await fetch('/api/delete_played_events',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({event_ids:ids})
    });
    const j=await r.json();
    if(j.ok)notify(j.msg||'Cleared ✓');else notify(j.msg||'Error','err');
    loadEvents();
  }catch(e){notify('Error clearing events: '+e,'err');}
}

// ════════════════════════════════════════════════════════════
// LOGS
// ════════════════════════════════════════════════════════════
function setLogLv(lv){
  logLv=lv;
  document.querySelectorAll('.log-chip').forEach(c=>{
    c.className='log-chip'+(c.dataset.lv===lv?' a-'+lv:'');
  });
  renderLogs();
}
async function loadLogs(){
  try{
    const stream=document.getElementById('log-stream-sel').value;
    const data=await fetch(`/api/logs?level=${logLv}&stream=${encodeURIComponent(stream)}&n=600`).then(r=>r.json());
    logEntries=data.entries||[];renderLogs();
  }catch(_){}
}
function renderLogs(){
  const q=(document.getElementById('log-search').value||'').toLowerCase();
  const el=document.getElementById('log-box');
  el.innerHTML=logEntries
    .filter(([m])=>!q||m.toLowerCase().includes(q))
    .slice().reverse()
    .map(([m,lv])=>`<div class="ll l${lv==='ERROR'?'e':lv==='WARN'?'w':'i'}">${esc(m)}</div>`)
    .join('')||'<span style="color:var(--muted)">No log entries.</span>';
  if(document.getElementById('log-autoscroll').checked)el.scrollTop=0;
}

// ════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════
(async function init(){
  await updateHdrStats();
  loadStreams();
  startRefresh();
  setInterval(()=>{
    updateHdrStats();
    if(document.getElementById('tab-logs').classList.contains('active'))loadLogs();
  },8000);
  // Clock
  setInterval(()=>{
    const now=new Date();
    const el=document.getElementById('h-time');
    if(el)el.textContent=[now.getHours(),now.getMinutes(),now.getSeconds()]
      .map(n=>String(n).padStart(2,'0')).join(':');
  },1000);
})();

// Global keyboard shortcuts
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT')return;
  if(e.key==='Escape')document.querySelectorAll('.modal-overlay.open').forEach(m=>m.classList.remove('open'));
  if(e.key==='r'||e.key==='R'){loadStreams();notify('Refreshed','info');}
});
</script>
</body>
</html>"""


# =============================================================================
# WEB REQUEST HANDLER
# =============================================================================
class WebHandler(BaseHTTPRequestHandler):
    """Handles all HTTP requests for the HydraCast Web UI."""

    def log_message(self, *args: Any) -> None:
        pass  # suppress default Apache-style access log

    # ── Response helpers ──────────────────────────────────────────────────────
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

    # ── HTTP verbs ────────────────────────────────────────────────────────────
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
            "/":                    lambda: self._send(200, _HTML_PAGE, "text/html; charset=utf-8"),
            "/index.html":          lambda: self._send(200, _HTML_PAGE, "text/html; charset=utf-8"),
            "/health":              self._get_health,
            "/api/streams":         self._get_streams,
            "/api/streams_config":  self._get_streams_config,
            "/api/library":         self._get_library,
            "/api/subdirs":         self._get_subdirs,
            "/api/events":          self._get_events,
            "/api/logs":            lambda: self._get_logs(qs),
            "/api/system_stats":    self._get_system_stats,
            "/api/stream_detail":   lambda: self._get_stream_detail(qs),
            "/api/stream_view":     lambda: self._get_stream_view(qs),
            "/api/thumbnail":       lambda: self._get_thumbnail(qs),
        }

        handler = routes.get(path)
        if handler:
            try:
                handler()
            except Exception as exc:
                logging.error("WebHandler GET %s: %s", path, exc)
                self._json({"error": "internal server error"}, 500)
        else:
            self._send(404, b"Not Found", "text/plain")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        ct   = self.headers.get("Content-Type", "")

        if "multipart/form-data" in ct:
            try:
                self._handle_upload()
            except Exception as exc:
                logging.error("Upload error: %s", exc)
                self._json({"ok": False, "msg": f"Upload error: {exc}"}, 500)
            return

        length = int(self.headers.get("Content-Length", 0))
        if length > 4 * 1024 * 1024:
            self._json({"ok": False, "msg": "Request body too large"}, 413)
            return
        raw  = self.rfile.read(length) if length else b"{}"
        try:
            data: Dict[str, Any] = json.loads(raw)
        except Exception:
            self._json({"ok": False, "msg": "Invalid JSON"}, 400)
            return

        action = path.replace("/api/", "").strip("/")
        try:
            self._dispatch(action, data)
        except Exception as exc:
            logging.error("WebHandler POST %s: %s", path, exc)
            self._json({"ok": False, "msg": f"Internal error: {exc}"}, 500)

    # ── GET handlers ─────────────────────────────────────────────────────────
    def _get_health(self) -> None:
        mgr = _WEB_MANAGER
        if mgr is None:
            self._json({"status": "starting", "ready": False}, 503)
            return
        health = mgr.health_summary()
        uptime = ""
        try:
            boot = psutil.boot_time()
            secs = int(time.time() - boot)
            h, rem = divmod(secs, 3600)
            m, s   = divmod(rem,  60)
            uptime = f"{h:02d}:{m:02d}:{s:02d}"
        except Exception:
            pass
        self._json({
            "status":    "ok",
            "ready":     True,
            "timestamp": datetime.now().isoformat(),
            "uptime":    uptime,
            "streams":   health,
        })

    def _get_streams(self) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json([])
            return
        result = []
        for st in mgr.states:
            cfg = st.config
            rem = st.time_remaining()
            result.append({
                "name":           cfg.name,
                "port":           cfg.port,
                "weekdays":       cfg.weekdays_display(),
                "status":         st.status.label,
                "progress":       st.progress,
                "position":       st.format_pos(),
                "current_secs":   st.current_pos,
                "duration":       st.duration,
                "time_remaining": rem,
                "fps":            st.fps,
                "rtsp_url":       cfg.rtsp_url_external,
                "hls_url":        cfg.hls_url if cfg.hls_enabled else "",
                "shuffle":        cfg.shuffle,
                "playlist_count": len(cfg.playlist),
                "playlist":       cfg.playlist_display(),
                "enabled":        cfg.enabled,
                "app_ver":        APP_VER,
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
                "hls_enabled":   cfg.hls_enabled,
            })
        self._json(result)

    def _get_library(self) -> None:
        """Return cached library scan (refreshes at most every 60 s)."""
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
        result = []
        for ev in mgr.events:
            result.append({
                "event_id":    ev.event_id,
                "stream_name": ev.stream_name,
                "file_name":   ev.file_path.name,
                "play_at":     ev.play_at.strftime("%Y-%m-%d %H:%M:%S"),
                "post_action": ev.post_action,
                "played":      ev.played,
            })
        self._json(result)

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
        """System resource stats — also includes web_port so the UI can show it."""
        try:
            cpu  = psutil.cpu_percent(interval=0.15)
            mem  = psutil.virtual_memory()
            disk = psutil.disk_usage(str(BASE_DIR()))
            self._json({
                "cpu":          round(cpu,  1),
                "mem_percent":  round(mem.percent, 1),
                "mem_used":     _fmt_size(mem.used),
                "mem_total":    _fmt_size(mem.total),
                "disk_percent": round(disk.percent, 1),
                "disk_used":    _fmt_size(disk.used),
                "disk_total":   _fmt_size(disk.total),
                # Lazily resolved so --web-port CLI override is reflected correctly
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
        rem = st.time_remaining()
        self._json({
            "name":           cfg.name,
            "port":           cfg.port,
            "rtsp_url":       cfg.rtsp_url_external,
            "hls_url":        cfg.hls_url if cfg.hls_enabled else "",
            "weekdays":       cfg.weekdays_display(),
            "shuffle":        cfg.shuffle,
            "video_bitrate":  cfg.video_bitrate,
            "audio_bitrate":  cfg.audio_bitrate,
            "hls_enabled":    cfg.hls_enabled,
            "status":         st.status.label,
            "progress":       st.progress,
            "current_pos":    st.current_pos,
            "duration":       st.duration,
            "time_remaining": rem,
            "position":       st.format_pos(),
            "fps":            st.fps,
            "bitrate":        st.bitrate,
            "speed":          st.speed,
            "loop_count":     st.loop_count,
            "restart_count":  st.restart_count,
            "error_msg":      st.error_msg,
            "playlist":       playlist,
            "log":            log_snap,
            "started_at":     st.started_at.isoformat() if st.started_at else None,
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
        rem = st.time_remaining()
        self._json({
            "name":           cfg.name,
            "port":           cfg.port,
            "status":         st.status.label,
            "rtsp_url":       cfg.rtsp_url_external,
            "hls_url":        cfg.hls_url if cfg.hls_enabled else "",
            "hls_enabled":    cfg.hls_enabled,
            "current_pos":    st.current_pos,
            "duration":       st.duration,
            "time_remaining": rem,
            "progress":       st.progress,
        })

    def _get_thumbnail(self, qs: Dict[str, Any]) -> None:
        name = qs.get("name", [""])[0].strip()
        mgr  = _WEB_MANAGER
        if not mgr or not name:
            self._json({"error": "bad request"}, 400)
            return
        st = mgr.get_state(name)
        if not st:
            self._json({"error": "stream not found"}, 404)
            return
        cur_file = st.current_file()
        if not cur_file or not cur_file.exists():
            self._json({"error": "no current file"}, 503)
            return
        try:
            seek_secs = float(qs.get("seek_secs", [str(max(5.0, st.current_pos))])[0])
        except ValueError:
            seek_secs = 5.0
        png_bytes = grab_thumbnail(cur_file, seek_secs=seek_secs)
        if not png_bytes:
            self._json({"error": "thumbnail generation failed"}, 503)
            return
        self._send(200, png_bytes, "image/png")

    # ── POST dispatch ────────────────────────────────────────────────────────
    def _dispatch(self, action: str, data: Dict[str, Any]) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json({"ok": False, "msg": "Manager not ready"})
            return

        # ── Stream control ────────────────────────────────────────────────────
        if action == "start":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                mgr.start_stream(st)
                self._json({"ok": True, "msg": f"Starting {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "stop":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                mgr.stop_stream(st)
                self._json({"ok": True, "msg": f"Stopping {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "restart":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                mgr.restart_stream(st)
                self._json({"ok": True, "msg": f"Restarting {st.config.name}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        elif action == "start_all":
            mgr.start_all()
            self._json({"ok": True, "msg": "Starting all streams"})

        elif action == "stop_all":
            mgr.stop_all()
            self._json({"ok": True, "msg": "Stopped all streams"})

        elif action == "skip_next":
            st = mgr.get_state(str(data.get("name", "")))
            if st:
                mgr.skip_next(st)
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
                mgr.seek_stream(st, secs)
                self._json({"ok": True, "msg": f"Seeking to {_fmt_duration(secs)}"})
            else:
                self._json({"ok": False, "msg": "Stream not found"})

        # ── Config save ───────────────────────────────────────────────────────
        elif action == "save_config":
            try:
                streams_data = data.get("streams", [])
                if not isinstance(streams_data, list):
                    raise ValueError("streams must be a list")
                configs: List[StreamConfig] = []
                for row in streams_data:
                    name = str(row.get("name", "")).strip()
                    if not name or len(name) > 64:
                        raise ValueError(f"Invalid stream name: '{name}'")
                    port = int(row.get("port", 0))
                    if not (1024 <= port <= 65535):
                        raise ValueError(f"Port {port} out of range")
                    raw_files = str(row.get("files", "")).replace("\n", ";")
                    playlist  = CSVManager.parse_files(raw_files)
                    configs.append(StreamConfig(
                        name=name, port=port, playlist=playlist,
                        weekdays=CSVManager.parse_weekdays(
                            str(row.get("weekdays", "all"))),
                        enabled=bool(row.get("enabled", True)),
                        shuffle=bool(row.get("shuffle", False)),
                        stream_path=str(row.get("stream_path", "stream")).strip() or "stream",
                        video_bitrate=CSVManager._sanitize_bitrate(
                            str(row.get("video_bitrate", "2500k")), "2500k"),
                        audio_bitrate=CSVManager._sanitize_bitrate(
                            str(row.get("audio_bitrate", "128k")), "128k"),
                        hls_enabled=bool(row.get("hls_enabled", False)),
                    ))
                ports = [c.port for c in configs]
                if len(set(ports)) != len(ports):
                    raise ValueError("Duplicate port numbers detected")
                names_list = [c.name for c in configs]
                if len(set(names_list)) != len(names_list):
                    raise ValueError("Duplicate stream names detected")
                CSVManager.save(configs)
                self._json({"ok": True, "msg": "Config saved. Restart HydraCast to apply."})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        # ── Events ────────────────────────────────────────────────────────────
        elif action == "add_event":
            try:
                import re as _re
                stream_name = str(data.get("stream_name", "")).strip()
                file_path   = str(data.get("file_path",   "")).strip()
                play_at     = str(data.get("play_at",     "")).strip()
                start_pos   = str(data.get("start_pos",   "00:00:00")).strip()
                post_action = str(data.get("post_action", "resume")).strip()

                if post_action not in ("resume", "stop", "black"):
                    post_action = "resume"
                if not _re.fullmatch(r"\d{2}:\d{2}:\d{2}", start_pos):
                    start_pos = "00:00:00"

                dt = None
                for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt = datetime.strptime(play_at, fmt)
                        break
                    except ValueError:
                        continue
                if dt is None:
                    raise ValueError("Invalid datetime format")

                fp   = Path(file_path)
                safe = _safe_path(fp, MEDIA_DIR())
                if safe is None and not fp.exists():
                    raise ValueError("File not found or path unsafe")

                ev = OneShotEvent(
                    event_id=hashlib.md5(
                        f"{stream_name}{play_at}{file_path}".encode()
                    ).hexdigest()[:8],
                    stream_name=stream_name,
                    file_path=fp,
                    play_at=dt,
                    post_action=post_action,
                    start_pos=start_pos,
                )
                CSVManager.add_event(mgr.events, ev)
                self._json({"ok": True, "msg": "Event scheduled"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "delete_event":
            ev_id = str(data.get("event_id", "")).strip()
            if not ev_id:
                self._json({"ok": False, "msg": "Missing event_id"})
                return
            mgr.events = [e for e in mgr.events if e.event_id != ev_id]
            CSVManager.save_events(mgr.events)
            self._json({"ok": True, "msg": "Event deleted"})

        elif action == "delete_played_events":
            """Batch-delete a list of event IDs in one request."""
            ids = data.get("event_ids", [])
            if not isinstance(ids, list):
                self._json({"ok": False, "msg": "event_ids must be a list"})
                return
            id_set = set(str(i).strip() for i in ids)
            before = len(mgr.events)
            mgr.events = [e for e in mgr.events if e.event_id not in id_set]
            removed = before - len(mgr.events)
            CSVManager.save_events(mgr.events)
            self._json({"ok": True, "msg": f"Removed {removed} event(s)"})

        # ── File management ───────────────────────────────────────────────────
        elif action == "delete_file":
            import re as _re
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
                _invalidate_lib_cache()      # force refresh after deletion
                self._json({"ok": True, "msg": f"Deleted {safe.name}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        elif action == "create_subdir":
            import re as _re
            raw = str(data.get("name", "")).strip()
            if not raw or _re.search(r'[/\\<>"|?*\x00]', raw) or ".." in raw:
                self._json({"ok": False, "msg": "Invalid folder name"})
                return
            target = MEDIA_DIR() / raw
            safe   = _safe_path(target, MEDIA_DIR())
            if safe is None:
                self._json({"ok": False, "msg": "Path traversal denied"})
                return
            try:
                safe.mkdir(parents=True, exist_ok=True)
                self._json({"ok": True, "msg": f"Created folder: {raw}"})
            except Exception as exc:
                self._json({"ok": False, "msg": str(exc)})

        else:
            self._json({"ok": False, "msg": f"Unknown action: {action}"}, 404)

    # ── Multipart upload — streaming write (no full-body RAM buffer) ──────────
    def _handle_upload(self) -> None:
        """
        Parse multipart/form-data and stream the file directly to disk.

        Approach: read the raw body once (required for boundary parsing with
        BaseHTTPRequestHandler), then write the file part to disk without
        keeping a second copy in RAM.  For truly giant files a proper chunked
        streaming parser would be needed, but at ≤ UPLOAD_MAX_BYTES this is
        the cleanest solution available without third-party dependencies.
        """
        import re as _re
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > UPLOAD_MAX_BYTES:
                self._json({"ok": False, "msg": "File exceeds 10 GB server limit"}, 413)
                return

            ct = self.headers.get("Content-Type", "")
            boundary: Optional[bytes] = None
            for part in ct.split(";"):
                p = part.strip()
                if p.lower().startswith("boundary="):
                    boundary = p[9:].strip('"').encode("latin-1")
                    break
            if not boundary:
                self._json({"ok": False, "msg": "Missing multipart boundary"})
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

            subdir      = _re.sub(r'[/\\<>"|?*\x00]', '_', subdir)[:128]
            subdir      = _re.sub(r'\.\.', '_', subdir)
            fname_clean = Path(file_name).name
            ext         = Path(fname_clean).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                self._json({"ok": False, "msg": f"Unsupported extension: {ext}"})
                return

            safe_name = _re.sub(r'[^\w.\-]', '_', fname_clean)
            if not safe_name or safe_name.startswith('.'):
                self._json({"ok": False, "msg": "Invalid filename"})
                return

            dest_dir = (MEDIA_DIR() / subdir) if subdir else MEDIA_DIR()
            safe_dir = _safe_path(dest_dir, MEDIA_DIR())
            if safe_dir is None:
                self._json({"ok": False, "msg": "Invalid upload directory"})
                return
            safe_dir.mkdir(parents=True, exist_ok=True)

            dest = safe_dir / safe_name
            # Write via a temp file to avoid partial writes on error
            tmp_path = dest.with_suffix(dest.suffix + ".tmp")
            try:
                tmp_path.write_bytes(file_bytes)
                tmp_path.rename(dest)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

            _invalidate_lib_cache()          # force library refresh after upload
            self._json({
                "ok":  True,
                "msg": f"Saved: {safe_name} → {str(dest.relative_to(BASE_DIR()))}",
            })
        except Exception as exc:
            self._json({"ok": False, "msg": f"Upload error: {exc}"}, 500)


# =============================================================================
# WEB SERVER
# =============================================================================
class _HydraCastHTTPServer(HTTPServer):
    """HTTPServer subclass with SO_REUSEADDR enabled before bind."""
    allow_reuse_address = True   # sets SO_REUSEADDR before server_bind()


class WebServer:
    """Threaded HTTP server that hosts the HydraCast Web UI."""

    def __init__(self, port: int = 8080) -> None:
        self._port   = port
        self._server: Optional[_HydraCastHTTPServer] = None
        self._thread: Optional[threading.Thread]     = None

    def start(self) -> None:
        try:
            self._server = _HydraCastHTTPServer(("0.0.0.0", self._port), WebHandler)
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True, name="webui",
            )
            self._thread.start()
            logging.info("Web UI → http://0.0.0.0:%d", self._port)
        except OSError as exc:
            logging.error(
                "Web UI failed to bind :%d — %s. "
                "Try a different port with --web-port.",
                self._port, exc,
            )
        except Exception as exc:
            logging.error("Web UI failed to start: %s", exc)

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
