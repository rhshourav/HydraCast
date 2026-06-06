"""hc/web_server.py  —  HTTP/HTTPS server classes for HydraCast Web UI.

Dual-listener design
────────────────────
When SSL is active two sockets are opened:

  • HTTPS listener  (default :443)  — serves the full Web UI over TLS.
  • HTTP  listener  (default :80)   — issues a 301 redirect to the HTTPS
                                      URL for every request.  Browsers that
                                      visit http://host/ are bounced to
                                      https://host/ automatically.

Disable the HTTP redirect listener with --http-port 0.
When SSL is NOT active (no cert + not port 443) only the HTTP listener
starts and it serves the full UI directly (no redirect).

SSL quick-start
───────────────
Drop your certificate files into the  ssl/  folder next to hydracast.py:

    ssl/cert.pem   <- certificate (chain)
    ssl/key.pem    <- private key

HydraCast will automatically detect them and start in HTTPS mode.
When the HTTPS port is 443 and no cert files are found, a self-signed
certificate is generated automatically into ssl/ (valid 10 years).

Alternatively pass explicit paths via CLI:

    python hydracast.py --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem

Self-signed certificate (for local testing only):

    openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem \
        -out ssl/cert.pem -sha256 -days 365 --nodes \
        -subj "/CN=localhost"
"""
from __future__ import annotations

import logging
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from hc.web_handler import WebHandler

log = logging.getLogger(__name__)


# =============================================================================
# BASE SERVER  (shared allow_reuse_address)
# =============================================================================
class _HydraCastHTTPServer(HTTPServer):
    allow_reuse_address = True


# =============================================================================
# HTTP -> HTTPS REDIRECT HANDLER
# =============================================================================
class _RedirectHandler(BaseHTTPRequestHandler):
    """
    Responds to every HTTP request with a permanent redirect (301) to the
    same path/query on the HTTPS host.

    ``server.https_port`` must be set on the server instance before use.
    """

    def log_message(self, *args) -> None:
        pass  # suppress default access log

    def _redirect(self) -> None:
        parsed      = urlparse(self.path)
        https_port: int = getattr(self.server, "https_port", 443)
        host_header = self.headers.get("Host", "")
        # Strip any existing port from the Host header before rewriting.
        host_only   = host_header.split(":")[0] if host_header else "localhost"

        if https_port == 443:
            location = f"https://{host_only}{parsed.path}"
        else:
            location = f"https://{host_only}:{https_port}{parsed.path}"
        if parsed.query:
            location += f"?{parsed.query}"

        body = (
            b"<html><body>"
            b"<h1>301 Moved Permanently</h1>"
            b"<p>This site requires HTTPS. "
            b'<a href="' + location.encode() + b'">Click here</a>.</p>'
            b"</body></html>"
        )
        self.send_response(301)
        self.send_header("Location",       location)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection",     "close")
        # HSTS header so browsers pin to HTTPS for a year after the first visit.
        self.send_header("Strict-Transport-Security", "max-age=31536000")
        self.end_headers()
        self.wfile.write(body)

    # Redirect all methods the same way.
    do_GET  = _redirect
    do_POST = _redirect
    do_HEAD = _redirect
    do_PUT  = _redirect


# =============================================================================
# PORT DEFAULTS
# =============================================================================
_PORT_HTTPS         = 443
_PORT_HTTP          = 80
_PORT_HTTP_FALLBACK = 8080  # used when SSL generation fails


