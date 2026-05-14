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
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

*{box-sizing:border-box;margin:0;padding:0}

/* ── Shared non-colour tokens ── */
:root{
  --font-sans:'Inter',system-ui,sans-serif;
  --font-display:'Plus Jakarta Sans',system-ui,sans-serif;
  --font-mono:'JetBrains Mono',monospace;
  --radius:10px;
  --radius-lg:14px;
}

/* ── Dark (default) ── */
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
}

/* ── Light ── */
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
}

/* ── Ocean ── deep blue/teal */
[data-theme="ocean"]{
  --bg:#0d1b2a;
  --bg2:#112233;
  --bg3:#152c40;
  --bg4:#1a3550;
  --border:#1e3d5a;
  --border2:#2a5070;
  --text:#d8eaf8;
  --text2:#8aafcc;
  --text3:#4a7a99;
  --green:#5ba88a;
  --green-dim:rgba(91,168,138,0.14);
  --red:#c06e7a;
  --red-dim:rgba(192,110,122,0.14);
  --yellow:#c8a84a;
  --yellow-dim:rgba(200,168,74,0.14);
  --blue:#5a9fd4;
  --blue-dim:rgba(90,159,212,0.12);
  --cyan:#4ac8d8;
  --purple:#8a78c8;
  --purple-dim:rgba(138,120,200,0.14);
  --accent:#2196b8;
  --accent-light:#38b8d8;
  --accent-gradient:linear-gradient(135deg,#2196b8 0%,#38b8d8 50%,#2aaccc 100%);
  --accent-gradient-hover:linear-gradient(135deg,#38b8d8 0%,#50cce8 50%,#38b8d8 100%);
  --shadow:rgba(0,0,0,0.45);
}

/* ── Midnight ── purple/indigo */
[data-theme="midnight"]{
  --bg:#0f0e17;
  --bg2:#15141f;
  --bg3:#1c1a2a;
  --bg4:#252334;
  --border:#2e2a42;
  --border2:#3d3858;
  --text:#ede8ff;
  --text2:#a89ec8;
  --text3:#60587a;
  --green:#6aaa82;
  --green-dim:rgba(106,170,130,0.14);
  --red:#cc7088;
  --red-dim:rgba(204,112,136,0.14);
  --yellow:#c8a85a;
  --yellow-dim:rgba(200,168,90,0.14);
  --blue:#7a8ccc;
  --blue-dim:rgba(122,140,204,0.12);
  --cyan:#68b8cc;
  --purple:#b898e8;
  --purple-dim:rgba(184,152,232,0.14);
  --accent:#8066cc;
  --accent-light:#a088e8;
  --accent-gradient:linear-gradient(135deg,#8066cc 0%,#a088e8 50%,#9070da 100%);
  --accent-gradient-hover:linear-gradient(135deg,#a088e8 0%,#b8a0f0 50%,#a088e8 100%);
  --shadow:rgba(0,0,0,0.50);
}

/* ── Forest ── green/earth */
[data-theme="forest"]{
  --bg:#0e1a14;
  --bg2:#121f18;
  --bg3:#182a1e;
  --bg4:#1e3326;
  --border:#213a29;
  --border2:#2e5038;
  --text:#e0f0e4;
  --text2:#88b894;
  --text3:#4a7255;
  --green:#68c87a;
  --green-dim:rgba(104,200,122,0.14);
  --red:#c07070;
  --red-dim:rgba(192,112,112,0.14);
  --yellow:#c8b858;
  --yellow-dim:rgba(200,184,88,0.14);
  --blue:#6898c8;
  --blue-dim:rgba(104,152,200,0.12);
  --cyan:#58c8a8;
  --purple:#9888b8;
  --purple-dim:rgba(152,136,184,0.14);
  --accent:#4a9a5a;
  --accent-light:#5aba6e;
  --accent-gradient:linear-gradient(135deg,#4a9a5a 0%,#5aba6e 50%,#52aa62 100%);
  --accent-gradient-hover:linear-gradient(135deg,#5aba6e 0%,#70cc82 50%,#5aba6e 100%);
  --shadow:rgba(0,0,0,0.45);
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
  background:#ffeec4;
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  font-size:15px;font-weight:900;color:#fff;flex-shrink:0;
  box-shadow:0 3px 10px rgba(255,238,196,0.45);
  transition:transform 0.2s,box-shadow 0.2s;
}
.logo-icon:hover{transform:scale(1.08);box-shadow:0 5px 16px rgba(255,238,196,0.55)}
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

/* ─────────── THEME PICKER ─────────── */
.theme-picker-wrap{position:relative;display:flex;align-items:center;flex-shrink:0}
.theme-picker-btn{
  background:var(--bg3);border:1px solid var(--border);color:var(--text2);
  cursor:pointer;font:500 12px var(--font-sans);padding:6px 12px;border-radius:20px;
  display:inline-flex;align-items:center;gap:7px;
  transition:all 0.22s;white-space:nowrap;
}
.theme-picker-btn:hover{border-color:var(--border2);color:var(--text);background:var(--bg4)}
.theme-picker-btn .theme-dot{
  width:10px;height:10px;border-radius:50%;flex-shrink:0;
  background:var(--accent);
  box-shadow:0 0 0 2px var(--bg3),0 0 0 3px var(--accent);
  transition:background 0.3s;
}
.theme-picker-dropdown{
  position:absolute;top:calc(100% + 8px);right:0;z-index:9999;
  background:var(--bg2);border:1px solid var(--border);
  border-radius:var(--radius-lg);padding:8px;
  min-width:180px;
  box-shadow:0 8px 32px var(--shadow);
  display:none;flex-direction:column;gap:2px;
  animation:fadeSlideIn 0.18s ease;
}
.theme-picker-dropdown.open{display:flex}
.theme-opt{
  display:flex;align-items:center;gap:10px;
  padding:8px 10px;border-radius:8px;
  cursor:pointer;font:500 13px var(--font-sans);color:var(--text2);
  transition:background 0.15s,color 0.15s;border:none;background:none;width:100%;
  text-align:left;
}
.theme-opt:hover{background:var(--bg3);color:var(--text)}
.theme-opt.active{background:var(--bg4);color:var(--text)}
.theme-opt .to-swatch{
  width:28px;height:18px;border-radius:5px;flex-shrink:0;
  border:1px solid rgba(255,255,255,0.08);
}
.to-swatch-dark   {background:linear-gradient(135deg,#1c1c1e 50%,#b87333 100%)}
.to-swatch-light  {background:linear-gradient(135deg,#f2f2f4 50%,#b87333 100%);border-color:rgba(0,0,0,0.12)}
.to-swatch-ocean  {background:linear-gradient(135deg,#0d1b2a 50%,#2196b8 100%)}
.to-swatch-midnight{background:linear-gradient(135deg,#0f0e17 50%,#8066cc 100%)}
.to-swatch-forest {background:linear-gradient(135deg,#0e1a14 50%,#4a9a5a 100%)}
.theme-opt .to-check{margin-left:auto;color:var(--accent);font-size:11px;opacity:0}
.theme-opt.active .to-check{opacity:1}

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
      ║      '/your- resources/logo.png';                               ║
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
    <button class="nav-tab" onclick="switchTab('media',this);if(!_fmLoaded){_fmLoaded=true;loadFiles('');}">
      <span class="tab-dot"></span>Media
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

    <!-- ── Holidays pill ── -->
    <div style="position:relative" id="hd-wrap">
      <button class="stat-pill" id="hd-btn" onclick="toggleHolidays(event)"
          title="Bangladesh Public Holidays"
          style="cursor:pointer;user-select:none;border-color:rgba(154,138,176,0.35)">
        🗓&nbsp;<b id="hd-next-label" style="color:var(--purple)">Holidays</b>
      </button>
      <div class="hd-popup" id="hd-popup" style="display:none">
        <div class="hd-popup-hdr">🇧🇩 Bangladesh Holidays &nbsp;<span id="hd-year" style="color:var(--accent-light)"></span></div>
        <div id="hd-list"><div style="padding:14px;text-align:center;color:var(--text3);font-size:12px">Loading…</div></div>
      </div>
    </div>

    <div class="theme-picker-wrap" id="theme-picker-wrap">
      <button class="theme-picker-btn" id="theme-picker-btn" onclick="toggleThemePicker()" title="Choose theme">
        <span class="theme-dot" id="theme-dot"></span>
        <span id="theme-label">Theme</span>
        <i class="fas fa-chevron-down" style="font-size:10px;opacity:0.6"></i>
      </button>
      <div class="theme-picker-dropdown" id="theme-picker-dropdown">
        <button class="theme-opt" data-theme="dark"      onclick="setTheme('dark')">
          <span class="to-swatch to-swatch-dark"></span>Dark
          <i class="fas fa-check to-check"></i>
        </button>
        <button class="theme-opt" data-theme="light"     onclick="setTheme('light')">
          <span class="to-swatch to-swatch-light"></span>Light
          <i class="fas fa-check to-check"></i>
        </button>
        <button class="theme-opt" data-theme="ocean"     onclick="setTheme('ocean')">
          <span class="to-swatch to-swatch-ocean"></span>Ocean
          <i class="fas fa-check to-check"></i>
        </button>
        <button class="theme-opt" data-theme="midnight"  onclick="setTheme('midnight')">
          <span class="to-swatch to-swatch-midnight"></span>Midnight
          <i class="fas fa-check to-check"></i>
        </button>
        <button class="theme-opt" data-theme="forest"    onclick="setTheme('forest')">
          <span class="to-swatch to-swatch-forest"></span>Forest
          <i class="fas fa-check to-check"></i>
        </button>
      </div>
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
            <span class="fm-dir-icon">📁</span> Media (root)
          </div>
        </div>
      </div>

      <!-- Main file list -->
      <div style="display:flex;flex-direction:column;overflow:hidden">
        <!-- Breadcrumb + toolbar -->
        <div style="padding:9px 14px;background:var(--bg3);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <div class="fm-breadcrumb" id="fm-breadcrumb" style="flex:1;min-width:0">
            <span onclick="loadFiles('')">Media</span>
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
      <select id="fm-move-dest" style="width:100%"><option value="">Media (root)</option></select>
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
      <select id="fm-copy-dest" style="width:100%"><option value="">Media (root)</option></select>
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
  <div class="section-hdr"><h2>Schedule Event</h2><span class="sep"></span></div>

  <!-- ── One-Shot form ── -->
  <div class="card">
    <div class="card-hdr">
      <i class="fa fa-calendar-plus" style="color:var(--accent);margin-right:6px"></i>
      <h3>One-Shot Event</h3>
      <span style="margin-left:auto;font-size:11px;color:var(--text3)">Select streams and assign a video to each</span>
    </div>
    <div class="card-body">

      <!-- Row 1: datetime + positions + after + submit -->
      <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(175px,1fr));margin-bottom:16px;gap:12px">
        <div class="fg">
          <label><i class="fa fa-clock" style="margin-right:4px;opacity:0.65"></i>Play at (local time) *</label>
          <input type="datetime-local" id="ev-dt">
        </div>
        <div class="fg">
          <label><i class="fa fa-step-forward" style="margin-right:4px;opacity:0.65"></i>Start position (HH:MM:SS)</label>
          <input type="text" id="ev-pos" value="00:00:00" placeholder="00:00:00"
                 pattern="\d{1,2}:\d{2}:\d{2}" title="Format: HH:MM:SS">
        </div>
        <div class="fg">
          <label style="display:flex;align-items:center;gap:6px">
            <i class="fa fa-step-backward" style="opacity:0.65"></i>End position
            <span style="font-size:10px;color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0">(optional)</span>
          </label>
          <input type="text" id="ev-end-pos" placeholder="leave blank = play to end"
                 pattern="\d{1,2}:\d{2}:\d{2}" title="Stop playback at this position (HH:MM:SS). Leave blank to play to end.">
        </div>
        <div class="fg"><label><i class="fa fa-redo" style="margin-right:4px;opacity:0.65"></i>After playback</label>
          <select id="ev-post">
            <option value="resume">Resume playlist</option>
            <option value="stop">Stop stream</option>
            <option value="black">Black screen</option>
          </select>
        </div>
        <div class="fg" style="justify-content:flex-end;align-self:flex-end">
          <button class="btn g" onclick="schedEvent()" title="Schedule events for all checked streams"
                  style="width:100%;justify-content:center;gap:8px;padding:9px 16px">
            <i class="fa fa-check"></i> Schedule All
          </button>
        </div>
      </div>
      <!-- Progress bar for bulk scheduling -->
      <div id="ev-sched-progress" style="display:none;margin-bottom:12px">
        <div style="font-size:11px;color:var(--text3);margin-bottom:5px" id="ev-sched-msg">Scheduling…</div>
        <div style="height:4px;background:var(--bg3);border-radius:2px;overflow:hidden">
          <div id="ev-sched-bar" style="height:100%;width:0%;background:var(--accent-gradient);border-radius:2px;transition:width 0.2s"></div>
        </div>
      </div>

      <!-- Row 2: stream + file grid -->
      <div style="margin-bottom:6px;display:flex;align-items:center;gap:10px">
        <label style="display:flex;align-items:center;gap:7px;cursor:pointer;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0">
          <input type="checkbox" id="ev-sel-all" style="width:auto;accent-color:var(--accent)"
                 onchange="evToggleAll(this.checked)" title="Select / deselect all streams">
          <b>Select All Streams</b>
        </label>
        <span style="font-size:11px;color:var(--text3)" id="ev-sel-count"></span>
      </div>

      <!-- Stream rows (stream checkbox + file selector each) -->
      <div class="ev-stream-grid" id="ev-stream-grid">
        <div style="padding:14px;text-align:center;color:var(--text3);font-size:12px">Loading streams…</div>
      </div>

    </div>
  </div>

  <!-- ── Scheduled Events table ── -->
  <div class="section-hdr">
    <h2>Scheduled Events</h2>
    <span class="sep"></span>
    <select id="ev-filter-stream" onchange="renderEventsTable()"
      title="Show events for a specific stream only"
      style="background:var(--bg3);border:1px solid var(--border);color:var(--text2);
             border-radius:var(--radius);padding:5px 10px;font-size:12px;font-family:var(--font-sans)">
      <option value="">All streams</option>
    </select>
    <select id="ev-filter-status" onchange="renderEventsTable()"
      title="Show only pending or already-played events"
      style="background:var(--bg3);border:1px solid var(--border);color:var(--text2);
             border-radius:var(--radius);padding:5px 10px;font-size:12px;font-family:var(--font-sans)">
      <option value="">All statuses</option>
      <option value="pending">Pending</option>
      <option value="played">Played</option>
    </select>
    <button class="btn r" onclick="clearPlayed()" title="Remove all events that have already been played">✕ Clear Played</button>
    <button class="btn b" onclick="loadEvents()" title="Refresh the events list now">↻</button>
    <label style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text3);cursor:pointer" title="Auto-refresh the events list every few seconds">
      <input type="checkbox" id="ev-autoref" checked style="width:auto;accent-color:var(--accent)"> Live
    </label>
  </div>
  <div class="card">
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Stream</th><th>File</th><th>Play At</th>
          <th>Countdown</th><th>Position</th><th>After</th><th>Status</th><th style="text-align:right">Actions</th>
        </tr></thead>
        <tbody id="evtbl"><tr><td colspan="8"><div class="empty"><div class="empty-icon">📅</div>Loading…</div></td></tr></tbody>
      </table>
    </div>
  </div>



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
  <div class="section-hdr"><h2>Application Settings</h2><span class="sep"></span></div>
  <div class="settings-grid">
    <!-- UI Preferences -->
    <div class="setting-card">
      <h3>UI Preferences</h3>
      <div class="setting-row">
        <div><div class="setting-label">Auto-refresh streams</div><div class="setting-desc">Poll every 2.5 seconds</div></div>
        <div class="toggle on" id="st-autoref" onclick="toggleSetting('autoref',this)" title="Poll stream status every 2.5 seconds"></div>
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

    <!-- Notifications -->
    <div class="setting-card">
      <h3>Notifications</h3>
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
        <select id="st-stats-interval" style="width:100px" title="How often to refresh CPU and RAM stats in the header">
          <option value="5000">5 s</option>
          <option value="8000" selected>8 s</option>
          <option value="15000">15 s</option>
        </select>
      </div>
      <div class="setting-row">
        <div class="setting-label">Log auto-refresh</div>
        <select id="st-log-interval" style="width:100px" title="How often to reload the log view when Auto-scroll is on">
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

  <!-- Mail Alerts -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2>Mail Alerts</h2><span class="sep"></span>
      <button class="btn b" onclick="loadMailConfig()" title="Load saved mail alert settings from disk">↻ Load</button>
    </div>
    <div class="card card-body" style="padding:16px">

      <!-- Mode tabs -->
      <div style="display:flex;gap:0;margin-bottom:16px;border-bottom:1px solid var(--border)">
        <button id="ml-tab-gmail" class="nav-tab active" onclick="switchMailMode('gmail_oauth2')"
          style="padding:8px 18px;font-size:12px" title="Use Gmail via OAuth2 — no password stored">
          <span class="tab-dot"></span>Gmail (OAuth2)
        </button>
        <button id="ml-tab-ms" class="nav-tab" onclick="switchMailMode('microsoft_oauth2')"
          style="padding:8px 18px;font-size:12px" title="Use Outlook / Office 365 via Microsoft OAuth2">
          <span class="tab-dot"></span>Microsoft (OAuth2)
        </button>
        <button id="ml-tab-smtp" class="nav-tab" onclick="switchMailMode('smtp')"
          style="padding:8px 18px;font-size:12px" title="Use Yahoo Mail, Gmail App Password, or a custom SMTP server">
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
          <button class="btn b" style="margin-left:auto" onclick="connectGmail()" title="Open Google sign-in to authorise HydraCast to send email">🔗 Connect Gmail</button>
          <button class="btn r" id="ml-gmail-revoke" style="display:none" onclick="revokeGmail()" title="Remove stored Gmail OAuth2 credentials">✕ Disconnect</button>
        </div>
        <div id="ml-gmail-poll-msg" style="font-size:11px;color:var(--yellow);margin-bottom:12px;display:none">
          ⏳ Waiting for Google sign-in in browser… <button class="btn" style="margin-left:8px" onclick="checkOAuthStatus()" title="Check whether Google sign-in has completed">Check Status</button>
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
          <button class="btn b" style="margin-left:auto" onclick="connectMicrosoft()" title="Start Microsoft device sign-in to authorise HydraCast to send email">🔗 Connect Microsoft</button>
          <button class="btn r" id="ml-ms-revoke" style="display:none" onclick="revokeMicrosoft()" title="Remove stored Microsoft OAuth2 credentials">✕ Disconnect</button>
        </div>
        <div id="ml-ms-device-box" style="display:none;background:var(--bg3);border:1px solid rgba(251,191,36,0.5);
            border-radius:8px;padding:14px;margin-bottom:14px;font-size:12px">
          <div style="color:var(--yellow);font-weight:600;margin-bottom:8px">🔐 Device Sign-in Required</div>
          <div>1. Open <a id="ml-ms-uri" href="https://microsoft.com/devicelogin" target="_blank" style="color:var(--blue)">https://microsoft.com/devicelogin</a></div>
          <div style="margin:6px 0">2. Enter code: <code id="ml-ms-code" style="color:var(--accent-light);font-size:15px;font-weight:700;letter-spacing:3px">——————</code></div>
          <div style="color:var(--text3)">3. Sign in, then click Check Status below.</div>
          <button class="btn" style="margin-top:10px" onclick="checkMsOAuthStatus()" title="Check whether Microsoft device sign-in has completed">↻ Check Status</button>
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
          <button class="btn" onclick="smtpPreset('yahoo')" style="font-size:10px" title="Fill in Yahoo Mail SMTP settings">Yahoo</button>
          <button class="btn" onclick="smtpPreset('gmail')" style="font-size:10px" title="Fill in Gmail App Password SMTP settings">Gmail SMTP</button>
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
          <button class="btn g" onclick="saveMailConfig()" title="Save mail alert configuration to disk">💾 Save Config</button>
          <div class="fg" style="flex-direction:row;gap:6px;align-items:center;flex:1;min-width:200px">
            <input id="ml-test-to" placeholder="Test recipient (optional)" style="flex:1" title="Optional: override the To address just for this test email">
            <button class="btn b" onclick="testMailAlert()" title="Send a test email to verify your mail settings">✉ Send Test</button>
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
          <div id="restore-status" style="font-size:11px;color:var(--text3);margin-top:8px"></div>
        </div>

      </div>
    </div>
  </div>

  <!-- ── Stream Source Selector ── -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2>Stream Source</h2><span class="sep"></span></div>
    <div class="card card-body" style="padding:16px">
      <div style="font-size:12px;color:var(--text2);margin-bottom:14px;line-height:1.7">
        Pick a stream, then choose a <b>folder</b> (auto-scanned) or individual <b>files</b> as its media source.
        Changes are saved immediately and the stream is restarted.
      </div>

      <!-- Stream picker -->
      <div class="form-grid" style="grid-template-columns:1fr 1fr;margin-bottom:14px">
        <div class="fg">
          <label>Stream</label>
          <select id="ss-stream" onchange="ssLoadSource()" title="Pick the stream to modify">
            <option value="">— select a stream —</option>
          </select>
        </div>
        <div class="fg">
          <label>Source type</label>
          <div style="display:flex;gap:0;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;height:38px">
            <button id="ss-tab-folder" class="nav-tab active"
                    style="flex:1;border-radius:0;border:none;border-right:1px solid var(--border);font-size:12px;padding:0 14px"
                    onclick="ssSwitchMode('folder')" title="Use a folder — all supported files inside are scanned automatically">
              📁 Folder
            </button>
            <button id="ss-tab-files" class="nav-tab"
                    style="flex:1;border-radius:0;border:none;font-size:12px;padding:0 14px"
                    onclick="ssSwitchMode('files')" title="Pick one or more individual files from the media library">
              🎬 Files
            </button>
          </div>
        </div>
      </div>

      <!-- FOLDER mode -->
      <div id="ss-panel-folder">
        <div class="fg" style="margin-bottom:12px">
          <label>Folder path (relative to media root)</label>
          <div style="display:flex;gap:8px;align-items:center">
            <select id="ss-folder-select" style="flex:1" title="Choose a folder from the media library">
              <option value="">— loading folders… —</option>
            </select>
            <button class="btn b" onclick="ssRefreshFolders()" title="Reload the folder list from the server" style="white-space:nowrap">↻ Refresh</button>
          </div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px">
          <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
            <input type="checkbox" id="ss-shuffle" style="width:auto;accent-color:var(--accent)"> Shuffle playback
          </label>
        </div>
      </div>

      <!-- FILES mode -->
      <div id="ss-panel-files" style="display:none">
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
          <select id="ss-file-browser" style="flex:1;min-width:0" title="Browse available media files">
            <option value="">— loading files… —</option>
          </select>
          <button class="btn b" onclick="ssAddFile()" title="Add the selected file to the list below" style="white-space:nowrap">＋ Add</button>
          <button class="btn" onclick="ssRefreshFiles()" title="Reload file list from the server" style="white-space:nowrap">↻</button>
        </div>
        <!-- Selected files list -->
        <div id="ss-file-list" style="background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);min-height:64px;max-height:200px;overflow-y:auto">
          <div id="ss-file-empty" style="padding:20px;text-align:center;color:var(--text3);font-size:12px">No files selected yet.</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px;margin-bottom:4px">
          <label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text2);text-transform:none;letter-spacing:0;cursor:pointer">
            <input type="checkbox" id="ss-files-shuffle" style="width:auto;accent-color:var(--accent)"> Shuffle playback
          </label>
        </div>
      </div>

      <!-- Action row -->
      <div style="display:flex;gap:8px;align-items:center;margin-top:14px;flex-wrap:wrap">
        <button class="btn g" onclick="ssApply()" title="Save this source to the stream and restart it">💾 Apply &amp; Restart</button>
        <button class="btn" onclick="ssClear()" title="Clear the selection">✕ Clear</button>
        <span id="ss-status" style="font-size:11px;color:var(--text3)"></span>
      </div>
    </div>
  </div>

  <!-- Danger Zone -->
  <div style="margin-top:4px">
    <div class="section-hdr"><h2 style="color:var(--red)">Danger Zone</h2><span class="sep"></span></div>
    <div class="card card-body" style="border-color:rgba(248,113,113,0.2);padding:16px">
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <button class="btn r" onclick="if(confirm('Stop ALL streams?')) api('stop_all',{})" title="Immediately stop every running stream">■ Stop All Streams</button>
        <button class="btn r" onclick="if(confirm('Restart ALL streams?')) api('restart_all',{})" title="Stop and restart every stream">↺ Restart All</button>
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
  else if(name==='events'){loadEvtForm();loadEvents();if(!_hdLoaded)loadHolidays();_startEvTimers();}
  else if(name==='viewer'){loadViewer();}
  else if(name==='config'){loadConfig();}
  else if(name==='settings'){updateSysInfo();loadMailConfig();ssInit();}
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
      if(wasAuto) _autoTimer=setInterval(loadStreams,2500);
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
         s.current_file||''].join('|');
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
  let data;
  try{
    data=await fetch('/api/streams').then(r=>r.json());
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

    if(!existing[s.name]){
      // ── First render: create the full card ──
      const div=document.createElement('div');
      div.className='stream-card'+(isLive||isEvent?' is-live':'');
      div.dataset.vname=s.name;
      div.innerHTML=`
        <div class="stream-card-header">
          <span class="badge vc-badge-${esc(s.name)}">${esc(status)}</span>
          <span class="stream-card-title">${esc(s.name)}</span>
          <span style="font-size:11px;color:var(--accent-light)">:${s.port}</span>
        </div>
        ${nowFile?`<div class="vc-nowplaying-${esc(s.name)}" style="padding:5px 14px 0;display:flex;align-items:center;gap:5px;min-width:0;overflow:hidden">
          <span style="font-size:9px;font-weight:700;flex-shrink:0;letter-spacing:0.04em;text-transform:uppercase;${isEvent?'color:var(--purple)':'color:var(--accent-light)'}">${isEvent?'EVENT':'PLAYLIST'}</span>
          <span style="font-size:10px;font-family:var(--font-mono);color:${isEvent?'var(--purple)':'var(--text2)'};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;background:${isEvent?'var(--purple-dim)':'var(--bg3)'};border:1px solid ${isEvent?'rgba(154,138,176,0.3)':'var(--border)'};border-radius:4px;padding:2px 8px"
                title="${esc(nowFile)}">${esc(nowFile)}</span>
        </div>`:`<div class="vc-nowplaying-${esc(s.name)}" style="padding:5px 14px 0;height:22px"></div>`}
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
            <div class="stat-item">FPS <b class="vc-fps-${esc(s.name)}">${s.fps>0?Math.round(s.fps)+'fps':'—'}</b></div>
            <div class="stat-item">Pos <b class="vc-pos-${esc(s.name)}">${esc(s.position||'—')}</b></div>
            <div class="stat-item"><b class="vc-pct-${esc(s.name)}">${pct}%</b></div>
          </div>
          <div class="btn-group">
            <button class="btn b vc-copy-${esc(s.name)}" style="font-size:10px;padding:3px 8px" data-hls="${esc(s.hls_url||'')}" data-rtsp="${esc(s.rtsp_url||'')}" onclick="copyText(this.dataset.hls||this.dataset.rtsp)" title="Copy stream URL to clipboard">📋</button>
          </div>
        </div>
        <div style="padding:0 14px 10px">
          <div class="prog vc-prog-${esc(s.name)}" style="height:5px;border-radius:3px">
            <div class="prog-fill vc-progfill-${esc(s.name)}" style="width:${pct}%;background:${isEvent?'var(--purple)':+pct>80?'var(--red)':+pct>55?'var(--yellow)':'var(--green)'}"></div>
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
      const safeName=s.name.replace(/[^a-zA-Z0-9_-]/g,'');
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
  const fullName=_fmCurrentPath?_fmCurrentPath+'/'+n.trim():n.trim();
  const r=await api('create_subdir',{name:fullName});
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

async function loadHolidays(){
  try{
    const data = await fetch('/api/holidays').then(r=>r.json());
    if(!Array.isArray(data)){ throw new Error('bad response'); }
    _hdData = data;
    _hdLoaded = true;
    const today = new Date().toISOString().slice(0,10);
    const yr    = today.slice(0,4);
    document.getElementById('hd-year').textContent = yr;
    // Set next upcoming holiday label in pill
    const upcoming = _hdData.filter(h=>h.date >= today);
    if(upcoming.length){
      const next = upcoming[0];
      const d = new Date(next.date + 'T00:00:00');
      const label = d.toLocaleDateString('en-US',{month:'short',day:'numeric'});
      document.getElementById('hd-next-label').textContent = label;
    }
    // Render list
    const list = document.getElementById('hd-list');
    if(!_hdData.length){
      list.innerHTML='<div style="padding:14px;text-align:center;color:var(--text3);font-size:12px">No holiday data available</div>';
      return;
    }
    list.innerHTML = _hdData.map(h=>{
      const isPast   = h.date < today;
      const isToday  = h.date === today;
      return `<div class="hd-row${isPast?' past':''}${isToday?' today':''}">
        <div class="hd-date">${esc(h.date)}</div>
        <div class="hd-name">${esc(h.name)}</div>
        ${isToday?'<div class="hd-today-tag">TODAY</div>':''}
      </div>`;
    }).join('');
    // Holidays loaded — calendar removed
  }catch(e){
    document.getElementById('hd-list').innerHTML = '<div style="padding:14px;color:var(--red);font-size:12px">⚠ Failed to load holidays. Ensure the <code>holidays</code> Python package is installed.</div>';
  }
}

// ═══════════════════════════════════
// EVENTS
// ═══════════════════════════════════
let _evData = [];          // cached event list from server
let _evTimer = null;       // auto-refresh interval
let _evCountdown = null;   // per-second countdown ticker
let _evStreams = [];        // cached stream list
let _evLib    = [];        // cached file library

async function loadEvtForm(){
  try{
    const[streams,lib]=await Promise.all([
      fetch('/api/streams').then(r=>r.json()),
      fetch('/api/library').then(r=>r.json()),
    ]);
    _evStreams = streams;
    _evLib    = lib;

    // Build stream-grid rows
    const grid = document.getElementById('ev-stream-grid');
    if(!streams.length){
      grid.innerHTML = '<div style="padding:14px;text-align:center;color:var(--text3);font-size:12px">No streams configured.</div>';
    } else {
      const fileOpts = lib.map(f=>`<option value="${esc(f.full_path)}">${esc(f.path)} (${esc(f.duration||'?')})</option>`).join('');
      grid.innerHTML = streams.map((s,i)=>`
        <div class="ev-stream-row" id="ev-row-${i}">
          <label>
            <input type="checkbox" class="ev-stream-cb" data-idx="${i}"
              style="width:auto;accent-color:var(--accent)"
              onchange="evRowToggle(${i},this.checked)">
            <span style="overflow:hidden;text-overflow:ellipsis;max-width:140px;white-space:nowrap"
                  title="${esc(s.name)}">${esc(s.name)}</span>
            <span style="font-size:10px;color:var(--text3)">:${s.port}</span>
          </label>
          <select id="ev-file-${i}" disabled title="Video file for ${esc(s.name)}">
            ${fileOpts}
          </select>
        </div>`).join('');
    }

    // Set default datetime
    const dt=new Date(Date.now()+5*60000);
    document.getElementById('ev-dt').value=
      new Date(dt-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);

    // Populate stream filter dropdown
    const fsel = document.getElementById('ev-filter-stream');
    const prev = fsel.value;
    fsel.innerHTML = '<option value="">All streams</option>' +
      streams.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
    if(prev) fsel.value = prev;

    evUpdateSelCount();
  }catch(e){ console.warn('loadEvtForm:', e); }
}

function evRowToggle(idx, checked){
  const row = document.getElementById('ev-row-'+idx);
  const sel = document.getElementById('ev-file-'+idx);
  if(row){ row.classList.toggle('checked', checked); }
  if(sel){ sel.disabled = !checked; }
  evUpdateSelCount();
}

function evToggleAll(checked){
  document.querySelectorAll('.ev-stream-cb').forEach((cb,i)=>{
    cb.checked = checked;
    evRowToggle(i, checked);
  });
}

function evUpdateSelCount(){
  const total   = document.querySelectorAll('.ev-stream-cb').length;
  const checked = document.querySelectorAll('.ev-stream-cb:checked').length;
  const el = document.getElementById('ev-sel-count');
  if(el) el.textContent = checked ? `${checked} / ${total} selected` : '';
  const allCb = document.getElementById('ev-sel-all');
  if(allCb) allCb.checked = checked > 0 && checked === total;
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
      `<tr><td colspan="8"><div class="empty"><div class="empty-icon">📅</div>No events${filterStream||filterStatus?' matching filter':' scheduled'}.</div></td></tr>`;
    return;
  }
  const now = Date.now();
  document.getElementById('evtbl').innerHTML = rows.map(ev=>{
    const secsNow = Math.round((new Date(ev.play_at_iso||ev.play_at.replace(' ','T')) - now)/1000);
    const imminent = !ev.played && secsNow >= 0 && secsNow < 300;
    const past     = !ev.played && secsNow < 0;
    const cdColor  = ev.played ? 'var(--text3)' : imminent ? 'var(--yellow)' : past ? 'var(--red)' : 'var(--accent-light)';
    const rowStyle = imminent ? 'background:rgba(201,168,120,0.06)' : '';
    const cdText   = ev.played ? '—' : _fmtCountdown(secsNow);
    const fireBtn  = !ev.played
      ? `<button class="btn" style="font-size:10px;padding:3px 8px;color:var(--yellow);border-color:rgba(201,168,120,0.4)"
           onclick="fireNow('${esc(ev.event_id)}')" title="Fire this event right now, skipping the scheduled time">▶ Now</button>`
      : '';
    const posStr = ev.start_pos && ev.start_pos !== '00:00:00'
      ? (ev.end_pos ? `${esc(ev.start_pos)} → ${esc(ev.end_pos)}` : `▶ ${esc(ev.start_pos)}`)
      : (ev.end_pos ? `→ ${esc(ev.end_pos)}` : '<span style="color:var(--text3)">—</span>');
    return `<tr style="${rowStyle}">
      <td style="color:var(--accent-light)">${esc(ev.stream_name)}</td>
      <td class="td-muted" title="${esc(ev.file_path||ev.file_name)}">${esc(ev.file_name)}</td>
      <td class="td-muted" style="white-space:nowrap;font-family:var(--font-mono);font-size:11px">${esc(ev.play_at)}</td>
      <td class="ev-cd" data-secs="${secsNow}" data-played="${ev.played?1:0}" style="font-size:11px;color:${cdColor};white-space:nowrap">${cdText}</td>
      <td class="td-muted" style="font-size:11px;font-family:var(--font-mono);white-space:nowrap">${posStr}</td>
      <td class="td-muted" style="font-size:11px">${esc(ev.post_action||'resume')}</td>
      <td><span class="badge ${ev.played?'STOPPED':'SCHED'}">${ev.played?'✓ Played':'⏰ Pending'}</span></td>
      <td style="text-align:right;white-space:nowrap;display:flex;gap:4px;justify-content:flex-end">
        ${fireBtn}
        <button class="btn r" style="font-size:10px;padding:3px 8px" onclick="delEvent('${esc(ev.event_id)}')" title="Delete this scheduled event">✕</button>
      </td>
    </tr>`;
  }).join('');
}

function _tickCountdowns(){
  // Update only the countdown cells every second — no full re-render
  document.querySelectorAll('.ev-cd').forEach(cell=>{
    if(cell.dataset.played==='1'){ cell.textContent='—'; return; }
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
  const dt      = document.getElementById('ev-dt').value;
  const pos     = (document.getElementById('ev-pos').value||'00:00:00').trim();
  const endPos  = (document.getElementById('ev-end-pos')?.value||'').trim();
  const post    = document.getElementById('ev-post').value;

  if(!dt){ toast('Set a date/time first','err'); return; }

  // Validate start position format
  const hmsRe = /^\d{1,2}:\d{2}:\d{2}$/;
  const startPosVal = hmsRe.test(pos) ? pos : '00:00:00';
  const endPosVal   = endPos && hmsRe.test(endPos) ? endPos : '';

  const checked = Array.from(document.querySelectorAll('.ev-stream-cb:checked'));
  if(!checked.length){ toast('Select at least one stream','err'); return; }

  // Validate all files before starting any requests
  const tasks = [];
  const missingFile = [];
  for(const cb of checked){
    const idx    = parseInt(cb.dataset.idx);
    const stream = _evStreams[idx];
    if(!stream) continue;
    const fileSel = document.getElementById('ev-file-'+idx);
    const file    = fileSel ? fileSel.value.trim() : '';
    if(!file){ missingFile.push(stream.name); continue; }
    tasks.push({stream, file});
  }
  if(missingFile.length){
    toast(`No file for: ${missingFile.join(', ')}`, 'err');
    return;
  }

  // Show progress bar
  const progWrap = document.getElementById('ev-sched-progress');
  const progBar  = document.getElementById('ev-sched-bar');
  const progMsg  = document.getElementById('ev-sched-msg');
  if(progWrap){ progWrap.style.display=''; progBar.style.width='0%'; }

  let scheduled = 0, errors = 0;
  const errMsgs = [];

  for(let i=0; i<tasks.length; i++){
    const {stream, file} = tasks[i];
    if(progMsg) progMsg.textContent = `Scheduling ${stream.name} (${i+1}/${tasks.length})…`;
    if(progBar) progBar.style.width = Math.round((i/tasks.length)*100)+'%';
    try{
      const payload = {
        stream_name: stream.name,
        file_path:   file,
        play_at:     dt,
        start_pos:   startPosVal,
        post_action: post,
      };
      if(endPosVal) payload.end_pos = endPosVal;
      const r = await fetch('/api/add_event',{
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const j = await r.json();
      if(j.ok){ scheduled++; }
      else{ errMsgs.push(`${stream.name}: ${j.msg||'Error'}`); errors++; }
    }catch(e){
      errMsgs.push(`${stream.name}: Network error`);
      errors++;
    }
  }

  // Complete progress bar
  if(progBar) progBar.style.width='100%';
  if(progMsg){
    progMsg.textContent = scheduled
      ? `✓ Scheduled ${scheduled} event${scheduled>1?'s':''}${errors?' · '+errors+' failed':''}${errMsgs.length?' — '+errMsgs[0]:''}`
      : `✕ All ${errors} failed`;
    progMsg.style.color = errors ? 'var(--red)' : 'var(--green)';
  }
  setTimeout(()=>{ if(progWrap) progWrap.style.display='none'; if(progMsg) progMsg.style.color=''; }, 4000);

  if(scheduled > 0){
    toast(`Scheduled ${scheduled} event${scheduled>1?'s':''}${errors?' ('+errors+' failed)':''}`, errors?'info':'ok');
    await loadEvents();
  } else if(errors > 0){
    toast(errMsgs[0]||'All events failed to schedule', 'err');
  }
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
        <div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr));margin-top:4px">
          <div class="fg">
            <label title="How often (seconds) HydraCast re-checks position against the expected broadcast offset. Minimum 60 s.">Resync interval (seconds)</label>
            <input id="cfg-comp-resync-interval" type="number" min="60" step="60"
                   value="${s.compliance_resync_interval??7200}" placeholder="7200">
          </div>
          <div class="fg">
            <label title="Maximum tolerated drift (seconds) before a hard resync is triggered. 0 = always resync on every check.">Drift threshold (seconds)</label>
            <input id="cfg-comp-drift-threshold" type="number" min="0" step="1"
                   value="${s.compliance_drift_threshold??30}" placeholder="30">
          </div>
        </div>
        <div class="st-comp-row" style="margin-top:2px">
          <label for="cfg-comp-alert" style="flex:1;font-size:12px;color:var(--text2);cursor:pointer;text-transform:none;letter-spacing:0">
            Show banner alerts when compliance file is missing or seek fails
            <small>Displays a pulsing error banner in the Web UI until dismissed</small>
          </label>
          <input type="checkbox" id="cfg-comp-alert" ${s.compliance_alert_enabled!==false?'checked':''}
                 style="width:auto;accent-color:var(--accent);flex-shrink:0">
        </div>
        <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
          <button class="btn" style="font-size:11px;padding:4px 12px"
                  title="Immediately seek this stream to its correct compliance position right now"
                  onclick="complianceResyncNow('${esc(s.name)}',this)">
            &#x21BA; Resync Now
          </button>
          <span id="cfg-comp-resync-status" style="font-size:11px;color:var(--text3)"></span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:4px">
          When enabled, HydraCast calculates the correct playback seek offset so the stream matches a continuous linear broadcast that started at the configured time today.
          Periodic drift checks run every <em>resync interval</em> seconds and trigger a hard seek when drift exceeds the threshold.
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
    compliance_resync_interval:parseFloat(document.getElementById('cfg-comp-resync-interval')?.value)||7200,
    compliance_drift_threshold:parseFloat(document.getElementById('cfg-comp-drift-threshold')?.value)||30,
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
  _playlistItems.sort((a,b)=>a.priority-b.priority);
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
  _playlistItems.sort((a,b)=>a.priority-b.priority);
  _renderPLTable(cid);
}
function _plAdd(cid){
  const inp=document.getElementById(cid+'-new');if(!inp)return;
  const raw=inp.value.trim();if(!raw){toast('Enter a file path','err');return;}
  const parsed=_parsePL(raw);if(!parsed.length){toast('Invalid path','err');return;}
  _playlistItems.push(...parsed);
  _playlistItems.sort((a,b)=>a.priority-b.priority);
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
  if(ta){_playlistItems=_parsePL(ta.value);_playlistItems.sort((a,b)=>a.priority-b.priority);_markDirty();}
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
    video_bitrate:(document.getElementById('new-vbr')?.value||'2500k').trim()||'2500k',
    audio_bitrate:(document.getElementById('new-abr')?.value||'128k').trim()||'128k',
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
  if(!confirm(`Delete stream "${name}"?\n\nThis will remove it from streams.json immediately. The stream will be stopped if it is currently running.`))return;
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
};

function mbOpen(mode, target) {
  _mb.mode    = mode;
  _mb.target  = target;
  _mb.path    = '';
  _mb.selected = null;
  _mb.loading  = false;

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
  _playlistItems.sort((a,b)=>a.priority-b.priority);
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

  const listing = document.getElementById('mb-listing');
  const sidebar = document.getElementById('mb-sidebar');
  const statusBar = document.getElementById('mb-status-bar');

  listing.innerHTML = '<div class="fm-empty"><div class="empty-icon" style="animation:spin 1s linear infinite;font-size:28px">⟳</div></div>';
  statusBar.textContent = 'Loading…';

  try {
    // Load current dir + root dirs in parallel
    const [data, rootData] = await Promise.all([
      fetch('/api/files?path=' + encodeURIComponent(path)).then(r => r.json()),
      path ? fetch('/api/files?path=').then(r => r.json()).catch(() => ({dirs:[]})) : Promise.resolve(null),
    ]);

    if (data.error) {
      listing.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>${esc(data.error)}</div></div>`;
      statusBar.textContent = 'Error loading folder';
      _mb.loading = false;
      return;
    }

    // ── Breadcrumb ────────────────────────────────────────────
    const bc = document.getElementById('mb-breadcrumb');
    bc.innerHTML = (data.breadcrumb || [{name:'Media', path:''}]).map((crumb, i, arr) => {
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
    const rootDirs = (rootData || data).dirs || [];
    if (!path) _mb.rootDirs = rootDirs;
    sidebar.innerHTML =
      `<div onclick="_mbLoad('')"
            style="padding:9px 14px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:12px;
                   border-bottom:1px solid var(--border);transition:background 0.12s;
                   ${!path ? 'background:rgba(184,115,51,0.09);border-left:2px solid var(--accent);padding-left:12px;color:var(--accent)' : 'color:var(--text2)'}"
            onmouseover="this.style.background='var(--bg3)'"
            onmouseout="this.style.background='${!path?'rgba(184,115,51,0.09)':''}'"
            title="Media root directory">
         <span style="opacity:0.65">📁</span> Media (root)
       </div>` +
      (_mb.rootDirs.length ? _mb.rootDirs : rootDirs).map(d => {
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

    // In folder mode: the current dir is itself selectable
    if (isFolderMode) {
      const curLabel = path ? (data.breadcrumb || []).slice(-1)[0]?.name || path.split('/').pop() : 'Media (root)';
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

    // Sub-folders
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
          <span style="font-size:11px;color:var(--text3);font-family:var(--font-mono)">${d.items} item${d.items!==1?'s':''}</span>
          <button onclick="event.stopPropagation();_mbLoad('${esc(d.path)}')"
                  style="background:none;border:1px solid var(--border);color:var(--text3);cursor:pointer;
                         font-size:10px;padding:2px 8px;border-radius:5px;transition:all 0.15s"
                  onmouseover="this.style.color='var(--accent)';this.style.borderColor='var(--accent)'"
                  onmouseout="this.style.color='var(--text3)';this.style.borderColor='var(--border)'"
                  title="Open this folder">Open →</button>
        </div>`);
    });

    // Files (only shown in files mode, or greyed out in folder mode)
    (data.files || []).forEach(f => {
      const isMedia = f.supported;
      const ico = (f.ext||'').match(/\.(mp3|aac|flac|wav|ogg|m4a)$/i) ? '🎵' : '🎬';
      if (isFolderMode) {
        // Show files greyed out as context, not clickable
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

    // Restore selection highlight if same path still selected
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

  } catch(e) {
    listing.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>Failed to load: ${esc(e.message)}</div></div>`;
    statusBar.textContent = 'Error';
  }
  _mb.loading = false;
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

async function complianceResyncNow(streamName, btn) {
  const statusEl = document.getElementById('cfg-comp-resync-status');
  if (btn) btn.disabled = true;
  if (statusEl) { statusEl.textContent = 'Resyncing…'; statusEl.style.color = 'var(--yellow)'; }
  try {
    const r = await api('compliance_resync', {name: streamName});
    if (r?.ok) {
      if (statusEl) { statusEl.textContent = '✓ Resync initiated'; statusEl.style.color = 'var(--green)'; }
      toast('Compliance resync initiated', 'ok');
    } else {
      if (statusEl) { statusEl.textContent = '✕ ' + (r?.msg||'Failed'); statusEl.style.color = 'var(--red)'; }
      toast(r?.msg || 'Resync failed', 'err');
    }
  } catch(e) {
    if (statusEl) { statusEl.textContent = '✕ Request failed'; statusEl.style.color = 'var(--red)'; }
    toast('Resync request failed', 'err');
  } finally {
    if (btn) btn.disabled = false;
    setTimeout(() => { if (statusEl) { statusEl.textContent = ''; statusEl.style.color = ''; } }, 4000);
  }
}

function toggleComplianceAlerts(checked) {
  _compAlertsEnabled = checked;
  localStorage.setItem('hc_comp_alerts', checked ? 'true' : 'false');
  if (!checked) {
    document.querySelectorAll('.compliance-alert-banner').forEach(b => b.remove());
    Object.keys(_compAlertActive).forEach(k => delete _compAlertActive[k]);
  }
}

const _settings={autoref:true,autoscroll:true,compact:false,showrtsp:true,notifStart:true,notifErr:true,notifEvent:false};

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
    sel.innerHTML = '<option value="">— Media root (all files) —</option>' +
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
  applySettings();
}

function applySettings(){
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
// ═══════════════════════════════════
// THEME PICKER
// ═══════════════════════════════════
const THEMES={
  dark:     {label:'Dark',    dot:'#b87333'},
  light:    {label:'Light',   dot:'#b87333'},
  ocean:    {label:'Ocean',   dot:'#2196b8'},
  midnight: {label:'Midnight',dot:'#8066cc'},
  forest:   {label:'Forest',  dot:'#4a9a5a'},
};
function setTheme(name){
  if(!THEMES[name]) name='dark';
  document.documentElement.setAttribute('data-theme',name);
  try{localStorage.setItem('hc-theme',name);}catch(_){}
  _updateThemeUI(name);
  const dd=document.getElementById('theme-picker-dropdown');
  if(dd) dd.classList.remove('open');
}
function _updateThemeUI(name){
  const t=THEMES[name]||THEMES.dark;
  const dot=document.getElementById('theme-dot');
  const lbl=document.getElementById('theme-label');
  if(dot){dot.style.background=t.dot;dot.style.boxShadow='0 0 0 2px var(--bg3),0 0 0 3px '+t.dot;}
  if(lbl) lbl.textContent=t.label;
  document.querySelectorAll('.theme-opt').forEach(el=>{
    el.classList.toggle('active',el.dataset.theme===name);
  });
}
function toggleThemePicker(){
  const dd=document.getElementById('theme-picker-dropdown');
  if(dd) dd.classList.toggle('open');
}
document.addEventListener('click',function(e){
  const wrap=document.getElementById('theme-picker-wrap');
  if(wrap&&!wrap.contains(e.target)){
    const dd=document.getElementById('theme-picker-dropdown');
    if(dd) dd.classList.remove('open');
  }
});
(function initTheme(){
  try{
    const stored=localStorage.getItem('hc-theme');
    const name=(stored&&THEMES[stored])?stored:'dark';
    document.documentElement.setAttribute('data-theme',name);
  }catch(_){}
})();
document.addEventListener('DOMContentLoaded',function(){
  const name=document.documentElement.getAttribute('data-theme')||'dark';
  _updateThemeUI(name);
});
function toggleTheme(){
  const cur=document.documentElement.getAttribute('data-theme')||'dark';
  setTheme(cur==='dark'?'light':'dark');
}

// ═══════════════════════════════════
// INIT
// ═══════════════════════════════════
(async function init(){
  document.getElementById('logo-img').src = '/ resources/logo.png';
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
  _fmCurrentPath = path || '';
  const body   = document.getElementById('fm-body');
  const status = document.getElementById('fm-status');
  body.innerHTML = '<div class="fm-empty"><div class="empty-icon" style="animation:spin 1.2s linear infinite">⟳</div></div>';
  status.textContent = 'Loading…';
  try {
    const d = await fetch('/api/files?path=' + encodeURIComponent(_fmCurrentPath)).then(r => r.json());
    if (d.error) {
      body.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>${d.error}</div></div>`;
      status.textContent = 'Error';
      return;
    }

    // ── Breadcrumb ──────────────────────────────────────────────
    const bc = document.getElementById('fm-breadcrumb');
    bc.innerHTML = d.breadcrumb.map((crumb, i) => {
      const isLast = i === d.breadcrumb.length - 1;
      return (i > 0 ? '<span class="fm-sep">›</span>' : '') +
        `<span onclick="loadFiles('${crumb.path}')"
               class="${isLast ? 'fm-cur' : ''}">${crumb.name}</span>`;
    }).join('');

    // ── Sidebar rebuild (root dirs only) ────────────────────────
    _fmAllDirs = [''];
    const sidebar = document.getElementById('fm-dir-list');
    sidebar.innerHTML =
      `<div class="fm-dir-item${_fmCurrentPath===''?' active':''}" onclick="loadFiles('')">` +
      `<span class="fm-dir-icon">📁</span> Media (root)</div>`;
    try {
      const root = await fetch('/api/files?path=').then(r => r.json());
      (root.dirs || []).forEach(dir => {
        _fmAllDirs.push(dir.path);
        sidebar.insertAdjacentHTML('beforeend',
          `<div class="fm-dir-item${dir.path===_fmCurrentPath?' active':''}"
                onclick="loadFiles('${dir.path}')">` +
          `<span class="fm-dir-icon">📂</span> ${dir.name}</div>`);
      });
    } catch(_) {}

    // ── Body rows ───────────────────────────────────────────────
    const rows = [];

    // Folders first
    d.dirs.forEach(dir => {
      rows.push(`
        <div class="fm-row">
          <span class="fm-row-icon">📁</span>
          <span class="fm-row-name is-dir" ondblclick="loadFiles('${dir.path}')"
                onclick="loadFiles('${dir.path}')">${dir.name}</span>
          <span class="fm-row-meta">${dir.items} item${dir.items!==1?'s':''}</span>
          <div class="fm-row-actions">
            <button class="fm-action-btn"
                    title="Rename this folder"
                    onclick="fmStartRename('${dir.path}','${dir.name}',true)">✏ Rename</button>
            <button class="fm-action-btn mv"
                    title="Move this folder to a different location"
                    onclick="fmStartMove('${dir.path}','${dir.name}',true)">↗ Move</button>
            <button class="fm-action-btn del"
                    title="Permanently delete this folder and all its contents"
                    onclick="fmDeleteDir('${dir.path}','${dir.name}')">🗑 Delete</button>
          </div>
        </div>`);
    });

    // Files
    d.files.forEach(f => {
      const ico = f.ext.match(/\.(mp3|aac|flac|wav|ogg|m4a)$/i) ? '🎵' : '🎬';
      const sup = f.supported
        ? `<span style="font-size:10px;color:var(--green);margin-left:4px">✓</span>`
        : `<span style="font-size:10px;color:var(--text3);margin-left:4px" title="Unsupported format">—</span>`;
      rows.push(`
        <div class="fm-row">
          <span class="fm-row-icon">${ico}</span>
          <span class="fm-row-name">${f.name}${sup}</span>
          <span class="fm-row-meta">${f.size}</span>
          <div class="fm-row-actions">
            <button class="fm-action-btn"
                    title="Rename this file"
                    onclick="fmStartRename('${f.path}','${f.name}',false)">✏ Rename</button>
            <button class="fm-action-btn mv"
                    title="Move this file to a different folder"
                    onclick="fmStartMove('${f.path}','${f.name}',false)">↗ Move</button>
            <button class="fm-action-btn cp"
                    title="Copy this file to another folder"
                    onclick="fmStartCopy('${f.path}','${f.name}')">⎘ Copy</button>
            <button class="fm-action-btn del"
                    title="Permanently delete this file"
                    onclick="fmDelete('${f.path}','${f.name}')">🗑 Delete</button>
          </div>
        </div>`);
    });

    if (!rows.length) {
      body.innerHTML = '<div class="fm-empty"><div class="empty-icon">📂</div><div>This folder is empty.</div></div>';
    } else {
      body.innerHTML = rows.join('');
    }

    const total = d.dirs.length + d.files.length;
    status.innerHTML =
      `<b>${d.dirs.length}</b> folder${d.dirs.length!==1?'s':''}&nbsp;&nbsp;` +
      `<b>${d.files.length}</b> file${d.files.length!==1?'s':''}&ensp;·&ensp;` +
      `<span style="color:var(--accent-light)">${_fmCurrentPath||'Media (root)'}</span>`;

  } catch(e) {
    body.innerHTML = `<div class="fm-empty"><div class="empty-icon">⚠</div><div>Load failed: ${e.message}</div></div>`;
    status.textContent = 'Error';
  }
}

// ── New folder ────────────────────────────────────────────────
async function fmNewFolder() {
  const name = prompt('New folder name:');
  if (!name || !name.trim()) return;
  const fullName = _fmCurrentPath ? _fmCurrentPath + '/' + name.trim() : name.trim();
  const r = await api('create_subdir', {name: fullName});
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
  sel.innerHTML = '<option value="">Media (root)</option>';
  _fmAllDirs
    .filter(d => d && d !== excludePath)
    .forEach(d => sel.insertAdjacentHTML('beforeend',
      `<option value="${d}">${d}</option>`));
}

// ── Close all FM dialogs ──────────────────────────────────────
function fmCloseDialogs() {
  document.querySelectorAll('.fm-dialog-overlay').forEach(el => el.classList.remove('open'));
  _fmOp = null;
}
</script>
</body>
</html>

"""
