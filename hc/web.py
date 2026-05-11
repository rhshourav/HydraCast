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
from hc.csv_manager import CSVManager
from hc.models import OneShotEvent, PlaylistItem, StreamConfig, StreamStatus
from hc.utils import _fmt_duration, _fmt_size, _local_ip, _safe_path

log = logging.getLogger(__name__)

# Module-level manager reference (set by hydracast.py)
_WEB_MANAGER: Optional[Any] = None


# =============================================================================
# MINIMAL HTML UI
# =============================================================================
_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HydraCast</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0e1117;--bg2:#161b22;--bg3:#21262d;--border:#30363d;
  --text:#e6edf3;--muted:#7d8590;--green:#3fb950;--red:#f85149;
  --yellow:#d29922;--blue:#58a6ff;--cyan:#39d0d8;
  --font:'Courier New',monospace;
}
body{background:var(--bg);color:var(--text);font:13px/1.5 var(--font);min-height:100vh}
a{color:var(--blue);text-decoration:none}
a:hover{text-decoration:underline}

/* ─ HEADER ─ */
header{
  background:var(--bg2);border-bottom:1px solid var(--border);
  padding:10px 20px;display:flex;align-items:center;gap:16px;
  position:sticky;top:0;z-index:50;
}
.logo{font-weight:bold;font-size:16px;color:var(--cyan)}
.logo span{color:var(--muted);font-size:11px;margin-left:6px}
.hstats{margin-left:auto;display:flex;gap:16px;font-size:11px;color:var(--muted)}
.hstats b{color:var(--text)}

/* ─ TABS ─ */
nav{background:var(--bg2);border-bottom:1px solid var(--border);padding:0 20px;display:flex;gap:0}
nav button{
  background:none;border:none;color:var(--muted);cursor:pointer;
  font:13px var(--font);padding:8px 16px;
  border-bottom:2px solid transparent;
}
nav button:hover{color:var(--text)}
nav button.on{color:var(--blue);border-bottom-color:var(--blue)}

/* ─ MAIN ─ */
.main{padding:16px 20px;max-width:1400px;margin:0 auto}

/* ─ TABLES ─ */
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;padding:7px 10px;color:var(--muted);font-weight:normal;
   border-bottom:1px solid var(--border);white-space:nowrap;font-size:11px;
   text-transform:uppercase;letter-spacing:.06em}
td{padding:7px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:hover td{background:rgba(255,255,255,.02)}

/* ─ BUTTONS ─ */
.btn{
  background:var(--bg3);border:1px solid var(--border);color:var(--text);
  cursor:pointer;font:11px var(--font);padding:4px 10px;border-radius:4px;
  display:inline-flex;align-items:center;gap:4px;white-space:nowrap;
}
.btn:hover{border-color:var(--muted)}
.g{background:rgba(63,185,80,.12);border-color:rgba(63,185,80,.3);color:var(--green)}
.g:hover{background:rgba(63,185,80,.2)}
.r{background:rgba(248,81,73,.12);border-color:rgba(248,81,73,.3);color:var(--red)}
.r:hover{background:rgba(248,81,73,.2)}
.b{background:rgba(88,166,255,.1);border-color:rgba(88,166,255,.25);color:var(--blue)}
.b:hover{background:rgba(88,166,255,.2)}

/* ─ STATUS BADGE ─ */
.badge{
  display:inline-block;font-size:10px;font-weight:bold;
  padding:2px 7px;border-radius:10px;letter-spacing:.04em;
}
.LIVE{background:rgba(63,185,80,.18);color:var(--green);border:1px solid rgba(63,185,80,.35)}
.STOPPED{background:rgba(125,133,144,.1);color:var(--muted);border:1px solid var(--border)}
.STARTING{background:rgba(210,153,34,.15);color:var(--yellow);border:1px solid rgba(210,153,34,.3)}
.ERROR{background:rgba(248,81,73,.15);color:var(--red);border:1px solid rgba(248,81,73,.3)}
.SCHED{background:rgba(88,166,255,.12);color:var(--blue);border:1px solid rgba(88,166,255,.25)}
.DISABLED{background:rgba(50,50,60,.2);color:var(--muted);border:1px solid var(--border)}
.ONESHOT{background:rgba(130,80,255,.15);color:#a78bfa;border:1px solid rgba(130,80,255,.3)}

/* ─ PROGRESS ─ */
.prog{height:5px;background:var(--bg3);border-radius:3px;overflow:hidden;min-width:100px}
.prog-fill{height:100%;border-radius:3px;background:var(--green);transition:width .5s}

/* ─ LOG BOX ─ */
#logbox{
  background:var(--bg);border:1px solid var(--border);border-radius:4px;
  padding:10px;height:480px;overflow-y:auto;font-size:11px;line-height:1.7;
}
.li{color:var(--text)}.lw{color:var(--yellow)}.le{color:var(--red);font-weight:bold}

/* ─ FORM ─ */
.form-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px}
.fg{display:flex;flex-direction:column;gap:4px;flex:1;min-width:140px}
label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
input,select,textarea{
  background:var(--bg3);border:1px solid var(--border);color:var(--text);
  border-radius:4px;padding:5px 8px;font:12px var(--font);width:100%;
}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--blue)}
textarea{resize:vertical}

