#!/usr/bin/env python3
"""
apply_web_compliance_patch.py
─────────────────────────────
Run this script once from the HydraCast root to apply compliance v2 changes
to hc/web.py automatically.

Usage:
    python apply_web_compliance_patch.py [path/to/hc/web.py]
"""
import re
import sys
from pathlib import Path

WEB_PY = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("hc/web.py")

if not WEB_PY.exists():
    print(f"ERROR: {WEB_PY} not found.")
    sys.exit(1)

src = WEB_PY.read_text(encoding="utf-8")
original = src
changes = 0


def patch(find: str, replace: str, label: str) -> None:
    global src, changes
    if find not in src:
        print(f"  SKIP (already applied or not found): {label}")
        return
    src = src.replace(find, replace, 1)
    changes += 1
    print(f"  OK: {label}")


print(f"Patching {WEB_PY} ...")

# ── 1. _get_streams: expose compliance alert fields ───────────────────────────
patch(
    find='"next_in_queue":  _get_next_in_queue(st, cfg, n=2),\n            })',
    replace=(
        '"next_in_queue":  _get_next_in_queue(st, cfg, n=2),\n'
        '                # Compliance alert (v2)\n'
        '                "compliance_enabled":       cfg.compliance_enabled,\n'
        '                "compliance_alert":         getattr(st, "compliance_alert", None),\n'
        '                "compliance_alert_enabled": getattr(cfg, "compliance_alert_enabled", True),\n'
        '            })'
    ),
    label="_get_streams: add compliance_alert fields",
)

# ── 2. _get_streams_config: expose compliance_alert_enabled ───────────────────
patch(
    find=(
        '                "compliance_enabled":   cfg.compliance_enabled,\n'
        '                "compliance_start":     cfg.compliance_start,\n'
        '                "compliance_loop":      cfg.compliance_loop,\n'
    ),
    replace=(
        '                "compliance_enabled":       cfg.compliance_enabled,\n'
        '                "compliance_start":         cfg.compliance_start,\n'
        '                "compliance_loop":          cfg.compliance_loop,\n'
        '                "compliance_alert_enabled": getattr(cfg, "compliance_alert_enabled", True),\n'
    ),
    label="_get_streams_config: add compliance_alert_enabled",
)

# ── 3. CSS: add compliance alert banner styles ────────────────────────────────
COMPLIANCE_CSS = r"""
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
"""

patch(
    find="@keyframes iconBounce{\n  0%,100%{transform:translateY(0)}\n  40%{transform:translateY(-4px)}\n  70%{transform:translateY(-2px)}\n}",
    replace=(
        "@keyframes iconBounce{\n  0%,100%{transform:translateY(0)}\n"
        "  40%{transform:translateY(-4px)}\n  70%{transform:translateY(-2px)}\n}"
        + COMPLIANCE_CSS
    ),
    label="CSS: compliance alert banner styles",
)

# ── 4. JS: compliance alert banner logic ──────────────────────────────────────
COMPLIANCE_JS = r"""
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

"""

# Insert the JS block just before the settings const definition
patch(
    find="const _settings={autoref:true,",
    replace=COMPLIANCE_JS + "const _settings={autoref:true,",
    label="JS: compliance alert banner functions",
)

# ── 5. JS: hook _updateComplianceAlerts into loadStreams ──────────────────────
# Find renderStreams(data) and add the call after it.
patch(
    find="renderStreams(data);",
    replace="renderStreams(data);\n      _updateComplianceAlerts(data);",
    label="JS: hook _updateComplianceAlerts into loadStreams",
)

# ── 6. HTML: Settings tab — add compliance alerts toggle ─────────────────────
# We insert it after the existing "notifEvent" toggle (last in the settings list)
# Strategy: find the settings object initialiser and the applySettings function,
# then search for the settings tab panel content.
SETTINGS_COMP_ROW = (
    '\n      <div class="st-comp-row">'
    '\n        <label for="st-comp-alerts">'
    '\n          <span style="font-weight:500">Compliance error alerts</span>'
    '\n          <small>Show a pulsing banner when a compliance stream has an error</small>'
    '\n        </label>'
    '\n        <input type="checkbox" id="st-comp-alerts"'
    '\n          onchange="toggleComplianceAlerts(this.checked)"'
    '\n          style="width:auto;accent-color:var(--accent);transform:scale(1.25)">'
    '\n      </div>'
)

