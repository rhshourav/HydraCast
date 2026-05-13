"""
hc/web.py  —  Simple, stripped-down Web UI for HydraCast.

Design goals:
  • Zero external dependencies loaded from CDN (no HLS.js, no Google Fonts).
  • One file, no modals, no drag-drop, no fancy animations.
  • Every button does exactly one thing and the response is shown in-page.
  • Polling every 2 s to keep stream table fresh.
  • Logs tab shows the LogBuffer in real time.
  • Config tab shows streams.csv contents as plain text (read-only).
  • Upload tab for media files.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
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

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSVManager compatibility shim
# ---------------------------------------------------------------------------
# web.py was written against CSVManager.  Now that persistence has moved to
# JSONManager the helper methods (parse_files, parse_weekdays, _sanitize_*,
# add_event, save_events) are reproduced here as a thin static class so no
# call-sites in _dispatch need to change.
# ---------------------------------------------------------------------------
import re as _re

class CSVManager:
    """Shim that exposes the subset of the old CSVManager API used by web.py."""

    # ── Persist (delegate straight to JSONManager) ────────────────────────────
    @staticmethod
    def save(configs) -> None:
        JSONManager.save(configs)

    @staticmethod
    def save_events(events) -> None:
        JSONManager._save_events(events)

    @staticmethod
    def add_event(events, ev) -> None:
        """Append *ev* (already-constructed OneShotEvent) and persist."""
        events.append(ev)
        JSONManager._save_events(events)

    # ── Parsing helpers ───────────────────────────────────────────────────────
    @staticmethod
    def parse_files(raw: str):
        """
        Parse a semicolon-or-newline separated list of file entries.
        Each entry: path[@HH:MM:SS][#priority]
        Returns a list of PlaylistItem.
        """
        from hc.models import PlaylistItem
        from pathlib import Path as _Path
        items = []
        for part in _re.split(r"[;\n]+", raw):
            part = part.strip()
            if not part:
                continue
            priority = 0
            if "#" in part:
                part, pri_s = part.rsplit("#", 1)
                try:
                    priority = int(pri_s.strip())
                except ValueError:
                    pass
            start = "00:00:00"
            if "@" in part:
                part, start = part.rsplit("@", 1)
                start = start.strip()
                if not _re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", start):
                    start = "00:00:00"
            fp = _Path(part.strip())
            items.append(PlaylistItem(
                file_path=fp,
                start_position=start,
                priority=priority,
            ))
        return items

    @staticmethod
    def parse_weekdays(raw: str):
        """
        Convert a weekday string to a list of abbreviations, e.g.
        'mon|wed|fri' → ['mon','wed','fri'],  'all' → ['mon','tue',…,'sun'].
        """
        from hc.constants import WEEKDAY_MAP, DAY_ABBR
        raw = raw.strip().lower()
        if raw in ("all", "everyday", ""):
            return [d.lower() for d in DAY_ABBR]
        if raw == "weekdays":
            return ["mon", "tue", "wed", "thu", "fri"]
        if raw == "weekends":
            return ["sat", "sun"]
        result = []
        for part in _re.split(r"[|,\s]+", raw):
            part = part.strip()
            if part in WEEKDAY_MAP:
                idx = WEEKDAY_MAP[part]
                if isinstance(idx, list):
                    result.extend(DAY_ABBR[i].lower() for i in idx)
                else:
                    result.append(DAY_ABBR[idx].lower())
        # deduplicate while preserving order
        seen = set()
        deduped = []
        for d in result:
            if d not in seen:
                seen.add(d)
                deduped.append(d)
        return deduped or [d.lower() for d in DAY_ABBR]

    @staticmethod
    def _sanitize_bitrate(value: str, fallback: str) -> str:
        value = value.strip()
        if _re.fullmatch(r"\d+[kKmM]?", value):
            return value.lower()
        return fallback

    @staticmethod
    def _sanitize_hms(value: str) -> str:
        value = value.strip()
        if _re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", value):
            return value
        return "00:00:00"

# Module-level manager reference (set by hydracast.py)
_WEB_MANAGER: Optional[Any] = None


# =============================================================================
# MINIMAL HTML UI
# =============================================================================
_HTML = r"""
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HydraCast</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

*{box-sizing:border-box;margin:0;padding:0}

/* ── CryptoVault Dark Theme ── */
:root,[data-theme="dark"]{
  --bg:#1c1c1e;
  --bg2:#232325;
  --bg3:#2c2c2e;
  --bg4:#363638;
  --border:#3a3a3c;
  --border2:#505052;
  --text:#f5f0e8;
  --text2:#b8b8b8;
  --text3:#787878;
  --green:#6b8e6b;
  --green-dim:rgba(107,142,107,0.15);
  --red:#c27878;
  --red-dim:rgba(194,120,120,0.15);
  --yellow:#c9a878;
  --yellow-dim:rgba(201,168,120,0.15);
  --blue:#7a9fc2;
  --blue-dim:rgba(122,159,194,0.12);
  --cyan:#7ab8c2;
  --purple:#9a8ab0;
  --purple-dim:rgba(154,138,176,0.15);
  --accent:#b87333;
  --accent-light:#d4945a;
  --accent-gradient:linear-gradient(135deg,#b87333 0%,#d4945a 50%,#c9845a 100%);
  --accent-gradient-hover:linear-gradient(135deg,#c9845a 0%,#daa57a 50%,#d4945a 100%);
  --shadow:rgba(0,0,0,0.35);
  --font-sans:'Inter',system-ui,sans-serif;
  --font-display:'Plus Jakarta Sans',system-ui,sans-serif;
  --font-mono:'JetBrains Mono',monospace;
  --radius:10px;
  --radius-lg:14px;
}

/* ── CryptoVault Light Theme ── */
[data-theme="light"]{
  --bg:#f2f2f4;
  --bg2:#ffffff;
  --bg3:#f7f7f9;
  --bg4:#ebebed;
  --border:#dcdcde;
  --border2:#c0c0c2;
  --text:#1c1c1e;
  --text2:#525252;
  --text3:#9a9a9a;
  --green:#4a7a4a;
  --green-dim:rgba(74,122,74,0.10);
  --red:#a85050;
  --red-dim:rgba(168,80,80,0.10);
  --yellow:#9a7030;
  --yellow-dim:rgba(154,112,48,0.10);
  --blue:#4a6a8a;
  --blue-dim:rgba(74,106,138,0.10);
  --cyan:#3a7a8a;
  --purple:#6a5a7a;
  --purple-dim:rgba(106,90,122,0.10);
  --accent:#b87333;
  --accent-light:#c9845a;
  --accent-gradient:linear-gradient(135deg,#b87333 0%,#d4945a 50%,#c9845a 100%);
  --accent-gradient-hover:linear-gradient(135deg,#c9845a 0%,#daa57a 50%,#d4945a 100%);
  --shadow:rgba(0,0,0,0.07);
  --font-sans:'Inter',system-ui,sans-serif;
  --font-display:'Plus Jakarta Sans',system-ui,sans-serif;
  --font-mono:'JetBrains Mono',monospace;
  --radius:10px;
  --radius-lg:14px;
}

/* ─────────── KEYFRAMES ─────────── */
@keyframes pulse{
  0%,100%{opacity:1;transform:scale(1)}
  50%{opacity:0.45;transform:scale(0.82)}
}
@keyframes fadeSlideIn{
  from{opacity:0;transform:translateY(10px)}
  to{opacity:1;transform:translateY(0)}
}
@keyframes fadeIn{
  from{opacity:0}to{opacity:1}
}
@keyframes shimmer{
  0%{background-position:-200% 0}
  100%{background-position:200% 0}
}
@keyframes spin{
  from{transform:rotate(0deg)}to{transform:rotate(360deg)}
}
@keyframes slideUp{
  from{opacity:0;transform:translateY(16px)}
  to{opacity:1;transform:translateY(0)}
}
@keyframes logEntry{
  from{opacity:0;transform:translateX(-6px)}
  to{opacity:1;transform:translateX(0)}
}
@keyframes borderGlow{
  0%,100%{box-shadow:0 0 0 0 rgba(184,115,51,0)}
  50%{box-shadow:0 0 0 3px rgba(184,115,51,0.15)}
}
@keyframes iconBounce{
  0%,100%{transform:translateY(0)}
  40%{transform:translateY(-4px)}
  70%{transform:translateY(-2px)}
}

html{background:var(--bg);transition:background 0.35s}
body{
  background:var(--bg);color:var(--text);
  font-family:var(--font-sans);font-size:14px;line-height:1.6;
  min-height:100vh;overflow-x:hidden;
  transition:background 0.35s,color 0.35s;
  -webkit-font-smoothing:antialiased;
}
a{color:var(--accent-light);text-decoration:none;transition:color 0.2s}
a:hover{color:var(--accent)}
::selection{background:rgba(184,115,51,0.28);color:var(--text)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:10px}
::-webkit-scrollbar-thumb:hover{background:var(--text3)}

/* ─────────── LAYOUT ─────────── */
.app{display:flex;flex-direction:column;height:100vh;overflow:hidden}

/* ─────────── TOP BAR ─────────── */
.topbar{
  background:var(--bg2);
  border-bottom:1px solid var(--border);
  padding:0 24px;
  display:flex;align-items:center;gap:0;
  height:60px;
  flex-shrink:0;
  position:relative;
  z-index:100;
  transition:background 0.35s,border-color 0.35s;
  box-shadow:0 1px 0 var(--border),0 2px 12px var(--shadow);
}
.topbar::after{
  content:'';position:absolute;bottom:0;left:0;right:0;height:2px;
  background:var(--accent-gradient);
  opacity:0.55;
}

.logo{
  display:flex;align-items:center;gap:12px;
  font-family:var(--font-display);font-weight:800;font-size:20px;
  color:var(--text);letter-spacing:-0.3px;
  margin-right:28px;white-space:nowrap;
}
.logo-icon{
  width:36px;height:36px;
  background:var(--accent-gradient);
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  font-size:15px;font-weight:900;color:#fff;flex-shrink:0;
  box-shadow:0 3px 10px rgba(184,115,51,0.35);
  transition:transform 0.2s,box-shadow 0.2s;
}
.logo-icon:hover{transform:scale(1.08);box-shadow:0 5px 16px rgba(184,115,51,0.45)}
.logo sub{
  font-family:var(--font-mono);font-size:11px;color:var(--text3);
  font-weight:400;vertical-align:middle;margin-left:3px;
}

.nav-tabs{display:flex;gap:2px;align-items:stretch;height:100%;flex:1}
.nav-tab{
  background:none;border:none;color:var(--text3);cursor:pointer;
  font-family:var(--font-sans);font-weight:500;font-size:13px;padding:0 18px;
  border-bottom:2px solid transparent;
  display:flex;align-items:center;gap:7px;
  transition:all 0.22s;white-space:nowrap;
  letter-spacing:0.01em;position:relative;
}
.nav-tab:hover{color:var(--text2);background:rgba(184,115,51,0.06)}
.nav-tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.nav-tab .tab-dot{
  width:5px;height:5px;border-radius:50%;background:currentColor;
  opacity:0;transition:opacity 0.22s;flex-shrink:0;
}
.nav-tab.active .tab-dot{opacity:1;animation:pulse 2.5s ease-in-out infinite}

.topbar-right{
  margin-left:auto;display:flex;align-items:center;gap:8px;
}
.stat-pill{
  display:flex;align-items:center;gap:7px;
  background:var(--bg3);border:1px solid var(--border);
  border-radius:20px;padding:5px 13px;font-size:12px;font-weight:500;
  color:var(--text3);transition:background 0.35s,border-color 0.35s;
  font-family:var(--font-sans);
}
.stat-pill b{color:var(--text);font-weight:600}
.stat-pill.live{border-color:rgba(107,142,107,0.35)}
.stat-pill.live b{color:var(--green)}
.pulse-dot{
  display:inline-block;width:7px;height:7px;border-radius:50%;
  background:var(--green);
  box-shadow:0 0 0 0 rgba(107,142,107,0.6);
  animation:livePulse 2.2s ease-out infinite;
}
@keyframes livePulse{
  0%{box-shadow:0 0 0 0 rgba(107,142,107,0.55)}
  70%{box-shadow:0 0 0 6px rgba(107,142,107,0)}
  100%{box-shadow:0 0 0 0 rgba(107,142,107,0)}
}
/* keep .pulse alias for badge usage */
.pulse{display:inline-block;width:5px;height:5px;border-radius:50%;
  background:currentColor;animation:pulse 2s infinite}

/* ─────────── THEME TOGGLE ─────────── */
.theme-btn{
  width:38px;height:38px;
  background:var(--bg3);border:1px solid var(--border);
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  cursor:pointer;font-size:16px;transition:all 0.22s;flex-shrink:0;
}
.theme-btn:hover{
  background:rgba(184,115,51,0.12);border-color:var(--accent);
  transform:rotate(12deg) scale(1.05);
}

.topbar-btns{display:flex;gap:6px}
.hbtn{
  background:var(--bg3);border:1px solid var(--border);color:var(--text2);
  cursor:pointer;font:500 12px var(--font-sans);padding:7px 14px;border-radius:20px;
  display:inline-flex;align-items:center;gap:6px;
  transition:all 0.22s;white-space:nowrap;letter-spacing:0.01em;
}
.hbtn:hover{border-color:var(--border2);color:var(--text);background:var(--bg4);transform:translateY(-1px)}
.hbtn.g{border-color:rgba(107,142,107,0.5);color:var(--green);background:var(--green-dim)}
.hbtn.g:hover{background:rgba(107,142,107,0.25)}
.hbtn.r{border-color:rgba(194,120,120,0.5);color:var(--red);background:var(--red-dim)}
.hbtn.r:hover{background:rgba(194,120,120,0.25)}

/* ─────────── MAIN AREA ─────────── */
.main-area{flex:1;overflow:hidden;display:flex;flex-direction:column}
.tab-panel{display:none;flex:1;overflow:auto;padding:24px}
.tab-panel.active{
  display:flex;flex-direction:column;gap:20px;
  animation:fadeSlideIn 0.28s ease both;
}

/* ─────────── SECTION HEADER ─────────── */
.section-hdr{
  display:flex;align-items:center;gap:12px;margin-bottom:4px;
}
.section-hdr h2{
  font-family:var(--font-display);font-size:11px;font-weight:700;
  color:var(--text3);letter-spacing:0.12em;text-transform:uppercase;
}
.section-hdr .sep{flex:1;height:1px;background:var(--border);margin-left:4px}
.count-badge{
  font-size:11px;font-weight:600;
  background:var(--bg3);border:1px solid var(--border);
  color:var(--text3);border-radius:20px;padding:2px 10px;
  font-family:var(--font-sans);
}

/* ─────────── CARD ─────────── */
.card{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  overflow:hidden;transition:background 0.35s,border-color 0.35s,box-shadow 0.25s;
  box-shadow:0 1px 4px var(--shadow);
  animation:fadeIn 0.25s ease both;
}
.card:hover{box-shadow:0 4px 16px var(--shadow)}
.card-hdr{
  padding:14px 20px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:10px;
  background:var(--bg3);
}
.card-hdr h3{
  font-family:var(--font-display);font-size:12px;font-weight:700;
  color:var(--text2);letter-spacing:0.05em;text-transform:uppercase;
}
.card-body{padding:20px}

/* ─────────── TABLE ─────────── */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{
  text-align:left;padding:11px 14px;color:var(--text3);font-weight:600;
  border-bottom:1px solid var(--border);white-space:nowrap;font-size:11px;
  text-transform:uppercase;letter-spacing:0.08em;background:var(--bg3);
  font-family:var(--font-display);transition:background 0.35s;
}
td{
  padding:12px 14px;border-bottom:1px solid var(--border);
  vertical-align:middle;transition:background 0.18s;
  font-family:var(--font-sans);
}
tr{animation:fadeIn 0.2s ease both}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(184,115,51,0.045)}
.td-name{font-weight:600;color:var(--text);font-family:var(--font-display)}
.td-muted{color:var(--text3);font-size:12px}

/* ─────────── BUTTONS ─────────── */
.btn{
  background:var(--bg3);border:1px solid var(--border);color:var(--text2);
  cursor:pointer;font:500 12px var(--font-sans);padding:6px 13px;border-radius:8px;
  display:inline-flex;align-items:center;gap:5px;white-space:nowrap;
  transition:all 0.2s;letter-spacing:0.01em;
}
.btn:hover{
  border-color:var(--accent);color:var(--accent);
  background:rgba(184,115,51,0.09);transform:translateY(-1px);
}
.btn:active{transform:translateY(0)}
.btn.g{border-color:rgba(107,142,107,0.5);color:var(--green);background:var(--green-dim)}
.btn.g:hover{background:rgba(107,142,107,0.22);border-color:var(--green)}
.btn.r{border-color:rgba(194,120,120,0.5);color:var(--red);background:var(--red-dim)}
.btn.r:hover{background:rgba(194,120,120,0.22);border-color:var(--red)}
.btn.b{border-color:rgba(122,159,194,0.4);color:var(--blue);background:var(--blue-dim)}
.btn.b:hover{background:rgba(122,159,194,0.2);border-color:var(--blue)}
.btn.y{border-color:rgba(201,168,120,0.4);color:var(--yellow);background:var(--yellow-dim)}
.btn.y:hover{background:rgba(201,168,120,0.22);border-color:var(--yellow)}
.btn.p{border-color:rgba(154,138,176,0.4);color:var(--purple);background:var(--purple-dim)}
.btn.p:hover{background:rgba(154,138,176,0.22);border-color:var(--purple)}
.btn-group{display:flex;gap:4px;flex-wrap:wrap}

/* ─────────── BADGE ─────────── */
.badge{
  display:inline-flex;align-items:center;gap:5px;
  font-size:11px;font-weight:600;
  padding:3px 10px;border-radius:20px;letter-spacing:0.04em;
  white-space:nowrap;font-family:var(--font-sans);
}
.LIVE{background:var(--green-dim);color:var(--green);border:1px solid rgba(107,142,107,0.4)}
.LIVE::before{
  content:'';width:6px;height:6px;border-radius:50%;background:var(--green);
  display:inline-block;box-shadow:0 0 0 0 rgba(107,142,107,0.6);
  animation:livePulse 2.2s ease-out infinite;
}
.STOPPED{background:rgba(100,100,100,0.09);color:var(--text3);border:1px solid var(--border)}
.STARTING{background:var(--yellow-dim);color:var(--yellow);border:1px solid rgba(201,168,120,0.4)}
.ERROR{background:var(--red-dim);color:var(--red);border:1px solid rgba(194,120,120,0.4)}
.SCHED{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(122,159,194,0.3)}
.DISABLED{background:rgba(100,100,100,0.07);color:var(--text3);border:1px solid var(--border)}
.ONESHOT{background:var(--purple-dim);color:var(--purple);border:1px solid rgba(154,138,176,0.4)}

/* ─────────── PROGRESS ─────────── */
.prog{
  height:5px;background:var(--bg4);border-radius:3px;
  overflow:hidden;min-width:110px;position:relative;
}
.prog-fill{
  height:100%;border-radius:3px;background:var(--green);
  transition:width .6s cubic-bezier(0.4,0,0.2,1);
  position:relative;
}
.prog-fill::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.18) 50%,transparent 100%);
  background-size:200% 100%;
  animation:shimmer 2s linear infinite;
}
.prog-label{font-size:11px;color:var(--text3);margin-top:4px;font-family:var(--font-sans)}

/* ─────────── CHIP / URL ─────────── */
.chip{
  display:inline-flex;align-items:center;gap:5px;
  background:var(--bg3);border:1px solid var(--border);
  border-radius:6px;padding:4px 10px;font-size:11px;color:var(--accent-light);
  cursor:pointer;max-width:210px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;vertical-align:middle;transition:all 0.2s;
  font-family:var(--font-mono);
}
.chip:hover{
  border-color:var(--accent);background:rgba(184,115,51,0.09);
  color:var(--accent);transform:translateY(-1px);
}

/* ─────────── LOGBOX ─────────── */
#logbox{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px;height:460px;overflow-y:auto;font-size:12px;line-height:1.9;
  font-family:var(--font-mono);transition:background 0.35s,border-color 0.35s;
}
.le{color:var(--red)}.lw{color:var(--yellow)}.li{color:var(--text2)}
.log-time{color:var(--text3);margin-right:8px}
.log-row{
  padding:2px 0;border-bottom:1px solid rgba(100,100,100,0.08);
  animation:logEntry 0.15s ease both;
}

