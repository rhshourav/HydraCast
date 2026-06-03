Unicode True

; ============================================================================
;  HydraCast Installer - NSIS Script
;  Produces a single compressed self-extracting EXE installer
;
;  Requirements (build machine):
;    NSIS 3.x  https://nsis.sourceforge.io/
;    Place this .nsi next to the  dist\HydraCast\  folder produced by build.bat
;
;  Build command:
;    makensis HydraCast_Installer.nsi
;
;  Features:
;    - LZMA solid compression  (~60-70 % size reduction)
;    - User-configurable install directory
;    - Start Menu shortcut group (configurable)
;    - Optional "Launch at Windows startup" checkbox
;    - Desktop shortcut (optional)
;    - Full uninstaller registered in Add/Remove Programs
;    - Silent install support  (/S flag)
; ============================================================================

; -- Compression --------------------------------------------------------------
SetCompressor /SOLID lzma
SetCompressorDictSize 64          ; 64 MB dictionary - best ratio for large dirs

; -- Includes -----------------------------------------------------------------
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"

; -- Product metadata ---------------------------------------------------------
!define PRODUCT_NAME        "HydraCast"
!define PRODUCT_VERSION     "6.5.0"
!define PRODUCT_PUBLISHER   "rhshourav"
!define PRODUCT_URL         "https://github.com/rhshourav/HydraCast"
!define PRODUCT_EXE         "hydracast.exe"
!define PRODUCT_BG_EXE      "hydracast_bg.exe"
!define PRODUCT_GUARDIAN_EXE "hydracast_guardian.exe"
!define FFMPEG_EXE           "ffmpeg.exe"
!define FFPROBE_EXE          "ffprobe.exe"
!define MEDIAMTX_EXE         "mediamtx.exe"
!define PRODUCT_ICON        "dist\HydraCast\_internal\resources\HydraCast.ico"
!define UNINSTALLER_NAME    "Uninstall HydraCast.exe"
!define REG_KEY             "Software\Microsoft\Windows\CurrentVersion\Uninstall\HydraCast"
!define STARTUP_REG_KEY     "Software\Microsoft\Windows\CurrentVersion\Run"
!define MUTEX_NAME          "HydraCastInstallerMutex"

; -- Output -------------------------------------------------------------------
Name                "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile             "HydraCast-${PRODUCT_VERSION}-Setup.exe"
InstallDir          "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey    HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
ShowInstDetails     show
ShowUninstDetails   show

; -- MUI Configuration --------------------------------------------------------
!define MUI_ICON                          "${PRODUCT_ICON}"
!define MUI_UNICON                        "${PRODUCT_ICON}"
!define MUI_ABORTWARNING
!define MUI_ABORTWARNING_TEXT             "Are you sure you want to cancel the installation?"
!define MUI_WELCOMEPAGE_TITLE             "Welcome to HydraCast ${PRODUCT_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT              "This wizard will guide you through the installation of HydraCast, a multi-stream RTSP weekly scheduler.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN                "$INSTDIR\${PRODUCT_BG_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT           "Launch HydraCast in background (system tray)"
!define MUI_FINISHPAGE_LINK               "Visit HydraCast on GitHub"
!define MUI_FINISHPAGE_LINK_LOCATION      "${PRODUCT_URL}"

; -- Pages --------------------------------------------------------------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE             "dist\HydraCast\_internal\cryptography-48.0.0.dist-info\licenses\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
Page custom StartupPage StartupPageLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; -- Variables ----------------------------------------------------------------
Var StartupCheck      ; checkbox for "run at startup"
Var DesktopCheck      ; checkbox for "create desktop shortcut"
Var DoStartup         ; 1 = add startup entry
Var DoDesktop         ; 1 = create desktop shortcut

