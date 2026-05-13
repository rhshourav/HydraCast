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


def _wait_for_rtsp(port: int, timeout: float = 15.0, interval: float = 0.25) -> bool:
    """
    Wait until MediaMTX RTSP handler is fully ready by sending a real
    RTSP OPTIONS request and checking for a 200 OK response.

    _wait_for_port() only checks TCP connectivity.  On Windows, MediaMTX
    binds the TCP port 500-800 ms before its RTSP handler is initialised.
    FFmpeg connecting during that window sends ANNOUNCE and gets a
    400 Bad Request because the publisher path is not registered yet.

    This probe waits for a valid RTSP response, not just a TCP handshake.
    """
    import socket as _socket

    request = (
        b"OPTIONS rtsp://127.0.0.1:" + str(port).encode() +
        b"/ RTSP/1.0\r\n"
        b"CSeq: 1\r\n"
        b"User-Agent: HydraCast-probe\r\n"
        b"\r\n"
    )

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("127.0.0.1", port))
            s.sendall(request)
            resp = s.recv(256).decode(errors="replace")
            s.close()
            # MediaMTX returns "RTSP/1.0 200 OK" when fully ready.
            if "RTSP/1.0 200" in resp:
                return True
        except Exception:
            pass
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
