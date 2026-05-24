"""
hc/web_settings_manager.py — Persistence layer for app_settings.hcf.

v2.0 changes
────────────
• Settings are now organised into four named groups:
    appearance   – accent colour, brand name/logo, date/time display format
    regional     – holiday country/subdivision, timezone hint
    notifications – compliance alert defaults, stream-error toast duration
    system       – auto-backup interval, log retention, session timeout
• load_settings()  returns a flat dict merged over defaults (backwards-compat).
• load_settings_grouped()  returns the same data structured by group, plus a
  schema listing type / label / description for each key — consumed by the
  Settings UI to auto-render the form.
• save_settings(updates)  accepts both flat and grouped payloads.
• reset_settings()  wipes the file and returns factory defaults.
• SETTINGS_SCHEMA  is the single source of truth; add keys here to expose them
  in the UI automatically.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from hc.constants import CONFIG_DIR

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema — single source of truth for every persisted setting
# ---------------------------------------------------------------------------
# Each entry: key → {group, type, label, description, default}
# type:  "str" | "bool" | "int" | "color" | "select" | "image_url"
# For "select", an "options" list of {"value", "label"} is required.

SETTINGS_SCHEMA: Dict[str, Dict[str, Any]] = {

    # ── Appearance ──────────────────────────────────────────────────────────
    "accent_color": {
        "group":       "appearance",
        "type":        "color",
        "label":       "Accent colour",
        "description": "Primary highlight colour used throughout the Web UI.",
        "default":     "#b87333",       # copper/bronze
    },
    "brand_name": {
        "group":       "appearance",
        "type":        "str",
        "label":       "Brand name",
        "description": "Custom application name shown in the top bar. "
                       "Leave blank to use the server default.",
        "default":     "",
    },
    "brand_logo": {
        "group":       "appearance",
        "type":        "image_url",
        "label":       "Brand logo",
        "description": "Base64 data-URL or absolute URL for the top-bar logo. "
                       "Recommended: 48 px tall PNG/SVG with transparent background.",
        "default":     "",
    },
    "date_format": {
        "group":       "appearance",
        "type":        "select",
        "label":       "Date format",
        "description": "How dates are displayed across the UI.",
        "default":     "YYYY-MM-DD",
        "options": [
            {"value": "YYYY-MM-DD", "label": "ISO 8601  (2025-12-31)"},
            {"value": "DD/MM/YYYY", "label": "UK / EU   (31/12/2025)"},
            {"value": "MM/DD/YYYY", "label": "US        (12/31/2025)"},
            {"value": "DD.MM.YYYY", "label": "European  (31.12.2025)"},
        ],
    },
    "time_format": {
        "group":       "appearance",
        "type":        "select",
        "label":       "Time format",
        "description": "12-hour or 24-hour clock display.",
        "default":     "24h",
        "options": [
            {"value": "24h", "label": "24-hour  (14:30)"},
            {"value": "12h", "label": "12-hour  (2:30 PM)"},
        ],
    },

    # ── Regional ────────────────────────────────────────────────────────────
    "holiday_country": {
        "group":       "regional",
        "type":        "str",
        "label":       "Holiday country",
        "description": "ISO 3166-1 alpha-2 country code used to fetch public "
                       "holidays in the schedule calendar (e.g. US, GB, DE).",
        "default":     "US",
    },
    "holiday_subdiv": {
        "group":       "regional",
        "type":        "str",
        "label":       "Holiday subdivision",
        "description": "ISO 3166-2 subdivision code for regional holidays "
                       "(e.g. US-CA for California, GB-ENG for England). "
                       "Leave blank for national holidays only.",
        "default":     None,
    },
    "timezone": {
        "group":       "regional",
        "type":        "str",
        "label":       "Display timezone",
        "description": "IANA timezone for date/time display in the UI "
                       "(e.g. America/New_York, Europe/London). "
                       "Leave blank to use the server's local timezone.",
        "default":     "",
    },

    # ── Notifications ───────────────────────────────────────────────────────
    "notify_on_stream_error": {
        "group":       "notifications",
        "type":        "bool",
        "label":       "Alert on stream error",
        "description": "Show a browser toast notification when a stream enters "
                       "the ERROR state.",
        "default":     True,
    },
    "notify_on_stream_stop": {
        "group":       "notifications",
        "type":        "bool",
        "label":       "Alert on stream stop",
        "description": "Show a browser toast notification when a stream is "
                       "manually stopped.",
        "default":     False,
    },
    "toast_duration_secs": {
        "group":       "notifications",
        "type":        "int",
        "label":       "Toast duration (s)",
        "description": "How long browser toast notifications remain visible "
                       "before auto-dismissing (seconds, 0 = persistent).",
        "default":     6,
    },
    "compliance_alert_default": {
        "group":       "notifications",
        "type":        "bool",
        "label":       "Compliance alert default",
        "description": "Default value for 'compliance_alert_enabled' on newly "
                       "created streams.",
        "default":     True,
    },

    # ── System ──────────────────────────────────────────────────────────────
    "auto_backup_enabled": {
        "group":       "system",
        "type":        "bool",
        "label":       "Automatic backup",
        "description": "Automatically write a timestamped .hc backup file to "
                       "<config>/backups/ on the schedule below.",
        "default":     False,
    },
    "auto_backup_interval_hours": {
        "group":       "system",
        "type":        "int",
        "label":       "Backup interval (hours)",
        "description": "How often to write an automatic backup (minimum 1 hour). "
                       "Only active when Automatic backup is enabled.",
        "default":     24,
    },
    "log_retain_days": {
        "group":       "system",
        "type":        "int",
        "label":       "Log retention (days)",
        "description": "Delete log files older than this many days (0 = keep forever).",
        "default":     14,
    },
    "session_timeout_mins": {
        "group":       "system",
        "type":        "int",
        "label":       "Session timeout (min)",
        "description": "Idle Web UI session timeout in minutes (0 = never).",
        "default":     0,
    },
    "library_cache_ttl_secs": {
        "group":       "system",
        "type":        "int",
        "label":       "Library cache TTL (s)",
        "description": "How long the media-library listing is cached before a "
                       "refresh scan is triggered (seconds).",
        "default":     60,
    },
}

# Flat defaults dict derived from schema — used everywhere internally
_DEFAULTS: Dict[str, Any] = {k: v["default"] for k, v in SETTINGS_SCHEMA.items()}

# Ordered group names (controls UI tab order)
SETTINGS_GROUPS: List[str] = ["appearance", "regional", "notifications", "system"]


# ---------------------------------------------------------------------------
# File path
# ---------------------------------------------------------------------------

def _settings_path():
    d = CONFIG_DIR()
    d.mkdir(parents=True, exist_ok=True)
    return d / "app_settings.hcf"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_settings() -> Dict[str, Any]:
    """
    Return persisted settings merged over defaults — flat dict, fully
    backwards-compatible with all existing callers.
    """
    p = _settings_path()
    if not p.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(_DEFAULTS)
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except Exception as exc:
        log.warning("web_settings_manager: could not load settings — %s", exc)
        return dict(_DEFAULTS)


def load_settings_grouped() -> Dict[str, Any]:
    """
    Return settings structured for the Settings UI:

    {
      "groups": ["appearance", "regional", "notifications", "system"],
      "schema": { <key>: {group, type, label, description, default, options?} },
      "values": { <key>: <current_value> }
    }

    The UI can iterate ``groups`` to render tabs, use ``schema`` to auto-build
    form controls, and populate them from ``values``.
    """
    return {
        "groups": SETTINGS_GROUPS,
        "schema": SETTINGS_SCHEMA,
        "values": load_settings(),
    }


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge *updates* into persisted settings, write to disk, return the
    complete flat settings dict after the merge.

    Accepts both flat ``{key: value}`` and grouped ``{group: {key: value}}``
    payloads; the latter is flattened automatically.
    """
    # Flatten grouped payload if received
    flat_updates: Dict[str, Any] = {}
    for k, v in updates.items():
        if k in SETTINGS_GROUPS and isinstance(v, dict):
            flat_updates.update(v)
        else:
            flat_updates[k] = v

    # Only persist keys present in the schema (ignore unknown keys)
    known = {k: flat_updates[k] for k in flat_updates if k in SETTINGS_SCHEMA}
    if len(known) < len(flat_updates):
        skipped = set(flat_updates) - set(known)
        log.debug("web_settings_manager: ignoring unknown keys: %s", skipped)

    current = load_settings()
    current.update(known)

    p = _settings_path()
    tmp = p.with_name(p.name + ".tmp")
    try:
        tmp.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Could not save settings: {exc}") from exc

    log.info("web_settings_manager: saved %d setting(s) to '%s'", len(known), p)
    return current


