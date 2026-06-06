@echo off
setlocal EnableDelayedExpansion

echo [HydraCast] Standalone build  (unified TUI+tray single EXE)
echo.

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

REM ── Tray + SSL + pywin32 dependencies ────────────────────────────────────
echo [HydraCast] Ensuring tray, SSL and win32 dependencies ...
pip install pystray Pillow cryptography pywin32 psutil -q
if errorlevel 1 (
    echo [HydraCast] WARNING: optional dependency install had errors -- continuing.
)
python .build_env\Scripts\pywin32_postinstall.py -install 2>nul

REM ── Build hydracast.exe (unified TUI + tray) ──────────────────────────────
echo.
echo [HydraCast] Building hydracast.exe (unified TUI + tray) ...
pyinstaller hydracast.spec --clean --noconfirm
if errorlevel 1 (
    echo [HydraCast] ERROR: hydracast.spec build failed.
    pause & exit /b 1
)

REM ── Build hydracast_guardian.exe (headless supervisor) ───────────────────
echo.
echo [HydraCast] Building hydracast_guardian.exe (guardian watchdog) ...
pyinstaller hydracast_guardian.spec --clean --noconfirm
if errorlevel 1 (
    echo [HydraCast] ERROR: hydracast_guardian.spec build failed.
    pause & exit /b 1
)

REM ── Merge hydracast_guardian.exe into the main HydraCast folder ──────────
echo.
echo [HydraCast] Merging hydracast_guardian.exe into dist\HydraCast\ ...
copy /Y "dist\HydraCast_Guardian\hydracast_guardian.exe" "dist\HydraCast\hydracast_guardian.exe"
if errorlevel 1 (
    echo [HydraCast] ERROR: Could not copy hydracast_guardian.exe.
    pause & exit /b 1
)
rmdir /S /Q "dist\HydraCast_Guardian"

echo.
echo [HydraCast] dist\HydraCast\ is ready.
echo.
echo   hydracast.exe          -- main app (TUI + tray, single EXE)
echo   hydracast_guardian.exe -- guardian watchdog (auto-launched by hydracast.exe)
echo.

REM ── NSIS Installer ───────────────────────────────────────────────────────
echo [HydraCast] Looking for NSIS to build installer ...

set MAKENSIS=
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe
if exist "C:\Program Files\NSIS\makensis.exe"       set MAKENSIS=C:\Program Files\NSIS\makensis.exe

if "!MAKENSIS!"=="" (
    where makensis >nul 2>&1
    if not errorlevel 1 set MAKENSIS=makensis
)

if "!MAKENSIS!"=="" (
    echo [HydraCast] WARNING: NSIS not found -- skipping installer build.
    echo             Download NSIS from https://nsis.sourceforge.io/
    echo             Then re-run:  makensis HydraCast_Installer.nsi
    echo.
    goto :done
)

echo [HydraCast] Building installer with NSIS ...
"!MAKENSIS!" /V2 HydraCast_Installer.nsi
if errorlevel 1 (
    echo [HydraCast] ERROR: NSIS build failed.
    pause & exit /b 1
)

echo.
echo [HydraCast] ============================================================
echo [HydraCast]  Installer ready:
for %%F in (HydraCast-*-Setup.exe) do echo    %%~fF
echo [HydraCast] ============================================================

:done
echo.
pause
