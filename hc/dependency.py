"""
hc/dependency.py  —  Download MediaMTX, FFmpeg, and FFprobe.

Binary resolution order (v6.4+)
────────────────────────────────
  For mediamtx, ffmpeg, and ffprobe the lookup follows this priority:

  1. bin/  (next to hydracast.exe / repo root)
       — checked first; if found, used immediately.

  2. HydraCast_internal/bin/  (a separate bundled-binary folder)
       — if a binary is present here but absent from bin/, it is COPIED
         into bin/ and then used from there.  This ensures that bin/ is
         always the canonical runtime location.

  3. System PATH  (for ffmpeg / ffprobe only)
       — checked via shutil.which + subprocess version-probe and, on
         Windows, via ``cmd /c where``.

  4. Download from the internet
       — only attempted when NONE of the above locations contain the
         binary.  The download URL catalogue (MEDIAMTX_URLS /
         _FFMPEG_ARCHIVES / _FFPROBE_ARCHIVES) is unchanged.

The HydraCast_internal directory is resolved relative to the install dir
(_install_dir() in ssl_bootstrap.py uses the same logic):
  Frozen (.exe) : Path(sys.executable).parent / "HydraCast_internal"
  Source (.py)  : repo_root / "HydraCast_internal"
"""
from __future__ import annotations

