@echo off
setlocal enabledelayedexpansion

:: 1. Prompt for the target folder
set /p "target_dir=Enter the full path of the folder: "
set "target_dir=%target_dir:"=%"

if not exist "%target_dir%" (
    echo Error: The specified folder does not exist.
    pause
    exit /b
)

:: 2. Display the options menu
echo.
echo Select Renaming Option:
echo 1. Short Underscore to Long Underscore   (e.g., _MON_ to _MONDAY_)
echo 2. Long Underscore to Short Underscore   (e.g., _MONDAY_ to _MON_)
echo 3. Parentheses to Short Underscore       (e.g., (MON) or (MONDAY) to _MON_)
echo 4. Parentheses to Double Underscore Long (e.g., (MON) or (MONDAY) to __MONDAY__)
echo.

choice /c 1234 /m "Enter your choice (1-4): "
set "choice=%errorlevel%"

echo --------------------------------------------------
echo Processing files and folders...
echo --------------------------------------------------

:: Define day mappings (SHORT:LONG)
set "days=MON:MONDAY TUE:TUESDAY WED:WEDNESDAY THU:THURSDAY FRI:FRIDAY SAT:SATURDAY SUN:SUNDAY"

:: Loop through each day pair
for %%A in (%days%) do (
    for /f "tokens=1,2 delims=:" %%B in ("%%A") do (
        set "short=%%B"
        set "long=%%C"

        if "!choice!"=="1" call :Process "_!short!_" "_!long!_"
        if "!choice!"=="2" call :Process "_!long!_" "_!short!_"
        if "!choice!"=="3" (
            call :Process "(!short!)" "_!short!_"
            call :Process "(!long!)" "_!short!_"
        )
        if "!choice!"=="4" (
            call :Process "(!short!)" "__!long!__"
            call :Process "(!long!)" "__!long!__"
        )
    )
)

echo --------------------------------------------------
echo Done! All matching items have been processed.
pause
exit /b

:: Dynamic Processing Subroutine
:Process
set "search=%~1"
set "replace=%~2"

:: Step A: Rename Files
for /f "delims=" %%F in ('dir "%target_dir%\*%search%*" /b /s /a:-d 2^>nul') do (
    set "filepath=%%F"
    set "filename=%%~nxF"
    
    :: Safely evaluate dynamic string replacement
    call set "newfilename=%%filename:!search!=!replace!%%"
    
    if not "!filename!"=="!newfilename!" (
        echo Renaming File: !filename! -^> !newfilename!
        ren "!filepath!" "!newfilename!"
    )
)

:: Step B: Rename Folders (Deepest paths sorted first via 'sort /r')
for /f "delims=" %%D in ('dir "%target_dir%\*%search%*" /b /s /a:d 2^>nul ^| sort /r') do (
    set "dirpath=%%D"
    set "dirname=%%~nxD"
    
    call set "newdirname=%%dirname:!search!=!replace!%%"
    
    if not "!dirname!"=="!newdirname!" (
        echo Renaming Folder: !dirname! -^> !newdirname!
        ren "!dirpath!" "!newdirname!"
    )
)
goto :eof
