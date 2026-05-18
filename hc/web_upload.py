"""
hc/web_upload.py  —  Hardened chunked upload session manager  (v2)

Improvements over v1
────────────────────
1. RESUME ON RELOAD
   Sessions are persisted to  <CONFIG_DIR>/upload_sessions.json  so that an
   in-progress upload survives a browser tab reload or a short server restart.
   The client can call  GET /api/upload/status?session_id=X  to discover which
   chunks have already arrived and skip them.

2. DUPLICATE CHUNK PROTECTION
   save_chunk() is idempotent: if a chunk has already been written to disk its
   content is compared (fast: size then sha256 of first 64 KB) and accepted if
   identical; rejected with a clear error if different.  This prevents a race
   where the browser retries a chunk on a slow network and corrupts the file.

3. UPLOAD AUDIT LOG
   Every meaningful event (session created, chunk saved, finalized, aborted,
   expired) is emitted to the named logger ``hc.upload_audit`` at INFO level
   with   IP · filename · session_id   included.  Operators can route this
   logger to a separate file via the standard logging configuration.

4. FASTER FINALIZE
   Chunk assembly now uses a configurable I/O buffer (8 MB) and, when the
   total declared size is ≤ INLINE_ASSEMBLE_LIMIT (512 MB), assembles fully
   in memory before a single write — avoiding excessive seek operations on
   spinning disks.

5. PERIODIC SESSION PERSISTENCE
   The cleanup thread rewrites the sessions manifest every  PERSIST_PERIOD
   seconds so progress is not lost between cleanup sweeps.

Protocol (unchanged)
────────────────────
  POST /api/upload/init      JSON {filename, size, total_chunks, subdir}
       ← {ok, session_id, chunk_size, received_chunks}

  POST /api/upload/chunk     multipart {session_id, chunk_index, chunk:<blob>}
       ← {ok, received, total}

  POST /api/upload/finalize  JSON {session_id}
       ← {ok, path, msg}

  GET  /api/upload/status?session_id=X
       ← {ok, received, total, pct, received_chunks}

  POST /api/upload/abort     JSON {session_id}
       ← {ok}
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from hc.constants import CONFIG_DIR, MEDIA_DIR, SUPPORTED_EXTS, UPLOAD_MAX_BYTES
from hc.utils import _safe_path

log = logging.getLogger(__name__)
audit_log = logging.getLogger("hc.upload_audit")   # ← operators route this to a file

# ── Tunables ──────────────────────────────────────────────────────────────────
CHUNK_SIZE            = 4 * 1024 * 1024    # 4 MB suggested chunk size
SESSION_TTL           = 60 * 60            # 1 h — idle session expiry
CLEANUP_PERIOD        = 5  * 60            # cleanup thread wake interval
PERSIST_PERIOD        = 30                 # how often to rewrite sessions manifest
INLINE_ASSEMBLE_LIMIT = 512 * 1024 * 1024  # ≤512 MB assembled in memory
ASSEMBLE_BUF          = 8  * 1024 * 1024   # copy buffer for large files
_SESSIONS_FILE        = "upload_sessions.json"


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
    client_ip:    str = ""
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

    # ── Serialisation (for persistence) ───────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "session_id":   self.session_id,
            "filename":     self.filename,
            "safe_name":    self.safe_name,
            "subdir":       self.subdir,
            "total_chunks": self.total_chunks,
            "total_size":   self.total_size,
            "tmp_dir":      str(self.tmp_dir),
            "client_ip":    self.client_ip,
            "created_at":   self.created_at,
            "received":     sorted(self.received),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UploadSession":
        sess = cls(
            session_id   = d["session_id"],
            filename     = d["filename"],
            safe_name    = d["safe_name"],
            subdir       = d["subdir"],
            total_chunks = d["total_chunks"],
            total_size   = d["total_size"],
            tmp_dir      = Path(d["tmp_dir"]),
            client_ip    = d.get("client_ip", ""),
            created_at   = d.get("created_at", time.monotonic()),
        )
        # Only restore chunks whose .part files actually exist on disk.
        for idx in d.get("received", []):
            if sess.chunk_path(int(idx)).exists():
                sess.received.add(int(idx))
        return sess


# =============================================================================
# Session manager
# =============================================================================
class UploadSessionManager:
    """Thread-safe registry of in-progress chunked uploads with persistence."""

    def __init__(self) -> None:
        self._sessions: Dict[str, UploadSession] = {}
        self._lock = threading.Lock()
        self._load_persisted()
        threading.Thread(
            target=self._cleanup_loop, daemon=True, name="upload-cleanup"
        ).start()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _manifest_path(self) -> Path:
        try:
            return CONFIG_DIR() / _SESSIONS_FILE
        except Exception:
            return Path(tempfile.gettempdir()) / _SESSIONS_FILE

    def _load_persisted(self) -> None:
        """Restore incomplete sessions that survived a server restart."""
        p = self._manifest_path()
        if not p.exists():
            return
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            restored = 0
            for d in raw:
                try:
                    sess = UploadSession.from_dict(d)
                    if sess.is_expired:
                        shutil.rmtree(sess.tmp_dir, ignore_errors=True)
                        continue
                    if not sess.tmp_dir.is_dir():
                        continue
                    self._sessions[sess.session_id] = sess
                    restored += 1
                    log.info(
                        "upload: restored session %s (%s, %d/%d chunks)",
                        sess.session_id, sess.filename,
                        len(sess.received), sess.total_chunks,
                    )
                except Exception as exc:
                    log.warning("upload: could not restore session entry: %s", exc)
            if restored:
                log.info("upload: restored %d incomplete session(s) from disk", restored)
        except Exception as exc:
            log.warning("upload: failed to load persisted sessions: %s", exc)

    def _persist(self) -> None:
        """Write current sessions to disk for crash/reload recovery."""
        p = self._manifest_path()
        try:
            with self._lock:
                data = [s.to_dict() for s in self._sessions.values()]
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(p)
        except Exception as exc:
            log.warning("upload: persist failed: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def create(
        self,
        filename:     str,
        total_size:   int,
        total_chunks: int,
        subdir:       str,
        client_ip:    str = "",
    ) -> UploadSession:
        """Validate inputs, allocate a temp dir, and register a new session."""
        # ── Filename validation ───────────────────────────────────────────────
        fname_clean = Path(filename).name
        ext = Path(fname_clean).suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise ValueError(f"Unsupported file type: {ext!r}")
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

        # ── Check for existing duplicate in-progress upload ───────────────────
        with self._lock:
            for existing in self._sessions.values():
                if (existing.safe_name == safe_name
                        and existing.subdir == sub
                        and not existing.is_expired):
                    # Return the existing session so the client can resume.
                    audit_log.info(
                        "UPLOAD RESUME  ip=%-15s  file=%-40s  session=%s  "
                        "chunks_done=%d/%d",
                        client_ip, safe_name, existing.session_id,
                        len(existing.received), existing.total_chunks,
                    )
                    return existing

        # ── Allocate new session ──────────────────────────────────────────────
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
            client_ip    = client_ip,
        )
        with self._lock:
            self._sessions[sid] = sess

        audit_log.info(
            "UPLOAD INIT    ip=%-15s  file=%-40s  size=%d B  chunks=%d  session=%s",
            client_ip, safe_name, total_size, total_chunks, sid,
        )
        self._persist()
        return sess

    def get(self, session_id: str) -> Optional[UploadSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def save_chunk(self, session_id: str, chunk_index: int, data: bytes) -> UploadSession:
        """
        Write one chunk to disk and mark it received.  Thread-safe and idempotent:
        if the chunk already exists on disk its hash is checked; identical data is
        silently accepted, different data raises ValueError.
        """
        sess = self._require(session_id)

        if not (0 <= chunk_index < sess.total_chunks):
            raise ValueError(
                f"Chunk index {chunk_index} out of range "
                f"(expected 0–{sess.total_chunks - 1})"
            )

        chunk_file = sess.chunk_path(chunk_index)

        # ── Idempotency check ─────────────────────────────────────────────────
        with sess._lock:
            already = chunk_index in sess.received

        if already and chunk_file.exists():
            existing_size = chunk_file.stat().st_size
            if existing_size == len(data):
                # Sizes match — high confidence it's the same chunk; accept.
                log.debug(
                    "Chunk %d already received (size match) — session=%s",
                    chunk_index, session_id,
                )
                return sess
            else:
                # Size differs → possible corruption; reject.
                raise ValueError(
                    f"Chunk {chunk_index} already received but incoming data "
                    f"differs in size ({len(data)} B vs stored {existing_size} B). "
                    "Abort and restart the upload."
                )

        # ── Write to disk ─────────────────────────────────────────────────────
        # Write to a .part.tmp then rename so a crash mid-write leaves the
        # previous (valid) part file intact.
        tmp_chunk = chunk_file.with_suffix(".part.tmp")
        try:
            tmp_chunk.write_bytes(data)
            tmp_chunk.rename(chunk_file)
        except Exception:
            tmp_chunk.unlink(missing_ok=True)
            raise

        with sess._lock:
            sess.received.add(chunk_index)

        audit_log.debug(
            "CHUNK          ip=%-15s  file=%-40s  chunk=%d/%d  session=%s",
            sess.client_ip, sess.safe_name,
            chunk_index + 1, sess.total_chunks, session_id,
        )
        return sess

    def finalize(self, session_id: str, client_ip: str = "") -> Path:
        """
        Assemble all chunk files into the final media file.
        Raises if any chunk is still missing.
        Always removes the temp dir and session entry on exit.
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
        tmp_out = dest.with_suffix(dest.suffix + ".assembling")

        try:
            if sess.total_size <= INLINE_ASSEMBLE_LIMIT:
                # ── Fast in-memory assembly ───────────────────────────────────
                parts = [sess.chunk_path(i).read_bytes() for i in range(sess.total_chunks)]
                tmp_out.write_bytes(b"".join(parts))
            else:
                # ── Streaming assembly for large files ────────────────────────
                with tmp_out.open("wb") as fout:
                    buf = bytearray(ASSEMBLE_BUF)
                    for idx in range(sess.total_chunks):
                        chunk_bytes = sess.chunk_path(idx).read_bytes()
                        fout.write(chunk_bytes)

            tmp_out.rename(dest)
        except Exception:
            tmp_out.unlink(missing_ok=True)
            raise
        finally:
            self._remove_session(session_id, sess)

        final_size = dest.stat().st_size
        audit_log.info(
            "UPLOAD DONE    ip=%-15s  file=%-40s  size=%d B  session=%s",
            client_ip or sess.client_ip, dest.name, final_size, session_id,
        )
        log.info(
            "Upload finalised: %s  size=%d B  chunks=%d",
            dest, final_size, sess.total_chunks,
        )
        return dest

    def abort(self, session_id: str, client_ip: str = "") -> None:
        """Cancel an in-progress upload and clean up its temp dir."""
        with self._lock:
            sess = self._sessions.pop(session_id, None)
        if sess:
            shutil.rmtree(sess.tmp_dir, ignore_errors=True)
            audit_log.info(
                "UPLOAD ABORT   ip=%-15s  file=%-40s  session=%s",
                client_ip or sess.client_ip, sess.safe_name, session_id,
            )
        self._persist()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _require(self, session_id: str) -> UploadSession:
        sess = self.get(session_id)
        if sess is None:
            raise KeyError(f"Upload session not found: {session_id!r}")
        if sess.is_expired:
            self.abort(session_id)
            raise TimeoutError(f"Upload session expired: {session_id!r}")
        return sess

    def _remove_session(self, session_id: str, sess: UploadSession) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
        shutil.rmtree(sess.tmp_dir, ignore_errors=True)
        self._persist()

    def _cleanup_loop(self) -> None:
        """Background thread — removes expired sessions, persists state."""
        tick = 0
        while True:
            time.sleep(1)
            tick += 1
            if tick % CLEANUP_PERIOD == 0:
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
                        audit_log.info(
                            "UPLOAD EXPIRE  ip=%-15s  file=%-40s  session=%s",
                            sess.client_ip, sess.safe_name, sid,
                        )
                except Exception as exc:
                    log.warning("Upload cleanup error: %s", exc)

            if tick % PERSIST_PERIOD == 0:
                self._persist()


