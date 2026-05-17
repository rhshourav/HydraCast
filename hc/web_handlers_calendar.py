"""
hc/web_handlers_calendar.py — GET/POST handlers for the Events calendar tab.

Mixin into WebHandler exactly like _GetHandlersMixin / _PostHandlersMixin.

Routes
──────
GET  /api/holidays?year=YYYY[&country=XX][&subdiv=XX][&refresh=1]
       Returns merged [{date, name, country, source}, …] for the year.
       Library holidays are cached to disk on first fetch; subsequent calls
       return the cache unless ?refresh=1 is supplied.
       Falls back to country stored in app_settings.json when not supplied.

GET  /api/holidays/custom
       Returns all user-defined holidays (all years, all countries).

POST /api/holidays/custom
       Add a custom holiday.
       Body: {"date": "2026-12-31", "name": "My Holiday", "country": "BD"}
       country is optional; defaults to "CUSTOM".

PUT  /api/holidays/custom
       Update an existing custom holiday.
       Body: {"date": "2026-12-31", "old_name": "My Holiday",
              "new_date": "2026-12-30", "new_name": "Updated Name",
              "new_country": "BD"}
       All new_* fields are optional.

DELETE /api/holidays/custom
       Remove a custom holiday by exact date + name.
       Body: {"date": "2026-12-31", "name": "My Holiday"}

DELETE /api/holidays/cache
       Purge the library cache for a specific year/country[/subdiv].
       Body: {"year": 2026, "country": "BD", "subdiv": null}

GET  /api/settings
       Returns the full app_settings.json dict.

POST /api/settings
       Merges the JSON body into app_settings.json and returns the result.
       Body: {"holiday_country": "BD", "holiday_subdiv": null}

POST /api/events/bulk
       Creates one OneShotEvent per stream entry in the payload and
       persists all of them via JSONManager.
       Body:
         {
           "play_at":  "2026-06-15T14:30:00",
           "streams":  [
             {"stream_name": "Main Channel", "file_path": "/media/promo.mp4"},
             {"stream_name": "HD Stream",    "file_path": "/media/promo.mp4"}
           ],
           "loop_count":    0,
           "broadcast_end": "2026-06-15T16:00:00"
         }
       Response 200 on full success, 207 on partial, 400 on total failure:
         {"created": [{event_id, stream_name, file_path, play_at}, …],
          "errors":  [{stream_name, error}, …]}

Wiring (add to WebHandler.do_GET / do_POST / do_PUT / do_DELETE dispatch):
──────────────────────────────────────────────────────────────────────────
    # In do_GET:
    elif path == "/api/holidays":        self._get_holidays(qs)
    elif path == "/api/holidays/custom": self._get_holidays_custom()
    elif path == "/api/settings":        self._get_settings()

    # In do_POST:
    elif path == "/api/settings":           self._post_settings(body)
    elif path == "/api/events/bulk":        self._post_events_bulk(body)
    elif path == "/api/holidays/custom":    self._post_holidays_custom(body)

    # In do_PUT:
    elif path == "/api/holidays/custom":    self._put_holidays_custom(body)

    # In do_DELETE:
    elif path == "/api/holidays/custom":    self._delete_holidays_custom(body)
    elif path == "/api/holidays/cache":     self._delete_holidays_cache(body)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class _CalendarHandlersMixin:
    """Mixed into WebHandler — calendar-tab GET/POST/PUT/DELETE route handlers."""

    # ------------------------------------------------------------------
    # GET /api/holidays
    # ------------------------------------------------------------------
    def _get_holidays(self, qs: Dict[str, Any]) -> None:
        """
        Return public + custom holidays for the requested year/country/subdiv.

        Library holidays are fetched from the `holidays` package on the first
        request and cached to disk.  Subsequent requests serve the cache.
        Pass ?refresh=1 to force a re-fetch from the library.
        """
        try:
            import holidays as _holidays  # type: ignore[import]
        except ImportError:
            self._json(
                {"error": "The 'holidays' Python package is not installed. "
                          "Run: pip install holidays"},
                500,
            )
            return

        from hc.web_settings_manager import load_settings
        from hc.web_holiday_store import (
            load_library_cache, save_library_cache, get_all_holidays,
        )

        settings = load_settings()

        try:
            year       = int(qs.get("year",    [datetime.now().year])[0])
            country    = qs.get("country", [settings.get("holiday_country", "US")])[0].upper()
            subdiv_raw = qs.get("subdiv",  [settings.get("holiday_subdiv") or ""])[0]
            subdiv     = subdiv_raw if subdiv_raw and subdiv_raw.lower() != "null" else None
            force_refresh = qs.get("refresh", ["0"])[0] == "1"
        except (ValueError, IndexError) as exc:
            self._json({"error": f"Bad query parameters: {exc}"}, 400)
            return

        # ── Try cache first (unless caller asked for a refresh) ───────────
        if not force_refresh:
            cached = load_library_cache(year, country, subdiv)
            if cached is not None:
                # Merge with custom and return
                result = get_all_holidays(year, country, subdiv)
                self._json(result)
                return

        # ── Fetch from the holidays library ───────────────────────────────
        try:
            kwargs: Dict[str, Any] = {"years": year}
            if subdiv:
                kwargs["subdiv"] = subdiv
            h = _holidays.country_holidays(country, **kwargs)
            lib_entries = [
                {"date": str(date), "name": name, "country": country, "source": "library"}
                for date, name in sorted(h.items())
            ]
        except Exception as exc:
            log.error("_get_holidays: library fetch failed: %s", exc)
            self._json({"error": str(exc)}, 500)
            return

        # ── Persist to disk cache ─────────────────────────────────────────
        try:
            save_library_cache(year, country, lib_entries, subdiv)
        except Exception as exc:
            log.warning("_get_holidays: could not write cache: %s", exc)

        # ── Merge with custom holidays and return ─────────────────────────
        try:
            result = get_all_holidays(year, country, subdiv)
        except Exception:
            result = lib_entries   # fallback: library only

        self._json(result)

    # ------------------------------------------------------------------
    # GET /api/holidays/custom
    # ------------------------------------------------------------------
    def _get_holidays_custom(self) -> None:
        """Return all user-defined holidays."""
        from hc.web_holiday_store import load_custom
        try:
            self._json(load_custom())
        except Exception as exc:
            log.error("_get_holidays_custom: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # POST /api/holidays/custom  — add a custom holiday
    # ------------------------------------------------------------------
    def _post_holidays_custom(self, body: bytes) -> None:
        """
        Add a user-defined holiday.
        Body: {"date": "YYYY-MM-DD", "name": "...", "country": "XX"}
        country is optional (defaults to "CUSTOM").
        """
        from hc.web_holiday_store import add_custom
        try:
            payload = json.loads(body.decode("utf-8"))
            date    = payload.get("date",    "").strip()
            name    = payload.get("name",    "").strip()
            country = payload.get("country", "CUSTOM").strip()
            if not date or not name:
                raise ValueError("'date' and 'name' are required.")
            entry = add_custom(date=date, name=name, country=country)
            self._json({"ok": True, "entry": entry})
        except (json.JSONDecodeError, ValueError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            log.error("_post_holidays_custom: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # PUT /api/holidays/custom  — update a custom holiday
    # ------------------------------------------------------------------
    def _put_holidays_custom(self, body: bytes) -> None:
        """
        Update an existing custom holiday.
        Body: {"date": "YYYY-MM-DD", "old_name": "...",
               "new_date": "...", "new_name": "...", "new_country": "..."}
        All new_* fields are optional.
        """
        from hc.web_holiday_store import update_custom
        try:
            payload  = json.loads(body.decode("utf-8"))
            date     = payload.get("date",     "").strip()
            old_name = payload.get("old_name", "").strip()
            if not date or not old_name:
                raise ValueError("'date' and 'old_name' are required.")
            updated = update_custom(
                date        = date,
                old_name    = old_name,
                new_date    = payload.get("new_date")    or None,
                new_name    = payload.get("new_name")    or None,
                new_country = payload.get("new_country") or None,
            )
            if updated is None:
                self._json(
                    {"error": f"No custom holiday found for date={date!r} name={old_name!r}"},
                    404,
                )
            else:
                self._json({"ok": True, "entry": updated})
        except (json.JSONDecodeError, ValueError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            log.error("_put_holidays_custom: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # DELETE /api/holidays/custom  — remove a custom holiday
    # ------------------------------------------------------------------
    def _delete_holidays_custom(self, body: bytes) -> None:
        """
        Delete a custom holiday.
        Body: {"date": "YYYY-MM-DD", "name": "..."}
        """
        from hc.web_holiday_store import delete_custom
        try:
            payload = json.loads(body.decode("utf-8"))
            date    = payload.get("date", "").strip()
            name    = payload.get("name", "").strip()
            if not date or not name:
                raise ValueError("'date' and 'name' are required.")
            removed = delete_custom(date=date, name=name)
            if removed:
                self._json({"ok": True})
            else:
                self._json(
                    {"error": f"No custom holiday found for date={date!r} name={name!r}"},
                    404,
                )
        except (json.JSONDecodeError, ValueError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            log.error("_delete_holidays_custom: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # DELETE /api/holidays/cache  — purge library cache
    # ------------------------------------------------------------------
    def _delete_holidays_cache(self, body: bytes) -> None:
        """
        Purge the on-disk library cache for a given year/country[/subdiv].
        Body: {"year": 2026, "country": "BD", "subdiv": null}
        """
        from hc.web_holiday_store import clear_library_cache
        try:
            payload = json.loads(body.decode("utf-8"))
            year    = int(payload.get("year", 0))
            country = str(payload.get("country", "")).strip().upper()
            subdiv_raw = payload.get("subdiv") or None
            subdiv  = str(subdiv_raw).strip() if subdiv_raw else None
            if not year or not country:
                raise ValueError("'year' and 'country' are required.")
            cleared = clear_library_cache(year=year, country=country, subdiv=subdiv)
            self._json({"ok": True, "cleared": cleared})
        except (json.JSONDecodeError, ValueError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            log.error("_delete_holidays_cache: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # GET /api/settings
    # ------------------------------------------------------------------
    def _get_settings(self) -> None:
        from hc.web_settings_manager import load_settings
        try:
            self._json(load_settings())
        except Exception as exc:
            log.error("_get_settings: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # POST /api/settings
    # ------------------------------------------------------------------
    def _post_settings(self, body: bytes) -> None:
        from hc.web_settings_manager import save_settings
        try:
            updates = json.loads(body.decode("utf-8"))
            if not isinstance(updates, dict):
                raise ValueError("Request body must be a JSON object.")
            result = save_settings(updates)
            self._json(result)
        except (json.JSONDecodeError, ValueError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            log.error("_post_settings: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # POST /api/events/bulk
    # ------------------------------------------------------------------
    def _post_events_bulk(self, body: bytes) -> None:
        import hc.web_handler as _wh_mod
        from hc.json_manager import JSONManager
        from typing import Optional as _Opt

        mgr = _wh_mod._WEB_MANAGER
        if mgr is None:
            self._json({"error": "Manager not ready — try again shortly."}, 503)
            return

        try:
            payload: Dict[str, Any] = json.loads(body.decode("utf-8"))
            play_at_str: str  = payload["play_at"]
            streams_raw: List = payload["streams"]
            if not isinstance(streams_raw, list) or not streams_raw:
                raise ValueError("'streams' must be a non-empty list.")
            play_at = datetime.fromisoformat(play_at_str)
            if play_at <= datetime.now():
                raise ValueError("Cannot schedule events in the past.")
        except (KeyError, ValueError) as exc:
            self._json({"error": f"Bad payload: {exc}"}, 400)
            return

        loop_count: int = 0
        try:
            loop_count = int(payload.get("loop_count", 0))
        except (TypeError, ValueError):
            loop_count = 0

        broadcast_end: Optional[datetime] = None
        be_str = payload.get("broadcast_end", "")
        if be_str:
            try:
                broadcast_end = datetime.fromisoformat(be_str)
                if broadcast_end <= play_at:
                    log.warning(
                        "_post_events_bulk: broadcast_end %s is not after play_at %s — ignored",
                        be_str, play_at_str,
                    )
                    broadcast_end = None
            except ValueError:
                log.warning("_post_events_bulk: invalid broadcast_end %r — ignored", be_str)

        created: List[Dict[str, Any]] = []
        errors:  List[Dict[str, Any]] = []

        for item in streams_raw:
            stream_name = item.get("stream_name", "").strip()
            file_path_s = item.get("file_path",   "").strip()

            if not stream_name or not file_path_s:
                errors.append({
                    "stream_name": stream_name or "?",
                    "error": "stream_name and file_path are required.",
                })
                continue

            if mgr.get_state(stream_name) is None:
                errors.append({
                    "stream_name": stream_name,
                    "error": f"Stream '{stream_name}' not found.",
                })
                log.warning("bulk event skipped — unknown stream: %s", stream_name)
                continue

            try:
                ev = JSONManager.add_event(
                    mgr.events,
                    stream_name   = stream_name,
                    file_path     = Path(file_path_s),
                    play_at       = play_at,
                    broadcast_end = broadcast_end,
                    loop_count    = loop_count,
                )
                ev_dict: Dict[str, Any] = {
                    "event_id":    ev.event_id,
                    "stream_name": ev.stream_name,
                    "file_path":   str(ev.file_path),
                    "play_at":     ev.play_at.isoformat(),
                }
                if broadcast_end is not None:
                    ev_dict["broadcast_end"] = broadcast_end.isoformat()
                created.append(ev_dict)
                log.info(
                    "bulk event created: stream=%s file=%s at=%s%s",
                    stream_name, file_path_s, play_at.isoformat(),
                    f" end={broadcast_end.isoformat()}" if broadcast_end else "",
                )
            except Exception as exc:
                errors.append({"stream_name": stream_name, "error": str(exc)})
                log.error("bulk event failed for stream=%s: %s", stream_name, exc)

        if not created:
            status = 400
        elif errors:
            status = 207
        else:
            status = 200

        self._json({"created": created, "errors": errors}, status)