import logging
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from hc.constants import (
    ARCH_KEY, BIN_DIR, FFMPEG_BIN_NAME, FFPROBE_BIN_NAME,
    IS_WIN, MEDIAMTX_BIN, MEDIAMTX_URLS, MEDIAMTX_VER, OS_KEY,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HydraCast_internal/bin  —  secondary binary source
# ---------------------------------------------------------------------------

def _install_dir() -> Path:
    """
    Return the directory containing hydracast.exe (frozen) or the repo root
    (source).  Mirrors the same helper in ssl_bootstrap.py.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # hc/dependency.py  →  ../  →  repo root
    return Path(__file__).resolve().parent.parent


def _internal_bin_dir() -> Path:
    """
    Return <install_dir>/HydraCast_internal/bin — the secondary location
    where pre-bundled binaries may be shipped alongside the .exe.
    """
    return _install_dir() / "HydraCast_internal" / "bin"


def _copy_from_internal(bin_name: str) -> Optional[Path]:
    """
    Look for *bin_name* in HydraCast_internal/bin/.
    If found, copy it into BIN_DIR() and return the destination path.
    Returns None when the binary is absent from the internal folder or
    when the copy fails.
    """
    src = _internal_bin_dir() / bin_name
    if not src.exists():
        return None
    dest = BIN_DIR() / bin_name
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if not IS_WIN:
            dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        log.info(
            "[dep] Copied %s from HydraCast_internal/bin/ → %s", bin_name, dest
        )
        return dest
    except Exception as exc:
        log.warning(
            "[dep] Could not copy %s from HydraCast_internal/bin/: %s", bin_name, exc
        )
        return None

# ---------------------------------------------------------------------------
# FFmpeg / FFprobe static-build download catalogue
# ---------------------------------------------------------------------------
# BtbN GPL builds (Linux / Windows): https://github.com/BtbN/FFmpeg-Builds
# evermeet.cx (macOS):                https://evermeet.cx/ffmpeg/
#
# Format tag meanings:
#   "tar.xz"     – tar.xz containing …/bin/ffmpeg  + …/bin/ffprobe
#   "zip"        – zip    containing …/bin/ffmpeg.exe + …/bin/ffprobe.exe
#   "zip_single" – zip    containing a single bare binary (macOS evermeet style)
#
# Linux / Windows: both binaries ship in the *same* archive → one download.
# macOS           : ffmpeg and ffprobe are separate evermeet downloads.
# ---------------------------------------------------------------------------
_FFMPEG_ARCHIVES: dict[tuple[str, str], tuple[str, str]] = {
    ("linux",  "amd64"): (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-linux64-gpl.tar.xz",
        "tar.xz",
    ),
    ("linux",  "arm64"): (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-linuxarm64-gpl.tar.xz",
        "tar.xz",
    ),
    # Windows is handled via winget (see _install_ffmpeg_windows).
    ("darwin", "amd64"): (
        "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
        "zip_single",
    ),
    ("darwin", "arm64"): (
        "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
        "zip_single",
    ),
}

# Separate ffprobe archives — only required for macOS.
# On Linux / Windows, ffprobe ships inside the same BtbN archive as ffmpeg.
_FFPROBE_ARCHIVES: dict[tuple[str, str], tuple[str, str]] = {
    ("darwin", "amd64"): (
        "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",
        "zip_single",
    ),
    ("darwin", "arm64"): (
        "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",
        "zip_single",
    ),
}


class DependencyManager:

    # ── Binary detection ──────────────────────────────────────────────────────
    @staticmethod
    def _find_binary(name: str) -> Optional[str]:
        """Return the resolved path to *name* if it is executable, else None.

        Checks (in order):
          1. Local BIN_DIR() – the canonical runtime location.
          2. HydraCast_internal/bin/ – if found, copies to BIN_DIR() first.
          3. System PATH via shutil.which + a -version probe.
          4. On Windows: ``cmd /c where <name>`` to catch winget installs whose
             PATH update is not yet visible in the current process.
        """
        # 1. Local bin/ directory — primary location
        local = BIN_DIR() / name
        if local.exists():
            for flag in ("-version", "--version"):
                try:
                    r = subprocess.run(
                        [str(local), flag], capture_output=True, timeout=8
                    )
                    if r.returncode == 0:
                        return str(local)
                except Exception:
                    pass
            # Binary exists but version probe failed — return path anyway.
            return str(local)

        # 2. HydraCast_internal/bin/ — copy into bin/ then use from there
        copied = _copy_from_internal(name)
        if copied is not None:
            return str(copied)

        # 3. System PATH
        sys_path = shutil.which(name)
        if sys_path:
            for flag in ("-version", "--version"):
                try:
                    r = subprocess.run(
                        [sys_path, flag], capture_output=True, timeout=8
                    )
                    if r.returncode == 0:
                        return sys_path
                except Exception:
                    pass

        # 4. Windows: shell out so the child process inherits the *updated* PATH
        #    that winget wrote to the registry (the current process started before
        #    winget modified PATH, so os.environ is stale).
        if IS_WIN:
            try:
                r = subprocess.run(
                    ["cmd", "/c", f"where {name}"],
                    capture_output=True, text=True, timeout=8,
                )
                if r.returncode == 0:
                    found = r.stdout.strip().splitlines()[0].strip()
                    if found:
                        return found
            except Exception:
                pass

        return None

    @classmethod
    def check_ffmpeg(cls) -> Optional[str]:
        return cls._find_binary(FFMPEG_BIN_NAME)

    @classmethod
    def check_ffprobe(cls) -> Optional[str]:
        return cls._find_binary(FFPROBE_BIN_NAME)

    # ── Shared download/extraction helpers ───────────────────────────────────
    @staticmethod
    def _download_file(url: str, dest: Path, label: str, console: object) -> bool:
        """Download *url* to *dest* with a progress bar.  Returns True on success."""
        from hc.constants import CR, CY
        console.print(f"[{CY}]⬇  Downloading {label} …[/]")
        try:
            def _progress(bn: int, bs: int, ts: int) -> None:
                if ts <= 0:
                    return
                pct = min(100, bn * bs * 100 // ts)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"\r  [{bar}] {pct:3d}%", end="", flush=True)

            urllib.request.urlretrieve(url, dest, reporthook=_progress)
            print()
            return True
        except Exception as exc:
            print()
            console.print(f"[{CR}]✘  Download failed: {exc}[/]")
            return False

    @staticmethod
    def _extract_single_binary(
        archive: Path, target: Path, bin_name: str, fmt: str
    ) -> bool:
        """
        Extract the binary whose filename stem matches *bin_name* from
        *archive* and write it to *target*.

        *bin_name* may include a platform suffix (e.g. "ffmpeg.exe"); the
        comparison is done against both the bare stem and the .exe variant so
        the same code works on every OS.
        """
        stem = Path(bin_name).stem.lower()          # "ffmpeg"  (no extension)
        candidates = {stem, f"{stem}.exe"}           # accept either form

        try:
            if fmt == "tar.xz":
                with tarfile.open(archive, "r:xz") as tf:
                    for m in tf.getmembers():
                        if Path(m.name).name.lower() in candidates and m.isfile():
                            fobj = tf.extractfile(m)
                            if fobj:
                                target.parent.mkdir(parents=True, exist_ok=True)
                                target.write_bytes(fobj.read())
                                return True

            elif fmt in ("zip", "zip_single"):
                with zipfile.ZipFile(archive) as zf:
                    for entry in zf.namelist():
                        if Path(entry).name.lower() in candidates:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(zf.read(entry))
                            return True
        except Exception:
            pass

        return False

    @staticmethod
    def _make_executable(path: Path) -> None:
        """Add execute bits on POSIX systems (no-op on Windows)."""
        if not IS_WIN and path.exists():
            path.chmod(
                path.stat().st_mode
                | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
            )

    # ── Windows: winget installer ─────────────────────────────────────────────
    @classmethod
    def _install_ffmpeg_windows(cls, console: object) -> bool:
        """
        Ensure FFmpeg (and FFprobe) are available on Windows.

        Resolution order — winget is only attempted as a last resort:
          1. bin/ffmpeg.exe already present  → use it (no-op).
          2. HydraCast_internal/bin/ffmpeg.exe present → copy to bin/.
          3. System PATH (shutil.which / cmd where) → use from PATH.
          4. winget install Gyan.FFmpeg → last resort, requires internet.

        This mirrors _find_binary() but is kept here so download_ffmpeg()
        has a single Windows entry-point with clear, auditable steps.
        """
        from hc.constants import CG, CR, CY

        # ── 1. Already in bin/ ─────────────────────────────────────────────
        local = BIN_DIR() / FFMPEG_BIN_NAME
        if local.exists():
            console.print(f"[{CG}]✔  FFmpeg already present → {local}[/]")
            return True

        # ── 2. HydraCast_internal/bin/ → copy into bin/ ───────────────────
        copied = _copy_from_internal(FFMPEG_BIN_NAME)
        if copied is not None:
            console.print(
                f"[{CG}]✔  FFmpeg copied from HydraCast_internal/bin/ → {copied}[/]"
            )
            # Also copy ffprobe if available
            _copy_from_internal(FFPROBE_BIN_NAME)
            return True

        # ── 3. System PATH ─────────────────────────────────────────────────
        sys_ff = shutil.which(FFMPEG_BIN_NAME) or shutil.which("ffmpeg")
        if sys_ff:
            console.print(f"[{CG}]✔  FFmpeg found on system PATH → {sys_ff}[/]")
            # Copy into bin/ so it becomes the canonical runtime location.
            try:
                local.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sys_ff, local)
                console.print(f"[{CG}]   Copied to bin/ for consistent runtime access.[/]")
                # Mirror ffprobe if it sits next to ffmpeg on PATH.
                sys_fp = shutil.which(FFPROBE_BIN_NAME) or shutil.which("ffprobe")
                if sys_fp:
                    shutil.copy2(sys_fp, BIN_DIR() / FFPROBE_BIN_NAME)
            except Exception as exc:
                log.warning("[dep] Could not copy PATH FFmpeg into bin/: %s", exc)
                # Non-fatal: the PATH version is still usable.
            return True

        # ── 4. winget — last resort (requires internet + UAC) ─────────────
        if not shutil.which("winget"):
            console.print(
                f"[{CR}]✘  FFmpeg not found and winget is not available.[/]\n"
                f"[{CY}]   Install FFmpeg manually from "
                f"https://www.gyan.dev/ffmpeg/builds/ and place ffmpeg.exe "
                f"in the bin/ folder next to hydracast.exe.[/]"
            )
            return False

        console.print(f"[{CY}]⬇  Installing FFmpeg via winget (Gyan.FFmpeg) …[/]")
        console.print(f"[{CY}]   This may take a minute — a UAC prompt may appear.[/]")
        try:
            result = subprocess.run(
                [
                    "winget", "install",
                    "--id",    "Gyan.FFmpeg",
                    "-e",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                # Do NOT capture output so the winget progress bar is visible.
                timeout=300,
            )
        except FileNotFoundError:
            console.print(f"[{CR}]✘  winget executable not found.[/]")
            return False
        except subprocess.TimeoutExpired:
            console.print(f"[{CR}]✘  winget timed out after 5 minutes.[/]")
            return False
        except Exception as exc:
            console.print(f"[{CR}]✘  winget error: {exc}[/]")
            return False

        if result.returncode != 0:
            console.print(
                f"[{CR}]✘  winget exited with code {result.returncode}.[/]\n"
                f"[{CY}]   Try running manually:  winget install --id Gyan.FFmpeg -e[/]"
            )
            return False

        console.print(f"[{CG}]✔  FFmpeg installed via winget.[/]")
        return True

    # ── FFmpeg / FFprobe downloader ───────────────────────────────────────────
    @classmethod
    def _pick_ffmpeg_entry(
        cls,
    ) -> Optional[Tuple[str, str]]:
        """Return (url, fmt) for the current OS/arch, or None if unsupported."""
        key = (OS_KEY, ARCH_KEY)
        if key in _FFMPEG_ARCHIVES:
            return _FFMPEG_ARCHIVES[key]
        # Fallback: match OS only (e.g. unknown arm variant → try the arm64 build)
        for (os_, _arch), val in _FFMPEG_ARCHIVES.items():
            if os_ == OS_KEY:
                return val
        return None

    @classmethod
    def download_ffmpeg(cls, console: object) -> bool:
        """
        Install FFmpeg (and FFprobe where bundled) for the current platform.

        • Windows  → ``winget install --id Gyan.FFmpeg``
        • Linux    → BtbN static .tar.xz  (ffmpeg + ffprobe bundled)
        • macOS    → evermeet.cx static .zip (ffmpeg); separate download for ffprobe

        Returns True if at least FFmpeg was successfully installed.
        FFprobe installation is attempted but its failure is non-fatal.
        """
        from hc.constants import CG, CR, CY

        # ── Windows: delegate entirely to winget ──────────────────────────────
        if IS_WIN:
            return cls._install_ffmpeg_windows(console)

        # ── Linux / macOS: static archive download ────────────────────────────
        bin_dir = BIN_DIR()
        bin_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_dest  = bin_dir / FFMPEG_BIN_NAME
        ffprobe_dest = bin_dir / FFPROBE_BIN_NAME
        key          = (OS_KEY, ARCH_KEY)

        # ── Already present in bin/? ───────────────────────────────────────────
        if ffmpeg_dest.exists():
            console.print(f"[{CG}]✔  FFmpeg already present.[/]")
            if not ffprobe_dest.exists():
                cls._maybe_download_ffprobe(ffprobe_dest, key, console)
            return True

        # ── HydraCast_internal/bin/ fallback — copy both if available ─────────
        ff_copied = _copy_from_internal(FFMPEG_BIN_NAME)
        if ff_copied is not None:
            console.print(
                f"[{CG}]✔  FFmpeg copied from HydraCast_internal/bin/ → {ff_copied}[/]"
            )
            fp_copied = _copy_from_internal(FFPROBE_BIN_NAME)
            if fp_copied is not None:
                console.print(
                    f"[{CG}]✔  FFprobe copied from HydraCast_internal/bin/ → {fp_copied}[/]"
                )
            else:
                # ffprobe missing from internal — attempt platform-specific download
                cls._maybe_download_ffprobe(ffprobe_dest, key, console)
            return True

        # ── Resolve archive URL ───────────────────────────────────────────────
        entry = cls._pick_ffmpeg_entry()
        if not entry:
            console.print(
                f"[{CR}]✘  No FFmpeg static build is available for "
                f"{OS_KEY}/{ARCH_KEY}.[/]"
            )
            return False

        url, fmt = entry
        archive_name = Path(url).name or f"ffmpeg_{OS_KEY}_{ARCH_KEY}.archive"
        archive = bin_dir / archive_name

        # ── Download ──────────────────────────────────────────────────────────
        label = f"FFmpeg static build ({OS_KEY}/{ARCH_KEY})"
        if not cls._download_file(url, archive, label, console):
            archive.unlink(missing_ok=True)
            return False

        # ── Extract ffmpeg ────────────────────────────────────────────────────
        ok_ffmpeg = cls._extract_single_binary(archive, ffmpeg_dest, FFMPEG_BIN_NAME, fmt)

        # ── Extract ffprobe (same archive for Linux / Windows BtbN builds) ───
        ok_ffprobe = False
        if fmt in ("tar.xz", "zip"):
            ok_ffprobe = cls._extract_single_binary(
                archive, ffprobe_dest, FFPROBE_BIN_NAME, fmt
            )

        archive.unlink(missing_ok=True)

        if not ok_ffmpeg:
            console.print(f"[{CR}]✘  Could not extract FFmpeg from the archive.[/]")
            return False

        # ── Mark executables ──────────────────────────────────────────────────
        cls._make_executable(ffmpeg_dest)
        cls._make_executable(ffprobe_dest)

        console.print(f"[{CG}]✔  FFmpeg  installed → {ffmpeg_dest}[/]")
        if ok_ffprobe:
            console.print(f"[{CG}]✔  FFprobe installed → {ffprobe_dest}[/]")
        elif not ok_ffprobe and fmt in ("tar.xz", "zip"):
            # BtbN archives always contain ffprobe — warn but don't abort.
            console.print(f"[{CY}]⚠  FFprobe not found in archive (optional).[/]")

        # ── macOS: separate ffprobe download ──────────────────────────────────
        if not ok_ffprobe:
            cls._maybe_download_ffprobe(ffprobe_dest, key, console)

        return True

    @classmethod
    def _maybe_download_ffprobe(
        cls, dest: Path, key: tuple[str, str], console: object
    ) -> None:
        """Download ffprobe from a platform-specific separate archive if available."""
        from hc.constants import CG, CR, CY

        if key not in _FFPROBE_ARCHIVES:
            return  # Not available for this platform separately

        if dest.exists():
            return  # Already installed

        url, fmt = _FFPROBE_ARCHIVES[key]
        # evermeet URLs don't have a meaningful filename; craft one.
        archive = dest.parent / f"ffprobe_{key[0]}_{key[1]}.zip"

        console.print(f"[{CY}]⬇  Downloading FFprobe separately ({key[0]}/{key[1]}) …[/]")
        if not cls._download_file(url, archive, "FFprobe", console):
            archive.unlink(missing_ok=True)
            console.print(f"[{CY}]⚠  FFprobe download failed (optional — continuing).[/]")
            return

        ok = cls._extract_single_binary(archive, dest, FFPROBE_BIN_NAME, fmt)
        archive.unlink(missing_ok=True)

        if ok:
            cls._make_executable(dest)
            console.print(f"[{CG}]✔  FFprobe installed → {dest}[/]")
        else:
            console.print(f"[{CY}]⚠  FFprobe extraction failed (optional — continuing).[/]")

    # ── High-level ensure methods (called from _preflight) ───────────────────
    @classmethod
    def ensure_ffmpeg(cls, console: object) -> Optional[str]:
        """
        Return the path to FFmpeg, auto-downloading a static build if it is
        not already present on the system or in BIN_DIR().

        Returns None only if the binary is unavailable after all attempts.
        """
        from hc.constants import CG, CY

        path = cls.check_ffmpeg()
        if path:
            console.print(f"[{CG}]✔  FFmpeg  : {path}[/]")
            return path

        console.print(
            f"[{CY}]⚠  FFmpeg not found in bin/ or HydraCast_internal/bin/ — "
            f"attempting automatic download …[/]"
        )
        if cls.download_ffmpeg(console):
            return cls.check_ffmpeg()
        return None

    @classmethod
    def ensure_ffprobe(cls, console: object) -> Optional[str]:
        """
        Return the path to FFprobe, auto-downloading if not present.

        Missing FFprobe is non-fatal; this method returns None on failure
        without printing an error — the caller decides how to handle absence.
        """
        from hc.constants import CG, CY

        path = cls.check_ffprobe()
        if path:
            console.print(f"[{CG}]✔  FFprobe : {path}[/]")
            return path

        key = (OS_KEY, ARCH_KEY)

        # For macOS, try the dedicated ffprobe archive.
        if key in _FFPROBE_ARCHIVES:
            console.print(
                f"[{CY}]⚠  FFprobe not found — attempting automatic download …[/]"
            )
            ffprobe_dest = BIN_DIR() / FFPROBE_BIN_NAME
            cls._maybe_download_ffprobe(ffprobe_dest, key, console)
            return cls.check_ffprobe()

        # For Linux / Windows, ffprobe ships bundled with FFmpeg.
        # On Windows it was installed by winget alongside ffmpeg; if it still
        # cannot be found, there is nothing more we can do here.
        if IS_WIN:
            console.print(f"[{CY}]⚠  FFprobe not found in PATH (optional — continuing).[/]")
            return None

        # Linux: ffprobe ships bundled with FFmpeg. If it is missing here,
        # re-run the full FFmpeg download to recover it.
        ffprobe_dest = BIN_DIR() / FFPROBE_BIN_NAME
        if not ffprobe_dest.exists():
            console.print(
                f"[{CY}]⚠  FFprobe not found — re-running FFmpeg download to recover it …[/]"
            )
            # Temporarily rename existing ffmpeg so download_ffmpeg does not
            # short-circuit on the "already present" check.
            ffmpeg_dest = BIN_DIR() / FFMPEG_BIN_NAME
            _tmp = ffmpeg_dest.with_suffix(".bak") if ffmpeg_dest.exists() else None
            if _tmp:
                ffmpeg_dest.rename(_tmp)
            try:
                cls.download_ffmpeg(console)
            finally:
                if _tmp and _tmp.exists() and not ffmpeg_dest.exists():
                    _tmp.rename(ffmpeg_dest)
                elif _tmp and _tmp.exists():
                    _tmp.unlink(missing_ok=True)

        return cls.check_ffprobe()

    # ── MediaMTX downloader ───────────────────────────────────────────────────
    @staticmethod
    def _pick_mediamtx_url() -> Optional[str]:
        key = (OS_KEY, ARCH_KEY)
        if key in MEDIAMTX_URLS:
            return MEDIAMTX_URLS[key]
        # Fallback: match OS only
        for (os_, _), url in MEDIAMTX_URLS.items():
            if os_ == OS_KEY:
                return url
        return None

    @staticmethod
    def download_mediamtx(console: object) -> bool:
        from rich.console import Console as RichConsole
        con: RichConsole = console  # type: ignore[assignment]
        from hc.constants import CG, CR, CY

        mtx_bin = MEDIAMTX_BIN()

        # 1. Already in bin/
        if mtx_bin.exists():
            con.print(f"[{CG}]✔  MediaMTX already present.[/]")
            return True

        # 2. HydraCast_internal/bin/ — copy into bin/ first
        copied = _copy_from_internal(mtx_bin.name)
        if copied is not None:
            con.print(f"[{CG}]✔  MediaMTX copied from HydraCast_internal/bin/ → {copied}[/]")
            return True

        # 3. Download from the internet
        url = DependencyManager._pick_mediamtx_url()
        if not url:
            con.print(f"[{CR}]✘  No MediaMTX build for {OS_KEY}/{ARCH_KEY}.[/]")
            return False

        archive = BIN_DIR() / Path(url).name
        con.print(f"[{CY}]⬇  Downloading MediaMTX v{MEDIAMTX_VER} …[/]")

        try:
            def _progress(bn: int, bs: int, ts: int) -> None:
                if ts <= 0:
                    return
                pct = min(100, bn * bs * 100 // ts)
                print(f"\r  [{'█'*(pct//5)}{'░'*(20-pct//5)}] {pct:3d}%",
                      end="", flush=True)
            urllib.request.urlretrieve(url, archive, reporthook=_progress)
            print()
        except Exception as exc:
            con.print(f"\n[{CR}]✘  Download failed: {exc}[/]")
            return False

        try:
            if archive.suffix in (".gz", ".tgz") or archive.name.endswith(".tar.gz"):
                with tarfile.open(archive, "r:gz") as tf:
                    for m in tf.getmembers():
                        if Path(m.name).name in ("mediamtx", "mediamtx.exe") and m.isfile():
                            m.name = mtx_bin.name
                            tf.extract(m, BIN_DIR())
                            break
            elif archive.suffix == ".zip":
                with zipfile.ZipFile(archive) as zf:
                    for name in zf.namelist():
                        if Path(name).name.lower().startswith("mediamtx"):
                            mtx_bin.write_bytes(zf.read(name))
                            break
            archive.unlink(missing_ok=True)
        except Exception as exc:
            con.print(f"[{CR}]✘  Extraction failed: {exc}[/]")
            return False

        if not IS_WIN:
            mtx_bin.chmod(mtx_bin.stat().st_mode | stat.S_IEXEC)

        con.print(f"[{CG}]✔  MediaMTX installed → {mtx_bin}[/]")
        return True
