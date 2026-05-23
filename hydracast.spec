# hydracast.spec  —  Standalone build (no Google Auth)
# ─────────────────────────────────────────────────────
# Build:  pyinstaller hydracast.spec --clean --noconfirm
#
# Output: dist/HydraCast/hydracast.exe   (one-dir, self-contained)
#
# What changed vs the old spec:
#   • Removed all google.auth / google-oauth2 / googleapiclient references
#     (datas, hiddenimports) — not needed for standalone use.
#   • Added 'excludes' list to shed unused heavy packages (test suites,
#     tkinter, matplotlib, etc.) that PyInstaller may drag in transitively.
#   • Removed pkg_resources.py2_warn (deprecated shim, causes warnings on
#     modern pip/setuptools).
#   • Fixed icon path: resources/HydraCast.ico  (matches actual filename in
#     the repo; old spec referenced resources/shourav.ico which doesn't exist
#     and causes a build warning / missing-icon on the final .exe).
#   • upx=False on COLLECT to avoid UPX corrupting binary data files;
#     UPX is still applied to the EXE stub only (upx=True on EXE).

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# ── Package data needed at runtime ────────────────────────────────────────────
holidays_datas = collect_data_files('holidays')

a = Analysis(
    ['hydracast.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # hc package (non-py files, e.g. templates, static assets inside hc/)
        ('hc', 'hc'),
        # Web/UI resources (SVG, ICO, logo, etc.)
        ('resources', 'resources'),
        # Pre-bundled runtime binaries: mediamtx.exe + ffmpeg in bin/bin/
        # Both are copied into the output bin/ tree as-is.
        ('bin', 'bin'),
        # holidays locale data (required by the holiday-store module)
        *holidays_datas,
    ],
    hiddenimports=[
        # ── hc sub-modules (imported dynamically at runtime) ──────────────────
        'hc.compliance',
        'hc.constants',
        'hc.dependency',
        'hc.firewall',
        'hc.folder_scanner',
        'hc.folder_watcher',
        'hc.hc_system',
        'hc.json_manager',
        'hc.mailer',
        'hc.manager',
        'hc.mediamtx_cfg',
        'hc.models',
        'hc.resume_store',
        'hc.theme',
        'hc.tui',
        'hc.utils',
        'hc.watchdog',
        'hc.web',
        'hc.web_access_log',
        'hc.web_csvmanager',
        'hc.web_filemanager',
        'hc.web_handler',
        'hc.web_handlers_calendar',
        'hc.web_handlers_get',
        'hc.web_handlers_post',
        'hc.web_holiday_store',
        'hc.web_html',
        'hc.web_server',
        'hc.web_settings_manager',
        'hc.web_upload',
        'hc.worker',
        # ── stdlib modules that PyInstaller sometimes misses ──────────────────
        'ctypes',
        'ctypes.wintypes',
        'email.mime.multipart',
        'email.mime.text',
        # ── third-party ───────────────────────────────────────────────────────
        'rich.console',
        'psutil',
        'holidays',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # ── Explicitly exclude packages we do NOT use ─────────────────────────────
    # This shrinks the bundle and avoids pulling in unneeded transitive deps.
    excludes=[
        # Google ecosystem (removed from this build)
        'google',
        'google.auth',
        'google.oauth2',
        'google_auth_oauthlib',
        'googleapiclient',
        # GUI toolkits — HydraCast is a console/TUI app
        'tkinter',
        '_tkinter',
        'wx',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        # Heavy scientific/plotting libs not used at runtime
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        # Test frameworks
        'pytest',
        'unittest',
        'doctest',
        # IPython / Jupyter
        'IPython',
        'jupyter',
        'notebook',
        # Misc unused
        'xmlrpc',
        'pydoc',
        'pdb',
        'profile',
        'cProfile',
        'difflib',
        'distutils',
    ],
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
    exclude_binaries=True,          # one-dir mode — binaries go in COLLECT
    name='hydracast',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                       # compress the EXE stub (needs UPX in PATH)
    upx_exclude=[                   # never UPX-compress these — they break
        'vcruntime140.dll',
        'python*.dll',
        'ffmpeg.exe',
        'ffprobe.exe',
        'mediamtx.exe',
    ],
    console=True,                   # TUI app — keep the console window
    icon='resources/HydraCast.ico', # must exist; build will warn if absent
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,          # do NOT UPX the collected binaries — safe for data files
    upx_exclude=[],
    name='HydraCast',   # dist/HydraCast/  output folder
)