/* ─ MONO CHIP ─ */
.chip{
  display:inline-block;background:var(--bg3);border:1px solid var(--border);
  border-radius:3px;padding:1px 6px;font-size:10px;color:var(--cyan);
  cursor:pointer;max-width:220px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;vertical-align:middle;
}
.chip:hover{border-color:var(--cyan)}

/* ─ TOAST ─ */
#toast{
  position:fixed;bottom:20px;right:20px;z-index:999;
  background:var(--bg2);border:1px solid var(--border);border-radius:4px;
  padding:8px 16px;font-size:12px;
  transform:translateX(120%);transition:transform .25s;pointer-events:none;
}
#toast.show{transform:translateX(0)}
#toast.err{border-color:var(--red);color:var(--red)}
#toast.ok{border-color:var(--green);color:var(--green)}

.tab{display:none}.tab.on{display:block}
.section-title{font-size:11px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.07em;margin-bottom:8px;padding-bottom:4px;
  border-bottom:1px solid var(--border)}

/* ─ UPLOAD ─ */
#dropzone{
  border:2px dashed var(--border);border-radius:6px;padding:32px;
  text-align:center;cursor:pointer;color:var(--muted);font-size:13px;
  margin-bottom:12px;
}
#dropzone:hover,#dropzone.over{border-color:var(--blue);color:var(--blue)}
#uplist{list-style:none;display:flex;flex-direction:column;gap:5px}
#uplist li{display:flex;align-items:center;gap:8px;font-size:11px;
  background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:5px 10px}
.ubar{flex:1;height:3px;background:var(--bg);border-radius:3px;overflow:hidden}
.ufill{height:100%;background:var(--blue);border-radius:3px}
</style>
</head>
<body>

<header>
  <div class="logo">HydraCast <span id="ver"></span></div>
  <div class="hstats">
    <span>LIVE <b id="h-live">0</b></span>
    <span>CPU <b id="h-cpu">—</b></span>
    <span>RAM <b id="h-ram">—</b></span>
    <span id="h-time"></span>
  </div>
  <div style="display:flex;gap:6px;margin-left:16px">
    <button class="btn g" onclick="api('start_all',{})">▶ All</button>
    <button class="btn r" onclick="api('stop_all',{})">■ All</button>
  </div>
</header>

<nav>
  <button class="on" onclick="tab('streams',this)">Streams</button>
  <button onclick="tab('logs',this)">Logs</button>
  <button onclick="tab('upload',this)">Upload</button>
  <button onclick="tab('events',this)">Events</button>
</nav>

<div class="main">

<!-- STREAMS -->
<div id="tab-streams" class="tab on">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
    <span class="section-title" style="margin:0">Live Streams</span>
    <button class="btn b" onclick="loadStreams()">↻ Refresh</button>
    <label style="font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px">
      <input type="checkbox" id="auto" checked onchange="toggleAuto(this.checked)">
      Auto-refresh
    </label>
  </div>
  <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>#</th><th>Name</th><th>Port</th><th>Status</th>
        <th>Progress</th><th>Position</th><th>FPS</th>
        <th>RTSP URL</th><th>Actions</th>
      </tr></thead>
      <tbody id="stbl"></tbody>
    </table>
  </div>
