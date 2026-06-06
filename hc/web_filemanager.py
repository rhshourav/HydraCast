"""
hc/web_filemanager.py  —  File Manager mixin for WebHandler.

Provides:
  GET  /api/files?path=<encoded>   list a directory inside any media root
  POST file_rename                 rename a file or folder
  POST file_delete                 delete a file (or empty folder)
  POST file_delete_dir             delete a folder recursively
  POST file_move                   move a file/folder to a new location
  POST file_copy                   copy a file to a new location

Multi-root path encoding
────────────────────────
Paths are encoded as  @N/relative/path  where N is the zero-based index
returned by get_media_roots().

  path=""          → top-level listing of all roots  (multi_root: true)
  path="@0"        → browse the default media root (MEDIA_DIR)
  path="@0/sub"    → browse a sub-folder inside root 0
  path="@1"        → browse the first extra root
  path="@1/a/b"    → browse  <root1>/a/b

Bare paths without a leading "@" are treated as root-0 paths for
backwards compatibility with any code that has not been updated yet.

After any mutation the mixin:
  • Invalidates the library cache.
  • Updates every StreamConfig.playlist that references the affected path.
  • Re-saves streams.json so the change persists across restarts.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hc.constants import SUPPORTED_EXTS, get_media_roots

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Multi-root safe path helper
# ---------------------------------------------------------------------------

def _safe_in_root(target: Path, root: Path) -> Optional[Path]:
    """
    Return the resolved absolute path of *target* if and only if it sits
    inside *root* (after resolving symlinks on both sides).
    Returns None if the path escapes the root (path traversal guard).

    This is a root-agnostic replacement for _safe_path(target, MEDIA_DIR())
    so that extra media roots outside MEDIA_DIR are handled correctly.
    """
    try:
        resolved_target = target.resolve()
        resolved_root   = root.resolve()
        resolved_target.relative_to(resolved_root)   # raises ValueError if outside
        return resolved_target
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# Multi-root path helpers
# ---------------------------------------------------------------------------

def _decode_root(raw_path: str) -> Optional[Tuple[int, Path, str]]:
    """
    Decode a multi-root encoded path.

    Formats accepted:
      "@N"         → (N, roots[N], "")
      "@N/rel"     → (N, roots[N], "rel")
      "bare/path"  → (0, roots[0], "bare/path")   # legacy compatibility

    Returns (root_idx, root_dir, rel_within_root) or None if invalid.
    """
    roots = get_media_roots()
    if not roots:
        return None

    if raw_path.startswith("@"):
        slash = raw_path.find("/", 1)
        if slash == -1:
            idx_str, rel = raw_path[1:], ""
        else:
            idx_str, rel = raw_path[1:slash], raw_path[slash + 1:]
        try:
            idx = int(idx_str)
        except ValueError:
            return None
        if idx < 0 or idx >= len(roots):
            return None
        return (idx, roots[idx], rel)
    else:
        # Legacy bare path → root 0
        return (0, roots[0], raw_path)


def _encode_path(root_idx: int, rel_within: str) -> str:
    """Return the canonical encoded path string for a root + relative combo."""
    if rel_within:
        return f"@{root_idx}/{rel_within}"
    return f"@{root_idx}"


def _resolve_fm_path(raw_path: str) -> Optional[Tuple[Path, Path]]:
    """
    Decode *raw_path* and validate it as a safe path inside its root.

    Returns (root_dir, absolute_safe_path) or None if invalid / access denied.
    Uses the resolved (canonical) root so _safe_path works correctly for
    extra roots that may be symlinked or mounted outside MEDIA_DIR.
    """
    decoded = _decode_root(raw_path)
    if decoded is None:
        return None
    _, root_dir, rel_within = decoded
    # Resolve the root so that symlinks and extra roots outside MEDIA_DIR
    # are handled correctly by _safe_path's relative_to check.
    try:
        resolved_root = root_dir.resolve()
    except Exception:
        resolved_root = root_dir
    if rel_within:
        target = resolved_root / rel_within
        safe = _safe_in_root(target, resolved_root)
        if safe is None:
            return None
        return (resolved_root, safe)
    return (resolved_root, resolved_root)


# ---------------------------------------------------------------------------
# Playlist sync helpers
# ---------------------------------------------------------------------------

def _update_stream_playlists(
    old_path: Path,
    new_path: Optional[Path],
    mgr: Any,
) -> int:
    """
    Walk every stream config and update (or remove) PlaylistItem entries
    whose file_path resolves to *old_path*.
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
            else:
                new_playlist.append(item)

        if changed:
            cfg.playlist = new_playlist

    if count > 0:
        try:
            from hc.json_manager import JSONManager
            JSONManager.save([st.config for st in mgr.states])
            log.info(
                "filemanager: updated %d playlist reference(s): %s -> %s",
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
    """Like _update_stream_playlists but for every file inside a directory."""
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
            except ValueError:
                new_playlist.append(item)

        if changed:
            cfg.playlist = new_playlist

    if count > 0:
        try:
            from hc.json_manager import JSONManager
            JSONManager.save([st.config for st in mgr.states])
            log.info(
                "filemanager: updated %d playlist entries for dir: %s -> %s",
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
    """

    # ── GET /api/files ────────────────────────────────────────────────────────

    def _get_files(self, qs: Dict[str, Any]) -> None:
        """
        List contents of a directory inside any configured media root.

        path=""       -> virtual top-level: list all roots as folder entries
        path="@N"     -> browse root N
        path="@N/rel" -> browse sub-folder inside root N
        """
        from hc.utils import _fmt_size

        roots = get_media_roots()
        if not roots:
            self._json({"error": "No media roots configured"}, 500)
            return

        rel_raw = qs.get("path", [""])[0].strip().lstrip("/\\")

        # ── Top-level: list all roots ─────────────────────────────────────────
        if not rel_raw:
            if len(roots) == 1:
                # Single root — enter it directly; no visible UX change.
                rel_raw = "@0"
            else:
                dirs: List[Dict] = []
                for i, root in enumerate(roots):
                    label = root.name or str(root)
                    try:
                        item_count = sum(1 for _ in root.iterdir()) if root.is_dir() else 0
                    except OSError:
                        item_count = 0
                    dirs.append({
                        "name":    label,
                        "path":    f"@{i}",
                        "items":   item_count,
                        "is_root": True,
                    })
                self._json({
                    "path":        "",
                    "dirs":        dirs,
                    "files":       [],
                    "breadcrumb":  [{"name": "Roots", "path": ""}],
                    "multi_root":  True,
                    "roots_total": len(roots),
                })
                return

        # ── Decode root from path ─────────────────────────────────────────────
        decoded = _decode_root(rel_raw)
        if decoded is None:
            self._json({"error": "Invalid path"}, 400)
            return

        root_idx, root_dir, rel_within = decoded

        # Use the resolved root so _safe_path works for symlinked/extra roots.
        try:
            root_dir = root_dir.resolve()
        except Exception:
            pass

        if not root_dir.exists():
            self._json({"error": f"Root directory does not exist: {root_dir}"}, 500)
            return

        if rel_within:
            target = root_dir / rel_within
            safe   = _safe_in_root(target, root_dir)
            if safe is None or not safe.is_dir():
                self._json({"error": "Directory not found or access denied"}, 404)
                return
        else:
            safe = root_dir

        root_label = root_dir.name or str(root_dir)

        try:
            import os as _os
            dirs_out: List[Dict] = []
            files_out: List[Dict] = []

            try:
                raw_entries = list(_os.scandir(safe))
            except OSError as exc:
                self._json({"error": f"Cannot read directory: {exc}"}, 500)
                return

            # Dirs first, then files — each alphabetically (case-insensitive)
            raw_entries.sort(key=lambda e: (e.is_file(follow_symlinks=False), e.name.lower()))

            for entry in raw_entries:
                entry_path = Path(entry.path)
                try:
                    entry_rel = str(entry_path.relative_to(root_dir))
                except ValueError:
                    continue
                encoded = _encode_path(root_idx, entry_rel)

                if entry.is_dir(follow_symlinks=True):
                    # Count items inside the subdir with a single scandir call.
                    # This is O(1) per entry on most filesystems (same cost as
                    # iterdir) and avoids sending "-1" to the UI.
                    try:
                        sub_count = sum(1 for _ in _os.scandir(entry.path))
                    except OSError:
                        sub_count = 0
                    dirs_out.append({
                        "name":        entry.name,
                        "path":        encoded,
                        "items":       sub_count,
                        "has_media":   None,
                        "has_subdirs": None,
                    })
                elif entry.is_file(follow_symlinks=True):
                    ext = entry_path.suffix.lower()
                    try:
                        # DirEntry.stat() reuses the inode data from scandir (no extra syscall)
                        size_b = entry.stat(follow_symlinks=True).st_size
                    except OSError:
                        size_b = 0
                    files_out.append({
                        "name":      entry.name,
                        "path":      encoded,
                        "size":      _fmt_size(size_b),
                        "size_b":    size_b,
                        "supported": ext in SUPPORTED_EXTS,
                        "ext":       ext,
                    })

            # Breadcrumb: RootName [> sub > …]
            # When only one root exists we skip the generic top-level crumb and
            # go straight to the root folder name so the user sees the real name.
            crumbs = [{"name": root_label, "path": f"@{root_idx}"}]
            if len(roots) > 1:
                # Multi-root: prepend a top-level "Roots" home crumb
                crumbs.insert(0, {"name": "Roots", "path": ""})
            if rel_within:
                parts = Path(rel_within).parts
                for i, part in enumerate(parts):
                    crumb_rel = str(Path(*parts[: i + 1]))
                    crumbs.append({
                        "name": part,
                        "path": _encode_path(root_idx, crumb_rel),
                    })

            self._json({
                "path":        _encode_path(root_idx, rel_within),
                "dirs":        dirs_out,
                "files":       files_out,
                "breadcrumb":  crumbs,
                "root_idx":    root_idx,
                "root_label":  root_label,
                "roots_total": len(roots),
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

        resolved = _resolve_fm_path(raw_path)
        if resolved is None:
            self._json({"ok": False, "msg": "File/folder not found or access denied"})
            return
        root_dir, src = resolved
        if not src.exists():
            self._json({"ok": False, "msg": "File/folder not found"})
            return

        dst = src.parent / new_name
        if dst.exists():
            self._json({"ok": False, "msg": f"'{new_name}' already exists in this folder"})
            return

        is_dir = src.is_dir()
        try:
            src.rename(dst)
        except Exception as exc:
            self._json({"ok": False, "msg": str(exc)})
            return

        _invalidate_lib_cache()
        mgr = _WEB_MANAGER
        n = _update_folder_in_playlists(src, dst, mgr) if is_dir \
            else _update_stream_playlists(src, dst, mgr)

        decoded = _decode_root(raw_path)
        try:
            new_rel = str(dst.relative_to(root_dir))
        except ValueError:
            new_rel = dst.name
        new_path_encoded = _encode_path(decoded[0], new_rel) if decoded else new_rel

        self._json({
            "ok":       True,
            "msg":      f"Renamed to '{new_name}'" + (f" · {n} playlist item(s) updated" if n else ""),
            "new_path": new_path_encoded,
        })

    # ── delete file ──────────────────────────────────────────────────────────

    def _fm_delete(self, data: Dict[str, Any]) -> None:
        """Delete a single file."""
        from hc.web import _WEB_MANAGER, _invalidate_lib_cache  # type: ignore

        raw_path = str(data.get("path", "")).strip()
        if not raw_path:
            self._json({"ok": False, "msg": "path is required"})
            return

        resolved = _resolve_fm_path(raw_path)
        if resolved is None or not resolved[1].is_file():
            self._json({"ok": False, "msg": "File not found or access denied"})
            return
        _, target = resolved

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

        resolved = _resolve_fm_path(raw_path)
        if resolved is None or not resolved[1].is_dir():
            self._json({"ok": False, "msg": "Directory not found or access denied"})
            return
        root_dir, target = resolved

        if target.resolve() == root_dir.resolve():
            self._json({"ok": False, "msg": "Cannot delete a media root directory itself"})
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
        """
        Move a file or folder to a different directory.
        Both path and dest_dir accept @N/rel encoding, enabling cross-root moves.
        """
        from hc.web import _WEB_MANAGER, _invalidate_lib_cache  # type: ignore

        raw_src  = str(data.get("path", "")).strip()
        raw_dest = str(data.get("dest_dir", "")).strip()

        if not raw_src:
            self._json({"ok": False, "msg": "path is required"})
            return

        src_resolved = _resolve_fm_path(raw_src)
        if src_resolved is None or not src_resolved[1].exists():
            self._json({"ok": False, "msg": "Source not found or access denied"})
            return
        src_root, src = src_resolved

        if raw_dest:
            dest_resolved = _resolve_fm_path(raw_dest)
            if dest_resolved is None or not dest_resolved[1].is_dir():
                self._json({"ok": False, "msg": "Destination directory not found"})
                return
            dest_root, dest_dir = dest_resolved
        else:
            dest_root = src_root
            dest_dir  = src_root

        dst = dest_dir / src.name
        if dst.resolve() == src.resolve():
            self._json({"ok": False, "msg": "Source and destination are the same"})
            return
        if dst.exists():
            self._json({"ok": False, "msg": f"'{src.name}' already exists in destination"})
            return

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

        dest_label = dest_dir.name or dest_root.name
        self._json({
            "ok":  True,
            "msg": f"Moved '{src.name}' -> '{dest_label}'" +
                   (f" · {n} playlist item(s) updated" if n else ""),
        })

    # ── copy ─────────────────────────────────────────────────────────────────

    def _fm_copy(self, data: Dict[str, Any]) -> None:
        """
        Copy a file to a destination (cross-root supported via @N/rel encoding).
        """
        from hc.web import _invalidate_lib_cache  # type: ignore

        raw_src  = str(data.get("path", "")).strip()
        raw_dest = str(data.get("dest_dir", "")).strip()
        new_name = str(data.get("new_name", "")).strip()

        if not raw_src:
            self._json({"ok": False, "msg": "path is required"})
            return

        src_resolved = _resolve_fm_path(raw_src)
        if src_resolved is None or not src_resolved[1].is_file():
            self._json({"ok": False, "msg": "Source file not found or access denied"})
            return
        src_root, src = src_resolved

        if raw_dest:
            dest_resolved = _resolve_fm_path(raw_dest)
            if dest_resolved is None or not dest_resolved[1].is_dir():
                self._json({"ok": False, "msg": "Destination directory not found"})
                return
            _, dest_dir = dest_resolved
        else:
            dest_dir = src_root

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
            "ok":  True,
            "msg": f"Copied '{src.name}' -> '{dest_dir.name or 'Media'}/{fname}'",
        })