/* ─────────── FORMS ─────────── */
.form-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px;align-items:end}
.form-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:end}
.fg{display:flex;flex-direction:column;gap:6px}
label{
  font-size:11px;color:var(--text3);text-transform:uppercase;
  letter-spacing:0.08em;font-weight:600;font-family:var(--font-display);
}
input,select,textarea{
  background:var(--bg3);border:1px solid var(--border);color:var(--text);
  border-radius:var(--radius);padding:9px 13px;
  font:14px var(--font-sans);width:100%;
  transition:border-color 0.2s,box-shadow 0.2s,background 0.35s;
}
input:focus,select:focus,textarea:focus{
  outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(184,115,51,0.13);
  animation:borderGlow 1.5s ease;
}
input::placeholder{color:var(--text3)}
textarea{resize:vertical;min-height:90px;font-family:var(--font-mono);font-size:13px}
select option{background:var(--bg3)}

/* ─────────── UPLOAD ZONE ─────────── */
#dropzone{
  border:2px dashed var(--border);border-radius:var(--radius-lg);padding:48px 40px;
  text-align:center;cursor:pointer;color:var(--text3);
  transition:all 0.25s;background:var(--bg3);
  display:flex;flex-direction:column;align-items:center;gap:10px;
}
#dropzone:hover,#dropzone.over{
  border-color:var(--accent);color:var(--text);
  background:rgba(184,115,51,0.05);transform:scale(1.005);
}
.dz-icon{
  font-size:36px;opacity:0.45;margin-bottom:6px;
  transition:transform 0.25s;
}
#dropzone:hover .dz-icon{animation:iconBounce 0.6s ease}
#uplist{list-style:none;display:flex;flex-direction:column;gap:8px;margin-top:14px}
#uplist li{
  display:flex;align-items:center;gap:12px;font-size:13px;
  background:var(--bg3);border:1px solid var(--border);
  border-radius:var(--radius);padding:10px 14px;
  animation:slideUp 0.2s ease both;
}
.ubar{flex:1;height:4px;background:var(--bg4);border-radius:2px;overflow:hidden}
.ufill{height:100%;background:var(--accent);border-radius:2px;transition:width 0.2s}

/* ─────────── TOAST ─────────── */
#toast{
  position:fixed;bottom:28px;right:28px;z-index:9999;
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:13px 20px;font-size:13px;display:flex;align-items:center;gap:10px;
  transform:translateX(130%);
  transition:transform 0.28s cubic-bezier(0.34,1.56,0.64,1);
  pointer-events:none;min-width:220px;max-width:380px;
  box-shadow:0 10px 40px var(--shadow);
  font-family:var(--font-sans);font-weight:500;
}
#toast.show{transform:translateX(0)}
#toast.err{border-color:rgba(194,120,120,0.65);color:var(--red)}
#toast.ok{border-color:rgba(107,142,107,0.65);color:var(--green)}
#toast.info{border-color:rgba(184,115,51,0.55);color:var(--accent-light)}

/* ─────────── STREAM VIEWER ─────────── */
.viewer-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(330px,1fr));
  gap:16px;
}
.stream-card{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  overflow:hidden;transition:border-color 0.25s,box-shadow 0.25s,transform 0.25s,background 0.35s;
  box-shadow:0 2px 8px var(--shadow);
  animation:slideUp 0.25s ease both;
}
.stream-card:hover{
  border-color:var(--accent);
  box-shadow:0 8px 28px var(--shadow);
  transform:translateY(-2px);
}
.stream-card.is-live{border-color:rgba(107,142,107,0.45)}
.stream-card-header{
  padding:12px 16px;display:flex;align-items:center;gap:10px;
  border-bottom:1px solid var(--border);background:var(--bg3);
}
.stream-card-title{
  font-weight:700;font-size:14px;flex:1;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;font-family:var(--font-display);
}
.stream-preview{
  height:170px;background:var(--bg);display:flex;align-items:center;justify-content:center;
  font-size:12px;color:var(--text3);position:relative;overflow:hidden;
}
.stream-preview canvas{width:100%;height:100%;object-fit:contain}
.stream-preview video{width:100%;height:100%;object-fit:contain;background:#000}
.stream-overlay{
  position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:8px;
  background:rgba(28,28,30,0.78);
  transition:background 0.2s;
}
.stream-play-btn{
  width:50px;height:50px;border-radius:50%;
  background:rgba(184,115,51,0.18);border:2px solid var(--accent);
  display:flex;align-items:center;justify-content:center;
  cursor:pointer;font-size:18px;
  transition:all 0.22s;color:var(--accent);
}
.stream-play-btn:hover{
  background:rgba(184,115,51,0.32);transform:scale(1.12);
  box-shadow:0 0 16px rgba(184,115,51,0.3);
}
.stream-card-footer{
  padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:8px;
}
.stream-stats{display:flex;gap:12px}
.stat-item{font-size:11px;color:var(--text3);font-family:var(--font-sans)}
.stat-item b{color:var(--text2);font-weight:600}

/* ─────────── CONFIG PANEL ─────────── */
.config-layout{display:grid;grid-template-columns:235px 1fr;gap:18px;height:100%}
.config-sidebar{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  overflow:hidden;transition:background 0.35s,border-color 0.35s;
}
.config-sidebar-hdr{
  padding:12px 16px;border-bottom:1px solid var(--border);background:var(--bg3);
  font-size:11px;font-weight:700;text-transform:uppercase;
  letter-spacing:0.1em;color:var(--text3);font-family:var(--font-display);
}
.config-stream-item{
  padding:12px 16px;cursor:pointer;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:10px;transition:background 0.18s;
  font-size:13px;font-family:var(--font-sans);
  animation:fadeIn 0.18s ease both;
}
.config-stream-item:hover{background:var(--bg3)}
.config-stream-item.active{
  background:rgba(184,115,51,0.09);border-left:3px solid var(--accent);
  padding-left:14px;
}
.config-stream-item .dot{
  width:8px;height:8px;border-radius:50%;flex-shrink:0;background:var(--text3);
  transition:background 0.2s,box-shadow 0.2s;
}
.config-stream-item .dot.live{background:var(--green);box-shadow:0 0 6px var(--green)}
.config-stream-item .dot.error{background:var(--red)}
.config-main{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  overflow:hidden;display:flex;flex-direction:column;
  transition:background 0.35s,border-color 0.35s;
}
.config-main-hdr{
  padding:16px 22px;border-bottom:1px solid var(--border);background:var(--bg3);
  display:flex;align-items:center;gap:12px;
}
.config-main-hdr h2{font-family:var(--font-display);font-size:17px;font-weight:700}
.config-main-body{padding:24px;overflow:auto;flex:1}
.config-section{margin-bottom:28px}
.config-section-title{
  font-size:11px;text-transform:uppercase;letter-spacing:0.1em;
  color:var(--accent);font-weight:700;margin-bottom:14px;padding-bottom:8px;
  border-bottom:1px solid var(--border);font-family:var(--font-display);
}
.config-main-footer{
  padding:16px 22px;border-top:1px solid var(--border);background:var(--bg3);
  display:flex;gap:10px;justify-content:flex-end;
}

/* ─────────── SETTINGS ─────────── */
.settings-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}
.setting-card{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:20px;
  transition:background 0.35s,border-color 0.35s,box-shadow 0.25s,transform 0.25s;
  box-shadow:0 1px 4px var(--shadow);
  animation:slideUp 0.25s ease both;
}
.setting-card:hover{box-shadow:0 4px 16px var(--shadow);transform:translateY(-1px)}
.setting-card h3{
  font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;
  color:var(--accent);margin-bottom:16px;padding-bottom:10px;
  border-bottom:1px solid var(--border);font-family:var(--font-display);
}
.setting-row{
  display:flex;justify-content:space-between;align-items:center;
  padding:10px 0;border-bottom:1px solid var(--border);
}
.setting-row:last-child{border-bottom:none}
.setting-label{font-size:13px;color:var(--text2);font-weight:500;font-family:var(--font-sans)}
.setting-desc{font-size:11px;color:var(--text3);margin-top:2px}
.toggle{
  position:relative;width:42px;height:24px;
  background:var(--bg4);border:1px solid var(--border);border-radius:12px;
  cursor:pointer;transition:all 0.25s;flex-shrink:0;
}
.toggle::after{
  content:'';position:absolute;left:3px;top:3px;
  width:16px;height:16px;border-radius:50%;background:var(--text3);
  transition:all 0.25s cubic-bezier(0.34,1.56,0.64,1);
  box-shadow:0 1px 4px rgba(0,0,0,0.2);
}
.toggle.on{background:rgba(184,115,51,0.22);border-color:var(--accent)}
.toggle.on::after{transform:translateX(18px);background:var(--accent)}

/* ─────────── RESPONSIVE ─────────── */
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px}

/* ─────────── SEEK MODAL ─────────── */
.modal-bg{
  position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:1000;
  display:none;align-items:center;justify-content:center;backdrop-filter:blur(6px);
}
.modal-bg.open{display:flex;animation:fadeIn 0.2s ease both}
.modal{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:28px;width:400px;max-width:90vw;
  box-shadow:0 28px 70px var(--shadow);
  transition:background 0.35s,border-color 0.35s;
  animation:slideUp 0.25s cubic-bezier(0.34,1.56,0.64,1) both;
}
.modal h3{
  font-family:var(--font-display);font-size:18px;font-weight:700;
  margin-bottom:18px;color:var(--text);
}
.modal-footer{display:flex;gap:10px;justify-content:flex-end;margin-top:24px}

