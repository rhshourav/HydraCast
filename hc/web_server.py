"""hc/web_server.py  —  HTTP server classes for HydraCast Web UI."""
from __future__ import annotations

import logging
import threading
from http.server import HTTPServer
from typing import Optional

from hc.web_handler import WebHandler

log = logging.getLogger(__name__)

# =============================================================================
# SERVER
# =============================================================================
class _HydraCastHTTPServer(HTTPServer):
    allow_reuse_address = True


class WebServer:
    def __init__(self, port: int = 8080) -> None:
        self._port   = port
        self._server: Optional[_HydraCastHTTPServer] = None
        self._thread: Optional[threading.Thread]     = None

    def start(self) -> None:
        try:
            self._server = _HydraCastHTTPServer(("0.0.0.0", self._port), WebHandler)
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True, name="webui",
            )
            self._thread.start()
            log.info("Web UI → http://0.0.0.0:%d", self._port)
        except OSError as exc:
            log.error(
                "Web UI failed to bind :%d — %s. "
                "Try --web-port to use a different port.",
                self._port, exc,
            )
        except Exception as exc:
            log.error("Web UI failed to start: %s", exc)

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
