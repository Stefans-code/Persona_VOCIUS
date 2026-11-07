; Installer Windows di Vocius (Inno Setup 6). Prende la cartella dist\Vocius prodotta da
; PyInstaller con vocius_persona_windows.spec. I modelli vocali si scaricano dall'app al primo uso.
#define AppVer GetEnv("VOCIUS_VERSION")
#if AppVer == ""
  #define AppVer "1.0.2"
#endif

[Setup]
AppId={{6F3B8C2E-9A41-4D7B-B2E5-1C0A7E4D9F31}
AppName=Vocius
AppVersion={#AppVer}
AppPublisher=Nexflamma
AppPublisherURL=https://nexflamma.net
AppSupportURL=https://nexflamma.net
AppCopyright=© 2026 Nexflamma
DefaultDirName={autopf}\Vocius
DefaultGroupName=Vocius
DisableProgramGroupPage=yes
LicenseFile=license_installer.txt
OutputDir=installer_out
OutputBaseFilename=Vocius_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\Vocius.exe
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Vocius\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Vocius"; Filename: "{app}\Vocius.exe"
Name: "{autodesktop}\Vocius"; Filename: "{app}\Vocius.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Vocius.exe"; Description: "{cm:LaunchProgram,Vocius}"; Flags: nowait postinstall skipifsilent