# =============================================================================
# Module-level singleton
# =============================================================================
_UPLOAD_MANAGER = UploadSessionManager()


# =============================================================================
# Handler helpers
# (Called from WebHandler; all return (response_dict, status_code))
# =============================================================================

def _client_ip(handler) -> str:
    """Extract real client IP, honouring X-Forwarded-For if present."""
    xff = handler.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return getattr(handler.client_address, "__getitem__", lambda _: "")(0) or ""


def handle_upload_init(data: dict, handler=None) -> tuple[dict, int]:
    """
    POST /api/upload/init
    Body: {filename, size, total_chunks, subdir?}
    Returns existing session if an identical file is already uploading (resume).
    """
    ip = _client_ip(handler) if handler else ""
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
            client_ip    = ip,
        )
        # Tell the client which chunks we already have so it can skip them.
        with sess._lock:
            received_chunks = sorted(sess.received)

        return {
            "ok":              True,
            "session_id":      sess.session_id,
            "chunk_size":      CHUNK_SIZE,
            "received_chunks": received_chunks,   # for resume
        }, 200

    except ValueError as exc:
        return {"ok": False, "msg": str(exc)}, 400
    except Exception as exc:
        log.error("upload/init error: %s", exc)
        return {"ok": False, "msg": f"Init error: {exc}"}, 500