</div>

<!-- LOGS -->
<div id="tab-logs" class="tab">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
    <span class="section-title" style="margin:0">Event Log</span>
    <select id="log-stream" style="width:150px;height:26px;padding:2px 6px" onchange="loadLogs()">
      <option value="">All streams</option>
    </select>
    <select id="log-level" style="width:100px;height:26px;padding:2px 6px" onchange="loadLogs()">
      <option value="ALL">ALL</option>
      <option value="INFO">INFO</option>
      <option value="WARN">WARN</option>
      <option value="ERROR">ERROR</option>
    </select>
    <button class="btn b" onclick="loadLogs()">↻</button>
    <label style="font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px">
      <input type="checkbox" id="log-auto" checked> Auto-scroll
    </label>
  </div>
  <div id="logbox"></div>
</div>

<!-- UPLOAD -->
<div id="tab-upload" class="tab">
  <div style="margin-bottom:10px">
    <div class="section-title">Upload Media</div>
    <div class="form-row" style="margin-bottom:10px">
      <div class="fg" style="max-width:260px">
        <label>Sub-folder (optional)</label>
        <select id="upload-subdir"></select>
      </div>
      <button class="btn" onclick="mkSubdir()" style="margin-bottom:1px">+ New folder</button>
    </div>
  </div>
  <div id="dropzone" onclick="document.getElementById('fpick').click()">
    Drop files here or click to browse<br>
    <span style="font-size:11px">MP4 MKV AVI MOV TS FLV WMV WEBM MPG MP3 AAC FLAC WAV OGG — max 10 GB</span>
  </div>
  <input type="file" id="fpick" multiple accept="video/*,audio/*" style="display:none"
         onchange="doUpload(this.files)">
  <ul id="uplist"></ul>
</div>

<!-- EVENTS -->
<div id="tab-events" class="tab">
  <div class="section-title" style="margin-bottom:12px">Schedule One-Shot Event</div>
  <div class="form-row">
    <div class="fg"><label>Stream</label><select id="ev-stream"></select></div>
    <div class="fg"><label>Video file</label><select id="ev-file"></select></div>
    <div class="fg"><label>Play at (local time)</label>
      <input type="datetime-local" id="ev-dt"></div>
  </div>
  <div class="form-row">
    <div class="fg" style="max-width:160px"><label>Start position</label>
      <input type="text" id="ev-pos" value="00:00:00" placeholder="HH:MM:SS"></div>
    <div class="fg"><label>After playback</label>
      <select id="ev-post">
        <option value="resume">Resume playlist</option>
        <option value="stop">Stop stream</option>
        <option value="black">Black screen</option>
      </select></div>
    <button class="btn g" onclick="schedEvent()" style="margin-bottom:1px">Schedule</button>
  </div>

  <div style="margin-top:20px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
      <span class="section-title" style="margin:0">Pending Events</span>
      <button class="btn r" onclick="clearPlayed()">Clear Played</button>
      <button class="btn b" onclick="loadEvents()">↻</button>
    </div>
    <table>
      <thead><tr>
        <th>Stream</th><th>File</th><th>Play At</th>
        <th>Countdown</th><th>After</th><th>Status</th><th></th>
      </tr></thead>
      <tbody id="evtbl"></tbody>
    </table>
  </div>
</div>

</div><!-- /main -->
<div id="toast"></div>

