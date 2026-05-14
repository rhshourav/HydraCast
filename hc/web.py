"""
hc/web.py  —  Simple, stripped-down Web UI for HydraCast.

Design goals:
  • Zero external dependencies loaded from CDN (no HLS.js, no Google Fonts).
  • One file, no modals, no drag-drop, no fancy animations.
  • Every button does exactly one thing and the response is shown in-page.
  • Polling every 2 s to keep stream table fresh.
  • Logs tab shows the LogBuffer in real time.
  • Config tab shows streams.csv contents as plain text (read-only).
  • Upload tab for media files.

Implementation is split across:
  hc/web_html.py        — _HTML template string
  hc/web_csvmanager.py  — CSVManager compatibility shim
  hc/web_handler.py     — WebHandler + library cache + helper functions
  hc/web_server.py      — WebServer / _HydraCastHTTPServer
"""
from __future__ import annotations

# Re-export the full public API so any code that does
#   from hc.web import WebServer, WebHandler, CSVManager, _WEB_MANAGER
# or
#   import hc.web; hc.web._WEB_MANAGER = mgr
# continues to work without modification.

from hc.web_html import _HTML                              # noqa: F401
from hc.web_csvmanager import CSVManager                   # noqa: F401
from hc.web_handler import (                               # noqa: F401
    WebHandler,
    _WEB_MANAGER,
    _SEC_HEADERS,
    _get_library_cached,
    _invalidate_lib_cache,
    _notify_folder_upload,
    _get_next_in_queue,
)
from hc.web_server import WebServer, _HydraCastHTTPServer  # noqa: F401

# Allow callers to set the module-level manager via
#   import hc.web; hc.web._WEB_MANAGER = mgr
# by forwarding the write through to web_handler where it is actually used.
import hc.web_handler as _wh
import sys as _sys

class _WebModule(_sys.modules[__name__].__class__):
    """Custom module class so ``hc.web._WEB_MANAGER = x`` updates web_handler."""
    @property
    def _WEB_MANAGER(self):
        return _wh._WEB_MANAGER

    @_WEB_MANAGER.setter
    def _WEB_MANAGER(self, value):
        _wh._WEB_MANAGER = value

    @property
    def _GLOG(self):
        return _wh._GLOG

    @_GLOG.setter
    def _GLOG(self, value):
        _wh._GLOG = value

    @property
    def _lib_cache(self):
        return _wh._lib_cache

    @_lib_cache.setter
    def _lib_cache(self, value):
        _wh._lib_cache = value

    @property
    def _lib_cache_ts(self):
        return _wh._lib_cache_ts

    @_lib_cache_ts.setter
    def _lib_cache_ts(self, value):
        _wh._lib_cache_ts = value

    @property
    def _LIB_CACHE_TTL(self):
        return _wh._LIB_CACHE_TTL

_sys.modules[__name__].__class__ = _WebModule
