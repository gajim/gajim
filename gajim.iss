; -- Example1.iss --
; Demonstrates copying 3 files and creating an icon.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=Gajim
AppVerName=Gajim version 0.8.1
DefaultDirName={pf}\Gajim
DefaultGroupName=Gajim
UninstallDisplayIcon={app}\src\Gajim.exe
Compression=lzma
SolidCompression=yes

[Components]
Name: "main"; Description: "Main Files"; Types: full compact custom; Flags: fixed

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Components: main

[Files]
Source: "dist\*.pyd"; DestDir: "{app}\src"
Source: "dist\*.dll"; DestDir: "{app}\src"
Source: "dist\*.zip"; DestDir: "{app}\src"
Source: "COPYING"; DestDir: "{app}"
Source: "dist\gajim.exe"; DestDir: "{app}\src"; components: main
Source: "dist\*.glade"; DestDir: "{app}\src"
Source: "data\*"; DestDir: "{app}\data"; Flags: recursesubdirs
Source: "po\*"; DestDir: "{app}\po"; Flags: recursesubdirs

[Icons]
Name: "{group}\Gajim"; Filename: "{app}\src\Gajim.exe"; WorkingDir: "{app}\src"
Name: "{group}\Uninstall Gajim"; Filename: "{app}\unins000.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Gajim"; Filename: "{app}\src\gajim.exe"; WorkingDir: "{app}\src"; IconFilename: "{app}\data\pixmaps\gajim.ico"; Components: main; Tasks: desktopicon

[Run]
Filename: "{app}\src\gajim.exe"; Description: "Launch application"; Flags: postinstall nowait skipifsilent
