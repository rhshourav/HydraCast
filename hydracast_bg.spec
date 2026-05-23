# hydracast_bg.spec  —  Background + system tray EXE (no Google Auth)
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

holidays_datas = collect_data_files('holidays')
pystray_datas  = collect_data_files('pystray')

a = Analysis(
    ['hydracast_bg.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('hc', 'hc'),
        ('resources', 'resources'),
        ('bin', 'bin'),
        *holidays_datas,
        *pystray_datas,
    ],
    hiddenimports=[
        'hc.compliance', 'hc.constants', 'hc.dependency', 'hc.firewall',
        'hc.folder_scanner', 'hc.folder_watcher', 'hc.hc_system',
        'hc.json_manager', 'hc.mailer', 'hc.manager', 'hc.mediamtx_cfg',
        'hc.models', 'hc.resume_store', 'hc.theme', 'hc.tui', 'hc.utils',
        'hc.watchdog', 'hc.web', 'hc.web_access_log', 'hc.web_csvmanager',
        'hc.web_filemanager', 'hc.web_handler', 'hc.web_handlers_calendar',
        'hc.web_handlers_get', 'hc.web_handlers_post', 'hc.web_holiday_store',
        'hc.web_html', 'hc.web_server', 'hc.web_settings_manager',
        'hc.web_upload', 'hc.worker', 'hc.ssl_bootstrap',
        'pystray', 'pystray._win32',
        'PIL', 'PIL.Image', 'PIL.IcoImagePlugin', 'PIL.PngImagePlugin',
        'holidays', 'rich.console', 'psutil',
        'ctypes', 'ctypes.wintypes',
        'email.mime.multipart', 'email.mime.text',
        'webbrowser', 'cryptography',
        'cryptography.x509', 'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.primitives.serialization',
        'cryptography.hazmat.primitives.asymmetric.rsa',
    ],
    excludes=[
        'google', 'google.auth', 'google.oauth2',
        'google_auth_oauthlib', 'googleapiclient',
        'httplib2', 'uritemplate',
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
    name='hydracast_bg',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # no console window — tray only
    icon='resources/HydraCast.ico',
)

# Build into a temp folder; build.bat copies hydracast_bg.exe into
# dist\HydraCast\ so both EXEs live side-by-side sharing bin/, config/, etc.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['ffmpeg.exe', 'ffprobe.exe', 'mediamtx.exe'],
    name='HydraCast_BG',
)
