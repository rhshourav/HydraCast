#!/usr/bin/env python3
"""
apply_patches.py  —  Apply HydraCast v5.1.0 patches to the hc/ package.

Run from the HydraCast root directory:
    python apply_patches.py

What this does:
  1. Replaces hc/worker.py   → fixes stop/restart race, auto-restart guard
  2. Replaces hc/tui.py      → interactive overlays, fixed key bindings
  3. Replaces hydracast.py   → uses new run_tui_loop from tui.py
  4. Patches  hc/web.py      → after upload, trigger folder rescan on
                               matching streams so new files appear instantly
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
HC   = HERE / "hc"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _replace(src: Path, dst: Path) -> None:
    if not src.exists():
        print(f"  SKIP (source not found): {src.name}")
        return
    shutil.copy2(src, dst)
    print(f"  ✔  {dst.relative_to(HERE)}")


def _patch_web_upload(web_path: Path) -> None:
    """
    Patch _handle_upload in web.py to trigger an in-memory folder rescan
    on all streams whose folder_source is a subdirectory of the upload dir.
    """
    text = web_path.read_text(encoding="utf-8")

    OLD = (
        "            _invalidate_lib_cache()\n"
        "            log.info(\"Upload saved: %s\", dest)\n"
        "            self._json({\"ok\": True, \"msg\": f\"Saved: {safe_name}\"})"
    )
    NEW = (
        "            _invalidate_lib_cache()\n"
        "            log.info(\"Upload saved: %s\", dest)\n"
        "            # ── Notify folder-source streams about the new file ──\n"
        "            _notify_folder_upload(safe_dir)\n"
        "            self._json({\"ok\": True, \"msg\": f\"Saved: {safe_name}\"})"
    )

    HELPER = '''

def _notify_folder_upload(upload_dir: Path) -> None:
    """
    After a successful upload into *upload_dir*, walk all active streams that
    have a folder_source.  If the stream's folder_source is *upload_dir* or
    any parent of *upload_dir*, invalidate its in-memory playlist so that the
    next start/restart picks up the new files automatically.

    This does NOT restart the stream — it only marks the playlist as stale so
    the worker's folder-rescan logic runs on the very next _do_start().
    """
    mgr = _WEB_MANAGER
    if mgr is None:
        return
    try:
        upload_resolved = upload_dir.resolve()
        for st in mgr.states:
            cfg = st.config
            if cfg.folder_source is None:
                continue
            try:
                folder_resolved = cfg.folder_source.resolve()
            except Exception:
                continue
            # Match if upload landed in the folder or a subfolder of it.
            try:
                upload_resolved.relative_to(folder_resolved)
                is_related = True
            except ValueError:
                is_related = (folder_resolved == upload_resolved)
            if not is_related:
                continue
            # Trigger a rescan immediately (non-blocking)
            import threading as _thr
            from hc.folder_scanner import scan_folder
            def _rescan(cfg=cfg, folder=folder_resolved):
                try:
                    items, warnings = scan_folder(folder)
                    if items:
                        cfg.playlist = items
                        log.info(
                            "web upload: refreshed playlist for '%s' "
                            "(%d files from %s)",
                            cfg.name, len(items), folder.name,
                        )
                    for w in warnings:
                        log.warning("web upload folder scan: %s", w)
                except Exception as exc:
                    log.warning(
                        "web upload: folder rescan for '%s' failed: %s",
                        cfg.name, exc,
                    )
            _thr.Thread(target=_rescan, daemon=True,
                        name=f"upload-rescan-{cfg.name}").start()
    except Exception as exc:
        log.debug("_notify_folder_upload error: %s", exc)
'''

    if OLD not in text:
        print("  SKIP web.py patch (marker not found — already patched or changed)")
        return

    if "_notify_folder_upload" in text:
        print("  SKIP web.py patch (already applied)")
        return

    text = text.replace(OLD, NEW)
    # Insert the helper before the REQUEST HANDLER section
    INSERT_BEFORE = "# =============================================================================\n# REQUEST HANDLER\n"
    if INSERT_BEFORE in text:
        text = text.replace(INSERT_BEFORE, HELPER + "\n" + INSERT_BEFORE, 1)
    else:
        text += HELPER

    web_path.write_text(text, encoding="utf-8")
    print(f"  ✔  hc/web.py (upload folder-rescan hook injected)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\nHydraCast v5.1.0 patcher — root: {HERE}\n")

    patch_dir = HERE / "patches_v510"

    print("Applying file replacements …")
    _replace(patch_dir / "worker.py",    HC / "worker.py")
    _replace(patch_dir / "tui.py",       HC / "tui.py")
    _replace(patch_dir / "hydracast.py", HERE / "hydracast.py")

    print("\nApplying web.py upload patch …")
    _patch_web_upload(HC / "web.py")

    print("\nAll patches applied.  Restart HydraCast to use v5.1.0.\n")
