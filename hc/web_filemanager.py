"""
hc/web_filemanager.py  —  File Manager mixin for WebHandler.

Provides:
  GET  /api/files?path=<rel>       list a directory inside MEDIA_DIR
  POST file_rename                 rename a file or folder
  POST file_delete                 delete a file (or empty folder)
  POST file_delete_dir             delete a folder recursively
  POST file_move                   move a file/folder to a new location
  POST file_copy                   copy a file to a new location

After any mutation the mixin:
  • Invalidates the library cache.
  • Updates every StreamConfig.playlist that references the affected path.
  • Re-saves streams.json so the change persists across restarts.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hc.constants import MEDIA_DIR, SUPPORTED_EXTS
from hc.utils import _safe_path

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Playlist sync helpers (module-level so they can be unit-tested independently)
# ---------------------------------------------------------------------------

def _update_stream_playlists(
    old_path: Path,
    new_path: Optional[Path],
    mgr: Any,
) -> int:
    """
    Walk every stream config and update (or remove) PlaylistItem entries
    whose file_path resolves to *old_path*.

    Parameters
    ----------
    old_path : Path   absolute path that was renamed / moved / deleted
    new_path : Path | None
        New absolute path after rename/move.  Pass None to delete the entry.
    mgr      : StreamManager | None

    Returns
    -------
    int  number of playlist items changed
    """
    if mgr is None:
        return 0

    count = 0
    old_resolved = old_path.resolve()

    for st in mgr.states:
        cfg = st.config
        new_playlist = []
        changed = False

        for item in cfg.playlist:
            try:
                item_resolved = item.file_path.resolve()
            except Exception:
                item_resolved = item.file_path

            if item_resolved == old_resolved:
                changed = True
                count += 1
                if new_path is not None:
                    item.file_path = new_path
                    new_playlist.append(item)
                # else: deletion — drop the item
            else:
                new_playlist.append(item)

        if changed:
            cfg.playlist = new_playlist

    if count > 0:
        try:
            from hc.json_manager import JSONManager
            JSONManager.save([st.config for st in mgr.states])
            log.info(
                "filemanager: updated %d playlist reference(s): %s → %s",
                count, old_path.name, new_path.name if new_path else "DELETED",
            )
        except Exception as exc:
            log.warning("filemanager: failed to persist playlist update: %s", exc)

    return count


def _update_folder_in_playlists(
    old_dir: Path,
    new_dir: Optional[Path],
    mgr: Any,
) -> int:
    """
    Like _update_stream_playlists but for every file inside a *directory*.
    Used when a folder is renamed / moved.
    """
    if mgr is None:
        return 0

    count = 0
    old_resolved = old_dir.resolve()

    for st in mgr.states:
        cfg = st.config
        new_playlist = []
        changed = False

        for item in cfg.playlist:
            try:
                item_resolved = item.file_path.resolve()
            except Exception:
                item_resolved = item.file_path

            try:
                rel = item_resolved.relative_to(old_resolved)
                changed = True
                count += 1
                if new_dir is not None:
                    item.file_path = new_dir / rel
                    new_playlist.append(item)
                # else deletion — drop
            except ValueError:
                new_playlist.append(item)

        if changed:
            cfg.playlist = new_playlist

    if count > 0:
        try:
            from hc.json_manager import JSONManager
            JSONManager.save([st.config for st in mgr.states])
            log.info(
                "filemanager: updated %d playlist entries for dir: %s → %s",
                count, old_dir.name, new_dir.name if new_dir else "DELETED",
            )
        except Exception as exc:
            log.warning("filemanager: failed to persist dir playlist update: %s", exc)

    return count


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class _FileManagerMixin:
    """
    Mixed into WebHandler.  Provides _get_files() and _handle_file_op().
    Expects self._json() and self._WEB_MANAGER to exist on the host class.
    """

    # ── GET /api/files ────────────────────────────────────────────────────────

    def _get_files(self, qs: Dict[str, Any]) -> None:
        """
        List contents of MEDIA_DIR/<rel_path>.
        Returns {path, dirs: [...], files: [...], breadcrumb: [...]}
        """
        from hc.utils import _fmt_size

        # Guard: MEDIA_DIR() raises RuntimeError if set_base_dir() was never called.
        try:
            media = MEDIA_DIR()
        except RuntimeError as exc:
            log.error("_get_files: %s", exc)
            self._json({"error": str(exc)}, 500)
            return

        if not media.exists():
            log.error("_get_files: media directory does not exist: %s", media)
            self._json({"error": f"Media directory does not exist: {media}"}, 500)
            return

        log.debug("_get_files: serving from '%s'", media)

        rel_raw = qs.get("path", [""])[0].strip().lstrip("/\\")

        if rel_raw:
            target = media / rel_raw
            safe   = _safe_path(target, media)
            if safe is None or not safe.is_dir():
                self._json({"error": "Directory not found or access denied"}, 404)
                return
        else:
            safe = media

        try:
            dirs: List[Dict] = []
            files: List[Dict] = []
            for entry in sorted(safe.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                rel = str(entry.relative_to(media))
                if entry.is_dir():
                    try:
                        item_count = sum(1 for _ in entry.iterdir())
                    except OSError:
                        item_count = 0
                    dirs.append({
                        "name":  entry.name,
                        "path":  rel,
                        "items": item_count,
                    })
                elif entry.is_file():
                    ext = entry.suffix.lower()
                    try:
                        size_b = entry.stat().st_size
                    except OSError:
                        size_b = 0
                    files.append({
                        "name":      entry.name,
                        "path":      rel,
                        "size":      _fmt_size(size_b),
                        "size_b":    size_b,
                        "supported": ext in SUPPORTED_EXTS,
                        "ext":       ext,
                    })

            # Build breadcrumb
            crumbs = [{"name": "Media", "path": ""}]
            parts = Path(rel_raw).parts if rel_raw else []
            for i, part in enumerate(parts):
                crumbs.append({
                    "name": part,
                    "path": str(Path(*parts[: i + 1])),
                })

            self._json({
                "path":       str(safe.relative_to(media)) if safe != media else "",
                "dirs":       dirs,
                "files":      files,
                "breadcrumb": crumbs,
            })
        except Exception as exc:
            log.error("_get_files error: %s", exc)
            self._json({"error": str(exc)}, 500)

    # ── POST file operations ──────────────────────────────────────────────────

    def _handle_file_op(self, action: str, data: Dict[str, Any]) -> None:
        """Route file-manager POST actions."""
        if action == "file_rename":
            self._fm_rename(data)
        elif action == "file_delete":
            self._fm_delete(data)
        elif action == "file_delete_dir":
            self._fm_delete_dir(data)
        elif action == "file_move":
            self._fm_move(data)
        elif action == "file_copy":
            self._fm_copy(data)
        else:
            self._json({"ok": False, "msg": f"Unknown file action: {action}"}, 404)

    # ── rename ───────────────────────────────────────────────────────────────

    def _fm_rename(self, data: Dict[str, Any]) -> None:
        """Rename a file or folder in-place."""
        import re as _re
        from hc.web import _WEB_MANAGER, _invalidate_lib_cache  # type: ignore

        raw_path = str(data.get("path", "")).strip()
        new_name = str(data.get("new_name", "")).strip()

        if not raw_path or not new_name:
            self._json({"ok": False, "msg": "path and new_name are required"})
            return
        if _re.search(r'[/\\<>"|?*\x00]', new_name) or ".." in new_name:
            self._json({"ok": False, "msg": "Invalid name — contains forbidden characters"})
            return

        media = MEDIA_DIR()
        src   = _safe_path(media / raw_path, media)
        if src is None or not src.exists():
            self._json({"ok": False, "msg": "File/folder not found or access denied"})
            return

        dst = src.parent / new_name
        if dst.exists():
            self._json({"ok": False, "msg": f"'{new_name}' already exists in this folder"})
            return

        # FIX: capture is_dir BEFORE rename so the check survives the fs operation.
        is_dir = src.is_dir()

        try:
            src.rename(dst)
        except Exception as exc:
            self._json({"ok": False, "msg": str(exc)})
            return

        _invalidate_lib_cache()
        mgr = _WEB_MANAGER

        if is_dir:
            n = _update_folder_in_playlists(src, dst, mgr)
        else:
            n = _update_stream_playlists(src, dst, mgr)

        self._json({
            "ok":  True,
            "msg": f"Renamed to '{new_name}'" + (f" · {n} playlist item(s) updated" if n else ""),
            "new_path": str(dst.relative_to(media)),
        })

    # ── delete file ──────────────────────────────────────────────────────────

    def _fm_delete(self, data: Dict[str, Any]) -> None:
        """Delete a single file."""
        from hc.web import _WEB_MANAGER, _invalidate_lib_cache  # type: ignore

        raw_path = str(data.get("path", "")).strip()
        if not raw_path:
            self._json({"ok": False, "msg": "path is required"})
            return

        media = MEDIA_DIR()
        target = _safe_path(media / raw_path, media)
        if target is None or not target.is_file():
            self._json({"ok": False, "msg": "File not found or access denied"})
            return

        try:
            target.unlink()
        except Exception as exc:
            self._json({"ok": False, "msg": str(exc)})
            return

        _invalidate_lib_cache()
        n = _update_stream_playlists(target, None, _WEB_MANAGER)
        self._json({
            "ok":  True,
            "msg": f"Deleted '{target.name}'" + (f" · {n} playlist item(s) removed" if n else ""),
        })

    # ── delete directory ─────────────────────────────────────────────────────

    def _fm_delete_dir(self, data: Dict[str, Any]) -> None:
        """Delete a directory and all its contents (recursive)."""
        from hc.web import _WEB_MANAGER, _invalidate_lib_cache  # type: ignore

        raw_path = str(data.get("path", "")).strip()
        if not raw_path:
            self._json({"ok": False, "msg": "path is required"})
            return

        media = MEDIA_DIR()
        target = _safe_path(media / raw_path, media)
        if target is None or not target.is_dir():
            self._json({"ok": False, "msg": "Directory not found or access denied"})
            return

        try:
            shutil.rmtree(target)
        except Exception as exc:
            self._json({"ok": False, "msg": str(exc)})
            return

        _invalidate_lib_cache()
        n = _update_folder_in_playlists(target, None, _WEB_MANAGER)
        self._json({
            "ok":  True,
            "msg": f"Deleted folder '{target.name}'" + (f" · {n} playlist item(s) removed" if n else ""),
        })

    # ── move ─────────────────────────────────────────────────────────────────

    def _fm_move(self, data: Dict[str, Any]) -> None:
        """Move a file or folder to a different directory inside MEDIA_DIR."""
        from hc.web import _WEB_MANAGER, _invalidate_lib_cache  # type: ignore

        raw_src  = str(data.get("path", "")).strip()
        raw_dest = str(data.get("dest_dir", "")).strip()  # relative dir path

        if not raw_src:
            self._json({"ok": False, "msg": "path is required"})
            return

        media = MEDIA_DIR()
        src   = _safe_path(media / raw_src, media)
        if src is None or not src.exists():
            self._json({"ok": False, "msg": "Source not found or access denied"})
            return

        if raw_dest:
            dest_dir = _safe_path(media / raw_dest, media)
            if dest_dir is None or not dest_dir.is_dir():
                self._json({"ok": False, "msg": "Destination directory not found"})
                return
        else:
            dest_dir = media  # move to root

        dst = dest_dir / src.name
        if dst.resolve() == src.resolve():
            self._json({"ok": False, "msg": "Source and destination are the same"})
            return
        if dst.exists():
            self._json({"ok": False, "msg": f"'{src.name}' already exists in destination"})
            return

        # FIX: capture is_dir BEFORE the move operation.
        is_dir = src.is_dir()
        try:
            shutil.move(str(src), str(dst))
        except Exception as exc:
            self._json({"ok": False, "msg": str(exc)})
            return

        _invalidate_lib_cache()
        mgr = _WEB_MANAGER
        n = _update_folder_in_playlists(src, dst, mgr) if is_dir \
            else _update_stream_playlists(src, dst, mgr)

        self._json({
            "ok":      True,
            "msg":     f"Moved '{src.name}' → '{dest_dir.name or 'Media'}'" +
                       (f" · {n} playlist item(s) updated" if n else ""),
            "new_path": str(dst.relative_to(media)),
        })

    # ── copy ─────────────────────────────────────────────────────────────────

    def _fm_copy(self, data: Dict[str, Any]) -> None:
        """Copy a file (not a directory) to a destination inside MEDIA_DIR."""
        from hc.web import _invalidate_lib_cache  # type: ignore

        raw_src  = str(data.get("path", "")).strip()
        raw_dest = str(data.get("dest_dir", "")).strip()
        new_name = str(data.get("new_name", "")).strip()

        if not raw_src:
            self._json({"ok": False, "msg": "path is required"})
            return

        media = MEDIA_DIR()
        src   = _safe_path(media / raw_src, media)
        if src is None or not src.is_file():
            self._json({"ok": False, "msg": "Source file not found or access denied"})
            return

        if raw_dest:
            dest_dir = _safe_path(media / raw_dest, media)
            if dest_dir is None or not dest_dir.is_dir():
                self._json({"ok": False, "msg": "Destination directory not found"})
                return
        else:
            dest_dir = media

        fname = new_name if new_name else src.name
        dst   = dest_dir / fname

        if dst.resolve() == src.resolve():
            self._json({"ok": False, "msg": "Source and destination are the same"})
            return
        if dst.exists():
            self._json({"ok": False, "msg": f"'{fname}' already exists in destination"})
            return

        try:
            shutil.copy2(str(src), str(dst))
        except Exception as exc:
            self._json({"ok": False, "msg": str(exc)})
            return

        _invalidate_lib_cache()
        self._json({
            "ok":      True,
            "msg":     f"Copied '{src.name}' → '{dest_dir.name or 'Media'}/{fname}'",
            "new_path": str(dst.relative_to(media)),
        })
