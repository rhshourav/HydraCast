"""
hc/resume_store.py — Disk-based per-stream resume-position storage.

Positions are written to  <BASE_DIR>/resume_positions.json  so they survive a
full program restart.  The file is keyed by stream name; each entry records
the file path, playback position in seconds, and a human-readable timestamp.

Thread-safe via a module-level lock.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resume_file() -> Path:
    from hc.constants import BASE_DIR
    return BASE_DIR() / "resume_positions.json"


def _load_all() -> Dict:
    fp = _resume_file()
    if not fp.exists():
        return {}
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("resume_store: failed to load '%s': %s", fp, exc)
        return {}


def _save_all(data: Dict) -> None:
    fp = _resume_file()
    try:
        fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.warning("resume_store: failed to save '%s': %s", fp, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_position(stream_name: str, file_path: Path, position: float) -> None:
    """
    Persist the current playback position for *stream_name*.

    Call this just before stopping/killing FFmpeg so the exact position is
    captured.  Position 0 is not saved (nothing to resume from).
    """
    if position <= 0:
        return
    with _lock:
        data = _load_all()
        data[stream_name] = {
            "file_path": str(file_path),
            "position":  round(position, 2),
            "saved_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        _save_all(data)
        log.info(
            "resume_store: saved %s → %s @ %.1fs",
            stream_name, file_path.name, position,
        )


def load_position(stream_name: str) -> Optional[Dict]:
    """
    Return saved resume info for *stream_name*, or ``None`` if absent.

    Returned dict keys:  ``file_path`` (str), ``position`` (float),
    ``saved_at`` (str).
    """
    with _lock:
        return _load_all().get(stream_name)


def clear_position(stream_name: str) -> None:
    """
    Delete the saved position for *stream_name* (e.g. after user chose
    "start from beginning").
    """
    with _lock:
        data = _load_all()
        if stream_name in data:
            del data[stream_name]
            _save_all(data)
            log.info("resume_store: cleared position for '%s'", stream_name)


def clear_all() -> None:
    """Wipe all saved positions (useful for factory-reset / troubleshooting)."""
    with _lock:
        _save_all({})
        log.info("resume_store: all positions cleared")
