#define AppName "Esyy B1Connector"
#define AppPublisher "Esyy"
#define AppURL "http://127.0.0.1:8010/login"

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#ifndef SourceRoot
  #define SourceRoot ".."
#endif

#ifndef OutputRoot
  #define OutputRoot SourceRoot + "\dist\installer"
#endif

[Setup]
AppId={{A0A63FE8-0B98-4A9A-9445-18A0A654BA3A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL={#AppURL}
SetupIconFile={#SourceRoot}\assets\esyy_b1connector.ico
UninstallDisplayIcon={app}\assets\esyy_b1connector.ico
DefaultDirName={autopf}\Esyy\B1Connector
DefaultGroupName={#AppName}
DisableProgramGroupPage=no
OutputDir={#OutputRoot}
OutputBaseFilename=Esyy_B1Connector_Setup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
SetupLogging=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea collegamento sul desktop"; Flags: unchecked
Name: "autostartsystem"; Description: "Abilita avvio automatico (SYSTEM, consigliato)"; Flags: checkedonce exclusive
Name: "autostartcurrentuser"; Description: "Abilita avvio automatico (utente corrente)"; Flags: unchecked exclusive

[Dirs]
Name: "{app}\logs"

[Files]
Source: "{#SourceRoot}\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourceRoot}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\run_prod.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\run_prod.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\run_dev.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\setup_windows.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\install_autostart_task.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\uninstall_autostart_task.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\install_client.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\assets\esyy_b1connector.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\Apri Esyy B1Connector"; Filename: "{cmd}"; Parameters: "/c start """" ""http://127.0.0.1:8010/login"""; IconFilename: "{app}\assets\esyy_b1connector.ico"
Name: "{group}\Riavvia Servizio Esyy B1Connector"; Filename: "{cmd}"; Parameters: "/c schtasks /End /TN EsyyB1Connector & schtasks /Run /TN EsyyB1Connector"; IconFilename: "{app}\assets\esyy_b1connector.ico"
Name: "{group}\Disinstalla avvio automatico"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\uninstall_autostart_task.ps1"" -TaskName ""EsyyB1Connector"""; IconFilename: "{app}\assets\esyy_b1connector.ico"
Name: "{group}\Disinstalla {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Esyy B1Connector"; Filename: "{cmd}"; Parameters: "/c start """" ""http://127.0.0.1:8010/login"""; IconFilename: "{app}\assets\esyy_b1connector.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\setup_windows.ps1"" -InstallDeps -TaskName ""EsyyB1Connector"" -HostName 127.0.0.1 -Port 8010"; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install_autostart_task.ps1"" -TaskName ""EsyyB1Connector"" -HostName 127.0.0.1 -Port 8010"; Flags: runhidden waituntilterminated; Tasks: autostartsystem
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install_autostart_task.ps1"" -TaskName ""EsyyB1Connector"" -HostName 127.0.0.1 -Port 8010 -UseCurrentUser"; Flags: runhidden waituntilterminated; Tasks: autostartcurrentuser
Filename: "{cmd}"; Parameters: "/c start """" ""http://127.0.0.1:8010/login"""; Description: "Apri Esyy B1Connector nel browser"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\uninstall_autostart_task.ps1"" -TaskName ""EsyyB1Connector"""; Flags: runhidden waituntilterminated