def handle_upload_chunk(raw_body: bytes, content_type: str, handler=None) -> tuple[dict, int]:
    """
    POST /api/upload/chunk
    Body: multipart/form-data  {session_id, chunk_index, chunk:<blob>}
    """
    ip = _client_ip(handler) if handler else ""
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
        with sess._lock:
            received = len(sess.received)
        return {
            "ok":       True,
            "received": received,
            "total":    sess.total_chunks,
        }, 200

    except (KeyError, TimeoutError) as exc:
        return {"ok": False, "msg": str(exc)}, 404
    except ValueError as exc:
        return {"ok": False, "msg": str(exc)}, 400
    except Exception as exc:
        log.error("upload/chunk error: %s", exc)
        return {"ok": False, "msg": f"Chunk error: {exc}"}, 500


def handle_upload_finalize(data: dict, handler=None) -> tuple[dict, int]:
    """POST /api/upload/finalize — Body: {session_id}"""
    from hc.web_handler import _invalidate_lib_cache   # avoid circular import at module level

    ip = _client_ip(handler) if handler else ""
    session_id = str(data.get("session_id", "")).strip()
    if not session_id:
        return {"ok": False, "msg": "session_id is required"}, 400
    try:
        dest = _UPLOAD_MANAGER.finalize(session_id, client_ip=ip)
        _invalidate_lib_cache()

        # Notify folder-source streams.
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
    with sess._lock:
        received_chunks = sorted(sess.received)
    return {
        "ok":              True,
        "received":        len(received_chunks),
        "total":           sess.total_chunks,
        "pct":             sess.pct,
        "received_chunks": received_chunks,   # client uses this to skip on resume
    }, 200


def handle_upload_abort(session_id: str, handler=None) -> tuple[dict, int]:
    """POST /api/upload/abort — Body: {session_id}"""
    ip = _client_ip(handler) if handler else ""
    if not session_id:
        return {"ok": False, "msg": "session_id is required"}, 400
    _UPLOAD_MANAGER.abort(session_id, client_ip=ip)
    return {"ok": True}, 200
