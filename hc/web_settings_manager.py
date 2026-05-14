"""
hc/web_settings_manager.py — App-wide settings store (JSON).

Persists settings that are global (not per-stream), such as the
holiday country / subdivision shown in the Events calendar tab.

Storage: <config_dir>/app_settings.json

Usage
─────
    from hc.web_settings_manager import load_settings, save_settings

    cfg = load_settings()
    # cfg == {"holiday_country": "BD", "holiday_subdiv": None, ...}

    updated = save_settings({"holiday_country": "US", "holiday_subdiv": "CA"})
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from hc.constants import CONFIG_DIR

log = logging.getLogger(__name__)

# Default values returned when no settings file exists yet.
_DEFAULTS: Dict[str, Any] = {
    "holiday_country": "US",   # ISO 3166-1 alpha-2
    "holiday_subdiv":  None,   # state / province code, or null
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _path() -> Path:
    d = CONFIG_DIR()
    d.mkdir(parents=True, exist_ok=True)
    return d / "app_settings.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_settings() -> Dict[str, Any]:
    """
    Return the current app settings, merged over defaults.

    Always returns a full dict (never raises).  Missing keys are filled
    from _DEFAULTS so callers can always rely on every key being present.
    """
    p = _path()
    if not p.exists():
        return dict(_DEFAULTS)
    try:
        data: Dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except Exception as exc:
        log.error("web_settings_manager: could not load settings: %s", exc)
        return dict(_DEFAULTS)


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge *updates* into the current settings, persist, and return the
    complete updated settings dict.

    Raises OSError / IOError on disk errors (caller should handle).
    """
    current = load_settings()
    current.update(updates)

    p = _path()
    tmp = p.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps(current, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(p)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    log.info(
        "web_settings_manager: saved — keys updated: %s",
        list(updates.keys()),
    )
    return current
