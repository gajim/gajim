; -- Example1.iss --
; Demonstrates copying 3 files and creating an icon.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=Gajim
AppVerName=Gajim version 0.7.1
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
Source: "*.ico"; DestDir: "{app}"
Source: "dist\*.glade"; DestDir: "{app}\src"
Source: "data\iconsets\sun\*"; DestDir: "{app}\data\iconsets\sun"
Source: "data\iconsets\stellar\*"; DestDir: "{app}\data\iconsets\stellar"
Source: "data\iconsets\gossip\*"; DestDir: "{app}\data\iconsets\gossip"
Source: "data\iconsets\transports\aim\*"; DestDir: "{app}\data\iconsets\transports\aim"
Source: "data\iconsets\transports\gadugadu\*"; DestDir: "{app}\data\iconsets\transports\gadugadu"
Source: "data\iconsets\transports\icq\*"; DestDir: "{app}\data\iconsets\transports\icq"
Source: "data\iconsets\transports\msn\*"; DestDir: "{app}\data\iconsets\transports\msn"
Source: "data\iconsets\transports\yahoo\*"; DestDir: "{app}\data\iconsets\transports\yahoo"
Source: "data\emoticons\*"; DestDir: "{app}\data\emoticons"
Source: "data\pixmaps\*"; DestDir: "{app}\data\pixmaps"
Source: "data\sounds\*"; DestDir: "{app}\data\sounds"

[Icons]
Name: "{group}\Gajim"; Filename: "{app}\src\Gajim.exe"; WorkingDir: "{app}\src"; IconFilename: "{app}\gajim.ico"
Name: "{userdesktop}\Gajim"; Filename: "{app}\src\gajim.exe"; WorkingDir: "{app}\src"; IconFilename: "{app}\gajim.ico"; Components: main; Tasks: desktopicon

[Run]
Filename: "{app}\src\gajim.exe"; Description: "Launch application"; Flags: postinstall nowait skipifsilent