/* ─────────── INLINE TAGS ─────────── */
.tag-shuf{
  font-size:10px;color:var(--purple);background:var(--purple-dim);
  border:1px solid rgba(154,138,176,0.4);border-radius:20px;
  padding:1px 7px;vertical-align:middle;font-family:var(--font-sans);font-weight:500;
}
.tag-dis{
  font-size:10px;color:var(--text3);background:var(--bg4);
  border:1px solid var(--border);border-radius:20px;
  padding:1px 7px;vertical-align:middle;font-family:var(--font-sans);
}

/* ─────────── EMPTY STATE ─────────── */
.empty{
  padding:56px;text-align:center;color:var(--text3);
  display:flex;flex-direction:column;align-items:center;gap:10px;
  animation:fadeIn 0.3s ease both;
}
.empty-icon{
  font-size:40px;opacity:0.28;margin-bottom:6px;
  animation:iconBounce 3s ease-in-out infinite;
}

/* ─────────── STREAM INFO CHIP ROW ─────────── */
.info-row{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}
.info-chip{
  font-size:11px;background:var(--bg3);border:1px solid var(--border);
  border-radius:6px;padding:3px 10px;color:var(--text3);
  display:flex;align-items:center;gap:4px;font-family:var(--font-sans);
}
.info-chip b{color:var(--accent-light);font-weight:600}

/* ─────────── COPPER ACCENT LINE ─────────── */
.accent-line{
  height:2px;background:var(--accent-gradient);border-radius:2px;
  margin-bottom:18px;opacity:0.5;
}

/* ─────────── APP FOOTER ─────────── */
.app-footer{
  background:var(--bg2);border-top:1px solid var(--border);
  padding:7px 24px;display:flex;align-items:center;justify-content:center;
  gap:10px;font-size:11px;color:var(--text3);flex-shrink:0;
  font-family:var(--font-sans);
  transition:background 0.35s,border-color 0.35s;
  letter-spacing:0.02em;
}
.app-footer a{color:var(--accent-light);transition:color 0.2s}
.app-footer a:hover{color:var(--accent)}
.app-footer .footer-sep{opacity:0.35;margin:0 2px}
.author-badge{
  display:inline-flex;align-items:center;gap:7px;
  background:var(--bg3);border:1px solid var(--border);border-radius:20px;
  padding:3px 11px;transition:all 0.22s;text-decoration:none !important;
}
.author-badge:hover{border-color:var(--accent);background:rgba(184,115,51,0.07)}
.author-ico{
  width:18px;height:18px;border-radius:50%;object-fit:cover;
  flex-shrink:0;border:1px solid var(--border2);
}
.author-name{font-size:11px;color:var(--text2);font-weight:500}

/* ─────────── LOGO IMAGE SUPPORT ─────────── */
.logo-icon{position:relative;overflow:hidden}
.logo-icon img{
  position:absolute;inset:0;width:100%;height:100%;
  object-fit:cover;border-radius:10px;
}
.logo-icon .logo-letter{
  font-size:15px;font-weight:900;color:#fff;
  position:relative;z-index:1;
}

</style>
</head>
<body>

<div class="app">

<!-- ══ TOP BAR ══ -->
<header class="topbar">
  <div class="logo">
    <!--
      ╔══════════════════════════════════════════════════════╗
      ║  LOGO PLACEHOLDER                                    ║
      ║  To add your own logo image:                         ║
      ║    document.getElementById('logo-img').src =         ║
      ║      '/your-logo.png';                               ║
      ║  The fallback "LOGO" text hides automatically when   ║
      ║  the image loads.                                    ║
      ╚══════════════════════════════════════════════════════╝
    -->
    <div class="logo-icon" id="logo-icon-wrap"
         title="Add your logo — see HTML comment above"
         style="cursor:default">
      <img id="logo-img" src="" alt=""
           style="display:none;position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:10px"
           onload="this.style.display='block';document.getElementById('logo-letter').style.display='none'"
           onerror="this.style.display='none';document.getElementById('logo-letter').style.display=''">
      <span class="logo-letter" id="logo-letter"
            style="font-size:8px;font-weight:700;letter-spacing:0.06em;color:rgba(255,255,255,0.75);text-transform:uppercase;pointer-events:none;user-select:none;position:relative;z-index:1">
        LOGO
      </span>
    </div>
    HydraCast
    <sub id="ver-badge">v—</sub>
  </div>

  <nav class="nav-tabs">
    <button class="nav-tab active" onclick="switchTab('streams',this)">
      <span class="tab-dot"></span>Streams
    </button>
    <button class="nav-tab" onclick="switchTab('viewer',this)">
      <span class="tab-dot"></span>Viewer
    </button>
    <button class="nav-tab" onclick="switchTab('logs',this)">
      <span class="tab-dot"></span>Logs
    </button>
    <button class="nav-tab" onclick="switchTab('upload',this)">
      <span class="tab-dot"></span>Upload
    </button>
    <button class="nav-tab" onclick="switchTab('events',this)">
      <span class="tab-dot"></span>Events
    </button>
    <button class="nav-tab" onclick="switchTab('config',this)">
      <span class="tab-dot"></span>Configure
    </button>
    <button class="nav-tab" onclick="switchTab('settings',this)">
      <span class="tab-dot"></span>Settings
    </button>
  </nav>

  <div class="topbar-right">
    <div class="stat-pill live">
      <span class="pulse"></span>
      LIVE <b id="h-live">0</b>
    </div>
    <div class="stat-pill">CPU <b id="h-cpu">—</b></div>
    <div class="stat-pill">RAM <b id="h-ram">—</b></div>
    <div class="stat-pill" style="font-variant-numeric:tabular-nums"><b id="h-time">—</b></div>
    <button class="theme-btn" id="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">☽</button>
    <div class="topbar-btns">
      <button class="hbtn g" onclick="api('start_all',{})">▶ All</button>
      <button class="hbtn r" onclick="api('stop_all',{})">■ All</button>
    </div>
  </div>
</header>

<!-- ══ STREAMS TAB ══ -->
<div id="tab-streams" class="tab-panel active">
  <div class="section-hdr">
    <h2>Live Streams</h2>
    <span class="sep"></span>
    <label style="font-size:11px;color:var(--text3);display:flex;align-items:center;gap:6px;cursor:pointer">
      <input type="checkbox" id="auto-ref" checked onchange="toggleAuto(this.checked)" style="width:auto">
      Auto-refresh
    </label>
    <button class="btn b" onclick="loadStreams()">↻ Refresh</button>
  </div>
  <div class="card">
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Stream</th>
            <th>Port</th>
            <th>Status</th>
            <th style="min-width:140px">Progress</th>
            <th>Position</th>
            <th>FPS</th>
            <th>Loop</th>
            <th>Bitrate</th>
            <th>RTSP URL</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="stbl">
          <tr><td colspan="11" class="empty"><div class="empty"><div class="empty-icon">📡</div>Loading streams…</div></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ VIEWER TAB ══ -->
<div id="tab-viewer" class="tab-panel">
  <div class="section-hdr">
    <h2>Stream Viewer</h2>
    <span class="sep"></span>
    <button class="btn b" onclick="loadViewer()">↻ Refresh</button>
  </div>
  <div id="viewer-grid" class="viewer-grid">
    <div class="empty"><div class="empty-icon">📺</div>Switch to this tab to load viewers…</div>
  </div>
</div>

<!-- ══ LOGS TAB ══ -->
<div id="tab-logs" class="tab-panel">
  <div class="section-hdr">
    <h2>Event Log</h2>
    <span class="sep"></span>
    <select id="log-stream" style="width:160px" onchange="loadLogs()">
      <option value="">All streams</option>
    </select>
    <select id="log-level" style="width:110px" onchange="loadLogs()">
      <option value="ALL">ALL</option>
      <option value="INFO">INFO</option>
      <option value="WARN">WARN</option>
      <option value="ERROR">ERROR</option>
    </select>
    <button class="btn b" onclick="loadLogs()">↻</button>
    <label style="font-size:11px;color:var(--text3);display:flex;align-items:center;gap:6px;cursor:pointer">
      <input type="checkbox" id="log-auto" checked style="width:auto"> Auto-scroll
    </label>
  </div>
  <div id="logbox"></div>
</div>

<!-- ══ UPLOAD TAB ══ -->
<div id="tab-upload" class="tab-panel">
  <div class="section-hdr"><h2>Upload Media</h2><span class="sep"></span></div>
  <div class="card card-body" style="padding:16px">
    <div class="row" style="margin-bottom:16px">
      <div class="fg" style="max-width:280px">
        <label>Destination Sub-folder</label>
        <select id="upload-subdir"></select>
      </div>
      <button class="btn" onclick="mkSubdir()" style="margin-top:16px">＋ New folder</button>
    </div>
    <div id="dropzone" onclick="document.getElementById('fpick').click()">
      <div class="dz-icon">⬆</div>
      <div style="font-size:14px;font-weight:600;color:var(--text2)">Drop files or click to browse</div>
      <div style="font-size:11px">MP4 MKV AVI MOV TS FLV WMV WEBM MPG · MP3 AAC FLAC WAV OGG — max 10 GB</div>
    </div>
    <input type="file" id="fpick" multiple accept="video/*,audio/*" style="display:none" onchange="doUpload(this.files)">
    <ul id="uplist"></ul>
  </div>
</div>

<!-- ══ EVENTS TAB ══ -->
<div id="tab-events" class="tab-panel">
  <div class="section-hdr"><h2>Schedule Event</h2><span class="sep"></span></div>
  <div class="card">
    <div class="card-hdr"><h3>One-Shot Event</h3></div>
    <div class="card-body">
      <div class="form-grid" style="margin-bottom:12px">
        <div class="fg"><label>Stream *</label><select id="ev-stream"></select></div>
        <div class="fg"><label>Video File *</label><select id="ev-file"></select></div>
        <div class="fg"><label>Play at (local time) *</label><input type="datetime-local" id="ev-dt"></div>
        <div class="fg"><label>Start position (HH:MM:SS)</label><input type="text" id="ev-pos" value="00:00:00" placeholder="00:00:00"></div>
        <div class="fg"><label>After playback</label>
          <select id="ev-post">
            <option value="resume">Resume playlist</option>
            <option value="stop">Stop stream</option>
            <option value="black">Black screen</option>
          </select>
        </div>
        <div class="fg" style="justify-content:flex-end">
          <label>&nbsp;</label>
          <button class="btn g" onclick="schedEvent()">✓ Schedule</button>
        </div>
      </div>
    </div>
  </div>

  <div class="section-hdr">
    <h2>Scheduled Events</h2>
    <span class="sep"></span>
    <select id="ev-filter-stream" onchange="renderEventsTable()"
      style="background:var(--bg3);border:1px solid var(--border);color:var(--text2);
             border-radius:var(--radius);padding:5px 10px;font-size:12px;font-family:var(--font-sans)">
      <option value="">All streams</option>
    </select>
    <select id="ev-filter-status" onchange="renderEventsTable()"
      style="background:var(--bg3);border:1px solid var(--border);color:var(--text2);
             border-radius:var(--radius);padding:5px 10px;font-size:12px;font-family:var(--font-sans)">
      <option value="">All statuses</option>
      <option value="pending">Pending</option>
      <option value="played">Played</option>
    </select>
    <button class="btn r" onclick="clearPlayed()">✕ Clear Played</button>
    <button class="btn b" onclick="loadEvents()">↻</button>
    <label style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text3);cursor:pointer">
      <input type="checkbox" id="ev-autoref" checked style="width:auto;accent-color:var(--accent)"> Live
    </label>
  </div>
  <div class="card">
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Stream</th><th>File</th><th>Play At</th>
          <th>Countdown</th><th>After</th><th>Status</th><th style="text-align:right">Actions</th>
        </tr></thead>
        <tbody id="evtbl"><tr><td colspan="7"><div class="empty"><div class="empty-icon">📅</div>Loading…</div></td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ CONFIGURE TAB ══ -->
<div id="tab-config" class="tab-panel">
  <div class="section-hdr">
    <h2>Stream Configuration</h2>
    <span class="sep"></span>
    <button class="btn b" onclick="loadConfig()">↻ Reload</button>
  </div>
  <div class="config-layout">
    <div class="config-sidebar">
      <div class="config-sidebar-hdr" style="display:flex;align-items:center;justify-content:space-between">
        <span>Streams</span>
        <button class="btn g" style="padding:2px 8px;font-size:10px;border-radius:5px" onclick="showNewStreamForm()">＋ New</button>
      </div>
      <div id="config-stream-list"></div>
    </div>
    <div class="config-main">
      <div class="config-main-hdr" id="config-main-hdr">
        <h2 style="color:var(--text3);font-size:14px">Select a stream</h2>
      </div>
      <div class="config-main-body" id="config-main-body">
        <div class="empty"><div class="empty-icon">⚙</div>Select a stream from the sidebar to configure it.</div>
      </div>
      <div class="config-main-footer" id="config-main-footer" style="display:none">
        <button class="btn" onclick="cancelConfig()">Cancel</button>
        <button class="btn g" onclick="saveConfig()">Save Changes</button>
      </div>
    </div>
  </div>
</div>

