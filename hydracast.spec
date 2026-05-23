# hydracast.spec  —  Standalone build (no Google Auth)
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Only collect holidays data; Google Auth is excluded entirely.
holidays_datas = collect_data_files('holidays')

a = Analysis(
    ['hydracast.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # hc package non-py files
        ('hc', 'hc'),
        # resources folder (icon, SVG, etc.)
        ('resources', 'resources'),
        # bin folder — mediamtx.exe + bin/bin/ffmpeg.exe etc. included as-is
        ('bin', 'bin'),
        # holidays locale/data files
        *holidays_datas,
    ],
    hiddenimports=[
        # ── hc submodules (dynamically imported) ─────────────────────────────
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
        # ── stdlib / third-party ─────────────────────────────────────────────
        'holidays',
        'rich.console',
        'psutil',
        'ctypes',
        'ctypes.wintypes',
        'email.mime.multipart',
        'hc.ssl_bootstrap',
        'cryptography',
        'cryptography.x509',
        'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.primitives.serialization',
        'cryptography.hazmat.primitives.asymmetric.rsa',
        'email.mime.text',
    ],
    # Explicitly exclude Google Auth packages to keep the EXE small.
    excludes=[
        'google',
        'google.auth',
        'google.oauth2',
        'google_auth_oauthlib',
        'googleapiclient',
        'httplib2',
        'uritemplate',
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
    exclude_binaries=True,           # one-dir mode (dist/HydraCast/)
    name='hydracast',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                        # compress if UPX is installed
    console=True,                    # TUI needs a visible console
    icon='resources/HydraCast.ico',  # corrected icon filename
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        # Do not UPX-compress native binaries — they are already compressed
        # and double-compression often breaks them.
        'ffmpeg.exe',
        'ffprobe.exe',
        'mediamtx.exe',
    ],
    name='HydraCast',                # output folder: dist/HydraCast/
)
