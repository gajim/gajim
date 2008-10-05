!include "MUI2.nsh"

Name "Gajim"
OutFile "Gajim.exe"
SetCompressor /final /solid lzma

InstallDir "$PROGRAMFILES\Gajim"
InstallDirRegKey HKCU "Software\Gajim" ""
RequestExecutionLevel admin

Var StartMenuFolder

!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\orange-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\orange-uninstall.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "data\pixmaps\nsis_header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "data\pixmaps\nsis_wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "data\pixmaps\nsis_wizard.bmp"
;!define MUI_COMPONENTSPAGE_CHECKBITMAP "${NSISDIR}\Contrib\Graphics\Checks\colorful.bmp"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "COPYING"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU"
!define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\Gajim"
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\bin\Gajim.exe"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_RESERVEFILE_LANGDLL

; English
LangString NAME_Emoticons ${LANG_ENGLISH} "Emoticons"
LangString NAME_Iconsets ${LANG_ENGLISH} "Iconsets"
LangString NAME_Languages ${LANG_ENGLISH} "Languages"
LangString NAME_SecLanguagesOther ${LANG_ENGLISH} "Other"
LangString NAME_Themes ${LANG_ENGLISH} "Themes"
LangString NAME_SecDesktopIcon ${LANG_ENGLISH} "Create icon on desktop"
LangString NAME_SecAutostart ${LANG_ENGLISH} "Start Gajim when Windows starts"
LangString DESC_SecGajim ${LANG_ENGLISH} "Installs the main Gajim files."
LangString DESC_SecGtk ${LANG_ENGLISH} "Installs Gtk+ 2 (necessary to run Gajim)."
LangString DESC_SecDesktopIcon ${LANG_ENGLISH} "If set, a shortcut for Gajim will be created on the desktop."
LangString DESC_SecAutostart ${LANG_ENGLISH} "If set, Gajim will be automatically started when Windows starts."

; French		TODO: TRANSLATE!
LangString NAME_Emoticons ${LANG_FRENCH} "Emoticônes"
LangString NAME_Iconsets ${LANG_FRENCH} "Bibliothèque d'icônes"
LangString NAME_Languages ${LANG_FRENCH} "Langues"
LangString NAME_SecLanguagesOther ${LANG_FRENCH} "Autre"
LangString NAME_Themes ${LANG_FRENCH} "Thèmes"
LangString NAME_SecDesktopIcon ${LANG_FRENCH} "Create icon on desktop"
LangString NAME_SecAutostart ${LANG_FRENCH} "Lancer Gajim au démarrage de Windows"
LangString DESC_SecGajim ${LANG_FRENCH} "Installer les fichiers principaux de Gajim."
LangString DESC_SecGtk ${LANG_FRENCH} "Installer Gtk+ 2 (nécessaire à Gajim)."
LangString DESC_SecDesktopIcon ${LANG_FRENCH} "If set, a shortcut for Gajim will be created on the desktop."
LangString DESC_SecAutostart ${LANG_FRENCH} "Si activé, Gajim sera automatiquement lancé au démarrage de Windows."

; German
LangString NAME_Emoticons ${LANG_GERMAN} "Emoticons"
LangString NAME_Iconsets ${LANG_GERMAN} "Symbolsets"
LangString NAME_Languages ${LANG_GERMAN} "Sprachen"
LangString NAME_SecLanguagesOther ${LANG_GERMAN} "Sonstige"
LangString NAME_Themes ${LANG_GERMAN} "Designs"
LangString NAME_SecDesktopIcon ${LANG_GERMAN} "Desktop-Icon erstellen"
LangString NAME_SecAutostart ${LANG_GERMAN} "Gajim mit Windows starten"
LangString DESC_SecGajim ${LANG_GERMAN} "Installiert die Hauptdateien von Gajim."
LangString DESC_SecGtk ${LANG_GERMAN} "Installert Gtk+ 2 (notwendig um Gajim zu benutzen)."
LangString DESC_SecDesktopIcon ${LANG_GERMAN} "Wenn dies aktiviert wird, wird ein Icon für Gajim auf dem Desktop erstellt."
LangString DESC_SecAutostart ${LANG_GERMAN} "Gajim wird automatisch gestartet, sowie Windows startet, wenn dies aktivier wird."

