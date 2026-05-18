@echo off
setlocal enabledelayedexpansion

:: Prompt the user to enter the target folder path
set /p "target_dir=Enter the full path of the folder: "

:: Remove any accidental quotes the user might have pasted
set "target_dir=%target_dir:"=%"

:: Check if the directory exists
if not exist "%target_dir%" (
    echo Error: The specified folder does not exist.
    pause
    exit /b
)

echo Processing files and folders in: %target_dir%
echo --------------------------------------------------

:: Define the short and long day mappings
:: Format is "SHORT:LONG"
set "days=MON:MONDAY TUE:TUESDAY WED:WEDNESDAY THU:THURSDAY FRI:FRIDAY SAT:SATURDAY SUN:SUNDAY"

:: Loop through each day pair
for %%A in (%days%) do (
    for /f "tokens=1,2 delims=:" %%B in ("%%A") do (
        set "short=%%B"
        set "long=%%C"
        
        echo Replacing ^(!short!^) with ^(!long!^)...

        :: 1. Rename files first (ordered by depth so subfolders don't shift paths mid-process)
        for /f "delims=" %%F in ('dir "%target_dir%\*(%%B)*" /b /s /a:-d 2^>nul') do (
            set "filepath=%%F"
            set "filename=%%~nxF"
            set "folderpath=%%~dpF"
            
            :: Substitute the string
            set "newfilename=!filename:(%%B)=(%%C)!"
            
            :: Perform the rename
            if not "!filename!"=="!newfilename!" (
                ren "!filepath!" "!newfilename!"
            )
        )

        :: 2. Rename directories (using 'sort /r' to rename deepest subfolders first)
        for /f "delims=" %%D in ('dir "%target_dir%\*(%%B)*" /b /s /a:d 2^>nul ^| sort /r') do (
            set "dirpath=%%D"
            set "dirname=%%~nxD"
            
            set "newdirname=!dirname:(%%B)=(%%C)!"
            
            if not "!dirname!"=="!newdirname!" (
                ren "!dirpath!" "!newdirname!"
            )
        )
    )
)

echo --------------------------------------------------
echo Done! All matching days have been updated.
pause