<script>
// ═══════════════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════════════
function esc(s){
  return String(s??'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtSecs(s){
  s=Math.max(0,Math.floor(+s||0));
  return [Math.floor(s/3600),Math.floor((s%3600)/60),s%60]
    .map(n=>String(n).padStart(2,'0')).join(':');
}
function fmtBytes(n){
  if(n<1024)return n+' B';
  if(n<1048576)return (n/1024).toFixed(1)+' KB';
  if(n<1073741824)return (n/1048576).toFixed(1)+' MB';
  return (n/1073741824).toFixed(2)+' GB';
}
let _nt;
function toast(msg,type='ok'){
  const el=document.getElementById('toast');
  el.textContent=msg;el.className='show '+type;
  clearTimeout(_nt);_nt=setTimeout(()=>el.className='',type==='err'?5000:2800);
}

// ═══════════════════════════════════════════════════
// TABS
// ═══════════════════════════════════════════════════
function tab(name,btn){
  document.querySelectorAll('.tab').forEach(el=>el.classList.remove('on'));
  document.querySelectorAll('nav button').forEach(el=>el.classList.remove('on'));
  document.getElementById('tab-'+name).classList.add('on');
  btn.classList.add('on');
  if(name==='streams') loadStreams();
  else if(name==='logs'){fillLogStreamSel();loadLogs();}
  else if(name==='upload') loadSubdirs();
  else if(name==='events'){loadEvtForm();loadEvents();}
}

// ═══════════════════════════════════════════════════
// API
// ═══════════════════════════════════════════════════
async function api(action,data){
  try{
    const r=await fetch('/api/'+action,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    const j=await r.json();
    if(j.ok) toast(j.msg||'Done ✓','ok');
    else toast(j.msg||'Error','err');
    loadStreams();
    return j;
  }catch(e){toast('Request failed','err');}
}

// ═══════════════════════════════════════════════════
// HEADER STATS
// ═══════════════════════════════════════════════════
async function updateStats(){
  try{
    const r=await fetch('/api/system_stats');
    const s=await r.json();
    document.getElementById('h-cpu').textContent=s.cpu+'%';
    document.getElementById('h-ram').textContent=s.mem_percent+'%';
  }catch(_){}
}

// ═══════════════════════════════════════════════════
// STREAMS
// ═══════════════════════════════════════════════════
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
    if(data[0]) document.getElementById('ver').textContent='v'+data[0].app_ver;
    renderStreams(data);
  }catch(_){}
}

function renderStreams(data){
  const tb=document.getElementById('stbl');
  tb.innerHTML=data.map((s,i)=>{
    const pct=Math.max(0,Math.min(100,+s.progress)).toFixed(1);
    const fc=s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
    const status=s.status||'STOPPED';
    const pos=s.position||'--';
    return `<tr>
      <td style="color:var(--muted)">${i+1}</td>
      <td><b>${esc(s.name)}</b>${s.shuffle?' <small style="color:var(--muted)">[SHUF]</small>':''}</td>
      <td style="color:var(--cyan)">:${s.port}</td>
      <td><span class="badge ${esc(status)}">${esc(status)}</span></td>
      <td style="min-width:130px">
        <div class="prog"><div class="prog-fill" style="width:${pct}%;background:${fc}"></div></div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px">${pct}%</div>
      </td>
      <td style="font-size:11px;color:var(--muted);white-space:nowrap">${esc(pos)}</td>
      <td style="color:var(--muted)">${s.fps>0?Math.round(s.fps)+'fps':'--'}</td>
      <td>
        <span class="chip" onclick="copy('${esc(s.rtsp_url)}')" title="${esc(s.rtsp_url)}">${esc(s.rtsp_url)}</span>
      </td>
      <td>
        <div style="display:flex;gap:3px;flex-wrap:wrap">
          <button class="btn g" onclick="api('start',{name:'${esc(s.name)}'})">▶</button>
          <button class="btn r" onclick="api('stop',{name:'${esc(s.name)}'})">■</button>
          <button class="btn" onclick="api('restart',{name:'${esc(s.name)}'})">↺</button>
          ${s.playlist_count>1?`<button class="btn" onclick="api('skip_next',{name:'${esc(s.name)}'})">⏭</button>`:''}
          ${s.status==='LIVE'?`<button class="btn b" onclick="openSeek('${esc(s.name)}',${s.duration||0},${s.current_secs||0})">⏩</button>`:''}
        </div>
        ${s.error_msg?`<div style="font-size:10px;color:var(--red);margin-top:3px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(s.error_msg)}">⚠ ${esc(s.error_msg)}</div>`:''}
      </td>
    </tr>`;
  }).join('');
}

function copy(url){
  navigator.clipboard.writeText(url).then(()=>toast('Copied ✓','ok'));
}