; Italian		TODO: TRANSLATE!
LangString NAME_Emoticons ${LANG_ITALIAN} "Emoticons"
LangString NAME_Iconsets ${LANG_ITALIAN} "Iconsets"
LangString NAME_Languages ${LANG_ITALIAN} "Languages"
LangString NAME_SecLanguagesOther ${LANG_ITALIAN} "Other"
LangString NAME_Themes ${LANG_ITALIAN} "Themes"
LangString NAME_SecDesktopIcon ${LANG_ITALIAN} "Create icon on desktop"
LangString NAME_SecAutostart ${LANG_ITALIAN} "Start Gajim when Windows starts"
LangString DESC_SecGajim ${LANG_ITALIAN} "Installs the main Gajim files."
LangString DESC_SecGtk ${LANG_ITALIAN} "Installs Gtk+ 2 (necessary to run Gajim)."
LangString DESC_SecDesktopIcon ${LANG_ITALIAN} "If set, a shortcut for Gajim will be created on the desktop."
LangString DESC_SecAutostart ${LANG_ITALIAN} "If set, Gajim will be automatically started when Windows starts."

; Spanish		TODO: TRANSLATE!
LangString NAME_Emoticons ${LANG_SPANISH} "Emoticons"
LangString NAME_Iconsets ${LANG_SPANISH} "Iconsets"
LangString NAME_Languages ${LANG_SPANISH} "Languages"
LangString NAME_SecLanguagesOther ${LANG_SPANISH} "Other"
LangString NAME_Themes ${LANG_THEMES} "Themes"
LangString NAME_SecDesktopIcon ${LANG_SPANISH} "Create icon on desktop"
LangString NAME_SecAutostart ${LANG_SPANISH} "Start Gajim when Windows starts"
LangString DESC_SecGajim ${LANG_SPANISH} "Installs the main Gajim files."
LangString DESC_SecGtk ${LANG_SPANISH} "Installs Gtk+ 2 (necessary to run Gajim)."
LangString DESC_SecDesktopIcon ${LANG_SPANISH} "If set, a shortcut for Gajim will be created on the desktop."
LangString DESC_SecAutostart ${LANG_SPANISH} "If set, Gajim will be automatically started when Windows starts."

; Russian		TODO: TRANSLATE!
LangString NAME_Emoticons ${LANG_RUSSIAN} "Emoticons"
LangString NAME_Iconsets ${LANG_RUSSIAN} "Iconsets"
LangString NAME_Languages ${LANG_RUSSIAN} "Languages"
LangString NAME_SecLanguagesOther ${LANG_RUSSIAN} "Other"
LangString NAME_Themes ${LANG_RUSSIAN} "Themes"
LangString NAME_SecDesktopIcon ${LANG_RUSSIAN} "Create icon on desktop"
LangString NAME_SecAutostart ${LANG_RUSSIAN} "Start Gajim when Windows starts"
LangString DESC_SecGajim ${LANG_RUSSIAN} "Installs the main Gajim files."
LangString DESC_SecGtk ${LANG_RUSSIAN} "Installs Gtk+ 2 (necessary to run Gajim)."
LangString DESC_SecDesktopIcon ${LANG_RUSSIAN} "If set, a shortcut for Gajim will be created on the desktop."
LangString DESC_SecAutostart ${LANG_RUSSIAN} "If set, Gajim will be automatically started when Windows starts."

