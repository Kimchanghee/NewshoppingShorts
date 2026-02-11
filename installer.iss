; SSMaker Inno Setup Installer Script
; Builds a Windows installer from the PyInstaller onedir output.
;
; Usage:
;   iscc /DMyAppVersion=1.3.31 installer.iss

#ifndef MyAppVersion
  #define MyAppVersion "1.3.31"
#endif

#define MyAppName "SSMaker"
#define MyAppExeName "ssmaker.exe"
#define MyAppPublisher "SSMaker"

[Setup]
AppId={{B8F2A7C1-3D4E-5F60-A1B2-C3D4E5F6A7B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
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
CloseApplicationsFilter=*.exe
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
; Install everything from the PyInstaller onedir output
Source: "dist\ssmaker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} 제거"; Filename: "{uninstallexe}"
; Desktop (if user selected the task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Interactive install: user chooses whether to launch
Filename: "{app}\{#MyAppExeName}"; Description: "SSMaker 실행"; Flags: nowait postinstall skipifsilent
; Silent install (auto-update): always launch after install
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent

[UninstallDelete]
; Clean up logs and cache on uninstall
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"
