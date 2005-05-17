; -- Example1.iss --
; Demonstrates copying 3 files and creating an icon.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=Gajim
AppVerName=Gajim version 0.7
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
Source: "dist\*.glade"; DestDir: "{app}"
Source: "dist\data\iconsets\sun\*"; DestDir: "{app}\data\iconsets\sun"
Source: "dist\data\iconsets\stellar\*"; DestDir: "{app}\data\iconsets\stellar"
Source: "dist\data\iconsets\gossip\*"; DestDir: "{app}\data\iconsets\gossip"
Source: "dist\data\iconsets\transports\aim\*"; DestDir: "{app}\data\iconsets\transports\aim"
Source: "dist\data\iconsets\transports\gadugadu\*"; DestDir: "{app}\data\iconsets\transports\gadugadu"
Source: "dist\data\iconsets\transports\icq\*"; DestDir: "{app}\data\iconsets\transports\icq"
Source: "dist\data\iconsets\transports\msn\*"; DestDir: "{app}\data\iconsets\transports\msn"
Source: "dist\data\iconsets\transports\yahoo\*"; DestDir: "{app}\data\iconsets\transports\yahoo"
Source: "dist\data\emoticons\*"; DestDir: "{app}\data\emoticons"
Source: "dist\data\pixmaps\*"; DestDir: "{app}\data\pixmaps"
Source: "dist\data\sounds\*"; DestDir: "{app}\data\sounds"

[Icons]
Name: "{group}\Gajim"; Filename: "{app}\Gajim.exe"; WorkingDir: "{app}"; IconFilename: "{app}\gajim.ico"
Name: "{userdesktop}\Gajim"; Filename: "{app}\gajim.exe"; WorkingDir: "{app}"; IconFilename: "{app}\gajim.ico"; Components: main; Tasks: desktopicon

[Run]
Filename: "{app}\gajim.exe"; Description: "Launch application"; Flags: postinstall nowait skipifsilent
