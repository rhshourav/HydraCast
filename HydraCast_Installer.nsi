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
;    - Start Menu shortcut group
;    - Optional "Launch at Windows startup" checkbox
;    - Desktop shortcut (optional)
;    - Full uninstaller registered in Add/Remove Programs
;    - Silent install support  (/S flag)
;
;  v5.5 changes
;  -------------
;  hydracast_bg.exe fully removed -- unified into hydracast.exe.
;  Single-instance mutex prevents double-launch without UAC on restart.
;  Guardian restarts never trigger UAC (inherits elevated token).
; ============================================================================

; -- Compression --------------------------------------------------------------
SetCompressor /SOLID lzma
SetCompressorDictSize 64

; -- Includes -----------------------------------------------------------------
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"

; -- Product metadata ---------------------------------------------------------
!define PRODUCT_NAME         "HydraCast"
!define PRODUCT_VERSION      "6.5.0"
!define PRODUCT_PUBLISHER    "rhshourav"
!define PRODUCT_URL          "https://github.com/rhshourav/HydraCast"
!define PRODUCT_EXE          "hydracast.exe"
!define PRODUCT_GUARDIAN_EXE "hydracast_guardian.exe"
!define FFMPEG_EXE           "ffmpeg.exe"
!define FFPROBE_EXE          "ffprobe.exe"
!define MEDIAMTX_EXE         "mediamtx.exe"
!define PRODUCT_ICON         "dist\HydraCast\_internal\resources\HydraCast.ico"
!define UNINSTALLER_NAME     "Uninstall HydraCast.exe"
!define REG_KEY              "Software\Microsoft\Windows\CurrentVersion\Uninstall\HydraCast"
!define STARTUP_REG_KEY      "Software\Microsoft\Windows\CurrentVersion\Run"
!define MUTEX_NAME           "HydraCastInstallerMutex"

; -- Output -------------------------------------------------------------------
Name                "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile             "HydraCast-${PRODUCT_VERSION}-Setup.exe"
InstallDir          "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey    HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
ShowInstDetails     show
ShowUninstDetails   show

; -- MUI Configuration --------------------------------------------------------
!define MUI_ICON                     "${PRODUCT_ICON}"
!define MUI_UNICON                   "${PRODUCT_ICON}"
!define MUI_ABORTWARNING
!define MUI_ABORTWARNING_TEXT        "Are you sure you want to cancel the installation?"
!define MUI_WELCOMEPAGE_TITLE        "Welcome to HydraCast ${PRODUCT_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT         "This wizard will guide you through the installation of HydraCast, a multi-stream RTSP weekly scheduler.$\r$\n$\r$\nClick Next to continue."

; Finish page launches hydracast.exe -- opens TUI and tray icon immediately.
!define MUI_FINISHPAGE_RUN           "$INSTDIR\${PRODUCT_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT      "Launch HydraCast"
!define MUI_FINISHPAGE_LINK          "Visit HydraCast on GitHub"
!define MUI_FINISHPAGE_LINK_LOCATION "${PRODUCT_URL}"

; -- Pages --------------------------------------------------------------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE        "dist\HydraCast\_internal\cryptography-48.0.0.dist-info\licenses\LICENSE"
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
Var StartupCheck
Var DesktopCheck
Var DoStartup
Var DoDesktop

