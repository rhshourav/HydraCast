"""hc/web_html.py  —  HTML template for the HydraCast Web UI.

This module contains only the _HTML string. Import it via::

    from hc.web_html import _HTML
"""
_HTML = r"""
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HydraCast</title>
<link rel="icon" type="image/svg+xml" href="https://raw.githubusercontent.com/rhshourav/HydraCast/refs/heads/main/resources/HydraCast.svg">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.10.0/dist/tabler-icons.min.css">
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
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

/* ── Calendar design tokens — maps EventsCalendar generic vars to HydraCast theme ── */
:root,[data-theme="dark"]{
  --color-background-primary:var(--bg2);
  --color-background-secondary:var(--bg3);
  --color-background-info:var(--blue-dim);
  --color-background-success:var(--green-dim);
  --color-background-danger:var(--red-dim);
  --color-text-primary:var(--text);
  --color-text-secondary:var(--text2);
  --color-text-tertiary:var(--text3);
  --color-text-info:var(--blue);
  --color-text-success:var(--green);
  --color-text-danger:var(--red);
  --color-border-primary:var(--border);
  --color-border-secondary:var(--border2);
  --color-border-tertiary:var(--border);
  --color-border-info:rgba(122,159,194,0.45);
  --color-border-success:rgba(107,142,107,0.45);
  --color-border-danger:rgba(194,120,120,0.45);
  --border-radius-sm:6px;
  --border-radius-md:var(--radius);
  --border-radius-lg:var(--radius-lg);
}
[data-theme="light"]{
  --color-background-primary:var(--bg2);
  --color-background-secondary:var(--bg3);
  --color-background-info:var(--blue-dim);
  --color-background-success:var(--green-dim);
  --color-background-danger:var(--red-dim);
  --color-text-primary:var(--text);
  --color-text-secondary:var(--text2);
  --color-text-tertiary:var(--text3);
  --color-text-info:var(--blue);
  --color-text-success:var(--green);
  --color-text-danger:var(--red);
  --color-border-primary:var(--border);
  --color-border-secondary:var(--border2);
  --color-border-tertiary:var(--border);
  --color-border-info:rgba(74,106,138,0.4);
  --color-border-success:rgba(74,122,74,0.4);
  --color-border-danger:rgba(168,80,80,0.4);
  --border-radius-sm:6px;
  --border-radius-md:var(--radius);
  --border-radius-lg:var(--radius-lg);
}

/* ── Calendar container ── */
#events-calendar-root{
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:var(--radius-lg);
  overflow:hidden;
  flex:1;
  min-height:0;
  transition:background 0.35s,border-color 0.35s;
}
#events-calendar-root button{
  background:var(--bg3);
  border:1px solid var(--border);
  color:var(--text2);
  cursor:pointer;
  font:500 12px var(--font-sans);
  padding:5px 12px;
  border-radius:var(--radius);
  display:inline-flex;align-items:center;gap:5px;
  transition:all 0.18s;
}
#events-calendar-root button:hover{
  border-color:var(--border2);color:var(--text);background:var(--bg4);
}
#events-calendar-root button:disabled{opacity:0.5;pointer-events:none}
#events-calendar-root input,
#events-calendar-root select{
  background:var(--bg3);
  border:1px solid var(--border);
  color:var(--text);
  font:14px var(--font-sans);
  padding:6px 10px;
  border-radius:var(--radius);
  outline:none;
  transition:border-color 0.18s;
}
#events-calendar-root input:focus,
#events-calendar-root select:focus{border-color:var(--accent)}
#events-calendar-root select[size]{padding:4px 6px}

/* ─────────── KEYFRAMES ─────────── */
@keyframes toastIn{
  from{opacity:0;transform:translateX(-50%) translateY(12px) scale(0.92)}
  to{opacity:1;transform:translateX(-50%) translateY(0) scale(1)}
}
@keyframes pulse{
  0%,100%{opacity:1;transform:scale(1)}
  50%{opacity:0.45;transform:scale(0.82)}
}
/* ── Calendar day cell hover glow ── */
#events-calendar-root .cal-day-cell{
  transition:background 0.15s, box-shadow 0.15s;
}
#events-calendar-root .cal-day-cell:hover{
  box-shadow:inset 0 0 0 2px var(--accent);
  z-index:1;
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
/* ─────────── COMPLIANCE ALERT BANNER ─────────── */
@keyframes compliancePulse{
  0%,100%{opacity:1;border-color:rgba(194,120,120,0.6);box-shadow:0 0 0 0 rgba(194,120,120,0)}
  50%{opacity:0.88;border-color:rgba(194,120,120,1);box-shadow:0 0 10px 3px rgba(194,120,120,0.22)}
}
.compliance-alert-banner{
  position:fixed;right:18px;top:72px;z-index:9999;
  max-width:370px;min-width:260px;
  background:var(--bg2);
  border:1.5px solid var(--red);
  border-radius:var(--radius-lg);
  padding:14px 16px;
  box-shadow:0 4px 20px rgba(194,120,120,0.18);
  animation:compliancePulse 3s ease-in-out infinite;
  display:flex;flex-direction:column;gap:8px;
}
.compliance-alert-banner .cab-hdr{
  display:flex;align-items:center;gap:8px;font-weight:700;
  font-size:12px;color:var(--red);font-family:var(--font-display);
  letter-spacing:0.04em;text-transform:uppercase;
}
.compliance-alert-banner .cab-body{
  font-size:12px;color:var(--text2);line-height:1.5;
}
.compliance-alert-banner .cab-stream{
  font-size:11px;color:var(--text3);font-family:var(--font-mono);margin-top:2px;
}
.compliance-alert-banner .cab-dismiss{
  align-self:flex-end;background:none;border:1px solid var(--border);
  color:var(--text3);cursor:pointer;font:500 11px var(--font-sans);
  padding:4px 10px;border-radius:6px;transition:all 0.2s;
}
.compliance-alert-banner .cab-dismiss:hover{
  border-color:var(--red);color:var(--red);background:var(--red-dim);
}
.cab-dot{
  display:inline-block;width:8px;height:8px;border-radius:50%;
  background:var(--red);flex-shrink:0;
  box-shadow:0 0 0 0 rgba(194,120,120,0.6);
  animation:livePulse 1.8s ease-out infinite;
}
.st-comp-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-top:1px solid var(--border)}
.st-comp-row label{flex:1;font-size:13px;color:var(--text2);cursor:pointer;text-transform:none;letter-spacing:0}
.st-comp-row small{display:block;font-size:11px;color:var(--text3);margin-top:2px}

/* ─────────── PORT NOTIFICATION PANEL ─────────── */
@keyframes portPanelIn{
  from{opacity:0;transform:translateX(18px) scale(0.97)}
  to{opacity:1;transform:translateX(0) scale(1)}
}
@keyframes portPanelOut{
  from{opacity:1;transform:translateX(0) scale(1)}
  to{opacity:0;transform:translateX(18px) scale(0.95)}
}
.port-notif-panel{
  position:fixed;right:20px;top:80px;z-index:8000;
  width:300px;
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:var(--radius-lg);
  box-shadow:0 8px 32px rgba(0,0,0,0.28),0 2px 8px rgba(0,0,0,0.18);
  overflow:hidden;
  display:none;
  animation:portPanelIn 0.22s cubic-bezier(0.34,1.56,0.64,1) both;
}
.port-notif-panel.open{display:block}
.port-notif-panel.closing{animation:portPanelOut 0.18s ease both}
.port-notif-hdr{
  display:flex;align-items:center;gap:8px;
  padding:10px 14px;
  background:var(--bg3);
  border-bottom:1px solid var(--border);
}
.port-notif-hdr-title{
  flex:1;font-size:12px;font-weight:700;
  font-family:var(--font-display);
  color:var(--text2);letter-spacing:0.04em;text-transform:uppercase;
}
.port-notif-close{
  background:none;border:none;color:var(--text3);cursor:pointer;
  font-size:14px;padding:2px 4px;border-radius:5px;
  transition:color 0.15s,background 0.15s;line-height:1;
}
.port-notif-close:hover{color:var(--text);background:var(--bg4)}
.port-notif-body{padding:12px 14px;display:flex;flex-direction:column;gap:8px}
/* ── Uniform port map chip ── */
.pmc{
  display:inline-flex;align-items:center;gap:5px;
  height:26px;padding:0 10px;
  border-radius:6px;font-size:11px;font-weight:600;
  font-family:var(--font-mono);
  border:1px solid;
  white-space:nowrap;cursor:default;
  transition:box-shadow 0.15s;
}
.pmc.ok{background:var(--green-dim);border-color:rgba(107,142,107,0.4);color:var(--green)}
.pmc.err{background:var(--red-dim);border-color:rgba(194,120,120,0.4);color:var(--red);cursor:help}
.pmc-label{font-size:10px;font-weight:400;font-family:var(--font-sans);color:var(--text3);margin-left:2px}
.pmc-icon{font-size:9px;opacity:0.8}
/* Port status banner */
.pnb{
  display:flex;align-items:center;gap:8px;
  padding:8px 11px;border-radius:8px;
  font-size:12px;font-weight:500;border:1px solid;
}
.pnb.ok{background:var(--green-dim);border-color:rgba(107,142,107,0.45);color:var(--green)}
.pnb.err{background:var(--red-dim);border-color:rgba(194,120,120,0.45);color:var(--red)}
.pnb.warn{background:var(--yellow-dim);border-color:rgba(201,168,120,0.45);color:var(--yellow)}
.pnb.info{background:var(--blue-dim);border-color:rgba(122,159,194,0.35);color:var(--blue)}
/* Port map grid */
.pmgrid{display:flex;flex-wrap:wrap;gap:5px}
/* Firewall row */
.fw-row{
  display:flex;align-items:center;gap:7px;
  padding:6px 10px;border-radius:7px;
  font-size:11px;border:1px solid var(--border);
  background:var(--bg3);color:var(--text3);
}
/* Port field row in config */
.port-field-row{display:flex;align-items:center;gap:5px}
.port-field-row input[type=number]{
  width:80px;flex-shrink:0;
  font-family:var(--font-mono);font-size:13px;font-weight:600;
  text-align:center;
}
/* Icon-only square button (Suggest) */
.port-icon-btn{
  display:inline-flex;align-items:center;justify-content:center;
  width:32px;height:32px;border-radius:7px;
  font-size:14px;cursor:pointer;flex-shrink:0;
  border:1px solid;transition:all 0.18s;
  background:var(--bg3);border-color:var(--border);color:var(--text3);
}
.port-icon-btn:hover{background:var(--blue-dim);border-color:rgba(122,159,194,0.55);color:var(--blue)}
.port-icon-btn:disabled{opacity:0.45;pointer-events:none}
.port-action-btn{
  display:inline-flex;align-items:center;gap:5px;
  height:32px;padding:0 11px;border-radius:7px;
  font-size:11px;font-weight:600;cursor:pointer;
  border:1px solid;transition:all 0.18s;white-space:nowrap;flex-shrink:0;
}
.port-action-btn.suggest{
  background:var(--blue-dim);border-color:rgba(122,159,194,0.45);color:var(--blue);
}
.port-action-btn.suggest:hover{background:rgba(122,159,194,0.22);border-color:var(--blue)}
.port-action-btn.check{
  background:var(--bg3);border-color:var(--border);color:var(--text2);
}
.port-action-btn.check:hover{border-color:var(--accent);color:var(--accent);background:rgba(184,115,51,0.07)}
/* Firewall open button inside notification panel */
.fw-open-btn{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;
  width:100%;height:34px;border-radius:8px;
  font-size:12px;font-weight:600;cursor:pointer;
  border:1px solid rgba(201,168,120,0.55);
  background:var(--yellow-dim);color:var(--yellow);
  transition:all 0.2s;
}
.fw-open-btn:hover{background:rgba(201,168,120,0.22);border-color:var(--yellow)}
.fw-open-btn:disabled{opacity:0.5;pointer-events:none}
.fw-open-btn.done{background:var(--green-dim);border-color:rgba(107,142,107,0.55);color:var(--green)}
/* Info button */
.info-btn{
  display:inline-flex;align-items:center;justify-content:center;
  width:18px;height:18px;border-radius:50%;
  background:var(--bg4);border:1px solid var(--border);
  color:var(--text3);font-size:9px;cursor:help;
  transition:all 0.15s;flex-shrink:0;vertical-align:middle;
  font-style:normal;font-weight:700;
  position:relative;
}
.info-btn:hover{border-color:var(--blue);color:var(--blue);background:var(--blue-dim)}
/* Tooltip */
.info-btn .ibt{
  display:none;position:absolute;bottom:calc(100% + 7px);left:50%;
  transform:translateX(-50%);width:220px;
  background:var(--bg);border:1px solid var(--border);border-radius:8px;
  padding:8px 10px;font-size:10px;color:var(--text2);line-height:1.55;
  font-family:var(--font-sans);font-weight:400;font-style:normal;
  box-shadow:0 4px 18px rgba(0,0,0,0.25);z-index:200;
  pointer-events:none;white-space:normal;text-align:left;
}
.info-btn:hover .ibt{display:block}

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
  flex-shrink:0;
}
.logo-icon{
  width:36px;height:36px;
  background:#ffffff;
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  font-size:15px;font-weight:900;color:#333;flex-shrink:0;
  box-shadow:0 3px 10px rgba(255,255,255,0.18);
  transition:transform 0.2s,box-shadow 0.2s;
}
.logo-icon:hover{transform:scale(1.08);box-shadow:0 5px 16px rgba(255,255,255,0.28)}
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
  flex-shrink:0;
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
/* ── THEME TOGGLE (moon/sun) ── */
.hc-toggle-wrap{display:flex;align-items:center;flex-shrink:0}
.hc-toggle-cb{opacity:0;position:absolute;width:0;height:0}
.hc-toggle-label{
  background-color:#111;
  width:50px;height:26px;border-radius:50px;
  position:relative;padding:5px;cursor:pointer;
  display:flex;justify-content:space-between;align-items:center;
  transition:background 0.2s linear;
  box-shadow:0 2px 8px rgba(0,0,0,0.35);
}
[data-theme="light"] .hc-toggle-label{background-color:#b87333}
.hc-toggle-label .fa-moon{color:#f1c40f;font-size:12px}
.hc-toggle-label .fa-sun {color:#f39c12;font-size:12px}
.hc-toggle-ball{
  background-color:#fff;
  width:22px;height:22px;
  position:absolute;left:2px;top:2px;
  border-radius:50%;
  transition:transform 0.2s linear;
  box-shadow:0 1px 4px rgba(0,0,0,0.3);
}
.hc-toggle-cb:checked + .hc-toggle-label .hc-toggle-ball{
  transform:translateX(24px);
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
.main-area{flex:1;min-height:0;display:flex;flex-direction:column}
.tab-panel{display:none;flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;padding:24px}
.tab-panel.active{
  display:flex;flex-direction:column;gap:20px;
  overflow-y:auto;overflow-x:hidden;
  animation:fadeSlideIn 0.28s ease both;
}

/* ─────────── RESPONSIVE ─────────── */
/* Keep topbar at fixed 60 px — nav tabs scroll horizontally on narrow windows */
.nav-tabs{
  display:flex;gap:2px;align-items:stretch;height:100%;
  flex:1;min-width:0;
  overflow-x:auto;overflow-y:hidden;
  scrollbar-width:none;          /* Firefox */
  -ms-overflow-style:none;       /* IE/Edge */
}
.nav-tabs::-webkit-scrollbar{display:none}   /* Chrome/Safari */

@media(max-width:960px){
  .topbar{padding:0 14px}
  .logo{margin-right:14px;font-size:17px}
  .logo sub{display:none}
  .nav-tab{padding:0 12px;font-size:12px}
  .stat-pill{display:none}
  .tab-panel{padding:16px}
}
@media(max-width:600px){
  .topbar{padding:0 10px}
  .logo{margin-right:8px}
  .logo span[id="topbar-app-name"]{display:none}  /* hide text name, keep icon */
  .nav-tab{padding:0 9px;font-size:11px;gap:4px}
  .nav-tab .tab-dot{display:none}
  .hc-toggle-wrap{display:none}
  .topbar-btns .hbtn span{display:none}
  .topbar-btns .hbtn{padding:5px 8px}
  .tab-panel{padding:10px}
  .tab-panel.active{gap:12px}
  .card-body{padding:12px}
  .card-hdr{padding:10px 14px}
}

/* Responsive 2-column grid — collapses to 1 col below 700 px */
.rg-2{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
@media(max-width:700px){.rg-2{grid-template-columns:1fr}}

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
  flex-shrink:0;
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
/* The config tab must not scroll at the page level — the stream list
   sidebar scrolls internally.  We lock the tab to its viewport height
   and let the sidebar flex-child consume the leftover space. */
#tab-config{overflow:hidden;padding-bottom:0}
.config-layout{display:grid;grid-template-columns:235px 1fr;gap:18px;height:100%}
.config-sidebar{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  overflow:hidden;transition:background 0.35s,border-color 0.35s;
  display:flex;flex-direction:column;
}
.config-sidebar-hdr{
  padding:12px 16px;border-bottom:1px solid var(--border);background:var(--bg3);
  font-size:11px;font-weight:700;text-transform:uppercase;
  letter-spacing:0.1em;color:var(--text3);font-family:var(--font-display);
  flex-shrink:0;
}
#config-stream-list{
  flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;
}
#config-stream-list::-webkit-scrollbar{width:4px}
#config-stream-list::-webkit-scrollbar-track{background:transparent}
#config-stream-list::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px}
#config-stream-list::-webkit-scrollbar-thumb:hover{background:var(--text3)}
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
  overflow:hidden;display:flex;flex-direction:column;min-height:0;max-height:100%;
  transition:background 0.35s,border-color 0.35s;
}
.config-main-hdr{
  padding:16px 22px;border-bottom:1px solid var(--border);background:var(--bg3);
  display:flex;align-items:center;gap:12px;
}
.config-main-hdr h2{font-family:var(--font-display);font-size:17px;font-weight:700}
.config-main-body{padding:24px 24px 8px;overflow:auto;flex:1;scroll-padding-bottom:80px}
.config-section{margin-bottom:28px}
.config-section-title{
  font-size:11px;text-transform:uppercase;letter-spacing:0.1em;
  color:var(--accent);font-weight:700;margin-bottom:14px;padding-bottom:8px;
  border-bottom:1px solid var(--border);font-family:var(--font-display);
}
.config-main-footer{
  padding:16px 22px;border-top:1px solid var(--border);background:var(--bg3);
  display:flex;gap:10px;justify-content:flex-end;flex-shrink:0;
}

/* ─────────── PLAYLIST EDITOR ─────────── */
.pl-editor{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;margin-top:8px}
.pl-toolbar{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid var(--border);background:var(--bg4);flex-wrap:wrap}
.pl-toolbar-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text3);flex:1;min-width:0}
.pl-table{width:100%;border-collapse:collapse}
.pl-table th{padding:7px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--text3);border-bottom:1px solid var(--border);background:var(--bg4);text-align:left;white-space:nowrap}
.pl-table td{padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;vertical-align:middle}
.pl-table tr:last-child td{border-bottom:none}
.pl-table tr:hover td{background:rgba(184,115,51,0.04)}
.pl-path{font-family:var(--font-mono);font-size:11px;color:var(--text2)}
.pl-channel-tag{font-size:10px;color:var(--blue);background:var(--blue-dim);border:1px solid rgba(122,159,194,0.3);border-radius:20px;padding:1px 8px;white-space:nowrap;font-family:var(--font-sans);font-weight:500;display:inline-block}
.pl-table input[type=text]{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:3px 7px;border-radius:5px;font-size:11px;font-family:var(--font-mono);width:100%;transition:border-color 0.2s;box-sizing:border-box}
.pl-table input[type=number]{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:3px 5px;border-radius:5px;font-size:11px;font-family:var(--font-mono);transition:border-color 0.2s;box-sizing:border-box;text-align:center}
.pl-table input:focus{outline:none;border-color:var(--accent)}
.pl-add-row{display:flex;align-items:center;gap:8px;padding:9px 12px;border-top:1px solid var(--border);background:var(--bg3)}
.pl-add-row input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:5px 10px;border-radius:6px;font-size:11px;font-family:var(--font-mono);min-width:0}
.pl-add-row input:focus{outline:none;border-color:var(--accent)}
.pl-empty{padding:24px;text-align:center;color:var(--text3);font-size:12px;display:flex;flex-direction:column;align-items:center;gap:6px}
.pl-priority-badge{display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:20px;border-radius:5px;font-size:10px;font-weight:700;font-family:var(--font-mono);padding:0 5px;margin-bottom:2px}
.pl-priority-badge.high{background:rgba(107,142,107,0.18);color:var(--green);border:1px solid rgba(107,142,107,0.3)}
.pl-priority-badge.mid{background:var(--yellow-dim);color:var(--yellow);border:1px solid rgba(201,168,120,0.3)}
.pl-priority-badge.low{background:var(--bg4);color:var(--text3);border:1px solid var(--border)}
/* Dirty / unsaved indicator */
.dirty-badge{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:600;color:var(--yellow);background:var(--yellow-dim);border:1px solid rgba(201,168,120,0.4);border-radius:20px;padding:2px 9px;margin-right:auto;animation:pulse 2s infinite}
/* Unsaved modal */
.unsaved-modal-body{font-size:13px;color:var(--text2);line-height:1.65;margin-bottom:20px}
.unsaved-modal-body strong{color:var(--yellow)}

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

/* ── FILE MANAGER ── */
.fm-layout{display:grid;grid-template-columns:220px 1fr;gap:16px;height:100%;min-height:0}
.fm-sidebar{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden;display:flex;flex-direction:column;transition:background 0.35s,border-color 0.35s}
.fm-sidebar-hdr{padding:12px 16px;background:var(--bg3);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--text3);font-family:var(--font-display)}
.fm-dir-list{flex:1;overflow-y:auto;padding:6px 0}
.fm-dir-item{padding:9px 16px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:13px;transition:background 0.15s;font-family:var(--font-sans);color:var(--text2)}
.fm-dir-item:hover{background:var(--bg3)}
.fm-dir-item.active{background:rgba(184,115,51,0.09);color:var(--accent);border-left:2px solid var(--accent);padding-left:14px}
.fm-dir-icon{font-size:14px;flex-shrink:0;opacity:0.65}
.fm-main{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden;display:flex;flex-direction:column;transition:background 0.35s,border-color 0.35s}
.fm-main-hdr{padding:11px 16px;background:var(--bg3);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.fm-breadcrumb{display:flex;align-items:center;gap:3px;font-size:12px;flex:1;flex-wrap:wrap;min-width:0}
.fm-breadcrumb span{color:var(--text3);cursor:pointer;padding:2px 6px;border-radius:5px;transition:color 0.15s,background 0.15s;white-space:nowrap}
.fm-breadcrumb span:hover{color:var(--accent);background:rgba(184,115,51,0.08)}
.fm-breadcrumb .fm-sep{color:var(--text3);opacity:0.4;font-size:10px;cursor:default;padding:0 2px}
.fm-breadcrumb span.fm-cur{color:var(--text);font-weight:600;cursor:default}
.fm-toolbar{display:flex;gap:6px;flex-shrink:0}
.fm-body{flex:1;overflow-y:auto}
.fm-empty{padding:56px 24px;text-align:center;color:var(--text3);display:flex;flex-direction:column;align-items:center;gap:10px}
.fm-row{display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid var(--border);transition:background 0.12s;font-size:13px;font-family:var(--font-sans);position:relative}
.fm-row:last-child{border-bottom:none}
.fm-row:hover{background:rgba(184,115,51,0.04)}
.fm-row-icon{font-size:16px;flex-shrink:0;width:22px;text-align:center}
.fm-row-name{flex:1;font-weight:500;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:default}
.fm-row-name.is-dir{cursor:pointer;color:var(--text)}
.fm-row-name.is-dir:hover{color:var(--accent)}
.fm-row-meta{font-size:11px;color:var(--text3);white-space:nowrap;font-family:var(--font-mono);flex-shrink:0}
.fm-row-actions{display:flex;gap:4px;opacity:0;transition:opacity 0.15s;flex-shrink:0}
.fm-row:hover .fm-row-actions{opacity:1}
.fm-action-btn{background:var(--bg3);border:1px solid var(--border);color:var(--text3);cursor:pointer;font-size:11px;padding:3px 9px;border-radius:6px;transition:all 0.15s;white-space:nowrap;font-family:var(--font-sans)}
.fm-action-btn:hover{color:var(--accent);border-color:var(--accent);background:rgba(184,115,51,0.09)}
.fm-action-btn.del:hover{color:var(--red);border-color:var(--red);background:var(--red-dim)}
.fm-action-btn.cp:hover{color:var(--blue);border-color:var(--blue);background:var(--blue-dim)}
.fm-action-btn.mv:hover{color:var(--yellow);border-color:var(--yellow);background:var(--yellow-dim)}
.fm-status-bar{padding:7px 16px;font-size:11px;color:var(--text3);border-top:1px solid var(--border);background:var(--bg3);display:flex;align-items:center;gap:10px;font-family:var(--font-sans);flex-shrink:0}
.fm-status-bar b{color:var(--text2)}
/* FM Dialogs */
.fm-dialog-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:2000;display:none;align-items:center;justify-content:center;backdrop-filter:blur(5px)}
.fm-dialog-overlay.open{display:flex;animation:fadeIn 0.18s ease both}
.fm-dialog{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);padding:24px;width:440px;max-width:92vw;box-shadow:0 24px 70px var(--shadow);animation:slideUp 0.22s ease both;transition:background 0.35s,border-color 0.35s}
.fm-dialog h4{font-family:var(--font-display);font-size:16px;font-weight:700;margin-bottom:16px;color:var(--text)}
.fm-dialog-footer{display:flex;gap:8px;justify-content:flex-end;margin-top:20px}

/* ─────────── HOLIDAY POPUP ─────────── */
.hd-popup{
  position:absolute;right:0;top:calc(100% + 8px);
  width:310px;max-height:340px;overflow-y:auto;
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
  box-shadow:0 8px 32px var(--shadow);z-index:500;
  animation:slideUp 0.18s ease both;
  scrollbar-width:thin;
}
.hd-popup-hdr{
  padding:10px 14px;border-bottom:1px solid var(--border);background:var(--bg3);
  font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;
  color:var(--text3);font-family:var(--font-display);
  border-radius:var(--radius-lg) var(--radius-lg) 0 0;
  position:sticky;top:0;z-index:1;
}
.hd-row{
  padding:7px 14px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:10px;transition:background 0.15s;
}
.hd-row:last-child{border-bottom:none}
.hd-row:hover{background:var(--bg3)}
.hd-row.today{background:var(--green-dim) !important}
.hd-row.past{opacity:0.42}
.hd-date{font-family:var(--font-mono);font-size:11px;color:var(--accent-light);white-space:nowrap;min-width:82px}
.hd-name{font-size:12px;color:var(--text2);flex:1;line-height:1.4}
.hd-today-tag{font-size:10px;font-weight:700;color:var(--green);background:var(--green-dim);border:1px solid rgba(107,142,107,0.4);border-radius:20px;padding:1px 7px;white-space:nowrap}

/* ─────────── MULTI-STREAM EVENT FORM ─────────── */
.ev-stream-grid{
  display:flex;flex-direction:column;gap:0;
  background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);
  max-height:220px;overflow-y:auto;
  scrollbar-width:thin;
}
.ev-stream-row{
  display:grid;grid-template-columns:auto 1fr 1fr;gap:10px;align-items:center;
  padding:7px 12px;border-bottom:1px solid var(--border);
  font-size:12px;transition:background 0.15s;
}
.ev-stream-row:last-child{border-bottom:none}
.ev-stream-row:hover{background:var(--bg4)}
.ev-stream-row.checked{background:rgba(184,115,51,0.06)}
.ev-stream-row label{
  display:flex;align-items:center;gap:7px;cursor:pointer;
  font-size:12px;color:var(--text2);font-weight:500;
  text-transform:none;letter-spacing:0;
}
.ev-stream-row select{
  background:var(--bg);border:1px solid var(--border);color:var(--text);
  border-radius:6px;padding:4px 8px;font:12px var(--font-sans);
  width:100%;transition:border-color 0.2s;
}
.ev-stream-row select:focus{outline:none;border-color:var(--accent)}
.ev-stream-row select:disabled{opacity:0.35;pointer-events:none}



/* ════════════════════════════════════════════════════════════════════════
   RESPONSIVE  —  360 px phone  →  4 K monitor
   ════════════════════════════════════════════════════════════════════════ */

/* ── Tablet / small laptop  768 – 1199 px ── */
@media (max-width:1199px){
  .tab-panel{padding:16px 14px}
  .topbar{padding:0 16px}
  .app-footer{padding:6px 16px}
  .nav-tab{padding:0 13px;font-size:12px}
  .chip{max-width:170px}
  #logbox{height:380px}
}

/* ── Large monitor  ≥ 1600 px ── */
@media (min-width:1600px){
  .tab-panel{padding:32px 48px}
  .topbar{padding:0 48px}
  .app-footer{padding:8px 48px}
  table{font-size:14px}
  th{font-size:12px;padding:12px 16px}
  td{padding:13px 16px}
  .card-body{padding:26px}
  .chip{max-width:340px}
  #logbox{height:580px;font-size:13px}
}

/* ── Mobile  < 768 px ── */
@media (max-width:767px){
  /* Layout */
  .app{height:100svh}          /* safe viewport height on iOS */
  .tab-panel{padding:10px 8px;gap:12px}
  .topbar{padding:0 10px;height:54px}
  .app-footer{padding:5px 10px;font-size:10px;gap:5px;flex-wrap:wrap;justify-content:center}

  /* Logo — shrink to icon only */
  .logo{font-size:0;margin-right:8px}        /* hide text */
  .logo-icon{width:30px;height:30px;font-size:12px;flex-shrink:0;display:flex!important}
  .logo sub{display:none}

  /* Nav tabs — icon + dot only, labels hidden */
  .nav-tabs{gap:0;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .nav-tabs::-webkit-scrollbar{display:none}
  .nav-tab{padding:0 10px;font-size:0;gap:0;min-width:40px;justify-content:center}
  .nav-tab i,.nav-tab .ti{font-size:16px;display:block}
  .nav-tab .tab-dot{position:absolute;top:8px;right:6px}

  /* Right side — hide verbose elements */
  .stat-pill{display:none}
  .topbar-btns .hbtn span{display:none}
  .topbar-btns .hbtn{padding:6px 8px;min-width:32px;justify-content:center}

  /* Tables — horizontal scroll, tighter cells */
  .tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -8px;padding:0 8px}
  table{font-size:11px;min-width:520px}
  th{padding:8px 8px;font-size:10px}
  td{padding:9px 8px}

  /* Cards */
  .card-hdr{padding:10px 12px}
  .card-body{padding:12px}

  /* Buttons */
  .btn{font-size:11px;padding:5px 10px}
  .btn-group{flex-wrap:wrap;gap:5px}
  .badge{font-size:10px;padding:2px 7px}

  /* Chips — shorter URLs */
  .chip{max-width:120px;font-size:10px}

  /* Logbox */
  #logbox{height:260px;font-size:11px;padding:10px;line-height:1.7}

  /* File manager — stack vertically */
  .fm-layout{grid-template-columns:1fr;grid-template-rows:160px 1fr}
  .fm-sidebar{max-height:160px}

  /* Progress bar — wider min */
  .prog{min-width:60px}

  /* Modals — full-width */
  .modal{width:96vw;max-width:96vw;padding:16px}
  .fm-dialog{width:96vw;max-width:96vw;padding:16px}

  /* Misc */
  .section-hdr{margin-bottom:4px}
  .count-badge{display:none}
}

/* ── Very small  < 480 px ── */
@media (max-width:479px){
  .topbar{height:48px}
  .nav-tab{padding:0 8px;min-width:36px}
  .hc-toggle-wrap{display:none}  /* hide theme toggle */
  .tab-panel{padding:8px 6px}
}

/* ── Short screens  height < 580 px (landscape phone) ── */
@media (max-height:580px){
  .topbar{height:44px}
  #logbox{height:180px}
  .tab-panel{padding:6px}
}
</style>
</head>
<body>

<div class="app">

<!-- ══ TOP BAR ══ -->
<header class="topbar">
  <div class="logo">
    <div class="logo-icon" id="logo-icon-wrap" style="cursor:default">
      <img id="logo-img" src="/resources/logo.png" alt="HydraCast"
           style="display:none;position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:10px"
           onload="this.style.display='block';document.getElementById('logo-letter').style.display='none'"
           onerror="this.style.display='none';document.getElementById('logo-letter').style.display=''">
      <span class="logo-letter" id="logo-letter"
            style="font-size:8px;font-weight:700;letter-spacing:0.06em;color:rgba(255,255,255,0.75);text-transform:uppercase;pointer-events:none;user-select:none;position:relative;z-index:1">
        HC
      </span>
    </div>
    <span id="topbar-app-name">__APP_NAME__</span>
    <sub id="ver-badge">v__APP_VER__</sub>
  </div>

  <nav class="nav-tabs">
    <button class="nav-tab active" onclick="switchTab('streams',this)">
      <span class="tab-dot"></span>Streams
    </button>
    <button class="nav-tab" onclick="switchTab('viewer',this)">
      <span class="tab-dot"></span>Viewer
    </button>
    <button class="nav-tab" onclick="switchTab('config',this)">
      <span class="tab-dot"></span>Configure
    </button>
    <button class="nav-tab" onclick="switchTab('logs',this)">
      <span class="tab-dot"></span>Logs
    </button>
    <button class="nav-tab" onclick="switchTab('media',this);if(!_fmLoaded){_fmLoaded=true;loadFiles('');}">
      <span class="tab-dot"></span>Media
    </button>
    <button class="nav-tab" onclick="switchTab('events',this)">
      <span class="tab-dot"></span>Events
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

    <!-- ── Holidays pill ── -->
    <div style="position:relative" id="hd-wrap">
      <button class="stat-pill" id="hd-btn" onclick="toggleHolidays(event)"
          title="Public Holidays"
          style="cursor:pointer;user-select:none;border-color:rgba(154,138,176,0.35)">
        🗓&nbsp;<b id="hd-next-label" style="color:var(--purple)">Holidays</b>
      </button>
      <div class="hd-popup" id="hd-popup" style="display:none">
        <div class="hd-popup-hdr" id="hd-popup-hdr" style="display:flex;align-items:center;justify-content:space-between;gap:6px">
          <span>🗓 Holidays &nbsp;<span id="hd-year" style="color:var(--accent-light)"></span></span>
          <span style="display:flex;gap:4px;flex-shrink:0">
            <button onclick="hdRefresh()" title="Force re-fetch from library" style="background:none;border:none;color:var(--text2);cursor:pointer;font-size:13px;padding:2px 5px;border-radius:4px" onmouseover="this.style.color='var(--accent-light)'" onmouseout="this.style.color='var(--text2)'">↻</button>
            <button onclick="hdAddCustomOpen()" title="Add a custom holiday" style="background:none;border:none;color:var(--text2);cursor:pointer;font-size:13px;padding:2px 5px;border-radius:4px" onmouseover="this.style.color='var(--accent-light)'" onmouseout="this.style.color='var(--text2)'">＋</button>
          </span>
        </div>
        <div id="hd-add-form" style="display:none;padding:10px 14px;border-bottom:1px solid var(--border);background:var(--bg3)">
          <div style="display:grid;grid-template-columns:130px 1fr 80px;gap:6px;align-items:end">
            <div><label style="font-size:10px;color:var(--text3);display:block;margin-bottom:3px">Date</label>
              <input id="hd-add-date" type="date" style="width:100%;font-size:12px;padding:4px 6px;background:var(--bg4);border:1px solid var(--border2);border-radius:5px;color:var(--text)"></div>
            <div><label style="font-size:10px;color:var(--text3);display:block;margin-bottom:3px">Name</label>
              <input id="hd-add-name" placeholder="Holiday name" style="width:100%;font-size:12px;padding:4px 6px;background:var(--bg4);border:1px solid var(--border2);border-radius:5px;color:var(--text)"></div>
            <button onclick="hdAddCustomSave()" style="padding:4px 8px;font-size:12px;background:var(--accent);color:#fff;border:none;border-radius:5px;cursor:pointer;height:28px;margin-top:auto">Add</button>
          </div>
          <div id="hd-add-err" style="font-size:11px;color:var(--red);margin-top:4px;display:none"></div>
        </div>
        <div id="hd-list"><div style="padding:14px;text-align:center;color:var(--text3);font-size:12px">Loading…</div></div>
      </div>
    </div>

    <div class="hc-toggle-wrap" title="Toggle between dark and light mode">
      <input type="checkbox" class="hc-toggle-cb" id="hc-theme-cb">
      <label for="hc-theme-cb" class="hc-toggle-label" title="Toggle between dark and light mode">
        <i class="fas fa-moon"></i>
        <i class="fas fa-sun"></i>
        <span class="hc-toggle-ball"></span>
      </label>
    </div>
    <div class="topbar-btns">
      <button class="hbtn g" onclick="api('start_all',{})" title="Start every stream">▶ All</button>
      <button class="hbtn r" onclick="api('stop_all',{})" title="Stop every stream">■ All</button>
    </div>
  </div>
</header>

<!-- ══ STREAMS TAB ══ -->
<div id="tab-streams" class="tab-panel active">
  <div class="section-hdr">
    <h2>Live Streams</h2>
    <span class="sep"></span>
    <label style="font-size:11px;color:var(--text3);display:flex;align-items:center;gap:6px;cursor:pointer" title="Automatically refresh stream status every 2.5 seconds">
      <input type="checkbox" id="auto-ref" checked onchange="toggleAuto(this.checked)" style="width:auto">
      Auto-refresh
    </label>
    <button class="btn b" onclick="loadStreams()" title="Refresh stream list now">↻ Refresh</button>
    <button class="btn" onclick="downloadUrlsCsv()" title="Download all stream URLs as a CSV file">⬇ URLs CSV</button>
    <label style="font-size:11px;color:var(--text3);display:flex;align-items:center;gap:5px;cursor:pointer" title="Include playlist filenames in the exported CSV">
      <input type="checkbox" id="csv-files" style="width:auto;accent-color:var(--accent)"> + filenames
    </label>
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
            <th>Stream URLs</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="stbl">
          <tr><td colspan="10" class="empty"><div class="empty"><div class="empty-icon">📡</div>Loading streams…</div></td></tr>
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
    <button class="btn b" onclick="loadViewer()" title="Reload stream viewer cards">↻ Refresh</button>
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
    <select id="log-stream" style="width:160px" onchange="loadLogs()" title="Filter logs by a specific stream">
      <option value="">All streams</option>
    </select>
    <select id="log-level" style="width:110px" onchange="loadLogs()" title="Filter logs by severity level">
      <option value="ALL">ALL</option>
      <option value="INFO">INFO</option>
      <option value="WARN">WARN</option>
      <option value="ERROR">ERROR</option>
    </select>
    <button class="btn b" onclick="loadLogs()" title="Refresh log entries now">↻</button>
    <label style="font-size:11px;color:var(--text3);display:flex;align-items:center;gap:6px;cursor:pointer" title="Automatically scroll to the newest log entry">
      <input type="checkbox" id="log-auto" checked style="width:auto"> Auto-scroll
    </label>
  </div>
  <div id="logbox"></div>
</div>

<!-- ══ UPLOAD TAB ══ -->
<!-- ══ MEDIA TAB (Upload + File Manager merged) ══ -->
<div id="tab-media" class="tab-panel">

  <!-- Top bar: upload strip -->
  <div class="section-hdr">
    <h2>Media Library</h2><span class="sep"></span>
    <button class="btn b" onclick="loadFiles(_fmCurrentPath)" title="Refresh the current folder listing">↻ Refresh</button>
    <button class="btn g" onclick="fmNewFolder()" title="Create a new folder in the current directory">＋ New Folder</button>
  </div>

  <!-- Upload drop zone (collapsed bar at top) -->
  <div class="card" style="padding:0;overflow:visible">
    <div style="padding:12px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;border-bottom:1px solid var(--border);background:var(--bg3);border-radius:var(--radius-lg) var(--radius-lg) 0 0">
      <div style="font-size:13px;font-weight:600;color:var(--text2);display:flex;align-items:center;gap:8px">
        <span style="font-size:16px">⬆</span> Upload to:
      </div>
      <div class="fg" style="min-width:180px;max-width:240px;margin:0">
        <select id="upload-subdir" style="margin:0"></select>
      </div>
      <button class="btn" onclick="mkSubdir()" title="Create a new subfolder inside the selected upload directory">＋ Subfolder</button>
      <button class="btn g" onclick="document.getElementById('fpick').click()" style="margin-left:auto" title="Browse your device and upload media files">
        Browse &amp; Upload…
      </button>
      <div id="dropzone-mini"
           style="display:flex;align-items:center;gap:8px;padding:7px 14px;border:2px dashed var(--border);border-radius:var(--radius);cursor:pointer;color:var(--text3);font-size:12px;transition:all 0.2s"
           title="Click or drag-and-drop files here to upload them to the selected folder"
           onclick="document.getElementById('fpick').click()"
           ondragover="event.preventDefault();this.style.borderColor='var(--accent)'"
           ondragleave="this.style.borderColor='var(--border)'"
           ondrop="event.preventDefault();this.style.borderColor='var(--border)';doUpload(event.dataTransfer.files)">
        Drop files here
      </div>
      <input type="file" id="fpick" multiple accept="video/*,audio/*" style="display:none" onchange="doUpload(this.files)">
    </div>
    <!-- Upload progress list -->
    <div id="uplist-wrap" style="display:none;padding:10px 16px;border-bottom:1px solid var(--border)">
      <ul id="uplist" style="list-style:none;display:flex;flex-direction:column;gap:6px;margin:0;padding:0"></ul>
    </div>

    <!-- File Manager layout -->
    <div style="display:grid;grid-template-columns:210px 1fr;min-height:520px">

      <!-- Sidebar -->
      <div style="border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden">
        <div style="padding:10px 14px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--text3);background:var(--bg3);border-bottom:1px solid var(--border);font-family:var(--font-display)">Folders</div>
        <div class="fm-dir-list" id="fm-dir-list" style="flex:1;overflow-y:auto">
          <div class="fm-dir-item active" onclick="loadFiles('')">
            <span class="fm-dir-icon">📁</span> <span id="fm-root-label">Files</span>
          </div>
        </div>
      </div>

      <!-- Main file list -->
      <div style="display:flex;flex-direction:column;overflow:hidden">
        <!-- Breadcrumb + toolbar -->
        <div style="padding:9px 14px;background:var(--bg3);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <div class="fm-breadcrumb" id="fm-breadcrumb" style="flex:1;min-width:0">
            <span onclick="loadFiles('')" id="fm-breadcrumb-root">Files</span>
          </div>
        </div>
        <!-- File rows -->
        <div class="fm-body" id="fm-body" style="flex:1;overflow-y:auto">
          <div class="fm-empty">
            <div class="empty-icon">📂</div>
            <div>Open the Media tab to browse files.</div>
          </div>
        </div>
        <!-- Status bar -->
        <div class="fm-status-bar" id="fm-status">Ready</div>
      </div>

    </div>
  </div>

</div>

<!-- FM dialogs (shared, outside tab panel) -->
<div class="fm-dialog-overlay" id="fm-rename-overlay">
  <div class="fm-dialog">
    <h4>✏ Rename</h4>
    <div class="fg">
      <label>New name</label>
      <input type="text" id="fm-rename-input" placeholder="new name"
             onkeydown="if(event.key==='Enter')fmDoRename()">
    </div>
    <div class="fm-dialog-footer">
      <button class="btn" onclick="fmCloseDialogs()" title="Close without renaming">Cancel</button>
      <button class="btn g" onclick="fmDoRename()" title="Apply the new name">Rename</button>
    </div>
  </div>
</div>

<div class="fm-dialog-overlay" id="fm-move-overlay">
  <div class="fm-dialog">
    <h4>↗ Move to folder</h4>
    <div class="fg" style="margin-bottom:10px">
      <label>Destination folder</label>
      <select id="fm-move-dest" style="width:100%"><option value="">Media (top)</option></select>
    </div>
    <div class="fm-dialog-footer">
      <button class="btn" onclick="fmCloseDialogs()" title="Close without moving">Cancel</button>
      <button class="btn y" onclick="fmDoMove()" title="Move the file or folder to the selected destination">Move</button>
    </div>
  </div>
</div>

<div class="fm-dialog-overlay" id="fm-copy-overlay">
  <div class="fm-dialog">
    <h4>⎘ Copy to folder</h4>
    <div class="fg" style="margin-bottom:10px">
      <label>Destination folder</label>
      <select id="fm-copy-dest" style="width:100%"><option value="">Media (top)</option></select>
    </div>
    <div class="fg">
      <label>New filename <span style="color:var(--text3);font-weight:400">(optional)</span></label>
      <input type="text" id="fm-copy-name" placeholder="leave blank to keep same name">
    </div>
    <div class="fm-dialog-footer">
      <button class="btn" onclick="fmCloseDialogs()" title="Close without copying">Cancel</button>
      <button class="btn b" onclick="fmDoCopy()" title="Copy the file to the selected destination">Copy</button>
    </div>
  </div>
</div>

<!-- ══ EVENTS TAB ══ -->
<div id="tab-events" class="tab-panel">
  <div id="events-calendar-root"></div>
</div>

<!-- ══ CONFIGURE TAB ══ -->
<div id="tab-config" class="tab-panel">
  <div class="section-hdr">
    <h2>Stream Configuration</h2>
    <span class="sep"></span>
    <button class="btn b" onclick="_guardNav(loadConfig)" title="Reload stream configuration from disk">&#x21BB; Reload</button>
  </div>
  <div class="config-layout">
    <div class="config-sidebar">
      <div class="config-sidebar-hdr" style="display:flex;align-items:center;justify-content:space-between">
        <span>Streams</span>
        <button class="btn g" style="padding:2px 8px;font-size:10px;border-radius:5px" onclick="_guardNav(showNewStreamForm)" title="Add a new stream configuration">&#xFF0B; New</button>
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
        <button class="btn" onclick="cancelConfig()" title="Discard unsaved changes and go back">Cancel</button>
        <button class="btn g" onclick="saveConfig()" title="Save changes to this stream configuration">Save Changes</button>
      </div>
    </div>
  </div>
</div>

<!-- ══ SETTINGS TAB ══ -->
<div id="tab-settings" class="tab-panel">
  <div class="section-hdr">
    <h2>Application Settings</h2><span class="sep"></span>
    <button class="btn" onclick="resetAppSettings()"
      title="Reset ALL server-persisted settings (accent colour, branding, holiday country, notifications, system) back to factory defaults. UI-only toggles are not affected."
      style="color:var(--red);border-color:var(--red)">↺ Reset to Defaults</button>
  </div>
  <div id="settings-reset-status" style="font-size:11px;padding:0 2px 10px;display:none"></div>
  <!-- ── Server-persisted settings (appearance + notifications + system) ── -->
  <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--accent);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border)">Server Settings — saved across sessions</div>
  <div class="settings-grid">
    <!-- Accent Color -->
    <div class="setting-card">
      <h3>Accent Color</h3>
      <div style="font-size:12px;color:var(--text2);margin-bottom:14px;line-height:1.6">
        Customise the interface highlight colour used for buttons, borders, and focus rings.
      </div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">
        <input type="color" id="accent-color-picker" value="#b87333"
          style="width:44px;height:44px;padding:2px;border-radius:8px;border:1px solid var(--border);
                 background:var(--bg3);cursor:pointer;flex-shrink:0"
          oninput="accentPreview(this.value)"
          title="Pick your accent colour">
        <div style="flex:1;min-width:120px">
          <input id="accent-color-hex" value="#b87333" maxlength="7"
            style="font-family:var(--font-mono);font-size:13px;text-transform:uppercase;letter-spacing:0.06em"
            placeholder="#b87333"
            oninput="if(/^#[0-9a-fA-F]{6}$/.test(this.value)){document.getElementById('accent-color-picker').value=this.value;accentPreview(this.value);}"
            title="Enter a hex colour code">
        </div>
      </div>
      <!-- Preset swatches -->
      <div style="display:flex;flex-wrap:wrap;gap:7px;margin-bottom:14px">
        <button onclick="setAccentSwatch('#b87333')" title="Copper (default)"
          style="width:22px;height:22px;border-radius:5px;background:#b87333;border:2px solid transparent;cursor:pointer;padding:0;transition:transform 0.15s"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform=''"></button>
        <button onclick="setAccentSwatch('#4f8ef7')" title="Blue"
          style="width:22px;height:22px;border-radius:5px;background:#4f8ef7;border:2px solid transparent;cursor:pointer;padding:0;transition:transform 0.15s"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform=''"></button>
        <button onclick="setAccentSwatch('#7ac97a')" title="Green"
          style="width:22px;height:22px;border-radius:5px;background:#7ac97a;border:2px solid transparent;cursor:pointer;padding:0;transition:transform 0.15s"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform=''"></button>
        <button onclick="setAccentSwatch('#e05c6a')" title="Red"
          style="width:22px;height:22px;border-radius:5px;background:#e05c6a;border:2px solid transparent;cursor:pointer;padding:0;transition:transform 0.15s"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform=''"></button>
        <button onclick="setAccentSwatch('#c97fd4')" title="Purple"
          style="width:22px;height:22px;border-radius:5px;background:#c97fd4;border:2px solid transparent;cursor:pointer;padding:0;transition:transform 0.15s"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform=''"></button>
        <button onclick="setAccentSwatch('#e0a030')" title="Amber"
          style="width:22px;height:22px;border-radius:5px;background:#e0a030;border:2px solid transparent;cursor:pointer;padding:0;transition:transform 0.15s"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform=''"></button>
        <button onclick="setAccentSwatch('#4fc0c0')" title="Teal"
          style="width:22px;height:22px;border-radius:5px;background:#4fc0c0;border:2px solid transparent;cursor:pointer;padding:0;transition:transform 0.15s"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform=''"></button>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn g" onclick="saveAccentColor()" title="Save accent colour to server and persist across sessions">📁 Save</button>
        <button class="btn" onclick="setAccentSwatch('#b87333')" title="Reset to default copper colour">↺ Default</button>
        <div id="accent-status" style="font-size:11px;color:var(--text3)"></div>
      </div>
    </div>

    <!-- Branding -->
    <div class="setting-card">
      <h3>Branding</h3>
      <div style="font-size:12px;color:var(--text2);margin-bottom:14px;line-height:1.6">
        Customise the app name and logo shown in the topbar. Logo can be uploaded as an image file or entered as a URL.
      </div>

      <div class="fg" style="margin-bottom:12px">
        <label style="font-size:11px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:0.07em;display:block;margin-bottom:6px">App Name</label>
        <input id="brand-name" type="text" placeholder="HydraCast"
               style="width:100%;box-sizing:border-box"
               title="Custom name shown in the topbar. Leave blank to use the server default.">
      </div>

      <div class="fg" style="margin-bottom:12px">
        <label style="font-size:11px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:0.07em;display:block;margin-bottom:6px">Logo Image</label>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <div id="brand-logo-preview"
               style="width:40px;height:40px;border-radius:8px;background:var(--bg4);border:1px solid var(--border2);display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0">
            <span style="font-size:9px;color:var(--text3)">HC</span>
          </div>
          <div style="flex:1;min-width:0">
            <input id="brand-logo-url" type="text" placeholder="https://… or leave blank"
                   style="width:100%;box-sizing:border-box;margin-bottom:6px"
                   title="Direct URL to a logo image"
                   oninput="brandLogoUrlPreview(this.value)">
            <label class="btn" style="display:inline-flex;align-items:center;gap:5px;cursor:pointer;font-size:11px;padding:4px 10px">
              📁 Upload file
              <input id="brand-logo-file" type="file" accept="image/*"
                     style="display:none" onchange="brandLogoFileChosen(this)">
            </label>
            <button class="btn" style="font-size:11px;padding:4px 10px;margin-left:4px"
                    onclick="clearBrandLogo()" title="Remove custom logo and revert to initials">✕ Clear</button>
          </div>
        </div>
        <div id="brand-logo-size" style="font-size:10px;color:var(--text3)"></div>
      </div>

      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <button class="btn g" onclick="saveBrandingSettings()" title="Save branding to server">📁 Save</button>
        <div id="brand-status" style="font-size:11px;color:var(--text3)"></div>
      </div>
    </div>
  </div>
  <!-- end server settings-grid -->

  <!-- ── UI-only settings (not persisted to server) ── -->
  <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--text3);margin:18px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)">Browser Settings — stored locally in this browser only</div>
  <div class="settings-grid">
    <!-- UI Preferences -->
    <div class="setting-card">
      <h3>UI Preferences</h3>
      <div class="setting-row">
        <div><div class="setting-label">Auto-refresh streams</div><div class="setting-desc">Poll for stream status updates</div></div>
        <div class="toggle on" id="st-autoref" onclick="toggleSetting('autoref',this)" title="Automatically poll stream status at the configured interval"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Auto-scroll logs</div><div class="setting-desc">Jump to newest log entry</div></div>
        <div class="toggle on" id="st-autoscroll" onclick="toggleSetting('autoscroll',this)" title="Automatically scroll the log view to the newest entry"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Compact stream table</div><div class="setting-desc">Reduce row padding</div></div>
        <div class="toggle" id="st-compact" onclick="toggleSetting('compact',this)" title="Use smaller row padding to fit more streams on screen"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Show RTSP chip</div><div class="setting-desc">Display URL in stream table</div></div>
        <div class="toggle on" id="st-showrtsp" onclick="toggleSetting('showrtsp',this)" title="Show the RTSP URL column in the Streams table"></div>
      </div>
    </div>

    <!-- Notifications (browser-only) -->
    <div class="setting-card">
      <h3>Browser Notifications</h3>
      <div class="setting-row">
        <div><div class="setting-label">Toast on stream start</div><div class="setting-desc">Show notification when stream goes LIVE</div></div>
        <div class="toggle on" id="st-notif-start" onclick="toggleSetting('notifStart',this)" title="Show a toast notification when a stream goes LIVE"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Toast on stream error</div><div class="setting-desc">Alert when ERROR status detected</div></div>
        <div class="toggle on" id="st-notif-err" onclick="toggleSetting('notifErr',this)" title="Show a toast notification when a stream enters an ERROR state"></div>
      </div>
      <div class="setting-row">
        <div><div class="setting-label">Event countdown alerts</div><div class="setting-desc">Warn 1 min before scheduled event</div></div>
        <div class="toggle" id="st-notif-event" onclick="toggleSetting('notifEvent',this)" title="Show a warning notification 1 minute before a scheduled event fires"></div>
      </div>
    </div>

    <!-- Refresh Intervals -->
    <div class="setting-card">
      <h3>Refresh Intervals</h3>
      <div class="setting-row">
        <div class="setting-label">Stream poll interval</div>
        <select id="st-poll-interval" onchange="applyPollInterval()" style="width:100px" title="How often to poll the server for stream status updates">
          <option value="1500">1.5 s</option>
          <option value="2500" selected>2.5 s</option>
          <option value="5000">5 s</option>
          <option value="10000">10 s</option>
        </select>
      </div>
      <div class="setting-row">
        <div class="setting-label">System stats interval</div>
        <select id="st-stats-interval" onchange="applyStatsInterval()" style="width:100px" title="How often to refresh CPU and RAM stats in the header">
          <option value="5000">5 s</option>
          <option value="8000" selected>8 s</option>
          <option value="15000">15 s</option>
        </select>
      </div>
      <div class="setting-row">
        <div class="setting-label">Log auto-refresh</div>
        <select id="st-log-interval" onchange="applyLogInterval()" style="width:100px" title="How often to reload the log view when it is open">
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
        <button class="btn b" onclick="updateSysInfo()" style="width:100%;justify-content:center" title="Refresh CPU, RAM and active stream count">↻ Refresh Info</button>
      </div>
    </div>
  </div>
  <!-- end browser settings-grid -->

  <div style="margin-top:4px">
    <div class="section-hdr"><h2>Holidays</h2><span class="sep"></span>
      <button class="btn b" onclick="loadHolidaySettings();loadCustomHolidays();" title="Reload holiday settings from server">↻ Load</button>
    </div>
    <div class="card card-body" style="padding:16px">
      <!-- ── Public Holiday Country ── -->
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--accent);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">Public Holiday Country</div>
      <div style="font-size:12px;color:var(--text2);margin-bottom:12px;line-height:1.7">
        Sets the country used to show public holidays in the Events calendar.
        Use the two-letter ISO country code (e.g. <code style="color:var(--accent-light)">US</code>, <code style="color:var(--accent-light)">BD</code>, <code style="color:var(--accent-light)">GB</code>, <code style="color:var(--accent-light)">AU</code>).
        Requires the <code style="color:var(--accent-light)">holidays</code> Python package.
      </div>
      <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));margin-bottom:12px">
        <div class="fg">
          <label>Country</label>
          <select id="hol-country" title="Select the country for public holiday display in the Events calendar">
            <option value="AE">AE — UAE</option>
            <option value="AR">AR — Argentina</option>
            <option value="AT">AT — Austria</option>
            <option value="AU">AU — Australia</option>
            <option value="BD">BD — Bangladesh</option>
            <option value="BE">BE — Belgium</option>
            <option value="BR">BR — Brazil</option>
            <option value="CA">CA — Canada</option>
            <option value="CH">CH — Switzerland</option>
            <option value="CN">CN — China</option>
            <option value="CO">CO — Colombia</option>
            <option value="CZ">CZ — Czech Republic</option>
            <option value="DE">DE — Germany</option>
            <option value="DK">DK — Denmark</option>
            <option value="EG">EG — Egypt</option>
            <option value="ES">ES — Spain</option>
            <option value="FI">FI — Finland</option>
            <option value="FR">FR — France</option>
            <option value="GB">GB — United Kingdom</option>
            <option value="GH">GH — Ghana</option>
            <option value="GR">GR — Greece</option>
            <option value="HU">HU — Hungary</option>
            <option value="ID">ID — Indonesia</option>
            <option value="IE">IE — Ireland</option>
            <option value="IL">IL — Israel</option>
            <option value="IN">IN — India</option>
            <option value="IQ">IQ — Iraq</option>
            <option value="IR">IR — Iran</option>
            <option value="IT">IT — Italy</option>
            <option value="JP">JP — Japan</option>
            <option value="KE">KE — Kenya</option>
            <option value="KR">KR — South Korea</option>
            <option value="KW">KW — Kuwait</option>
            <option value="LK">LK — Sri Lanka</option>
            <option value="MA">MA — Morocco</option>
            <option value="MX">MX — Mexico</option>
            <option value="MY">MY — Malaysia</option>
            <option value="NG">NG — Nigeria</option>
            <option value="NL">NL — Netherlands</option>
            <option value="NO">NO — Norway</option>
            <option value="NP">NP — Nepal</option>
            <option value="NZ">NZ — New Zealand</option>
            <option value="OM">OM — Oman</option>
            <option value="PH">PH — Philippines</option>
            <option value="PK">PK — Pakistan</option>
            <option value="PL">PL — Poland</option>
            <option value="PT">PT — Portugal</option>
            <option value="QA">QA — Qatar</option>
            <option value="RO">RO — Romania</option>
            <option value="RU">RU — Russia</option>
            <option value="SA">SA — Saudi Arabia</option>
            <option value="SE">SE — Sweden</option>
            <option value="SG">SG — Singapore</option>
            <option value="TH">TH — Thailand</option>
            <option value="TN">TN — Tunisia</option>
            <option value="TR">TR — Turkey</option>
            <option value="TZ">TZ — Tanzania</option>
            <option value="UA">UA — Ukraine</option>
            <option value="UG">UG — Uganda</option>
            <option value="US" selected>US — United States</option>
            <option value="VN">VN — Vietnam</option>
            <option value="ZA">ZA — South Africa</option>
            <option value="ZW">ZW — Zimbabwe</option>
          </select>
        </div>
        <div class="fg">
          <label>State / Province <span style="font-weight:400;color:var(--text3)">optional</span></label>
          <input id="hol-subdiv" placeholder="e.g. CA, NSW, ON…"
            title="Optional subdivision code for regional holidays. Leave blank for national-only.">
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:20px">
        <button class="btn g" onclick="saveHolidaySettings()" title="Save holiday country to disk">📁 Save</button>
        <div id="hol-status" style="font-size:11px;color:var(--text3)"></div>
      </div>

      <!-- ── Custom Holidays ── -->
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--accent);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">Custom Holidays</div>
      <div style="font-size:12px;color:var(--text2);margin-bottom:12px;line-height:1.7">
        Add your own holidays to overlay on the Events calendar alongside public holidays.
        Custom holidays are stored locally and are never overwritten by library updates.
      </div>
      <!-- Table of existing custom holidays -->
      <div style="overflow-x:auto;border:1px solid var(--border);border-radius:6px;margin-bottom:14px">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:var(--bg3);font-size:11px;color:var(--text3);text-align:left">
              <th style="padding:6px 8px;font-weight:500">Date</th>
              <th style="padding:6px 8px;font-weight:500">Name</th>
              <th style="padding:6px 8px;font-weight:500">Country</th>
              <th style="padding:6px 8px;font-weight:500;text-align:right"></th>
            </tr>
          </thead>
          <tbody id="custom-hol-tbody">
            <tr><td colspan="4" style="padding:12px;text-align:center;color:var(--text3);font-size:12px">Click ↻ Load to fetch saved holidays.</td></tr>
          </tbody>
        </table>
      </div>
      <!-- Add form -->
      <div style="font-size:11px;color:var(--text3);margin-bottom:8px;font-weight:500">Add new custom holiday</div>
      <div class="form-grid" style="grid-template-columns:150px 1fr 100px;margin-bottom:10px;align-items:end">
        <div class="fg">
          <label>Date</label>
          <input id="chol-date" type="date" title="Date of the custom holiday">
        </div>
        <div class="fg">
          <label>Name</label>
          <input id="chol-name" placeholder="e.g. Company Founding Day" title="Display name for this holiday">
        </div>
        <div class="fg">
          <label>Country <span style="font-weight:400;color:var(--text3)">opt.</span></label>
          <input id="chol-country" placeholder="e.g. BD, US" maxlength="10" title="ISO country code (optional, defaults to CUSTOM)">
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <button class="btn g" onclick="addCustomHoliday()" title="Save this custom holiday to disk">＋ Add Holiday</button>
        <div id="chol-status" style="font-size:11px;color:var(--text3)"></div>
      </div>
    </div>
  </div>

  <!-- Mail Alerts -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2>Mail Alerts</h2><span class="sep"></span>
      <button class="btn b" onclick="loadMailConfig()" title="Load saved mail alert settings from disk">↻ Load</button>
    </div>
    <div class="card card-body" style="padding:16px">

      <!-- Info banner -->
      <div style="font-size:12px;color:var(--text2);margin-bottom:16px;line-height:1.8;background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:12px">
        Sends alerts via <b style="color:var(--accent-light)">Microsoft Graph API</b> (Outlook / Office 365).<br>
        Requires an <b>Azure App Registration</b> with <code style="color:var(--accent-light)">Mail.Send</code> (Application permission) and admin consent.<br>
        <a href="https://portal.azure.com" target="_blank" style="color:var(--blue)">portal.azure.com</a>
        → App registrations → New → Certificates &amp; secrets → API permissions → Microsoft Graph → Application → Mail.Send
      </div>

      <!-- Azure credentials -->
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--accent);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">Azure App Credentials</div>
      <div class="form-grid" style="grid-template-columns:1fr 1fr;margin-bottom:14px">
        <div class="fg">
          <label>Tenant ID <span style="color:var(--text3);font-weight:400">(Directory ID)</span></label>
          <input id="ml-tenant-id" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autocomplete="off"
            title="Azure Active Directory Tenant (Directory) ID">
        </div>
        <div class="fg">
          <label>Client ID <span style="color:var(--text3);font-weight:400">(Application ID)</span></label>
          <input id="ml-client-id" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autocomplete="off"
            title="Azure App Registration Application (Client) ID">
        </div>
        <div class="fg">
          <label>Client Secret</label>
          <input id="ml-client-secret" type="password" placeholder="••••••••" autocomplete="new-password"
            title="Client secret value from Certificates &amp; secrets">
        </div>
        <div class="fg">
          <label>From Address <span style="color:var(--text3);font-weight:400">(sender mailbox)</span></label>
          <input id="ml-from" placeholder="hydracast@yourdomain.com" autocomplete="off"
            title="The mailbox address the app will send from (must be in your tenant)">
        </div>
      </div>

      <!-- Recipients + options -->
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--accent);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">Recipients &amp; Options</div>
      <div class="form-grid" style="grid-template-columns:1fr auto;align-items:end;margin-bottom:12px">
        <div class="fg">
          <label>To Addresses <span style="color:var(--text3);font-weight:400">comma-separated</span></label>
          <input id="ml-to" placeholder="ops@example.com, alerts@example.com" title="One or more recipient addresses, comma-separated">
        </div>
        <div class="fg">
          <label>Cooldown <span style="color:var(--text3);font-weight:400">(seconds)</span></label>
          <input id="ml-cooldown" type="number" value="300" min="0" style="width:90px"
            title="Minimum seconds between repeated alerts for the same stream">
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
        <button class="btn g" onclick="saveMailConfig()" title="Save mail alert configuration to disk">📁 Save Config</button>
        <div class="fg" style="flex-direction:row;gap:6px;align-items:center;flex:1;min-width:200px">
          <input id="ml-test-to" placeholder="Test recipient (optional)" style="flex:1" title="Optional: override the To address just for this test email">
          <button class="btn b" onclick="testMailAlert()" title="Send a test email to verify your mail settings">✉ Send Test</button>
        </div>
      </div>
      <div id="ml-status" style="font-size:11px;color:var(--text3);margin-top:10px"></div>

    </div>
  </div>
  <!-- Media Root Directories -->
  <div style="margin-top:4px" id="media-roots-section">
    <div class="section-hdr">
      <h2>Media Root Directories</h2><span class="sep"></span>
      <button class="btn b" onclick="loadMediaRoots()" title="Reload root directories from server">↻ Load</button>
    </div>
    <div class="card card-body" style="padding:16px">
      <div style="font-size:12px;color:var(--text2);margin-bottom:14px;line-height:1.7">
        HydraCast scans these directories for media files shown in the
        <b>Library</b> and available to streams.
        The <b>default root</b> (<code id="mr-default-path" style="color:var(--accent-light)">media/</code>) is always active and cannot be removed.
        Extra roots must be absolute paths on the server.
      </div>

      <!-- Root list -->
      <div id="mr-list" style="display:flex;flex-direction:column;gap:6px;margin-bottom:14px"></div>

      <!-- Add new root row -->
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <input id="mr-new-path" type="text"
          placeholder="/absolute/path/to/extra/media"
          style="flex:1;min-width:160px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:7px 11px;border-radius:var(--radius);font-size:12px;font-family:var(--font-mono);outline:none;transition:border-color 0.2s"
          onfocus="this.style.borderColor='var(--accent)'"
          onblur="this.style.borderColor='var(--border)'"
          onkeydown="if(event.key==='Enter')addMediaRoot()"
          title="Absolute server-side path to add as a media root">
        <button class="btn g" onclick="addMediaRoot()" style="white-space:nowrap;flex-shrink:0" title="Add this directory as an extra media root">+ Add Root</button>
      </div>
      <div id="mr-status" style="font-size:11px;color:var(--text3);margin-top:8px"></div>
    </div>
  </div>

  <!-- Backup & Restore -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2>Backup &amp; Restore</h2><span class="sep"></span></div>
    <div class="card card-body" style="padding:16px">
      <div class="rg-2">

        <!-- Backup -->
        <div>
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--accent);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">Create Backup</div>
          <div style="font-size:12px;color:var(--text2);margin-bottom:12px;line-height:1.7">
            Downloads a single <code style="color:var(--accent-light)">.hc</code> file containing all your configuration:
            <ul style="margin:6px 0 0 16px;color:var(--text3);font-size:11px;line-height:1.9">
              <li>Stream definitions (streams.hcf)</li>
              <li>Scheduled events (events.hcf)</li>
              <li>Mail alert config (mail_config.hcf)</li>
              <li>Resume positions (resume_positions.hcf)</li>
              <li>App settings (holiday country, etc.)</li>
              <li>Media root directory list (media_roots.hcf)</li>
            </ul>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-streams" checked style="width:auto;accent-color:var(--accent)" title="Include stream definitions in the backup"> Streams
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-events" checked style="width:auto;accent-color:var(--accent)" title="Include scheduled events in the backup"> Events
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-mail" checked style="width:auto;accent-color:var(--accent)" title="Include mail alert configuration in the backup (password is excluded)"> Mail config
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-resume" checked style="width:auto;accent-color:var(--accent)" title="Include per-file resume positions in the backup"> Resume positions
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-app-settings" checked style="width:auto;accent-color:var(--accent)" title="Include app settings (holiday country, etc.) in the backup"> App settings
            </label>
            <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
              <input type="checkbox" id="bk-media-roots" checked style="width:auto;accent-color:var(--accent)" title="Include extra media root directory paths in the backup"> Media roots
            </label>
          </div>
          <button class="btn g" onclick="downloadBackup()" title="Download a .hc backup file containing the selected configuration">⬇ Download Backup</button>
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
            title="Click or drag-and-drop a .hc backup file to restore your configuration"
            onclick="document.getElementById('restore-file').click()"
            ondragover="event.preventDefault();this.style.borderColor='var(--accent)'"
            ondragleave="this.style.borderColor='var(--border)'"
            ondrop="event.preventDefault();this.style.borderColor='var(--border)';doRestore(event.dataTransfer.files[0])">
            <div style="font-size:24px;margin-bottom:6px;opacity:0.4">⬆</div>
            <div style="font-size:13px;font-weight:600;color:var(--text2)">Drop .hc file or click to browse</div>
          </div>
          <input type="file" id="restore-file" accept=".hc" style="display:none" onchange="doRestore(this.files[0])">
          <div id="restore-preview" style="display:none;margin-top:10px;padding:10px 12px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);font-size:11px;color:var(--text2);line-height:1.8"></div>
          <div id="restore-status" style="font-size:11px;color:var(--text3);margin-top:8px"></div>
        </div>

      </div>
    </div>
  </div>

  <!-- Service Restart -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2>⚡ Service Control</h2><span class="sep"></span></div>
    <div class="card card-body" style="padding:16px">
      <div style="display:flex;flex-wrap:wrap;align-items:stretch;gap:12px">
        <div style="flex:1;min-width:200px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:12px">
          <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:4px">↺ Restart Everything</div>
          <div style="font-size:11px;color:var(--text3);margin-bottom:8px;line-height:1.5">Stops all streams, then relaunches the entire application process (<code style="font-size:10px">os.execv</code>). Page reconnects automatically in ~5 s.</div>
          <button class="btn r" style="font-weight:600;width:100%" onclick="svcRestartAll()"
                  title="Stop all streams then restart the web server process (os.execv)">&#x26A1; Restart All Services</button>
        </div>
        <div style="flex:1;min-width:200px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:12px">
          <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:4px">↺ Streams Only</div>
          <div style="font-size:11px;color:var(--text3);margin-bottom:8px;line-height:1.5">Restarts every stream without touching the web UI process. Faster — no page reload needed.</div>
          <button class="btn b" style="width:100%" onclick="if(confirm('Restart ALL streams?')) api('restart_all',{})"
                  title="Stop and restart every stream">↺ Restart Streams</button>
        </div>
      </div>
      <div id="svc-restart-status" style="font-size:11px;color:var(--text3);margin-top:10px"></div>
    </div>
  </div>

  <!-- Danger Zone -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2 style="color:var(--red)">Danger Zone</h2><span class="sep"></span></div>
    <div class="card card-body" style="border-color:rgba(194,120,120,0.3);padding:16px;background:rgba(194,120,120,0.03)">
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start">
        <!-- Stop All -->
        <div style="flex:1;min-width:180px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:12px">
          <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:4px">■ Stop All Streams</div>
          <div style="font-size:11px;color:var(--text3);margin-bottom:8px;line-height:1.5">Immediately stop every running stream process.</div>
          <button class="btn r" onclick="if(confirm('Force-stop ALL streams?')) api('stop_all',{})"
            title="Immediately stop every running stream" style="width:100%">■ Stop All</button>
        </div>
        <!-- Clear Events -->
        <div style="flex:1;min-width:180px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:12px">
          <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:4px">🗑 Clear Played Events</div>
          <div style="font-size:11px;color:var(--text3);margin-bottom:8px;line-height:1.5">Delete all played events from schedule history permanently.</div>
          <button class="btn r" onclick="clearPlayedEvents()"
            title="Delete all played events from schedule history"
            style="background:rgba(194,120,120,0.1);border-color:var(--red);width:100%">🗑 Clear Events</button>
        </div>
        <!-- Factory Reset -->
        <div style="flex:1;min-width:220px;background:rgba(194,120,120,0.06);border:1.5px solid rgba(194,120,120,0.45);border-radius:var(--radius);padding:12px">
          <div style="font-size:12px;font-weight:700;color:var(--red);margin-bottom:4px;display:flex;align-items:center;gap:6px">
            <i class="ti ti-alert-triangle" style="font-size:14px"></i>Factory Reset
          </div>
          <div style="font-size:11px;color:var(--text3);margin-bottom:8px;line-height:1.5">
            Force-stops <em>all</em> streams → deletes <em>every</em> file &amp; folder in <code style="font-size:10px">config/</code> → restarts the server. <b style="color:var(--red)">Cannot be undone.</b>
          </div>
          <button class="btn r" id="factory-reset-btn" onclick="factoryReset()"
            title="Force-stop all streams · wipe entire config directory · restart server"
            style="background:rgba(194,120,120,0.22);border-color:var(--red);font-weight:700;width:100%">
            <i class="ti ti-alert-triangle" style="margin-right:4px"></i>⚠ Factory Reset
          </button>
        </div>
      </div>
      <div id="danger-status" style="font-size:11px;margin-top:10px"></div>
    </div>
  </div>
</div>

</div><!-- /app -->

<!-- ══ FOOTER ══ -->
<footer class="app-footer">
  <span id="ft-app-name" style="display:inline-flex;align-items:center;gap:6px;">
    <img id="ft-brand-logo"
         src="https://raw.githubusercontent.com/rhshourav/HydraCast/refs/heads/main/resources/HydraCast.svg"
         alt="HydraCast logo"
         style="width:16px;height:16px;flex-shrink:0;opacity:0.85;"
         onerror="this.style.display='none'">
    <span id="ft-brand-name">HydraCast</span>
  </span>
  <span class="footer-sep">·</span>
  <span id="ft-ver">—</span>
  <span class="footer-sep">·</span>
  <a href="https://github.com/rhshourav"
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
      <button class="btn" onclick="closeSeek()" title="Close without seeking">Cancel</button>
      <button class="btn g" onclick="doSeek()" title="Jump the stream to the specified position">⏩ Seek</button>
    </div>
  </div>
</div>

<!-- ══ UNSAVED CHANGES MODAL ══ -->
<!-- ══ MEDIA BROWSER MODAL ══ -->
<div class="modal-bg" id="mb-modal" onclick="if(event.target===this)mbClose()">
  <div class="modal" style="width:min(760px,96vw);max-width:none;padding:0;display:flex;flex-direction:column;max-height:88vh">

    <!-- Header -->
    <div style="padding:18px 22px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;flex-shrink:0">
      <span id="mb-mode-icon" style="font-size:20px">📁</span>
      <div style="flex:1;min-width:0">
        <h3 style="font-family:var(--font-display);font-size:16px;font-weight:700;margin-bottom:2px" id="mb-title">Browse Media</h3>
        <div id="mb-subtitle" style="font-size:11px;color:var(--text3)">Select a folder or file</div>
      </div>
      <button class="btn" onclick="mbClose()" title="Close browser" style="padding:5px 11px">✕</button>
    </div>

    <!-- Breadcrumb -->
    <div style="padding:8px 16px;background:var(--bg3);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:6px;flex-wrap:wrap;flex-shrink:0">
      <div id="mb-breadcrumb" style="display:flex;align-items:center;gap:3px;flex-wrap:wrap;flex:1;min-width:0;font-size:12px"></div>
      <button class="btn" onclick="mbRefresh()" title="Reload this folder" style="padding:3px 9px;font-size:11px;flex-shrink:0">↻</button>
    </div>

    <!-- Body: sidebar + file list -->
    <div style="display:grid;grid-template-columns:180px 1fr;flex:1;overflow:hidden;min-height:0">

      <!-- Sidebar: top-level folders -->
      <div style="border-right:1px solid var(--border);overflow-y:auto;background:var(--bg2)">
        <div style="padding:8px 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;color:var(--text3);background:var(--bg3);border-bottom:1px solid var(--border)">Folders</div>
        <div id="mb-sidebar"></div>
      </div>

      <!-- Main listing -->
      <div style="display:flex;flex-direction:column;overflow:hidden;background:var(--bg2)">
        <!-- Listing -->
        <div id="mb-listing" style="flex:1;overflow-y:auto"></div>
        <!-- Status bar -->
        <div id="mb-status-bar" style="padding:6px 14px;font-size:11px;color:var(--text3);border-top:1px solid var(--border);background:var(--bg3);flex-shrink:0"></div>
      </div>
    </div>

    <!-- Footer: current selection + action -->
    <div style="padding:12px 18px;border-top:1px solid var(--border);background:var(--bg3);display:flex;align-items:center;gap:10px;flex-shrink:0">
      <div style="flex:1;min-width:0">
        <div style="font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:0.07em;margin-bottom:3px">Selection</div>
        <div id="mb-selection-display" style="font-size:12px;font-family:var(--font-mono);color:var(--accent-light);overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
             title="">Nothing selected</div>
      </div>
      <button class="btn" onclick="mbClose()" style="white-space:nowrap">Cancel</button>
      <button class="btn g" id="mb-confirm-btn" onclick="mbConfirm()" style="white-space:nowrap" disabled>✓ Use Selection</button>
    </div>
  </div>
</div>

<div class="modal-bg" id="unsaved-modal">
  <div class="modal">
    <h3>&#x26A0;&#xFE0F; Unsaved Changes</h3>
    <div class="unsaved-modal-body">
      You have <strong>unsaved changes</strong> in the current configuration.<br>
      What would you like to do?
    </div>
    <div class="modal-footer">
      <button class="btn" onclick="handleUnsaved('cancel')" title="Go back and keep editing">Stay Here</button>
      <button class="btn r" onclick="handleUnsaved('discard')" title="Throw away unsaved edits and continue">Discard Changes</button>
      <button class="btn g" onclick="handleUnsaved('save')" title="Save your changes, then continue">Save &amp; Continue</button>
    </div>
  </div>
</div>

<!-- ══ PORT NOTIFICATION PANEL ══ -->
<div id="port-notif-panel" class="port-notif-panel">
  <div class="port-notif-hdr">
    <i class="ti ti-router" style="font-size:13px;color:var(--accent)"></i>
    <span class="port-notif-hdr-title">Port Analysis</span>
    <button class="port-notif-close" onclick="closePortNotif()" title="Dismiss">&#x2715;</button>
  </div>
  <div class="port-notif-body" id="port-notif-body"></div>
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
function fmtRemaining(secs){
  /* Convert raw seconds to compact human string: 1h 02m  /  45m 30s  /  58s */
  const s=Math.max(0,Math.round(+secs||0));
  const h=Math.floor(s/3600), m=Math.floor((s%3600)/60), ss=s%60;
  if(h>0) return h+'h '+String(m).padStart(2,'0')+'m';
  if(m>0) return m+'m '+String(ss).padStart(2,'0')+'s';
  return ss+'s';
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
  if(name!=='config'&&_configDirty){
    _guardNav(()=>_doSwitchTab(name,btn));
    return;
  }
  _doSwitchTab(name,btn);
}
function _doSwitchTab(name,btn){
  document.querySelectorAll('.tab-panel').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  if(name==='streams'){loadStreams();}
  else if(name==='logs'){fillLogStreamSel();loadLogs();}
  else if(name==='media'){loadSubdirs();loadFiles(_fmCurrentPath);}
  else if(name==='events'){if(!_hdLoaded)loadHolidays();}
  else if(name==='viewer'){loadViewer();}
  else if(name==='config'){loadConfig();}
  else if(name==='settings'){updateSysInfo();loadMailConfig();ssInit();loadHolidaySettings();loadCustomHolidays();loadMediaRoots();loadBrandingSettings();}
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
    // For stop/start actions give the backend time to settle before refreshing,
    // and pause auto-refresh for that window so the poller doesn't race.
    const settleMs = (action==='stop'||action==='stop_all') ? 1500
                   : (action==='start'||action==='start_all'||action==='restart'||action==='restart_all') ? 800
                   : 0;
    if(settleMs>0){
      const wasAuto=document.getElementById('auto-ref')?.checked;
      if(wasAuto) clearInterval(_autoTimer);
      await new Promise(res=>setTimeout(res,settleMs));
      loadStreams();
      if(_configSelected) loadConfig();
      if(wasAuto) _autoTimer=setInterval(loadStreams,parseInt(document.getElementById('st-poll-interval')?.value)||2500);
    } else {
      loadStreams();
      if(_configSelected) loadConfig();
    }
    return j;
  }catch(e){toast('Request failed','err');}
}

// ═══════════════════════════════════
// DOWNLOAD URLS CSV
// ═══════════════════════════════════
function downloadUrlsCsv(){
  const incFiles=document.getElementById('csv-files')?.checked?'1':'0';
  const a=document.createElement('a');
  a.href='/api/urls_csv?include_files='+incFiles;
  a.download='';           // filename comes from Content-Disposition
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  toast('Downloading URLs CSV\u2026','info');
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
let _statsTimer=null;
let _logTimer=null;

function toggleAuto(on){
  clearInterval(_autoTimer);
  if(on){
    const v=parseInt(document.getElementById('st-poll-interval')?.value)||2500;
    _autoTimer=setInterval(loadStreams,v);
  }
}

function applyStatsInterval(){
  const v=parseInt(document.getElementById('st-stats-interval')?.value)||8000;
  clearInterval(_statsTimer);
  _statsTimer=setInterval(updateStats,v);
  try{localStorage.setItem('hc-stats-interval',v);}catch(_){}
}

function applyLogInterval(){
  const v=parseInt(document.getElementById('st-log-interval')?.value)||4000;
  clearInterval(_logTimer);
  _logTimer=setInterval(()=>{
    if(document.getElementById('tab-logs')?.classList.contains('active')) loadLogs();
  },v);
  try{localStorage.setItem('hc-log-interval',v);}catch(_){}
}

async function loadStreams(){
  try{
    const data=await fetch('/api/streams').then(r=>r.json());
    data.sort((a,b)=>a.name.localeCompare(b.name));
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
      _updateComplianceAlerts(data);
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
         s.error_msg||'',
         s.playlist_count||0,
         s.enabled?1:0,
         s.shuffle?1:0,
         s.active_event||'',
         s.current_file||'',
         s.oneshot_active?1:0].join('|');
}

function _rowCells(s,i,showRtsp){
  const pct=Math.max(0,Math.min(100,+s.progress)).toFixed(1);
  const fc=s.progress>80?'var(--red)':s.progress>55?'var(--yellow)':'var(--green)';
  const status=s.status||'STOPPED';
  const isEvent = status==='ONESHOT' || !!s.oneshot_active;
  const nowPlayingFile = s.current_file || (isEvent ? s.active_event : null);
  return `
    <td class="td-muted">${i+1}</td>
    <td>
      <span class="td-name">${esc(s.name)}</span>
      ${s.shuffle?`<span class="tag-shuf">SHUF</span>`:''}
      ${!s.enabled?`<span class="tag-dis">OFF</span>`:''}
      ${isEvent?`<span style="font-size:10px;font-weight:700;color:var(--purple);background:var(--purple-dim);border:1px solid rgba(154,138,176,0.4);border-radius:4px;padding:2px 7px;margin-left:4px">🎬 EVENT</span>`:''}
      ${s.playlist_count>1?`<span style="font-size:10px;color:var(--text3);margin-left:4px">(${s.playlist_count} files)</span>`:''}
      ${nowPlayingFile?`
      <div style="margin-top:4px;display:flex;align-items:center;gap:5px;max-width:260px;overflow:hidden">
        <span style="font-size:9px;font-weight:700;flex-shrink:0;letter-spacing:0.04em;text-transform:uppercase;${isEvent?'color:var(--purple)':'color:var(--accent-light)'}">${isEvent?'EVENT':'PLAYLIST'}</span>
        <span style="font-size:10px;font-family:var(--font-mono);color:${isEvent?'var(--purple)':'var(--text2)'};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;background:${isEvent?'var(--purple-dim)':'var(--bg3)'};border:1px solid ${isEvent?'rgba(154,138,176,0.3)':'var(--border)'};border-radius:4px;padding:2px 7px"
              title="${esc(nowPlayingFile)}">${esc(nowPlayingFile)}</span>
      </div>`:''}
      ${s.next_in_queue&&s.next_in_queue.length?`
  <div style="margin-top:3px;display:flex;flex-direction:column;gap:1px">
    ${s.next_in_queue.map((name,qi)=>`
      <div style="font-size:10px;color:var(--text3);display:flex;align-items:center;gap:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px">
        <span style="color:var(--accent-light);font-family:var(--font-mono);font-weight:600;flex-shrink:0">+${qi+1}</span>
        <span style="overflow:hidden;text-overflow:ellipsis">${esc(name)}</span>
      </div>`).join('')}
  </div>`:''}
    </td>
    <td style="color:var(--accent-light)">:${s.port}</td>
    <td><span class="badge ${esc(status)}">${esc(status)}</span></td>
    <td style="min-width:140px">
      ${isEvent?`
        <div class="prog"><div class="prog-fill" style="width:${pct}%;background:var(--purple)"></div></div>
        <div class="prog-label" style="color:var(--purple)">🎬 ${pct}%${s.time_remaining?' · '+fmtRemaining(s.time_remaining)+' left':''}</div>
      `:`
        <div class="prog"><div class="prog-fill" style="width:${pct}%;background:${fc}"></div></div>
        <div class="prog-label">${pct}%${s.time_remaining?' · '+fmtRemaining(s.time_remaining)+' left':''}</div>
      `}
    </td>
    <td class="td-muted" style="white-space:nowrap">${esc(s.position||'--')}</td>
    <td class="td-muted">${s.fps>0?Math.round(s.fps)+'fps':'--'}</td>
    <td class="td-muted">${s.loop_count!=null&&s.loop_count!==undefined?'×'+s.loop_count:'--'}</td>
    <td>
      <div style="display:flex;flex-direction:column;gap:5px;min-width:220px">
        ${s.rtsp_url?`
          <div style="display:flex;align-items:center;gap:5px">
            <span style="font-size:10px;font-weight:700;color:var(--accent-light);font-family:var(--font-mono);white-space:nowrap">RTSP</span>
            <span style="flex:1;font-size:11px;font-family:var(--font-mono);color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;background:var(--bg3);border:1px solid var(--border);border-radius:5px;padding:3px 8px" title="${esc(s.rtsp_url)}">${esc(s.rtsp_url)}</span>
            <button class="btn" style="padding:3px 8px;font-size:11px;flex-shrink:0" onclick="copyText('${esc(s.rtsp_url)}')" title="Copy RTSP URL to clipboard">📋</button>
          </div>`:'<span class="td-muted">—</span>'}
        ${s.hls_url?`
          <div style="display:flex;align-items:center;gap:5px">
            <span style="font-size:10px;font-weight:700;color:var(--cyan);font-family:var(--font-mono);white-space:nowrap">HLS</span>
            <span style="flex:1;font-size:11px;font-family:var(--font-mono);color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;background:var(--bg3);border:1px solid var(--border);border-radius:5px;padding:3px 8px" title="${esc(s.hls_url)}">${esc(s.hls_url)}</span>
            <button class="btn" style="padding:3px 8px;font-size:11px;flex-shrink:0;color:var(--cyan)" onclick="copyText('${esc(s.hls_url)}')" title="Copy HLS URL to clipboard">📋</button>
          </div>`:``}
      </div>
    </td>
    <td>
      <div class="btn-group">
        <button class="btn g" onclick="api('start',{name:'${esc(s.name)}'})" title="Start this stream">▶</button>
        <button class="btn r" onclick="api('stop',{name:'${esc(s.name)}'})" title="Stop this stream">■</button>
        <button class="btn" onclick="api('restart',{name:'${esc(s.name)}'})" title="Restart this stream">↺</button>
        ${s.playlist_count>1?`<button class="btn" onclick="api('skip_next',{name:'${esc(s.name)}'})" title="Skip to the next file in the playlist">⏭</button>`:''}
        ${s.status==='LIVE'?`<button class="btn b" onclick="openSeek('${esc(s.name)}',${s.duration||0},${s.current_secs||0})" title="Jump to a specific position in the current file">⏩</button>`:''}
        ${isEvent?`<button class="btn" style="background:var(--purple-dim);color:var(--purple);border:1px solid rgba(154,138,176,0.5);font-size:11px" onclick="cancelEvent('${esc(s.name)}')" title="Stop the running event and resume compliance/playlist immediately">✕ Cancel Event</button>`:''}
      </div>
      ${s.error_msg?`<div style="font-size:10px;color:var(--red);margin-top:4px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(s.error_msg)}">⚠ ${esc(s.error_msg)}</div>`:''}
    </td>`;
}

function renderStreams(data){
  const tb=document.getElementById('stbl');
  const showRtsp=document.getElementById('st-showrtsp')?.classList.contains('on')!==false;

  if(!data.length){
    tb.innerHTML=`<tr><td colspan="10"><div class="empty"><div class="empty-icon">📡</div>No streams configured.</div></td></tr>`;
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
  if(navigator.clipboard&&window.isSecureContext){
    navigator.clipboard.writeText(url)
      .then(()=>toast('Copied!','ok'))
      .catch(()=>_copyFallback(url));
  } else {
    _copyFallback(url);
  }
}
function _copyFallback(url){
  /* Works on HTTP (non-secure) pages where clipboard API is blocked */
  const ta=document.createElement('textarea');
  ta.value=url;
  ta.style.cssText='position:fixed;top:-9999px;left:-9999px;opacity:0';
  document.body.appendChild(ta);
  ta.focus();ta.select();
  try{
    document.execCommand('copy');
    toast('Copied!','ok');
  }catch(_){
    toast('Copy failed — select manually','err');
  }
  document.body.removeChild(ta);
}

// ═══════════════════════════════════
// SEEK MODAL
// ═══════════════════════════════════
let _seekName='';
function cancelEvent(name){
  if(!confirm('Cancel the running event on "'+name+'" and resume compliance/playlist immediately?'))return;
  api('cancel_event',{name});
}

function openSeek(name,dur,cur){
  _seekName=name;
  document.getElementById('seek-info').innerHTML=
    `Stream: <b style="color:var(--text)">${esc(name)}</b> &nbsp;·&nbsp; Duration: <b>${fmtSecs(dur)}</b> &nbsp;·&nbsp; Current: <b>${fmtSecs(cur)}</b>`;
  document.getElementById('seek-val').value=fmtSecs(cur);
  const slider=document.getElementById('seek-slider');
  const _seekMax=Math.max(0,(dur||100)-1);
  slider.max=_seekMax;slider.value=Math.min(cur||0,_seekMax);
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
  const _durEl=document.getElementById('seek-slider');
  const _maxSecs=Math.max(0,(+_durEl.max||0));
  if(_maxSecs>0 && s>_maxSecs){
    toast('Seek position exceeds file duration — capped to '+fmtSecs(_maxSecs),'warn');
    s=_maxSecs;
  }
  api('seek',{name:_seekName,seconds:s});
  closeSeek();
}

// ═══════════════════════════════════
// VIEWER TAB
// ═══════════════════════════════════
async function loadViewer(){
  const grid=document.getElementById('viewer-grid');
  let data;
  try{
    data=await fetch('/api/streams').then(r=>r.json());
    data.sort((a,b)=>a.name.localeCompare(b.name));
  }catch(_){
    if(!grid.querySelector('.stream-card'))
      grid.innerHTML=`<div class="empty"><div class="empty-icon">⚠</div>Failed to load streams.</div>`;
    return;
  }
  if(!data.length){
    grid.innerHTML=`<div class="empty"><div class="empty-icon">📺</div>No streams available.</div>`;
    return;
  }

  // Build map of existing cards so we don't rebuild playing video elements
  const existing={};
  grid.querySelectorAll('.stream-card[data-vname]').forEach(c=>existing[c.dataset.vname]=c);

  // Clear any placeholder/empty message if cards are about to be added
  if(!Object.keys(existing).length) grid.innerHTML='';

  // Remove cards for streams that no longer exist
  const names=new Set(data.map(s=>s.name));
  Object.keys(existing).forEach(n=>{ if(!names.has(n)){existing[n].remove();delete existing[n];} });

  data.forEach((s,idx)=>{
    const status=s.status||'STOPPED';
    const isLive=status==='LIVE';
    const isEvent=status==='ONESHOT' || !!s.oneshot_active;
    const pct=(+s.progress||0).toFixed(1);
    const nowFile = s.current_file || (isEvent ? s.active_event : null);
    // safeName must be computed ONCE here and used in BOTH the first-render
    // innerHTML template and the update-path querySelector calls.
    // Previously the first render used esc(s.name) (HTML-encode only) while
    // the update path used s.name.replace(/[^a-zA-Z0-9_-]/g,'') (strip).
    // Those two transforms produce different strings for any name containing
    // special chars (spaces, dots, ampersands, etc.), so every querySelector
    // returned null and the progress bar / position never updated after the
    // card was first created.
    const safeName=s.name.replace(/[^a-zA-Z0-9_-]/g,'');

    if(!existing[s.name]){
      // ── First render: create the full card ──
      const div=document.createElement('div');
      div.className='stream-card'+(isLive||isEvent?' is-live':'');
      div.dataset.vname=s.name;
      div.innerHTML=`
        <div class="stream-card-header">
          <span class="badge vc-badge-${safeName}">${esc(status)}</span>
          <span class="stream-card-title">${esc(s.name)}</span>
          <span style="font-size:11px;color:var(--accent-light)">:${s.port}</span>
        </div>
        ${nowFile?`<div class="vc-nowplaying-${safeName}" style="padding:5px 14px 0;display:flex;align-items:center;gap:5px;min-width:0;overflow:hidden">
          <span style="font-size:9px;font-weight:700;flex-shrink:0;letter-spacing:0.04em;text-transform:uppercase;${isEvent?'color:var(--purple)':'color:var(--accent-light)'}">${isEvent?'EVENT':'PLAYLIST'}</span>
          <span style="font-size:10px;font-family:var(--font-mono);color:${isEvent?'var(--purple)':'var(--text2)'};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;background:${isEvent?'var(--purple-dim)':'var(--bg3)'};border:1px solid ${isEvent?'rgba(154,138,176,0.3)':'var(--border)'};border-radius:4px;padding:2px 8px"
                title="${esc(nowFile)}">${esc(nowFile)}</span>
        </div>`:`<div class="vc-nowplaying-${safeName}" style="padding:5px 14px 0;height:22px"></div>`}
        <div class="stream-preview" id="vp-${esc(s.name)}">
          <div class="stream-overlay" id="vo-${esc(s.name)}">
            ${isLive||isEvent?`
              <div class="stream-play-btn" onclick="loadHLSStream('${esc(s.name)}','${esc(s.hls_url||'')}','${esc(s.rtsp_url||'')}')" title="Click to load stream">▶</div>
              <div style="font-size:10px;color:var(--text3)">Click to preview</div>
            `:`<div style="font-size:12px;color:var(--text3)">Stream offline</div>`}
          </div>
        </div>
        <div class="stream-card-footer">
          <div class="stream-stats">
            <div class="stat-item">FPS <b class="vc-fps-${safeName}">${s.fps>0?Math.round(s.fps)+'fps':'—'}</b></div>
            <div class="stat-item">Pos <b class="vc-pos-${safeName}">${esc(s.position||'—')}</b></div>
            <div class="stat-item"><b class="vc-pct-${safeName}">${pct}%</b></div>
          </div>
          <div class="btn-group">
            <button class="btn b vc-copy-${safeName}" style="font-size:10px;padding:3px 8px" data-hls="${esc(s.hls_url||'')}" data-rtsp="${esc(s.rtsp_url||'')}" onclick="copyText(this.dataset.hls||this.dataset.rtsp)" title="Copy stream URL to clipboard">📋</button>
            ${isEvent?`<button class="btn" style="background:var(--purple-dim);color:var(--purple);border:1px solid rgba(154,138,176,0.5);font-size:10px;padding:3px 8px" onclick="cancelEvent('${esc(s.name)}')" title="Stop running event, resume compliance/playlist">✕ Event</button>`:''}
          </div>
        </div>
        <div style="padding:0 14px 10px">
          <div class="prog vc-prog-${safeName}" style="height:5px;border-radius:3px">
            <div class="prog-fill vc-progfill-${safeName}" style="width:${pct}%;background:${isEvent?'var(--purple)':+pct>80?'var(--red)':+pct>55?'var(--yellow)':'var(--green)'}"></div>
          </div>
        </div>`;
      // Insert in correct order
      const all=[...grid.querySelectorAll('.stream-card[data-vname]')];
      if(idx>=all.length) grid.appendChild(div);
      else grid.insertBefore(div,all[idx]);
      existing[s.name]=div;
    } else {
      // ── Subsequent renders: only update text/status, leave preview untouched ──
      const card=existing[s.name];
      card.className='stream-card'+(isLive||isEvent?' is-live':'');
      // safeName already computed above — same value used for first-render classes.
      const badge=card.querySelector('.vc-badge-'+safeName);
      if(badge){badge.className='badge '+esc(status);badge.textContent=status;}
      const pctEl=card.querySelector('.vc-pct-'+safeName);
      if(pctEl)pctEl.textContent=pct+'%';
      const fpsEl=card.querySelector('.vc-fps-'+safeName);
      if(fpsEl)fpsEl.textContent=s.fps>0?Math.round(s.fps)+'fps':'—';
      const posEl=card.querySelector('.vc-pos-'+safeName);
      if(posEl)posEl.textContent=s.position||'—';
      const pfill=card.querySelector('.vc-progfill-'+safeName);
      if(pfill){pfill.style.width=pct+'%';pfill.style.background=isEvent?'var(--purple)':+pct>80?'var(--red)':+pct>55?'var(--yellow)':'var(--green)';}
      const copyBtn=card.querySelector('.vc-copy-'+safeName);
      if(copyBtn){if(s.hls_url)copyBtn.dataset.hls=s.hls_url;if(s.rtsp_url)copyBtn.dataset.rtsp=s.rtsp_url;}
      // Update now-playing chip
      const npEl=card.querySelector('.vc-nowplaying-'+safeName);
      if(npEl){
        if(nowFile){
          npEl.style.cssText='padding:5px 14px 0;display:flex;align-items:center;gap:5px;min-width:0;overflow:hidden';
          npEl.innerHTML=`<span style="font-size:9px;font-weight:700;flex-shrink:0;letter-spacing:0.04em;text-transform:uppercase;${isEvent?'color:var(--purple)':'color:var(--accent-light)'}">${isEvent?'EVENT':'PLAYLIST'}</span>
            <span style="font-size:10px;font-family:var(--font-mono);color:${isEvent?'var(--purple)':'var(--text2)'};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;background:${isEvent?'var(--purple-dim)':'var(--bg3)'};border:1px solid ${isEvent?'rgba(154,138,176,0.3)':'var(--border)'};border-radius:4px;padding:2px 8px"
                  title="${esc(nowFile)}">${esc(nowFile)}</span>`;
        } else {
          npEl.innerHTML='';
        }
      }
      // Update offline overlay only if preview has no video playing
      const preview=document.getElementById('vp-'+s.name);
      const overlay=document.getElementById('vo-'+s.name);
      if(overlay&&!preview?.querySelector('video')){
        overlay.innerHTML=isLive||isEvent?`
          <div class="stream-play-btn" onclick="loadHLSStream('${esc(s.name)}','${esc(s.hls_url||'')}','${esc(s.rtsp_url||'')}')" title="Click to load stream">▶</div>
          <div style="font-size:10px;color:var(--text3)">Click to preview</div>
        `:`<div style="font-size:12px;color:var(--text3)">Stream offline</div>`;
      }
    }
  });
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
    data.sort((a,b)=>a.name.localeCompare(b.name));
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
    const dirs=data.dirs||[];
    // API now returns [{path:"@N/rel", label:"..."}] objects;
    // fall back to plain strings for backwards compatibility.
    sel.innerHTML='<option value="">/ (root)</option>'+
      dirs.filter(Boolean).map(d=>{
        const p=typeof d==='object'?d.path:d;
        const l=typeof d==='object'?d.label:d;
        return `<option value="${esc(p)}">${esc(l)}</option>`;
      }).join('');
  }catch(_){}
}
async function mkSubdir(){
  const n=prompt('New folder name:');
  if(!n||!n.trim())return;
  // Send the @N/rel encoded current path + the new folder name.
  // The server will decode the root and create the subfolder inside it.
  const parentEncoded = _fmCurrentPath || '';
  const newFolderName = n.trim().replace(/[/\\<>"|?*\x00]/g,'_');
  const fullEncoded = parentEncoded ? parentEncoded + '/' + newFolderName : newFolderName;
  const r=await api('create_subdir',{name:fullEncoded});
  if(r&&r.ok){loadSubdirs();loadFiles(_fmCurrentPath);}
}

const dz=document.getElementById('dropzone-mini');
if(dz){
  dz.addEventListener('dragover',e=>{e.preventDefault();dz.style.borderColor='var(--accent)'});
  dz.addEventListener('dragleave',()=>dz.style.borderColor='var(--border)');
  dz.addEventListener('drop',e=>{e.preventDefault();dz.style.borderColor='var(--border)';doUpload(e.dataTransfer.files)});
}

function doUpload(files){
  const wrap=document.getElementById('uplist-wrap');
  if(wrap)wrap.style.display='';
  Array.from(files).forEach(upOne);
}

// Number of simultaneous chunk fetches per file
const UP_PARALLEL = 4;

async function upOne(file){
  if(file.size>10*1024*1024*1024){toast(file.name+': exceeds 10 GB','err');return;}

  // ── Progress row ──────────────────────────────────────────────────────────
  const id='u'+Math.random().toString(36).slice(2,7);
  const li=document.createElement('li');
  li.id='li-'+id;
  li.style.cssText='display:flex;align-items:center;gap:10px;font-size:12px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px';
  li.innerHTML=`
    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;color:var(--text2)">${esc(file.name)}</span>
    <span class="td-muted">${fmtBytes(file.size)}</span>
    <div class="ubar"><div class="ufill" id="uf-${id}" style="width:0"></div></div>
    <span id="up-${id}" style="min-width:36px;text-align:right;color:var(--text3);font-size:11px">0%</span>`;
  document.getElementById('uplist').appendChild(li);

  function setPct(pct,color){
    const b=document.getElementById('uf-'+id),t=document.getElementById('up-'+id);
    if(b){b.style.width=pct+'%';if(color)b.style.background=color;}
    if(t)t.textContent=pct+'%';
  }
  function setLabel(text,color){
    const t=document.getElementById('up-'+id);
    if(t){t.textContent=text;if(color)t.style.color=color;}
  }
  function markErr(msg){
    const b=document.getElementById('uf-'+id);
    if(b)b.style.background='var(--red)';
    setLabel('✕','var(--red)');
    toast('Failed: '+msg,'err');
  }

  const subdir=document.getElementById('upload-subdir').value;

  // ── 1. Init ───────────────────────────────────────────────────────────────
  let session_id, chunkSize, totalChunks;
  try{
    const CLIENT_CHUNK=4*1024*1024;
    const estChunks=Math.max(1,Math.ceil(file.size/CLIENT_CHUNK));
    const r=await fetch('/api/upload/init',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({filename:file.name,size:file.size,total_chunks:estChunks,subdir})
    });
    const j=await r.json();
    if(!j.ok){markErr(j.msg||'Init failed');return;}
    session_id=j.session_id;
    chunkSize=j.chunk_size||CLIENT_CHUNK;
    totalChunks=Math.max(1,Math.ceil(file.size/chunkSize));
  }catch(e){markErr('Network error (init)');return;}

  // ── 2. Upload chunks in parallel batches ──────────────────────────────────
  let done=0;

  async function uploadChunk(idx){
    const start=idx*chunkSize;
    const blob=file.slice(start,Math.min(start+chunkSize,file.size));
    const fd=new FormData();
    fd.append('session_id',session_id);
    fd.append('chunk_index',String(idx));
    fd.append('chunk',blob,file.name);
    const r=await fetch('/api/upload/chunk',{method:'POST',body:fd});
    const j=await r.json();
    if(!r.ok||!j.ok)throw new Error(j.msg||`Chunk ${idx} failed`);
    done++;
    setPct(Math.round(done/totalChunks*100),done===totalChunks?'var(--green)':'var(--accent)');
  }

  try{
    const indices=Array.from({length:totalChunks},(_,i)=>i);
    for(let i=0;i<indices.length;i+=UP_PARALLEL){
      await Promise.all(indices.slice(i,i+UP_PARALLEL).map(uploadChunk));
    }
  }catch(e){
    fetch('/api/upload/abort',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session_id})}).catch(()=>{});
    markErr(e.message||'Upload failed');
    return;
  }

  // ── 3. Finalize ───────────────────────────────────────────────────────────
  try{
    const r=await fetch('/api/upload/finalize',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session_id})
    });
    const j=await r.json();
    if(j.ok){
      setLabel('✓','var(--green)');
      toast(file.name+' uploaded','ok');
      loadFiles(_fmCurrentPath);
    }else{
      markErr(j.msg||'Finalize failed');
    }
  }catch(e){markErr('Network error (finalize)');}
}

// ═══════════════════════════════════
// HOLIDAYS
// ═══════════════════════════════════
let _hdData = [];
let _hdLoaded = false;

function toggleHolidays(e){
  if(e) e.stopPropagation();
  const popup = document.getElementById('hd-popup');
  const isOpen = popup.style.display !== 'none';
  popup.style.display = isOpen ? 'none' : 'block';
  if(!isOpen && !_hdLoaded) loadHolidays();
}
document.addEventListener('click', e=>{
  const wrap = document.getElementById('hd-wrap');
  if(wrap && !wrap.contains(e.target)){
    const p = document.getElementById('hd-popup');
    if(p) p.style.display = 'none';
  }
});

// Country code → flag emoji
function _countryFlag(cc){
  if(!cc||cc.length!==2) return '🗓';
  return String.fromCodePoint(...cc.toUpperCase().split('').map(c=>c.charCodeAt(0)+127397));
}

// Country names lookup (mirrors COUNTRIES in the React block)
const _COUNTRY_NAMES={
  AE:"UAE",AR:"Argentina",AT:"Austria",AU:"Australia",BD:"Bangladesh",
  BE:"Belgium",BR:"Brazil",CA:"Canada",CH:"Switzerland",CN:"China",
  CO:"Colombia",CZ:"Czech Republic",DE:"Germany",DK:"Denmark",EG:"Egypt",
  ES:"Spain",FI:"Finland",FR:"France",GB:"United Kingdom",GH:"Ghana",
  GR:"Greece",HU:"Hungary",ID:"Indonesia",IE:"Ireland",IL:"Israel",
  IN:"India",IQ:"Iraq",IR:"Iran",IT:"Italy",JP:"Japan",KE:"Kenya",
  KR:"South Korea",KW:"Kuwait",LK:"Sri Lanka",MA:"Morocco",MX:"Mexico",
  MY:"Malaysia",NG:"Nigeria",NL:"Netherlands",NO:"Norway",NP:"Nepal",
  NZ:"New Zealand",OM:"Oman",PH:"Philippines",PK:"Pakistan",PL:"Poland",
  PT:"Portugal",QA:"Qatar",RO:"Romania",RU:"Russia",SA:"Saudi Arabia",
  SE:"Sweden",SG:"Singapore",TH:"Thailand",TN:"Tunisia",TR:"Turkey",
  TZ:"Tanzania",UA:"Ukraine",UG:"Uganda",US:"United States",VN:"Vietnam",
  ZA:"South Africa",ZW:"Zimbabwe",
};

async function loadHolidays(){
  try{
    // Fetch current country from settings first
    const settings = await fetch('/api/settings').then(r=>r.json()).catch(()=>({}));
    const country  = (settings.holiday_country||'US').toUpperCase();
    const subdiv   = settings.holiday_subdiv||null;
    const countryName = _COUNTRY_NAMES[country]||country;
    const flag     = _countryFlag(country);
    const yr       = new Date().getFullYear();

    // Update pill title and popup header
    const btn = document.getElementById('hd-btn');
    if(btn) btn.title = `${countryName} Public Holidays`;
    const hdr = document.getElementById('hd-popup-hdr');
    if(hdr) hdr.innerHTML = `${flag} ${countryName} Holidays &nbsp;<span id="hd-year" style="color:var(--accent-light)">${yr}</span>`;

    // Build query
    let url = `/api/holidays?year=${yr}&country=${country}`;
    if(subdiv) url += `&subdiv=${encodeURIComponent(subdiv)}`;

    const data = await fetch(url).then(r=>r.json());
    if(!Array.isArray(data)){ throw new Error(data.error||'bad response'); }
    _hdData   = data;
    _hdLoaded = true;
    const today = new Date().toISOString().slice(0,10);

    // Set next upcoming holiday label in pill
    const upcoming = _hdData.filter(h=>h.date >= today);
    if(upcoming.length){
      const next  = upcoming[0];
      const d     = new Date(next.date + 'T00:00:00');
      const label = d.toLocaleDateString('en-US',{month:'short',day:'numeric'});
      document.getElementById('hd-next-label').textContent = label;
    } else {
      document.getElementById('hd-next-label').textContent = countryName;
    }

    // Render list
    const list = document.getElementById('hd-list');
    if(!_hdData.length){
      list.innerHTML='<div style="padding:14px;text-align:center;color:var(--text3);font-size:12px">No holiday data for '+esc(countryName)+'</div>';
      return;
    }
    list.innerHTML = _hdData.map(h=>{
      const isPast   = h.date < today;
      const isToday  = h.date === today;
      const isCustom = (h.source === 'custom');
      const badge    = isCustom
        ? `<span style="font-size:9px;padding:1px 5px;border-radius:3px;background:var(--purple-dim);color:var(--purple);margin-left:4px;vertical-align:middle">custom</span>`
        : '';
      const delBtn   = isCustom
        ? `<button onclick="hdDeleteCustom(${JSON.stringify(h.date)},${JSON.stringify(h.name)},this)" title="Delete this custom holiday" style="margin-left:auto;background:none;border:none;color:var(--text3);cursor:pointer;font-size:12px;padding:2px 4px;border-radius:3px;flex-shrink:0" onmouseover="this.style.color='var(--red)'" onmouseout="this.style.color='var(--text3)'">✕</button>`
        : '';
      return `<div class="hd-row${isPast?' past':''}${isToday?' today':''}" style="display:flex;align-items:center;gap:0">
        <div class="hd-date" style="flex-shrink:0">${esc(h.date)}</div>
        <div class="hd-name" style="flex:1;min-width:0">${esc(h.name)}${badge}</div>
        ${isToday?'<div class="hd-today-tag">TODAY</div>':''}
        ${delBtn}
      </div>`;
    }).join('');
  }catch(e){
    document.getElementById('hd-list').innerHTML = '<div style="padding:14px;color:var(--red);font-size:12px">⚠ '+esc(e.message||'Failed to load holidays')+'. Ensure the <code>holidays</code> Python package is installed.</div>';
  }
}

// ── Custom holiday helpers ──────────────────────────────────────────────────
function hdAddCustomOpen(){
  const f=document.getElementById('hd-add-form');
  if(!f) return;
  const isOpen=f.style.display!=='none';
  f.style.display=isOpen?'none':'block';
  if(!isOpen){
    const di=document.getElementById('hd-add-date');
    if(di && !di.value) di.value=new Date().toISOString().slice(0,10);
    document.getElementById('hd-add-name')?.focus();
    document.getElementById('hd-add-err').style.display='none';
  }
}

async function hdAddCustomSave(){
  const date=(document.getElementById('hd-add-date')?.value||'').trim();
  const name=(document.getElementById('hd-add-name')?.value||'').trim();
  const errEl=document.getElementById('hd-add-err');
  if(!date||!name){errEl.textContent='Date and name are required.';errEl.style.display='block';return;}
  try{
    const r=await fetch('/api/holidays/custom',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({date,name,country:'CUSTOM'})});
    const j=await r.json();
    if(j.error) throw new Error(j.error);
    document.getElementById('hd-add-form').style.display='none';
    document.getElementById('hd-add-name').value='';
    toast('Custom holiday added','ok');
    _hdLoaded=false; _hdData=[];
    if(typeof window.calendarRefreshHolidays==='function') window.calendarRefreshHolidays();
    loadHolidays();
    loadCustomHolidays();
  }catch(e){errEl.textContent='✕ '+e.message;errEl.style.display='block';}
}

async function hdDeleteCustom(date,name,btn){
  if(!confirm(`Remove custom holiday "${name}" on ${date}?`)) return;
  try{
    const r=await fetch('/api/holidays/custom',{method:'DELETE',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({date,name})});
    const j=await r.json();
    if(j.error) throw new Error(j.error);
    toast('Holiday removed','ok');
    _hdLoaded=false; _hdData=[];
    if(typeof window.calendarRefreshHolidays==='function') window.calendarRefreshHolidays();
    loadHolidays();
    loadCustomHolidays();
  }catch(e){toast('Delete failed: '+e.message,'err');}
}

async function hdRefresh(){
  _hdLoaded=false; _hdData=[];
  document.getElementById('hd-list').innerHTML='<div style="padding:14px;text-align:center;color:var(--text3);font-size:12px">Refreshing…</div>';
  // Determine current country so we can bust the server cache
  try{
    const settings=await fetch('/api/settings').then(r=>r.json()).catch(()=>({}));
    const country=(settings.holiday_country||'US').toUpperCase();
    const subdiv=settings.holiday_subdiv||null;
    const yr=new Date().getFullYear();
    let url=`/api/holidays?year=${yr}&country=${country}&refresh=1`;
    if(subdiv) url+=`&subdiv=${encodeURIComponent(subdiv)}`;
    await fetch(url);
  }catch(e){}
  loadHolidays();
}

// ── Custom holiday manager (Settings tab section) ───────────────────────────
let _customHolidays=[];

async function loadCustomHolidays(){
  const tbody=document.getElementById('custom-hol-tbody');
  if(!tbody) return;
  tbody.innerHTML='<tr><td colspan="4" style="padding:10px;text-align:center;color:var(--text3);font-size:12px">Loading…</td></tr>';
  try{
    const data=await fetch('/api/holidays/custom').then(r=>r.json());
    _customHolidays=Array.isArray(data)?data:[];
    renderCustomHolidays();
  }catch(e){
    tbody.innerHTML='<tr><td colspan="4" style="padding:10px;color:var(--red);font-size:12px">✕ '+esc(e.message)+'</td></tr>';
  }
}

function renderCustomHolidays(){
  const tbody=document.getElementById('custom-hol-tbody');
  if(!tbody) return;
  if(!_customHolidays.length){
    tbody.innerHTML='<tr><td colspan="4" style="padding:12px;text-align:center;color:var(--text3);font-size:12px">No custom holidays yet. Add one below.</td></tr>';
    return;
  }
  tbody.innerHTML=_customHolidays.map((h,i)=>`
    <tr id="chol-row-${i}" style="border-bottom:1px solid var(--border)">
      <td style="padding:7px 8px;font-size:12px;font-family:var(--font-mono)">${esc(h.date)}</td>
      <td style="padding:7px 8px;font-size:12px">${esc(h.name)}</td>
      <td style="padding:7px 8px;font-size:11px;color:var(--text3)">${esc(h.country||'CUSTOM')}</td>
      <td style="padding:7px 8px;text-align:right">
        <button onclick="deleteCustomHoliday(${i})" title="Delete this holiday"
          style="background:none;border:1px solid var(--border2);color:var(--red);cursor:pointer;border-radius:4px;padding:2px 8px;font-size:11px">✕</button>
      </td>
    </tr>`).join('');
}

async function addCustomHoliday(){
  const date=(document.getElementById('chol-date')?.value||'').trim();
  const name=(document.getElementById('chol-name')?.value||'').trim();
  const country=(document.getElementById('chol-country')?.value||'CUSTOM').trim()||'CUSTOM';
  const st=document.getElementById('chol-status');
  if(!date||!name){st.textContent='Date and name are required.';st.style.color='var(--red)';return;}
  st.textContent='Saving…';st.style.color='var(--yellow)';
  try{
    const r=await fetch('/api/holidays/custom',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({date,name,country})});
    const j=await r.json();
    if(j.error) throw new Error(j.error);
    st.textContent='✓ Added';st.style.color='var(--green)';
    document.getElementById('chol-date').value='';
    document.getElementById('chol-name').value='';
    toast('Custom holiday added','ok');
    _hdLoaded=false; _hdData=[];
    if(typeof window.calendarRefreshHolidays==='function') window.calendarRefreshHolidays();
    loadCustomHolidays();
    loadHolidays();
  }catch(e){st.textContent='✕ '+e.message;st.style.color='var(--red)';}
}

async function deleteCustomHoliday(idx){
  const h=_customHolidays[idx];
  if(!h||!confirm(`Remove "${h.name}" on ${h.date}?`)) return;
  try{
    const r=await fetch('/api/holidays/custom',{method:'DELETE',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({date:h.date,name:h.name})});
    const j=await r.json();
    if(j.error) throw new Error(j.error);
    toast('Holiday removed','ok');
    _hdLoaded=false; _hdData=[];
    if(typeof window.calendarRefreshHolidays==='function') window.calendarRefreshHolidays();
    loadCustomHolidays();
    loadHolidays();
  }catch(e){toast('Delete failed: '+e.message,'err');}
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
    }).sort((a,b)=>a.name.localeCompare(b.name));
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
  _guardNav(()=>{
    _configSelected=name;
    renderConfigSidebar();
    const s=_configStreams.find(s=>s.name===name);
    if(s)renderConfigEditor(s);
  });
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
        <div class="fg">
          <label>Stream Name</label>
          <input id="cfg-name" value="${esc(s.name)}" readonly style="opacity:0.6">
        </div>
        <div class="fg">
          <label style="display:flex;align-items:center;gap:6px">
            Port (odd)
            <i class="info-btn" title="">i
              <span class="ibt">Must be an <b>odd</b> number.<br>
                HLS = port+1 &nbsp;·&nbsp; RTP = port+2 (even) &nbsp;·&nbsp; RTCP = RTP+1<br><br>
                Click <b>Check</b> to verify availability &amp; firewall status.<br>
                Click <b>Suggest</b> to auto-find the next free odd port.
              </span>
            </i>
          </label>
          <div class="port-field-row">
            <input id="cfg-port" type="number" value="${s.port}" min="1025" max="65533" step="2"
              oninput="if(+this.value%2===0&&this.value)this.value=+this.value+1"
              title="Must be an ODD number. HLS will use this port + 1.">
            <button type="button" id="suggest-btn-cfg-port"
              class="port-icon-btn"
              onclick="suggestNextPort('cfg-port','cfg-port-check-result')"
              title="Auto-find next free odd port">
              ✦
            </button>
            <button type="button" class="port-icon-btn"
              onclick="checkPort('cfg-port','cfg-port-check-result')"
              title="Check if this port is free and firewall is open">
              <i class="ti ti-radar"></i>
            </button>
          </div>
          <div id="cfg-port-check-result" style="display:none"></div>
        </div>
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
          <input type="checkbox" id="cfg-shuffle" ${s.shuffle?'checked':''} style="width:auto;accent-color:var(--accent)" title="Play files in a random order instead of sequentially">
          Shuffle playlist
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-enabled" ${s.enabled!==false?'checked':''} style="width:auto;accent-color:var(--accent)" title="Enable or disable this stream — disabled streams will not start automatically">
          Stream enabled
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-hls" ${s.hls_enabled?'checked':''} style="width:auto;accent-color:var(--accent)" title="Also serve this stream over HLS (HTTP Live Streaming) in addition to RTSP">
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
          <input type="checkbox" id="cfg-comp-en" ${s.compliance_enabled?'checked':''} style="width:auto;accent-color:var(--accent)"
            title="Sync playback position to real-world clock so viewers see what a linear broadcast would show right now">
          Enable compliance mode (broadcast-sync seek on start)
        </label>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">
          <div class="fg">
            <label>Broadcast start time (HH:MM:SS)</label>
            <input id="cfg-comp-start" value="${esc(s.compliance_start||'06:00:00')}" placeholder="06:00:00" pattern="\\d{1,2}:\\d{2}:\\d{2}">
          </div>
        </div>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="cfg-comp-loop" ${s.compliance_loop?'checked':''} style="width:auto;accent-color:var(--accent)"
            title="When the video is shorter than 24 h, calculate the seek position within the current loop iteration">
          Loop calculation (seek within loops for videos shorter than 24 h)
        </label>
        <div style="font-size:10px;color:var(--text3)">
          When enabled, HydraCast calculates the correct playback seek offset so the stream matches a continuous linear broadcast that started at the configured time today.
        </div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Playlist Source</div>
      <div style="display:flex;gap:0;margin-bottom:12px;border-bottom:1px solid var(--border)">
        <button id="cfg-src-tab-files" class="nav-tab ${!s.folder_source?'active':''}"
                onclick="switchCfgSrcTab('files')" style="padding:7px 16px;font-size:12px"
                title="Build the playlist by adding individual files">
          <span class="tab-dot"></span>File List
        </button>
        <button id="cfg-src-tab-folder" class="nav-tab ${s.folder_source?'active':''}"
                onclick="switchCfgSrcTab('folder')" style="padding:7px 16px;font-size:12px"
                title="Use an entire folder as the playlist source — all media files inside will play in order">
          <span class="tab-dot"></span>Folder Source
        </button>
      </div>
      <div id="cfg-src-files" style="display:${!s.folder_source?'':'none'}">
        <div id="cfg-pl-wrap"></div>
      </div>
      <div id="cfg-src-folder" style="display:${s.folder_source?'':'none'}">
        <div class="fg">
          <label>Folder Path</label>
          <div style="display:flex;gap:8px;align-items:center">
            <input id="cfg-folder" value="${esc(s.folder_source||'')}"
                   placeholder="/media/shows  or  media/news" style="flex:1;min-width:0"
                   oninput="_markDirty()">
            <button class="btn b" style="white-space:nowrap;flex-shrink:0"
                    title="Browse the media library to pick a folder"
                    onclick="mbOpen('folder','cfg-folder')">
              <i class="fa fa-folder-open" style="margin-right:5px"></i>Browse
            </button>
          </div>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:6px">
          HydraCast will scan the folder and auto-rebuild the playlist when files change.
          Day-tags (_mon_, _tue_, …) are detected automatically.
        </div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Stream Actions</div>
      <div class="btn-group">
        <button class="btn g" onclick="api('start',{name:'${esc(s.name)}'})" title="Start this stream">▶ Start</button>
        <button class="btn r" onclick="api('stop',{name:'${esc(s.name)}'})" title="Stop this stream">■ Stop</button>
        <button class="btn" onclick="api('restart',{name:'${esc(s.name)}'})" title="Restart this stream">↺ Restart</button>
        ${s.playlist_count>1?`<button class="btn" onclick="api('skip_next',{name:'${esc(s.name)}'})" title="Skip to the next file in the playlist">⏭ Skip</button>`:''}
      </div>
    </div>`;

  document.getElementById('config-main-footer').style.display='flex';
  _clearDirty();
  renderPlaylistEditor('cfg-pl-wrap', s.files||'');
  setTimeout(_attachDirtyListeners, 0);
}

function _restoreFooter(){
  document.getElementById('config-main-footer').innerHTML=`
    <button class="btn" onclick="cancelConfig()" title="Discard unsaved changes and go back">Cancel</button>
    <button class="btn g" onclick="saveConfig()" title="Save changes to this stream configuration">Save Changes</button>`;
}

function cancelConfig(){
  _clearDirty();
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
  // Detect source mode
  const isFolderMode=document.getElementById('cfg-src-folder')?.style.display!=='none';
  const folderPath=isFolderMode?(document.getElementById('cfg-folder')?.value||'').trim():'';
  const files=isFolderMode?'':_plGetStr('cfg-pl-wrap');
  if(isFolderMode&&!folderPath){toast('Folder path is required for folder source','err');return;}
  if(!isFolderMode&&!files){toast('At least one file path is required','err');return;}
  const payload={
    name:_configSelected,
    port:parseInt(document.getElementById('cfg-port')?.value||0),
    stream_path:document.getElementById('cfg-path')?.value||'',
    video_bitrate:document.getElementById('cfg-vbr')?.value||'',
    audio_bitrate:document.getElementById('cfg-abr')?.value||'',
    shuffle:document.getElementById('cfg-shuffle')?.checked||false,
    enabled:document.getElementById('cfg-enabled')?.checked!==false,
    hls_enabled:document.getElementById('cfg-hls')?.checked||false,
    files,
    folder_source:folderPath||null,
    weekdays:weekdaysStr,
    compliance_enabled:document.getElementById('cfg-comp-en')?.checked||false,
    compliance_start:document.getElementById('cfg-comp-start')?.value||'06:00:00',
    compliance_loop:document.getElementById('cfg-comp-loop')?.checked||false,
    compliance_alert_enabled:document.getElementById('cfg-comp-alert')?.checked!==false,
  };
  const r=await api('update_config',payload);
  if(r?.ok){_clearDirty();loadConfig();}
}

function switchCfgSrcTab(mode){
  document.getElementById('cfg-src-files').style.display=mode==='files'?'':'none';
  document.getElementById('cfg-src-folder').style.display=mode==='folder'?'':'none';
  document.getElementById('cfg-src-tab-files').classList.toggle('active',mode==='files');
  document.getElementById('cfg-src-tab-folder').classList.toggle('active',mode==='folder');
  _markDirty();
}

// ═══════════════════════════════════
// NEW STREAM / DELETE STREAM
// ═══════════════════════════════════
let _configMode='edit'; // 'edit' | 'create'

// ── Dirty / Unsaved state ────────────────────────────────────────────────────
let _configDirty=false;
let _pendingNav=null;
let _playlistItems=[];

function _markDirty(){
  if(_configDirty)return;
  _configDirty=true;
  const ftr=document.getElementById('config-main-footer');
  if(ftr&&!document.getElementById('_dirty-badge')){
    const b=document.createElement('span');
    b.id='_dirty-badge';b.className='dirty-badge';b.textContent='● Unsaved';
    ftr.insertBefore(b,ftr.firstChild);
  }
}
function _clearDirty(){
  _configDirty=false;
  const b=document.getElementById('_dirty-badge');if(b)b.remove();
}
function _guardNav(cb){
  if(!_configDirty){cb();return;}
  _pendingNav=cb;
  document.getElementById('unsaved-modal').classList.add('open');
}
function handleUnsaved(action){
  document.getElementById('unsaved-modal').classList.remove('open');
  if(action==='cancel'){_pendingNav=null;return;}
  const cb=_pendingNav;_pendingNav=null;
  if(action==='discard'){_clearDirty();if(cb)cb();}
  else if(action==='save'){
    const fn=_configMode==='create'?submitNewStream:saveConfig;
    fn().then(()=>{if(cb)cb();});
  }
}
function _attachDirtyListeners(){
  const body=document.getElementById('config-main-body');if(!body)return;
  body.querySelectorAll('input,select,textarea').forEach(el=>{
    el.addEventListener('change',_markDirty);
    if(el.type==='text'||el.type==='number')el.addEventListener('input',_markDirty);
  });
}

// ── Weekday-aware playlist sort ─────────────────────────────
// Detects _mon_/_monday_, _tue_, … _sun_ tags in file basenames and sorts
// Mon→Tue→Wed→Thu→Fri→Sat→Sun.  Falls back to numeric priority for non-day files.
(function(){
  const _DAY_RANK={monday:0,mon:0,tuesday:1,tue:1,wednesday:2,wed:2,
                   thursday:3,thu:3,friday:4,fri:4,saturday:5,sat:5,sunday:6,sun:6};
  const _DAY_RE=/[_\-](monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)[_\-]/i;
  function _dayRank(path){
    const m=_DAY_RE.exec((path||'').replace(/\\/g,'/').split('/').pop()||'');
    return m?_DAY_RANK[m[1].toLowerCase()]:-1;
  }
  // Check whether ALL items that have a day tag together cover a full week
  // (or at least more than one day), so we only apply weekday sort when the
  // playlist really is a weekly set and not a coincidental single day-tag.
  function _isWeeklySet(items){
    const tagged=items.filter(it=>_dayRank(it.path)>=0);
    if(!tagged.length)return false;
    const unique=new Set(tagged.map(it=>_dayRank(it.path)));
    return unique.size>1;  // two or more distinct days → treat as weekly set
  }
  window._plSortItems=function(items){
    if(_isWeeklySet(items)){
      // Day-tagged files sort Mon→Sun; untagged files go after (stable relative order)
      items.sort((a,b)=>{
        const da=_dayRank(a.path),db=_dayRank(b.path);
        if(da>=0&&db>=0)return da-db;   // both tagged: weekday order
        if(da>=0)return -1;             // only a tagged: a comes first
        if(db>=0)return  1;             // only b tagged: b comes first
        // neither tagged: fall back to priority
        const ap=a.priority>0?a.priority:999999,bp=b.priority>0?b.priority:999999;
        return ap-bp;
      });
    } else {
      // No weekly set → keep original priority-only sort
      items.sort((a,b)=>{const ap=a.priority>0?a.priority:999999,bp=b.priority>0?b.priority:999999;return ap-bp;});
    }
    return items;
  };
})();

// ── Playlist editor helpers ──────────────────────────────────────────────────
function _parsePL(raw){
  const items=[];
  for(let part of (raw||'').split(/[;\n]+/)){
    part=part.trim();if(!part)continue;
    let priority=0,start='00:00:00';
    if(part.includes('#')){const idx=part.lastIndexOf('#');const n=parseInt(part.slice(idx+1));if(!isNaN(n))priority=n;part=part.slice(0,idx).trim();}
    if(part.includes('@')){const idx=part.lastIndexOf('@');const s=part.slice(idx+1).trim();if(/^\d{1,2}:\d{2}:\d{2}$/.test(s))start=s;part=part.slice(0,idx).trim();}
    if(part)items.push({path:part,start,priority});
  }
  return items;
}
function _plToStr(items){
  return items.map(item=>{
    let s=item.path;
    if(item.start&&item.start!=='00:00:00')s+='@'+item.start;
    if(item.priority!==0)s+='#'+item.priority;
    return s;
  }).join('\n');
}
function _plChannel(path){
  const p=(path||'').replace(/\\/g,'/').split('/').filter(Boolean);
  return p.length>=2?p[p.length-2]:'';
}
function _plPriBadge(n){
  const cls=n>=10?'high':n>0?'mid':'low';
  return '<span class="pl-priority-badge '+cls+'">'+n+'</span>';
}
function _plGetStr(cid){
  const ta=document.querySelector('#'+cid+' textarea');
  if(ta)return ta.value;
  document.querySelectorAll('#'+cid+' .pl-table tbody tr').forEach((tr,i)=>{
    const pi=tr.querySelector('input[type=number]'),si=tr.querySelector('input[type=text]');
    if(pi&&_playlistItems[i])_playlistItems[i].priority=parseInt(pi.value)||0;
    if(si&&_playlistItems[i])_playlistItems[i].start=si.value||'00:00:00';
  });
  return _plToStr(_playlistItems);
}
function renderPlaylistEditor(cid,raw){
  _playlistItems=_parsePL(raw);
  _plSortItems(_playlistItems);
  _renderPLTable(cid);
}
function _renderPLTable(cid){
  const wrap=document.getElementById(cid);if(!wrap)return;
  const rows=_playlistItems.map((item,i)=>{
    const ch=_plChannel(item.path);
    const fname=(item.path||'').replace(/\\/g,'/').split('/').pop()||item.path;
    return '<tr>'
      +'<td style="width:82px;text-align:center;vertical-align:top;padding-top:8px">'
        +_plPriBadge(item.priority)
        +'<div style="margin-top:4px"><input type="number" value="'+item.priority+'" min="0" max="999"'
        +' oninput="_plUpd('+i+',&apos;p&apos;,this.value)" style="width:54px;text-align:center"></div>'
      +'</td>'
      +'<td style="width:100px">'+(ch?'<span class="pl-channel-tag">'+esc(ch)+'</span>':'<span style="color:var(--text3);font-size:10px">—</span>')+'</td>'
      +'<td><div class="pl-path" title="'+esc(item.path)+'" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:300px">'+esc(fname)+'</div>'
        +'<div style="font-size:10px;color:var(--text3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:300px">'+esc(item.path)+'</div></td>'
      +'<td style="width:106px"><input type="text" value="'+esc(item.start)+'" placeholder="00:00:00"'
        +' oninput="_plUpd('+i+',&apos;s&apos;,this.value)" style="width:94px;font-family:var(--font-mono);font-size:11px"></td>'
      +'<td style="width:40px;text-align:right"><button class="btn r" style="padding:2px 7px;font-size:10px"'
        +' title="Remove this file from the playlist" onclick="_plRemove('+i+',&apos;'+cid+'&apos;)">&#x2715;</button></td>'
      +'</tr>';
  }).join('');

  wrap.innerHTML=
    '<div class="pl-editor">'
      +'<div class="pl-toolbar">'
        +'<span class="pl-toolbar-label"><i class="fa fa-list-ol" style="margin-right:5px;opacity:0.65"></i>'
        +_playlistItems.length+' file'+(_playlistItems.length!==1?'s':'')+'</span>'
        +'<button class="btn b" style="padding:3px 10px;font-size:10px" title="Sort files by priority (highest first)" onclick="_plSort(&apos;'+cid+'&apos;)">'
          +'<i class="fa fa-sort-numeric-up" style="margin-right:4px"></i>Sort by Priority</button>'
        +'<button class="btn" style="padding:3px 10px;font-size:10px" title="View or edit the raw playlist text" onclick="_plRawView(&apos;'+cid+'&apos;)">'
          +'<i class="fa fa-code" style="margin-right:4px"></i>Raw</button>'
      +'</div>'
      +(_playlistItems.length>0
        ?'<div style="overflow-x:auto"><table class="pl-table">'
          +'<thead><tr>'
            +'<th style="width:82px;text-align:center">Priority</th>'
            +'<th style="width:100px">Channel</th>'
            +'<th>File</th>'
            +'<th style="width:106px">Start At</th>'
            +'<th style="width:40px"></th>'
          +'</tr></thead>'
          +'<tbody>'+rows+'</tbody>'
          +'</table></div>'
        :'<div class="pl-empty"><i class="fa fa-film" style="font-size:22px;opacity:0.25;margin-bottom:6px;display:block"></i>'
          +'No files yet — add one below</div>')
      +'<div class="pl-add-row">'
        +'<input type="text" id="'+cid+'-new" placeholder="/path/to/video.mp4  (optional: path@HH:MM:SS#priority)"'
          +' onkeydown="if(event.key===&apos;Enter&apos;)_plAdd(&apos;'+cid+'&apos;)">'
        +'<button class="btn b" style="padding:5px 10px;font-size:11px;white-space:nowrap;flex-shrink:0"'
          +' title="Browse the media library to pick a file" onclick="mbOpen(&apos;files&apos;,&apos;'+cid+'&apos;)">'
          +'<i class="fa fa-folder-open" style="margin-right:4px"></i>Browse</button>'
        +'<button class="btn g" style="padding:5px 12px;font-size:11px;white-space:nowrap"'
          +' title="Add this file path to the playlist" onclick="_plAdd(&apos;'+cid+'&apos;)"><i class="fa fa-plus"></i> Add</button>'
      +'</div>'
    +'</div>';
}
function _plUpd(i,field,v){
  if(!_playlistItems[i])return;
  if(field==='p')_playlistItems[i].priority=parseInt(v)||0;
  else _playlistItems[i].start=v||'00:00:00';
  _markDirty();
}
function _plRemove(i,cid){
  _playlistItems.splice(i,1);
  _markDirty();
  _renderPLTable(cid);
}
function _plSort(cid){
  document.querySelectorAll('#'+cid+' .pl-table tbody tr').forEach((tr,i)=>{
    const pi=tr.querySelector('input[type=number]'),si=tr.querySelector('input[type=text]');
    if(pi&&_playlistItems[i])_playlistItems[i].priority=parseInt(pi.value)||0;
    if(si&&_playlistItems[i])_playlistItems[i].start=si.value||'00:00:00';
  });
  _plSortItems(_playlistItems);
  _renderPLTable(cid);
}
function _plAdd(cid){
  const inp=document.getElementById(cid+'-new');if(!inp)return;
  const raw=inp.value.trim();if(!raw){toast('Enter a file path','err');return;}
  const parsed=_parsePL(raw);if(!parsed.length){toast('Invalid path','err');return;}
  _playlistItems.push(...parsed);
  _plSortItems(_playlistItems);
  inp.value='';_markDirty();_renderPLTable(cid);
}
function _plRawView(cid){
  document.querySelectorAll('#'+cid+' .pl-table tbody tr').forEach((tr,i)=>{
    const pi=tr.querySelector('input[type=number]'),si=tr.querySelector('input[type=text]');
    if(pi&&_playlistItems[i])_playlistItems[i].priority=parseInt(pi.value)||0;
    if(si&&_playlistItems[i])_playlistItems[i].start=si.value||'00:00:00';
  });
  const raw=_plToStr(_playlistItems);
  const wrap=document.getElementById(cid);if(!wrap)return;
  wrap.innerHTML=
    '<div class="pl-editor">'
      +'<div class="pl-toolbar">'
        +'<span class="pl-toolbar-label"><i class="fa fa-code" style="margin-right:5px;opacity:0.65"></i>Raw edit</span>'
        +'<button class="btn" style="padding:3px 10px;font-size:10px" title="Switch back to the visual playlist table editor" onclick="_plTableView(&apos;'+cid+'&apos;)">'
          +'<i class="fa fa-table" style="margin-right:4px"></i>Back to Table</button>'
      +'</div>'
      +'<div style="padding:12px">'
        +'<textarea rows="8" style="width:100%;font-size:11px;font-family:var(--font-mono);background:var(--bg);border:1px solid var(--border);'
          +'border-radius:var(--radius);padding:10px;color:var(--text);resize:vertical;box-sizing:border-box"'
          +' oninput="_markDirty()">'+esc(raw)+'</textarea>'
        +'<div style="font-size:10px;color:var(--text3);margin-top:5px">Format: '
          +'<code style="color:var(--accent-light)">/path/to/file.mp4@00:00:00#10</code>'
          +' — one per line or semicolon-separated</div>'
      +'</div>'
    +'</div>';
}
function _plTableView(cid){
  const ta=document.querySelector('#'+cid+' textarea');
  if(ta){_playlistItems=_parsePL(ta.value);_plSortItems(_playlistItems);_markDirty();}
  _renderPLTable(cid);
}

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
        <div class="fg">
          <label style="display:flex;align-items:center;gap:6px">
            Port * (odd)
            <i class="info-btn" title="">i
              <span class="ibt">Must be an <b>odd</b> number, ≥10 apart from other streams.<br>
                HLS = port+1 &nbsp;·&nbsp; RTP = port+2 (even) &nbsp;·&nbsp; RTCP = RTP+1<br><br>
                Click <b>Suggest</b> to auto-find the next free odd port.
              </span>
            </i>
          </label>
          <div class="port-field-row">
            <input id="new-port" type="number" value="30123" min="1025" max="65533" step="2"
              oninput="if(+this.value%2===0&&this.value)this.value=+this.value+1"
              title="Must be an ODD number. HLS will use this port + 1 (even).">
            <button type="button" id="suggest-btn-new-port"
              class="port-icon-btn"
              onclick="suggestNextPort('new-port','new-port-check-result')"
              title="Auto-find next free odd port">
              ✦
            </button>
            <button type="button" class="port-icon-btn"
              onclick="checkPort('new-port','new-port-check-result')"
              title="Check if this port is free and firewall is open">
              <i class="ti ti-radar"></i>
            </button>
          </div>
          <div id="new-port-check-result" style="display:none"></div>
        </div>
        <div class="fg">
          <label>Stream Path <span style="font-size:10px;color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0">(blank = IP:Port/ root)</span></label>
          <input id="new-spath" value="" placeholder="e.g. live  (optional)">
        </div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Playlist Source</div>
      <div style="display:flex;gap:0;margin-bottom:12px;border-bottom:1px solid var(--border)">
        <button id="new-src-tab-files" class="nav-tab active" onclick="switchNewSrcTab('files')" style="padding:7px 16px;font-size:12px" title="Build the playlist by adding individual files"><span class="tab-dot"></span>File List</button>
        <button id="new-src-tab-folder" class="nav-tab" onclick="switchNewSrcTab('folder')" style="padding:7px 16px;font-size:12px" title="Use an entire folder as the playlist source — all media files inside will play in order"><span class="tab-dot"></span>Folder Source</button>
      </div>
      <div id="new-src-files">
        <div id="new-pl-wrap"></div>
      </div>
      <div id="new-src-folder" style="display:none">
        <div class="fg">
          <label>Folder Path</label>
          <div style="display:flex;gap:8px;align-items:center">
            <input id="new-folder" placeholder="/media/shows  or  media/news" style="flex:1;min-width:0">
            <button class="btn b" style="white-space:nowrap;flex-shrink:0"
                    title="Browse the media library to pick a folder"
                    onclick="mbOpen('folder','new-folder')">
              <i class="fa fa-folder-open" style="margin-right:5px"></i>Browse
            </button>
          </div>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:6px">HydraCast will scan the folder and auto-rebuild the playlist when files change. Day-tags (_mon_, _tue_, …) are detected automatically.</div>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Encoding</div>
      <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">
        <div class="fg"><label>Video Bitrate</label><input id="new-vbr" value="" placeholder="copy (default) or e.g. 2500k"></div>
        <div class="fg"><label>Audio Bitrate</label><input id="new-abr" value="" placeholder="copy (default) or e.g. 128k"></div>
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
          <input type="checkbox" id="new-shuffle" style="width:auto;accent-color:var(--accent)" title="Play files in a random order instead of sequentially">Shuffle playlist
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="new-enabled" checked style="width:auto;accent-color:var(--accent)" title="Enable this stream — uncheck to create it without starting it">Enabled
        </label>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
          <input type="checkbox" id="new-hls" style="width:auto;accent-color:var(--accent)" title="Also serve this stream over HLS (HTTP Live Streaming) in addition to RTSP">HLS enabled
        </label>
      </div>
    </div>
    <div class="config-section">
      <div class="config-section-title">Compliance — Broadcast Sync</div>
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:12px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:13px;color:var(--text);font-weight:500;margin-bottom:12px">
          <input type="checkbox" id="new-comp-en" style="width:auto;accent-color:var(--accent)"
            title="Sync playback position to real-world clock so viewers see what a linear broadcast would show right now"
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
            <input type="checkbox" id="new-comp-loop" style="width:auto;accent-color:var(--accent)"
              title="When the video is shorter than 24 h, calculate the seek position within the current loop iteration">
            Loop calculation — seek within loops for videos shorter than 24 h
          </label>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
            <input type="checkbox" id="new-comp-strict" style="width:auto;accent-color:var(--accent)"
              title="Stop the stream entirely if the calculated seek offset exceeds the video duration (prevents silent looping)">
            Strict mode — stop stream if seek offset exceeds video duration
          </label>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2);margin-top:6px">
            <input type="checkbox" id="new-comp-alert" checked style="width:auto;accent-color:var(--accent)"
              title="Show a pulsing error banner on the dashboard when a compliance error occurs">
            Show compliance error banner on dashboard
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
    <button class="btn" onclick="cancelConfig()" title="Discard and go back without creating a stream">Cancel</button>
    <button class="btn g" onclick="submitNewStream()" title="Create this new stream and save it to configuration">&#x2713; Create Stream</button>`;
  document.getElementById('config-main-footer').style.display='flex';
  _clearDirty();
  renderPlaylistEditor('new-pl-wrap', '');
  setTimeout(_attachDirtyListeners, 0);
  // Auto-suggest a free port on load
  setTimeout(()=>suggestNextPort('new-port','new-port-check-result'), 120);
}

function switchNewSrcTab(mode){
  document.getElementById('new-src-files').style.display=mode==='files'?'':'none';
  document.getElementById('new-src-folder').style.display=mode==='folder'?'':'none';
  document.getElementById('new-src-tab-files').classList.toggle('active',mode==='files');
  document.getElementById('new-src-tab-folder').classList.toggle('active',mode==='folder');
}

// ── Port checker ─────────────────────────────────────────────────────────────

/** Suggest and auto-apply the next free odd port, then run checkPort. */
async function suggestNextPort(inputId, resultId){
  const inp = document.getElementById(inputId);
  if(!inp) return;
  // Always start 2 above the current value so the button advances to a
  // genuinely *next* free port instead of returning the same port when
  // the current one happens to be free already.
  const cur = parseInt(inp.value||0)||60121;
  const from = cur + 2;
  const suggestBtn = document.getElementById('suggest-btn-'+inputId);
  if(suggestBtn){
    suggestBtn._origHTML = suggestBtn.innerHTML;
    suggestBtn.innerHTML='<i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite"></i>';
    suggestBtn.disabled=true;
  }
  _showPortNotif(_portSpinner('Scanning for a free port…'));
  try{
    const d = await fetch('/api/suggest_port?from='+from).then(r=>r.json());
    if(d.port){
      inp.value = d.port;
      inp.dispatchEvent(new Event('input'));
      await checkPort(inputId, resultId);
    } else {
      _showPortNotif(_portBanner('err','No free port found in the scanned range. Try a different starting port.'));
    }
  }catch(e){
    _showPortNotif(_portBanner('err','Suggest failed: '+esc(e.message||String(e))));
  }finally{
    if(suggestBtn){ suggestBtn.innerHTML=suggestBtn._origHTML||'✦'; suggestBtn.disabled=false; }
  }
}

async function checkPort(inputId, resultId){
  const inp = document.getElementById(inputId);
  if(!inp) return;
  const port = parseInt(inp.value||0);
  if(!port||port<1024||port>65534){
    _showPortNotif(_portBanner('warn','Enter a valid port first (1024–65534).'));
    return;
  }
  _showPortNotif(_portSpinner('Checking port '+port+'…'));
  try{
    const d = await fetch('/api/check_port?port='+port).then(r=>r.json());

    // ── Verdict banner ────────────────────────────────────────────────────
    let html = d.ok
      ? _portBanner('ok', `Port <b>${port}</b> is free and ready to use.`)
      : _portBanner('err', `Port <b>${port}</b> has conflicts.`);

    // ── Odd-port nudge ────────────────────────────────────────────────────
    if(!d.odd_ok){
      const next = port%2===0 ? port+1 : port;
      html += `<div class="pnb warn" style="flex-wrap:wrap;gap:8px">
        <i class="ti ti-alert-triangle" style="flex-shrink:0"></i>
        <span style="flex:1">Odd port required — HLS uses the next even port.</span>
        <button type="button" onclick="document.getElementById('${inputId}').value=${next};
          document.getElementById('${inputId}').dispatchEvent(new Event('input'));
          checkPort('${inputId}','${resultId}')"
          style="background:var(--yellow);color:#1c1c1e;border:none;border-radius:5px;
          padding:3px 10px;font-size:10px;font-weight:700;cursor:pointer;white-space:nowrap;flex-shrink:0">
          Use ${next} ↵
        </button>
      </div>`;
    }

    // ── Port map chips ────────────────────────────────────────────────────
    html += `<div>
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;
        color:var(--text3);margin-bottom:6px">Port Map</div>
      <div class="pmgrid">${_portMapChips(d.ports)}</div>`;

    // ── Conflict process details ───────────────────────────────────────────
    const conflicts = Object.entries(d.ports||{}).filter(([,i])=>!i.free);
    if(conflicts.length){
      html += `<div style="margin-top:6px;font-size:10px;color:var(--text3);line-height:2;display:flex;flex-wrap:wrap;gap:6px">`;
      conflicts.forEach(([p,info])=>{
        html += `<span style="display:inline-flex;align-items:center;gap:4px;
          background:var(--red-dim);border:1px solid rgba(194,120,120,0.3);
          border-radius:5px;padding:2px 8px">
          <i class="ti ti-lock" style="color:var(--red);font-size:9px"></i>
          <b style="color:var(--text2);font-family:var(--font-mono)">${p}</b>
          <span style="color:var(--red)">${esc(info.process||'in use')}</span>
        </span>`;
      });
      html += `</div>`;
    }
    html += `</div>`;

    // ── Firewall row with open button ─────────────────────────────────────
    if(d.firewall&&d.firewall.checked){
      const fwOk=!d.firewall.blocked;
      html += `<div class="fw-row">
        <i class="ti ti-shield${fwOk?'-check':'-x'}" style="color:${fwOk?'var(--green)':'var(--red)'};font-size:13px;flex-shrink:0"></i>
        <span style="font-size:11px;flex:1;color:${fwOk?'var(--green)':'var(--red)'}">${esc(d.firewall.detail)}</span>
      </div>`;
      if(!fwOk){
        const allPorts=Object.keys(d.ports||{}).map(Number).filter(Boolean);
        html += `<button id="fw-open-action-btn" class="fw-open-btn"
          onclick="openFirewall([${allPorts.join(',')}], '${inputId}')"
          title="Attempt to automatically open these ports in your system firewall">
          <i class="ti ti-shield-plus"></i> Open Ports in Firewall
        </button>`;
      }
    } else if(d.firewall&&d.firewall.detail){
      html += `<div class="fw-row">
        <i class="ti ti-info-circle" style="font-size:13px;flex-shrink:0"></i>
        <span style="font-size:11px;flex:1">${esc(d.firewall.detail)}</span>
      </div>`;
      // Always show open button even for informational firewall status
      const allPorts=Object.keys(d.ports||{}).map(Number).filter(Boolean);
      if(allPorts.length){
        html += `<button id="fw-open-action-btn" class="fw-open-btn"
          onclick="openFirewall([${allPorts.join(',')}], '${inputId}')"
          title="Attempt to automatically open these ports in your system firewall">
          <i class="ti ti-shield-plus"></i> Open Ports in Firewall
        </button>`;
      }
    }

    // ── Warnings ──────────────────────────────────────────────────────────
    (d.warnings||[]).forEach(w=>{
      html += _portBanner('warn', esc(w));
    });

    // ── Suggest next if conflicts ──────────────────────────────────────────
    if(!d.ok){
      html += `<button type="button"
        class="port-action-btn suggest" style="width:100%;justify-content:center"
        onclick="suggestNextPort('${inputId}','${resultId}')">
        ✦ Find next free port
      </button>`;
    }

    _showPortNotif(html);
  }catch(e){
    _showPortNotif(_portBanner('err','Check failed: '+esc(e.message||String(e))));
  }
}

/** Open ports in system firewall via the backend API */
async function openFirewall(ports, inputId){
  const btn = document.getElementById('fw-open-action-btn');
  if(btn){ btn.disabled=true; btn.innerHTML='<i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite"></i> Opening…'; }
  try{
    const res = await fetch('/api/open_firewall',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ports}),
    });
    const d = await res.json();
    const body = document.getElementById('port-notif-body');
    if(!body) return;

    if(d.ok){
      // Replace the fw-open-btn with success banner
      const fwBtn = document.getElementById('fw-open-action-btn');
      if(fwBtn){
        fwBtn.className='fw-open-btn done';
        fwBtn.disabled=true;
        fwBtn.innerHTML=`<i class="ti ti-shield-check"></i> Opened ${d.opened.length} port(s) — ${esc(d.msg)}`;
      }
      // Re-run the port check to confirm
      setTimeout(()=>checkPort(inputId,'_'), 800);
    } else {
      // Show error in the panel below existing content
      const existing = body.querySelector('.fw-err-row');
      if(existing) existing.remove();
      const errDiv = document.createElement('div');
      errDiv.className='fw-err-row';
      errDiv.innerHTML = _portBanner('err', esc(d.msg||'Firewall open failed.'))
        + (d.hint ? `<div style="margin-top:5px;font-size:10px;color:var(--text3);font-family:var(--font-mono);background:var(--bg3);border:1px solid var(--border);border-radius:5px;padding:6px 10px;white-space:pre-wrap">${esc(d.hint)}</div>` : '');
      body.appendChild(errDiv);
      if(btn){ btn.disabled=false; btn.innerHTML='<i class="ti ti-shield-plus"></i> Open Ports in Firewall'; }
    }
  }catch(e){
    if(btn){ btn.disabled=false; btn.innerHTML='<i class="ti ti-shield-plus"></i> Open Ports in Firewall'; }
    _showPortNotif(_portBanner('err','Firewall request failed: '+esc(e.message||String(e))));
  }
}

async function submitNewStream(){
  const name=(document.getElementById('new-name')?.value||'').trim();
  const port=parseInt(document.getElementById('new-port')?.value||0);
  // Detect source mode
  const isFolderMode=document.getElementById('new-src-folder')?.style.display!=='none';
  const files=isFolderMode?'':_plGetStr('new-pl-wrap');
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
    video_bitrate:(document.getElementById('new-vbr')?.value||'copy').trim()||'copy',
    audio_bitrate:(document.getElementById('new-abr')?.value||'copy').trim()||'copy',
    shuffle:document.getElementById('new-shuffle')?.checked||false,
    enabled:document.getElementById('new-enabled')?.checked!==false,
    hls_enabled:document.getElementById('new-hls')?.checked||false,
    compliance_enabled:document.getElementById('new-comp-en')?.checked||false,
    compliance_start:(document.getElementById('new-comp-start')?.value||'06:00:00').trim()||'06:00:00',
    compliance_loop:document.getElementById('new-comp-loop')?.checked||false,
    compliance_strict:document.getElementById('new-comp-strict')?.checked||false,
    compliance_alert_enabled:document.getElementById('new-comp-alert')?.checked!==false,
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
  if(!confirm(`Delete stream "${name}"?\n\nThis will remove it from streams.hcf immediately. The stream will be stopped if it is currently running.`))return;
  const r=await api('delete_stream',{name});
  if(r?.ok){
    if(_configSelected===name) cancelConfig();
    loadConfig();
  }
}

// ═══════════════════════════════════════════════════════════════
// MEDIA BROWSER MODAL
// ═══════════════════════════════════════════════════════════════
/*
  mbOpen(mode, target)
    mode   : 'files'  → user picks a file; path is inserted into target input or playlist
           : 'folder' → user picks a folder; path is written into target input
    target : element id of the <input> to write into (folder mode),
             or playlist container id (files mode, triggers _plAddPath)

  The browser fetches /api/files?path=<relative> and /api/files?path=
  to build the sidebar of top-level dirs. Clicking a folder navigates into it.
  In files mode, clicking a file row selects it; double-click confirms.
  In folder mode, clicking any folder row selects it; double-click navigates.
*/

let _mb = {
  mode:     'files',   // 'files' | 'folder'
  target:   '',        // input id or playlist cid
  path:     '',        // current browse path (relative to media root)
  selected: null,      // {path, isDir, fullServerPath}
  loading:  false,
  rootDirs: [],        // top-level dirs for sidebar
  _fmRootMeta: [],     // [{path, label}] for dir-select dropdowns
  // ── path cache: avoids re-fetching a folder already visited this session ──
  _cache:   {},        // path → {data, ts}
  _rootCache: null,    // cached root listing (never changes in a session)
};
const _MB_CACHE_TTL = 30000; // ms — stale after 30 s

function _mbCacheGet(path) {
  const e = _mb._cache[path];
  if (!e) return null;
  if (Date.now() - e.ts > _MB_CACHE_TTL) { delete _mb._cache[path]; return null; }
  return e.data;
}
function _mbCacheSet(path, data) {
  _mb._cache[path] = { data, ts: Date.now() };
}

function mbOpen(mode, target) {
  _mb.mode    = mode;
  _mb.target  = target;
  _mb.path    = '';
  _mb.selected = null;
  _mb.loading  = false;
  // Clear per-path cache on each open so fresh content is shown.
  // Root cache is kept — root dirs never change during a session.
  _mb._cache = {};

  // Update modal chrome
  document.getElementById('mb-mode-icon').textContent = mode === 'folder' ? '📁' : '🎬';
  document.getElementById('mb-title').textContent     = mode === 'folder' ? 'Browse for Folder' : 'Browse for File';
  document.getElementById('mb-subtitle').textContent  = mode === 'folder'
    ? 'Navigate and click a folder to select it, then confirm.'
    : 'Navigate and click a file to select it, then confirm. Double-click to confirm instantly.';

  _mbSetSelection(null);
  document.getElementById('mb-modal').classList.add('open');
  _mbLoad('');
}

function mbClose() {
  document.getElementById('mb-modal').classList.remove('open');
  _mb.selected = null;
}

function mbRefresh() { _mbLoad(_mb.path); }

function mbConfirm() {
  if (!_mb.selected) { toast('Nothing selected', 'err'); return; }
  const p = _mb.selected.path;

  if (_mb.mode === 'folder') {
    // Write into the target input
    const el = document.getElementById(_mb.target);
    if (el) { el.value = p; el.dispatchEvent(new Event('input')); }
    _markDirty();
    toast('Folder selected', 'ok');
  } else {
    // Files mode — insert into playlist
    const cid = _mb.target;
    _plAddPath(cid, p);
    toast('File added to playlist', 'ok');
  }
  mbClose();
}

// Insert a path directly into the playlist by cid (bypasses the text input)
function _plAddPath(cid, path) {
  if (!path) return;
  // Sync any inline edits first
  document.querySelectorAll('#'+cid+' .pl-table tbody tr').forEach((tr,i)=>{
    const pi=tr.querySelector('input[type=number]'),si=tr.querySelector('input[type=text]');
    if(pi&&_playlistItems[i])_playlistItems[i].priority=parseInt(pi.value)||0;
    if(si&&_playlistItems[i])_playlistItems[i].start=si.value||'00:00:00';
  });
  _playlistItems.push({path, start:'00:00:00', priority:0});
  _plSortItems(_playlistItems);
  _markDirty();
  _renderPLTable(cid);
}

function _mbSetSelection(item) {
  _mb.selected = item;
  const disp = document.getElementById('mb-selection-display');
  const btn  = document.getElementById('mb-confirm-btn');
  if (!item) {
    disp.textContent = 'Nothing selected';
    disp.title = '';
    btn.disabled = true;
    return;
  }
  const label = item.fullServerPath || item.path || '(root)';
  disp.textContent = label;
  disp.title = label;
  btn.disabled = false;
}

async function _mbLoad(path) {
  if (_mb.loading) return;
  _mb.loading = true;
  _mb.path = path;

  const listing   = document.getElementById('mb-listing');
  const sidebar   = document.getElementById('mb-sidebar');
  const statusBar = document.getElementById('mb-status-bar');

  // ── Serve from cache instantly, then revalidate in background ────────────
  const cached = _mbCacheGet(path);
  if (cached) {
    _mbRender(cached, path, listing, sidebar, statusBar);
    _mb.loading = false;
    // Silent background revalidation — update cache but don't re-render
    // unless the content actually changed (avoids flicker).
    fetch('/api/files?path=' + encodeURIComponent(path))
      .then(r => r.json())
      .then(fresh => { if (!fresh.error) _mbCacheSet(path, fresh); })
      .catch(() => {});
    return;
  }

  listing.innerHTML = '<div class="fm-empty"><div class="empty-icon" style="animation:spin 1s linear infinite;font-size:28px">⟳</div></div>';
  statusBar.textContent = 'Loading…';

  try {
    // Root dirs are fetched once and reused — no need to re-fetch on every navigation
    const needRoots = !path && !_mb._rootCache;
    const data = await fetch('/api/files?path=' + encodeURIComponent(path)).then(r => r.json());

    if (data.error) {
      listing.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>${esc(data.error)}</div></div>`;
      statusBar.textContent = 'Error loading folder';
      _mb.loading = false;
      return;
    }

    // Cache the result
    _mbCacheSet(path, data);

    // Cache root dirs on first successful load
    if (!path && !data.error) {
      _mb._rootCache = data.dirs || [];
      _mb.rootDirs   = _mb._rootCache;
    } else if (_mb._rootCache) {
      _mb.rootDirs = _mb._rootCache;
    }

    _mbRender(data, path, listing, sidebar, statusBar);
  } catch(e) {
    listing.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>Failed to load: ${esc(e.message)}</div></div>`;
    statusBar.textContent = 'Error';
  }
  _mb.loading = false;
}

function _mbRender(data, path, listing, sidebar, statusBar) {
    // ── Breadcrumb ────────────────────────────────────────────
    const bc = document.getElementById('mb-breadcrumb');
    bc.innerHTML = (data.breadcrumb || [{name:'Files', path:''}]).map((crumb, i, arr) => {
      const isLast = i === arr.length - 1;
      const sep = i > 0 ? '<span style="opacity:0.4;font-size:10px;padding:0 2px">›</span>' : '';
      return sep + `<span onclick="_mbLoad('${crumb.path}')"
               style="cursor:pointer;padding:2px 6px;border-radius:5px;color:${isLast?'var(--text)':'var(--text3)'};
                      font-weight:${isLast?'600':'400'}"
               onmouseover="if(!${isLast})this.style.color='var(--accent)'"
               onmouseout="this.style.color='${isLast?'var(--text)':'var(--text3)'}'"
               >${esc(crumb.name)}</span>`;
    }).join('');

    // ── Sidebar (root dirs) ───────────────────────────────────
    const rootDirs = _mb.rootDirs.length ? _mb.rootDirs : (data.dirs || []);
    sidebar.innerHTML =
      `<div onclick="_mbLoad('')"
            style="padding:9px 14px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:12px;
                   border-bottom:1px solid var(--border);transition:background 0.12s;
                   ${!path ? 'background:rgba(184,115,51,0.09);border-left:2px solid var(--accent);padding-left:12px;color:var(--accent)' : 'color:var(--text2)'}"
            onmouseover="this.style.background='var(--bg3)'"
            onmouseout="this.style.background='${!path?'rgba(184,115,51,0.09)':''}'"
            title="Root directory">
         <span style="opacity:0.65">📁</span> ${(data.breadcrumb && data.breadcrumb[0]) ? esc(data.breadcrumb[0].name) : 'Files'}
       </div>` +
      rootDirs.map(d => {
        const isActive = path === d.path || path.startsWith(d.path + '/');
        return `<div onclick="_mbLoad('${d.path}')"
                     style="padding:9px 14px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:12px;
                            border-bottom:1px solid var(--border);transition:background 0.12s;
                            ${isActive ? 'background:rgba(184,115,51,0.09);border-left:2px solid var(--accent);padding-left:12px;color:var(--accent)' : 'color:var(--text2)'}"
                     onmouseover="this.style.background='var(--bg3)'"
                     onmouseout="this.style.background='${isActive?'rgba(184,115,51,0.09)':''}'"
                     title="${esc(d.path)}">
               <span style="opacity:0.65">📂</span> ${esc(d.name)}
             </div>`;
      }).join('');

    // ── Main listing ──────────────────────────────────────────
    const rows = [];
    const isFolderMode = _mb.mode === 'folder';

    if (isFolderMode) {
      rows.push(`
        <div onclick="_mbSelectRow(this, {path:'${esc(path)}', isDir:true})"
             ondblclick="_mbSelectRow(this,{path:'${esc(path)}',isDir:true});mbConfirm()"
             style="display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--border);
                    cursor:pointer;font-size:12px;background:rgba(184,115,51,0.06)"
             title="Select current folder: ${esc(path||'Media root')}">
          <span style="font-size:15px">📂</span>
          <span style="flex:1;font-weight:600;color:var(--accent)">
            <i class="fa fa-check-circle" style="margin-right:5px;opacity:0.7"></i>
            Use this folder: <code style="font-size:11px;font-family:var(--font-mono)">${esc(path || '(root)')}</code>
          </span>
        </div>`);
    }

    (data.dirs || []).forEach(d => {
      const isSelectable = isFolderMode;
      rows.push(`
        <div class="mb-row"
             onclick="${isSelectable
               ? `_mbSelectRow(this,{path:'${esc(d.path)}',isDir:true})`
               : `_mbLoad('${esc(d.path)}')`}"
             ondblclick="_mbLoad('${esc(d.path)}')"
             style="display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--border);
                    cursor:pointer;font-size:12px;transition:background 0.1s"
             onmouseover="this.style.background='rgba(184,115,51,0.04)'"
             onmouseout="this.style.background=''"
             title="${isSelectable ? 'Click to select · Double-click to navigate into' : 'Double-click to navigate into'}: ${esc(d.path)}">
          <span style="font-size:15px">📁</span>
          <span style="flex:1;color:var(--text);font-weight:500">${esc(d.name)}</span>
          <button onclick="event.stopPropagation();_mbLoad('${esc(d.path)}')"
                  style="background:none;border:1px solid var(--border);color:var(--text3);cursor:pointer;
                         font-size:10px;padding:2px 8px;border-radius:5px;transition:all 0.15s"
                  onmouseover="this.style.color='var(--accent)';this.style.borderColor='var(--accent)'"
                  onmouseout="this.style.color='var(--text3)';this.style.borderColor='var(--border)'"
                  title="Open this folder">Open →</button>
        </div>`);
    });

    (data.files || []).forEach(f => {
      const isMedia = f.supported;
      const ico = (f.ext||'').match(/\.(mp3|aac|flac|wav|ogg|m4a)$/i) ? '🎵' : '🎬';
      if (isFolderMode) {
        rows.push(`
          <div style="display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--border);
                      font-size:12px;opacity:0.35;cursor:default" title="${esc(f.full_path||f.path)}">
            <span style="font-size:14px">${ico}</span>
            <span style="flex:1;color:var(--text2)">${esc(f.name)}</span>
            <span style="font-size:11px;color:var(--text3);font-family:var(--font-mono)">${esc(f.size)}</span>
          </div>`);
      } else {
        const opacity = isMedia ? '1' : '0.45';
        rows.push(`
          <div class="mb-row"
               onclick="${isMedia ? `_mbSelectRow(this,{path:'${esc(f.path)}',isDir:false})` : ''}"
               ondblclick="${isMedia ? `_mbSelectRow(this,{path:'${esc(f.path)}',isDir:false});mbConfirm()` : ''}"
               style="display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--border);
                      font-size:12px;opacity:${opacity};transition:background 0.1s;
                      cursor:${isMedia?'pointer':'default'}"
               ${isMedia ? `onmouseover="this.style.background='rgba(184,115,51,0.05)'" onmouseout="this.style.background=''"` : ''}
               title="${isMedia ? 'Click to select · Double-click to add' : 'Unsupported format'}: ${esc(f.path)}">
            <span style="font-size:14px">${ico}</span>
            <span style="flex:1;color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.name)}</span>
            ${f.duration ? `<span style="font-size:10px;color:var(--text3);font-family:var(--font-mono);flex-shrink:0">${esc(f.duration)}</span>` : ''}
            <span style="font-size:11px;color:var(--text3);font-family:var(--font-mono);flex-shrink:0">${esc(f.size)}</span>
            ${!isMedia ? '<span style="font-size:10px;color:var(--text3);flex-shrink:0">unsupported</span>' : ''}
          </div>`);
      }
    });

    if (!rows.length || (isFolderMode && rows.length === 1)) {
      rows.push('<div class="fm-empty"><div class="empty-icon">📂</div><div>This folder is empty.</div></div>');
    }

    listing.innerHTML = rows.join('');

    if (_mb.selected) {
      listing.querySelectorAll('.mb-row').forEach(row => {
        if (row.title && row.title.includes(_mb.selected.path)) {
          row.style.background = 'rgba(184,115,51,0.10)';
          row.style.outline = '1px solid var(--accent)';
        }
      });
    }

    const nDirs = (data.dirs||[]).length;
    const nFiles = (data.files||[]).length;
    const nMediaFiles = (data.files||[]).filter(f=>f.supported).length;
    statusBar.innerHTML = isFolderMode
      ? `<b>${nDirs}</b> subfolder${nDirs!==1?'s':''} &ensp;·&ensp; <b>${nFiles}</b> file${nFiles!==1?'s':''}`
      : `<b>${nDirs}</b> subfolder${nDirs!==1?'s':''} &ensp;·&ensp; <b>${nMediaFiles}</b> supported media file${nMediaFiles!==1?'s':''} of ${nFiles}`;
}

function _mbSelectRow(rowEl, item) {
  // Clear previous highlight
  document.querySelectorAll('#mb-listing .mb-row').forEach(r => {
    r.style.background = '';
    r.style.outline = '';
  });
  // Highlight selected
  rowEl.style.background = 'rgba(184,115,51,0.12)';
  rowEl.style.outline = '1px solid var(--accent)';
  _mbSetSelection(item);
}

// ═══════════════════════════════════
// SETTINGS
// ═══════════════════════════════════

// ═══════════════════════════════════════════════════════
// COMPLIANCE ALERT BANNER (v2)
// ═══════════════════════════════════════════════════════

let _compAlertsEnabled = localStorage.getItem('hc_comp_alerts') !== 'false';
const _compAlertActive = {};

function _updateComplianceAlerts(streams) {
  if (!_compAlertsEnabled) {
    document.querySelectorAll('.compliance-alert-banner').forEach(el => el.remove());
    Object.keys(_compAlertActive).forEach(k => delete _compAlertActive[k]);
    return;
  }
  const seenNames = new Set();
  for (const s of streams) {
    if (!s.compliance_enabled) continue;
    if (!s.compliance_alert) continue;
    if (s.compliance_alert_enabled === false) continue;
    seenNames.add(s.name);
    if (_compAlertActive[s.name]) {
      const el = document.getElementById('cab-comp-' + s.name.replace(/[^a-z0-9]/gi,'_'));
      if (el) el.querySelector('.cab-body').textContent = s.compliance_alert;
      continue;
    }
    _compAlertActive[s.name] = true;
    const safeId = 'cab-comp-' + s.name.replace(/[^a-z0-9]/gi,'_');
    const div = document.createElement('div');
    div.className = 'compliance-alert-banner';
    div.id = safeId;
    // Offset each banner vertically so multiple streams don't overlap
    const offset = Object.keys(_compAlertActive).length - 1;
    div.style.top = (72 + offset * 170) + 'px';
    div.innerHTML =
      '<div class="cab-hdr"><span class="cab-dot"></span>Compliance Error</div>' +
      '<div class="cab-body">' + esc(s.compliance_alert) + '</div>' +
      '<div class="cab-stream">Stream: ' + esc(s.name) + '</div>' +
      '<button class="cab-dismiss" onclick="_dismissCompAlert(\'' +
        s.name.replace(/\\/g,'\\\\').replace(/'/g,"\\'") + '\')">Dismiss ×</button>';
    document.body.appendChild(div);
  }
  for (const name of Object.keys(_compAlertActive)) {
    if (!seenNames.has(name)) {
      const safeId = 'cab-comp-' + name.replace(/[^a-z0-9]/gi,'_');
      const el = document.getElementById(safeId);
      if (el) { el.style.opacity='0'; setTimeout(()=>el.remove(),300); }
      delete _compAlertActive[name];
    }
  }
}

function _dismissCompAlert(streamName) {
  const safeId = 'cab-comp-' + streamName.replace(/[^a-z0-9]/gi,'_');
  const el = document.getElementById(safeId);
  if (el) { el.style.transition='opacity 0.3s'; el.style.opacity='0'; setTimeout(()=>el.remove(),300); }
  delete _compAlertActive[streamName];
  // Allow re-display after 60 s if still unresolved
  setTimeout(() => { /* passive — next loadStreams tick re-evaluates */ }, 60000);
}

function toggleComplianceAlerts(checked) {
  _compAlertsEnabled = checked;
  localStorage.setItem('hc_comp_alerts', checked ? 'true' : 'false');
  if (!checked) {
    document.querySelectorAll('.compliance-alert-banner').forEach(b => b.remove());
    Object.keys(_compAlertActive).forEach(k => delete _compAlertActive[k]);
  }
}

const _settingsDefaults={autoref:true,autoscroll:true,compact:false,showrtsp:true,notifStart:true,notifErr:true,notifEvent:false};
const _settings=Object.assign({},_settingsDefaults);
// Restore persisted settings
try{
  const _stored=JSON.parse(localStorage.getItem('hc-settings')||'{}');
  Object.assign(_settings,_stored);
  // Sync toggle UI after defaults are applied
  Object.entries(_settings).forEach(([k,v])=>{
    const el=document.getElementById('st-'+k.toLowerCase().replace(/([A-Z])/g,'-$1').toLowerCase());
    if(el&&el.classList.contains('toggle')) el.classList.toggle('on',!!v);
  });
}catch(_){}

// ═══════════════════════════════════
// STREAM SOURCE SELECTOR
// ═══════════════════════════════════
let _ssMode = 'folder';   // 'folder' | 'files'
let _ssFiles = [];         // selected files in files-mode

// Populate stream dropdown when Settings tab opens
async function ssInit() {
  const sel = document.getElementById('ss-stream');
  if (!sel) return;
  try {
    const streams = await fetch('/api/streams').then(r => r.json());
    sel.innerHTML = '<option value="">— select a stream —</option>' +
      streams.map(s => `<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
  } catch(e) {
    sel.innerHTML = '<option value="">Failed to load streams</option>';
  }
  await ssRefreshFolders();
  await ssRefreshFiles();
}

function ssSwitchMode(mode) {
  _ssMode = mode;
  document.getElementById('ss-panel-folder').style.display = mode === 'folder' ? '' : 'none';
  document.getElementById('ss-panel-files').style.display  = mode === 'files'  ? '' : 'none';
  document.getElementById('ss-tab-folder').classList.toggle('active', mode === 'folder');
  document.getElementById('ss-tab-files').classList.toggle('active',  mode === 'files');
}

// Load current source for the selected stream into the UI
async function ssLoadSource() {
  const name = document.getElementById('ss-stream').value;
  if (!name) return;
  document.getElementById('ss-status').textContent = '';
  try {
    const cfgs = await fetch('/api/streams_config').then(r => r.json());
    const cfg = cfgs.find(c => c.name === name);
    if (!cfg) return;
    if (cfg.folder_source) {
      ssSwitchMode('folder');
      // Try to select the matching folder option
      const rel = cfg.folder_source.replace(/\\/g, '/');
      const folderSel = document.getElementById('ss-folder-select');
      // find option with value matching the tail of the path
      const opt = Array.from(folderSel.options).find(o => rel.endsWith(o.value) || o.value === rel);
      if (opt) folderSel.value = opt.value;
      document.getElementById('ss-shuffle').checked = !!cfg.shuffle;
    } else if (cfg.files) {
      ssSwitchMode('files');
      _ssFiles = cfg.files.split(/[;\n]+/).map(s => s.trim()).filter(Boolean);
      ssRenderFileList();
      document.getElementById('ss-files-shuffle').checked = !!cfg.shuffle;
    }
  } catch(e) {}
}

// Populate folder dropdown from /api/files
async function ssRefreshFolders() {
  const sel = document.getElementById('ss-folder-select');
  if (!sel) return;
  try {
    const root = await fetch('/api/files?path=').then(r => r.json());
    const dirs = root.dirs || [];
    const _rootName = (root.breadcrumb && root.breadcrumb[0]) ? root.breadcrumb[0].name : 'Root';
    sel.innerHTML = `<option value="">— ${_rootName} (all files) —</option>` +
      dirs.map(d => `<option value="${esc(d.path)}">${esc(d.name)}</option>`).join('');
  } catch(e) {
    sel.innerHTML = '<option value="">Failed to load folders</option>';
  }
}

// Populate file browser from /api/library
async function ssRefreshFiles() {
  const sel = document.getElementById('ss-file-browser');
  if (!sel) return;
  try {
    const lib = await fetch('/api/library').then(r => r.json());
    sel.innerHTML = '<option value="">— choose a file —</option>' +
      lib.map(f => `<option value="${esc(f.path)}" title="${esc(f.duration||'')} · ${esc(f.size||'')}">${esc(f.path)}</option>`).join('');
  } catch(e) {
    sel.innerHTML = '<option value="">Failed to load library</option>';
  }
}

function ssAddFile() {
  const sel = document.getElementById('ss-file-browser');
  const val = sel.value;
  if (!val) { toast('Pick a file first', 'err'); return; }
  if (_ssFiles.includes(val)) { toast('Already added', 'info'); return; }
  _ssFiles.push(val);
  ssRenderFileList();
}

function ssRemoveFile(idx) {
  _ssFiles.splice(idx, 1);
  ssRenderFileList();
}

function ssRenderFileList() {
  const wrap = document.getElementById('ss-file-list');
  const empty = document.getElementById('ss-file-empty');
  if (!_ssFiles.length) {
    wrap.innerHTML = '';
    wrap.appendChild(empty);
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  wrap.innerHTML = _ssFiles.map((f, i) => `
    <div style="display:flex;align-items:center;gap:8px;padding:7px 12px;border-bottom:1px solid var(--border);font-size:12px">
      <span style="flex:1;font-family:var(--font-mono);color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
            title="${esc(f)}">${esc(f)}</span>
      <button class="fm-action-btn del" onclick="ssRemoveFile(${i})" title="Remove from list">✕</button>
    </div>`).join('') + `<div id="ss-file-empty" style="display:none;padding:20px;text-align:center;color:var(--text3);font-size:12px">No files selected yet.</div>`;
}

function ssClear() {
  _ssFiles = [];
  ssRenderFileList();
  document.getElementById('ss-folder-select').value = '';
  document.getElementById('ss-shuffle').checked = false;
  document.getElementById('ss-files-shuffle').checked = false;
  document.getElementById('ss-stream').value = '';
  document.getElementById('ss-status').textContent = '';
}

async function ssApply() {
  const name = document.getElementById('ss-stream').value;
  if (!name) { toast('Select a stream first', 'err'); return; }
  const st = document.getElementById('ss-status');

  let payload;
  if (_ssMode === 'folder') {
    const folder = document.getElementById('ss-folder-select').value;
    payload = {
      name,
      folder_source: folder || null,
      files: '',
      shuffle: document.getElementById('ss-shuffle').checked,
    };
  } else {
    if (!_ssFiles.length) { toast('Add at least one file', 'err'); return; }
    payload = {
      name,
      folder_source: null,
      files: _ssFiles.join('\n'),
      shuffle: document.getElementById('ss-files-shuffle').checked,
    };
  }

  st.textContent = 'Saving…'; st.style.color = 'var(--yellow)';
  try {
    const r = await api('update_config', payload);
    if (r?.ok) {
      st.textContent = '✓ Saved — restarting stream…'; st.style.color = 'var(--green)';
      toast('Stream source updated', 'ok');
      // Restart stream so it picks up the new source
      setTimeout(() => api('restart', {name}), 600);
    } else {
      st.textContent = '✕ ' + (r?.msg || 'Error'); st.style.color = 'var(--red)';
      toast(r?.msg || 'Failed to save', 'err');
    }
  } catch(e) {
    st.textContent = '✕ Request failed'; st.style.color = 'var(--red)';
    toast('Save failed', 'err');
  }
}

function toggleSetting(key,el){
  _settings[key]=!_settings[key];
  el.classList.toggle('on',_settings[key]);
  try{localStorage.setItem('hc-settings',JSON.stringify(_settings));}catch(_){}
  applySettings();
}

function applySettings(){
  // Autoref toggle → restart/stop the poll timer
  clearInterval(_autoTimer);
  if(_settings.autoref){
    const v=parseInt(document.getElementById('st-poll-interval')?.value)||2500;
    _autoTimer=setInterval(loadStreams,v);
  }
  // sync compliance alerts toggle
  const caEl=document.getElementById('st-comp-alerts');
  if(caEl)caEl.checked=_compAlertsEnabled;
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
  try{localStorage.setItem('hc-poll-interval',v);}catch(_){}
  clearInterval(_autoTimer);
  if(_settings.autoref) _autoTimer=setInterval(loadStreams,v);
}

// ═══════════════════════════════════
// MAIL CONFIG
// ═══════════════════════════════════
// MAIL ALERTS  (Outlook / Microsoft Graph — client credentials)
// ═══════════════════════════════════

async function loadMailConfig(){
  try{
    const d=await fetch('/api/mail_config').then(r=>r.json());
    if(d.error){document.getElementById('ml-status').textContent='⚠ '+d.error;return;}

    document.getElementById('ml-tenant-id').value=d.tenant_id||'';
    document.getElementById('ml-client-id').value=d.client_id||'';
    document.getElementById('ml-client-secret').value=d.client_secret||'';
    document.getElementById('ml-from').value=d.from_addr||'';
    document.getElementById('ml-to').value=(d.to_addrs||[]).join(', ');
    document.getElementById('ml-cooldown').value=d.cooldown_secs??300;
    document.getElementById('ml-enabled').checked=!!d.enabled;
    document.getElementById('ml-on-error').checked=d.on_error!==false;
    document.getElementById('ml-on-stop').checked=d.on_stop!==false;

    const st=document.getElementById('ml-status');
    st.textContent='✓ Config loaded from mail_config.hcf';
    st.style.color='var(--green)';
  }catch(e){
    const st=document.getElementById('ml-status');
    st.textContent='Failed to load config';
    st.style.color='var(--red)';
  }
}

async function saveMailConfig(){
  const toRaw=document.getElementById('ml-to').value;
  const toList=toRaw.split(',').map(s=>s.trim()).filter(Boolean);
  if(!toList.length){toast('Enter at least one To address','err');return;}
  const payload={
    enabled:document.getElementById('ml-enabled').checked,
    tenant_id:document.getElementById('ml-tenant-id').value.trim(),
    client_id:document.getElementById('ml-client-id').value.trim(),
    client_secret:document.getElementById('ml-client-secret').value,
    from_addr:document.getElementById('ml-from').value.trim(),
    to_addrs:toList,
    on_error:document.getElementById('ml-on-error').checked,
    on_stop:document.getElementById('ml-on-stop').checked,
    cooldown_secs:parseInt(document.getElementById('ml-cooldown').value)||300,
  };
  try{
    const r=await fetch('/api/action',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:'save_mail_config',...payload})
    });
    const j=await r.json();
    toast(j.msg||(j.ok?'Saved':'Error'),j.ok?'ok':'err');
    const st=document.getElementById('ml-status');
    st.textContent=j.ok?'✓ mail_config.hcf saved':'✕ '+j.msg;
    st.style.color=j.ok?'var(--green)':'var(--red)';
  }catch(e){toast('Save failed','err');}
}

async function testMailAlert(){
  const to=document.getElementById('ml-test-to').value.trim()||null;
  const st=document.getElementById('ml-status');
  st.textContent='Sending test email…';st.style.color='var(--yellow)';
  try{
    const r=await fetch('/api/action',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(Object.assign({action:'test_mail_alert'},to?{to_addr:to}:{}))
    });
    const j=await r.json();
    toast(j.msg||(j.ok?'Test sent':'Failed'),j.ok?'ok':'err');
    st.textContent=j.ok?'✓ Test email sent successfully':'✕ '+j.msg;
    st.style.color=j.ok?'var(--green)':'var(--red)';
  }catch(e){toast('Test failed','err');st.textContent='Request failed';st.style.color='var(--red)';}
}

// ═══════════════════════════════════
// ACCENT COLOR
// ═══════════════════════════════════

function _hexToRgb(hex){
  const r=parseInt(hex.slice(1,3),16);
  const g=parseInt(hex.slice(3,5),16);
  const b=parseInt(hex.slice(5,7),16);
  return {r,g,b};
}
function _lighten(hex, amount){
  const {r,g,b}=_hexToRgb(hex);
  const lr=Math.min(255,Math.round(r+(255-r)*amount));
  const lg=Math.min(255,Math.round(g+(255-g)*amount));
  const lb=Math.min(255,Math.round(b+(255-b)*amount));
  return '#'+[lr,lg,lb].map(v=>v.toString(16).padStart(2,'0')).join('');
}

function accentPreview(hex){
  if(!/^#[0-9a-fA-F]{6}$/.test(hex)) return;
  const light=_lighten(hex,0.15);
  const r=document.documentElement;
  r.style.setProperty('--accent',hex);
  r.style.setProperty('--accent-light',light);
  r.style.setProperty('--accent-gradient',`linear-gradient(135deg,${hex} 0%,${light} 50%,${_lighten(hex,0.1)} 100%)`);
  r.style.setProperty('--accent-gradient-hover',`linear-gradient(135deg,${_lighten(hex,0.1)} 0%,${_lighten(hex,0.22)} 50%,${light} 100%)`);
  const picker=document.getElementById('accent-color-picker');
  const hexIn=document.getElementById('accent-color-hex');
  if(picker) picker.value=hex;
  if(hexIn) hexIn.value=hex.toUpperCase();
}

function setAccentSwatch(hex){
  accentPreview(hex);
}

async function saveAccentColor(){
  const hex=(document.getElementById('accent-color-hex')?.value||'').trim().toUpperCase();
  if(!/^#[0-9a-fA-F]{6}$/.test(hex)){toast('Enter a valid hex colour (e.g. #b87333)','err');return;}
  const st=document.getElementById('accent-status');
  st.textContent='Saving…';st.style.color='var(--yellow)';
  try{
    const r=await fetch('/api/settings',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({accent_color:hex})
    });
    const j=await r.json();
    if(j.error) throw new Error(j.error);
    accentPreview(hex);
    st.textContent='✓ Saved — '+hex;st.style.color='var(--green)';
    toast('Accent colour saved','ok');
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Save failed','err');
  }
}

// Apply saved accent colour on page load
(async function initAccentColor(){
  try{
    const s=await fetch('/api/settings').then(r=>r.json());
    const hex=(s.accent_color||'#b87333').trim();
    if(/^#[0-9a-fA-F]{6}$/.test(hex)){
      accentPreview(hex);
      const picker=document.getElementById('accent-color-picker');
      const hexIn=document.getElementById('accent-color-hex');
      if(picker) picker.value=hex;
      if(hexIn) hexIn.value=hex.toUpperCase();
    }
  }catch(e){}
})();

// ═══════════════════════════════════
// BRANDING (name + logo)
// ═══════════════════════════════════

/** Apply brand_name and brand_logo from a settings object to the live UI. */
function applyBranding(s){
  const name = (s.brand_name||'').trim();
  const logo = (s.brand_logo||'').trim();

  // Topbar name
  const nameEl = document.getElementById('topbar-app-name');
  if(nameEl) nameEl.textContent = name || nameEl.dataset.default || nameEl.textContent;
  // Store the server default on first call so clearing restores it
  if(nameEl && !nameEl.dataset.default) nameEl.dataset.default = nameEl.textContent;
  if(nameEl) nameEl.textContent = name || nameEl.dataset.default;

  // Topbar logo
  const img  = document.getElementById('logo-img');
  const lttr = document.getElementById('logo-letter');
  if(img){
    if(logo){
      img.src = logo;
      // onload/onerror handlers on the element already toggle visibility
    } else {
      img.src = '/resources/logo.png'; // revert to server asset (may 404 → shows initials)
    }
  }

  // Footer name
  const ftName = document.getElementById('ft-brand-name');
  if(ftName) ftName.textContent = name || 'HydraCast';

  // Footer logo
  const ftImg = document.getElementById('ft-brand-logo');
  if(ftImg){
    if(logo){ ftImg.src = logo; ftImg.style.display = ''; }
    else { ftImg.src = 'https://raw.githubusercontent.com/rhshourav/HydraCast/refs/heads/main/resources/HydraCast.svg'; }
  }

  // Page title
  if(name) document.title = name;

  // Update settings card preview
  _brandLogoSetPreview(logo);
}

function _brandLogoSetPreview(src){
  const wrap = document.getElementById('brand-logo-preview');
  if(!wrap) return;
  if(src){
    wrap.innerHTML = `<img src="${src}" alt="logo"
      style="width:100%;height:100%;object-fit:cover;border-radius:7px"
      onerror="this.parentElement.innerHTML='<span style=\'font-size:9px;color:var(--red)\'>✕ Bad URL</span>'">`;
  } else {
    wrap.innerHTML = '<span style="font-size:9px;color:var(--text3)">HC</span>';
  }
}

function brandLogoUrlPreview(val){
  _brandLogoSetPreview(val.trim());
  document.getElementById('brand-logo-size').textContent = '';
}

function brandLogoFileChosen(input){
  const file = input.files[0];
  if(!file) return;
  if(file.size > 512*1024){
    document.getElementById('brand-logo-size').textContent =
      '⚠ File is '+Math.round(file.size/1024)+' KB — consider using a smaller image (< 512 KB)';
    document.getElementById('brand-logo-size').style.color = 'var(--yellow)';
  } else {
    document.getElementById('brand-logo-size').textContent =
      file.name+' ('+Math.round(file.size/1024)+' KB)';
    document.getElementById('brand-logo-size').style.color = 'var(--text3)';
  }
  const reader = new FileReader();
  reader.onload = e => {
    const dataUrl = e.target.result;
    const urlInput = document.getElementById('brand-logo-url');
    if(urlInput) urlInput.value = '';       // clear URL field — file takes precedence
    _brandLogoSetPreview(dataUrl);
    // Stash temporarily on the preview so saveBrandingSettings() can read it
    const wrap = document.getElementById('brand-logo-preview');
    if(wrap) wrap.dataset.pending = dataUrl;
  };
  reader.readAsDataURL(file);
}

function clearBrandLogo(){
  const urlInput = document.getElementById('brand-logo-url');
  if(urlInput) urlInput.value = '';
  const wrap = document.getElementById('brand-logo-preview');
  if(wrap){ wrap.dataset.pending = ''; wrap.innerHTML = '<span style="font-size:9px;color:var(--text3)">HC</span>'; }
  document.getElementById('brand-logo-size').textContent = '';
  const fileInput = document.getElementById('brand-logo-file');
  if(fileInput) fileInput.value = '';
}

async function loadBrandingSettings(){
  try{
    const s = await fetch('/api/settings').then(r=>r.json());
    const nameInput = document.getElementById('brand-name');
    const urlInput  = document.getElementById('brand-logo-url');
    const wrap      = document.getElementById('brand-logo-preview');
    if(nameInput) nameInput.value = s.brand_name||'';
    const logo = s.brand_logo||'';
    if(urlInput) urlInput.value = logo.startsWith('data:') ? '' : logo;
    if(wrap) wrap.dataset.pending = '';
    _brandLogoSetPreview(logo);
  }catch(e){}
}

async function saveBrandingSettings(){
  const name = (document.getElementById('brand-name')?.value||'').trim();
  const wrap  = document.getElementById('brand-logo-preview');
  // Pending data-URL from file upload wins; otherwise use the URL text field
  const pendingDataUrl = wrap?.dataset.pending||'';
  const urlFieldVal    = (document.getElementById('brand-logo-url')?.value||'').trim();
  const logo = pendingDataUrl || urlFieldVal;

  const st = document.getElementById('brand-status');
  st.textContent='Saving…';st.style.color='var(--yellow)';
  try{
    const r = await fetch('/api/settings',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ brand_name:name, brand_logo:logo })
    });
    const j = await r.json();
    if(j.error) throw new Error(j.error);
    applyBranding({ brand_name:name, brand_logo:logo });
    if(wrap) wrap.dataset.pending = '';  // clear pending after successful save
    st.textContent='✓ Saved';st.style.color='var(--green)';
    toast('Branding saved','ok');
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Save failed','err');
  }
}

// Apply saved branding on page load
(async function initBranding(){
  try{
    const s = await fetch('/api/settings').then(r=>r.json());
    applyBranding(s);
  }catch(e){}
})();

// ═══════════════════════════════════
// MEDIA ROOT DIRECTORIES
// ═══════════════════════════════════

// Tracks the current roots array in-memory so UI renders without extra round-trips
let _mrRoots = [];
let _mrDefault = '';

async function loadMediaRoots(){
  try{
    const r = await fetch('/api/media_roots');
    if(!r.ok) throw new Error('Server error '+r.status);
    const d = await r.json();
    _mrRoots   = d.roots   || [];
    _mrDefault = d.default || '';
    const el = document.getElementById('mr-default-path');
    if(el) el.textContent = _mrDefault || 'media/';
    _renderMediaRoots();
  }catch(e){
    _mrStatus('Failed to load roots: '+e.message, 'err');
  }
}

function _renderMediaRoots(){
  const container = document.getElementById('mr-list');
  if(!container) return;
  container.innerHTML = '';

  _mrRoots.forEach((rootPath, idx) => {
    const isDefault = (rootPath === _mrDefault);
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:7px 10px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);font-size:12px';

    // Status dot — green if default, accent for extra roots
    const dot = document.createElement('span');
    dot.style.cssText = `width:7px;height:7px;border-radius:50%;flex-shrink:0;background:${isDefault ? 'var(--green)' : 'var(--accent)'}`;
    row.appendChild(dot);

    // Path text
    const pathEl = document.createElement('code');
    pathEl.style.cssText = 'flex:1;color:var(--text);font-family:var(--font-mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
    pathEl.title = rootPath;
    pathEl.textContent = rootPath;
    row.appendChild(pathEl);

    // Badge
    const badge = document.createElement('span');
    badge.style.cssText = `font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:2px 7px;border-radius:10px;flex-shrink:0;${isDefault ? 'background:rgba(100,200,100,0.12);color:var(--green)' : 'background:rgba(184,115,51,0.12);color:var(--accent)'}`;
    badge.textContent = isDefault ? 'default' : 'extra';
    row.appendChild(badge);

    // Remove button — disabled for default root
    if(!isDefault){
      const btn = document.createElement('button');
      btn.className = 'btn r';
      btn.style.cssText = 'padding:3px 10px;font-size:11px;flex-shrink:0';
      btn.title = 'Remove this extra media root';
      btn.textContent = '✕ Remove';
      btn.onclick = () => removeMediaRoot(rootPath);
      row.appendChild(btn);
    } else {
      const lk = document.createElement('span');
      lk.style.cssText = 'font-size:11px;color:var(--text3);flex-shrink:0';
      lk.textContent = '🔒 locked';
      row.appendChild(lk);
    }

    container.appendChild(row);
  });

  if(_mrRoots.length === 0){
    container.innerHTML = '<div style="font-size:12px;color:var(--text3);padding:8px 0">No roots loaded yet — click ↻ Load.</div>';
  }
}

async function addMediaRoot(){
  const input = document.getElementById('mr-new-path');
  const path  = (input?.value || '').trim();
  if(!path){ _mrStatus('Enter an absolute path first.', 'warn'); return; }

  _mrStatus('Adding…', 'busy');
  try{
    // Build the full new list: existing extras + new path
    const extras = _mrRoots.filter(r => r !== _mrDefault);
    if(extras.includes(path)){
      _mrStatus('⚠ That path is already in the list.', 'warn');
      return;
    }
    const newRoots = [...extras, path];
    await _saveRootsToServer(newRoots);
    if(input) input.value = '';
  }catch(e){
    _mrStatus('✕ '+e.message, 'err');
  }
}

async function removeMediaRoot(path){
  if(!confirm(`Remove media root?\n\n${path}\n\nThe directory itself will not be deleted.`)) return;
  _mrStatus('Removing…', 'busy');
  try{
    const extras = _mrRoots.filter(r => r !== _mrDefault && r !== path);
    await _saveRootsToServer(extras);
  }catch(e){
    _mrStatus('✕ '+e.message, 'err');
  }
}

async function _saveRootsToServer(extraRoots){
  // Always include the default root so the server deduplicates cleanly
  const roots = [_mrDefault, ...extraRoots].filter(Boolean);
  const r = await fetch('/api/action', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({action:'save_media_roots', roots})
  });
  const d = await r.json().catch(() => ({}));
  if(!d.ok) throw new Error(d.msg || 'Server error');

  _mrRoots = d.roots || roots;
  _renderMediaRoots();
  const warnings = (d.warnings || []).join(' · ');
  const msg = d.msg + (warnings ? ' ⚠ '+warnings : '');
  _mrStatus('✓ '+msg, 'ok');
  toast(d.msg || 'Media roots saved', 'ok');
}

function _mrStatus(msg, type){
  const el = document.getElementById('mr-status');
  if(!el) return;
  el.textContent = msg;
  el.style.color = type==='ok' ? 'var(--green)' : type==='err' ? 'var(--red)' : type==='warn' ? 'var(--yellow)' : 'var(--text3)';
}


// ═══════════════════════════════════
// BACKUP & RESTORE
// ═══════════════════════════════════
async function downloadBackup(){
  const st=document.getElementById('bk-status');
  st.textContent='Preparing backup…';st.style.color='var(--yellow)';
  try{
    const include={
      streams:      document.getElementById('bk-streams')?.checked!==false,
      events:       document.getElementById('bk-events')?.checked!==false,
      mail:         document.getElementById('bk-mail')?.checked!==false,
      resume:       document.getElementById('bk-resume')?.checked!==false,
      app_settings: document.getElementById('bk-app-settings')?.checked!==false,
      media_roots:  document.getElementById('bk-media-roots')?.checked!==false,
    };
    const r=await fetch('/api/backup',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(include)
    });
    if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.msg||`Server error ${r.status}`);}
    const blob=await r.blob();
    // Warn if the downloaded blob is suspiciously small (likely an error body)
    if(blob.size<20){throw new Error('Server returned an empty backup — check server logs');}
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
    const included=Object.entries(include).filter(([,v])=>v).map(([k])=>k).join(', ');
    const sizeKB=Math.round(blob.size/1024);
    st.textContent=`✓ Backup downloaded — ${included} (${sizeKB} KB)`;st.style.color='var(--green)';
    toast('Backup downloaded','ok');
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Backup failed: '+e.message,'err');
  }
}

// Maximum .hc file size we will parse client-side (4 MB matches server POST limit)
const _HC_MAX_BYTES = 4*1024*1024;

async function doRestore(file){
  if(!file)return;
  // Reset file input so re-selecting same file still triggers onchange
  const fileInput=document.getElementById('restore-file');
  if(fileInput) fileInput.value='';

  if(!file.name.endsWith('.hc')){toast('Must be a .hc backup file','err');return;}

  // Client-side size guard — server rejects bodies > 4 MB anyway
  if(file.size>_HC_MAX_BYTES){
    toast(`Backup file too large (${Math.round(file.size/1024)} KB > 4096 KB)`, 'err');
    return;
  }

  const st=document.getElementById('restore-status');
  const preview=document.getElementById('restore-preview');
  st.textContent='Reading file…';st.style.color='var(--yellow)';
  if(preview){preview.style.display='none';preview.innerHTML='';}

  try{
    const text=await file.text();
    let data;
    try{data=JSON.parse(text);}catch(_){throw new Error('Invalid .hc file — not valid JSON');}
    if(data.format!=='hydracast_backup'){throw new Error('Not a HydraCast backup file (missing format header)');}

    // ── Build section inventory (treat empty arrays/objects as present) ──────
    // Use 'format' key presence per-section, not truthiness, so an intentionally
    // empty streams:[] backup is still recognised and can wipe all streams.
    const sectionMap={
      streams:          {key:'streams',          label:'Streams',          present:'streams' in data},
      events:           {key:'events',            label:'Events',           present:'events' in data},
      mail_config:      {key:'mail_config',       label:'Mail config',      present:'mail_config' in data},
      resume_positions: {key:'resume_positions',  label:'Resume positions', present:'resume_positions' in data},
      app_settings:     {key:'app_settings',      label:'App settings',     present:'app_settings' in data},
      media_roots:      {key:'media_roots',       label:'Media roots',      present:'media_roots' in data},
    };
    const sections=Object.values(sectionMap).filter(s=>s.present).map(s=>s.label);
    if(sections.length===0){throw new Error('Backup file contains no restorable sections');}

    // ── Show file preview panel ───────────────────────────────────────────────
    const backupVer=data.version||'unknown';
    const backupDate=data.created? new Date(data.created).toLocaleString() : 'unknown';
    const sizeKB=Math.round(file.size/1024);

    // Gather per-section counts for the preview
    const counts={};
    if('streams' in data)          counts['Streams']=Array.isArray(data.streams)?`${data.streams.length} stream(s)`:'present';
    if('events' in data)           counts['Events']=Array.isArray(data.events)?`${data.events.length} event(s)`:'present';
    if('mail_config' in data)      counts['Mail config']='present (password excluded)';
    if('resume_positions' in data) counts['Resume positions']=typeof data.resume_positions==='object'?`${Object.keys(data.resume_positions).length} entry(ies)`:'present';
    if('app_settings' in data)     counts['App settings']='present';
    if('media_roots' in data)      counts['Media roots']=Array.isArray(data.media_roots)?`${data.media_roots.length} extra root(s)`:'present';

    // Version mismatch warning
    let verWarning='';
    const appVer=(typeof APP_VER!=='undefined')?APP_VER:null;
    if(appVer && backupVer!==appVer){
      verWarning=`<div style="color:var(--yellow);margin-top:4px">⚠ Backup version <b>${backupVer}</b> differs from running version <b>${appVer}</b> — review carefully before restoring.</div>`;
    }

    if(preview){
      const rows=Object.entries(counts).map(([k,v])=>`<tr><td style="color:var(--text3);padding-right:12px">${k}</td><td style="color:var(--text2)">${v}</td></tr>`).join('');
      preview.innerHTML=`
        <div style="font-weight:600;color:var(--text);margin-bottom:6px">📦 ${file.name} <span style="font-weight:400;color:var(--text3)">(${sizeKB} KB)</span></div>
        <div style="color:var(--text3)">Created: <span style="color:var(--text2)">${backupDate}</span> &nbsp;·&nbsp; App version: <span style="color:var(--text2)">${backupVer}</span></div>
        ${verWarning}
        <table style="margin-top:8px;border-collapse:collapse">${rows}</table>`;
      preview.style.display='block';
    }

    // ── Confirmation dialog with section detail ───────────────────────────────
    const confirmMsg=[
      `Restore from: ${file.name}`,
      `Created:      ${backupDate}`,
      `Version:      ${backupVer}`,
      ``,
      `Sections to restore:`,
      ...sections.map(s=>`  • ${s}`),
      ``,
      `All matching configuration will be replaced and streams will restart.`,
      ``,
      `Continue?`,
    ].join('\n');
    if(!confirm(confirmMsg))return;

    st.textContent=`Restoring: ${sections.join(', ')}…`;st.style.color='var(--yellow)';

    const r=await fetch('/api/restore',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    let j;
    try{j=await r.json();}catch(_){throw new Error(`Server returned non-JSON response (status ${r.status})`);}

    if(j.ok){
      const restored=(j.restored||[]).join(', ')||'(none)';
      const failed=(j.failed||[]);
      const warnPart=failed.length?`\n⚠ Warnings: ${failed.join('; ')}`:'' ;
      st.textContent=`✓ Restored: ${restored}${warnPart} — reloading in 3 s…`;
      st.style.color=failed.length?'var(--yellow)':'var(--green)';
      toast('Restore successful — restarting streams…','ok');

      // Reload UI state for every restored section
      const r_list=j.restored||[];
      if(r_list.includes('app_settings')){
        // Reload holiday settings and invalidate cached data
        if(typeof loadHolidaySettings==='function') loadHolidaySettings();
        if(typeof loadHolidays==='function'){
          if(typeof _hdLoaded!=='undefined') _hdLoaded=false;
          if(typeof _hdData!=='undefined')   _hdData=[];
          const lbl=document.getElementById('hd-next-label');
          if(lbl) lbl.textContent='Holidays';
          loadHolidays();
        }
      }
      // Always reload streams table and events after any restore
      setTimeout(()=>{
        if(typeof loadStreams==='function') loadStreams();
        if(r_list.includes('media_roots') && typeof loadMediaRoots==='function') loadMediaRoots();
      },3500);
    }else{
      throw new Error(j.msg||'Restore failed');
    }
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Restore failed: '+e.message,'err');
  }
}

// ═══════════════════════════════════
// HOLIDAY SETTINGS (Settings tab)
// ═══════════════════════════════════
async function loadHolidaySettings(){
  try{
    const s=await fetch('/api/settings').then(r=>r.json());
    const ci=document.getElementById('hol-country');
    const si=document.getElementById('hol-subdiv');
    if(ci) ci.value=s.holiday_country||'US';
    if(si) si.value=s.holiday_subdiv||'';
  }catch(e){}
}

async function saveHolidaySettings(){
  const country=(document.getElementById('hol-country')?.value||'').trim();
  const subdiv=(document.getElementById('hol-subdiv')?.value||'').trim()||null;
  const st=document.getElementById('hol-status');
  if(!country){
    st.textContent='✕ Select a country';st.style.color='var(--red)';return;
  }
  st.textContent='Saving…';st.style.color='var(--yellow)';
  try{
    const r=await fetch('/api/settings',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({holiday_country:country,holiday_subdiv:subdiv})
    });
    const j=await r.json();
    if(j.error) throw new Error(j.error);
    st.textContent='✓ Saved — '+country+(subdiv?' / '+subdiv:'');
    st.style.color='var(--green)';
    toast('Holiday settings saved','ok');
    // Invalidate holidays cache so pill + popup update to the new country
    _hdLoaded=false;
    _hdData=[];
    document.getElementById('hd-next-label').textContent='Holidays';
    loadHolidays();
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Save failed: '+e.message,'err');
  }
}

// ─── Reset ALL server-persisted settings to factory defaults ────────────────
async function resetAppSettings(){
  if(!confirm(
    'Reset ALL server settings to factory defaults?\n\n' +
    'This will clear:\n  • Accent colour\n  • Brand name & logo\n  • Date/time format\n' +
    '  • Holiday country & subdivision\n  • Server notification defaults\n  • System settings\n\n' +
    'Browser-only settings (toggles, poll intervals) are NOT affected.\n\n' +
    'Continue?'
  )) return;
  const statusEl=document.getElementById('settings-reset-status');
  if(statusEl){statusEl.style.display='';statusEl.textContent='Resetting…';statusEl.style.color='var(--yellow)';}
  try{
    const r=await fetch('/api/reset_settings',{
      method:'POST',headers:{'Content-Type':'application/json'},body:'{}'
    });
    const j=await r.json();
    if(!j.ok) throw new Error(j.msg||'Reset failed');
    // Re-apply all settings to the live UI
    const defaults=j.values||{};
    // Accent colour
    const hex=(defaults.accent_color||'#b87333').trim();
    if(/^#[0-9a-fA-F]{6}$/.test(hex)){
      accentPreview(hex);
      const picker=document.getElementById('accent-color-picker');
      const hexIn=document.getElementById('accent-color-hex');
      if(picker) picker.value=hex;
      if(hexIn) hexIn.value=hex.toUpperCase();
    }
    // Branding
    if(typeof applyBranding==='function') applyBranding(defaults);
    if(typeof loadBrandingSettings==='function') loadBrandingSettings();
    // Holiday country
    const ci=document.getElementById('hol-country');
    const si=document.getElementById('hol-subdiv');
    if(ci) ci.value=defaults.holiday_country||'US';
    if(si) si.value=defaults.holiday_subdiv||'';
    // Invalidate holiday cache
    _hdLoaded=false; _hdData=[];
    const lbl=document.getElementById('hd-next-label');
    if(lbl) lbl.textContent='Holidays';
    if(statusEl){statusEl.textContent='✓ Settings reset to factory defaults.';statusEl.style.color='var(--green)';}
    toast('Settings reset to factory defaults','ok');
    setTimeout(()=>{if(statusEl)statusEl.style.display='none';},6000);
  }catch(e){
    if(statusEl){statusEl.textContent='✕ Reset failed: '+e.message;statusEl.style.color='var(--red)';}
    toast('Reset failed: '+e.message,'err');
  }
}

// ═══════════════════════════════════
// CLEAR PLAYED EVENTS
// ═══════════════════════════════════
// ── Service restart (streams + web process) ───────────────
async function svcRestartAll() {
  const el = document.getElementById('svc-restart-status');
  if (!confirm('This will stop all streams and restart the entire application.\nThe page will reconnect automatically in ~5 seconds.\n\nContinue?')) return;
  el.textContent = '⟳ Stopping streams…';
  el.style.color = 'var(--accent-light)';
  try {
    // 1) stop all streams gracefully
    await api('stop_all', {});
    el.textContent = '⟳ Restarting process…';
    // 2) tell the server to execv itself; this request will not return
    fetch('/api/action', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'restart_process'}),
    }).catch(() => {});  // connection drop is expected
    // 3) poll until the server responds again, then reload
    el.textContent = '⟳ Waiting for server to come back…';
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      if (attempts > 40) {  // give up after ~20 s
        clearInterval(poll);
        el.style.color = 'var(--red)';
        el.textContent = '⚠ Server did not respond after 20 s. Refresh manually.';
        return;
      }
      try {
        const r = await fetch('/api/streams', {cache: 'no-store'});
        if (r.ok) { clearInterval(poll); location.reload(); }
      } catch(_) {}
    }, 500);
  } catch(e) {
    el.style.color = 'var(--red)';
    el.textContent = '⚠ ' + (e.message || 'Request failed');
  }
}

async function clearPlayedEvents(){
  const st=document.getElementById('danger-status');
  try{
    const events=await fetch('/api/events').then(r=>r.json());
    if(!Array.isArray(events)){throw new Error('Could not load events');}
    const played=events.filter(e=>e.played);
    if(!played.length){
      st.textContent='No played events to clear.';st.style.color='var(--text3)';
      toast('No played events to clear','info');return;
    }
    if(!confirm(`Clear ${played.length} played event${played.length!==1?'s':''}?\n\nThis removes them from the schedule history permanently.`)) return;
    st.textContent='Clearing…';st.style.color='var(--yellow)';
    const r=await api('clear_played_events',{});
    if(r?.ok){
      st.textContent='✓ '+r.msg;st.style.color='var(--green)';
      toast(r.msg,'ok');
    }else{
      throw new Error(r?.msg||'Failed');
    }
  }catch(e){
    st.textContent='✕ '+e.message;st.style.color='var(--red)';
    toast('Clear failed: '+e.message,'err');
  }

}

// ═══════════════════════════════════
// FACTORY RESET
// ═══════════════════════════════════
async function factoryReset(){
  const st  = document.getElementById('danger-status');
  const btn = document.getElementById('factory-reset-btn');
  const orig = btn ? btn.innerHTML : '';

  if(!confirm(
    '⚠  FACTORY RESET — POINT OF NO RETURN\n\n' +
    'This will permanently and immediately:\n' +
    '  1. Force-kill ALL running stream processes\n' +
    '  2. Delete EVERY file and folder inside config/\n' +
    '     (streams · events · mail · settings · backups · resume positions)\n' +
    '  3. Restart the entire HydraCast server process\n\n' +
    'The page will reconnect once the server is back up.\n\n' +
    'Type  RESET  in the next prompt to confirm.'
  )) return;

  if(prompt('Type exactly:  RESET') !== 'RESET'){
    if(st){st.textContent='Reset cancelled.';st.style.color='var(--text3)';}
    return;
  }

  if(btn){btn.disabled=true;btn.innerHTML='<i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite;margin-right:5px"></i>Resetting…';}
  if(st){
    st.style.color='var(--yellow)';
    st.innerHTML='<i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite;margin-right:4px"></i>Step 1/3: Force-stopping all streams…';
  }

  // Fire the request — server will execv so it may not reply
  fetch('/api/reset',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({confirm:true}),
  }).then(async r=>{
    try{
      const j=await r.json();
      const stopped=(j.stopped||[]).length;
      const wiped=(j.wiped||[]).length;
      if(st) st.innerHTML=`<i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite;margin-right:4px"></i>`
        +`Stopped ${stopped} stream(s), wiped ${wiped} file(s) — waiting for server restart…`;
    }catch(_){}
  }).catch(()=>{
    // connection drop is expected as server restarts
  });

  if(st){
    setTimeout(()=>{
      if(st) st.innerHTML='<i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite;margin-right:4px"></i>Step 2/3: Wiping config directory…';
    },600);
    setTimeout(()=>{
      if(st) st.innerHTML='<i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite;margin-right:4px"></i>Step 3/3: Waiting for server to restart…';
      if(st) st.style.color='var(--accent-light)';
    },1200);
  }

  let tries=0;
  const poll=setInterval(async()=>{
    tries++;
    if(tries>80){  // 40 s
      clearInterval(poll);
      if(st){st.style.color='var(--red)';st.textContent='⚠ Server did not respond after 40 s — refresh manually.';}
      if(btn){btn.disabled=false;btn.innerHTML=orig;}
      return;
    }
    try{
      const r=await fetch('/api/streams',{cache:'no-store'});
      if(r.ok){clearInterval(poll);location.reload();}
    }catch(_){}
  },500);
}

// ═══════════════════════════════════
// THEME TOGGLE
// ═══════════════════════════════════
// THEME TOGGLE (moon/sun checkbox)
// ═══════════════════════════════════
(function initTheme(){
  try{
    const stored=localStorage.getItem('hc-theme');
    const isDark=!stored||stored==='dark';
    document.documentElement.setAttribute('data-theme',isDark?'dark':'light');
    const cb=document.getElementById('hc-theme-cb');
    if(cb)cb.checked=!isDark; // checked = light mode (sun visible on right)
  }catch(_){}
})();
document.addEventListener('DOMContentLoaded',function(){
  const cb=document.getElementById('hc-theme-cb');
  if(!cb)return;
  // Set initial checked state from current attribute
  cb.checked=document.documentElement.getAttribute('data-theme')==='light';
  cb.addEventListener('change',function(){
    const next=this.checked?'light':'dark';
    document.documentElement.setAttribute('data-theme',next);
    try{localStorage.setItem('hc-theme',next);}catch(_){}
  });
});
function toggleTheme(){
  const cb=document.getElementById('hc-theme-cb');
  if(cb){cb.checked=!cb.checked;cb.dispatchEvent(new Event('change'));}
}

// ═══════════════════════════════════
// PORT NOTIFICATION PANEL HELPERS
// ═══════════════════════════════════
function _showPortNotif(html){
  const panel=document.getElementById('port-notif-panel');
  const body=document.getElementById('port-notif-body');
  if(!panel||!body)return;
  body.innerHTML=html;
  panel.classList.remove('closing');
  panel.classList.add('open');
  // Dismiss when clicking anywhere outside the panel
  setTimeout(()=>{
    function _outsideClick(e){
      if(!panel.contains(e.target)){
        closePortNotif();
        document.removeEventListener('click',_outsideClick);
      }
    }
    document.addEventListener('click',_outsideClick);
  },200);
}

function closePortNotif(){
  const panel=document.getElementById('port-notif-panel');
  if(!panel)return;
  panel.classList.add('closing');
  setTimeout(()=>panel.classList.remove('open','closing'),190);
}

function _portSpinner(msg){
  return `<div class="pnb info" style="animation:none">
    <i class="ti ti-loader-2" style="animation:spin 0.8s linear infinite;font-size:14px;flex-shrink:0"></i>
    <span>${esc(msg)}</span>
  </div>`;
}

function _portBanner(type,msg){
  const icons={ok:'ti-circle-check',err:'ti-circle-x',warn:'ti-alert-triangle',info:'ti-info-circle'};
  return `<div class="pnb ${type}">
    <i class="ti ${icons[type]||'ti-info-circle'}" style="font-size:14px;flex-shrink:0"></i>
    <span>${msg}</span>
  </div>`;
}

function _portMapChips(ports){
  return Object.entries(ports||{}).map(([p,info])=>{
    const cls=info.free?'ok':'err';
    const icon=info.free?'✓':'✕';
    return `<span class="pmc ${cls}" title="${info.free?'Free':'In use by: '+(info.process||'unknown')}">
      <span class="pmc-icon">${icon}</span>${p}
      <span class="pmc-label">${esc(info.label||'')}</span>
    </span>`;
  }).join('');
}

// ═══════════════════════════════════
// INIT
// ═══════════════════════════════════
(async function init(){

  // ── Restore saved interval preferences ──────────────────────────────────
  try{
    const pi=localStorage.getItem('hc-poll-interval');
    if(pi){
      const sel=document.getElementById('st-poll-interval');
      if(sel) sel.value=pi;
    }
    const si=localStorage.getItem('hc-stats-interval');
    if(si){
      const sel=document.getElementById('st-stats-interval');
      if(sel) sel.value=si;
    }
    const li=localStorage.getItem('hc-log-interval');
    if(li){
      const sel=document.getElementById('st-log-interval');
      if(sel) sel.value=li;
    }
  }catch(_){}

  loadStreams();
  updateStats();
  // Start configurable timers (read values from restored selects)
  toggleAuto(_settings.autoref);
  applyStatsInterval();
  applyLogInterval();

  setInterval(()=>{
    const now=new Date();
    const el=document.getElementById('h-time');
    if(el) el.textContent=[now.getHours(),now.getMinutes(),now.getSeconds()]
      .map(n=>String(n).padStart(2,'0')).join(':');
  },1000);
  setInterval(()=>{
    if(document.getElementById('tab-viewer').classList.contains('active')) loadViewer();
  },5000);

  // Load holiday settings into the Settings tab inputs
  loadHolidaySettings();
})();

// Keyboard shortcuts
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT')return;
  if((e.key==='r'||e.key==='R')&&!e.ctrlKey&&!e.metaKey){loadStreams();toast('Refreshed','info');}
  if(e.key==='Escape'){closeSeek();fmCloseDialogs();}
});
document.getElementById('seek-modal').addEventListener('click',e=>{
  if(e.target===e.currentTarget)closeSeek();
});

// ═══════════════════════════════════════════════════════════════
// FILE MANAGER
// ═══════════════════════════════════════════════════════════════
let _fmCurrentPath = '';
let _fmLoaded      = false;
let _fmOp          = null;   // {action, path, name, isDir}
let _fmAllDirs     = [];     // flat list of all subdir paths for move/copy selects

async function loadFiles(path) {
  _fmCurrentPath = (path === undefined || path === null) ? '' : String(path);
  const body   = document.getElementById('fm-body');
  const status = document.getElementById('fm-status');
  if (!body) return;
  body.innerHTML = '<div class="fm-empty"><div class="empty-icon" style="animation:spin 1.2s linear infinite">⟳</div></div>';
  if (status) status.textContent = 'Loading…';

  try {
    // ── Fetch current directory + root listing in parallel ──────────────
    const [d, rootResp] = await Promise.all([
      fetch('/api/files?path=' + encodeURIComponent(_fmCurrentPath)).then(r => r.json()),
      _fmCurrentPath
        ? fetch('/api/files?path=').then(r => r.json()).catch(() => ({ dirs: [], multi_root: false }))
        : Promise.resolve(null),
    ]);

    if (d.error) {
      body.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>${_fmEsc(d.error)}</div></div>`;
      if (status) status.textContent = 'Error';
      return;
    }

    // ── Breadcrumb ──────────────────────────────────────────────────────
    const bc = document.getElementById('fm-breadcrumb');
    if (bc) {
      bc.innerHTML = (d.breadcrumb || [{ name: 'Files', path: '' }]).map((crumb, i, arr) => {
        const isLast = (i === arr.length - 1);
        const sep    = i > 0 ? '<span class="fm-sep">›</span>' : '';
        // Use data-fmpath attribute — avoids JS injection from path strings
        return sep + `<span data-fmpath="${_fmAttr(crumb.path)}"
             class="${isLast ? 'fm-cur' : ''}">${_fmEsc(crumb.name)}</span>`;
      }).join('');
      // Delegated click so paths with apostrophes/special chars work
      bc.onclick = (e) => {
        const sp = e.target.closest('[data-fmpath]');
        if (sp) loadFiles(sp.dataset.fmpath);
      };
    }

    // ── Sidebar rebuild ─────────────────────────────────────────────────
    // rootData: the top-level listing (may be d itself when _fmCurrentPath='')
    const rootData   = rootResp || d;
    const isMultiRoot = rootData.multi_root === true;

    _fmAllDirs   = [''];
    _fmRootMeta  = [];

    const sidebar = document.getElementById('fm-dir-list');
    if (sidebar) {
      // Top-level "root" button
      const _rootTopLabel =
        (rootData.breadcrumb && rootData.breadcrumb[0])
          ? rootData.breadcrumb[0].name
          : (isMultiRoot ? 'Roots' : 'Files');
      const _rlEl = document.getElementById('fm-root-label');
      if (_rlEl) _rlEl.textContent = _rootTopLabel;

      // Build breadcrumb ancestry set so we can highlight active trail
      const activeCrumbs = new Set(
        (d.breadcrumb || []).map(c => c.path).filter(p => p !== '')
      );
      activeCrumbs.add(_fmCurrentPath);

      sidebar.innerHTML =
        `<div class="fm-dir-item${_fmCurrentPath === '' ? ' active' : ''}"
              data-fmpath=""
              title="${_fmAttr(_rootTopLabel)}">
           <span class="fm-dir-icon">📁</span> ${_fmEsc(_rootTopLabel)}
         </div>`;

      if (isMultiRoot) {
        // Show each root drive
        (rootData.dirs || []).forEach(root => {
          const isActive = _fmCurrentPath === root.path
                        || _fmCurrentPath.startsWith(root.path + '/');
          _fmAllDirs.push(root.path);
          _fmRootMeta.push({ path: root.path, label: root.name });
          sidebar.insertAdjacentHTML('beforeend',
            `<div class="fm-dir-item${isActive ? ' active' : ''}"
                  data-fmpath="${_fmAttr(root.path)}"
                  title="${_fmAttr(root.path)}">
               <span class="fm-dir-icon">📁</span> ${_fmEsc(root.name)}
             </div>`);
        });
      } else {
        // Single-root: show immediate subdirs of root in sidebar
        const sidebarDirs = rootData.dirs || [];
        const seen = new Set();
        sidebarDirs.forEach(dir => {
          if (seen.has(dir.path)) return;
          seen.add(dir.path);
          _fmAllDirs.push(dir.path);
          _fmRootMeta.push({ path: dir.path, label: dir.name });

          const isActive = activeCrumbs.has(dir.path)
                        || _fmCurrentPath === dir.path
                        || _fmCurrentPath.startsWith(dir.path + '/');

          // If we're inside this dir, show its children in the sidebar too
          const subDirsHtml = _fmBuildSidebarSubs(dir, d, activeCrumbs, 1);

          sidebar.insertAdjacentHTML('beforeend',
            `<div class="fm-dir-item${isActive ? ' active' : ''}"
                  data-fmpath="${_fmAttr(dir.path)}"
                  title="${_fmAttr(dir.path)}">
               <span class="fm-dir-icon">📂</span> ${_fmEsc(dir.name)}
             </div>
             ${subDirsHtml}`);
        });
      }

      // Delegated click for sidebar
      sidebar.onclick = (e) => {
        const item = e.target.closest('[data-fmpath]');
        if (item && item.dataset.fmpath !== undefined) {
          loadFiles(item.dataset.fmpath);
        }
      };
    }

    // ── Populate move/copy dir selects with ALL visible paths ───────────
    // Merge sidebar dirs + current dir's sub-dirs
    (d.dirs || []).forEach(dir => {
      if (!_fmAllDirs.includes(dir.path)) _fmAllDirs.push(dir.path);
    });

    // ── Body rows ───────────────────────────────────────────────────────
    const rows = [];

    // Folders
    (d.dirs || []).forEach(dir => {
      const subInfo = dir.has_subdirs
        ? `<span style="font-size:9px;color:var(--text3);margin-left:3px" title="Contains subdirectories">▸</span>` : '';
      const mediaInfo = dir.has_media
        ? `<span style="font-size:9px;color:var(--green);margin-left:3px" title="Contains media files">🎬</span>` : '';
      rows.push(
        `<div class="fm-row" data-row-type="dir" data-row-path="${_fmAttr(dir.path)}" data-row-name="${_fmAttr(dir.name)}">
           <span class="fm-row-icon">📁</span>
           <span class="fm-row-name is-dir">${_fmEsc(dir.name)}${subInfo}${mediaInfo}</span>
           <span class="fm-row-meta">${dir.items < 0 ? '—' : dir.items + ' item' + (dir.items !== 1 ? 's' : '')}</span>
           <div class="fm-row-actions">
             <button class="fm-action-btn" data-action="rename" title="Rename this folder">✏ Rename</button>
             <button class="fm-action-btn mv"  data-action="move"   title="Move this folder">↗ Move</button>
             <button class="fm-action-btn del" data-action="deldir" title="Delete this folder and all contents">🗑 Delete</button>
           </div>
         </div>`
      );
    });

    // Files
    (d.files || []).forEach(f => {
      const ico = /\.(mp3|aac|flac|wav|ogg|m4a)$/i.test(f.ext) ? '🎵' : '🎬';
      const sup = f.supported
        ? `<span style="font-size:10px;color:var(--green);margin-left:4px" title="Supported format">✓</span>`
        : `<span style="font-size:10px;color:var(--text3);margin-left:4px" title="Unsupported format">—</span>`;
      rows.push(
        `<div class="fm-row" data-row-type="file" data-row-path="${_fmAttr(f.path)}" data-row-name="${_fmAttr(f.name)}">
           <span class="fm-row-icon">${ico}</span>
           <span class="fm-row-name">${_fmEsc(f.name)}${sup}</span>
           <span class="fm-row-meta">${_fmEsc(f.size)}</span>
           <div class="fm-row-actions">
             <button class="fm-action-btn" data-action="rename" title="Rename this file">✏ Rename</button>
             <button class="fm-action-btn mv"  data-action="move" title="Move this file">↗ Move</button>
             <button class="fm-action-btn cp"  data-action="copy" title="Copy this file">⎘ Copy</button>
             <button class="fm-action-btn del" data-action="del"  title="Delete this file">🗑 Delete</button>
           </div>
         </div>`
      );
    });

    if (!rows.length) {
      body.innerHTML = '<div class="fm-empty"><div class="empty-icon">📂</div><div>This folder is empty.</div></div>';
    } else {
      body.innerHTML = rows.join('');
      // ── Single delegated event listener for all row actions ─────────
      body.onclick = (e) => {
        // Navigate into dir by clicking its name
        const nameSp = e.target.closest('.fm-row-name.is-dir');
        if (nameSp) {
          const row = nameSp.closest('[data-row-path]');
          if (row) { loadFiles(row.dataset.rowPath); return; }
        }

        // Action buttons
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const row = btn.closest('[data-row-path]');
        if (!row) return;
        const path  = row.dataset.rowPath;
        const name  = row.dataset.rowName;
        const isDir = row.dataset.rowType === 'dir';
        const action = btn.dataset.action;

        if (action === 'rename') { fmStartRename(path, name, isDir); }
        else if (action === 'move')   { fmStartMove(path, name, isDir); }
        else if (action === 'copy')   { fmStartCopy(path, name); }
        else if (action === 'del')    { fmDelete(path, name); }
        else if (action === 'deldir') { fmDeleteDir(path, name); }
      };
    }

    // ── Status bar ──────────────────────────────────────────────────────
    const _pathLabel = _fmCurrentPath
      ? (d.root_label
          ? d.root_label + (_fmCurrentPath.includes('/') ? '/' + _fmCurrentPath.split('/').slice(1).join('/') : '')
          : _fmCurrentPath)
      : ((d.breadcrumb && d.breadcrumb[0]) ? d.breadcrumb[0].name : 'Media');
    if (status) status.innerHTML =
      `<b>${(d.dirs || []).length}</b> folder${(d.dirs || []).length !== 1 ? 's' : ''}&nbsp;&nbsp;` +
      `<b>${(d.files || []).length}</b> file${(d.files || []).length !== 1 ? 's' : ''}&ensp;·&ensp;` +
      `<span style="color:var(--accent-light)">${_fmEsc(_pathLabel)}</span>`;

  } catch(e) {
    body.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>Load failed: ${_fmEsc(e.message)}</div></div>`;
    if (status) status.textContent = 'Error';
  }
}

/** Escape for HTML text content */
function _fmEsc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
/** Escape for HTML attribute values (double-quoted) */
function _fmAttr(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/** Escape a path string for use inside a single-quoted JS onclick attribute */
function _fmEscPath(s) {
  return String(s ?? '').replace(/\\/g,'\\\\').replace(/'/g,"\\'");
}


/**
 * Build sidebar sub-directory entries for dirs that are ancestors of the
 * current path (so the open trail is always visible in the sidebar).
 *
 * @param {Object} dir      - The parent dir object {path, name, items}
 * @param {Object} currentD - The API response for the currently viewed dir
 * @param {Set}    activeCrumbs - Set of path strings in the current breadcrumb
 * @param {number} depth    - Indentation depth
 */
function _fmBuildSidebarSubs(dir, currentD, activeCrumbs, depth) {
  // Only expand if this dir is an ancestor of the current path
  const isAncestor = _fmCurrentPath === dir.path
                  || _fmCurrentPath.startsWith(dir.path + '/');
  if (!isAncestor || depth > 6) return '';

  // Use the current dir's subdir listing when we are inside it;
  // otherwise we don't have sub-listing data (avoid extra API calls).
  let subs = [];
  if (_fmCurrentPath === dir.path) {
    subs = currentD.dirs || [];
  } else if (_fmCurrentPath.startsWith(dir.path + '/')) {
    // The current response's breadcrumb tells us the next level crumb
    // We render only breadcrumb crumbs we know about
    const nextCrumb = (currentD.breadcrumb || []).find(c =>
      c.path !== dir.path && c.path.startsWith(dir.path + '/') &&
      !c.path.slice(dir.path.length + 1).includes('/')
    );
    if (nextCrumb) subs = [{ path: nextCrumb.path, name: nextCrumb.name, items: '…' }];
  }

  if (!subs.length) return '';
  const indent = depth * 14;
  return subs.map(sub => {
    if (!_fmAllDirs.includes(sub.path)) _fmAllDirs.push(sub.path);
    const isActive = _fmCurrentPath === sub.path
                  || _fmCurrentPath.startsWith(sub.path + '/');
    const childSubs = _fmBuildSidebarSubs(sub, currentD, activeCrumbs, depth + 1);
    return `<div class="fm-dir-item${isActive ? ' active' : ''}"
                  data-fmpath="${_fmAttr(sub.path)}"
                  style="padding-left:${16 + indent}px"
                  title="${_fmAttr(sub.path)}">
               <span class="fm-dir-icon">📂</span> ${_fmEsc(sub.name)}
             </div>
             ${childSubs}`;
  }).join('');
}


// ── New folder ────────────────────────────────────────────────
async function fmNewFolder() {
  const name = prompt('New folder name:');
  if (!name || !name.trim()) return;
  // _fmCurrentPath is now @N/rel or '' for root.
  // Pass it as 'parent' so the backend can resolve it via _decode_root.
  const r = await api('create_subdir', {
    parent: _fmCurrentPath || '',
    name:   name.trim(),
  });
  if (r.ok) { loadFiles(_fmCurrentPath); loadSubdirs(); }
}

// ── Rename ────────────────────────────────────────────────────
function fmStartRename(path, name, isDir) {
  _fmOp = {action:'rename', path, name, isDir};
  const inp = document.getElementById('fm-rename-input');
  inp.value = name;
  document.getElementById('fm-rename-overlay').classList.add('open');
  setTimeout(() => { inp.select(); }, 80);
}
async function fmDoRename() {
  const newName = document.getElementById('fm-rename-input').value.trim();
  if (!newName) { toast('Enter a name','err'); return; }
  const r = await api('file_rename', {path:_fmOp.path, new_name:newName});
  if (r.ok) { fmCloseDialogs(); loadFiles(_fmCurrentPath); }
}

// ── Delete file ───────────────────────────────────────────────
async function fmDelete(path, name) {
  if (!confirm(`Delete file:\n"${name}"\n\nThis cannot be undone. Any stream playlist entries for this file will be removed automatically.`)) return;
  const r = await api('file_delete', {path});
  if (r.ok) loadFiles(_fmCurrentPath);
}

// ── Delete directory ──────────────────────────────────────────
async function fmDeleteDir(path, name) {
  if (!confirm(`Delete folder:\n"${name}"\n\nAll contents will be permanently deleted and playlist entries removed. Cannot be undone.`)) return;
  const r = await api('file_delete_dir', {path});
  if (r.ok) loadFiles(_fmCurrentPath);
}

// ── Move ──────────────────────────────────────────────────────
function fmStartMove(path, name, isDir) {
  _fmOp = {action:'move', path, name, isDir};
  _fmPopulateDirSelect('fm-move-dest', path);
  document.getElementById('fm-move-overlay').classList.add('open');
}
async function fmDoMove() {
  const dest = document.getElementById('fm-move-dest').value;
  const r = await api('file_move', {path:_fmOp.path, dest_dir:dest});
  if (r.ok) { fmCloseDialogs(); loadFiles(_fmCurrentPath); }
}

// ── Copy ──────────────────────────────────────────────────────
function fmStartCopy(path, name) {
  _fmOp = {action:'copy', path, name};
  _fmPopulateDirSelect('fm-copy-dest', path);
  document.getElementById('fm-copy-name').value = '';
  document.getElementById('fm-copy-overlay').classList.add('open');
}
async function fmDoCopy() {
  const dest    = document.getElementById('fm-copy-dest').value;
  const newName = document.getElementById('fm-copy-name').value.trim();
  const r = await api('file_copy', {path:_fmOp.path, dest_dir:dest, new_name:newName});
  if (r.ok) { fmCloseDialogs(); loadFiles(_fmCurrentPath); }
}

// ── Dir select helper ─────────────────────────────────────────
function _fmPopulateDirSelect(selectId, excludePath) {
  const sel = document.getElementById(selectId);
  const _rlEl2 = document.getElementById('fm-root-label');
  const _topLabel = (_rlEl2 && _rlEl2.textContent) ? _rlEl2.textContent + ' (top)' : 'Root (top)';
  sel.innerHTML = `<option value="">${_topLabel}</option>`;
  // Build a label map from _fmRootMeta (populated by loadFiles).
  const labelMap = {};
  (_fmRootMeta || []).forEach(m => { labelMap[m.path] = m.label; });
  _fmAllDirs
    .filter(d => d && d !== excludePath)
    .forEach(d => {
      const label = labelMap[d] || d;
      sel.insertAdjacentHTML('beforeend', `<option value="${d}">${label}</option>`);
    });
}

// ── Close all FM dialogs ──────────────────────────────────────
function fmCloseDialogs() {
  document.querySelectorAll('.fm-dialog-overlay').forEach(el => el.classList.remove('open'));
  _fmOp = null;
}

// ═══════════════════════════════════
// EVENTS CALENDAR (React)
// ═══════════════════════════════════
</script>
<script type="text/babel" data-presets="react">
/**
 * EventsCalendar.jsx  — v2.0
 *
 * Changes vs v1:
 *   • Calendar grid fills the full tab width (no fixed-width sidebar push)
 *   • Past dates/times are blocked — clicking them shows a tooltip, not the form
 *   • Created events are editable (click chip → EditModal with all fields)
 *   • Loop mode: play once / loop N times / loop indefinitely
 *   • Multi-date selection: pick multiple dates in one session, schedule all at once
 *   • Sidebar scrolls alongside and shows edit/delete buttons per event
 */

const { useState, useEffect, useRef, useCallback } = React;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const MONTHS     = ["January","February","March","April","May","June",
                    "July","August","September","October","November","December"];
const DAYS_SHORT = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

const COUNTRIES = [
  {code:"AE",name:"UAE"},{code:"AR",name:"Argentina"},{code:"AT",name:"Austria"},
  {code:"AU",name:"Australia"},{code:"BD",name:"Bangladesh"},{code:"BE",name:"Belgium"},
  {code:"BR",name:"Brazil"},{code:"CA",name:"Canada"},{code:"CH",name:"Switzerland"},
  {code:"CN",name:"China"},{code:"CO",name:"Colombia"},{code:"CZ",name:"Czech Republic"},
  {code:"DE",name:"Germany"},{code:"DK",name:"Denmark"},{code:"EG",name:"Egypt"},
  {code:"ES",name:"Spain"},{code:"FI",name:"Finland"},{code:"FR",name:"France"},
  {code:"GB",name:"United Kingdom"},{code:"GH",name:"Ghana"},{code:"GR",name:"Greece"},
  {code:"HU",name:"Hungary"},{code:"ID",name:"Indonesia"},{code:"IE",name:"Ireland"},
  {code:"IL",name:"Israel"},{code:"IN",name:"India"},{code:"IQ",name:"Iraq"},
  {code:"IR",name:"Iran"},{code:"IT",name:"Italy"},{code:"JP",name:"Japan"},
  {code:"KE",name:"Kenya"},{code:"KR",name:"South Korea"},{code:"KW",name:"Kuwait"},
  {code:"LK",name:"Sri Lanka"},{code:"MA",name:"Morocco"},{code:"MX",name:"Mexico"},
  {code:"MY",name:"Malaysia"},{code:"NG",name:"Nigeria"},{code:"NL",name:"Netherlands"},
  {code:"NO",name:"Norway"},{code:"NP",name:"Nepal"},{code:"NZ",name:"New Zealand"},
  {code:"OM",name:"Oman"},{code:"PH",name:"Philippines"},{code:"PK",name:"Pakistan"},
  {code:"PL",name:"Poland"},{code:"PT",name:"Portugal"},{code:"QA",name:"Qatar"},
  {code:"RO",name:"Romania"},{code:"RU",name:"Russia"},{code:"SA",name:"Saudi Arabia"},
  {code:"SE",name:"Sweden"},{code:"SG",name:"Singapore"},{code:"TH",name:"Thailand"},
  {code:"TN",name:"Tunisia"},{code:"TR",name:"Turkey"},{code:"TZ",name:"Tanzania"},
  {code:"UA",name:"Ukraine"},{code:"UG",name:"Uganda"},{code:"US",name:"United States"},
  {code:"VN",name:"Vietnam"},{code:"ZA",name:"South Africa"},{code:"ZW",name:"Zimbabwe"},
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmtDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
function getEventDate(ev) { return (ev.play_at_iso || ev.play_at || "").slice(0,10); }
function getEventTime(ev) { return (ev.play_at_iso || ev.play_at || "").slice(11,16); }

function isPastDate(ds, todayStr) { return ds < todayStr; }
function isPastDateTime(ds, timeStr, todayStr) {
  if (ds < todayStr) return true;
  if (ds === todayStr) {
    const now = new Date();
    const nowHHMM = `${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}`;
    return timeStr <= nowHHMM;
  }
  return false;
}

function loopLabel(n) {
  if (n === 0) return "Play once";
  if (n === -1) return "Loop forever";
  return `Loop ×${n+1}`;
}

// ---------------------------------------------------------------------------
// Shared label style
// ---------------------------------------------------------------------------
const lbl = {
  display:"block", fontSize:"11px", fontWeight:"500",
  color:"var(--color-text-secondary)", marginBottom:"6px",
};

// ---------------------------------------------------------------------------
// EventChip — clickable, opens edit modal
// ---------------------------------------------------------------------------
function EventChip({ ev, onEdit }) {
  const played = ev.played;
  return (
    <div
      onClick={e => { e.stopPropagation(); onEdit(ev); }}
      title={`${ev.stream_name} — ${ev.file_name || ev.file_path}\nClick to edit`}
      style={{
        borderRadius:"4px", padding:"3px 6px", marginBottom:"3px",
        fontSize:"11px", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
        cursor: played ? "default" : "pointer",
        background: played ? "var(--color-background-success)" : "var(--color-background-info)",
        border:`0.5px solid ${played ? "var(--color-border-success)" : "var(--color-border-info)"}`,
        color: played ? "var(--color-text-success)" : "var(--color-text-info)",
      }}
    >
      <span style={{fontWeight:"500"}}>{getEventTime(ev)}</span>
      {" "}{ev.stream_name}
      {ev.loop_count === -1 && " ∞"}
      {ev.loop_count > 0 && ` ×${ev.loop_count+1}`}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DayCell
// ---------------------------------------------------------------------------
function DayCell({ day, year, month, todayStr, holidays, eventsByDate, onOpen, selectedDates, onToggleSelect, multiSelect }) {
  if (!day) return (
    <div style={{
      minHeight:"120px",
      borderRight:"0.5px solid var(--color-border-tertiary)",
      borderBottom:"0.5px solid var(--color-border-tertiary)",
    }}/>
  );

  const ds      = `${year}-${String(month+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
  const isToday = ds === todayStr;
  const isPast  = isPastDate(ds, todayStr);
  const holidayObj = holidays[ds];
  const holiday    = holidayObj ? holidayObj.name : null;
  const holidaySrc = holidayObj ? (holidayObj.source || "library") : null;
  const dayEvts = eventsByDate[ds] || [];
  const isSelected = selectedDates && selectedDates.has(ds);
  const hasEvents = dayEvts.length > 0;

  const baseBg = isSelected
    ? "var(--color-background-success)"
    : isToday
      ? "var(--color-background-info)"
      : holidaySrc === "custom"
        ? "var(--purple-dim)"
        : holiday
          ? "var(--color-background-danger)"
          : "transparent";

  const handleClick = () => {
    if (isPast && !isToday) return;
    if (multiSelect) {
      onToggleSelect(ds);
    } else {
      onOpen(day, ds);
    }
  };

  return (
    <div
      onClick={handleClick}
      tabIndex={isPast && !isToday ? -1 : 0}
      role="button"
      aria-label={`${MONTHS[month]} ${day}, ${year}${holiday ? `, ${holiday}` : ""}${isPast && !isToday ? " (past)" : ""}`}
      onKeyDown={e => e.key === "Enter" && handleClick()}
      style={{
        minHeight:"120px", padding:"8px 9px",
        borderRight:"0.5px solid var(--color-border-tertiary)",
        borderBottom:"0.5px solid var(--color-border-tertiary)",
        background: baseBg,
        cursor: isPast && !isToday ? "not-allowed" : "pointer",
        opacity: isPast && !isToday ? 0.38 : 1,
        transition:"background 0.15s, box-shadow 0.15s",
        outline:"none",
        position:"relative",
        boxShadow: isToday ? "inset 0 0 0 2px var(--color-text-info)" : hasEvents && !isPast ? "inset 0 0 0 1px var(--color-border-info)" : "none",
      }}
      onMouseEnter={e => { if (!isPast || isToday) { e.currentTarget.style.background = isSelected ? "var(--color-background-success)" : "var(--color-background-secondary)"; e.currentTarget.style.boxShadow = `inset 0 0 0 2px var(--accent)`; }}}
      onMouseLeave={e => { e.currentTarget.style.background = baseBg; e.currentTarget.style.boxShadow = isToday ? "inset 0 0 0 2px var(--color-text-info)" : hasEvents && !isPast ? "inset 0 0 0 1px var(--color-border-info)" : "none"; }}
    >
      {/* Multi-select indicator */}
      {multiSelect && !isPast && (
        <div style={{
          position:"absolute",top:"4px",right:"4px",
          width:"14px",height:"14px",borderRadius:"3px",
          border:`1px solid ${isSelected ? "var(--color-text-success)" : "var(--color-border-secondary)"}`,
          background: isSelected ? "var(--color-text-success)" : "transparent",
          display:"flex",alignItems:"center",justifyContent:"center",
          flexShrink:0,
        }}>
          {isSelected && <i className="ti ti-check" style={{fontSize:"9px",color:"#fff"}}/>}
        </div>
      )}

      {/* Day number */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:"4px"}}>
        <span style={{
          fontSize:"15px",
          fontWeight: isToday ? "700" : "500",
          width:"26px", height:"26px",
          borderRadius:"50%",
          display:"flex", alignItems:"center", justifyContent:"center",
          background: isToday ? "var(--color-text-info)" : "transparent",
          color: isToday ? "#fff" : isPast ? "var(--color-text-tertiary)" : "var(--color-text-primary)",
          flexShrink:0,
        }}>{day}</span>
        {holiday && (
          <i className="ti ti-star-filled" aria-hidden="true"
             style={{fontSize:"12px",color: holidaySrc==="custom" ? "var(--purple)" : "var(--color-text-danger)",marginTop:"5px"}}/>
        )}
      </div>

      {holiday && (
        <div style={{fontSize:"10px",
          color: holidaySrc==="custom" ? "var(--purple)" : "var(--color-text-danger)",
          marginBottom:"4px",lineHeight:"1.3",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontWeight:"500"}}
          title={holiday + (holidaySrc==="custom" ? " (custom)" : "")}>{holiday}</div>
      )}

      {dayEvts.slice(0,3).map((ev,i) => (
        <EventChip key={i} ev={ev} onEdit={()=>{}}/>
      ))}
      {dayEvts.length > 3 && (
        <div style={{fontSize:"10px",color:"var(--color-text-tertiary)",fontWeight:"500"}}>
          +{dayEvts.length - 3} more
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar — event list for the current month
// ---------------------------------------------------------------------------
function Sidebar({ month, year, events, holidays, onEdit, onDelete, hidePlayed, onToggleHidePlayed }) {
  const monthPfx = `${year}-${String(month+1).padStart(2,"0")}`;
  const evts = events
    .filter(e => getEventDate(e).startsWith(monthPfx))
    .sort((a,b) => (getEventDate(a)+getEventTime(a)).localeCompare(getEventDate(b)+getEventTime(b)));

  const playedCount = evts.filter(e => e.played).length;
  const visible = hidePlayed ? evts.filter(e => !e.played) : evts;

  return (
    <aside style={{width:"230px",borderLeft:"0.5px solid var(--color-border-tertiary)",
      flexShrink:0,overflowY:"auto",maxHeight:"calc(100vh - 180px)"}}>
      <div style={{padding:"10px 14px",borderBottom:"0.5px solid var(--color-border-tertiary)",
        position:"sticky",top:0,background:"var(--color-background-primary)",zIndex:1}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom: playedCount > 0 ? "6px" : 0}}>
          <span style={{fontSize:"12px",fontWeight:"500",color:"var(--color-text-secondary)"}}>
            {MONTHS[month]} events
          </span>
          <span style={{fontSize:"12px",color:"var(--color-text-tertiary)"}}>{evts.length}</span>
        </div>
        {playedCount > 0 && (
          <button
            onClick={onToggleHidePlayed}
            title={hidePlayed ? "Show played events in list" : "Hide played events from list (still shown on calendar)"}
            style={{
              width:"100%",fontSize:"10px",padding:"3px 8px",
              display:"flex",alignItems:"center",justifyContent:"center",gap:"4px",
              background: hidePlayed ? "var(--color-background-success)" : "transparent",
              color:      hidePlayed ? "var(--color-text-success)"       : "var(--color-text-secondary)",
              border:`0.5px solid ${hidePlayed ? "var(--color-border-success)" : "var(--color-border-tertiary)"}`,
              borderRadius:"var(--border-radius-sm)",cursor:"pointer",
            }}>
            <i className={`ti ti-${hidePlayed ? "eye" : "eye-off"}`} style={{fontSize:"10px"}}/>
            {hidePlayed ? `Show ${playedCount} played` : `Hide ${playedCount} played`}
          </button>
        )}
      </div>

      {evts.length === 0 ? (
        <p style={{padding:"20px 14px",fontSize:"12px",color:"var(--color-text-tertiary)",
          textAlign:"center",lineHeight:"1.6",margin:0}}>
          No events this month.<br/>Click any future date to schedule.
        </p>
      ) : visible.length === 0 ? (
        <p style={{padding:"20px 14px",fontSize:"12px",color:"var(--color-text-tertiary)",
          textAlign:"center",lineHeight:"1.6",margin:0}}>
          All {playedCount} event{playedCount!==1?"s":""} played.<br/>
          <span style={{fontSize:"11px",opacity:0.7}}>Events still shown on calendar.</span>
        </p>
      ) : (
        visible.map((ev,i) => {
          const ds  = getEventDate(ev);
          const ts  = getEventTime(ev);
          const holObj = holidays[ds];
          const hol    = holObj ? holObj.name : null;
          const holSrc = holObj ? (holObj.source || "library") : null;
          return (
            <div key={i} style={{padding:"9px 14px",borderBottom:"0.5px solid var(--color-border-tertiary)",fontSize:"12px"}}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:"2px",alignItems:"center"}}>
                <span style={{color:"var(--color-text-secondary)",fontWeight:"500"}}>
                  {ds.slice(5).replace("-","/")} {ts}
                </span>
                <span style={{
                  fontSize:"10px",padding:"1px 6px",borderRadius:"999px",
                  background: ev.played ? "var(--color-background-success)" : "var(--color-background-info)",
                  color:      ev.played ? "var(--color-text-success)"       : "var(--color-text-info)",
                  border:`0.5px solid ${ev.played ? "var(--color-border-success)" : "var(--color-border-info)"}`,
                }}>{ev.played ? "played" : "upcoming"}</span>
              </div>
              <div style={{fontWeight:"500",color:"var(--color-text-primary)",
                overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                {ev.stream_name}
              </div>
              <div style={{color:"var(--color-text-tertiary)",overflow:"hidden",
                textOverflow:"ellipsis",whiteSpace:"nowrap",marginTop:"1px"}}
                title={ev.file_name || ev.file_path}>
                {ev.file_name || (ev.file_path||"").split("/").pop()}
              </div>
              <div style={{fontSize:"10px",color:"var(--color-text-secondary)",marginTop:"2px",
                display:"flex",alignItems:"center",gap:"4px",flexWrap:"wrap"}}>
                <i className="ti ti-rotate-clockwise" style={{fontSize:"10px"}}/>
                {ev.post_action || "resume"}
                {ev.loop_count === -1 && <span style={{marginLeft:"4px",color:"var(--color-text-info)"}}>∞ loop</span>}
                {ev.loop_count > 0 && <span style={{marginLeft:"4px",color:"var(--color-text-info)"}}>×{ev.loop_count+1}</span>}
              </div>
              {hol && (
                <div style={{fontSize:"10px",color: holSrc==="custom" ? "var(--purple)" : "var(--color-text-danger)",marginTop:"2px",
                  display:"flex",alignItems:"center",gap:"3px"}}>
                  <i className="ti ti-star-filled" style={{fontSize:"9px"}}/> {hol}{holSrc==="custom" && <span style={{fontSize:"9px",marginLeft:"2px",opacity:0.7}}>(custom)</span>}
                </div>
              )}
              {ev.comment && (
                <div style={{fontSize:"10px",color:"var(--color-text-secondary)",marginTop:"3px",
                  display:"flex",alignItems:"flex-start",gap:"3px",
                  overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}
                  title={ev.comment}>
                  <i className="ti ti-message-2" style={{fontSize:"10px",marginTop:"1px",flexShrink:0}}/>
                  <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{ev.comment}</span>
                </div>
              )}
              {!ev.played && (
                <div style={{display:"flex",gap:"5px",marginTop:"6px"}}>
                  <button onClick={()=>onEdit(ev)}
                    style={{fontSize:"10px",padding:"2px 8px",display:"flex",alignItems:"center",gap:"3px"}}>
                    <i className="ti ti-pencil" style={{fontSize:"10px"}}/>Edit
                  </button>
                  <button onClick={()=>onDelete(ev.event_id)}
                    style={{fontSize:"10px",padding:"2px 8px",
                      color:"var(--color-text-danger)",borderColor:"var(--color-border-danger)",
                      display:"flex",alignItems:"center",gap:"3px"}}>
                    <i className="ti ti-trash" style={{fontSize:"10px"}}/>Del
                  </button>
                </div>
              )}
            </div>
          );
        })
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// LoopSelector
// ---------------------------------------------------------------------------
function LoopSelector({ value, onChange }) {
  const opts = [
    { v: 0,  label: "Play once" },
    { v: 1,  label: "Loop ×2" },
    { v: 2,  label: "Loop ×3" },
    { v: 4,  label: "Loop ×5" },
    { v: 9,  label: "Loop ×10" },
    { v: -1, label: "Loop forever ∞" },
  ];
  return (
    <select value={value} onChange={e=>onChange(Number(e.target.value))} style={{width:"100%"}}>
      {opts.map(o=><option key={o.v} value={o.v}>{o.label}</option>)}
    </select>
  );
}

// ---------------------------------------------------------------------------
// CreateModal — supports multi-date + loop
// ---------------------------------------------------------------------------
function CreateModal({ dates, holidays, streams, library, libraryLoading, todayStr, onClose, onCreate }) {
  const [time,       setTime]       = useState("12:00");
  const [endTime,    setEndTime]    = useState("");
  const [selStreams,  setSelStreams] = useState({});   // name -> true
  const [files,      setFiles]      = useState({});   // name -> file_path
  const [loopCount,  setLoopCount]  = useState(0);
  const [postAction, setPostAction] = useState("resume");
  const [startPos,   setStartPos]   = useState("00:00:00");
  const [comment,    setComment]    = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err,        setErr]        = useState("");

  // sorted date list
  const sortedDates = [...dates].sort();

  // Check if any selected date+time is in the past
  const hasPastDateTime = sortedDates.some(ds => isPastDateTime(ds, time, todayStr));

  const toggle = name => setSelStreams(p => { const n={...p}; n[name] ? delete n[name] : (n[name]=true); return n; });

  const submit = async () => {
    const sel = Object.keys(selStreams);
    if (!sel.length) { setErr("Select at least one stream."); return; }
    for (const s of sel) {
      if (!files[s]) { setErr(`Select a file for "${s}".`); return; }
    }
    if (hasPastDateTime) { setErr("One or more selected date/time combinations are in the past."); return; }

    const [hh,mm] = time.split(":").map(Number);
    const timeStr = `${String(hh).padStart(2,"0")}:${String(mm).padStart(2,"0")}:00`;

    let broadcast_end_time;
    if (endTime) {
      const [ehh,emm] = endTime.split(":").map(Number);
      broadcast_end_time = `${String(ehh).padStart(2,"0")}:${String(emm).padStart(2,"0")}:00`;
    }

    setSubmitting(true);
    setErr("");
    try {
      // Fire one bulk call per date
      let totalCreated = 0;
      for (const ds of sortedDates) {
        const iso = `${ds}T${timeStr}`;
        const payload = {
          play_at:    iso,
          streams:    sel.map(name => ({ stream_name: name, file_path: files[name] })),
          post_action: postAction,
          loop_count: loopCount,
          comment:    comment.trim(),
        };
        if (broadcast_end_time) {
          // handle crossing midnight
          let edate = ds;
          if (broadcast_end_time <= timeStr) {
            // advance by 1 day
            const d = new Date(ds); d.setDate(d.getDate()+1);
            edate = fmtDate(d);
          }
          payload.broadcast_end = `${edate}T${broadcast_end_time}`;
        }
        const res  = await fetch("/api/events/bulk", {
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.created?.length) totalCreated += data.created.length;
      }
      await onCreate(totalCreated);
      onClose();
    } catch(e) {
      setErr(e.message || "Failed to schedule events.");
      setSubmitting(false);
    }
  };

  const dateLabel = sortedDates.length === 1
    ? new Date(sortedDates[0]+"T12:00:00").toLocaleDateString("en-GB",{weekday:"long",day:"numeric",month:"long",year:"numeric"})
    : `${sortedDates.length} dates selected`;

  return (
    <div style={{
      background:"var(--color-background-primary)",
      border:"0.5px solid var(--color-border-primary)",
      borderRadius:"var(--border-radius-lg)",
      width:"540px",maxHeight:"82vh",overflowY:"auto",
      boxShadow:"0 8px 32px rgba(0,0,0,0.22)",
    }}>
      {/* Header */}
      <div style={{padding:"16px 20px",borderBottom:"0.5px solid var(--color-border-tertiary)",
        display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div>
          <p style={{margin:0,fontSize:"15px",fontWeight:"500",color:"var(--color-text-primary)"}}>
            Schedule event{sortedDates.length > 1 ? "s" : ""}
          </p>
          <p style={{margin:"3px 0 0",fontSize:"13px",color:"var(--color-text-secondary)"}}>
            {dateLabel}
          </p>
        </div>
        <button onClick={onClose} aria-label="Close"
          style={{background:"none",border:"none",cursor:"pointer",
            color:"var(--color-text-secondary)",fontSize:"20px",lineHeight:1,padding:"2px 6px"}}>×</button>
      </div>

      <div style={{padding:"18px 20px"}}>
        {/* Selected dates (multi) */}
        {sortedDates.length > 1 && (
          <div style={{marginBottom:"16px"}}>
            <label style={lbl}>Selected dates ({sortedDates.length})</label>
            <div style={{display:"flex",flexWrap:"wrap",gap:"5px"}}>
              {sortedDates.map(ds=>{
                const past = isPastDateTime(ds, time, todayStr);
                return (
                  <span key={ds} style={{
                    fontSize:"11px",padding:"2px 8px",borderRadius:"999px",
                    background: past ? "var(--color-background-danger)" : "var(--color-background-info)",
                    color:      past ? "var(--color-text-danger)"       : "var(--color-text-info)",
                    border:`0.5px solid ${past ? "var(--color-border-danger)" : "var(--color-border-info)"}`,
                  }}>
                    {ds.slice(5).replace("-","/")}
                    {past && " ⚠"}
                  </span>
                );
              })}
            </div>
            {hasPastDateTime && (
              <p style={{fontSize:"11px",color:"var(--color-text-danger)",margin:"6px 0 0"}}>
                ⚠ Some dates are in the past and will be skipped.
              </p>
            )}
          </div>
        )}

        {/* Time */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>Broadcast start time</label>
          <input type="time" value={time} onChange={e=>setTime(e.target.value)} style={{width:"160px"}}/>
          {sortedDates.length===1 && hasPastDateTime && (
            <span style={{fontSize:"11px",color:"var(--color-text-danger)",marginLeft:"10px"}}>
              ⚠ This time is in the past
            </span>
          )}
        </div>

        {/* End time */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>
            Broadcast end time
            <span style={{fontWeight:"400",color:"var(--color-text-tertiary)",marginLeft:"6px"}}>optional</span>
          </label>
          <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
            <input type="time" value={endTime} onChange={e=>setEndTime(e.target.value)} style={{width:"160px"}}/>
            {endTime && (
              <button onClick={()=>setEndTime("")}
                style={{fontSize:"11px",padding:"3px 9px",color:"var(--color-text-tertiary)"}}>Clear</button>
            )}
          </div>
          <p style={{fontSize:"11px",color:"var(--color-text-tertiary)",margin:"5px 0 0"}}>
            Leave blank to play to file end.
            {endTime && time && endTime <= time && (
              <span style={{color:"var(--color-text-info)",marginLeft:"6px"}}>(wraps to next day)</span>
            )}
          </p>
        </div>

        {/* Start position */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>
            Start position
            <span style={{fontWeight:"400",color:"var(--color-text-tertiary)",marginLeft:"6px"}}>HH:MM:SS</span>
          </label>
          <input value={startPos} onChange={e=>setStartPos(e.target.value)}
            placeholder="00:00:00" style={{width:"140px"}}/>
        </div>

        {/* Loop */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>Loop / repeat</label>
          <LoopSelector value={loopCount} onChange={setLoopCount}/>
        </div>

        {/* Post-action */}
        <div style={{marginBottom:"16px"}}>
          <label style={lbl}>After playback</label>
          <select value={postAction} onChange={e=>setPostAction(e.target.value)} style={{width:"100%"}}>
            <option value="resume">Return to normal schedule / compliance</option>
            <option value="stop">Stop stream</option>
            <option value="black">Show black screen</option>
          </select>
        </div>

        {/* Streams */}
        <div style={{marginBottom:"16px"}}>
          <label style={lbl}>
            Streams
            {Object.keys(selStreams).length > 0 &&
              <span style={{fontWeight:"400",color:"var(--color-text-tertiary)",marginLeft:"6px"}}>
                — {Object.keys(selStreams).length} selected
              </span>}
          </label>
          {streams.length === 0 ? (
            <p style={{fontSize:"12px",color:"var(--color-text-tertiary)",margin:0}}>No streams configured.</p>
          ) : (
            <div style={{display:"flex",flexDirection:"column",gap:"6px"}}>
              {[...streams].sort((a,b)=>a.name.localeCompare(b.name)).map(st => {
                const sel = !!selStreams[st.name];
                return (
                  <div key={st.name} style={{
                    border:`0.5px solid ${sel ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
                    borderRadius:"var(--border-radius-md)",overflow:"hidden",
                    background: sel ? "var(--color-background-info)" : "var(--color-background-secondary)",
                    transition:"border-color 0.12s",
                  }}>
                    <div onClick={()=>toggle(st.name)}
                      style={{display:"flex",alignItems:"center",gap:"10px",padding:"9px 12px",cursor:"pointer"}}>
                      <div style={{
                        width:"15px",height:"15px",borderRadius:"3px",flexShrink:0,
                        border:`0.5px solid ${sel ? "var(--color-border-info)" : "var(--color-border-secondary)"}`,
                        background: sel ? "var(--color-text-info)" : "transparent",
                        display:"flex",alignItems:"center",justifyContent:"center",
                      }}>
                        {sel && <i className="ti ti-check" style={{fontSize:"10px",color:"#fff"}}/>}
                      </div>
                      <div style={{flex:1}}>
                        <p style={{margin:0,fontSize:"13px",fontWeight:"500",color:"var(--color-text-primary)"}}>{st.name}</p>
                        <p style={{margin:0,fontSize:"11px",color:"var(--color-text-secondary)"}}>:{st.port}</p>
                      </div>
                      <span style={{
                        fontSize:"10px",padding:"2px 7px",borderRadius:"999px",
                        background:"var(--color-background-secondary)",
                        color:"var(--color-text-secondary)",
                        border:"0.5px solid var(--color-border-tertiary)",
                      }}>{st.status}</span>
                    </div>
                    {sel && (
                      <div style={{padding:"0 12px 11px",borderTop:"0.5px solid var(--color-border-tertiary)"}}>
                        <label style={{...lbl,paddingTop:"9px",display:"block"}}>File for {st.name}</label>
                        {libraryLoading ? (
                          <p style={{fontSize:"12px",color:"var(--color-text-tertiary)",margin:0}}>Loading library…</p>
                        ) : (
                          <select value={files[st.name]||""} onChange={e=>setFiles(f=>({...f,[st.name]:e.target.value}))} style={{width:"100%"}}>
                            <option value="">— select a file —</option>
                            {library.map((f,i) => (
                              <option key={i} value={f.full_path}>{f.path}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Comment / notes */}
        <div style={{marginBottom:"16px"}}>
          <label style={lbl}>
            Comment
            <span style={{fontWeight:"400",color:"var(--color-text-tertiary)",marginLeft:"6px"}}>optional</span>
          </label>
          <textarea
            value={comment}
            onChange={e=>setComment(e.target.value)}
            placeholder="Internal note or description for this event…"
            maxLength={500}
            rows={2}
            style={{
              width:"100%",resize:"vertical",
              background:"var(--color-background-secondary)",
              border:"0.5px solid var(--color-border-primary)",
              borderRadius:"var(--border-radius-md)",
              color:"var(--color-text-primary)",
              font:"13px var(--font-sans)",
              padding:"7px 10px",
              outline:"none",
              lineHeight:"1.5",
            }}
          />
        </div>

        {err && (
          <div style={{padding:"8px 12px",borderRadius:"var(--border-radius-md)",
            background:"var(--color-background-danger)",border:"0.5px solid var(--color-border-danger)",
            fontSize:"12px",color:"var(--color-text-danger)",marginBottom:"14px"}}>{err}</div>
        )}

        <div style={{display:"flex",gap:"8px",justifyContent:"flex-end",alignItems:"center"}}>
          <button onClick={onClose}>Cancel</button>
          <button onClick={submit} disabled={submitting||(hasPastDateTime&&sortedDates.length===1)}
            style={{background:"var(--color-text-info)",color:"#fff",border:"none",
              opacity:(submitting||(hasPastDateTime&&sortedDates.length===1))?0.55:1}}>
            {submitting ? "Scheduling…" : sortedDates.length > 1 ? `Schedule for ${sortedDates.filter(ds=>!isPastDateTime(ds,time,todayStr)).length} date(s)` : "Schedule event"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EditModal — edit all fields of an existing event
// ---------------------------------------------------------------------------
function EditModal({ ev, streams, library, libraryLoading, todayStr, onClose, onSave, onDelete }) {
  const [streamName, setStreamName] = useState(ev.stream_name);
  const [filePath,   setFilePath]   = useState(ev.file_path || "");
  const [playAt,     setPlayAt]     = useState((ev.play_at_iso||ev.play_at||"").slice(0,16));
  const [postAction, setPostAction] = useState(ev.post_action || "resume");
  const [startPos,   setStartPos]   = useState(ev.start_pos  || "00:00:00");
  const [loopCount,  setLoopCount]  = useState(ev.loop_count !== undefined ? ev.loop_count : 0);
  const [comment,    setComment]    = useState(ev.comment || "");
  const [saving,     setSaving]     = useState(false);
  const [err,        setErr]        = useState("");

  const isPast = playAt && isPastDateTime(playAt.slice(0,10), playAt.slice(11,16), todayStr);

  const save = async () => {
    if (!streamName) { setErr("Stream is required."); return; }
    if (!filePath)   { setErr("File is required."); return; }
    if (!playAt)     { setErr("Date/time is required."); return; }
    if (isPast)      { setErr("Cannot reschedule to a past date/time."); return; }
    setSaving(true); setErr("");
    try {
      const res = await fetch("/api/action", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({
          action:      "update_event",
          event_id:    ev.event_id,
          stream_name: streamName,
          file_path:   filePath,
          play_at:     playAt,
          post_action: postAction,
          start_pos:   startPos,
          loop_count:  loopCount,
          comment:     comment.trim(),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.msg || "Failed");
      await onSave();
      onClose();
    } catch(e) {
      setErr(e.message);
      setSaving(false);
    }
  };

  const del = async () => {
    if (!confirm(`Delete this event for "${ev.stream_name}"?`)) return;
    await onDelete(ev.event_id);
    onClose();
  };

  return (
    <div style={{
      background:"var(--color-background-primary)",
      border:"0.5px solid var(--color-border-primary)",
      borderRadius:"var(--border-radius-lg)",
      width:"500px",maxHeight:"82vh",overflowY:"auto",
      boxShadow:"0 8px 32px rgba(0,0,0,0.22)",
    }}>
      <div style={{padding:"16px 20px",borderBottom:"0.5px solid var(--color-border-tertiary)",
        display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <p style={{margin:0,fontSize:"15px",fontWeight:"500",color:"var(--color-text-primary)"}}>
          Edit event
        </p>
        <button onClick={onClose} aria-label="Close"
          style={{background:"none",border:"none",cursor:"pointer",
            color:"var(--color-text-secondary)",fontSize:"20px",lineHeight:1,padding:"2px 6px"}}>×</button>
      </div>

      <div style={{padding:"18px 20px"}}>
        {/* Stream */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>Stream</label>
          <select value={streamName} onChange={e=>setStreamName(e.target.value)} style={{width:"100%"}}>
            {[...streams].sort((a,b)=>a.name.localeCompare(b.name)).map(st=>(
              <option key={st.name} value={st.name}>{st.name} :{st.port}</option>
            ))}
          </select>
        </div>

        {/* File */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>File</label>
          {libraryLoading ? (
            <p style={{fontSize:"12px",color:"var(--color-text-tertiary)",margin:0}}>Loading library…</p>
          ) : (
            <select value={filePath} onChange={e=>setFilePath(e.target.value)} style={{width:"100%"}}>
              <option value="">— select a file —</option>
              {library.map((f,i)=>(
                <option key={i} value={f.full_path}>{f.path}</option>
              ))}
            </select>
          )}
          {filePath && !library.find(f=>f.full_path===filePath) && (
            <p style={{fontSize:"11px",color:"var(--color-text-secondary)",margin:"4px 0 0",
              fontFamily:"var(--font-mono)",wordBreak:"break-all"}}>{filePath}</p>
          )}
        </div>

        {/* Date/time */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>Date &amp; time</label>
          <input type="datetime-local" value={playAt}
            onChange={e=>setPlayAt(e.target.value)}
            min={`${todayStr}T00:00`}
            style={{width:"230px"}}/>
          {isPast && (
            <p style={{fontSize:"11px",color:"var(--color-text-danger)",margin:"4px 0 0"}}>
              ⚠ This date/time is in the past
            </p>
          )}
        </div>

        {/* Start position */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>Start position <span style={{fontWeight:"400",color:"var(--color-text-tertiary)"}}>HH:MM:SS</span></label>
          <input value={startPos} onChange={e=>setStartPos(e.target.value)}
            placeholder="00:00:00" style={{width:"140px"}}/>
        </div>

        {/* Loop */}
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>Loop / repeat</label>
          <LoopSelector value={loopCount} onChange={setLoopCount}/>
        </div>

        {/* Post-action */}
        <div style={{marginBottom:"16px"}}>
          <label style={lbl}>After playback</label>
          <select value={postAction} onChange={e=>setPostAction(e.target.value)} style={{width:"100%"}}>
            <option value="resume">Return to normal schedule / compliance</option>
            <option value="stop">Stop stream</option>
            <option value="black">Show black screen</option>
          </select>
        </div>

        {/* Comment / notes */}
        <div style={{marginBottom:"16px"}}>
          <label style={lbl}>
            Comment
            <span style={{fontWeight:"400",color:"var(--color-text-tertiary)",marginLeft:"6px"}}>optional</span>
          </label>
          <textarea
            value={comment}
            onChange={e=>setComment(e.target.value)}
            placeholder="Internal note or description…"
            maxLength={500}
            rows={2}
            style={{
              width:"100%",resize:"vertical",
              background:"var(--color-background-secondary)",
              border:"0.5px solid var(--color-border-primary)",
              borderRadius:"var(--border-radius-md)",
              color:"var(--color-text-primary)",
              font:"13px var(--font-sans)",
              padding:"7px 10px",
              outline:"none",
              lineHeight:"1.5",
            }}
          />
        </div>

        {err && (
          <div style={{padding:"8px 12px",borderRadius:"var(--border-radius-md)",
            background:"var(--color-background-danger)",border:"0.5px solid var(--color-border-danger)",
            fontSize:"12px",color:"var(--color-text-danger)",marginBottom:"14px"}}>{err}</div>
        )}

        <div style={{display:"flex",gap:"8px",justifyContent:"space-between",alignItems:"center"}}>
          <button onClick={del}
            style={{fontSize:"12px",padding:"5px 12px",
              color:"var(--color-text-danger)",borderColor:"var(--color-border-danger)",
              display:"flex",alignItems:"center",gap:"4px"}}>
            <i className="ti ti-trash" style={{fontSize:"12px"}}/>Delete
          </button>
          <div style={{display:"flex",gap:"8px"}}>
            <button onClick={onClose}>Cancel</button>
            <button onClick={save} disabled={saving||isPast}
              style={{background:"var(--color-text-info)",color:"#fff",border:"none",
                opacity:(saving||isPast)?0.55:1}}>
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------
function Legend() {
  return (
    <div style={{display:"flex",alignItems:"center",gap:"10px",fontSize:"11px",color:"var(--color-text-secondary)"}}>
      {[
        ["var(--color-background-danger)","var(--color-border-danger)","Public Holiday"],
        ["var(--purple-dim)","var(--purple)","Custom Holiday"],
        ["var(--color-background-info)","var(--color-border-info)","Upcoming"],
        ["var(--color-background-success)","var(--color-border-success)","Played"],
      ].map(([bg,border,label]) => (
        <span key={label} style={{display:"flex",alignItems:"center",gap:"4px"}}>
          <span style={{width:"9px",height:"9px",borderRadius:"2px",
            background:bg,border:`0.5px solid ${border}`,display:"inline-block",flexShrink:0}}/>
          {label}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main EventsCalendar
// ---------------------------------------------------------------------------
function EventsCalendar() {
  const TODAY = new Date();
  const todayStr = fmtDate(TODAY);

  const [month,      setMonth]      = useState(TODAY.getMonth());
  const [year,       setYear]       = useState(TODAY.getFullYear());
  const [events,     setEvents]     = useState([]);
  const [streams,    setStreams]     = useState([]);
  const [library,    setLibrary]    = useState([]);
  const [libLoading, setLibLoading] = useState(false);
  const [settings,   setSettings]   = useState({ holiday_country:"US", holiday_subdiv:null });
  const [holidays,   setHolidays]   = useState({});
  const [holKey,     setHolKey]     = useState("");
  const [loading,    setLoading]    = useState(true);
  const [modal,      setModal]      = useState(null);   // null | "create" | "edit" | "settings"
  const [selDates,   setSelDates]   = useState(new Set());  // multi-date selection
  const [multiMode,  setMultiMode]  = useState(false);
  const [editEv,     setEditEv]     = useState(null);
  const [toast,      setToast]      = useState(null);
  const [hidePlayed, setHidePlayed] = useState(false);
  const libLoaded = useRef(false);
  const toastRef  = useRef(null);

  // Expose a global hook so vanilla-JS add/delete handlers can force a
  // holiday re-fetch by clearing holKey (bypasses the key === holKey guard).
  useEffect(() => {
    window.calendarRefreshHolidays = () => setHolKey("");
    return () => { try { delete window.calendarRefreshHolidays; } catch(_){} };
  }, []);

  const showToast = (msg, type="success") => {
    if (toastRef.current) clearTimeout(toastRef.current);
    setToast({ msg, type });
    toastRef.current = setTimeout(() => setToast(null), 3500);
  };

  const refreshEvents = useCallback(() =>
    fetch("/api/events").then(r=>r.json()).then(d=>{ if(Array.isArray(d)) setEvents(d); }).catch(()=>{}), []);

  // Keep the stream list current so the CreateModal never shows stale data.
  // Streams can become available after the initial mount (manager init race),
  // so we refresh on the same cadence as events.
  const refreshStreams = useCallback(() =>
    fetch("/api/streams").then(r=>r.json()).then(d=>{
      if(Array.isArray(d)) setStreams([...d].sort((a,b)=>a.name.localeCompare(b.name)));
    }).catch(()=>{}), []);

  // Initial load
  useEffect(() => {
    Promise.all([
      fetch("/api/streams").then(r=>r.json()).catch(()=>[]),
      fetch("/api/events").then(r=>r.json()).catch(()=>[]),
      fetch("/api/settings").then(r=>r.json()).catch(()=>({holiday_country:"US"})),
    ]).then(([str, evts, sett]) => {
      setStreams(Array.isArray(str) ? [...str].sort((a,b)=>a.name.localeCompare(b.name)) : []);
      setEvents(Array.isArray(evts) ? evts : []);
      setSettings(sett || {});
      setLoading(false);
    });
  }, []);

  // Holidays
  useEffect(() => {
    if (loading) return;
    const country = settings.holiday_country || "US";
    const subdiv  = settings.holiday_subdiv  || "";
    const key = `${year}:${country}:${subdiv}`;
    if (key === holKey) return;
    const qs = new URLSearchParams({ year, country });
    if (subdiv) qs.set("subdiv", subdiv);
    fetch(`/api/holidays?${qs}`)
      .then(r=>r.json())
      .then(data => {
        if (Array.isArray(data)) {
          const map = {};
          data.forEach(h => { map[h.date] = { name: h.name, source: h.source || "library" }; });
          setHolidays(map);
          setHolKey(key);
        }
      }).catch(()=>{});
  }, [year, settings, loading, holKey]);

  // Lazy-load library
  useEffect(() => {
    if ((modal === "create" || modal === "edit") && !libLoaded.current) {
      setLibLoading(true);
      fetch("/api/library")
        .then(r=>r.json())
        .then(data=>{ setLibrary(Array.isArray(data)?data:[]); libLoaded.current=true; })
        .catch(()=>{})
        .finally(()=>setLibLoading(false));
    }
  }, [modal]);

  // Poll events + streams every 15s.
  // Polling streams ensures the CreateModal always reflects reality even when
  // the manager wasn't fully initialised at the time the calendar tab mounted.
  useEffect(() => {
    const t = setInterval(() => { refreshEvents(); refreshStreams(); }, 15_000);
    return () => clearInterval(t);
  }, [refreshEvents, refreshStreams]);

  // Also refresh streams immediately when the create modal opens so the list
  // is always fresh regardless of where we are in the 15-second poll cycle.
  useEffect(() => {
    if (modal === "create") refreshStreams();
  }, [modal, refreshStreams]);

  // Calendar grid
  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month+1, 0).getDate();
  const cells = [];
  for (let i=0; i<firstDay; i++) cells.push(null);
  for (let d=1; d<=daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const eventsByDate = {};
  events.forEach(ev => {
    const d = getEventDate(ev);
    if (d) (eventsByDate[d] = eventsByDate[d] || []).push(ev);
  });
  // Sort each day's events ascending by time
  Object.keys(eventsByDate).forEach(d => {
    eventsByDate[d].sort((a,b) => getEventTime(a).localeCompare(getEventTime(b)));
  });

  // Handlers
  const prevMonth = () => month===0 ? (setMonth(11),setYear(y=>y-1)) : setMonth(m=>m-1);
  const nextMonth = () => month===11 ? (setMonth(0),setYear(y=>y+1)) : setMonth(m=>m+1);
  const goToday   = () => { setMonth(TODAY.getMonth()); setYear(TODAY.getFullYear()); };

  const openCreateSingle = (day, ds) => {
    if (isPastDate(ds, todayStr) && ds !== todayStr) return;
    setSelDates(new Set([ds]));
    setModal("create");
  };

  const toggleDateSelect = (ds) => {
    if (isPastDate(ds, todayStr) && ds !== todayStr) return;
    setSelDates(prev => {
      const n = new Set(prev);
      n.has(ds) ? n.delete(ds) : n.add(ds);
      return n;
    });
  };

  const openMultiCreate = () => {
    if (selDates.size === 0) { showToast("Select at least one date first.", "error"); return; }
    setModal("create");
  };

  const openEdit = (ev) => {
    if (ev.played) return;
    setEditEv(ev);
    setModal("edit");
  };

  const handleCreated = async (count) => {
    await refreshEvents();
    setSelDates(new Set());
    setMultiMode(false);
    showToast(`${count} event${count!==1?"s":""} scheduled`);
  };

  const handleDelete = async (evId) => {
    try {
      const res = await fetch("/api/action", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ action:"delete_event", event_id: evId }),
      });
      const data = await res.json();
      if (data.ok) {
        await refreshEvents();
        showToast("Event deleted");
      } else {
        showToast(data.msg || "Delete failed", "error");
      }
    } catch(e) {
      showToast("Delete failed", "error");
    }
  };

  if (loading) return (
    <div style={{display:"flex",alignItems:"center",justifyContent:"center",minHeight:"300px",
      fontSize:"14px",color:"var(--color-text-secondary)"}}>
      <i className="ti ti-loader-2" style={{fontSize:"20px",marginRight:"8px"}}/>
      Loading calendar…
    </div>
  );

  return (
    <div style={{position:"relative",display:"flex",flexDirection:"column",height:"100%",minHeight:"680px"}}>
      {/* Toast — bottom center */}
      {toast && (
        <div style={{
          position:"fixed",bottom:"28px",left:"50%",transform:"translateX(-50%)",
          zIndex:2000,
          padding:"10px 22px",borderRadius:"999px",
          background: toast.type==="error" ? "var(--color-background-danger)" : "var(--color-background-success)",
          color:      toast.type==="error" ? "var(--color-text-danger)"      : "var(--color-text-success)",
          border:`1px solid ${toast.type==="error" ? "var(--color-border-danger)" : "var(--color-border-success)"}`,
          fontSize:"13px",fontWeight:"600",
          boxShadow:"0 4px 24px rgba(0,0,0,0.28)",
          whiteSpace:"nowrap",
          animation:"toastIn 0.22s cubic-bezier(0.34,1.56,0.64,1)",
        }}>{toast.msg}</div>
      )}

      {/* Modal overlay */}
      {modal && (
        <div role="dialog" aria-modal="true"
          onClick={e=>{ if(e.target===e.currentTarget) setModal(null); }}
          style={{
            position:"fixed",inset:0,zIndex:1000,
            background:"rgba(0,0,0,0.48)",
            backdropFilter:"blur(6px)",
            WebkitBackdropFilter:"blur(6px)",
            display:"flex",alignItems:"flex-start",justifyContent:"center",
            paddingTop:"60px",overflowY:"auto",
          }}>
          {modal==="create" && (
            <CreateModal
              dates={selDates}
              holidays={holidays}
              streams={streams}
              library={library}
              libraryLoading={libLoading}
              todayStr={todayStr}
              onClose={()=>{ setModal(null); }}
              onCreate={handleCreated}
            />
          )}
          {modal==="edit" && editEv && (
            <EditModal
              ev={editEv}
              streams={streams}
              library={library}
              libraryLoading={libLoading}
              todayStr={todayStr}
              onClose={()=>{ setModal(null); setEditEv(null); }}
              onSave={refreshEvents}
              onDelete={async id=>{ await handleDelete(id); await refreshEvents(); }}
            />
          )}
        </div>
      )}

      {/* Calendar header */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
        padding:"12px 16px",borderBottom:"0.5px solid var(--color-border-tertiary)",flexWrap:"wrap",gap:"8px"}}>
        <div style={{display:"flex",alignItems:"center",gap:"6px"}}>
          <button onClick={prevMonth} aria-label="Previous month"
            style={{width:"28px",height:"28px",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <i className="ti ti-chevron-left" style={{fontSize:"15px"}}/>
          </button>
          <span style={{fontSize:"18px",fontWeight:"600",minWidth:"200px",textAlign:"center",letterSpacing:"-0.02em"}}>
            {MONTHS[month]} {year}
          </span>
          <button onClick={nextMonth} aria-label="Next month"
            style={{width:"28px",height:"28px",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <i className="ti ti-chevron-right" style={{fontSize:"15px"}}/>
          </button>
          <button onClick={goToday} style={{fontSize:"11px",padding:"4px 9px",marginLeft:"4px"}}>Today</button>
        </div>

        <div style={{display:"flex",alignItems:"center",gap:"8px",flexWrap:"wrap"}}>
          <Legend/>

          {/* Multi-date mode toggle */}
          <button
            onClick={()=>{ setMultiMode(m=>!m); setSelDates(new Set()); }}
            style={{
              fontSize:"11px",padding:"4px 10px",
              display:"flex",alignItems:"center",gap:"5px",
              background: multiMode ? "var(--color-background-info)" : "transparent",
              color:      multiMode ? "var(--color-text-info)"       : "var(--color-text-secondary)",
              border:`0.5px solid ${multiMode ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
            }}>
            <i className="ti ti-calendar-plus" style={{fontSize:"13px"}}/>
            {multiMode ? `${selDates.size} date${selDates.size!==1?"s":""} selected` : "Multi-date"}
          </button>

          {/* Schedule button (multi mode) */}
          {multiMode && selDates.size > 0 && (
            <button onClick={openMultiCreate}
              style={{fontSize:"11px",padding:"4px 10px",
                background:"var(--color-text-info)",color:"#fff",border:"none",
                display:"flex",alignItems:"center",gap:"5px"}}>
              <i className="ti ti-calendar-event" style={{fontSize:"13px"}}/>
              Schedule {selDates.size} date{selDates.size!==1?"s":""}
            </button>
          )}
        </div>
      </div>

      {/* Grid + sidebar */}
      <div style={{display:"flex",flex:1,overflow:"hidden"}}>
        <div style={{flex:"1 1 0",minWidth:0,overflow:"auto"}}>
          {/* Weekday headers */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(7,minmax(0,1fr))",
            borderBottom:"0.5px solid var(--color-border-tertiary)",
            position:"sticky",top:0,background:"var(--color-background-primary)",zIndex:2}}>
            {DAYS_SHORT.map(d => (
              <div key={d} style={{padding:"10px 0",textAlign:"center",fontSize:"13px",fontWeight:"600",
                color:"var(--color-text-secondary)",borderRight:"0.5px solid var(--color-border-tertiary)",
                letterSpacing:"0.03em"}}>
                {d}
              </div>
            ))}
          </div>
          {/* Day cells */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(7,minmax(0,1fr))"}}>
            {cells.map((day,idx) => (
              <DayCell
                key={idx}
                day={day}
                year={year}
                month={month}
                todayStr={todayStr}
                holidays={holidays}
                eventsByDate={eventsByDate}
                onOpen={openCreateSingle}
                selectedDates={selDates}
                onToggleSelect={toggleDateSelect}
                multiSelect={multiMode}
              />
            ))}
          </div>
        </div>

        <Sidebar
          month={month}
          year={year}
          events={events}
          holidays={holidays}
          onEdit={openEdit}
          onDelete={handleDelete}
          hidePlayed={hidePlayed}
          onToggleHidePlayed={()=>setHidePlayed(h=>!h)}
        />
      </div>
    </div>
  );
}

// Mount once DOM is ready
(function mountCalendar(){
  const root = document.getElementById('events-calendar-root');
  if (!root || !window.ReactDOM) return;

  class ErrorBoundary extends React.Component {
    constructor(p) { super(p); this.state = { err: null }; }
    static getDerivedStateFromError(e) { return { err: e }; }
    render() {
      if (this.state.err) return React.createElement('div', {
        style: {
          padding:'40px', textAlign:'center',
          color:'var(--red)', fontSize:'13px', lineHeight:'1.6'
        }
      }, '\u26a0 Events calendar failed to load: ' + this.state.err.message);
      return this.props.children;
    }
  }

  ReactDOM.createRoot(root).render(
    React.createElement(ErrorBoundary, null,
      React.createElement(EventsCalendar))
  );
})();
</script>
</body>
</html>

"""
