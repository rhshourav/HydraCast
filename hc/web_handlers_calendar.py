"""
hc/web_handlers_calendar.py — GET/POST handlers for the Events calendar tab.

Mixin into WebHandler exactly like _GetHandlersMixin / _PostHandlersMixin.

New routes
──────────
GET  /api/holidays?year=YYYY[&country=XX][&subdiv=XX]
       Returns [{date, name, country}, …] for the year.
       Falls back to country stored in app_settings.json when not supplied.

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
           "play_at":  "2026-06-15T14:30:00",   // ISO local datetime
           "streams":  [
             {"stream_name": "Main Channel", "file_path": "/media/promo.mp4"},
             {"stream_name": "HD Stream",    "file_path": "/media/promo.mp4"}
           ],
           "post_action": "compliance"           // reserved; always compliance
         }
       Response 200 on full success, 207 on partial, 400 on total failure:
         {"created": [{event_id, stream_name, file_path, play_at}, …],
          "errors":  [{stream_name, error}, …]}

Wiring (add to WebHandler.do_GET / do_POST dispatch):
──────────────────────────────────────────────────────
    # In do_GET:
    elif path == "/api/holidays":   self._get_holidays(qs)
    elif path == "/api/settings":   self._get_settings()

    # In do_POST:
    elif path == "/api/settings":      self._post_settings(body)
    elif path == "/api/events/bulk":   self._post_events_bulk(body)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger(__name__)


class _CalendarHandlersMixin:
    """Mixed into WebHandler — calendar-tab GET/POST route handlers."""

    # ------------------------------------------------------------------
    # GET /api/holidays
    # ------------------------------------------------------------------
    def _get_holidays(self, qs: Dict[str, Any]) -> None:
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
        settings = load_settings()

        try:
            year    = int(qs.get("year",    [datetime.now().year])[0])
            country = qs.get("country", [settings.get("holiday_country", "US")])[0].upper()
            subdiv_raw = qs.get("subdiv", [settings.get("holiday_subdiv") or ""])[0]
            subdiv  = subdiv_raw if subdiv_raw and subdiv_raw.lower() != "null" else None
        except (ValueError, IndexError) as exc:
            self._json({"error": f"Bad query parameters: {exc}"}, 400)
            return

        try:
            kwargs: Dict[str, Any] = {"years": year}
            if subdiv:
                kwargs["subdiv"] = subdiv
            h = _holidays.country_holidays(country, **kwargs)
            result = [
                {"date": str(date), "name": name, "country": country}
                for date, name in sorted(h.items())
            ]
            self._json(result)
        except Exception as exc:
            log.error("_get_holidays: %s", exc)
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
    # Creates one OneShotEvent per stream entry, all sharing the same
    # play_at timestamp.  Partial success is returned as HTTP 207.
    # ------------------------------------------------------------------
    def _post_events_bulk(self, body: bytes) -> None:
        # Import the module so we always get the live value of _WEB_MANAGER,
        # not a stale snapshot from when the mixin was first loaded.
        import hc.web_handler as _wh_mod
        from hc.json_manager import JSONManager
        from typing import Optional as _Opt

        mgr = _wh_mod._WEB_MANAGER
        if mgr is None:
            self._json({"error": "Manager not ready — try again shortly."}, 503)
            return

        # --- parse payload ---
        try:
            payload: Dict[str, Any] = json.loads(body.decode("utf-8"))
            play_at_str: str  = payload["play_at"]      # ISO local datetime
            streams_raw: List = payload["streams"]       # [{stream_name, file_path}]
            if not isinstance(streams_raw, list) or not streams_raw:
                raise ValueError("'streams' must be a non-empty list.")
            play_at = datetime.fromisoformat(play_at_str)
        except (KeyError, ValueError) as exc:
            self._json({"error": f"Bad payload: {exc}"}, 400)
            return

        # --- optional broadcast end time ---
        broadcast_end: _Opt[datetime] = None
        be_str = payload.get("broadcast_end", "")
        if be_str:
            try:
                broadcast_end = datetime.fromisoformat(be_str)
                # Must be strictly after play_at; silently discard if not
                if broadcast_end <= play_at:
                    log.warning(
                        "_post_events_bulk: broadcast_end %s is not after play_at %s — ignored",
                        be_str, play_at_str,
                    )
                    broadcast_end = None
            except ValueError:
                log.warning("_post_events_bulk: invalid broadcast_end %r — ignored", be_str)

        # --- create one event per stream ---
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

            # Guard: stream must exist in the manager
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
                log.error(
                    "bulk event failed for stream=%s: %s", stream_name, exc,
                )

        if not created:
            status = 400
        elif errors:
            status = 207   # Multi-Status: some succeeded, some failed
        else:
            status = 200

        self._json({"created": created, "errors": errors}, status)
