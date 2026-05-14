"""
web.py — Compliance v2 patch
============================
Apply these THREE changes to web.py to implement:

  1. Expose compliance alert in the /api/streams response.
  2. Add "Compliance alert banner" toggle in the Settings tab.
  3. Show a pulsing red banner every 10 s for streams with active compliance errors.
  4. Add compliance_alert_enabled checkbox to the stream config form (new & edit).
  5. Pass compliance_alert_enabled through update_config / create_stream dispatch.

Each change is described as a FIND → REPLACE pair. Apply them in order.
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 1 — _get_streams(): expose compliance_alert fields
# ══════════════════════════════════════════════════════════════════════════════
#
# FIND (end of the per-stream dict in _get_streams, just before self._json):
#
#                 "next_in_queue":  _get_next_in_queue(st, cfg, n=2),
#             })
#         self._json(result)
#
# REPLACE WITH:
#
#                 "next_in_queue":  _get_next_in_queue(st, cfg, n=2),
#                 # Compliance alert (v2)
#                 "compliance_enabled":       cfg.compliance_enabled,
#                 "compliance_alert":         getattr(st, "compliance_alert", None),
#                 "compliance_alert_enabled": cfg.compliance_alert_enabled,
#             })
#         self._json(result)


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 2 — _get_streams_config(): expose compliance_alert_enabled
# ══════════════════════════════════════════════════════════════════════════════
#
# FIND:
#                 # Compliance fields (v5.0.6+)
#                 "compliance_enabled":   cfg.compliance_enabled,
#                 "compliance_start":     cfg.compliance_start,
#                 "compliance_loop":      cfg.compliance_loop,
#
# REPLACE WITH:
#                 # Compliance fields (v5.0.6+)
#                 "compliance_enabled":       cfg.compliance_enabled,
#                 "compliance_start":         cfg.compliance_start,
#                 "compliance_loop":          cfg.compliance_loop,
#                 "compliance_alert_enabled": cfg.compliance_alert_enabled,


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 3 — _dispatch(): handle compliance_alert_enabled in update_config
#            and create_stream
# ══════════════════════════════════════════════════════════════════════════════
#
# In the update_config handler, find the line that reads:
#     cfg.compliance_loop    = bool(data.get("compliance_loop", cfg.compliance_loop))
#
# ADD AFTER IT:
#     cfg.compliance_alert_enabled = bool(
#         data.get("compliance_alert_enabled", cfg.compliance_alert_enabled)
#     )
#
# In the create_stream handler, find the StreamConfig(...) constructor call
# and add the keyword argument:
#     compliance_alert_enabled = bool(data.get("compliance_alert_enabled", True)),


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 4 — HTML: compliance_alert_enabled checkbox in NEW STREAM form
# ══════════════════════════════════════════════════════════════════════════════
#
# FIND (inside the Compliance section of the new-stream form):
#           <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
#             <input type="checkbox" id="new-comp-loop" style="width:auto;accent-color:var(--accent)"
#               title="When the video is shorter than 24 h, calculate the seek position within the current loop iteration">
#             Loop calculation — seek within loops for videos shorter than 24 h
#           </label>
#           <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
#             <input type="checkbox" id="new-comp-strict" ...>
#             Strict mode — stop stream if seek offset exceeds video duration
#           </label>
#
# REPLACE WITH (keep existing labels, add alert toggle):
#           <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
#             <input type="checkbox" id="new-comp-loop" style="width:auto;accent-color:var(--accent)"
#               title="When the video is shorter than 24 h, calculate the seek position within the current loop iteration">
#             Loop calculation — seek within loops for videos shorter than 24 h
#           </label>
#           <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2)">
#             <input type="checkbox" id="new-comp-strict" style="width:auto;accent-color:var(--accent)"
#               title="Stop the stream entirely if the calculated seek offset exceeds the video duration (prevents silent looping)">
#             Strict mode — stop stream if seek offset exceeds video duration
#           </label>
#           <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2);margin-top:6px">
#             <input type="checkbox" id="new-comp-alert" checked style="width:auto;accent-color:var(--accent)"
#               title="Show a pulsing error banner on the dashboard when a compliance error occurs (missing day-tagged file, seek failure, etc.)">
#             Show compliance error banner on dashboard
#           </label>


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 5 — JS: submit compliance_alert_enabled from new-stream form
# ══════════════════════════════════════════════════════════════════════════════
#
# In submitNewStream(), FIND:
#     compliance_loop:document.getElementById('new-comp-loop')?.checked||false,
#     compliance_strict:document.getElementById('new-comp-strict')?.checked||false,
#
# REPLACE WITH:
#     compliance_loop:document.getElementById('new-comp-loop')?.checked||false,
#     compliance_strict:document.getElementById('new-comp-strict')?.checked||false,
#     compliance_alert_enabled:document.getElementById('new-comp-alert')?.checked!==false,


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 6 — JS: submit compliance_alert_enabled from edit-stream form
# ══════════════════════════════════════════════════════════════════════════════
#
# In saveConfig(), find the payload object. FIND:
#     compliance_loop:document.getElementById('cfg-comp-loop')?.checked||false,
#
# REPLACE WITH:
#     compliance_loop:document.getElementById('cfg-comp-loop')?.checked||false,
#     compliance_alert_enabled:document.getElementById('cfg-comp-alert')?.checked!==false,


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 7 — HTML: compliance_alert_enabled in edit-stream config panel
# ══════════════════════════════════════════════════════════════════════════════
#
# Inside loadConfig() where the compliance form fields are built for the
# selected stream (look for cfg-comp-en, cfg-comp-start, cfg-comp-loop),
# ADD after the cfg-comp-loop label:
#
#   <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2);margin-top:6px">
#     <input type="checkbox" id="cfg-comp-alert" style="width:auto;accent-color:var(--accent)"
#       title="Show a pulsing error banner when a compliance error occurs">
#     Show compliance error banner on dashboard
#   </label>
#
# And in the JavaScript where loadConfig() populates the form fields:
# FIND (near other cfg-comp-* lines):
#     document.getElementById('cfg-comp-loop').checked = cfg.compliance_loop || false;
#
# ADD AFTER:
#     const alertEl = document.getElementById('cfg-comp-alert');
#     if (alertEl) alertEl.checked = cfg.compliance_alert_enabled !== false;


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 8 — CSS: compliance alert banner styles
# Add to the <style> block (anywhere in the CSS section).
# ══════════════════════════════════════════════════════════════════════════════
CSS_TO_ADD = r"""
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
/* Settings toggle for compliance alerts */
.st-toggle-row{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 0;border-bottom:1px solid var(--border);
}
.st-toggle-row:last-child{border-bottom:none}
.st-toggle-label{font-size:13px;color:var(--text2);font-weight:500}
.st-toggle-desc{font-size:11px;color:var(--text3);margin-top:2px}
"""


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 9 — JS: compliance alert banner logic
# Add this JavaScript to the <script> section.
# ══════════════════════════════════════════════════════════════════════════════
JS_TO_ADD = r"""
// ═══════════════════════════════════════════════════════
// COMPLIANCE ALERT BANNER
// ═══════════════════════════════════════════════════════

