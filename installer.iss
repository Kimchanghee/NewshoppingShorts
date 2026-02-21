; SSMaker Inno Setup Installer Script
; Builds a Windows installer from the PyInstaller onedir output.
;
; Usage:
;   iscc /DMyAppVersion=1.3.31 installer.iss
;   iscc /DMyAppVersion=1.3.31 /DForceSilentReinstall=1 installer.iss
;
; Update behavior:
;   - AppId is a FIXED GUID shared across all versions.
;   - On first install, Inno Setup writes the install path to the Windows registry:
;       HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{AppId}_is1
;   - On subsequent installs (updates), Inno Setup reads this registry key
;     to find the EXISTING install directory and overwrites files in place.
;   - Silent install (/VERYSILENT) never prompts for a directory; it always
;     uses the previously registered path.
;   - Silent updates default to in-place overwrite (no uninstall).
;     Set ForceSilentReinstall=1 at build time to force old-version uninstall.

#ifndef MyAppVersion
  #define MyAppVersion "1.4.18"
#endif

#ifndef ForceSilentReinstall
  #define ForceSilentReinstall 0
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
; Code signing (Authenticode) - reduces SmartScreen warnings and prevents tampering.
; To enable: install a code signing certificate and configure signtool path below.
; Usage:  iscc /DMyAppVersion=1.3.33 /DSignToolAvailable installer.iss
;
; SignTool expects signtool.exe in PATH (Windows SDK) or set SIGNTOOL_PATH env var.
; Certificate can be specified via SIGN_CERT_THUMBPRINT env var.
#ifdef SignToolAvailable
SignTool=signtool sign /fd sha256 /tr https://timestamp.digicert.com /td sha256 /sha1 {#GetEnv("SIGN_CERT_THUMBPRINT")} $f
SignedUninstaller=yes
#endif

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
Name: "{group}\{#MyAppName} Uninstall"; Filename: "{uninstallexe}"
; Desktop (if user selected the task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Interactive install: user chooses whether to launch via checkbox
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SSMaker"; Flags: nowait postinstall skipifsilent
; Silent install (auto-update): always restart the app after files are replaced
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent

[InstallDelete]
; Remove stale binary-extension residues before copying new files.
; This prevents ABI mismatch crashes after in-place updates (e.g., numpy cp311/cp313 leftovers).
Type: files; Name: "{app}\*.pyd"
Type: files; Name: "{app}\python3*.dll"
Type: filesandordirs; Name: "{app}\numpy"
Type: filesandordirs; Name: "{app}\numpy.libs"
Type: filesandordirs; Name: "{app}\numpy-*.dist-info"
Type: filesandordirs; Name: "{app}\scipy"
Type: filesandordirs; Name: "{app}\scipy.libs"
Type: filesandordirs; Name: "{app}\scipy-*.dist-info"
Type: filesandordirs; Name: "{app}\cv2"
Type: filesandordirs; Name: "{app}\opencv_python-*.dist-info"
Type: filesandordirs; Name: "{app}\av"
Type: filesandordirs; Name: "{app}\av.libs"
Type: filesandordirs; Name: "{app}\av-*.dist-info"
Type: filesandordirs; Name: "{app}\tokenizers"
Type: filesandordirs; Name: "{app}\tokenizers-*.dist-info"

[UninstallDelete]
; Clean up runtime-generated files on uninstall
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"
; Remove possible stale Python binary/runtime residues too.
Type: files; Name: "{app}\*.pyd"
Type: files; Name: "{app}\python3*.dll"
Type: filesandordirs; Name: "{app}\numpy"
Type: filesandordirs; Name: "{app}\numpy.libs"
Type: filesandordirs; Name: "{app}\numpy-*.dist-info"
Type: filesandordirs; Name: "{app}\scipy"
Type: filesandordirs; Name: "{app}\scipy.libs"
Type: filesandordirs; Name: "{app}\scipy-*.dist-info"
Type: filesandordirs; Name: "{app}\cv2"
Type: filesandordirs; Name: "{app}\opencv_python-*.dist-info"
Type: filesandordirs; Name: "{app}\av"
Type: filesandordirs; Name: "{app}\av.libs"
Type: filesandordirs; Name: "{app}\av-*.dist-info"
Type: filesandordirs; Name: "{app}\tokenizers"
Type: filesandordirs; Name: "{app}\tokenizers-*.dist-info"

[Code]
const
  AppUninstallRegKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{B8F2A7C1-3D4E-5F60-A1B2-C3D4E5F6A7B8}_is1';

var
  ExistingInstallDetected: Boolean;
  ExistingInstallDir: string;
  ExistingUninstallCmd: string;
  ExistingQuietUninstallCmd: string;
  InstallModePage: TInputOptionWizardPage;

function ReadUninstallRegValue(const ValueName: string; var Value: string): Boolean;
begin
  Result :=
    RegQueryStringValue(HKCU, AppUninstallRegKey, ValueName, Value) or
    RegQueryStringValue(HKLM, AppUninstallRegKey, ValueName, Value);
end;

function DetectExistingInstall(): Boolean;
begin
  ExistingInstallDir := '';
  ExistingUninstallCmd := '';
  ExistingQuietUninstallCmd := '';

  ReadUninstallRegValue('InstallLocation', ExistingInstallDir);
  ReadUninstallRegValue('UninstallString', ExistingUninstallCmd);
  ReadUninstallRegValue('QuietUninstallString', ExistingQuietUninstallCmd);

  ExistingInstallDir := Trim(ExistingInstallDir);
  ExistingUninstallCmd := Trim(ExistingUninstallCmd);
  ExistingQuietUninstallCmd := Trim(ExistingQuietUninstallCmd);

  Result := (ExistingInstallDir <> '') or
            (ExistingUninstallCmd <> '') or
            (ExistingQuietUninstallCmd <> '');
end;

function SplitCommandLine(const CommandLine: string; var ExeFile, Params: string): Boolean;
var
  S: string;
  I: Integer;
begin
  S := Trim(CommandLine);
  ExeFile := '';
  Params := '';

  if S = '' then
  begin
    Result := False;
    exit;
  end;

  if S[1] = '"' then
  begin
    Delete(S, 1, 1);
    I := Pos('"', S);
    if I <= 0 then
    begin
      Result := False;
      exit;
    end;

    ExeFile := Copy(S, 1, I - 1);
    Params := Trim(Copy(S, I + 1, MaxInt));
  end
  else
  begin
    I := Pos(' ', S);
    if I <= 0 then
      ExeFile := S
    else
    begin
      ExeFile := Copy(S, 1, I - 1);
      Params := Trim(Copy(S, I + 1, MaxInt));
    end;
  end;

  Result := Trim(ExeFile) <> '';
end;

function IsReinstallSelected(): Boolean;
begin
  Result :=
    ExistingInstallDetected and
    Assigned(InstallModePage) and
    InstallModePage.Values[1];
end;

function BuildUninstallParams(const BaseParams: string): string;
var
  U: string;
begin
  U := Uppercase(BaseParams);
  Result := Trim(BaseParams);

  if (Pos('/SILENT', U) = 0) and (Pos('/VERYSILENT', U) = 0) then
    Result := Trim(Result + ' /VERYSILENT');
  if Pos('/SUPPRESSMSGBOXES', U) = 0 then
    Result := Trim(Result + ' /SUPPRESSMSGBOXES');
  if Pos('/NORESTART', U) = 0 then
    Result := Trim(Result + ' /NORESTART');
end;

function RunExistingUninstaller(var ExitCode: Integer): Boolean;
var
  CommandLine: string;
  ExeFile: string;
  Params: string;
begin
  Result := False;
  ExitCode := 0;

  if ExistingQuietUninstallCmd <> '' then
    CommandLine := ExistingQuietUninstallCmd
  else
    CommandLine := ExistingUninstallCmd;

  if not SplitCommandLine(CommandLine, ExeFile, Params) then
  begin
    Log('Reinstall requested but uninstall command could not be parsed.');
    exit;
  end;

  Params := BuildUninstallParams(Params);
  Log(Format('Running previous uninstaller: %s %s', [ExeFile, Params]));

  Result := Exec(ExeFile, Params, '', SW_HIDE, ewWaitUntilTerminated, ExitCode);
end;

procedure InitializeWizard();
begin
  ExistingInstallDetected := DetectExistingInstall();

  if not ExistingInstallDetected then
    exit;

  InstallModePage := CreateInputOptionPage(
    wpSelectDir,
    'Existing installation detected',
    'Choose install mode',
    'SSMaker appears to already be installed on this PC.'#13#10 +
    'Choose one mode below:'#13#10 +
    '- Update (recommended): overwrite app files in place.'#13#10 +
    '- Reinstall: remove previous version first, then install fresh.',
    True,
    False
  );
  InstallModePage.Add('Update in place (recommended)');
  InstallModePage.Add('Reinstall (remove previous version, then install)');
  InstallModePage.Values[0] := True;

  if ExistingInstallDir <> '' then
  begin
    WizardForm.DirEdit.Text := ExistingInstallDir;
    Log('Existing install directory detected: ' + ExistingInstallDir);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if Assigned(InstallModePage) and (CurPageID = InstallModePage.ID) and IsReinstallSelected() then
  begin
    Result :=
      MsgBox(
        'Reinstall will uninstall the existing SSMaker first.'#13#10 +
        'User data outside the install directory is preserved.'#13#10#13#10 +
        'Continue?',
        mbConfirmation,
        MB_YESNO
      ) = IDYES;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): string;
var
  ExitCode: Integer;
  Ok: Boolean;
begin
  Result := '';

  if not ExistingInstallDetected then
    exit;

  if not IsReinstallSelected() then
  begin
    if WizardSilent then
    begin
      #if ForceSilentReinstall
      Log('Silent update detected: forcing clean reinstall via previous uninstaller.');
      #else
      Log('Silent update detected: using in-place update mode (no uninstall).');
      exit;
      #endif
    end
    else
      exit;
  end;

  Ok := RunExistingUninstaller(ExitCode);
  if not Ok then
  begin
    if WizardSilent then
    begin
      Log('Silent reinstall fallback: previous uninstaller launch failed, continuing with in-place update.');
      exit;
    end;
    Result :=
      'Failed to launch the previous uninstaller. ' +
      'Please uninstall SSMaker manually and run setup again.';
    exit;
  end;

  if ExitCode <> 0 then
  begin
    if WizardSilent then
    begin
      Log('Silent reinstall fallback: previous uninstaller failed, continuing with in-place update.');
      exit;
    end;
    Result :=
      'Previous uninstall failed with exit code ' + IntToStr(ExitCode) + '. ' +
      'Please uninstall SSMaker manually and run setup again.';
    exit;
  end;
end;