<!-- ══ SETTINGS TAB ══ -->
<div id="tab-settings" class="tab-panel">
  <div class="section-hdr"><h2>Application Settings</h2><span class="sep"></span></div>
  <div class="settings-grid">
    <!-- UI Preferences -->
    <div class="setting-card">
      <h3>UI Preferences</h3>
      <div class="setting-row">
        <div><div class="setting-label">Auto-refresh streams</div><div class="setting-desc">Poll every 2.5 seconds</div></div>
        <div class="toggle on" id="st-autoref" onclick="toggleSetting('autoref',this)"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Auto-scroll logs</div><div class="setting-desc">Jump to newest log entry</div></div>
        <div class="toggle on" id="st-autoscroll" onclick="toggleSetting('autoscroll',this)"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Compact stream table</div><div class="setting-desc">Reduce row padding</div></div>
        <div class="toggle" id="st-compact" onclick="toggleSetting('compact',this)"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Show RTSP chip</div><div class="setting-desc">Display URL in stream table</div></div>
        <div class="toggle on" id="st-showrtsp" onclick="toggleSetting('showrtsp',this)"></div>
      </div>
    </div>

    <!-- Notifications -->
    <div class="setting-card">
      <h3>Notifications</h3>
      <div class="setting-row">
        <div><div class="setting-label">Toast on stream start</div><div class="setting-desc">Show notification when stream goes LIVE</div></div>
        <div class="toggle on" id="st-notif-start" onclick="toggleSetting('notifStart',this)"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Toast on stream error</div><div class="setting-desc">Alert when ERROR status detected</div></div>
        <div class="toggle on" id="st-notif-err" onclick="toggleSetting('notifErr',this)"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Event countdown alerts</div><div class="setting-desc">Warn 1 min before scheduled event</div></div>
        <div class="toggle" id="st-notif-event" onclick="toggleSetting('notifEvent',this)"></div>
      </div>
    </div>

    <!-- Refresh Intervals -->
    <div class="setting-card">
      <h3>Refresh Intervals</h3>
      <div class="setting-row">
        <div class="setting-label">Stream poll interval</div>
        <select id="st-poll-interval" onchange="applyPollInterval()" style="width:100px">
          <option value="1500">1.5 s</option>
          <option value="2500" selected>2.5 s</option>
          <option value="5000">5 s</option>
          <option value="10000">10 s</option>
        </select>
      </div>
      <div class="setting-row">
        <div class="setting-label">System stats interval</div>
        <select id="st-stats-interval" style="width:100px">
          <option value="5000">5 s</option>
          <option value="8000" selected>8 s</option>
          <option value="15000">15 s</option>
        </select>
      </div>
      <div class="setting-row">
        <div class="setting-label">Log auto-refresh</div>
        <select id="st-log-interval" style="width:100px">
          <option value="2000">2 s</option>
          <option value="4000" selected>4 s</option>
          <option value="8000">8 s</option>
        </select>
      </div>
    </div>

    <!-- System Info -->
    <div class="setting-card">
      <h3>System Info</h3>
      <div class="setting-row">
        <div class="setting-label">Version</div>
        <code id="sys-ver" style="font-size:11px;color:var(--accent-light)">—</code>
      </div>
      <div class="setting-row">
        <div class="setting-label">CPU Usage</div>
        <b id="sys-cpu" style="color:var(--text)">—</b>
      </div>
      <div class="setting-row">
        <div class="setting-label">RAM Usage</div>
        <b id="sys-ram" style="color:var(--text)">—</b>
      </div>
      <div class="setting-row">
        <div class="setting-label">Active Streams</div>
        <b id="sys-live" style="color:var(--green)">—</b>
      </div>
      <div class="setting-row" style="border:none;padding-top:12px">
        <button class="btn b" onclick="updateSysInfo()" style="width:100%;justify-content:center">↻ Refresh Info</button>
      </div>
    </div>
  </div>

  <!-- Mail Alerts -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2>Mail Alerts</h2><span class="sep"></span>
      <button class="btn b" onclick="loadMailConfig()">↻ Load</button>
    </div>
    <div class="card card-body" style="padding:16px">

      <!-- Mode tabs -->
      <div style="display:flex;gap:0;margin-bottom:16px;border-bottom:1px solid var(--border)">
        <button id="ml-tab-gmail" class="nav-tab active" onclick="switchMailMode('gmail_oauth2')"
          style="padding:8px 18px;font-size:12px">
          <span class="tab-dot"></span>Gmail (OAuth2)
        </button>
        <button id="ml-tab-ms" class="nav-tab" onclick="switchMailMode('microsoft_oauth2')"
          style="padding:8px 18px;font-size:12px">
          <span class="tab-dot"></span>Microsoft (OAuth2)
        </button>
        <button id="ml-tab-smtp" class="nav-tab" onclick="switchMailMode('smtp')"
          style="padding:8px 18px;font-size:12px">
          <span class="tab-dot"></span>SMTP (Yahoo / Custom)
        </button>
      </div>
      <input type="hidden" id="ml-mode" value="gmail_oauth2">

      <!-- ── Gmail OAuth2 panel ── -->
      <div id="ml-panel-gmail">
        <div style="font-size:11px;color:var(--text3);margin-bottom:14px;line-height:1.8">
          Sign in with Google — no passwords stored. Requires
          <code style="color:var(--accent-light)">gmail_client_secret.json</code> in the HydraCast base directory.<br>
          Libraries needed: <code style="color:var(--accent-light)">pip install google-auth google-auth-oauthlib google-api-python-client</code>
        </div>
        <div id="ml-gmail-status-box" style="padding:10px 14px;border-radius:8px;background:var(--bg3);
            border:1px solid var(--border);font-size:12px;margin-bottom:14px;display:flex;align-items:center;gap:10px">
          <span id="ml-gmail-dot" style="width:9px;height:9px;border-radius:50%;background:var(--text3);flex-shrink:0"></span>
          <span id="ml-gmail-label">Not connected</span>
          <button class="btn b" style="margin-left:auto" onclick="connectGmail()">🔗 Connect Gmail</button>
          <button class="btn r" id="ml-gmail-revoke" style="display:none" onclick="revokeGmail()">✕ Disconnect</button>
        </div>
        <div id="ml-gmail-poll-msg" style="font-size:11px;color:var(--yellow);margin-bottom:12px;display:none">
          ⏳ Waiting for Google sign-in in browser… <button class="btn" style="margin-left:8px" onclick="checkOAuthStatus()">Check Status</button>
        </div>
      </div>

      <!-- ── Microsoft OAuth2 panel ── -->
      <div id="ml-panel-ms" style="display:none">
        <div style="font-size:11px;color:var(--text3);margin-bottom:14px;line-height:1.8">
          <b style="color:var(--yellow)">⚡ Recommended for Outlook.com / Office 365</b> — fixes the<br>
          <code style="color:var(--red)">"5.7.139 basic authentication is disabled"</code> SMTP error.<br>
          Requires <code style="color:var(--accent-light)">pip install msal</code> and a free Azure App Registration.<br>
          <a href="https://portal.azure.com" target="_blank" style="color:var(--blue)">portal.azure.com</a>
          → App registrations → New → API permissions → Microsoft Graph → Delegated → Mail.Send
        </div>
        <div class="form-grid" style="grid-template-columns:1fr 1fr;margin-bottom:12px">
          <div class="fg">
            <label>Application (Client) ID</label>
            <input id="ml-ms-client-id" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx">
          </div>
          <div class="fg">
            <label>Your Mailbox Address</label>
            <input id="ml-ms-username" placeholder="you@outlook.com">
          </div>
        </div>
        <div id="ml-ms-status-box" style="padding:10px 14px;border-radius:8px;background:var(--bg3);
            border:1px solid var(--border);font-size:12px;margin-bottom:14px;display:flex;align-items:center;gap:10px">
          <span id="ml-ms-dot" style="width:9px;height:9px;border-radius:50%;background:var(--text3);flex-shrink:0"></span>
          <span id="ml-ms-label">Not connected</span>
          <button class="btn b" style="margin-left:auto" onclick="connectMicrosoft()">🔗 Connect Microsoft</button>
          <button class="btn r" id="ml-ms-revoke" style="display:none" onclick="revokeMicrosoft()">✕ Disconnect</button>
        </div>
        <div id="ml-ms-device-box" style="display:none;background:var(--bg3);border:1px solid rgba(251,191,36,0.5);
            border-radius:8px;padding:14px;margin-bottom:14px;font-size:12px">
          <div style="color:var(--yellow);font-weight:600;margin-bottom:8px">🔐 Device Sign-in Required</div>
          <div>1. Open <a id="ml-ms-uri" href="https://microsoft.com/devicelogin" target="_blank" style="color:var(--blue)">https://microsoft.com/devicelogin</a></div>
          <div style="margin:6px 0">2. Enter code: <code id="ml-ms-code" style="color:var(--accent-light);font-size:15px;font-weight:700;letter-spacing:3px">——————</code></div>
          <div style="color:var(--text3)">3. Sign in, then click Check Status below.</div>
          <button class="btn" style="margin-top:10px" onclick="checkMsOAuthStatus()">↻ Check Status</button>
        </div>
      </div>

      <!-- ── SMTP panel ── -->
      <div id="ml-panel-smtp" style="display:none">
        <div style="font-size:11px;color:var(--text3);margin-bottom:14px;line-height:1.8">
          Works with Yahoo, custom SMTP servers, or Gmail App Password.<br>
          <b style="color:var(--red)">⚠ Outlook.com / Office 365</b> — use the <b>Microsoft (OAuth2)</b> tab instead; basic SMTP auth is permanently disabled.
        </div>
        <div style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:12px;
            font-size:11px;color:var(--text3);margin-bottom:14px">
          <b style="color:var(--text2)">Quick presets:</b>&nbsp;
          <button class="btn" onclick="smtpPreset('yahoo')" style="font-size:10px">Yahoo</button>
          <button class="btn" onclick="smtpPreset('gmail')" style="font-size:10px">Gmail SMTP</button>
        </div>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr));margin-bottom:12px">
          <div class="fg">
            <label>SMTP Host</label>
            <input id="ml-host" placeholder="smtp.mail.yahoo.com">
          </div>
          <div class="fg">
            <label>SMTP Port</label>
            <input id="ml-port" type="number" placeholder="587" value="587">
          </div>
          <div class="fg">
            <label>Username</label>
            <input id="ml-user" placeholder="you@yahoo.com" autocomplete="username">
          </div>
          <div class="fg">
            <label>Password / App Password</label>
            <input id="ml-pass" type="password" placeholder="••••••••" autocomplete="current-password">
          </div>
          <div class="fg">
            <label>From Address</label>
            <input id="ml-from" placeholder="you@yahoo.com">
          </div>
        </div>
        <div style="display:flex;gap:16px;margin-bottom:12px">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0">
            <input type="checkbox" id="ml-tls" checked style="width:auto;accent-color:var(--accent)"> Use STARTTLS
          </label>
        </div>
      </div>

            <!-- ── Shared settings (both modes) ── -->
      <div style="border-top:1px solid var(--border);padding-top:14px;margin-top:4px">
        <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));margin-bottom:12px">
          <div class="fg">
            <label>To Addresses (comma-separated)</label>
            <input id="ml-to" placeholder="ops@example.com, backup@example.com">
          </div>
          <div class="fg">
            <label>Cooldown (seconds)</label>
            <input id="ml-cooldown" type="number" placeholder="300" value="300">
          </div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:14px">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0">
            <input type="checkbox" id="ml-enabled" style="width:auto;accent-color:var(--accent)"> Enabled
          </label>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0">
            <input type="checkbox" id="ml-on-error" checked style="width:auto;accent-color:var(--accent)"> Alert on ERROR
          </label>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0">
            <input type="checkbox" id="ml-on-stop" checked style="width:auto;accent-color:var(--accent)"> Alert on unexpected stop
          </label>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">
          <button class="btn g" onclick="saveMailConfig()">💾 Save Config</button>
          <div class="fg" style="flex-direction:row;gap:6px;align-items:center;flex:1;min-width:200px">
            <input id="ml-test-to" placeholder="Test recipient (optional)" style="flex:1">
            <button class="btn b" onclick="testMailAlert()">✉ Send Test</button>
          </div>
        </div>
        <div id="ml-status" style="font-size:11px;color:var(--text3);margin-top:10px"></div>
      </div>

    </div>
  </div>

  <!-- Backup & Restore -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2>Backup &amp; Restore</h2><span class="sep"></span></div>
    <div class="card card-body" style="padding:16px">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">

        <!-- Backup -->
        <div>
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--accent);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">Create Backup</div>
          <div style="font-size:12px;color:var(--text2);margin-bottom:12px;line-height:1.7">
            Downloads a single <code style="color:var(--accent-light)">.hc</code> file containing all your configuration:
            <ul style="margin:6px 0 0 16px;color:var(--text3);font-size:11px;line-height:1.9">
              <li>Stream definitions (streams.json)</li>
              <li>Scheduled events (events.json)</li>
              <li>Mail alert config (mail_config.json)</li>
              <li>Resume positions (resume_positions.json)</li>
            </ul>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-streams" checked style="width:auto;accent-color:var(--accent)"> Streams
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-events" checked style="width:auto;accent-color:var(--accent)"> Events
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-mail" checked style="width:auto;accent-color:var(--accent)"> Mail config
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-resume" checked style="width:auto;accent-color:var(--accent)"> Resume positions
            </label>
          </div>
          <button class="btn g" onclick="downloadBackup()">⬇ Download Backup</button>
          <div id="bk-status" style="font-size:11px;color:var(--text3);margin-top:8px"></div>
        </div>

        <!-- Restore -->
        <div>
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--yellow);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">Restore from Backup</div>
          <div style="font-size:12px;color:var(--text2);margin-bottom:12px;line-height:1.7">
            Upload a <code style="color:var(--accent-light)">.hc</code> backup file to restore configuration.
            <span style="color:var(--red);font-weight:600">All streams will be restarted after restore.</span>
          </div>
          <div id="restore-drop" style="border:2px dashed var(--border);border-radius:var(--radius);padding:24px 16px;text-align:center;cursor:pointer;color:var(--text3);transition:all 0.22s;background:var(--bg3)"
            onclick="document.getElementById('restore-file').click()"
            ondragover="event.preventDefault();this.style.borderColor='var(--accent)'"
            ondragleave="this.style.borderColor='var(--border)'"
            ondrop="event.preventDefault();this.style.borderColor='var(--border)';doRestore(event.dataTransfer.files[0])">
            <div style="font-size:24px;margin-bottom:6px;opacity:0.4">⬆</div>
            <div style="font-size:13px;font-weight:600;color:var(--text2)">Drop .hc file or click to browse</div>
          </div>
          <input type="file" id="restore-file" accept=".hc" style="display:none" onchange="doRestore(this.files[0])">
          <div id="restore-status" style="font-size:11px;color:var(--text3);margin-top:8px"></div>
        </div>

      </div>
    </div>
  </div>

  <!-- Danger Zone -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2 style="color:var(--red)">Danger Zone</h2><span class="sep"></span></div>
    <div class="card card-body" style="border-color:rgba(248,113,113,0.2);padding:16px">
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <button class="btn r" onclick="if(confirm('Stop ALL streams?')) api('stop_all',{})">■ Stop All Streams</button>
        <button class="btn r" onclick="if(confirm('Restart ALL streams?')) api('restart_all',{})">↺ Restart All</button>
      </div>
      <div style="font-size:11px;color:var(--text3);margin-top:10px">These actions affect all streams immediately.</div>
    </div>
  </div>
</div>

</div><!-- /app -->

<!-- ══ FOOTER ══ -->
<footer class="app-footer">
  <span id="ft-app-name">HydraCast</span>
  <span class="footer-sep">·</span>
  <span id="ft-ver">—</span>
  <span class="footer-sep">·</span>
  <a href="https://github.com/rhshourav/HydraCast"
     target="_blank" rel="noopener"
     class="author-badge">
    <img class="author-ico"
         src="https://raw.githubusercontent.com/rhshourav/HydraCast/refs/heads/main/resources/shourav.ico"
         alt="rhshourav"
         onerror="this.style.display='none'">
    <span class="author-name">rhshourav</span>
  </a>
  <span class="footer-sep">·</span>
  <a href="https://github.com/rhshourav/HydraCast" target="_blank" rel="noopener"
     style="font-size:11px;color:var(--text3)">GitHub ↗</a>
</footer>

<!-- ══ SEEK MODAL ══ -->
<div class="modal-bg" id="seek-modal">
  <div class="modal">
    <h3>Seek Stream</h3>
    <div id="seek-info" style="font-size:11px;color:var(--text3);margin-bottom:12px"></div>
    <div class="fg" style="margin-bottom:10px">
      <label>Seek position (seconds or HH:MM:SS)</label>
      <input type="text" id="seek-val" placeholder="e.g. 120 or 00:02:00">
    </div>
    <div class="fg">
      <input type="range" id="seek-slider" min="0" max="100" value="0" style="accent-color:var(--accent)">
    </div>
    <div class="modal-footer">
      <button class="btn" onclick="closeSeek()">Cancel</button>
      <button class="btn g" onclick="doSeek()">⏩ Seek</button>
    </div>
  </div>
