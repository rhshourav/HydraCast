"""
hc/utils.py  —  Utility helpers (networking, formatting, path safety).
"""
from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Optional

import psutil


def _local_ip() -> str:
    """Best-effort LAN IP detection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _wait_for_port(port: int, host: str = "127.0.0.1",
                   timeout: float = 12.0, interval: float = 0.25) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(port, "127.0.0.1"):
            return True
        if host not in ("127.0.0.1", "0.0.0.0") and _port_in_use(port, host):
            return True
        time.sleep(interval)
    return False


def _wait_for_rtsp(port: int, timeout: float = 20.0, interval: float = 0.25,
                   path: str = "stream",
                   check_alive=None) -> bool:
    """
    Wait until MediaMTX RTSP handler is fully ready by sending a real
    RTSP OPTIONS request, then a DESCRIBE on the target path.

    _wait_for_port() only checks TCP connectivity.  On Windows, MediaMTX
    binds the TCP port 500–800 ms before its RTSP handler is initialised,
    and the path handler is registered another 1–2 s after that.
    FFmpeg connecting during either gap sends ANNOUNCE and gets 400 Bad
    Request because the publisher path is not registered yet.

    Phase 1 — OPTIONS: any RTSP/1.0 response means the engine is alive.
    Phase 2 — DESCRIBE: 200 or 404 means the path handler is registered.
               400 = path not yet known — keep waiting.

    Parameters
    ----------
    check_alive:
        Optional zero-argument callable that returns False if the
        MediaMTX process has died.  When provided, the probe exits
        early rather than waiting out the full timeout.
    """
    import socket as _socket
    from hc.constants import LISTEN_ADDR as _LISTEN_ADDR

    port_s  = str(port).encode()
    path_b  = path.encode()

    # Build probe requests for loopback …
    options_req_lo = (
        b"OPTIONS rtsp://127.0.0.1:" + port_s +
        b"/ RTSP/1.0\r\nCSeq: 1\r\nUser-Agent: HydraCast-probe\r\n\r\n"
    )
    describe_req_lo = (
        b"DESCRIBE rtsp://127.0.0.1:" + port_s +
        b"/" + path_b +
        b" RTSP/1.0\r\nCSeq: 2\r\nUser-Agent: HydraCast-probe\r\n"
        b"Accept: application/sdp\r\n\r\n"
    )

    # … and also for the configured listen address when it is a specific IP
    # (not 0.0.0.0).  If LISTEN_ADDR is a specific IP, MediaMTX only binds
    # that interface and loopback probes will get "Connection refused".
    _la = _LISTEN_ADDR()
    _alt_host: str | None = _la if (_la and _la not in ("0.0.0.0", "127.0.0.1")) else None

    def _build_req(verb: bytes, host: str, cseq: int, extra: bytes = b"") -> bytes:
        h = host.encode()
        return (
            verb + b" rtsp://" + h + b":" + port_s + b"/" +
            (path_b if verb == b"DESCRIBE" else b"") +
            b" RTSP/1.0\r\nCSeq: " + str(cseq).encode() +
            b"\r\nUser-Agent: HydraCast-probe\r\n" + extra + b"\r\n"
        )

    def _probe(req: bytes, host: str = "127.0.0.1") -> str:
        """
        Open a TCP connection, send *req*, collect the full response
        (until headers end or socket times out), return it as str.
        Uses a 3-second socket timeout (was 1.5 s) and a recv loop so
        partial TCP deliveries on Windows are reassembled correctly.
        """
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((host, port))
            s.sendall(req)
            chunks: list[bytes] = []
            deadline_inner = time.time() + 3.0
            while time.time() < deadline_inner:
                try:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    # Stop once we have the end-of-headers marker.
                    if b"\r\n\r\n" in b"".join(chunks):
                        break
                except _socket.timeout:
                    break
            s.close()
            return b"".join(chunks).decode(errors="replace")
        except Exception:
            return ""

    deadline = time.time() + timeout
    options_ok = False

    while time.time() < deadline:
        # Early exit if the MediaMTX process has died.
        if check_alive is not None and not check_alive():
            return False

        if not options_ok:
            # Phase 1: any RTSP/1.0 response means the engine is accepting
            # connections (we no longer require exactly "200 OK" since some
            # MediaMTX builds return "200 OK" while others may differ).
            resp = _probe(options_req_lo)
            if not resp and _alt_host:
                resp = _probe(
                    _build_req(b"OPTIONS", _alt_host, 1), _alt_host
                )
            if "RTSP/1.0" in resp:
                options_ok = True
                # Fall through immediately to DESCRIBE in the same iteration.
        
        if options_ok:
            # Phase 2: verify path handler is registered.
            # 200 = publisher already present; 404 = path known, no publisher yet.
            # Both mean the path is registered and FFmpeg can ANNOUNCE.
            # 400 = path not yet known — keep waiting.
            # Any other RTSP response also means the path handler is alive.
            resp = _probe(describe_req_lo)
            if not resp and _alt_host:
                resp = _probe(
                    _build_req(b"DESCRIBE", _alt_host, 2,
                               b"Accept: application/sdp\r\n"),
                    _alt_host,
                )
            if "RTSP/1.0 200" in resp or "RTSP/1.0 404" in resp:
                return True
            # Accept any non-400 RTSP response as "handler alive" too.
            if "RTSP/1.0" in resp and "RTSP/1.0 400" not in resp:
                return True

        time.sleep(interval)

    return False


def _kill_orphan_on_port(port: int) -> None:
    """Terminate any process listening on the given TCP port."""
    try:
        for conn in psutil.net_connections("tcp"):
            if conn.laddr.port == port and conn.status in ("LISTEN", "ESTABLISHED"):
                if conn.pid:
                    try:
                        psutil.Process(conn.pid).terminate()
                    except Exception:
                        pass
    except Exception:
        pass


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


def _fmt_duration(s: float) -> str:
    s = int(max(0, s))
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


def _safe_path(p: Path, root: Path) -> Optional[Path]:
    """Return resolved path only if it sits inside *root*, else None."""
    try:
        resolved      = p.resolve()
        root_resolved = root.resolve()
        resolved.relative_to(root_resolved)
        return resolved
    except (ValueError, RuntimeError):
        return None
