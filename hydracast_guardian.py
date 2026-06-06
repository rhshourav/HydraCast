#!/usr/bin/env python3
"""
hydracast_guardian.py  —  Entry point for the HydraCast Guardian process.

This is a thin wrapper that simply calls watchdog.guardian_main().
It exists so PyInstaller can build a dedicated hydracast_guardian.exe without
pulling in any UI/TUI/tray dependencies.

Usage (the guardian is normally launched automatically by hydracast_bg.exe):

    hydracast_guardian.exe --target hydracast_bg.exe --log-dir logs

Or for source installs:

    python hydracast_guardian.py --target "python hydracast_bg.py" --log-dir logs
"""
import sys
from pathlib import Path

# Ensure the package root is on sys.path when running from source.
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from hc.watchdog import guardian_main

if __name__ == "__main__":
    guardian_main()
