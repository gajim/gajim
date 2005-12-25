[Setup]
AppName=Gajim
AppVerName=Gajim version 0.9.1
DefaultDirName={pf}\Gajim
DefaultGroupName=Gajim
UninstallDisplayIcon={app}\src\Gajim.exe
Compression=lzma
SolidCompression=yes
SetupIconFile=data\pixmaps\gajim.ico

[Components]
Name: "main"; Description: "Main Files"; Types: full compact custom; Flags: fixed

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Components: main
Name: removeprevious; Description: "Remove previously installed version"; GroupDescription: "Previous install:"; Components: main; Check: IsAlreadyInstalled('Gajim');

[Files]
Source: "dist\*.pyd"; DestDir: "{app}\src"
Source: "dist\*.dll"; DestDir: "{app}\src"
Source: "dist\*.zip"; DestDir: "{app}\src"
Source: "COPYING"; DestDir: "{app}"
Source: "dist\gajim.exe"; DestDir: "{app}\src"; components: main
Source: "dist\*.glade"; DestDir: "{app}\src"
Source: "data\*"; DestDir: "{app}\data"; Flags: recursesubdirs
Source: "po\*.mo"; DestDir: "{app}\po"; Flags: recursesubdirs

[Icons]
Name: "{group}\Gajim"; Filename: "{app}\src\Gajim.exe"; WorkingDir: "{app}\src"
Name: "{group}\Uninstall Gajim"; Filename: "{app}\unins000.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Gajim"; Filename: "{app}\src\gajim.exe"; WorkingDir: "{app}\src"; IconFilename: "{app}\data\pixmaps\gajim.ico"; Components: main; Tasks: desktopicon

[Run]
Filename: "{app}\src\gajim.exe"; Description: "Launch application"; Flags: postinstall nowait skipifsilent

[Code]

function GetUninstallPath( AppID: String ): String;
var
   sPrevPath: String;
begin
  sPrevPath := '';
  if not RegQueryStringValue( HKLM,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\'+AppID+'_is1',
    'UninstallString', sPrevpath) then
    RegQueryStringValue( HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\'+AppID+'_is1' ,
      'UninstallString', sPrevpath);

  Result := sPrevPath;
end;

function IsAlreadyInstalled( AppID: String ): Boolean;
var
	sPrevPath: String;
begin
  sPrevPath := GetUninstallPath( AppID );


  if ( Length(sPrevPath) > 0 ) then
    Result:=true
  else
    Result:=false;
 end;

procedure CurStepChanged(CurStep: TSetupStep);
var
	sUninstPath: String;
	sPrevID: String;
	ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    sPrevID := 'Gajim';
    sUninstPath := GetUninstallPath( sprevID );

    if ( Length(sUninstPath) > 0 ) then
    begin
      sUninstPath := RemoveQuotes(sUninstPath);
      Exec( RemoveQuotes(sUninstPath), '/silent', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;
