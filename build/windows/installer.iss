#define MyAppName "YouTube Downloader"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "amirhnfarahani"
#define MyAppExeName "YouTubeDownloader.exe"

[Setup]
AppId={{8D5B8C8E-8D9A-4E3A-BE45-8C9E6A9F2D11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\YouTube Downloader
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=YouTubeDownloader-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayName={#MyAppName}

[Files]
Source: "dist\YouTubeDownloader.exe"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\downloads"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "اجرای YouTube Downloader"; Flags: nowait postinstall skipifsilent
