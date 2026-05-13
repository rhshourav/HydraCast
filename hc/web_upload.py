"""
hc/web_upload.py  —  Chunked, multithreaded upload session manager.

Protocol
────────
  POST /api/upload/init      JSON {filename, size, total_chunks, subdir}
       ← {ok, session_id, chunk_size}

  POST /api/upload/chunk     multipart {session_id, chunk_index, chunk:<blob>}
       ← {ok, received, total}                     (N requests in parallel)

  POST /api/upload/finalize  JSON {session_id}
       ← {ok, path, msg}

  GET  /api/upload/status?session_id=X
       ← {ok, received, total, pct}

Each chunk is written straight to disk (tmp dir) as it arrives — the server
never buffers the entire file in memory.  All sessions are tracked in a
module-level UploadSessionManager that runs a background cleanup thread to
remove stale/expired temp dirs automatically.
"""
from __future__ import annotations

import logging
import re
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set

from hc.constants import MEDIA_DIR, SUPPORTED_EXTS, UPLOAD_MAX_BYTES
from hc.utils import _safe_path

log = logging.getLogger(__name__)

# ── Tunables ──────────────────────────────────────────────────────────────────
CHUNK_SIZE     = 4 * 1024 * 1024   # 4 MB — suggested chunk size sent to client
SESSION_TTL    = 30 * 60            # seconds before an incomplete session expires
CLEANUP_PERIOD = 5  * 60            # how often the cleanup thread wakes


# =============================================================================
# Session object
# =============================================================================
@dataclass
class UploadSession:
    session_id:   str
    filename:     str          # original (cleaned) filename
    safe_name:    str          # filesystem-safe version
    subdir:       str          # destination subdir (sanitised)
    total_chunks: int
    total_size:   int          # declared by client (bytes)
    tmp_dir:      Path
    created_at:   float = field(default_factory=time.monotonic)
    received:     Set[int] = field(default_factory=set)
    _lock:        threading.Lock = field(default_factory=threading.Lock)

    # ── Convenience ───────────────────────────────────────────────────────────
    @property
    def is_complete(self) -> bool:
        return len(self.received) >= self.total_chunks

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > SESSION_TTL

    @property
    def pct(self) -> int:
        if self.total_chunks == 0:
            return 100
        return min(100, round(len(self.received) * 100 / self.total_chunks))

    def dest_dir(self) -> Path:
        base = MEDIA_DIR()
        return (base / self.subdir) if self.subdir else base

    def chunk_path(self, index: int) -> Path:
        return self.tmp_dir / f"{index:05d}.part"


