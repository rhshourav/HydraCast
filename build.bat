@echo off
setlocal EnableDelayedExpansion

echo [HydraCast] Standalone build

REM ── Virtual environment ───────────────────────────────────────────────────
if exist ".build_env\Scripts\activate.bat" (
    echo [HydraCast] Reusing existing .build_env ...
) else (
    echo [HydraCast] Creating .build_env ...
    python -m venv .build_env
    if errorlevel 1 (
        echo [HydraCast] ERROR: python -m venv failed. Is Python 3.8+ in PATH?
        pause & exit /b 1
    )
)
call .build_env\Scripts\activate.bat

REM ── Dependencies ─────────────────────────────────────────────────────────
set REQ_HASH_FILE=.build_env\req.hash
set REQ_FILE=requirements.txt

for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%REQ_FILE%" MD5 2^>nul') do (
    if not defined CUR_HASH set CUR_HASH=%%H
)

set PREV_HASH=
if exist "%REQ_HASH_FILE%" set /p PREV_HASH=<"%REQ_HASH_FILE%"

if "!CUR_HASH!" == "!PREV_HASH!" (
    echo [HydraCast] requirements.txt unchanged -- skipping pip install.
) else (
    echo [HydraCast] Installing / updating dependencies ...
    pip install -r "%REQ_FILE%" -q
    if errorlevel 1 (
        echo [HydraCast] ERROR: pip install failed.
        pause & exit /b 1
    )
    pip uninstall -y google-auth google-auth-oauthlib google-api-python-client httplib2 uritemplate 2>nul
    echo !CUR_HASH!>"%REQ_HASH_FILE%"
)

REM ── Tray dependencies (pystray + Pillow) ─────────────────────────────────
echo [HydraCast] Ensuring tray dependencies (pystray, Pillow) ...
pip install pystray Pillow -q
if errorlevel 1 (
    echo [HydraCast] WARNING: pystray/Pillow install failed -- tray icon will be disabled.
)

REM ── Build hydracast.exe (console / TUI) ──────────────────────────────────
echo.
echo [HydraCast] Building hydracast.exe (TUI) ...
pyinstaller hydracast.spec --clean --noconfirm
if errorlevel 1 (
    echo [HydraCast] ERROR: hydracast.spec build failed.
    pause & exit /b 1
)

REM ── Build hydracast_bg.exe (no console / tray) ───────────────────────────
echo.
echo [HydraCast] Building hydracast_bg.exe (background + tray) ...
pyinstaller hydracast_bg.spec --noconfirm
if errorlevel 1 (
    echo [HydraCast] ERROR: hydracast_bg.spec build failed.
    pause & exit /b 1
)

echo.
echo [HydraCast] Done!
echo   TUI mode : dist\HydraCast\hydracast.exe
echo   BG  mode : dist\HydraCast\hydracast_bg.exe  (system tray)
echo.
echo [HydraCast] Copy your bin\ folder into dist\HydraCast\bin\ if not already there.
pause