Section "Gajim" SecGajim
	SectionIn RO

	SetOutPath "$INSTDIR"
	File "AUTHORS"
	File "COPYING"
	File "THANKS"
	File "THANKS.artists"

	SetOutPath "$INSTDIR\bin"
	File "bin\_cairo.pyd"
	File "bin\_ctypes.pyd"
	File "bin\_gobject.pyd"
	File "bin\_gtk.pyd"
	File "bin\_hashlib.pyd"
	File "bin\_socket.pyd"
	File "bin\_sqlite3.pyd"
	File "bin\_ssl.pyd"
	File "bin\_win32sysloader.pyd"
	File "bin\AES.pyd"
	File "bin\atk.pyd"
	File "bin\bz2.pyd"
	File "bin\crypto.pyd"
	File "bin\gajim.exe"
	File "bin\glade.pyd"
	File "bin\history_manager.exe"
	File "bin\libeay32.dll"
	File "bin\libglade-2.0-0.dll"
	File "bin\library.zip"
	File "bin\libxml2.dll"
	File "bin\msvcr71.dll"
	File "bin\pangocairo.pyd"
	File "bin\pango.pyd"
	File "bin\pyexpat.pyd"
	File "bin\python25.dll"
	File "bin\pywintypes25.dll"
	File "bin\rand.pyd"
	File "bin\select.pyd"
	File "bin\SHA256.pyd"
	File "bin\sqlite3.dll"
	File "bin\ssleay32.dll"
	File "bin\SSL.pyd"
	File "bin\unicodedata.pyd"
	File "bin\w9xpopen.exe"
	File "bin\win32api.pyd"
	File "bin\win32file.pyd"
	File "bin\winsound.pyd"
	File "bin\zlib1.dll"

	WriteRegStr HKCU "Software\Gajim" "" $INSTDIR
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "DisplayName" "Gajim"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "UninstallString" "$INSTDIR\Uninstall.exe"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "DisplayIcon" "$INSTDIR\bin\Gajim.exe"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "DisplayVersion" "0.12-alpha1"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "URLInfoAbout" "http://www.gajim.org/"
	WriteUninstaller "$INSTDIR\Uninstall.exe"

	!insertmacro MUI_STARTMENU_WRITE_BEGIN Application
		SetShellVarContext current
		CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Change Theme.lnk" "$INSTDIR\bin\gtk\bin\gtkthemeselector.exe"
		SetShellVarContext all
		CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Change Theme.lnk" "$INSTDIR\bin\gtk\bin\gtkthemeselector.exe"
	!insertmacro MUI_STARTMENU_WRITE_END

	SetOutPath "$INSTDIR\data"	
	File /r "data\glade"
	File /r "data\moods"
	File /r "data\activities"
	File /r "data\other"
	File /r "data\pixmaps"
	File /r "data\sounds"
SectionEnd

Section "Gtk+ 2" SecGtk
	SectionIn RO
	SetOutPath "$INSTDIR\bin\gtk"
	File /r "bin\gtk\bin"
	File /r "bin\gtk\etc"
	SetOutPath "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0\engines"
	File "bin\gtk\lib\gtk-2.0\2.10.0\engines\libclearlooks.dll"
	File "bin\gtk\lib\gtk-2.0\2.10.0\engines\libpixmap.dll"
	File "bin\gtk\lib\gtk-2.0\2.10.0\engines\libsvg.dll"
	SetOutPath "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0"
	SetOutPath "$INSTDIR\bin\gtk\lib"
	File "bin\gtk\lib\charset.alias"
	SetOutPath "$INSTDIR\bin\gtk\share"
	File /r "bin\gtk\share\gtkthemeselector"
	File /r "bin\gtk\share\xml"
SectionEnd

SectionGroup $(NAME_Emoticons)

Section "animated" SecEmoticonsAnimated
	SetOutPath "$INSTDIR\data\emoticons"
	File /r "data\emoticons\animated"
SectionEnd

Section "static" SecEmoticonsStatic
	SectionIn RO
	SetOutPath "$INSTDIR\data\emoticons"
	File /r "data\emoticons\static"
SectioNEnd

Section "static-big" SecEmoticonsStaticBig
	SetOutPath "$INSTDIR\data\emoticons"
	File /r "data\emoticons\static-big"
SectionEnd

SectionGroupEnd

SectionGroup $(NAME_Iconsets)

Section "crystal" SecIconsetsCrystal
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\crystal"
SectionEnd

Section "dcraven" SecIconsetsDcraven
	SectionIn RO
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\dcraven"
SectionEnd