# =============================================================================
# Session manager
# =============================================================================
class UploadSessionManager:
    """Thread-safe registry of in-progress chunked uploads."""

    def __init__(self) -> None:
        self._sessions: Dict[str, UploadSession] = {}
        self._lock      = threading.Lock()
        # Daemon thread removes stale sessions and their temp dirs.
        threading.Thread(
            target=self._cleanup_loop, daemon=True, name="upload-cleanup"
        ).start()

    # ── Public API ────────────────────────────────────────────────────────────

    def create(
        self,
        filename:     str,
        total_size:   int,
        total_chunks: int,
        subdir:       str,
    ) -> UploadSession:
        """Validate inputs, allocate a temp dir, and register a new session."""
        # ── Filename validation ───────────────────────────────────────────────
        fname_clean = Path(filename).name
        ext = Path(fname_clean).suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise ValueError(f"Unsupported file type: {ext}")
        safe_name = re.sub(r'[^\w.\-]', '_', fname_clean)
        if not safe_name or safe_name.startswith('.'):
            raise ValueError("Invalid filename")

        # ── Size validation ───────────────────────────────────────────────────
        if total_size > UPLOAD_MAX_BYTES:
            limit_gb = UPLOAD_MAX_BYTES // (1024 ** 3)
            raise ValueError(f"File exceeds {limit_gb} GB limit")
        if not (1 <= total_chunks <= 50_000):
            raise ValueError("Chunk count must be between 1 and 50 000")

        # ── Subdir sanitisation ───────────────────────────────────────────────
        sub = re.sub(r'[/\\<>"|?*\x00]', '_', (subdir or ""))[:128]
        sub = re.sub(r'\.\.', '_', sub)

        # ── Destination path check ────────────────────────────────────────────
        dest_dir = (MEDIA_DIR() / sub) if sub else MEDIA_DIR()
        if _safe_path(dest_dir, MEDIA_DIR()) is None:
            raise ValueError("Invalid upload directory (path traversal denied)")

        # ── Allocate session ──────────────────────────────────────────────────
        sid     = uuid.uuid4().hex
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"hcup_{sid}_"))

        sess = UploadSession(
            session_id   = sid,
            filename     = fname_clean,
            safe_name    = safe_name,
            subdir       = sub,
            total_chunks = total_chunks,
            total_size   = total_size,
            tmp_dir      = tmp_dir,
        )
        with self._lock:
            self._sessions[sid] = sess

        log.info(
            "Upload session created: %s  file=%s  chunks=%d  declared_size=%d B",
            sid, safe_name, total_chunks, total_size,
        )
        return sess

    def get(self, session_id: str) -> Optional[UploadSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def save_chunk(self, session_id: str, chunk_index: int, data: bytes) -> UploadSession:
        """Write one chunk to disk and mark it as received. Thread-safe."""
        sess = self._require(session_id)

        if not (0 <= chunk_index < sess.total_chunks):
            raise ValueError(
                f"Chunk index {chunk_index} out of range "
                f"(expected 0–{sess.total_chunks - 1})"
            )

        # Write to a per-chunk file so concurrent writes never conflict.
        sess.chunk_path(chunk_index).write_bytes(data)

        with sess._lock:
            sess.received.add(chunk_index)

        log.debug(
            "Chunk %d/%d saved  session=%s  size=%d B",
            chunk_index + 1, sess.total_chunks, session_id, len(data),
        )
        return sess

    def finalize(self, session_id: str) -> Path:
        """
        Assemble all chunk files into the final media file.

        Raises if any chunk is still missing.
        Always removes the temp dir and the session entry on exit.
        """
        sess = self._require(session_id)

        with sess._lock:
            missing = sorted(set(range(sess.total_chunks)) - sess.received)

        if missing:
            preview = missing[:10]
            suffix  = "…" if len(missing) > 10 else ""
            raise ValueError(
                f"{len(missing)} chunk(s) missing: {preview}{suffix}"
            )

        dest_dir = sess.dest_dir()
        safe_dir = _safe_path(dest_dir, MEDIA_DIR())
        if safe_dir is None:
            raise ValueError("Destination path is invalid")
        safe_dir.mkdir(parents=True, exist_ok=True)

        dest    = safe_dir / sess.safe_name
        tmp_out = dest.with_suffix(dest.suffix + ".tmp")

        try:
            with tmp_out.open("wb") as fout:
                for idx in range(sess.total_chunks):
                    fout.write(sess.chunk_path(idx).read_bytes())
            tmp_out.rename(dest)
        except Exception:
            tmp_out.unlink(missing_ok=True)
            raise
        finally:
            self._remove_session(session_id, sess)

        log.info(
            "Upload finalised: %s  size=%d B  chunks=%d",
            dest, dest.stat().st_size, sess.total_chunks,
        )
        return dest

    def abort(self, session_id: str) -> None:
        """Cancel an in-progress upload and clean up its temp dir."""
        with self._lock:
            sess = self._sessions.pop(session_id, None)
        if sess:
            shutil.rmtree(sess.tmp_dir, ignore_errors=True)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _require(self, session_id: str) -> UploadSession:
        sess = self.get(session_id)
        if sess is None:
            raise KeyError(f"Upload session not found: {session_id}")
        if sess.is_expired:
            self.abort(session_id)
            raise TimeoutError(f"Upload session expired: {session_id}")
        return sess

    def _remove_session(self, session_id: str, sess: UploadSession) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
        shutil.rmtree(sess.tmp_dir, ignore_errors=True)

    def _cleanup_loop(self) -> None:
        """Background thread — removes expired sessions every CLEANUP_PERIOD seconds."""
        while True:
            time.sleep(CLEANUP_PERIOD)
            try:
                with self._lock:
                    expired = [
                        (sid, s)
                        for sid, s in self._sessions.items()
                        if s.is_expired
                    ]
                for sid, sess in expired:
                    with self._lock:
                        self._sessions.pop(sid, None)
                    shutil.rmtree(sess.tmp_dir, ignore_errors=True)
                    log.info("Expired upload session cleaned up: %s  file=%s", sid, sess.safe_name)
            except Exception as exc:
                log.warning("Upload cleanup error: %s", exc)


# =============================================================================
# Module-level singleton (imported by handler mixins)
# =============================================================================
_UPLOAD_MANAGER = UploadSessionManager()


# =============================================================================
# Handler helpers
# (Called from WebHandler methods; all return (response_dict, status_code))
# =============================================================================

def handle_upload_init(data: dict) -> tuple[dict, int]:
    """
    POST /api/upload/init
    Body: {filename, size, total_chunks, subdir?}
    """
    try:
        filename     = str(data.get("filename", "")).strip()
        total_size   = int(data.get("size",     0))
        total_chunks = int(data.get("total_chunks", 1))
        subdir       = str(data.get("subdir",   "")).strip().lstrip("/\\")

        if not filename:
            return {"ok": False, "msg": "filename is required"}, 400

        sess = _UPLOAD_MANAGER.create(
            filename     = filename,
            total_size   = total_size,
            total_chunks = total_chunks,
            subdir       = subdir,
        )
        return {
            "ok":         True,
            "session_id": sess.session_id,
            "chunk_size": CHUNK_SIZE,
        }, 200

    except ValueError as exc:
        return {"ok": False, "msg": str(exc)}, 400
    except Exception as exc:
        log.error("upload/init error: %s", exc)
        return {"ok": False, "msg": f"Init error: {exc}"}, 500


def handle_upload_chunk(raw_body: bytes, content_type: str) -> tuple[dict, int]:
    """
    POST /api/upload/chunk
    Body: multipart/form-data  {session_id, chunk_index, chunk:<blob>}
    """
    try:
        # ── Extract multipart boundary ────────────────────────────────────────
        boundary: Optional[bytes] = None
        for part in content_type.split(";"):
            p = part.strip()
            if p.lower().startswith("boundary="):
                boundary = p[9:].strip('"').encode("latin-1")
                break
        if not boundary:
            return {"ok": False, "msg": "Missing multipart boundary"}, 400

        # ── Parse parts ───────────────────────────────────────────────────────
        session_id:  Optional[str]   = None
        chunk_index: Optional[int]   = None
        chunk_data:  Optional[bytes] = None

        sep = b"--" + boundary
        for seg in raw_body.split(sep):
            seg = seg.lstrip(b"\r\n")
            if not seg or seg.startswith(b"--"):
                continue
            if b"\r\n\r\n" not in seg:
                continue
            hdr_raw, body = seg.split(b"\r\n\r\n", 1)
            if body.endswith(b"\r\n"):
                body = body[:-2]
            hdr_str = hdr_raw.decode("utf-8", errors="replace")
            cd_line = next(
                (ln for ln in hdr_str.splitlines()
                 if ln.lower().startswith("content-disposition:")),
                "",
            )
            field_name = fname = ""
            for tok in cd_line.split(";"):
                tok = tok.strip()
                if tok.startswith("name="):
                    field_name = tok[5:].strip('"')
                elif tok.startswith("filename="):
                    fname = tok[9:].strip('"')

            if field_name == "session_id":
                session_id = body.decode("utf-8", errors="replace").strip()
            elif field_name == "chunk_index":
                try:
                    chunk_index = int(body.decode("utf-8", errors="replace").strip())
                except ValueError:
                    return {"ok": False, "msg": "chunk_index must be an integer"}, 400
            elif field_name == "chunk" and fname:
                chunk_data = body

        if not session_id:
            return {"ok": False, "msg": "Missing session_id field"}, 400
        if chunk_index is None:
            return {"ok": False, "msg": "Missing chunk_index field"}, 400
        if chunk_data is None:
            return {"ok": False, "msg": "Missing chunk data field"}, 400

        # ── Save chunk ────────────────────────────────────────────────────────
        sess = _UPLOAD_MANAGER.save_chunk(session_id, chunk_index, chunk_data)
        return {
            "ok":       True,
            "received": len(sess.received),
            "total":    sess.total_chunks,
        }, 200

    except (KeyError, TimeoutError) as exc:
        return {"ok": False, "msg": str(exc)}, 404
    except ValueError as exc:
        return {"ok": False, "msg": str(exc)}, 400
    except Exception as exc:
        log.error("upload/chunk error: %s", exc)
        return {"ok": False, "msg": f"Chunk error: {exc}"}, 500


def handle_upload_finalize(data: dict) -> tuple[dict, int]:
    """
    POST /api/upload/finalize
    Body: {session_id}
    """
    from hc.web_handlers_get import _invalidate_lib_cache  # avoid circular import

    session_id = str(data.get("session_id", "")).strip()
    if not session_id:
        return {"ok": False, "msg": "session_id is required"}, 400
    try:
        dest = _UPLOAD_MANAGER.finalize(session_id)
        _invalidate_lib_cache()

        # Notify folder-source streams (same helper used by old _handle_upload)
        try:
            from hc.web import _notify_folder_upload
            _notify_folder_upload(dest.parent)
        except Exception:
            pass

        return {"ok": True, "path": str(dest), "msg": f"Saved: {dest.name}"}, 200

    except (KeyError, TimeoutError) as exc:
        return {"ok": False, "msg": str(exc)}, 404
    except ValueError as exc:
        return {"ok": False, "msg": str(exc)}, 400
    except Exception as exc:
        log.error("upload/finalize error: %s", exc)
        return {"ok": False, "msg": f"Finalize error: {exc}"}, 500


def handle_upload_status(session_id: str) -> tuple[dict, int]:
    """GET /api/upload/status?session_id=X"""
    if not session_id:
        return {"ok": False, "msg": "session_id is required"}, 400
    sess = _UPLOAD_MANAGER.get(session_id)
    if sess is None:
        return {"ok": False, "msg": "Session not found or expired"}, 404
    return {
        "ok":       True,
        "received": len(sess.received),
        "total":    sess.total_chunks,
        "pct":      sess.pct,
    }, 200
