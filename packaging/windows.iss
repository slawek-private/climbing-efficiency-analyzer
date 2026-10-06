; Inno Setup script. packaging/build.py passes /DVersion, /DSource and /DOutput.
[Setup]
AppId={{6F1C3E52-7B0A-4C35-9E7E-2C1B7C0D5A11}
AppName=Climb Studio
AppVersion={#Version}
AppPublisher=Slawomir Babicz
AppPublisherURL=https://github.com/slawek-private/climbing-efficiency-analyzer
DefaultDirName={autopf}\Climb Studio
DefaultGroupName=Climb Studio
; Per-user install by default, no administrator prompt; users may choose all-users.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#Output}
OutputBaseFilename=Climb-Studio-{#Version}-Windows-x64-setup
UninstallDisplayIcon={app}\Climb Studio.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Close a running Climb Studio during in-app updates instead of asking.
CloseApplications=force
LicenseFile=..\LICENSE
SetupIconFile=icon.ico

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Source}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Climb Studio"; Filename: "{app}\Climb Studio.exe"
Name: "{group}\Uninstall Climb Studio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Climb Studio"; Filename: "{app}\Climb Studio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Climb Studio.exe"; Description: "{cm:LaunchProgram,Climb Studio}"; Flags: nowait postinstall skipifsilent
; In-app updates run Setup silently with /relaunch=1 and reopen the app afterwards.
Filename: "{app}\Climb Studio.exe"; Flags: nowait runasoriginaluser; Check: Relaunch

[Code]
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
