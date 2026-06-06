"""
hc/web_holiday_store.py — Local holiday storage for HydraCast.

Provides two layers:
  1. Library cache  — public holidays fetched from the `holidays` package are
     saved to disk so they survive restarts and work offline.
  2. Custom holidays — user-defined entries stored in a separate file;
     these are never overwritten by library refreshes.

Storage layout  (<config>/holidays/)
──────────────────────────────────────
  library_YYYY_CC[_SS].hcf    — cached library holidays
  custom.hcf                  — user-defined holidays (all years / countries)

JSON schema for a holiday entry
────────────────────────────────
  {
    "date":    "2026-12-25",        // ISO date string
    "name":    "Christmas Day",
    "country": "US",                // upper-case ISO-3166-1-alpha-2
    "source":  "library" | "custom"
  }
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hc.constants import CONFIG_DIR

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def _holiday_dir() -> Path:
    d = CONFIG_DIR() / "holidays"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _library_path(year: int, country: str, subdiv: Optional[str] = None) -> Path:
    suffix = f"_{subdiv}" if subdiv else ""
    return _holiday_dir() / f"library_{year}_{country}{suffix}.hcf"


def _custom_path() -> Path:
    return _holiday_dir() / "custom.hcf"


# ---------------------------------------------------------------------------
# Low-level read / write
# ---------------------------------------------------------------------------

def _read_json(p: Path) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception as exc:
        log.warning("holiday_store: could not read %s — %s", p.name, exc)
    return []


def _write_json(p: Path, data: List[Dict[str, Any]]) -> None:
    tmp = p.with_suffix(".hcf.tmp")
    try:
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(p)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        log.error("holiday_store: could not write %s — %s", p.name, exc)
        raise


# ---------------------------------------------------------------------------
# Library cache
# ---------------------------------------------------------------------------

def load_library_cache(
    year: int,
    country: str,
    subdiv: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Return cached library holidays or None if the cache file is absent."""
    p = _library_path(year, country, subdiv)
    if not p.exists():
        return None
    data = _read_json(p)
    log.debug("holiday_store: loaded %d library entries from cache (%s)", len(data), p.name)
    return data


def save_library_cache(
    year: int,
    country: str,
    entries: List[Dict[str, Any]],
    subdiv: Optional[str] = None,
) -> None:
    """Persist library holidays fetched from the `holidays` package."""
    p = _library_path(year, country, subdiv)
    _write_json(p, entries)
    log.info(
        "holiday_store: cached %d library holidays for %s %s%s",
        len(entries), year, country, f"/{subdiv}" if subdiv else "",
    )


def clear_library_cache(
    year: int,
    country: str,
    subdiv: Optional[str] = None,
) -> bool:
    """Delete the library cache for a specific year/country/subdiv combo."""
    p = _library_path(year, country, subdiv)
    if p.exists():
        p.unlink()
        log.info("holiday_store: cleared library cache %s", p.name)
        return True
    return False


# ---------------------------------------------------------------------------
# Custom holidays
# ---------------------------------------------------------------------------

def load_custom() -> List[Dict[str, Any]]:
    """Return all user-defined holidays."""
    return _read_json(_custom_path())


def add_custom(
    date: str,
    name: str,
    country: str = "CUSTOM",
) -> Dict[str, Any]:
    """
    Add a user-defined holiday and persist it.

    Parameters
    ----------
    date:
        ISO date string  e.g. "2026-12-31"
    name:
        Display name for the holiday.
    country:
        Optional ISO country code (defaults to "CUSTOM").

    Returns the newly created entry.
    Raises ValueError on bad date format.
    """
    # Validate date
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date '{date}'. Expected YYYY-MM-DD.")

    entries = load_custom()

    # Prevent exact duplicates (same date + name + country)
    country_up = country.strip().upper() or "CUSTOM"
    for e in entries:
        if e["date"] == date and e["name"] == name and e["country"] == country_up:
            log.debug("holiday_store: duplicate custom entry ignored (%s %s)", date, name)
            return e

    entry: Dict[str, Any] = {
        "date":    date,
        "name":    name.strip(),
        "country": country_up,
        "source":  "custom",
    }
    entries.append(entry)
    _write_json(_custom_path(), entries)
    log.info("holiday_store: added custom holiday %s '%s'", date, name)
    return entry


def delete_custom(date: str, name: str) -> bool:
    """
    Remove a user-defined holiday by exact date + name match.

    Returns True if an entry was removed.
    """
    entries = load_custom()
    before  = len(entries)
    entries = [
        e for e in entries
        if not (e["date"] == date and e["name"] == name)
    ]
    if len(entries) == before:
        return False
    _write_json(_custom_path(), entries)
    log.info("holiday_store: removed custom holiday %s '%s'", date, name)
    return True


def update_custom(
    date: str,
    old_name: str,
    new_date: Optional[str] = None,
    new_name: Optional[str] = None,
    new_country: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update an existing custom holiday in-place.

    Identifies the entry by (date, old_name).  Any supplied new_* value
    replaces the corresponding field.  Returns the updated entry or None
    if the entry was not found.
    """
    entries = load_custom()
    for e in entries:
        if e["date"] == date and e["name"] == old_name:
            if new_date is not None:
                try:
                    datetime.strptime(new_date, "%Y-%m-%d")
                except ValueError:
                    raise ValueError(f"Invalid date '{new_date}'. Expected YYYY-MM-DD.")
                e["date"] = new_date
            if new_name is not None:
                e["name"] = new_name.strip()
            if new_country is not None:
                e["country"] = new_country.strip().upper()
            _write_json(_custom_path(), entries)
            log.info("holiday_store: updated custom holiday → %s", e)
            return e
    return None


# ---------------------------------------------------------------------------
# Merged view
# ---------------------------------------------------------------------------

def get_all_holidays(
    year: int,
    country: str,
    subdiv: Optional[str] = None,
    include_custom: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return library holidays (from cache) merged with matching custom holidays
    for the given year.

    Custom holidays without an explicit country are always included; those
    with a country are included only when country matches.
    """
    lib = load_library_cache(year, country, subdiv) or []
    if not include_custom:
        return sorted(lib, key=lambda e: e["date"])

    custom_all = load_custom()
    country_up = country.upper()
    custom = [
        e for e in custom_all
        if (
            e["date"].startswith(str(year))
            and (e.get("country", "CUSTOM") in ("CUSTOM", country_up))
        )
    ]

    # Merge; custom entries shadow library entries with identical date+name
    combined: Dict[str, Dict[str, Any]] = {}
    for e in lib:
        combined[f"{e['date']}|{e['name']}"] = e
    for e in custom:
        combined[f"{e['date']}|{e['name']}"] = e

    return sorted(combined.values(), key=lambda e: e["date"])
