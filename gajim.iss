; -- Example1.iss --
; Demonstrates copying 3 files and creating an icon.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=Gajim
AppVerName=Gajim version 0.6
DefaultDirName={pf}\Gajim
DefaultGroupName=Gajim
UninstallDisplayIcon={app}\Gajim.exe
Compression=lzma
SolidCompression=yes

[Components]
Name: "main"; Description: "Main Files"; Types: full compact custom; Flags: fixed

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Components: main

[Files]
Source: "dist\*.pyd"; DestDir: "{app}"
Source: "dist\*.dll"; DestDir: "{app}"
Source: "dist\*.zip"; DestDir: "{app}"
Source: "dist\gajim.exe"; DestDir: "{app}"; components: main
Source: "*.ico"; DestDir: "{app}"
Source: "dist\plugins\gtkgui\*.glade"; DestDir: "{app}\plugins\gtkgui"
Source: "dist\plugins\gtkgui\icons\sun\*"; DestDir: "{app}\plugins\gtkgui\icons\sun"
Source: "dist\plugins\gtkgui\emoticons\*"; DestDir: "{app}\plugins\gtkgui\emoticons"
Source: "dist\plugins\gtkgui\pixmaps\*"; DestDir: "{app}\plugins\gtkgui\pixmaps"
Source: "dist\sounds\*"; DestDir: "{app}\sounds"

[Icons]
Name: "{group}\Gajim"; Filename: "{app}\Gajim.exe"; WorkingDir: "{app}"; IconFilename: "{app}\gajim.ico"
Name: "{userdesktop}\Gajim"; Filename: "{app}\gajim.exe"; WorkingDir: "{app}"; IconFilename: "{app}\gajim.ico"; Components: main; Tasks: desktopicon

[Run]
Filename: "{app}\gajim.exe"; Description: "Launch application"; Flags: postinstall nowait skipifsilent
