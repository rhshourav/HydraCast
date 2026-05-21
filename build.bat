@echo off
setlocal

echo [HydraCast] Setting up build environment...
python -m venv .build_env
call .build_env\Scripts\activate.bat

echo [HydraCast] Installing dependencies...
pip install -r requirements.txt -q

echo [HydraCast] Building EXE...
pyinstaller hydracast.spec --clean --noconfirm

echo.
echo [HydraCast] Done! Output: dist\HydraCast\hydracast.exe
pause