</div>

<!-- ══ TOAST ══ -->
<div id="toast"></div>

<script>
// ═══════════════════════════════════
// UTILS
// ═══════════════════════════════════
function esc(s){
  return String(s??'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtSecs(s){
  s=Math.max(0,Math.floor(+s||0));
  return[Math.floor(s/3600),Math.floor((s%3600)/60),s%60]
    .map(n=>String(n).padStart(2,'0')).join(':');
}
function fmtBytes(n){
  if(n<1024)return n+' B';
  if(n<1048576)return(n/1024).toFixed(1)+' KB';
  if(n<1073741824)return(n/1048576).toFixed(1)+' MB';
  return(n/1073741824).toFixed(2)+' GB';
}

let _nt;
function toast(msg,type='ok'){
  const el=document.getElementById('toast');
  const icons={ok:'✓',err:'✕',info:'ℹ'};
  el.innerHTML=`<span>${icons[type]||'•'}</span><span>${msg}</span>`;
  el.className='show '+type;
  clearTimeout(_nt);
  _nt=setTimeout(()=>el.className='',type==='err'?5000:2800);
}

// ═══════════════════════════════════
// TABS
// ═══════════════════════════════════
function switchTab(name,btn){
  document.querySelectorAll('.tab-panel').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  if(name==='streams'){loadStreams();}
  else if(name==='logs'){fillLogStreamSel();loadLogs();}
  else if(name==='upload'){loadSubdirs();}
  else if(name==='events'){loadEvtForm();loadEvents();}
  else if(name==='viewer'){loadViewer();}
  else if(name==='config'){loadConfig();}
  else if(name==='settings'){updateSysInfo();loadMailConfig();}
}

// ═══════════════════════════════════
// API
// ═══════════════════════════════════
async function api(action,data){
  try{
    const r=await fetch('/api/'+action,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    const j=await r.json();
    toast(j.msg||(j.ok?'Done':'Error'),j.ok?'ok':'err');
    loadStreams();
    return j;
  }catch(e){toast('Request failed','err');}
}

// ═══════════════════════════════════
// HEADER STATS
// ═══════════════════════════════════
async function updateStats(){
  try{
    const s=await fetch('/api/system_stats').then(r=>r.json());
    document.getElementById('h-cpu').textContent=s.cpu+'%';
    document.getElementById('h-ram').textContent=s.mem_percent+'%';
  }catch(_){}
}
async function updateSysInfo(){
  try{
    const s=await fetch('/api/system_stats').then(r=>r.json());
    const cpu=document.getElementById('sys-cpu');
    const ram=document.getElementById('sys-ram');
    if(cpu) cpu.textContent=s.cpu+'%';
    if(ram) ram.textContent=s.mem_percent+'%';
    const live=document.getElementById('sys-live');
    const streams=await fetch('/api/streams').then(r=>r.json());
    if(live) live.textContent=streams.filter(s=>s.status==='LIVE').length+' / '+streams.length;
    const sv=document.getElementById('sys-ver');
    if(sv&&streams[0]) sv.textContent='v'+streams[0].app_ver;
  }catch(_){}
}

// ═══════════════════════════════════
// STREAMS
// ═══════════════════════════════════
let _autoTimer=null;
function toggleAuto(on){
  clearInterval(_autoTimer);
  if(on) _autoTimer=setInterval(loadStreams,2500);
}

async function loadStreams(){
  try{
    const data=await fetch('/api/streams').then(r=>r.json());
    const live=data.filter(s=>s.status==='LIVE').length;
    document.getElementById('h-live').textContent=live;
    if(data[0]) {
      const ver='v'+data[0].app_ver;
      document.getElementById('ver-badge').textContent=ver;
      const sv=document.getElementById('sys-ver');
      if(sv) sv.textContent=ver;
      const fv=document.getElementById('ft-ver');
      if(fv) fv.textContent=ver;
    }
    renderStreams(data);
  }catch(_){}
}

// ═══════════════════════════════════
// STREAMS — flicker-free DOM diff
// ═══════════════════════════════════
let _streamSigs={};

function _sigOf(s){
  // A fingerprint of every visible field; if unchanged the row is untouched
  return[s.status||'',
         (+s.progress||0).toFixed(1),
         s.time_remaining||'',
         s.position||'',
         s.fps>0?Math.round(s.fps):'',
         s.loop_count||'',
         s.bitrate||'',
         s.error_msg||'',
         s.playlist_count||0,
         s.enabled?1:0,
         s.shuffle?1:0].join('|');
}

function _rowCells(s,i,showRtsp){
  const pct=Math.max(0,Math.min(100,+s.progress)).toFixed(1);
  const fc=s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
  const status=s.status||'STOPPED';
  return `
    <td class="td-muted">${i+1}</td>
    <td>
      <span class="td-name">${esc(s.name)}</span>
      ${s.shuffle?`<span class="tag-shuf">SHUF</span>`:''}
      ${!s.enabled?`<span class="tag-dis">OFF</span>`:''}
      ${s.playlist_count>1?`<span style="font-size:10px;color:var(--text3);margin-left:4px">(${s.playlist_count} files)</span>`:''}
    </td>
    <td style="color:var(--accent-light)">:${s.port}</td>
    <td><span class="badge ${esc(status)}">${esc(status)}</span></td>
    <td style="min-width:140px">
      <div class="prog"><div class="prog-fill" style="width:${pct}%;background:${fc}"></div></div>
      <div class="prog-label">${pct}%${s.time_remaining?' · '+esc(s.time_remaining)+' left':''}</div>
    </td>
    <td class="td-muted" style="white-space:nowrap">${esc(s.position||'--')}</td>
    <td class="td-muted">${s.fps>0?Math.round(s.fps)+'fps':'--'}</td>
    <td class="td-muted">${s.loop_count>0?'×'+s.loop_count:'--'}</td>
    <td class="td-muted">${(s.bitrate&&s.bitrate!=='—')?esc(s.bitrate):'--'}</td>
    <td>
      ${s.rtsp_url?`<span class="chip" onclick="copyText('${esc(s.rtsp_url)}')" title="${esc(s.rtsp_url)}">📋 ${esc(s.rtsp_url)}</span>`:'<span class="td-muted">—</span>'}
    </td>
    <td>
      <div class="btn-group">
        <button class="btn g" onclick="api('start',{name:'${esc(s.name)}'})">▶</button>
        <button class="btn r" onclick="api('stop',{name:'${esc(s.name)}'})">■</button>
        <button class="btn" onclick="api('restart',{name:'${esc(s.name)}'})">↺</button>
        ${s.playlist_count>1?`<button class="btn" onclick="api('skip_next',{name:'${esc(s.name)}'})">⏭</button>`:''}
        ${s.status==='LIVE'?`<button class="btn b" onclick="openSeek('${esc(s.name)}',${s.duration||0},${s.current_secs||0})">⏩</button>`:''}
      </div>
      ${s.error_msg?`<div style="font-size:10px;color:var(--red);margin-top:4px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(s.error_msg)}">⚠ ${esc(s.error_msg)}</div>`:''}
    </td>`;
}

function renderStreams(data){
  const tb=document.getElementById('stbl');
  const showRtsp=document.getElementById('st-showrtsp')?.classList.contains('on')!==false;

  if(!data.length){
    tb.innerHTML=`<tr><td colspan="11"><div class="empty"><div class="empty-icon">📡</div>No streams configured.</div></td></tr>`;
    _streamSigs={};
    return;
  }

  // Build lookup of existing keyed rows
  const existing={};
  tb.querySelectorAll('tr[data-sname]').forEach(r=>existing[r.dataset.sname]=r);

  // If transitioning from placeholder state, wipe it cleanly
  if(tb.querySelector('td[colspan]')){
    tb.innerHTML='';
    _streamSigs={};
    Object.keys(existing).forEach(k=>delete existing[k]);
  }

  const newNames=new Set(data.map(s=>s.name));

  // Remove rows for streams that disappeared
  Object.entries(existing).forEach(([name,row])=>{
    if(!newNames.has(name)){row.remove();delete _streamSigs[name];}
  });

  // Update / insert rows in data order
  data.forEach((s,i)=>{
    const sig=_sigOf(s);
    let row=existing[s.name];
    if(!row){
      // Brand-new stream → create row without animation flash
      row=document.createElement('tr');
      row.dataset.sname=s.name;
      row.innerHTML=_rowCells(s,i,showRtsp);
      tb.appendChild(row);
    } else if(_streamSigs[s.name]!==sig){
      // Something changed → update cells in-place (no remove/re-add)
      row.innerHTML=_rowCells(s,i,showRtsp);
    }
    // Unchanged → leave DOM completely untouched → zero flicker
    _streamSigs[s.name]=sig;
  });

  // Re-order rows if stream list order changed (rare)
  const rows=Array.from(tb.querySelectorAll('tr[data-sname]'));
  data.forEach((s,i)=>{
    if(rows[i]&&rows[i].dataset.sname!==s.name){
      const t=tb.querySelector(`tr[data-sname="${CSS.escape(s.name)}"]`);
      if(t)tb.insertBefore(t,rows[i]);
    }
  });
}

function copyText(url){
  navigator.clipboard.writeText(url).then(()=>toast('Copied to clipboard','ok'));
}

// ═══════════════════════════════════
// SEEK MODAL
// ═══════════════════════════════════
let _seekName='';
function openSeek(name,dur,cur){
  _seekName=name;
  document.getElementById('seek-info').innerHTML=
    `Stream: <b style="color:var(--text)">${esc(name)}</b> &nbsp;·&nbsp; Duration: <b>${fmtSecs(dur)}</b> &nbsp;·&nbsp; Current: <b>${fmtSecs(cur)}</b>`;
  document.getElementById('seek-val').value=fmtSecs(cur);
  const slider=document.getElementById('seek-slider');
  slider.max=dur||100;slider.value=cur||0;
  slider.oninput=()=>{document.getElementById('seek-val').value=fmtSecs(+slider.value);};
  document.getElementById('seek-modal').classList.add('open');
  document.getElementById('seek-val').focus();
}
function closeSeek(){document.getElementById('seek-modal').classList.remove('open');}
function doSeek(){
  const raw=document.getElementById('seek-val').value.trim();
  let s;
  const p=raw.split(':').map(Number);
  if(p.length===3)s=p[0]*3600+p[1]*60+p[2];
  else if(p.length===2)s=p[0]*60+p[1];
  else s=+p[0];
  if(isNaN(s)||s<0){toast('Invalid time','err');return;}
  api('seek',{name:_seekName,seconds:s});
  closeSeek();
}

// ═══════════════════════════════════
// VIEWER TAB
// ═══════════════════════════════════
async function loadViewer(){
  const grid=document.getElementById('viewer-grid');
  try{
    const data=await fetch('/api/streams').then(r=>r.json());
    if(!data.length){
      grid.innerHTML=`<div class="empty"><div class="empty-icon">📺</div>No streams available.</div>`;
      return;
    }
    grid.innerHTML=data.map(s=>{
      const status=s.status||'STOPPED';
      const isLive=status==='LIVE';
      return `<div class="stream-card ${isLive?'is-live':''}" id="vc-${esc(s.name)}">
        <div class="stream-card-header">
          <span class="badge ${esc(status)}" style="font-size:9px">${esc(status)}</span>
          <span class="stream-card-title">${esc(s.name)}</span>
          <span style="font-size:11px;color:var(--accent-light)">:${s.port}</span>
        </div>
        <div class="stream-preview" id="vp-${esc(s.name)}">
          <div class="stream-overlay" id="vo-${esc(s.name)}">
            ${isLive?`
              <div class="stream-play-btn" onclick="loadHLSStream('${esc(s.name)}','${esc(s.hls_url||'')}','${esc(s.rtsp_url||'')}')" title="Click to load stream">
                ▶
              </div>
              <div style="font-size:10px;color:var(--text3)">Click to preview</div>
            `:`<div style="font-size:12px;color:var(--text3)">Stream offline</div>`}
          </div>
        </div>
        <div class="stream-card-footer">
          <div class="stream-stats">
            <div class="stat-item">Progress <b>${(+s.progress||0).toFixed(1)}%</b></div>
            <div class="stat-item">FPS <b>${s.fps>0?Math.round(s.fps)+'fps':'—'}</b></div>
            <div class="stat-item">Pos <b>${esc(s.position||'—')}</b></div>
          </div>
          <div class="btn-group">
            ${isLive?`<button class="btn g" style="font-size:10px" onclick="api('restart',{name:'${esc(s.name)}'})">↺</button>`:''}
            <button class="btn b" style="font-size:10px" onclick="copyText('${esc(s.rtsp_url||'')}')">📋</button>
          </div>
        </div>
        ${s.rtsp_url?`<div style="padding:0 14px 10px">
          <div class="info-row">
            <span class="info-chip">RTSP <b>${esc(s.rtsp_url)}</b></span>
            ${s.hls_url?`<span class="info-chip">HLS <b>enabled</b></span>`:''}
          </div>
        </div>`:''}
      </div>`;
    }).join('');
  }catch(_){
    grid.innerHTML=`<div class="empty"><div class="empty-icon">⚠</div>Failed to load streams.</div>`;
  }
}

function loadHLSStream(name,hlsUrl,rtspUrl){
  const overlay=document.getElementById('vo-'+name);
  const preview=document.getElementById('vp-'+name);
  if(!hlsUrl&&!rtspUrl){
    toast('No HLS or RTSP URL available','err');return;
  }
  if(hlsUrl){
    // Try HLS.js if available, else native video
    preview.innerHTML=`
      <video id="vid-${esc(name)}" controls autoplay muted style="width:100%;height:100%;object-fit:contain;background:#000"
        onerror="this.outerHTML='<div class=\\'stream-overlay\\'><div style=\\'color:var(--red);font-size:11px\\'>HLS load failed</div></div>'">
        <source src="${esc(hlsUrl)}" type="application/x-mpegURL">
        Your browser doesn't support HLS.
      </video>`;
  } else {
    overlay.innerHTML=`
      <div style="font-size:11px;color:var(--text3);text-align:center;padding:20px">
        <div style="margin-bottom:8px;font-size:20px">📺</div>
        <div>RTSP streams require a native player.</div>
        <div style="margin-top:6px"><span class="chip" onclick="copyText('${esc(rtspUrl)}')" style="max-width:none">📋 ${esc(rtspUrl)}</span></div>
      </div>`;
  }
}

// ═══════════════════════════════════
// LOGS
// ═══════════════════════════════════
async function fillLogStreamSel(){
  try{
    const data=await fetch('/api/streams').then(r=>r.json());
    const sel=document.getElementById('log-stream');
    const cur=sel.value;
    sel.innerHTML='<option value="">All streams</option>'+
      data.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
    if(cur)sel.value=cur;
  }catch(_){}
}

async function loadLogs(){
  try{
    const stream=document.getElementById('log-stream').value;
    const level=document.getElementById('log-level').value;
    const url=`/api/logs?level=${level}&stream=${encodeURIComponent(stream)}&n=600`;
    const data=await fetch(url).then(r=>r.json());
    const entries=data.entries||[];
    const box=document.getElementById('logbox');
    box.innerHTML=entries.slice().reverse().map(([m,lv])=>{
      const cls=lv==='ERROR'?'le':lv==='WARN'?'lw':'li';
      const badge=lv==='ERROR'?`<span style="color:var(--red);font-size:9px;font-weight:700;margin-right:4px">[ERR]</span>`
                 :lv==='WARN'?`<span style="color:var(--yellow);font-size:9px;font-weight:700;margin-right:4px">[WRN]</span>`
                 :`<span style="color:var(--text3);font-size:9px;margin-right:4px">[INF]</span>`;
      return `<div class="${cls}" style="padding:1px 0;border-bottom:1px solid rgba(33,41,58,0.3)">${badge}${esc(m)}</div>`;
    }).join('')||'<div style="color:var(--text3);padding:12px">No log entries.</div>';
    if(document.getElementById('log-auto').checked) box.scrollTop=0;
  }catch(_){}
}

// ═══════════════════════════════════
// UPLOAD
// ═══════════════════════════════════
async function loadSubdirs(){
  try{
    const data=await fetch('/api/subdirs').then(r=>r.json());
    const sel=document.getElementById('upload-subdir');
    sel.innerHTML='<option value="">/ (root)</option>'+
      (data.dirs||[]).filter(Boolean).map(d=>`<option value="${esc(d)}">${esc(d)}</option>`).join('');
  }catch(_){}
}
async function mkSubdir(){
  const n=prompt('New folder name:');
  if(!n||!n.trim())return;
  const r=await api('create_subdir',{name:n.trim()});
  if(r&&r.ok)loadSubdirs();
}

const dz=document.getElementById('dropzone');
dz.addEventListener('dragover',e=>{e.preventDefault();dz.classList.add('over')});
dz.addEventListener('dragleave',()=>dz.classList.remove('over'));
dz.addEventListener('drop',e=>{e.preventDefault();dz.classList.remove('over');doUpload(e.dataTransfer.files)});

function doUpload(files){Array.from(files).forEach(upOne);}
function upOne(file){
  if(file.size>10*1024*1024*1024){toast(file.name+': exceeds 10 GB','err');return;}
  const id='u'+Math.random().toString(36).slice(2,7);
  const li=document.createElement('li');
  li.innerHTML=`
    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;color:var(--text2)">${esc(file.name)}</span>
    <span class="td-muted">${fmtBytes(file.size)}</span>
    <div class="ubar"><div class="ufill" id="uf-${id}" style="width:0"></div></div>
    <span id="up-${id}" style="min-width:32px;text-align:right;color:var(--text3);font-size:11px">0%</span>`;
  document.getElementById('uplist').appendChild(li);
  const fd=new FormData();
  fd.append('file',file);
  fd.append('subdir',document.getElementById('upload-subdir').value);
  const xhr=new XMLHttpRequest();
  xhr.upload.onprogress=e=>{
    if(!e.lengthComputable)return;
    const p=Math.round(e.loaded/e.total*100);
    const b=document.getElementById('uf-'+id),t=document.getElementById('up-'+id);
    if(b){b.style.width=p+'%';b.style.background=p===100?'var(--green)':'var(--accent)';}
    if(t)t.textContent=p+'%';
  };
  xhr.onload=()=>{
    const t=document.getElementById('up-'+id);
    try{
      const j=JSON.parse(xhr.responseText);
      if(xhr.status===200&&j.ok){if(t){t.textContent='✓';t.style.color='var(--green)';}toast(file.name+' uploaded','ok');}
      else{if(t){t.textContent='✕';t.style.color='var(--red)';}toast('Failed: '+(j.msg||file.name),'err');}
    }catch(_){if(t){t.textContent='✕';t.style.color='var(--red)';}}
  };
  xhr.onerror=()=>toast('Network error: '+file.name,'err');
  xhr.open('POST','/api/upload');xhr.send(fd);
}

// ═══════════════════════════════════
// EVENTS
// ═══════════════════════════════════
let _evData = [];          // cached event list from server
let _evTimer = null;       // auto-refresh interval
let _evCountdown = null;   // per-second countdown ticker

async function loadEvtForm(){
  try{
    const[streams,lib]=await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/library').then(r=>r.json()),
    ]);
    const streamSel = document.getElementById('ev-stream');
    streamSel.innerHTML = streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
    document.getElementById('ev-file').innerHTML =
      lib.map(f=>`<option value="${esc(f.full_path)}">${esc(f.path)} (${esc(f.duration||'?')})</option>`).join('');
    const dt=new Date(Date.now()+5*60000);
    document.getElementById('ev-dt').value=
      new Date(dt-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);
    // Populate stream filter dropdown
    const fsel = document.getElementById('ev-filter-stream');
    const prev = fsel.value;
    fsel.innerHTML = '<option value="">All streams</option>' +
      streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
    if(prev) fsel.value = prev;
  }catch(e){ log.warn && console.warn('loadEvtForm:', e); }
}

