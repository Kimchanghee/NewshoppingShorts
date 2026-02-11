; SSMaker Inno Setup Installer Script
; Builds a Windows installer from the PyInstaller onedir output.
;
; Usage:
;   iscc /DMyAppVersion=1.3.31 installer.iss
;
; Update behavior:
;   - AppId is a FIXED GUID shared across all versions.
;   - On first install, Inno Setup writes the install path to the Windows registry:
;       HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{AppId}_is1
;   - On subsequent installs (updates), Inno Setup reads this registry key
;     to find the EXISTING install directory and overwrites files in place.
;   - Silent install (/VERYSILENT) never prompts for a directory; it always
;     uses the previously registered path.

#ifndef MyAppVersion
  #define MyAppVersion "1.3.31"
#endif

#define MyAppName "SSMaker"
#define MyAppExeName "ssmaker.exe"
#define MyAppPublisher "SSMaker"

[Setup]
; CRITICAL: This AppId MUST remain the same across ALL versions.
; It is how Inno Setup identifies the existing installation and its path.
; Changing this would create a separate installation instead of updating.
AppId={{B8F2A7C1-3D4E-5F60-A1B2-C3D4E5F6A7B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Default install path for NEW installs only.
; For UPDATES, the path is read from the registry automatically.
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Refuse to downgrade
MinVersion=10.0
; If previous install exists, Inno Setup automatically uses its directory via AppId (default behavior).
; Output
OutputDir=dist
OutputBaseFilename=SSMaker_Setup_v{#MyAppVersion}
; Compression
Compression=lzma2
SolidCompression=yes
; UI
SetupIconFile=resource\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
; Privileges - user-level install (no admin required, like VS Code/Chrome)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Update support - force-close running instances during silent update
CloseApplications=force
CloseApplicationsFilter=ssmaker.exe
RestartApplications=no
; Version info for Add/Remove Programs
AppVerName={#MyAppName} v{#MyAppVersion}
VersionInfoVersion={#MyAppVersion}.0
UninstallDisplayName={#MyAppName}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Install ALL files from the PyInstaller onedir output.
; This includes: ssmaker.exe, all Python packages, DLLs, fonts, tesseract,
; whisper models, ffmpeg, resource files, version.json, etc.
; The 'ignoreversion' flag ensures files are always overwritten during updates.
Source: "dist\ssmaker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} 제거"; Filename: "{uninstallexe}"
; Desktop (if user selected the task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Interactive install: user chooses whether to launch via checkbox
Filename: "{app}\{#MyAppExeName}"; Description: "SSMaker 실행"; Flags: nowait postinstall skipifsilent
; Silent install (auto-update): always restart the app after files are replaced
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent

[UninstallDelete]
; Clean up runtime-generated files on uninstall
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"