# Insert into the settings tab body — look for the auto-ref checkbox which is
# always present in the settings panel, and add our row after the last toggle.
# We find the `applySettings` function where it syncs `st-comp-alerts`.
patch(
    find="function applySettings(){\n  // compact mode",
    replace=(
        "function applySettings(){\n"
        "  // sync compliance alerts toggle\n"
        "  const caEl=document.getElementById('st-comp-alerts');\n"
        "  if(caEl)caEl.checked=_compAlertsEnabled;\n"
        "  // compact mode"
    ),
    label="JS: applySettings syncs st-comp-alerts checkbox",
)

# ── 7. HTML new-stream: add compliance_alert_enabled checkbox ─────────────────
patch(
    find=(
        '<input type="checkbox" id="new-comp-strict" style="width:auto;accent-color:var(--accent)"\n'
        '              title="Stop the stream entirely if the calculated seek offset exceeds the video duration (prevents silent looping)">\n'
        '            Strict mode — stop stream if seek offset exceeds video duration\n'
        '          </label>'
    ),
    replace=(
        '<input type="checkbox" id="new-comp-strict" style="width:auto;accent-color:var(--accent)"\n'
        '              title="Stop the stream entirely if the calculated seek offset exceeds the video duration (prevents silent looping)">\n'
        '            Strict mode — stop stream if seek offset exceeds video duration\n'
        '          </label>\n'
        '          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:12px;color:var(--text2);margin-top:6px">\n'
        '            <input type="checkbox" id="new-comp-alert" checked style="width:auto;accent-color:var(--accent)"\n'
        '              title="Show a pulsing error banner on the dashboard when a compliance error occurs">\n'
        '            Show compliance error banner on dashboard\n'
        '          </label>'
    ),
    label="HTML new-stream: add compliance_alert_enabled checkbox",
)

# ── 8. JS submitNewStream: send compliance_alert_enabled ─────────────────────
patch(
    find=(
        "    compliance_loop:document.getElementById('new-comp-loop')?.checked||false,\n"
        "    compliance_strict:document.getElementById('new-comp-strict')?.checked||false,\n"
    ),
    replace=(
        "    compliance_loop:document.getElementById('new-comp-loop')?.checked||false,\n"
        "    compliance_strict:document.getElementById('new-comp-strict')?.checked||false,\n"
        "    compliance_alert_enabled:document.getElementById('new-comp-alert')?.checked!==false,\n"
    ),
    label="JS submitNewStream: send compliance_alert_enabled",
)

# ── 9. JS saveConfig: send compliance_alert_enabled ──────────────────────────
patch(
    find="    compliance_loop:document.getElementById('cfg-comp-loop')?.checked||false,\n  };",
    replace=(
        "    compliance_loop:document.getElementById('cfg-comp-loop')?.checked||false,\n"
        "    compliance_alert_enabled:document.getElementById('cfg-comp-alert')?.checked!==false,\n"
        "  };"
    ),
    label="JS saveConfig: send compliance_alert_enabled",
)

# ── Write output ──────────────────────────────────────────────────────────────
if changes == 0:
    print("\nNo changes applied — patch may already be applied.")
else:
    # Backup
    backup = WEB_PY.with_suffix(".py.pre_compliance_v2")
    backup.write_text(original, encoding="utf-8")
    print(f"\nBackup saved to: {backup}")
    WEB_PY.write_text(src, encoding="utf-8")
    print(f"Applied {changes} change(s) to {WEB_PY}")

print("\nDone.")
print()
print("MANUAL STEPS REMAINING:")
print("  1. In the Settings tab HTML, add the compliance toggle row:")
print("       <div class='st-comp-row'>... (see SETTINGS_COMP_ROW in this script)")
print("  2. In the edit-stream config panel HTML, add the cfg-comp-alert checkbox")
print("     after cfg-comp-loop (mirrors the new-comp-alert checkbox above).")
print("  3. In loadConfig() JS, after populating cfg-comp-loop, add:")
print("       const alertEl=document.getElementById('cfg-comp-alert');")
print("       if(alertEl)alertEl.checked=cfg.compliance_alert_enabled!==false;")
print("  4. In the _dispatch update_config handler (Python), add:")
print("       cfg.compliance_alert_enabled = bool(")
print("           data.get('compliance_alert_enabled', cfg.compliance_alert_enabled))")
print("  5. In the _dispatch create_stream handler (Python), add to StreamConfig():")
print("       compliance_alert_enabled=bool(data.get('compliance_alert_enabled', True)),")