def reset_settings() -> Dict[str, Any]:
    """
    Delete the persisted settings file AND any holiday store files, then
    return factory defaults.  Used by the factory-reset flow.

    Holiday data (custom_holidays.hcf and the library-cache directory) may
    live outside CONFIG_DIR, so we clear them here as a belt-and-braces
    measure in addition to the explicit wipe in _handle_reset.
    """
    import shutil as _shutil

    # ── App settings file ────────────────────────────────────────────────────
    p = _settings_path()
    try:
        p.unlink(missing_ok=True)
        log.info("web_settings_manager: settings reset to factory defaults")
    except Exception as exc:
        log.warning("web_settings_manager: could not delete settings file — %s", exc)

    # ── Holiday store — custom holidays + library cache ──────────────────────
    # Prefer the holiday store's own path helpers; fall back to filename
    # convention inside CONFIG_DIR if those helpers don't exist.
    try:
        from hc.web_holiday_store import _custom_path, _holiday_dir
        try:
            _custom_path().unlink(missing_ok=True)
        except Exception as exc:
            log.warning("web_settings_manager: could not delete custom holidays — %s", exc)
        try:
            _cd = _holiday_dir()
            if _cd.exists():
                _shutil.rmtree(_cd, ignore_errors=True)
        except Exception as exc:
            log.warning("web_settings_manager: could not clear holiday cache dir — %s", exc)
    except Exception:
        # Fallback: best-effort delete well-known file names inside CONFIG_DIR
        cfg = CONFIG_DIR()
        for _fname in ("custom_holidays.hcf", "holidays_cache.hcf"):
            try:
                (cfg / _fname).unlink(missing_ok=True)
            except Exception:
                pass
        for _dname in ("holidays", "holiday_cache"):
            _d = cfg / _dname
            try:
                if _d.exists():
                    _shutil.rmtree(_d, ignore_errors=True)
            except Exception:
                pass

    return dict(_DEFAULTS)
