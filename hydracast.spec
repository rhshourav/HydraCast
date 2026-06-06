# hydracast.spec  —  Unified TUI + tray EXE  (replaces hydracast.spec + hydracast_bg.spec)
#
# Produces ONE executable that opens the TUI immediately AND keeps a tray
# icon visible at all times.  Closing or minimizing the console hides it
# to the tray.  Right-click tray → "Show TUI" restores the console.
#
# hydracast_guardian.exe is still built from hydracast_guardian.spec
# (unchanged — separate lean EXE, no tray/pystray deps).
#
# Build:
#   pyinstaller hydracast.spec --clean --noconfirm
#   pyinstaller hydracast_guardian.spec --clean --noconfirm

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

holidays_datas = collect_data_files("holidays")
pystray_datas  = collect_data_files("pystray")
PIL_datas      = collect_data_files("PIL")
pystray_subs   = collect_submodules("pystray")
PIL_subs       = collect_submodules("PIL")

a = Analysis(
    ["hydracast.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("hc",        "hc"),
        ("resources", "resources"),
        ("bin",       "bin"),
        *holidays_datas,
        *pystray_datas,
        *PIL_datas,
    ],
    hiddenimports=[
        # ── hc submodules ─────────────────────────────────────────────────────
        "hc.compliance", "hc.constants", "hc.dependency", "hc.firewall",
        "hc.folder_scanner", "hc.folder_watcher", "hc.hc_system",
        "hc.json_manager", "hc.mailer", "hc.manager", "hc.mediamtx_cfg",
        "hc.models", "hc.resume_store", "hc.theme", "hc.tui", "hc.utils",
        "hc.watchdog", "hc.web", "hc.web_access_log", "hc.web_csvmanager",
        "hc.web_filemanager", "hc.web_handler", "hc.web_handlers_calendar",
        "hc.web_handlers_get", "hc.web_handlers_post", "hc.web_holiday_store",
        "hc.web_html", "hc.web_server", "hc.web_settings_manager",
        "hc.web_upload", "hc.worker", "hc.ssl_bootstrap",
        # ── pystray: all backends (win32, gtk, darwin) ────────────────────────
        *pystray_subs,
        # ── PIL: all plugins ──────────────────────────────────────────────────
        *PIL_subs,
        "PIL.Image", "PIL.IcoImagePlugin", "PIL.PngImagePlugin", "PIL.ImageDraw",
        # ── Windows shell / tray integration ─────────────────────────────────
        "win32api", "win32con", "win32gui", "win32gui_struct", "pywintypes",
        # ── stdlib / third-party ──────────────────────────────────────────────
        "holidays", "rich.console", "psutil",
        "ctypes", "ctypes.wintypes",
        "email.mime.multipart", "email.mime.text",
        "webbrowser", "winreg",
        "cryptography",
        "cryptography.x509",
        "cryptography.hazmat.primitives.hashes",
        "cryptography.hazmat.primitives.serialization",
        "cryptography.hazmat.primitives.asymmetric.rsa",
    ],
    excludes=[
        "google", "google.auth", "google.oauth2",
        "google_auth_oauthlib", "googleapiclient",
        "httplib2", "uritemplate",
        "curses", "_curses",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hydracast",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # console=True so the Rich TUI can render to the console window.
    # The tray icon runs on the main thread alongside it.
    console=True,
    icon="resources/HydraCast.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["ffmpeg.exe", "ffprobe.exe", "mediamtx.exe"],
    name="HydraCast",
)