async function loadEvents(){
  try{
    _evData = await fetch('/api/events').then(r=>r.json());
    renderEventsTable();
  }catch(e){ console.warn('loadEvents:', e); }
}

function _fmtCountdown(secs){
  if(secs === null || isNaN(secs)) return '—';
  const abs = Math.abs(Math.round(secs));
  const h = Math.floor(abs/3600);
  const m = Math.floor((abs%3600)/60);
  const s = abs%60;
  const hms = h>0
    ? `${h}h ${String(m).padStart(2,'0')}m`
    : m>0
      ? `${m}m ${String(s).padStart(2,'0')}s`
      : `${s}s`;
  return secs >= 0 ? `in ${hms}` : `${hms} ago`;
}

function renderEventsTable(){
  const filterStream = (document.getElementById('ev-filter-stream')||{}).value || '';
  const filterStatus = (document.getElementById('ev-filter-status')||{}).value || '';
  let rows = _evData.filter(ev=>{
    if(filterStream && ev.stream_name !== filterStream) return false;
    if(filterStatus === 'pending' && ev.played) return false;
    if(filterStatus === 'played'  && !ev.played) return false;
    return true;
  });
  if(!rows.length){
    document.getElementById('evtbl').innerHTML =
      `<tr><td colspan="7"><div class="empty"><div class="empty-icon">📅</div>No events${filterStream||filterStatus?' matching filter':' scheduled'}.</div></td></tr>`;
    return;
  }
  const now = Date.now();
  document.getElementById('evtbl').innerHTML = rows.map(ev=>{
    const secsNow = Math.round((new Date(ev.play_at_iso||ev.play_at.replace(' ','T')) - now)/1000);
    const imminent = !ev.played && secsNow >= 0 && secsNow < 300;
    const past     = !ev.played && secsNow < 0;
    const cdColor  = ev.played ? 'var(--text3)' : imminent ? 'var(--yellow)' : past ? 'var(--red)' : 'var(--accent-light)';
    const rowStyle = imminent ? 'background:rgba(201,168,120,0.06)' : '';
    const fireBtn  = !ev.played
      ? `<button class="btn" style="font-size:10px;padding:3px 8px;color:var(--yellow);border-color:rgba(201,168,120,0.4)"
           onclick="fireNow('${esc(ev.event_id)}')" title="Fire immediately">▶ Now</button>`
      : '';
    return `<tr style="${rowStyle}">
      <td style="color:var(--accent-light)">${esc(ev.stream_name)}</td>
      <td class="td-muted" title="${esc(ev.file_path||ev.file_name)}">${esc(ev.file_name)}</td>
      <td class="td-muted" style="white-space:nowrap;font-family:var(--font-mono);font-size:11px">${esc(ev.play_at)}</td>
      <td class="ev-cd" data-secs="${secsNow}" style="font-size:11px;color:${cdColor};white-space:nowrap">${_fmtCountdown(secsNow)}</td>
      <td class="td-muted" style="font-size:11px">${esc(ev.post_action||'resume')}</td>
      <td><span class="badge ${ev.played?'STOPPED':'SCHED'}">${ev.played?'✓ Played':'⏰ Pending'}</span></td>
      <td style="text-align:right;white-space:nowrap;display:flex;gap:4px;justify-content:flex-end">
        ${fireBtn}
        <button class="btn r" style="font-size:10px;padding:3px 8px" onclick="delEvent('${esc(ev.event_id)}')">✕</button>
      </td>
    </tr>`;
  }).join('');
}

function _tickCountdowns(){
  // Update only the countdown cells every second — no full re-render
  document.querySelectorAll('.ev-cd').forEach(cell=>{
    let s = parseInt(cell.dataset.secs, 10);
    s--;
    cell.dataset.secs = s;
    cell.textContent = _fmtCountdown(s);
    const imminent = s >= 0 && s < 300;
    const past     = s < 0;
    cell.style.color = imminent ? 'var(--yellow)' : past ? 'var(--red)' : 'var(--accent-light)';
  });
}

function _startEvTimers(){
  clearInterval(_evTimer);
  clearInterval(_evCountdown);
  _evTimer    = setInterval(()=>{ if(document.getElementById('ev-autoref')?.checked) loadEvents(); }, 15000);
  _evCountdown = setInterval(_tickCountdowns, 1000);
}

async function schedEvent(){
  const stream = document.getElementById('ev-stream').value;
  const file   = document.getElementById('ev-file').value;
  const dt     = document.getElementById('ev-dt').value;
  const pos    = document.getElementById('ev-pos').value||'00:00:00';
  const post   = document.getElementById('ev-post').value;
  if(!stream){ toast('Select a stream','err'); return; }
  if(!file)  { toast('Select a file','err');   return; }
  if(!dt)    { toast('Set a date/time','err'); return; }
  const r = await api('add_event',{stream_name:stream,file_path:file,play_at:dt,start_pos:pos,post_action:post});
  if(r?.ok) await loadEvents();
}

async function delEvent(id){
  if(!confirm('Delete this event?'))return;
  const r=await api('delete_event',{event_id:id});
  if(r?.ok) await loadEvents();
}

async function fireNow(id){
  if(!confirm('Fire this event immediately?'))return;
  const r=await api('fire_event_now',{event_id:id});
  if(r?.ok) await loadEvents();
}

async function clearPlayed(){
  const played = _evData.filter(e=>e.played).map(e=>e.event_id);
  if(!played.length){ toast('No played events to clear','info'); return; }
  if(!confirm(`Remove ${played.length} played event(s)?`))return;
  try{
    const r=await fetch('/api/delete_played_events',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({event_ids:played})
    });
    const j=await r.json();
    toast(j.ok?(j.msg||'Cleared'):(j.msg||'Error'),j.ok?'ok':'err');
    await loadEvents();
  }catch(e){ toast('Error: '+e,'err'); }
}

// ═══════════════════════════════════
// CONFIGURE TAB
// ═══════════════════════════════════
let _configStreams=[];
let _configSelected=null;

async function loadConfig(){
  try{
    const data=await fetch('/api/streams_config').then(r=>r.json());
    const statusData=await fetch('/api/streams').then(r=>r.json());
    _configStreams=data.map(c=>{
      const st=statusData.find(s=>s.name===c.name)||{};
      return{...c,_status:st.status||'STOPPED'};
    });
    renderConfigSidebar();
    if(_configSelected){
      const s=_configStreams.find(s=>s.name===_configSelected);
      if(s)renderConfigEditor(s);
    }
  }catch(_){toast('Failed to load config','err');}
}

function renderConfigSidebar(){
  const list=document.getElementById('config-stream-list');
  list.innerHTML=_configStreams.map(s=>`
    <div class="config-stream-item ${s.name===_configSelected?'active':''}" onclick="selectConfigStream('${esc(s.name)}')">
      <div class="dot ${s._status==='LIVE'?'live':s._status==='ERROR'?'error':''}"></div>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(s.name)}</span>
      <span style="font-size:10px;color:var(--text3);margin-right:4px">:${s.port}</span>
      <button class="btn r" style="padding:1px 6px;font-size:10px;flex-shrink:0"
        title="Delete stream"
        onclick="event.stopPropagation();deleteStream('${esc(s.name)}')">&#x2715;</button>
    </div>`).join('')||`<div class="empty" style="padding:20px"><div class="empty-icon">&#x2699;</div>No streams.</div>`;
}

function selectConfigStream(name){
  _configSelected=name;
  renderConfigSidebar();
  const s=_configStreams.find(s=>s.name===name);
  if(s)renderConfigEditor(s);
}

function renderConfigEditor(s){
  document.getElementById('config-main-hdr').innerHTML=`
    <span class="badge ${esc(s._status)}">${esc(s._status)}</span>
    <h2>${esc(s.name)}</h2>
    <span style="font-size:11px;color:var(--text3)">Port :${s.port}</span>`;

  document.getElementById('config-main-body').innerHTML=`
    <div class="config-section">
      <div class="config-section-title">Basic</div>
      <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">
        <div class="fg"><label>Stream Name</label><input id="cfg-name" value="${esc(s.name)}" readonly style="opacity:0.6"></div>
        <div class="fg"><label>Port</label><input id="cfg-port" type="number" value="${s.port}" min="1024" max="65535"></div>
        <div class="fg"><label>Stream Path</label><input id="cfg-path" value="${esc(s.stream_path||'')}"></div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Encoding</div>
      <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">
        <div class="fg"><label>Video Bitrate</label><input id="cfg-vbr" value="${esc(s.video_bitrate||'')}"></div>
        <div class="fg"><label>Audio Bitrate</label><input id="cfg-abr" value="${esc(s.audio_bitrate||'')}"></div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Playback</div>
      <div style="display:flex;flex-wrap:wrap;gap:16px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-shuffle" ${s.shuffle?'checked':''} style="width:auto;accent-color:var(--accent)">
          Shuffle playlist
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-enabled" ${s.enabled!==false?'checked':''} style="width:auto;accent-color:var(--accent)">
          Stream enabled
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-hls" ${s.hls_enabled?'checked':''} style="width:auto;accent-color:var(--accent)">
          HLS enabled
        </label>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Schedule (Weekdays)</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:4px">
        ${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d,i)=>{
          const checked=s.weekdays&&s.weekdays.includes(d.toLowerCase().slice(0,3))||s.weekdays==='All days'||s.weekdays==='ALL';
          return `<label style="display:flex;align-items:center;gap:5px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
            <input type="checkbox" class="cfg-wd" value="${i}" ${(s.weekdays==='ALL'||s.weekdays==='All days'||(s.weekdays&&s.weekdays.toLowerCase().includes(d.toLowerCase())))?'checked':''} style="width:auto;accent-color:var(--accent)">${d}
          </label>`;
        }).join('')}
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Compliance (Broadcast Sync)</div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-comp-en" ${s.compliance_enabled?'checked':''} style="width:auto;accent-color:var(--accent)">
          Enable compliance mode (broadcast-sync seek on start)
        </label>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">
          <div class="fg">
            <label>Broadcast start time (HH:MM:SS)</label>
            <input id="cfg-comp-start" value="${esc(s.compliance_start||'06:00:00')}" placeholder="06:00:00" pattern="\\d{1,2}:\\d{2}:\\d{2}">
          </div>
        </div>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-comp-loop" ${s.compliance_loop?'checked':''} style="width:auto;accent-color:var(--accent)">
          Loop calculation (seek within loops for videos shorter than 24 h)
        </label>
        <div style="font-size:10px;color:var(--text3)">
          When enabled, HydraCast calculates the correct playback seek offset so the stream matches a continuous linear broadcast that started at the configured time today.
        </div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Playlist Files</div>
      <textarea id="cfg-files" rows="6" style="font-size:11px;font-family:var(--font-mono)">${esc(s.files||'')}</textarea>
      <div style="font-size:10px;color:var(--text3);margin-top:6px">One file per line (or semicolon-separated). Format: path@HH:MM:SS#priority</div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Stream Actions</div>
      <div class="btn-group">
        <button class="btn g" onclick="api('start',{name:'${esc(s.name)}'})">▶ Start</button>
        <button class="btn r" onclick="api('stop',{name:'${esc(s.name)}'})">■ Stop</button>
        <button class="btn" onclick="api('restart',{name:'${esc(s.name)}'})">↺ Restart</button>
        ${s.playlist_count>1?`<button class="btn" onclick="api('skip_next',{name:'${esc(s.name)}'})">⏭ Skip</button>`:''}
      </div>
    </div>`;

  document.getElementById('config-main-footer').style.display='flex';
}