Section "gnome" SecIconsetsGnome
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\gnome"
SectionEnd

Section "goojim" SecIconsetsGoojim
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\goojim"
SectionEnd

Section "gossip" SecIconsetsGossip
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\gossip"
SectionEnd

Section "gota" SecIconsetsGota
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\gota"
SectionEnd

Section "jabberbulb" SecIconsetsJabberbulb
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\jabberbulb"
SectionEnd

Section "nuvola" SecIconsetsNuvola
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\nuvola"
SectionEnd

Section "simplebulb" SecIconsetsSimplebulb
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\simplebulb"
SectionEnd

Section "stellar" SecIconsetsStellar
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\stellar"
SectionEnd

Section "sun" SecIconsetsSun
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\sun"
SectionEnd

Section "transports" SecIconsetsTransports
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\transports"
	SectionIn Ro
SectionEnd

SectionGroupEnd

SectionGroup $(NAME_Languages)

Section "English (UK)" SecLanguagesEnglishUK
	SetOutPath "$INSTDIR\po"
	File /r "po\en_GB"
	SetOutPath "$INSTDIR\bin\gtk\share\locale"
	File /r "bin\gtk\share\locale\en_GB"
SectionEnd

Section "French" SecLanguagesFrench
	SetOutPath "$INSTDIR\po"
	File /r "po\fr"
	SetOutPath "$INSTDIR\bin\gtk\share\locale"
	File /r "bin\gtk\share\locale\fr"
SectionEnd

Section "German" SecLanguagesGerman
	SetOutPath "$INSTDIR\po"
	File /r "po\de"
	SetOutPath "$INSTDIR\bin\gtk\share\locale"
	File /r "bin\gtk\share\locale\de"
SectionEnd

Section "Italian" SecLanguagesItalian
	SetOutPath "$INSTDIR\po"
	File /r "po\it"
	SetOutPath "$INSTDIR\bin\gtk\share\locale"
	File /r "bin\gtk\share\locale\it"
SectionEnd

Section "Spanish" SecLanguagesSpanish
	SetOutPath "$INSTDIR\po"
	File /r "po\es"
	SetOutPath "$INSTDIR\bin\gtk\share\locale"
	File /r "bin\gtk\share\locale\es"
SectionEnd

Section "Russian" SecLanguagesRussian
	SetOutPath "$INSTDIR\po"
	File /r "po\ru"
	SetOutPath "$INSTDIR\bin\gtk\share\locale"
	File /r "bin\gtk\share\locale\ru"
SectionEnd