// ── Inline seek ──
function openSeek(name,dur,cur){
  const secs=prompt(`Seek [${name}] to (seconds or HH:MM:SS)\nDuration: ${fmtSecs(dur)}\nCurrent: ${fmtSecs(cur)}`);
  if(secs===null) return;
  let s;
  const p=secs.trim().split(':').map(Number);
  if(p.length===3) s=p[0]*3600+p[1]*60+p[2];
  else if(p.length===2) s=p[0]*60+p[1];
  else s=+p[0];
  if(isNaN(s)||s<0){toast('Invalid time','err');return;}
  api('seek',{name,seconds:s});
}

// ═══════════════════════════════════════════════════
// LOGS
// ═══════════════════════════════════════════════════
async function fillLogStreamSel(){
  try{
    const data=await fetch('/api/streams').then(r=>r.json());
    const sel=document.getElementById('log-stream');
    const cur=sel.value;
    sel.innerHTML='<option value="">All streams</option>'+
      data.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
    if(cur) sel.value=cur;
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
      return `<div class="${cls}">${esc(m)}</div>`;
    }).join('')||'<span style="color:var(--muted)">No log entries.</span>';
    if(document.getElementById('log-auto').checked) box.scrollTop=0;
  }catch(_){}
}

// ═══════════════════════════════════════════════════
// UPLOAD
// ═══════════════════════════════════════════════════
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
  if(!n||!n.trim()) return;
  const r=await api('create_subdir',{name:n.trim()});
  if(r&&r.ok) loadSubdirs();
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
  li.innerHTML=`<span style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(file.name)}</span>
    <span style="color:var(--muted)">${fmtBytes(file.size)}</span>
    <div class="ubar"><div class="ufill" id="uf-${id}" style="width:0"></div></div>
    <span id="up-${id}" style="min-width:30px;text-align:right;color:var(--muted)">0%</span>`;
  document.getElementById('uplist').appendChild(li);
  const fd=new FormData();
  fd.append('file',file);
  fd.append('subdir',document.getElementById('upload-subdir').value);
  const xhr=new XMLHttpRequest();
  xhr.upload.onprogress=e=>{
    if(!e.lengthComputable) return;
    const p=Math.round(e.loaded/e.total*100);
    const b=document.getElementById('uf-'+id);
    const t=document.getElementById('up-'+id);
    if(b)b.style.width=p+'%';if(t)t.textContent=p+'%';
  };
  xhr.onload=()=>{
    const t=document.getElementById('up-'+id);
    try{
      const j=JSON.parse(xhr.responseText);
      if(xhr.status===200&&j.ok){if(t){t.textContent='✓';t.style.color='var(--green)';}toast(file.name+' uploaded','ok');}
      else{if(t){t.textContent='✗';t.style.color='var(--red)';}toast('Failed: '+(j.msg||file.name),'err');}
    }catch(_){if(t){t.textContent='✗';t.style.color='var(--red)';}}
  };
  xhr.onerror=()=>toast('Network error: '+file.name,'err');
  xhr.open('POST','/api/upload');xhr.send(fd);
}

// ═══════════════════════════════════════════════════
// EVENTS
// ═══════════════════════════════════════════════════
async function loadEvtForm(){
  try{
    const[streams,lib]=await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/library').then(r=>r.json()),
    ]);
    document.getElementById('ev-stream').innerHTML=
      streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
    document.getElementById('ev-file').innerHTML=
      lib.map(f=>`<option value="${esc(f.full_path)}">${esc(f.path)}</option>`).join('');
    const dt=new Date(Date.now()+5*60000);
    document.getElementById('ev-dt').value=
      new Date(dt-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);
  }catch(_){}
}

async function schedEvent(){
  const stream=document.getElementById('ev-stream').value;
  const file=document.getElementById('ev-file').value;
  const dt=document.getElementById('ev-dt').value;
  const pos=document.getElementById('ev-pos').value||'00:00:00';
  const post=document.getElementById('ev-post').value;
  if(!stream||!file||!dt){toast('Fill all fields','err');return;}
  await api('add_event',{stream_name:stream,file_path:file,play_at:dt,start_pos:pos,post_action:post});
  loadEvents();
}

