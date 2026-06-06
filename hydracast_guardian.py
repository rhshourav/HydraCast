#!/usr/bin/env python3
"""
hydracast_guardian.py  —  Entry point for the HydraCast Guardian process.

This is a thin wrapper that simply calls watchdog.guardian_main().
It exists so PyInstaller can build a dedicated hydracast_guardian.exe without
pulling in any UI/TUI/tray dependencies.

KEY DESIGN NOTES
────────────────
• The guardian is launched ONCE by hydracast.exe after it has already
  obtained UAC elevation.  The guardian inherits the elevated token.

• When the guardian relaunches hydracast.exe after a crash it uses
  subprocess.Popen (CreateProcess), NOT ShellExecuteW("runas").
  Because the guardian already runs elevated, the child inherits that
  token — no UAC dialog is ever shown on restart.

• The guardian uses a PID-file lock so only one guardian instance runs
  at a time.  If hydracast.exe is restarted manually while the guardian
  is still alive, the guardian detects the new PID and keeps watching.

Usage (the guardian is normally launched automatically by hydracast.exe):

    hydracast_guardian.exe --target "C:\\...\\hydracast.exe" --log-dir logs

Or for source installs:

    python hydracast_guardian.py --target "python hydracast.py" --log-dir logs
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