function _restoreFooter(){
  document.getElementById('config-main-footer').innerHTML=`
    <button class="btn" onclick="cancelConfig()">Cancel</button>
    <button class="btn g" onclick="saveConfig()">Save Changes</button>`;
}

function cancelConfig(){
  _configSelected=null;
  _configMode='edit';
  renderConfigSidebar();
  document.getElementById('config-main-hdr').innerHTML=`<h2 style="color:var(--text3);font-size:14px">Select a stream</h2>`;
  document.getElementById('config-main-body').innerHTML=`<div class="empty"><div class="empty-icon">&#x2699;</div>Select a stream from the sidebar to configure it.</div>`;
  _restoreFooter();
  document.getElementById('config-main-footer').style.display='none';
}

async function saveConfig(){
  if(!_configSelected){toast('No stream selected','err');return;}
  // Collect weekday checkboxes
  const wdChecked=Array.from(document.querySelectorAll('.cfg-wd:checked')).map(el=>+el.value);
  const wdMap=['mon','tue','wed','thu','fri','sat','sun'];
  const weekdaysStr=wdChecked.length===7?'all':wdChecked.map(i=>wdMap[i]).join('|')||'all';
  const payload={
    name:_configSelected,
    port:parseInt(document.getElementById('cfg-port')?.value||0),
    stream_path:document.getElementById('cfg-path')?.value||'',
    video_bitrate:document.getElementById('cfg-vbr')?.value||'',
    audio_bitrate:document.getElementById('cfg-abr')?.value||'',
    shuffle:document.getElementById('cfg-shuffle')?.checked||false,
    enabled:document.getElementById('cfg-enabled')?.checked!==false,
    hls_enabled:document.getElementById('cfg-hls')?.checked||false,
    files:document.getElementById('cfg-files')?.value||'',
    weekdays:weekdaysStr,
    compliance_enabled:document.getElementById('cfg-comp-en')?.checked||false,
    compliance_start:document.getElementById('cfg-comp-start')?.value||'06:00:00',
    compliance_loop:document.getElementById('cfg-comp-loop')?.checked||false,
  };
  const r=await api('update_config',payload);
  if(r?.ok)loadConfig();
}

// ═══════════════════════════════════
// NEW STREAM / DELETE STREAM
// ═══════════════════════════════════
let _configMode='edit'; // 'edit' | 'create'

function showNewStreamForm(){
  _configSelected=null;
  _configMode='create';
  renderConfigSidebar();
  document.getElementById('config-main-hdr').innerHTML=`
    <h2 style="font-family:var(--font-display);font-size:16px;font-weight:700">New Stream</h2>`;
  document.getElementById('config-main-body').innerHTML=`
    <div class="config-section">
      <div class="config-section-title">Identity</div>
      <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">
        <div class="fg"><label>Stream Name *</label><input id="new-name" placeholder="My_Stream" autocomplete="off"></div>
        <div class="fg"><label>Port * (≥10 apart)</label><input id="new-port" type="number" value="8554" min="1024" max="65535"></div>
        <div class="fg">
          <label>Stream Path <span style="font-size:10px;color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0">(blank = root mount IP:Port/)</span></label>
          <input id="new-spath" value="" placeholder="e.g. live  (optional)">
        </div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Playlist Source</div>
      <div style="display:flex;gap:0;margin-bottom:12px;border-bottom:1px solid var(--border)">
        <button id="new-src-tab-files" class="nav-tab active" onclick="switchNewSrcTab('files')" style="padding:7px 16px;font-size:12px"><span class="tab-dot"></span>File List</button>
        <button id="new-src-tab-folder" class="nav-tab" onclick="switchNewSrcTab('folder')" style="padding:7px 16px;font-size:12px"><span class="tab-dot"></span>Folder Source</button>
      </div>
      <div id="new-src-files">
        <textarea id="new-files" rows="6" style="font-size:11px;font-family:var(--font-mono)"
          placeholder="/path/to/video.mp4\n/path/to/video2.mkv\n\nOptional format:  /path@HH:MM:SS#priority"></textarea>
        <div style="font-size:10px;color:var(--text3);margin-top:6px">One path per line (or semicolon-separated). Omit @position and #priority for defaults.</div>
      </div>
      <div id="new-src-folder" style="display:none">
        <div class="fg">
          <label>Folder Path</label>
          <input id="new-folder" placeholder="/media/shows  or  media/news">
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:6px">HydraCast will scan the folder and auto-rebuild the playlist when files change. Day-tags (_mon_, _tue_, …) are detected automatically.</div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Encoding</div>
      <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">
        <div class="fg"><label>Video Bitrate</label><input id="new-vbr" value="2500k"></div>
        <div class="fg"><label>Audio Bitrate</label><input id="new-abr" value="128k"></div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Schedule (Weekdays)</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:4px">
        ${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d,i)=>`
          <label style="display:flex;align-items:center;gap:5px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
            <input type="checkbox" class="new-wd" value="${i}" checked style="width:auto;accent-color:var(--accent)">${d}
          </label>`).join('')}
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Options</div>
      <div style="display:flex;flex-wrap:wrap;gap:16px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="new-shuffle" style="width:auto;accent-color:var(--accent)">Shuffle playlist
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="new-enabled" checked style="width:auto;accent-color:var(--accent)">Enabled
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="new-hls" style="width:auto;accent-color:var(--accent)">HLS enabled
        </label>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Compliance — Broadcast Sync</div>
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:12px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:13px;color:var(--text);font-weight:500;margin-bottom:12px">
          <input type="checkbox" id="new-comp-en" style="width:auto;accent-color:var(--accent)"
            onchange="document.getElementById('new-comp-fields').style.display=this.checked?'':'none'">
          Enable compliance mode
        </label>
        <div id="new-comp-fields" style="display:none">
          <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr));margin-bottom:12px">
            <div class="fg">
              <label>Broadcast Start Time (HH:MM:SS)</label>
              <input id="new-comp-start" value="06:00:00" placeholder="06:00:00">
            </div>
            <div class="fg">
              <label>Timezone offset</label>
              <input id="new-comp-tz" value="" placeholder="System time (default)" style="opacity:0.7" disabled title="Uses system local time — configure server timezone via OS">
            </div>
          </div>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2);margin-bottom:8px">
            <input type="checkbox" id="new-comp-loop" style="width:auto;accent-color:var(--accent)">
            Loop calculation — seek within loops for videos shorter than 24 h
          </label>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
            <input type="checkbox" id="new-comp-strict" style="width:auto;accent-color:var(--accent)">
            Strict mode — stop stream if seek offset exceeds video duration
          </label>
          <div style="font-size:10px;color:var(--text3);margin-top:10px;line-height:1.7;border-top:1px solid var(--border);padding-top:10px">
            <b style="color:var(--accent-light)">What is compliance mode?</b><br>
            Calculates the exact seek offset so viewers see what a continuous linear broadcast would be showing right now.
            Example: 24 h video, broadcast starts 06:00, current time 14:30 → seeks to 08:30:00.
            Useful for simulating scheduled broadcast channels.
          </div>
        </div>
      </div>
    </div>`;
  // Swap footer buttons for Create mode
  document.getElementById('config-main-footer').innerHTML=`
    <button class="btn" onclick="cancelConfig()">Cancel</button>
    <button class="btn g" onclick="submitNewStream()">&#x2713; Create Stream</button>`;
  document.getElementById('config-main-footer').style.display='flex';
}

function switchNewSrcTab(mode){
  document.getElementById('new-src-files').style.display=mode==='files'?'':'none';
  document.getElementById('new-src-folder').style.display=mode==='folder'?'':'none';
  document.getElementById('new-src-tab-files').classList.toggle('active',mode==='files');
  document.getElementById('new-src-tab-folder').classList.toggle('active',mode==='folder');
}

async function submitNewStream(){
  const name=(document.getElementById('new-name')?.value||'').trim();
  const port=parseInt(document.getElementById('new-port')?.value||0);
  // Detect source mode
  const isFolderMode=document.getElementById('new-src-folder')?.style.display!=='none';
  const files=isFolderMode?'':(document.getElementById('new-files')?.value||'').trim();
  const folderPath=isFolderMode?(document.getElementById('new-folder')?.value||'').trim():'';
  if(!name){toast('Stream name is required','err');return;}
  if(!/^[\w\-. ]+$/.test(name)){toast('Name: letters, numbers, spaces, hyphens, dots, underscores only','err');return;}
  if(!port||port<1024||port>65535){toast('Port must be 1024-65535','err');return;}
  if(!isFolderMode&&!files){toast('At least one file path is required','err');return;}
  if(isFolderMode&&!folderPath){toast('Folder path is required for folder source','err');return;}
  const wdChecked=Array.from(document.querySelectorAll('.new-wd:checked')).map(el=>+el.value);
  const wdMap=['mon','tue','wed','thu','fri','sat','sun'];
  const weekdays=wdChecked.length===7?'all':(wdChecked.map(i=>wdMap[i]).join('|')||'all');
  const r=await api('create_stream',{
    name,port,files,weekdays,
    folder_source: folderPath||null,
    stream_path:(document.getElementById('new-spath')?.value||'').trim(),
    video_bitrate:(document.getElementById('new-vbr')?.value||'2500k').trim()||'2500k',
    audio_bitrate:(document.getElementById('new-abr')?.value||'128k').trim()||'128k',
    shuffle:document.getElementById('new-shuffle')?.checked||false,
    enabled:document.getElementById('new-enabled')?.checked!==false,
    hls_enabled:document.getElementById('new-hls')?.checked||false,
    compliance_enabled:document.getElementById('new-comp-en')?.checked||false,
    compliance_start:(document.getElementById('new-comp-start')?.value||'06:00:00').trim()||'06:00:00',
    compliance_loop:document.getElementById('new-comp-loop')?.checked||false,
    compliance_strict:document.getElementById('new-comp-strict')?.checked||false,
  });
  if(r?.ok){
    cancelConfig();
    await loadConfig();
    // Auto-select the newly created stream
    selectConfigStream(name);
    toast(r.msg||'Stream created','ok');
  }
}

async function deleteStream(name){
  if(!confirm(`Delete stream "${name}"?\n\nThis will remove it from streams.json immediately. The stream will be stopped if it is currently running.`))return;
  const r=await api('delete_stream',{name});
  if(r?.ok){
    if(_configSelected===name) cancelConfig();
    loadConfig();
  }
}

// ═══════════════════════════════════
// SETTINGS
// ═══════════════════════════════════
const _settings={autoref:true,autoscroll:true,compact:false,showrtsp:true,notifStart:true,notifErr:true,notifEvent:false};

function toggleSetting(key,el){
  _settings[key]=!_settings[key];
  el.classList.toggle('on',_settings[key]);
  applySettings();
}

function applySettings(){
  // compact mode
  document.querySelectorAll('td').forEach(td=>{
    td.style.paddingTop=_settings.compact?'4px':'8px';
    td.style.paddingBottom=_settings.compact?'4px':'8px';
  });
  // sync checkboxes
  const arEl=document.getElementById('auto-ref');
  if(arEl)arEl.checked=_settings.autoref;
  const asEl=document.getElementById('log-auto');
  if(asEl)asEl.checked=_settings.autoscroll;
}

function applyPollInterval(){
  const v=parseInt(document.getElementById('st-poll-interval').value)||2500;
  clearInterval(_autoTimer);
  if(_settings.autoref) _autoTimer=setInterval(loadStreams,v);
}

// ═══════════════════════════════════
// MAIL CONFIG
// ═══════════════════════════════════
const _SMTP_PRESETS={
  outlook: {host:'smtp-mail.outlook.com', port:587, tls:true},
  office365:{host:'smtp.office365.com',   port:587, tls:true},
  yahoo:   {host:'smtp.mail.yahoo.com',   port:587, tls:true},
  gmail:   {host:'smtp.gmail.com',        port:587, tls:true},
};

function smtpPreset(key){
  const p=_SMTP_PRESETS[key];if(!p)return;
  document.getElementById('ml-host').value=p.host;
  document.getElementById('ml-port').value=p.port;
  document.getElementById('ml-tls').checked=p.tls;
  toast('Preset applied — fill in username & password','info');
}

function switchMailMode(mode){
  document.getElementById('ml-mode').value=mode;
  const isGmail=(mode==='gmail_oauth2');
  const isMs=(mode==='microsoft_oauth2');
  const isSmtp=(mode==='smtp');
  document.getElementById('ml-panel-gmail').style.display=isGmail?'':'none';
  document.getElementById('ml-panel-ms').style.display=isMs?'':'none';
  document.getElementById('ml-panel-smtp').style.display=isSmtp?'':'none';
  document.getElementById('ml-tab-gmail').classList.toggle('active',isGmail);
  document.getElementById('ml-tab-ms').classList.toggle('active',isMs);
  document.getElementById('ml-tab-smtp').classList.toggle('active',isSmtp);
}

function _setGmailUI(tokenExists){
  const dot=document.getElementById('ml-gmail-dot');
  const lbl=document.getElementById('ml-gmail-label');
  const rev=document.getElementById('ml-gmail-revoke');
  if(tokenExists){
    dot.style.background='var(--green)';
    lbl.textContent='Connected — Gmail account authorised';
    rev.style.display='';
  } else {
    dot.style.background='var(--text3)';
    lbl.textContent='Not connected';
    rev.style.display='none';
  }
}