async function loadEvents(){
  try{
    const data=await fetch('/api/events').then(r=>r.json());
    const now=Date.now();
    document.getElementById('evtbl').innerHTML=data.map(ev=>{
      const pa=new Date(ev.play_at.replace(' ','T'));
      const d=((pa-now)/1000).toFixed(0);
      const cd=ev.played?'—':d>0?`in ${Math.floor(d/60)}m ${d%60}s`:`${Math.abs(d)}s ago`;
      return `<tr>
        <td style="color:var(--blue)">${esc(ev.stream_name)}</td>
        <td style="font-size:11px">${esc(ev.file_name)}</td>
        <td style="font-size:11px;white-space:nowrap">${esc(ev.play_at)}</td>
        <td style="font-size:11px;color:${d>0?'var(--yellow)':'var(--muted)'}">${cd}</td>
        <td style="font-size:11px">${esc(ev.post_action)}</td>
        <td><span class="badge ${ev.played?'STOPPED':'SCHED'}">${ev.played?'Played':'Pending'}</span></td>
        <td><button class="btn r" onclick="delEvent('${esc(ev.event_id)}')">✕</button></td>
      </tr>`;
    }).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">No events.</td></tr>';
  }catch(_){}
}

async function delEvent(id){
  if(!confirm('Delete event?')) return;
  const r=await api('delete_event',{event_id:id});
  if(r&&r.ok) loadEvents();
}

async function clearPlayed(){
  if(!confirm('Remove all played events?')) return;
  try{
    const evts=await fetch('/api/events').then(r=>r.json());
    const ids=evts.filter(e=>e.played).map(e=>e.event_id);
    if(!ids.length){toast('Nothing to clear','ok');return;}
    const r=await fetch('/api/delete_played_events',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({event_ids:ids})
    });
    const j=await r.json();
    toast(j.ok?(j.msg||'Cleared ✓'):(j.msg||'Error'),j.ok?'ok':'err');
    loadEvents();
  }catch(e){toast('Error: '+e,'err');}
}

// ═══════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════
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
  // Auto-refresh logs when on that tab
  setInterval(()=>{
    if(document.getElementById('tab-logs').classList.contains('on')) loadLogs();
  },4000);
})();

document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){}
  if((e.key==='r'||e.key==='R')&&document.activeElement.tagName==='BODY'){
    loadStreams();toast('Refreshed','ok');
  }
});
</script>
</body>
</html>"""


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
            "streams":   mgr.health_summary(),
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

    # ── POST dispatch ────────────────────────────────────────────────────────
    def _dispatch(self, action: str, data: Dict[str, Any]) -> None:
        mgr = _WEB_MANAGER
        if not mgr:
            self._json({"ok": False, "msg": "Manager not ready"})
            return

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
                if post_action not in ("resume", "stop", "black"):
                    post_action = "resume"
                if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", start_pos):
                    start_pos = "00:00:00"
                dt = None
                for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt = datetime.strptime(play_at, fmt); break
                    except ValueError:
                        continue
                if dt is None:
                    raise ValueError("Invalid datetime")
                fp   = Path(file_path)
                safe = _safe_path(fp, MEDIA_DIR())
                if safe is None and not fp.exists():
                    raise ValueError("File not found or path unsafe")
                ev = OneShotEvent(
                    event_id=hashlib.md5(f"{stream_name}{play_at}{file_path}".encode()).hexdigest()[:8],
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
            ids = data.get("event_ids", [])
            if not isinstance(ids, list):
                self._json({"ok": False, "msg": "event_ids must be a list"})
                return
            id_set = set(str(i).strip() for i in ids)
            before = len(mgr.events)
            mgr.events = [e for e in mgr.events if e.event_id not in id_set]
            CSVManager.save_events(mgr.events)
            self._json({"ok": True, "msg": f"Removed {before - len(mgr.events)} event(s)"})

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
            self._json({"ok": True, "msg": f"Saved: {safe_name}"})
        except Exception as exc:
            log.error("Upload error: %s", exc)
            self._json({"ok": False, "msg": f"Upload error: {exc}"}, 500)


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
