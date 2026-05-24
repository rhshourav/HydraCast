# hydracast_guardian.spec  —  Guardian watchdog EXE (no console, no tray)
#
# Produces hydracast_guardian.exe, placed beside hydracast_bg.exe so the tray
# process can launch it as a fully independent supervisor.
#
# Build with:
#   pyinstaller hydracast_guardian.spec --clean --noconfirm
#
# build.bat handles this automatically — see the updated build.bat.

block_cipher = None

a = Analysis(
    ['hydracast_guardian.py'],   # thin wrapper that calls watchdog.guardian_main()
    pathex=['.'],
    binaries=[],
    datas=[
        ('hc', 'hc'),
    ],
    hiddenimports=[
        'hc.watchdog',
        'hc.constants',
        'hc.models',
        'psutil',
        'socket',
        'json',
        'logging',
        'threading',
        'subprocess',
        'pathlib',
        'http.server',
        'urllib.request',
    ],
    excludes=[
        'google', 'google.auth', 'google.oauth2',
        'google_auth_oauthlib', 'googleapiclient',
        'httplib2', 'uritemplate',
        'pystray', 'PIL', 'rich',
        'curses', '_curses',
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
    name='hydracast_guardian',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                 # no console — fully headless
    icon='resources/HydraCast.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HydraCast_Guardian',
)
