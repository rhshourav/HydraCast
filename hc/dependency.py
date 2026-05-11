"""
hc/dependency.py  —  Download MediaMTX and locate FFmpeg/FFprobe.
"""
from __future__ import annotations

import shutil
import stat
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from hc.constants import (
    ARCH_KEY, BIN_DIR, FFMPEG_BIN_NAME, FFPROBE_BIN_NAME,
    IS_WIN, MEDIAMTX_BIN, MEDIAMTX_URLS, MEDIAMTX_VER, OS_KEY,
)


class DependencyManager:

    # ── Binary detection ──────────────────────────────────────────────────────
    @staticmethod
    def _find_binary(name: str) -> Optional[str]:
        """Return path to *name* if it responds to -version, else None."""
        # Check system PATH first
        for flag in ("-version", "--version"):
            try:
                r = subprocess.run([name, flag], capture_output=True, timeout=8)
                if r.returncode == 0:
                    return shutil.which(name) or name
            except Exception:
                pass
        # Check local bin/ dir
        local = BIN_DIR() / name
        if local.exists():
            return str(local)
        return None

    @classmethod
    def check_ffmpeg(cls) -> Optional[str]:
        return cls._find_binary(FFMPEG_BIN_NAME)

    @classmethod
    def check_ffprobe(cls) -> Optional[str]:
        return cls._find_binary(FFPROBE_BIN_NAME)

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
    def download_mediamtx(console: object) -> bool:  # console: rich.Console
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
