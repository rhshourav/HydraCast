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

REM ── Tray + SSL dependencies ───────────────────────────────────────────────
echo [HydraCast] Ensuring tray and SSL dependencies ...
pip install pystray Pillow cryptography -q
if errorlevel 1 (
    echo [HydraCast] WARNING: optional dependency install had errors -- continuing.
)

REM ── Build hydracast.exe (console TUI) ────────────────────────────────────
echo.
echo [HydraCast] Building hydracast.exe (TUI + console) ...
pyinstaller hydracast.spec --clean --noconfirm
if errorlevel 1 (
    echo [HydraCast] ERROR: hydracast.spec build failed.
    pause & exit /b 1
)

REM ── Build hydracast_bg.exe (no console, system tray) ─────────────────────
echo.
echo [HydraCast] Building hydracast_bg.exe (background + tray) ...
pyinstaller hydracast_bg.spec --clean --noconfirm
if errorlevel 1 (
    echo [HydraCast] ERROR: hydracast_bg.spec build failed.
    pause & exit /b 1
)

REM ── Merge hydracast_bg.exe into the main HydraCast folder ─────────────────
echo.
echo [HydraCast] Copying hydracast_bg.exe into dist\HydraCast\ ...
copy /Y "dist\HydraCast_BG\hydracast_bg.exe" "dist\HydraCast\hydracast_bg.exe"
if errorlevel 1 (
    echo [HydraCast] ERROR: Could not copy hydracast_bg.exe.
    pause & exit /b 1
)
REM Clean up the temporary BG build folder.
rmdir /S /Q "dist\HydraCast_BG"

echo.
echo [HydraCast] Build complete!
echo.
echo   dist\HydraCast\hydracast.exe     -- TUI / interactive mode
echo   dist\HydraCast\hydracast_bg.exe  -- background mode (system tray)
echo.
echo [HydraCast] Both EXEs share the same bin\, config\, media\, logs\ folders.
pause