; -- Startup / Desktop options page -------------------------------------------
Function StartupPage
    !insertmacro MUI_HEADER_TEXT "Additional Options" "Choose extra installation options."
    nsDialogs::Create 1018
    Pop $0

    ${NSD_CreateLabel} 0 0 100% 20u "Select any additional options:"
    Pop $0

    ${NSD_CreateCheckbox} 10u 30u 100% 14u "Launch HydraCast automatically at Windows startup (background / tray mode)"
    Pop $StartupCheck
    ${NSD_SetState} $StartupCheck ${BST_CHECKED}   ; default: on

    ${NSD_CreateCheckbox} 10u 50u 100% 14u "Create Desktop shortcut"
    Pop $DesktopCheck
    ${NSD_SetState} $DesktopCheck ${BST_CHECKED}   ; default: on

    nsDialogs::Show
FunctionEnd

Function StartupPageLeave
    ${NSD_GetState} $StartupCheck $DoStartup
    ${NSD_GetState} $DesktopCheck $DoDesktop
FunctionEnd

; -- Prevent multiple installer instances -------------------------------------
Function .onInit
    System::Call 'kernel32::CreateMutexW(i 0, i 1, t "${MUTEX_NAME}") i .r0 ?e'
    Pop $1
    ${If} $1 = 183   ; ERROR_ALREADY_EXISTS
        MessageBox MB_OK|MB_ICONEXCLAMATION "The installer is already running."
        Abort
    ${EndIf}

    ; Warn if HydraCast is currently running
    FindWindow $0 "" "${PRODUCT_NAME}"
    ${If} $0 <> 0
        MessageBox MB_YESNO|MB_ICONQUESTION \
            "HydraCast appears to be running.$\r$\nIt is recommended to close it before installing.$\r$\n$\r$\nContinue anyway?" \
            IDYES +2
        Abort
    ${EndIf}
FunctionEnd

; -- Main install section -----------------------------------------------------
Section "HydraCast (required)" SecMain
    SectionIn RO   ; cannot be deselected

    SetOutPath "$INSTDIR"

    ; Copy all files from dist\HydraCast
    File /r "dist\HydraCast\*.*"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\${UNINSTALLER_NAME}"

    ; Registry: Add/Remove Programs entry
    WriteRegStr   HKLM "${REG_KEY}" "DisplayName"      "${PRODUCT_NAME} ${PRODUCT_VERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"   "${PRODUCT_VERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "Publisher"        "${PRODUCT_PUBLISHER}"
    WriteRegStr   HKLM "${REG_KEY}" "URLInfoAbout"     "${PRODUCT_URL}"
    WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   HKLM "${REG_KEY}" "UninstallString"  '"$INSTDIR\${UNINSTALLER_NAME}"'
    WriteRegStr   HKLM "${REG_KEY}" "QuietUninstallString" '"$INSTDIR\${UNINSTALLER_NAME}" /S'
    WriteRegStr   HKLM "${REG_KEY}" "DisplayIcon"      "$INSTDIR\_internal\resources\HydraCast.ico"
    WriteRegDWORD HKLM "${REG_KEY}" "NoModify"         1
    WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"         1

    ; Estimate installed size (in KB) - update if version changes
    WriteRegDWORD HKLM "${REG_KEY}" "EstimatedSize"    950000

    ; Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"

    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\HydraCast (TUI).lnk" \
        "$INSTDIR\${PRODUCT_EXE}" "" \
        "$INSTDIR\_internal\resources\HydraCast.ico" 0 \
        SW_SHOWNORMAL "" "HydraCast TUI - interactive console mode"

    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\HydraCast (Background).lnk" \
        "$INSTDIR\${PRODUCT_BG_EXE}" "" \
        "$INSTDIR\_internal\resources\HydraCast.ico" 0 \
        SW_SHOWNORMAL "" "HydraCast - background / system tray mode"

    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall HydraCast.lnk" \
        "$INSTDIR\${UNINSTALLER_NAME}" "" \
        "$INSTDIR\${UNINSTALLER_NAME}" 0

    ; Desktop shortcut (optional)
    ${If} $DoDesktop = ${BST_CHECKED}
        CreateShortcut "$DESKTOP\HydraCast.lnk" \
            "$INSTDIR\${PRODUCT_BG_EXE}" "" \
            "$INSTDIR\_internal\resources\HydraCast.ico" 0 \
            SW_SHOWNORMAL "" "HydraCast - background / system tray mode"
    ${EndIf}

    ; Startup registry entry - written to HKLM (machine-wide) AND HKCU (user).
    ; HKCU survives factory resets and reinstalls without needing admin rights.
    ; The tray icon menu manages HKCU at runtime after install.
    ${If} $DoStartup = ${BST_CHECKED}
        WriteRegStr HKLM "${STARTUP_REG_KEY}" "${PRODUCT_NAME}" \
            '"$INSTDIR\${PRODUCT_BG_EXE}"'
        WriteRegStr HKCU "${STARTUP_REG_KEY}" "${PRODUCT_NAME}" \
            '"$INSTDIR\${PRODUCT_BG_EXE}"'
    ${Else}
        DeleteRegValue HKLM "${STARTUP_REG_KEY}" "${PRODUCT_NAME}"
        DeleteRegValue HKCU "${STARTUP_REG_KEY}" "${PRODUCT_NAME}"
    ${EndIf}