Section $(NAME_SecLanguagesOther) SecLanguagesOther
	SetOutPath "$INSTDIR\po"
	File /r "po\be"
	File /r "po\be@latin"
	File /r "po\bg"
	File /r "po\br"
	File /r "po\cs"
	File /r "po\da"
	File /r "po\el"
	File /r "po\eo"
	File /r "po\eu"
	File /r "po\gl"
	File /r "po\hr"
	File /r "po\lt"
	File /r "po\nb"
	File /r "po\nl"
	File /r "po\no"
	File /r "po\pl"
	File /r "po\pt"
	File /r "po\pt_BR"
	File /r "po\sk"
	File /r "po\sr"
	File /r "po\sr@Latn"
	File /r "po\sv"
	File /r "po\zh_CN"
	SetOutPath "$INSTDIR\bin\gtk\share\locale"
	File /r "bin\gtk\share\locale\af"
	File /r "bin\gtk\share\locale\am"
	File /r "bin\gtk\share\locale\ang"
	File /r "bin\gtk\share\locale\ar"
	File /r "bin\gtk\share\locale\as"
	File /r "bin\gtk\share\locale\az"
	File /r "bin\gtk\share\locale\az_IR"
	File /r "bin\gtk\share\locale\be"
	File /r "bin\gtk\share\locale\be@latin"
	File /r "bin\gtk\share\locale\bg"
	File /r "bin\gtk\share\locale\bn"
	File /r "bin\gtk\share\locale\bn_IN"
	File /r "bin\gtk\share\locale\br"
	File /r "bin\gtk\share\locale\bs"
	File /r "bin\gtk\share\locale\ca"
	File /r "bin\gtk\share\locale\ca@valencia"
	File /r "bin\gtk\share\locale\cs"
	File /r "bin\gtk\share\locale\cy"
	File /r "bin\gtk\share\locale\da"
	File /r "bin\gtk\share\locale\dz"
	File /r "bin\gtk\share\locale\el"
	File /r "bin\gtk\share\locale\en_CA"
	File /r "bin\gtk\share\locale\eo"
	File /r "bin\gtk\share\locale\et"
	File /r "bin\gtk\share\locale\eu"
	File /r "bin\gtk\share\locale\fa"
	File /r "bin\gtk\share\locale\fi"
	File /r "bin\gtk\share\locale\ga"
	File /r "bin\gtk\share\locale\gl"
	File /r "bin\gtk\share\locale\gu"
	File /r "bin\gtk\share\locale\he"
	File /r "bin\gtk\share\locale\hi"
	File /r "bin\gtk\share\locale\hr"
	File /r "bin\gtk\share\locale\hu"
	File /r "bin\gtk\share\locale\hy"
	File /r "bin\gtk\share\locale\ia"
	File /r "bin\gtk\share\locale\id"
	File /r "bin\gtk\share\locale\io"
	File /r "bin\gtk\share\locale\is"
	File /r "bin\gtk\share\locale\ja"
	File /r "bin\gtk\share\locale\ka"
	File /r "bin\gtk\share\locale\kn"
	File /r "bin\gtk\share\locale\ko"
	File /r "bin\gtk\share\locale\ku"
	File /r "bin\gtk\share\locale\li"
	File /r "bin\gtk\share\locale\lt"
	File /r "bin\gtk\share\locale\lv"
	File /r "bin\gtk\share\locale\mai"
	File /r "bin\gtk\share\locale\mg"
	File /r "bin\gtk\share\locale\mi"
	File /r "bin\gtk\share\locale\mk"
	File /r "bin\gtk\share\locale\ml"
	File /r "bin\gtk\share\locale\mn"
	File /r "bin\gtk\share\locale\mr"
	File /r "bin\gtk\share\locale\ms"
	File /r "bin\gtk\share\locale\nb"
	File /r "bin\gtk\share\locale\ne"
	File /r "bin\gtk\share\locale\nl"
	File /r "bin\gtk\share\locale\nn"
	File /r "bin\gtk\share\locale\nso"
	File /r "bin\gtk\share\locale\oc"
	File /r "bin\gtk\share\locale\or"
	File /r "bin\gtk\share\locale\pa"
	File /r "bin\gtk\share\locale\pl"
	File /r "bin\gtk\share\locale\ps"
	File /r "bin\gtk\share\locale\pt"
	File /r "bin\gtk\share\locale\pt_BR"
	File /r "bin\gtk\share\locale\ro"
	File /r "bin\gtk\share\locale\rw"
	File /r "bin\gtk\share\locale\si"
	File /r "bin\gtk\share\locale\sk"
	File /r "bin\gtk\share\locale\sl"
	File /r "bin\gtk\share\locale\sq"
	File /r "bin\gtk\share\locale\sr"
	File /r "bin\gtk\share\locale\sr@ije"
	File /r "bin\gtk\share\locale\sr@latin"
	File /r "bin\gtk\share\locale\sv"
	File /r "bin\gtk\share\locale\ta"
	File /r "bin\gtk\share\locale\te"
	File /r "bin\gtk\share\locale\th"
	File /r "bin\gtk\share\locale\tk"
	File /r "bin\gtk\share\locale\tl"
	File /r "bin\gtk\share\locale\tr"
	File /r "bin\gtk\share\locale\tt"
	File /r "bin\gtk\share\locale\ug"
	File /r "bin\gtk\share\locale\uk"
	File /r "bin\gtk\share\locale\ur"
	File /r "bin\gtk\share\locale\uz"
	File /r "bin\gtk\share\locale\uz@cyrillic"
	File /r "bin\gtk\share\locale\vi"
	File /r "bin\gtk\share\locale\wa"
	File /r "bin\gtk\share\locale\xh"
	File /r "bin\gtk\share\locale\yi"
	File /r "bin\gtk\share\locale\zh_CN"
	File /r "bin\gtk\share\locale\zh_HK"
	File /r "bin\gtk\share\locale\zh_TW"