; -- Options page -------------------------------------------------------------
Function StartupPage
    !insertmacro MUI_HEADER_TEXT "Additional Options" "Choose extra installation options."
    nsDialogs::Create 1018
    Pop $0

    ${NSD_CreateLabel} 0 0 100% 20u "Select any additional options:"
    Pop $0

    ${NSD_CreateCheckbox} 10u 30u 100% 14u "Launch HydraCast automatically at Windows startup"
    Pop $StartupCheck
    ${NSD_SetState} $StartupCheck ${BST_CHECKED}

    ${NSD_CreateCheckbox} 10u 50u 100% 14u "Create Desktop shortcut"
    Pop $DesktopCheck
    ${NSD_SetState} $DesktopCheck ${BST_CHECKED}

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
    ${If} $1 = 183
        MessageBox MB_OK|MB_ICONEXCLAMATION "The installer is already running."
        Abort
    ${EndIf}

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
    SectionIn RO

    SetOutPath "$INSTDIR"
    File /r "dist\HydraCast\*.*"

    WriteUninstaller "$INSTDIR\${UNINSTALLER_NAME}"

    ; Add/Remove Programs
    WriteRegStr   HKLM "${REG_KEY}" "DisplayName"          "${PRODUCT_NAME} ${PRODUCT_VERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"       "${PRODUCT_VERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "Publisher"            "${PRODUCT_PUBLISHER}"
    WriteRegStr   HKLM "${REG_KEY}" "URLInfoAbout"         "${PRODUCT_URL}"
    WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"      "$INSTDIR"
    WriteRegStr   HKLM "${REG_KEY}" "UninstallString"      '"$INSTDIR\${UNINSTALLER_NAME}"'
    WriteRegStr   HKLM "${REG_KEY}" "QuietUninstallString" '"$INSTDIR\${UNINSTALLER_NAME}" /S'
    WriteRegStr   HKLM "${REG_KEY}" "DisplayIcon"          "$INSTDIR\_internal\resources\HydraCast.ico"
    WriteRegDWORD HKLM "${REG_KEY}" "NoModify"             1
    WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"             1
    WriteRegDWORD HKLM "${REG_KEY}" "EstimatedSize"        950000

    ; Start Menu -- single shortcut (TUI opens + tray is always visible)
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"

    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\HydraCast.lnk" \
        "$INSTDIR\${PRODUCT_EXE}" "" \
        "$INSTDIR\_internal\resources\HydraCast.ico" 0 \
        SW_SHOWNORMAL "" "HydraCast -- RTSP multi-stream scheduler"

    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall HydraCast.lnk" \
        "$INSTDIR\${UNINSTALLER_NAME}" "" \
        "$INSTDIR\${UNINSTALLER_NAME}" 0

    ; Desktop shortcut (optional)
    ${If} $DoDesktop = ${BST_CHECKED}
        CreateShortcut "$DESKTOP\HydraCast.lnk" \
            "$INSTDIR\${PRODUCT_EXE}" "" \
            "$INSTDIR\_internal\resources\HydraCast.ico" 0 \
            SW_SHOWNORMAL "" "HydraCast -- RTSP multi-stream scheduler"
    ${EndIf}

    ; Startup registry -- HKCU only (no admin needed at runtime)
    ; Points to hydracast.exe (unified TUI+tray, no separate bg exe).
    ${If} $DoStartup = ${BST_CHECKED}
        WriteRegStr HKCU "${STARTUP_REG_KEY}" "${PRODUCT_NAME}" \
            '"$INSTDIR\${PRODUCT_EXE}"'
    ${Else}
        DeleteRegValue HKCU "${STARTUP_REG_KEY}" "${PRODUCT_NAME}"
    ${EndIf}

SectionEnd

; -- Uninstaller --------------------------------------------------------------
Section "Uninstall"

    ; Kill processes -- workers first, then supervisors.
    ExecWait 'taskkill /F /IM "${FFMPEG_EXE}"'           $0
    ExecWait 'taskkill /F /IM "${FFPROBE_EXE}"'          $0
    ExecWait 'taskkill /F /IM "${MEDIAMTX_EXE}"'         $0
    ExecWait 'taskkill /F /IM "${PRODUCT_EXE}"'          $0
    ExecWait 'taskkill /F /IM "${PRODUCT_GUARDIAN_EXE}"' $0
    Sleep 2000

    ; Remove internal guardian runtime files (not user data).
    Delete "$INSTDIR\logs\guardian.pid"
    Delete "$INSTDIR\logs\guardian_self.pid"
    Delete "$INSTDIR\logs\guardian.log"
    Delete "$INSTDIR\logs\guardian.log.1"
    Delete "$INSTDIR\logs\guardian.log.2"
    Delete "$INSTDIR\logs\guardian.log.3"
    Delete "$INSTDIR\logs\guardian.log.4"
    Delete "$INSTDIR\logs\guardian.log.5"

    ; Ask whether to keep user data (config, logs, media).
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "Do you want to keep your configuration, logs, and media files?$\r$\n$\r$\nYES = keep config, logs, media folders.$\r$\nNO  = delete everything." \
        IDYES KeepUserData

    RMDir /r "$INSTDIR\config"
    RMDir /r "$INSTDIR\logs"
    RMDir /r "$INSTDIR\media"
    RMDir /r "$INSTDIR\ssl"

    KeepUserData:

    RMDir /r "$INSTDIR\_internal"
    Delete   "$INSTDIR\${PRODUCT_EXE}"
    Delete   "$INSTDIR\${PRODUCT_GUARDIAN_EXE}"
    Delete   "$INSTDIR\${UNINSTALLER_NAME}"
    RMDir /r "$INSTDIR\bin"
    RMDir    "$INSTDIR"

    RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
    Delete   "$DESKTOP\HydraCast.lnk"

    DeleteRegKey   HKLM "${REG_KEY}"
    DeleteRegValue HKCU "${STARTUP_REG_KEY}" "${PRODUCT_NAME}"

SectionEnd
