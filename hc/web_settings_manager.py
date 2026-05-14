"""
hc/web_settings_manager.py — Thin persistence layer for app_settings.json.

Provides load_settings() / save_settings() used by the calendar handlers.
The file is stored alongside streams.json in the config directory.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from hc.constants import CONFIG_DIR

log = logging.getLogger(__name__)

_DEFAULTS: Dict[str, Any] = {
    "holiday_country": "US",
    "holiday_subdiv":  None,
}


def _settings_path():
    d = CONFIG_DIR()
    d.mkdir(parents=True, exist_ok=True)
    return d / "app_settings.json"


def load_settings() -> Dict[str, Any]:
    """Return persisted settings merged over defaults."""
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


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge *updates* into persisted settings, write to disk, return result."""
    current = load_settings()
    current.update(updates)
    p = _settings_path()
    tmp = p.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Could not save settings: {exc}") from exc
    log.info("web_settings_manager: saved settings to '%s'", p)
    return current