# =============================================================================
# WEBSERVER
# =============================================================================
class WebServer:
    """
    Manages one HTTPS server (full UI) and one HTTP redirect server.

    Parameters
    ----------
    port      : HTTPS port override (None -> read from constants.WEB_PORT).
    http_port : HTTP redirect port override (None -> read from constants.get_http_port()).
                Pass 0 to disable the HTTP redirect listener entirely.
    """

    def __init__(
        self,
        port:      Optional[int] = None,
        http_port: Optional[int] = None,
    ) -> None:
        self._port      = port
        self._http_port = http_port

        self._https_server: Optional[_HydraCastHTTPServer] = None
        self._http_server:  Optional[_HydraCastHTTPServer] = None
        self._https_thread: Optional[threading.Thread]     = None
        self._http_thread:  Optional[threading.Thread]     = None

    # ------------------------------------------------------------------
    # SSL helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _generate_self_signed(cert: Path, key: Path) -> bool:
        """
        Generate a self-signed certificate using the ``cryptography`` package
        (preferred) or fall back to shelling out to ``openssl``.
        Returns True on success, False on failure.
        """
        # Try cryptography (pure-Python, no openssl binary needed)
        try:
            import datetime
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa

            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
            ])
            now = datetime.datetime.utcnow()
            cert_obj = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now)
                .not_valid_after(now + datetime.timedelta(days=3650))
                .add_extension(
                    x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                    critical=False,
                )
                .sign(private_key, hashes.SHA256())
            )
            key.write_bytes(
                private_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
            cert.write_bytes(cert_obj.public_bytes(serialization.Encoding.PEM))
            log.info("SSL: self-signed certificate generated via cryptography -> %s", cert)
            return True

        except ImportError:
            pass  # cryptography not installed; try openssl binary
        except Exception as exc:
            log.warning("SSL: cryptography cert generation failed: %s", exc)

        # Fallback: shell out to openssl
        try:
            subprocess.run(
                [
                    "openssl", "req", "-x509",
                    "-newkey", "rsa:2048",
                    "-keyout", str(key),
                    "-out",    str(cert),
                    "-sha256", "-days", "3650",
                    "-nodes",  "-subj", "/CN=localhost",
                ],
                check=True,
                capture_output=True,
            )
            log.info("SSL: self-signed certificate generated via openssl -> %s", cert)
            return True
        except FileNotFoundError:
            log.warning(
                "SSL: openssl binary not found and cryptography package not installed. "
                "Install the cryptography package:  pip install cryptography"
            )
        except subprocess.CalledProcessError as exc:
            log.warning("SSL: openssl cert generation failed: %s", exc.stderr.decode())
        except Exception as exc:
            log.warning("SSL: openssl cert generation error: %s", exc)

        return False

    @staticmethod
    def _resolve_ssl(https_port: int) -> "tuple[Optional[Path], Optional[Path]]":
        """
        Return (cert_path, key_path) or (None, None).  Priority:
          1. CLI flags  (--ssl-cert / --ssl-key)
          2. Default    ssl/cert.pem + ssl/key.pem
          3. Auto-generate a self-signed cert when https_port == 443
        """
        from hc.constants import SSL_CERT, SSL_KEY, SSL_DIR, get_ssl_cert, get_ssl_key

        cli_cert = get_ssl_cert()
        cli_key  = get_ssl_key()
        if cli_cert and cli_key:
            cert, key = Path(cli_cert), Path(cli_key)
            if cert.is_file() and key.is_file():
                return cert, key
            log.warning(
                "SSL: --ssl-cert/--ssl-key provided but file(s) not found "
                "(%s, %s) -- falling back to auto-detect.", cert, key,
            )

        cert = SSL_CERT()
        key  = SSL_KEY()
        if cert.is_file() and key.is_file():
            return cert, key

        if https_port == _PORT_HTTPS:
            log.info(
                "SSL: no certificate found for port 443 -- "
                "generating a self-signed certificate in %s/", SSL_DIR(),
            )
            if WebServer._generate_self_signed(cert, key):
                return cert, key
            log.warning(
                "SSL: could not generate a self-signed cert -- falling back to "
                "plain HTTP on port %d.  Install the 'cryptography' package or "
                "drop ssl/cert.pem + ssl/key.pem to enable HTTPS.", _PORT_HTTP_FALLBACK,
            )

        return None, None

    @staticmethod
    def _make_ssl_context(cert: Path, key: Path) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile=str(cert), keyfile=str(key))
        return ctx

    @staticmethod
    def _spawn(server: _HydraCastHTTPServer, name: str) -> threading.Thread:
        t = threading.Thread(target=server.serve_forever, daemon=True, name=name)
        t.start()
        return t

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        from hc.constants import LISTEN_ADDR, WEB_PORT, get_http_port

        bind_addr  = LISTEN_ADDR()
        https_port = self._port      if self._port      is not None else WEB_PORT
        http_port  = self._http_port if self._http_port is not None else get_http_port()

        cert, key = self._resolve_ssl(https_port)
        use_ssl   = cert is not None

        # SSL generation failed on port 443 -> fall back to plain HTTP on 8080.
        if not use_ssl and https_port == _PORT_HTTPS:
            https_port = _PORT_HTTP_FALLBACK

        # ------------------------------------------------------------------
        # HTTPS (or plain-HTTP fallback) listener
        # ------------------------------------------------------------------
        try:
            self._https_server = _HydraCastHTTPServer(
                (bind_addr, https_port), WebHandler
            )
            if use_ssl:
                ctx = self._make_ssl_context(cert, key)
                self._https_server.socket = ctx.wrap_socket(
                    self._https_server.socket, server_side=True
                )
                log.info(
                    "Web UI (HTTPS) -> https://%s:%d  [cert: %s]",
                    bind_addr, https_port, cert,
                )
            else:
                log.info("Web UI (HTTP) -> http://%s:%d", bind_addr, https_port)

            self._https_thread = self._spawn(self._https_server, "webui-https")

        except ssl.SSLError as exc:
            log.error(
                "SSL error -- could not wrap socket (cert=%s key=%s): %s. "
                "Check that the certificate and private key are valid and match.",
                cert, key, exc,
            )
            return
        except OSError as exc:
            log.error(
                "Web UI HTTPS failed to bind %s:%d -- %s. "
                "Try --web-port to use a different port, or run with elevated "
                "privileges for ports below 1024.",
                bind_addr, https_port, exc,
            )
            return
        except Exception as exc:
            log.error("Web UI HTTPS failed to start: %s", exc)
            return

        # ------------------------------------------------------------------
        # HTTP -> HTTPS redirect listener (only when SSL is active)
        # ------------------------------------------------------------------
        if not use_ssl:
            # No SSL active -> the main listener IS plain HTTP; no redirect.
            return

        if http_port == 0:
            log.info("Web UI: HTTP redirect listener disabled (--http-port 0).")
            return

        try:
            self._http_server = _HydraCastHTTPServer(
                (bind_addr, http_port), _RedirectHandler
            )
            # Tell _RedirectHandler which HTTPS port to send browsers to.
            self._http_server.https_port = https_port  # type: ignore[attr-defined]

            log.info(
                "Web UI (HTTP->HTTPS redirect) -> http://%s:%d  ->  https://%s:%d",
                bind_addr, http_port, bind_addr, https_port,
            )
            self._http_thread = self._spawn(self._http_server, "webui-http-redirect")

        except OSError as exc:
            log.warning(
                "Web UI: HTTP redirect listener failed to bind %s:%d -- %s. "
                "The HTTPS server is still running. "
                "Try --http-port to use a different port, or --http-port 0 to "
                "disable the redirect listener entirely.",
                bind_addr, http_port, exc,
            )
        except Exception as exc:
            log.warning(
                "Web UI: HTTP redirect listener failed to start: %s. "
                "The HTTPS server is still running.", exc,
            )

    def stop(self) -> None:
        for server in (self._https_server, self._http_server):
            if server:
                try:
                    server.shutdown()
                except Exception:
                    pass
        self._https_server = None
        self._http_server  = None
