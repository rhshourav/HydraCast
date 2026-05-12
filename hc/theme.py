"""
hc/theme.py — TUI colour-theme management for HydraCast.

Themes are stored as a mapping of Rich colour-token names (matching the
CG / CR / CY / … constants in hc.constants).  The active theme is persisted
to  <BASE_DIR>/theme.json  so it survives restarts.

Usage:
    from hc.theme import load_and_apply_theme   # call once at startup
    from hc.theme import BUILTIN_THEMES, apply_theme, save_theme
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in theme palette
# ---------------------------------------------------------------------------
BUILTIN_THEMES: Dict[str, Dict[str, str]] = {
    "default": {
        "CG": "bright_green",
        "CR": "bright_red",
        "CY": "yellow",
        "CC": "bright_cyan",
        "CW": "white",
        "CD": "dim white",
        "CM": "bright_magenta",
        "CB": "bright_blue",
    },
    "amber": {
        "CG": "bright_yellow",
        "CR": "red",
        "CY": "yellow",
        "CC": "yellow",
        "CW": "bright_yellow",
        "CD": "dim yellow",
        "CM": "red",
        "CB": "yellow",
    },
    "green_phosphor": {
        "CG": "bright_green",
        "CR": "green",
        "CY": "bright_green",
        "CC": "bright_green",
        "CW": "green",
        "CD": "dim green",
        "CM": "bright_green",
        "CB": "green",
    },
    "ocean": {
        "CG": "cyan",
        "CR": "bright_red",
        "CY": "bright_cyan",
        "CC": "bright_blue",
        "CW": "bright_cyan",
        "CD": "dim blue",
        "CM": "magenta",
        "CB": "bright_blue",
    },
    "cyberpunk": {
        "CG": "bright_magenta",
        "CR": "bright_red",
        "CY": "bright_yellow",
        "CC": "bright_cyan",
        "CW": "bright_white",
        "CD": "dim cyan",
        "CM": "bright_magenta",
        "CB": "bright_blue",
    },
    "monochrome": {
        "CG": "bright_white",
        "CR": "bright_white",
        "CY": "white",
        "CC": "bright_white",
        "CW": "white",
        "CD": "dim white",
        "CM": "bright_white",
        "CB": "white",
    },
    "solar": {
        "CG": "bright_green",
        "CR": "bright_red",
        "CY": "bright_yellow",
        "CC": "bright_yellow",
        "CW": "bright_white",
        "CD": "dim yellow",
        "CM": "yellow",
        "CB": "bright_yellow",
    },
}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _theme_file() -> Path:
    from hc.constants import BASE_DIR
    return BASE_DIR() / "theme.json"


def get_saved_theme_name() -> str:
    """Return the name of the last-saved theme, or 'default'."""
    fp = _theme_file()
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8")).get("name", "default")
        except Exception:
            pass
    return "default"


def load_saved_theme() -> Dict[str, str]:
    """
    Load the persisted theme colours.  Falls back to 'default' silently if
    the file is absent or corrupt.
    """
    fp = _theme_file()
    if fp.exists():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            colors = data.get("colors")
            if isinstance(colors, dict) and colors:
                return colors
        except Exception as exc:
            log.warning("theme: could not load '%s': %s", fp, exc)
    return BUILTIN_THEMES["default"].copy()


def save_theme(name: str, colors: Optional[Dict[str, str]] = None) -> None:
    """
    Persist *name* (and optionally explicit *colors*) to disk.
    If *colors* is None the built-in palette for *name* is used.
    """
    resolved = colors if colors is not None else BUILTIN_THEMES.get(name, {})
    try:
        _theme_file().write_text(
            json.dumps({"name": name, "colors": resolved}, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("theme: could not save: %s", exc)


# ---------------------------------------------------------------------------
# Apply to constants module at runtime
# ---------------------------------------------------------------------------

def apply_theme(colors: Dict[str, str]) -> None:
    """
    Inject *colors* into ``hc.constants`` so all subsequent Rich-markup that
    references those module-level variables picks up the new values.

    This works because Rich markup is evaluated lazily at render time, and
    the TUI reads hc.constants.CC / CG / … each frame.
    """
    import hc.constants as _c
    for key, value in colors.items():
        if hasattr(_c, key):
            setattr(_c, key, value)


def load_and_apply_theme() -> str:
    """
    Convenience: load the saved theme, apply it, return its name.
    Call this once at startup, after ``set_base_dir()`` has been called.
    """
    colors = load_saved_theme()
    apply_theme(colors)
    name = get_saved_theme_name()
    log.info("theme: applied '%s'", name)
    return name