SectionEnd

SectionGroupEnd

SectionGroup $(NAME_Themes)

Section "Clearlooks" SecThemesClearlooks
	SetOutPath "$INSTDIR\bin\gtk\share\themes"
	File /r "bin\gtk\share\themes\Clearlooks"
SectionEnd

Section "Default GTK" SecThemesDefault
	SetOutPath "$INSTDIR\bin\gtk\share\themes"
	File /r "bin\gtk\share\themes\Default"
SectionEnd

Section "Glossy" SecThemesGlossy
	SetOutPath "$INSTDIR\bin\gtk\share\themes"
	File /r "bin\gtk\share\themes\Glossy"
SectionEnd

Section "Glossy-js" SecThemesGlossyJs
	SectionIn RO
	SetOutPath "$INSTDIR\bin\gtk\share\themes"
	File /r "bin\gtk\share\themes\Glossy-js"
SectionEnd

Section "MS-Windows" SecThemesMSWindows
	SetOutPath "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0\engines"
	File "bin\gtk\lib\gtk-2.0\2.10.0\engines\libwimp.dll"
	SetOutPath "$INSTDIR\bin\gtk\share\themes"
	File /r "bin\gtk\share\themes\MS-Windows"
SectionEnd

SectionGroupEnd

Section $(NAME_SecDesktopIcon) SecDesktopIcon
	SetShellVarContext current
	SetOutPath "$INSTDIR\bin"
	CreateShortCut "$DESKTOP\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
SectionEnd

Section $(NAME_SecAutostart) SecAutostart
	SetShellVarContext current
	SetOutPath "$INSTDIR\bin"
	CreateShortCut "$SMSTARTUP\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
SectionEnd