SectionEnd

; -- Uninstaller --------------------------------------------------------------
Section "Uninstall"

    ; Kill ALL HydraCast-related processes before removing files.
    ; Order matters: kill child workers first, then supervisors.
    ; ffmpeg and mediamtx are spawned per-stream and must be killed
    ; explicitly — they are NOT children of the main EXE on Windows.
    ExecWait 'taskkill /F /IM "${FFMPEG_EXE}"'          $0
    ExecWait 'taskkill /F /IM "${FFPROBE_EXE}"'         $0
    ExecWait 'taskkill /F /IM "${MEDIAMTX_EXE}"'        $0
    ExecWait 'taskkill /F /IM "${PRODUCT_EXE}"'         $0
    ExecWait 'taskkill /F /IM "${PRODUCT_BG_EXE}"'      $0
    ExecWait 'taskkill /F /IM "${PRODUCT_GUARDIAN_EXE}"' $0
    Sleep 2000   ; give OS time to release all file handles

    ; Always remove guardian PID/lock files regardless of user-data choice.
    ; These are internal runtime artefacts, not user data, and must be
    ; cleaned up so a reinstall does not pick up a stale guardian PID.
    Delete "$INSTDIR\logs\guardian.pid"
    Delete "$INSTDIR\logs\guardian_self.pid"
    Delete "$INSTDIR\logs\guardian.log"
    Delete "$INSTDIR\logs\guardian.log.1"
    Delete "$INSTDIR\logs\guardian.log.2"
    Delete "$INSTDIR\logs\guardian.log.3"
    Delete "$INSTDIR\logs\guardian.log.4"
    Delete "$INSTDIR\logs\guardian.log.5"

    ; Ask whether to keep user data (config, logs, media)
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "Do you want to keep your configuration, logs, and media files?$\r$\n$\r$\n\
Click YES to keep them (config\, logs\, media\ folders).$\r$\n\
Click NO to delete everything." \
        IDYES KeepUserData

    ; Remove user data too
    RMDir /r "$INSTDIR\config"
    RMDir /r "$INSTDIR\logs"
    RMDir /r "$INSTDIR\media"
    RMDir /r "$INSTDIR\ssl"

    KeepUserData:

    ; Remove installed program files (but not user-data folders above
    ; if the user chose to keep them)
    RMDir /r "$INSTDIR\_internal"
    Delete   "$INSTDIR\${PRODUCT_EXE}"
    Delete   "$INSTDIR\${PRODUCT_BG_EXE}"
    Delete   "$INSTDIR\${UNINSTALLER_NAME}"

    ; Remove bin\ but not user-added binaries
    RMDir /r "$INSTDIR\bin"

    ; Try to remove install dir itself (succeeds only if empty)
    RMDir "$INSTDIR"

    ; Remove shortcuts
    RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
    Delete    "$DESKTOP\HydraCast.lnk"

    ; Remove registry entries
    DeleteRegKey   HKLM "${REG_KEY}"
    DeleteRegValue HKLM "${STARTUP_REG_KEY}" "${PRODUCT_NAME}"
    DeleteRegValue HKCU "${STARTUP_REG_KEY}" "${PRODUCT_NAME}"

SectionEnd