async function loadMailConfig(){
  try{
    const d=await fetch('/api/mail_config').then(r=>r.json());
    if(d.error){document.getElementById('ml-status').textContent='⚠ '+d.error;return;}

    const mode=d.mode||'smtp';
    switchMailMode(mode);

    // SMTP fields
    document.getElementById('ml-host').value=d.smtp_host||'smtp.gmail.com';
    document.getElementById('ml-port').value=d.smtp_port||587;
    document.getElementById('ml-user').value=d.username||'';
    document.getElementById('ml-pass').value=d.password||'';
    document.getElementById('ml-from').value=d.from_addr||'';
    document.getElementById('ml-tls').checked=d.use_tls!==false;

    // Microsoft OAuth2 fields
    document.getElementById('ml-ms-client-id').value=d.ms_client_id||'';
    document.getElementById('ml-ms-username').value=d.ms_username||'';
    _setMsUI(!!d.ms_token_exists);

    // Shared fields
    document.getElementById('ml-to').value=(d.to_addrs||[]).join(', ');
    document.getElementById('ml-cooldown').value=d.cooldown_secs??300;
    document.getElementById('ml-enabled').checked=!!d.enabled;
    document.getElementById('ml-on-error').checked=d.on_error!==false;
    document.getElementById('ml-on-stop').checked=d.on_stop!==false;

    // Gmail OAuth2 status
    _setGmailUI(!!d.oauth2_token_exists);

    document.getElementById('ml-status').textContent='✓ Config loaded from mail_config.json';
    document.getElementById('ml-status').style.color='var(--green)';
  }catch(e){
    document.getElementById('ml-status').textContent='Failed to load config';
    document.getElementById('ml-status').style.color='var(--red)';
  }
}
async function saveMailConfig(){
  const toRaw=document.getElementById('ml-to').value;
  const toList=toRaw.split(',').map(s=>s.trim()).filter(Boolean);
  if(!toList.length){toast('Enter at least one To address','err');return;}
  const mode=document.getElementById('ml-mode').value;
  const payload={
    mode,
    enabled:document.getElementById('ml-enabled').checked,
    to_addrs:toList,
    on_error:document.getElementById('ml-on-error').checked,
    on_stop:document.getElementById('ml-on-stop').checked,
    cooldown_secs:parseInt(document.getElementById('ml-cooldown').value)||300,
    // SMTP fields (kept in file for easy switching)
    smtp_host:document.getElementById('ml-host').value.trim(),
    smtp_port:parseInt(document.getElementById('ml-port').value)||587,
    use_tls:document.getElementById('ml-tls').checked,
    username:document.getElementById('ml-user').value.trim(),
    password:document.getElementById('ml-pass').value,
    from_addr:document.getElementById('ml-from').value.trim(),
    // Microsoft OAuth2 fields
    ms_client_id:document.getElementById('ml-ms-client-id').value.trim(),
    ms_username:document.getElementById('ml-ms-username').value.trim(),
  };
  try{
    const r=await fetch('/api/save_mail_config',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    const j=await r.json();
    toast(j.msg||(j.ok?'Saved':'Error'),j.ok?'ok':'err');
    const st=document.getElementById('ml-status');
    st.textContent=j.ok?'✓ mail_config.json saved':'✕ '+j.msg;
    st.style.color=j.ok?'var(--green)':'var(--red)';
  }catch(e){toast('Save failed','err');}
}

async function testMailAlert(){
  const to=document.getElementById('ml-test-to').value.trim()||null;
  const st=document.getElementById('ml-status');
  st.textContent='Sending test email…';st.style.color='var(--yellow)';
  try{
    const r=await fetch('/api/test_mail_alert',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(to?{to_addr:to}:{})
    });
    const j=await r.json();
    toast(j.msg||(j.ok?'Test sent':'Failed'),j.ok?'ok':'err');
    st.textContent=j.ok?'✓ Test email sent successfully':'✕ '+j.msg;
    st.style.color=j.ok?'var(--green)':'var(--red)';
  }catch(e){toast('Test failed','err');st.textContent='Request failed';st.style.color='var(--red)';}
}

async function connectGmail(){
  const st=document.getElementById('ml-status');
  st.textContent='Starting Gmail auth flow…';st.style.color='var(--yellow)';
  try{
    const r=await fetch('/api/gmail_oauth2_start',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const j=await r.json();
    if(j.ok){
      document.getElementById('ml-gmail-poll-msg').style.display='';
      st.textContent=j.msg||'Browser opened — sign in with Google.';
      st.style.color='var(--yellow)';
    } else {
      st.textContent='✕ '+j.msg;st.style.color='var(--red)';
      toast(j.msg,'err');
    }
  }catch(e){toast('Connect failed','err');}
}

async function checkOAuthStatus(){
  try{
    const r=await fetch('/api/gmail_oauth2_status').then(res=>res.json());
    const st=document.getElementById('ml-status');
    const poll=document.getElementById('ml-gmail-poll-msg');
    if(r.status==='done'||r.token_exists){
      poll.style.display='none';
      _setGmailUI(true);
      st.textContent='✓ Gmail connected successfully!';st.style.color='var(--green)';
      toast('Gmail connected!','ok');
    } else if(r.status==='error'){
      poll.style.display='none';
      st.textContent='✕ Auth failed: '+r.error;st.style.color='var(--red)';
      toast('OAuth2 failed','err');
    } else {
      st.textContent='Still waiting for sign-in…';st.style.color='var(--yellow)';
    }
  }catch(e){toast('Status check failed','err');}
}

async function revokeGmail(){
  if(!confirm('Disconnect Gmail? You will need to re-authorise to send alerts.'))return;
  try{
    const r=await fetch('/api/gmail_oauth2_revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const j=await r.json();
    toast(j.msg||(j.ok?'Disconnected':'Error'),j.ok?'ok':'err');
    if(j.ok) _setGmailUI(false);
    document.getElementById('ml-status').textContent=j.msg;
    document.getElementById('ml-status').style.color=j.ok?'var(--green)':'var(--red)';
  }catch(e){toast('Revoke failed','err');}
}


function _setMsUI(tokenExists){
  const dot=document.getElementById('ml-ms-dot');
  const lbl=document.getElementById('ml-ms-label');
  const rev=document.getElementById('ml-ms-revoke');
  if(!dot)return;
  if(tokenExists){
    dot.style.background='var(--green)';
    lbl.textContent='Connected — Microsoft account authorised';
    rev.style.display='';
  } else {
    dot.style.background='var(--text3)';
    lbl.textContent='Not connected';
    rev.style.display='none';
  }
}

async function connectMicrosoft(){
  const clientId=document.getElementById('ml-ms-client-id').value.trim();
  const username=document.getElementById('ml-ms-username').value.trim();
  if(!clientId){toast('Enter Application (Client) ID first','err');return;}
  if(!username){toast('Enter your mailbox address first','err');return;}
  // Save config first so the server has client_id
  await saveMailConfig();
  const st=document.getElementById('ml-status');
  st.textContent='Starting Microsoft device-code flow…';st.style.color='var(--yellow)';
  try{
    const r=await fetch('/api/microsoft_oauth2_start',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ms_client_id:clientId,ms_username:username})
    });
    const j=await r.json();
    if(j.ok){
      const box=document.getElementById('ml-ms-device-box');
      box.style.display='';
      if(j.user_code) document.getElementById('ml-ms-code').textContent=j.user_code;
      if(j.verification_uri){
        const a=document.getElementById('ml-ms-uri');
        a.href=j.verification_uri; a.textContent=j.verification_uri;
      }
      st.textContent='Enter the code at the URL shown above, then click Check Status.';
      st.style.color='var(--yellow)';
    } else {
      st.textContent='✕ '+j.msg;st.style.color='var(--red)';
      toast(j.msg,'err');
    }
  }catch(e){toast('Connect failed','err');}
}

async function checkMsOAuthStatus(){
  try{
    const r=await fetch('/api/microsoft_oauth2_status').then(res=>res.json());
    const st=document.getElementById('ml-status');
    const box=document.getElementById('ml-ms-device-box');
    if(r.status==='done'||r.token_exists){
      box.style.display='none';
      _setMsUI(true);
      st.textContent='✓ Microsoft connected successfully!';st.style.color='var(--green)';
      toast('Microsoft connected!','ok');
    } else if(r.status==='error'){
      box.style.display='none';
      st.textContent='✕ Auth failed: '+r.error;st.style.color='var(--red)';
      toast('Microsoft OAuth2 failed','err');
    } else {
      st.textContent='Still waiting for sign-in…';st.style.color='var(--yellow)';
    }
  }catch(e){toast('Status check failed','err');}
}

async function revokeMicrosoft(){
  if(!confirm('Disconnect Microsoft? You will need to re-authorise to send alerts.'))return;
  try{
    const r=await fetch('/api/microsoft_oauth2_revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const j=await r.json();
    toast(j.msg||(j.ok?'Disconnected':'Error'),j.ok?'ok':'err');
    if(j.ok){_setMsUI(false);document.getElementById('ml-ms-device-box').style.display='none';}
    document.getElementById('ml-status').textContent=j.msg;
    document.getElementById('ml-status').style.color=j.ok?'var(--green)':'var(--red)';
  }catch(e){toast('Revoke failed','err');}
}

// ═══════════════════════════════════
// BACKUP & RESTORE
// ═══════════════════════════════════
async function downloadBackup(){
  const st=document.getElementById('bk-status');
  st.textContent='Preparing backup…';st.style.color='var(--yellow)';
  try{
    const include={
      streams:document.getElementById('bk-streams')?.checked!==false,
      events:document.getElementById('bk-events')?.checked!==false,
      mail:document.getElementById('bk-mail')?.checked!==false,
      resume:document.getElementById('bk-resume')?.checked!==false,
    };
    const r=await fetch('/api/backup',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(include)
    });
    if(!r.ok){const j=await r.json();throw new Error(j.msg||'Backup failed');  }
    const blob=await r.blob();
    const now=new Date();
    const ts=[now.getFullYear(),
      String(now.getMonth()+1).padStart(2,'0'),
      String(now.getDate()).padStart(2,'0'),
      '_',
      String(now.getHours()).padStart(2,'0'),
      String(now.getMinutes()).padStart(2,'0'),
      String(now.getSeconds()).padStart(2,'0')].join('');
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=`hydracast_backup_${ts}.hc`;
    a.click();
    URL.revokeObjectURL(a.href);
    st.textContent='✓ Backup downloaded';st.style.color='var(--green)';
    toast('Backup downloaded','ok');
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Backup failed: '+e.message,'err');
  }
}

async function doRestore(file){
  if(!file)return;
  if(!file.name.endsWith('.hc')){toast('Must be a .hc backup file','err');return;}
  if(!confirm('Restore from this backup?\n\nAll current configuration will be replaced and all streams will restart.\n\nFile: '+file.name))return;
  const st=document.getElementById('restore-status');
  st.textContent='Uploading…';st.style.color='var(--yellow)';
  try{
    const text=await file.text();
    let data;
    try{data=JSON.parse(text);}catch(_){throw new Error('Invalid .hc file — not valid JSON');}
    if(data.format!=='hydracast_backup'){throw new Error('Not a HydraCast backup file (missing format header)');}
    const r=await fetch('/api/restore',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    const j=await r.json();
    if(j.ok){
      st.textContent='✓ Restored — reloading in 3 s…';st.style.color='var(--green)';
      toast('Restore successful — restarting streams…','ok');
      setTimeout(()=>loadStreams(),3500);
    }else{
      throw new Error(j.msg||'Restore failed');
    }
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Restore failed: '+e.message,'err');
  }
}

// ═══════════════════════════════════
// THEME TOGGLE
// ═══════════════════════════════════
function toggleTheme(){
  const html=document.documentElement;
  const isDark=html.getAttribute('data-theme')==='dark';
  const next=isDark?'light':'dark';
  html.setAttribute('data-theme',next);
  document.getElementById('theme-toggle').textContent=isDark?'☀':'☽';
  try{localStorage.setItem('hc-theme',next);}catch(_){}
}
(function applyStoredTheme(){
  try{
    const t=localStorage.getItem('hc-theme');
    if(t&&t!=='dark'){
      document.documentElement.setAttribute('data-theme',t);
      const btn=document.getElementById('theme-toggle');
      if(btn)btn.textContent='☀';
    }
  }catch(_){}
})();

// ═══════════════════════════════════
// INIT
// ═══════════════════════════════════
(async function init(){
  loadStreams();
  updateStats();
  toggleAuto(true);
  setInterval(updateStats,8000);
  setInterval(()=>{
    const now=new Date();
    const el=document.getElementById('h-time');
    if(el) el.textContent=[now.getHours(),now.getMinutes(),now.getSeconds()]
      .map(n=>String(n).padStart(2,'0')).join(':');
  },1000);
  setInterval(()=>{
    if(document.getElementById('tab-logs').classList.contains('active')) loadLogs();
  },4000);
  setInterval(()=>{
    if(document.getElementById('tab-events').classList.contains('active')) loadEvents();
  },10000);
  setInterval(()=>{
    if(document.getElementById('tab-viewer').classList.contains('active')) loadViewer();
  },5000);
})();

// Keyboard shortcuts
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT')return;
  if((e.key==='r'||e.key==='R')&&!e.ctrlKey&&!e.metaKey){loadStreams();toast('Refreshed','info');}
  if(e.key==='Escape'){closeSeek();}
});
document.getElementById('seek-modal').addEventListener('click',e=>{
  if(e.target===e.currentTarget)closeSeek();
});
</script>
</body>
</html>

"""


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

# =============================================================================
# REQUEST HANDLER
# =============================================================================
class WebHandler(BaseHTTPRequestHandler):

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
            "/api/events":         self._get_events,
            "/api/logs":           lambda: self._get_logs(qs),
            "/api/system_stats":   self._get_system_stats,
            "/api/stream_detail":  lambda: self._get_stream_detail(qs),
            "/api/stream_view":    lambda: self._get_stream_view(qs),
            "/api/mail_config":              self._get_mail_config,
            "/api/gmail_oauth2_status":      self._get_gmail_oauth2_status,
            "/api/microsoft_oauth2_status":  self._get_ms_oauth2_status,
        }

        handler = routes.get(path)
        if handler:
            try:
                handler()
            except Exception as exc:
                log.error("WebHandler GET %s: %s", path, exc)
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
                "speed":          st.speed,
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
                "hls_enabled":          cfg.hls_enabled,
                # Compliance fields (v5.0.6+)
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

    # ── POST dispatch ────────────────────────────────────────────────────────
    def _dispatch(self, action: str, data: Dict[str, Any]) -> None:
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
                post_action = str(data.get("post_action", "resume")).strip()
                notes       = str(data.get("notes", "")).strip()[:200]
                if post_action not in ("resume", "stop", "black"):
                    post_action = "resume"
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
                ev = OneShotEvent(
                    event_id    = ev_id,
                    stream_name = stream_name,
                    file_path   = fp,
                    play_at     = dt,
                    post_action = post_action,
                    start_pos   = start_pos,
                )
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


# =============================================================================
# SERVER
# =============================================================================
class _HydraCastHTTPServer(HTTPServer):
    allow_reuse_address = True


class WebServer:
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
            log.info("Web UI → http://0.0.0.0:%d", self._port)
        except OSError as exc:
            log.error(
                "Web UI failed to bind :%d — %s. "
                "Try --web-port to use a different port.",
                self._port, exc,
            )
        except Exception as exc:
            log.error("Web UI failed to start: %s", exc)

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