Section "Uninstall"
	RMDir /r "$INSTDIR\bin\gtk\bin"
	RMDir /r "$INSTDIR\bin\gtk\etc"
	Delete "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0\engines\libclearlooks.dll"
	Delete "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0\engines\libpixmap.dll"
	Delete "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0\engines\libsvg.dll"
	Delete "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0\engines\libwimp.dll"
	RMDir "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0\engines"
	RMDir "$INSTDIR\bin\gtk\lib\gtk-2.0\2.10.0"
	RMDir "$INSTDIR\bin\gtk\lib\gtk-2.0"
	Delete "$INSTDIR\bin\gtk\lib\charset.alias"
	RMDir "$INSTDIR\bin\gtk\lib"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\de"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\en_GB"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\es"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\fr"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\it"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ru"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\af"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\am"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ang"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ar"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\as"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\az"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\az_IR"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\be"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\be@latin"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\bg"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\bn"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\bn_IN"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\br"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\bs"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ca"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ca@valencia"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\cs"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\cy"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\da"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\dz"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\el"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\en_CA"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\eo"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\et"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\eu"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\fa"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\fi"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ga"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\gl"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\gu"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\he"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\hi"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\hr"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\hu"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\hy"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ia"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\id"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\io"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\is"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ja"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ka"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\kn"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ko"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ku"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\li"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\lt"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\lv"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\mai"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\mg"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\mi"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\mk"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ml"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\mn"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\mr"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ms"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\nb"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ne"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\nl"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\nn"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\nso"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\oc"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\or"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\pa"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\pl"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ps"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\pt"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\pt_BR"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ro"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\rw"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\si"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\sk"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\sl"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\sq"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\sr"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\sr@ije"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\sr@latin"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\sv"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ta"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\te"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\th"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\tk"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\tl"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\tr"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\tt"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ug"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\uk"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\ur"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\uz"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\uz@cyrillic"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\vi"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\wa"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\xh"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\yi"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\zh_CN"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\zh_HK"
	RMDir /r "$INSTDIR\bin\gtk\share\locale\zh_TW"
	RMDir "$INSTDIR\bin\gtk\share\locale"
	RMDir /r "$INSTDIR\bin\gtk\share\themes\Clearlooks"
	RMDir /r "$INSTDIR\bin\gtk\share\themes\Default"
	RMDir /r "$INSTDIR\bin\gtk\share\themes\Glossy"
	RMDir /r "$INSTDIR\bin\gtk\share\themes\Glossy-js"
	RMDir /r "$INSTDIR\bin\gtk\share\themes\MS-Windows"
	RMDir "$INSTDIR\bin\gtk\share\themes"
	RMDir /r "$INSTDIR\bin\gtk\share\gtkthemeselector"
	RMDir /r "$INSTDIR\bin\gtk\share\xml"
	RMDir "$INSTDIR\bin\gtk\share"
	RMDir "$INSTDIR\bin\gtk"
	Delete "$INSTDIR\bin\_cairo.pyd"
	Delete "$INSTDIR\bin\_ctypes.pyd"
	Delete "$INSTDIR\bin\_gobject.pyd"
	Delete "$INSTDIR\bin\_gtk.pyd"
	Delete "$INSTDIR\bin\_hashlib.pyd"
	Delete "$INSTDIR\bin\_socket.pyd"
	Delete "$INSTDIR\bin\_sqlite3.pyd"
	Delete "$INSTDIR\bin\_sqlite.pyd"
	Delete "$INSTDIR\bin\_ssl.pyd"
	Delete "$INSTDIR\bin\_win32sysloader.pyd"
	Delete "$INSTDIR\bin\AES.pyd"
	Delete "$INSTDIR\bin\atk.pyd"
	Delete "$INSTDIR\bin\bz2.pyd"
	Delete "$INSTDIR\bin\crypto.pyd"
	Delete "$INSTDIR\bin\gajim.exe"
	Delete "$INSTDIR\bin\glade.pyd"
	Delete "$INSTDIR\bin\history_manager.exe"
	Delete "$INSTDIR\bin\libeay32.dll"
	Delete "$INSTDIR\bin\libglade-2.0-0.dll"
	Delete "$INSTDIR\bin\library.zip"
	Delete "$INSTDIR\bin\libxml2.dll"
	Delete "$INSTDIR\bin\msvcr71.dll"
	Delete "$INSTDIR\bin\pangocairo.pyd"
	Delete "$INSTDIR\bin\pango.pyd"
	Delete "$INSTDIR\bin\pyexpat.pyd"
	Delete "$INSTDIR\bin\python25.dll"
	Delete "$INSTDIR\bin\pywintypes25.dll"
	Delete "$INSTDIR\bin\rand.pyd"
	Delete "$INSTDIR\bin\select.pyd"
	Delete "$INSTDIR\bin\SHA256.pyd"
	Delete "$INSTDIR\bin\sqlite3.dll"
	Delete "$INSTDIR\bin\ssleay32.dll"
	Delete "$INSTDIR\bin\SSL.pyd"
	Delete "$INSTDIR\bin\unicodedata.pyd"
	Delete "$INSTDIR\bin\w9xpopen.exe"
	Delete "$INSTDIR\bin\win32api.pyd"
	Delete "$INSTDIR\bin\win32file.pyd"
	Delete "$INSTDIR\bin\winsound.pyd"
	Delete "$INSTDIR\bin\zlib1.dll"
	RMDir "$INSTDIR\bin"
	RMDir /r "$INSTDIR\data\glade"
	RMDir /r "$INSTDIR\data\moods"
	RMDir /r "$INSTDIR\data\activities"
	RMDir /r "$INSTDIR\data\other"
	RMDir /r "$INSTDIR\data\pixmaps"
	RMDir /r "$INSTDIR\data\sounds"
	RMDir /r "$INSTDIR\data\emoticons\animated"
	RMDir /r "$INSTDIR\data\emoticons\static"
	RMDir /r "$INSTDIR\data\emoticons\static-big"
	RMDir "$INSTDIR\data\emoticons"
	RMDir /r "$INSTDIR\data\iconsets\crystal"
	RMDir /r "$INSTDIR\data\iconsets\dcraven"
	RMDir /r "$INSTDIR\data\iconsets\gnome"
	RMDir /r "$INSTDIR\data\iconsets\goojim"
	RMDir /r "$INSTDIR\data\iconsets\gossip"
	RMDir /r "$INSTDIR\data\iconsets\gota"
	RMDir /r "$INSTDIR\data\iconsets\jabberbulb"
	RMDir /r "$INSTDIR\data\iconsets\nuvola"
	RMDir /r "$INSTDIR\data\iconsets\simplebulb"
	RMDir /r "$INSTDIR\data\iconsets\stellar"
	RMDir /r "$INSTDIR\data\iconsets\sun"
	RMDir /r "$INSTDIR\data\iconsets\transports"
	RMDir "$INSTDIR\data\iconsets"
	RMDir "$INSTDIR\data"
	RMDir /r "$INSTDIR\po\be"
	RMDir /r "$INSTDIR\po\be@latin"
	RMDir /r "$INSTDIR\po\bg"
	RMDir /r "$INSTDIR\po\br"
	RMDir /r "$INSTDIR\po\cs"
	RMDir /r "$INSTDIR\po\da"
	RMDir /r "$INSTDIR\po\de"
	RMDir /r "$INSTDIR\po\el"
	RMDir /r "$INSTDIR\po\en_GB"
	RMDir /r "$INSTDIR\po\eo"
	RMDir /r "$INSTDIR\po\es"
	RMDir /r "$INSTDIR\po\eu"
	RMDir /r "$INSTDIR\po\fr"
	RMDir /r "$INSTDIR\po\gl"
	RMDir /r "$INSTDIR\po\hr"
	RMDir /r "$INSTDIR\po\it"
	RMDir /r "$INSTDIR\po\lt"
	RMDir /r "$INSTDIR\po\nb"
	RMDir /r "$INSTDIR\po\nl"
	RMDir /r "$INSTDIR\po\no"
	RMDir /r "$INSTDIR\po\pl"
	RMDir /r "$INSTDIR\po\pt"
	RMDir /r "$INSTDIR\po\pt_BR"
	RMDir /r "$INSTDIR\po\ru"
	RMDir /r "$INSTDIR\po\sk"
	RMDir /r "$INSTDIR\po\sr"
	RMDir /r "$INSTDIR\po\sr@Latn"
	RMDir /r "$INSTDIR\po\sv"
	RMDir /r "$INSTDIR\po\zh_CN"
	RMDir "$INSTDIR\po"
	Delete "$INSTDIR\AUTHORS"
	Delete "$INSTDIR\COPYING"
	Delete "$INSTDIR\THANKS"
	Delete "$INSTDIR\THANKS.artists"
	Delete "$INSTDIR\Uninstall.exe"
	RMDir "$INSTDIR"

	!insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder

	SetShellVarContext current
	Delete "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk"
	Delete "$SMPROGRAMS\$StartMenuFolder\Change Theme.lnk"
	RMDir "$SMPROGRAMS\$StartMenuFolder"
	Delete "$DESKTOP\Gajim.lnk"
	Delete "$SMSTARTUP\Gajim.lnk"
	SetShellVarContext all
	Delete "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk"
	Delete "$SMPROGRAMS\$StartMenuFolder\Change Theme.lnk"
	RMDir "$SMPROGRAMS\$StartMenuFolder"

	DeleteRegKey /ifempty HKCU "Software\Gajim"
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
	!insertmacro MUI_DESCRIPTION_TEXT ${SecGajim} $(DESC_SecGajim)
	!insertmacro MUI_DESCRIPTION_TEXT ${SecGtk} $(DESC_SecGtk)
	!insertmacro MUI_DESCRIPTION_TEXT ${SecDesktopIcon} $(DESC_SecDesktopIcon)
	!insertmacro MUI_DESCRIPTION_TEXT ${SecAutostart} $(DESC_SecAutostart)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function .onInit
	!insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd
