@echo off
setlocal EnableDelayedExpansion

echo [HydraCast] Standalone build ^(no Google Auth^)

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
REM  Track requirements hash so we only reinstall when the file changes.
set REQ_HASH_FILE=.build_env\req.hash
set REQ_FILE=requirements.txt

REM Generate hash of requirements.txt (CertUtil is available on all Windows)
for /f "tokens=*" %%H in ('certutil -hashfile "%REQ_FILE%" MD5 2^>nul ^| findstr /v ":"') do set CUR_HASH=%%H

set PREV_HASH=
if exist "%REQ_HASH_FILE%" set /p PREV_HASH=<"%REQ_HASH_FILE%"

if "!CUR_HASH!" == "!PREV_HASH!" (
    echo [HydraCast] requirements.txt unchanged — skipping pip install.
) else (
    echo [HydraCast] Installing / updating dependencies ...
    REM Exclude Google Auth packages — not needed for standalone build.
    pip install -r "%REQ_FILE%" ^
        --ignore-requires-python -q ^
        --constraint .build_env\constraints.txt 2>nul || ^
    pip install -r "%REQ_FILE%" -q
    if errorlevel 1 (
        echo [HydraCast] ERROR: pip install failed.
        pause & exit /b 1
    )
    REM Uninstall Google Auth if it snuck in via a transitive dependency.
    pip uninstall -y google-auth google-auth-oauthlib google-api-python-client ^
        httplib2 uritemplate 2>nul
    echo !CUR_HASH!>"%REQ_HASH_FILE%"
)

REM ── PyInstaller build ─────────────────────────────────────────────────────
echo [HydraCast] Building EXE ...
pyinstaller hydracast.spec --clean --noconfirm
if errorlevel 1 (
    echo [HydraCast] ERROR: PyInstaller failed.
    pause & exit /b 1
)

echo.
echo [HydraCast] Done!  Output: dist\HydraCast\hydracast.exe
echo [HydraCast] Copy your bin\ folder (mediamtx.exe + bin\bin\ff*.exe) into dist\HydraCast\bin\
pause
