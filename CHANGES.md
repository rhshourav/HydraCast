# HydraCast v5.1.0 — Patch Notes

## Bugs Fixed

### 1. Stop (S key) causes stream to immediately restart
**Root cause:** `_auto_restart()` in `worker.py` was called by `_monitor()` when
FFmpeg exited for *any* reason, including a deliberate stop. The `_stop` flag was
set by `stop()` **after** the processes were killed, but `_monitor()` could check
`_stop` before `stop()` set it — so the race was lost.

**Fix (worker.py):**
- `stop()` now sets `_stop = True` as its *first* action, before touching any processes.
- `_auto_restart()` checks `_stop` at every decision point: before scheduling,
  during the countdown (cancels if `_stop` gets set), and again just before calling
  `_do_start()`.
- `_monitor()` checks `_stop` before calling `_auto_restart()`.
- `restart()` no longer calls `stop()` (which sets `_stop`) and then clears it
  afterward in a racy way. Instead it owns the full stop/start sequence while
  holding `_start_lock`, clearing `_stop` only after the stop phase is done.

### 2. Stream selection keys broken (K key conflict, numbers not working)
**Root cause:** In the original `tui.py` / `hydracast.py`, the key `K` was mapped
to both "UP navigation" and a general hotkey placeholder, causing conflicts.
Number key selection worked but the `selected` variable wasn't clamped correctly
in all paths.

**Fix (tui.py + hydracast.py):**
- `K` is no longer used for UP navigation. Only `↑`/`↓` arrows navigate.
- Number keys 1–9 select streams directly (correctly index-clamped).
- Page Up / Page Down jump 5 streams at a time for large setups.
- All key handling extracted into `run_tui_loop()` in `tui.py` so it's
  co-located with the TUI class, not split across two files.

### 3. Newly uploaded files not picked up by streams
**Root cause:** After uploading via the Web UI, the file was saved to disk but
the in-memory `StreamConfig.playlist` was never updated. Folder-source streams
only rescanned on `start()` / `restart()`, not on upload.

**Fix (web.py + worker.py):**
- `web.py` now calls `_notify_folder_upload(upload_dir)` after every successful
  upload. This function finds all streams whose `folder_source` is inside or
  equal to the upload directory, and fires a background rescan thread that
  immediately replaces `cfg.playlist` in memory.
- `worker.py` `_do_start()` already rescans folders on every start — this now
  also benefits from the hot-update so the new file is visible even before the
  next restart.

### 4. `AttributeError: 'StreamState' has no attribute 'seek_start_pos'`
**Fix (worker.py):** `StreamWorker.__init__()` now initialises
`state.seek_start_pos = 0.0` if the attribute is missing (defensive guard).
`_apply_progress()` uses `getattr(self.state, "seek_start_pos", 0.0)` as a
fallback.

---

## New TUI Features

| Key | Action |
|-----|--------|
| `D` | **Detail overlay** — full stream config, all playlist files, RTSP/HLS URLs, error, restart count |
| `V` | **Log viewer** — scrollable per-stream log (↑/↓ to scroll, Page Up/Down for pages) |
| `H` or `?` | **Help overlay** — all keyboard shortcuts with descriptions |
| `F` | **Force folder rescan** — immediately rescans the folder and updates the playlist |
| `C` | **Clear error** — resets ERROR status to STOPPED and clears restart count |
| `Page Up/Down` | Navigate 5 streams at a time |
| `ESC` | Close any overlay and return to main view |

Stream table now shows:
- `[F]` badge for folder-source streams
- `[C]` badge for compliance-mode streams
- `↺N` on port column if the stream has restarted N times

---

## How to Apply

### Option A — Automatic patcher (recommended)

1. Copy the `patches_v510/` folder next to your `hydracast.py`:
   ```
   patches_v510/
     worker.py
     tui.py
     hydracast.py
   ```
2. Run:
   ```bash
   python apply_patches.py
   ```
   This replaces `hc/worker.py`, `hc/tui.py`, and `hydracast.py`, and patches
   `hc/web.py` in-place.

### Option B — Manual file replacement

Replace these files in your install:

| Source file (from this archive) | Destination |
|--------------------------------|-------------|
| `worker.py`    | `hc/worker.py`    |
| `tui.py`       | `hc/tui.py`       |
| `hydracast.py` | `hydracast.py`    |

For `web.py`, add the `_notify_folder_upload()` function (see `web_upload_patch.py`)
and call it from `_handle_upload()` right after `_invalidate_lib_cache()`.

---

## Files in This Patch Archive

```
worker.py          ← replaces hc/worker.py
tui.py             ← replaces hc/tui.py
hydracast.py       ← replaces hydracast.py (root)
apply_patches.py   ← automated patcher script
CHANGES.md         ← this file
web_upload_patch.py← standalone web.py patch helper
```
