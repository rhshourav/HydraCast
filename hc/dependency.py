"""
hc/dependency.py  —  Download MediaMTX, FFmpeg, and FFprobe.
"""
from __future__ import annotations

import shutil
import stat
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from hc.constants import (
    ARCH_KEY, BIN_DIR, FFMPEG_BIN_NAME, FFPROBE_BIN_NAME,
    IS_WIN, MEDIAMTX_BIN, MEDIAMTX_URLS, MEDIAMTX_VER, OS_KEY,
)

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
    ("win",    "amd64"): (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-win64-gpl.zip",
        "zip",
    ),
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
          1. System PATH via shutil.which + a -version probe.
          2. Local BIN_DIR() – accepts the file if it exists even when the
             version probe fails (the binary may need execute permission set).
        """
        # 1. System PATH
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

        # 2. Local bin/ directory
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
            # Binary exists but version probe failed — return the path anyway
            # so the caller can decide what to do.
            return str(local)

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
        Download a static FFmpeg build (and FFprobe where bundled) for the
        current platform into BIN_DIR().

        Returns True if at least FFmpeg was successfully installed.
        FFprobe installation is attempted but its failure is non-fatal.
        """
        from hc.constants import CG, CR, CY

        bin_dir = BIN_DIR()
        bin_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_dest  = bin_dir / FFMPEG_BIN_NAME
        ffprobe_dest = bin_dir / FFPROBE_BIN_NAME
        key          = (OS_KEY, ARCH_KEY)

        # ── Already present? ──────────────────────────────────────────────────
        if ffmpeg_dest.exists():
            console.print(f"[{CG}]✔  FFmpeg already present.[/]")
            if not ffprobe_dest.exists():
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
            f"[{CY}]⚠  FFmpeg not found in PATH or bin/ — "
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

        # For Linux / Windows, ffprobe ships bundled with FFmpeg. If it is
        # missing here, re-run the full FFmpeg download to recover it.
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
        if mtx_bin.exists():
            con.print(f"[{CG}]✔  MediaMTX already present.[/]")
            return True

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