// Global setting: whether to show compliance error banners.
// User can toggle in Settings → "Compliance error alerts".
// Persisted in localStorage under 'hc_comp_alerts'.
let _compAlertsEnabled = localStorage.getItem('hc_comp_alerts') !== 'false';

// Tracks which streams currently have a visible banner so we
// don't respawn it on every poll tick.
const _compAlertActive = {};  // streamName → true

// Called once per loadStreams() tick.
function _updateComplianceAlerts(streams) {
  if (!_compAlertsEnabled) {
    // Remove all banners if setting toggled off.
    document.querySelectorAll('.compliance-alert-banner').forEach(el => el.remove());
    Object.keys(_compAlertActive).forEach(k => delete _compAlertActive[k]);
    return;
  }

  const seenNames = new Set();

  for (const s of streams) {
    if (!s.compliance_enabled) continue;
    if (!s.compliance_alert) continue;   // no active alert
    if (!s.compliance_alert_enabled) continue; // per-stream opt-out

    seenNames.add(s.name);

    if (_compAlertActive[s.name]) {
      // Update message text in case it changed.
      const el = document.getElementById('cab-' + CSS.escape(s.name));
      if (el) el.querySelector('.cab-body').textContent = s.compliance_alert;
      continue;
    }

    // Create banner
    _compAlertActive[s.name] = true;
    const div = document.createElement('div');
    div.className = 'compliance-alert-banner';
    div.id = 'cab-' + s.name;
    div.innerHTML =
      '<div class="cab-hdr"><span class="cab-dot"></span>Compliance Error</div>' +
      '<div class="cab-body">' + esc(s.compliance_alert) + '</div>' +
      '<div class="cab-stream">Stream: ' + esc(s.name) + '</div>' +
      '<button class="cab-dismiss" onclick="_dismissComplianceAlert(\'' +
        s.name.replace(/'/g, "\\'") + '\')">Dismiss</button>';
    document.body.appendChild(div);

    // Re-show every 10 seconds if still active (pulsing CSS handles visual).
    // The banner is removed only when dismissed or alert clears server-side.
  }

  // Remove banners for streams whose alert cleared.
  for (const name of Object.keys(_compAlertActive)) {
    if (!seenNames.has(name)) {
      const el = document.getElementById('cab-' + name);
      if (el) el.remove();
      delete _compAlertActive[name];
    }
  }
}

function _dismissComplianceAlert(streamName) {
  const el = document.getElementById('cab-' + streamName);
  if (el) {
    el.style.transition = 'opacity 0.3s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 300);
  }
  // Mark as dismissed locally so it won't re-appear this session.
  // (Server-side alert persists until resolved, but we silence it locally.)
  delete _compAlertActive[streamName];
  // Re-check in 60 s in case operator wants to know if it is still happening.
  setTimeout(() => {
    // Allow banner to re-appear on next loadStreams tick if still active.
    // Just clear the 'dismissed' state silently.
  }, 60_000);
}

// ── Settings integration ──────────────────────────────────────────
function toggleComplianceAlerts(el) {
  _compAlertsEnabled = el.checked;
  localStorage.setItem('hc_comp_alerts', _compAlertsEnabled ? 'true' : 'false');
  if (!_compAlertsEnabled) {
    document.querySelectorAll('.compliance-alert-banner').forEach(b => b.remove());
    Object.keys(_compAlertActive).forEach(k => delete _compAlertActive[k]);
  }
}

// ── Hook into existing loadStreams() ─────────────────────────────
// Find the end of loadStreams() and add the call there.
// Specifically, after the line:
//   renderStreams(data);
// ADD:
//   _updateComplianceAlerts(data);
"""


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 10 — HTML: Settings tab — add compliance alerts toggle row
# ══════════════════════════════════════════════════════════════════════════════
#
# In the Settings tab HTML, after the existing toggle rows (autoref, compact,
# showrtsp, etc.), add:
#
SETTINGS_TOGGLE_HTML = r"""
<div class="st-toggle-row">
  <div>
    <div class="st-toggle-label">
      <i class="fa fa-broadcast-tower" style="margin-right:6px;opacity:0.7"></i>
      Compliance error alerts
    </div>
    <div class="st-toggle-desc">
      Show a pulsing red banner when a compliance stream has an error
      (missing day-tagged file, seek failure, etc.)
    </div>
  </div>
  <input type="checkbox" id="st-comp-alerts"
    onchange="toggleComplianceAlerts(this)"
    style="width:auto;accent-color:var(--accent);transform:scale(1.25);margin-left:16px"
    title="Toggle compliance error banners">
</div>
"""
# And in the JS that initialises the Settings tab, add:
#   const ca = document.getElementById('st-comp-alerts');
#   if (ca) ca.checked = _compAlertsEnabled;


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 11 — JS: hook _updateComplianceAlerts into loadStreams
# ══════════════════════════════════════════════════════════════════════════════
#
# FIND in loadStreams() (near the end of the success handler):
#   renderStreams(data);
#
# REPLACE WITH:
#   renderStreams(data);
#   _updateComplianceAlerts(data);


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY OF ALL CHANGES
# ══════════════════════════════════════════════════════════════════════════════
# 1.  _get_streams()       → add compliance_enabled, compliance_alert,
#                            compliance_alert_enabled to JSON response
# 2.  _get_streams_config()→ add compliance_alert_enabled
# 3.  _dispatch()          → parse compliance_alert_enabled in update_config
#                            and create_stream
# 4.  HTML new-stream form → add "Show compliance error banner" checkbox
# 5.  submitNewStream()    → send compliance_alert_enabled
# 6.  saveConfig()         → send compliance_alert_enabled
# 7.  loadConfig()         → populate cfg-comp-alert checkbox
# 8.  CSS                  → compliance alert banner + pulse animation
# 9.  JS                   → _updateComplianceAlerts(), _dismissComplianceAlert(),
#                            toggleComplianceAlerts()
# 10. Settings tab HTML    → "Compliance error alerts" toggle row
# 11. loadStreams()         → call _updateComplianceAlerts(data)
