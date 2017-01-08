!include "MUI2.nsh"

Name "Gajim"
OutFile "Gajim-Portable.exe"
SetCompressor /final /solid lzma

!define myAppName "Gajim"

InstallDir "$PROFILE\Gajim"
RequestExecutionLevel user

!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\orange-install.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "data\pixmaps\nsis_header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "data\pixmaps\nsis_wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "data\pixmaps\nsis_wizard.bmp"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "COPYING"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;Show all languages, despite user's codepage
!define MUI_LANGDLL_ALLLANGUAGES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "Hebrew"
!insertmacro MUI_RESERVEFILE_LANGDLL

; English
LangString NAME_Emoticons ${LANG_ENGLISH} "Emoticons"
LangString NAME_Iconsets ${LANG_ENGLISH} "Iconsets"
LangString NAME_Languages ${LANG_ENGLISH} "Languages"
LangString NAME_SecLanguagesOther ${LANG_ENGLISH} "Other"
LangString NAME_Themes ${LANG_ENGLISH} "Themes"
LangString DESC_SecGajim ${LANG_ENGLISH} "Installs the main Gajim files."
LangString DESC_SecGtk ${LANG_ENGLISH} "Installs Gtk+ 2 (necessary to run Gajim)."


; French
LangString NAME_Emoticons ${LANG_FRENCH} "Emoticônes"
LangString NAME_Iconsets ${LANG_FRENCH} "Bibliothèque d'icônes"
LangString NAME_Languages ${LANG_FRENCH} "Langues"
LangString NAME_SecLanguagesOther ${LANG_FRENCH} "Autre"
LangString NAME_Themes ${LANG_FRENCH} "Thèmes"
LangString DESC_SecGajim ${LANG_FRENCH} "Installer les fichiers principaux de Gajim."
LangString DESC_SecGtk ${LANG_FRENCH} "Installer Gtk+ 2 (nécessaire à Gajim)."


; German
LangString NAME_Emoticons ${LANG_GERMAN} "Emoticons"
LangString NAME_Iconsets ${LANG_GERMAN} "Symbolsets"
LangString NAME_Languages ${LANG_GERMAN} "Sprachen"
LangString NAME_SecLanguagesOther ${LANG_GERMAN} "Sonstige"
LangString NAME_Themes ${LANG_GERMAN} "Designs"
LangString DESC_SecGajim ${LANG_GERMAN} "Installiert die Hauptdateien von Gajim."
LangString DESC_SecGtk ${LANG_GERMAN} "Installiert Gtk+ 2 (notwendig um Gajim zu benutzen)."


; Italian
LangString NAME_Emoticons ${LANG_ITALIAN} "Emoticons"
LangString NAME_Iconsets ${LANG_ITALIAN} "Set di icone"
LangString NAME_Languages ${LANG_ITALIAN} "Lingue"
LangString NAME_SecLanguagesOther ${LANG_ITALIAN} "Altre"
LangString NAME_Themes ${LANG_ITALIAN} "Temi"
LangString DESC_SecGajim ${LANG_ITALIAN} "Installa i file principali di Gajim."
LangString DESC_SecGtk ${LANG_ITALIAN} "Installa Gtk+ 2 (necessario per eseguire Gajim)."


; Russian
LangString NAME_Emoticons ${LANG_RUSSIAN} "Ñìàéëèêè"
LangString NAME_Iconsets ${LANG_RUSSIAN} "Òåìû èêîíîê"
LangString NAME_Languages ${LANG_RUSSIAN} "ßçûêè"
LangString NAME_SecLanguagesOther ${LANG_RUSSIAN} "Äðóãîå"
LangString NAME_Themes ${LANG_RUSSIAN} "Òåìû"
LangString DESC_SecGajim ${LANG_RUSSIAN} "Óñòàíîâêà îñíîâíûõ ôàéëîâ Gajim."
LangString DESC_SecGtk ${LANG_RUSSIAN} "Óñòàíîâêà Gtk+ 2 (íåîáõîäèìî äëÿ ðàáîòû Gajim)."


; Hebrew
LangString NAME_Emoticons ${LANG_HEBREW} "øâùåðéí"
LangString NAME_Iconsets ${LANG_HEBREW} "îòøëé öìîéú"
LangString NAME_Languages ${LANG_HEBREW} "ùôåú"
LangString NAME_SecLanguagesOther ${LANG_HEBREW} "àçøåú"
LangString NAME_Themes ${LANG_HEBREW} "òøëàåú ðåùà"
LangString DESC_SecGajim ${LANG_HEBREW} "îú÷éï ÷áöé Gajim òé÷øééí."
LangString DESC_SecGtk ${LANG_HEBREW} "îú÷éï Gtk+ 2 (ðçåöä ìäøöú Gajim)."

Section "Gajim" SecGajim
	SectionIn RO

	SetOutPath "$INSTDIR"
	File "AUTHORS"
	File "COPYING"
	File "THANKS"
	File "THANKS.artists"
	File /r "bin"

	SetOutPath "$INSTDIR\data"	
	File /r "data\gui"
	File /r "data\moods"
	File /r "data\activities"
	File /r "data\other"
	File /r "data\pixmaps"
	File /r "data\sounds"
	
	SetOutPath "$INSTDIR\icons"	
	File /r "icons\hicolor"

	SetOutPath "$INSTDIR\bin"
	CreateShortCut "$INSTDIR\Gajim-Portable.lnk" "$INSTDIR\bin\Gajim.exe" \
  	"-c ..\UserData" "" "" SW_SHOWNORMAL "" "Gajim Portable"
SectionEnd

Section "Gtk+ 2" SecGtk
	SectionIn RO
	SetOutPath "$INSTDIR\bin\gtk"
	File /r "bin\gtk\bin"
	File /r "bin\gtk\etc"
	File /r "bin\gtk\lib"
	File /r "bin\gtk\share"
SectionEnd

Section "Plugins" SecPlugins
	SetOutPath "$INSTDIR\plugins"
	File /r "plugins\plugin_installer"
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

Section "gota" SecIconsetsGota
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\gota"
SectionEnd

Section "jabberbulb" SecIconsetsJabberbulb
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\jabberbulb"
SectionEnd

Section "sun" SecIconsetsSun
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\sun"
SectionEnd

Section "wroop" SecIconsetsWroop
	SetOutPath "$INSTDIR\data\iconsets"
	File /r "data\iconsets\wroop"
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
	File /r "po\he"
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
	File /r "po\uk"
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

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
	!insertmacro MUI_DESCRIPTION_TEXT ${SecGajim} $(DESC_SecGajim)
	!insertmacro MUI_DESCRIPTION_TEXT ${SecGtk} $(DESC_SecGtk)
!insertmacro MUI_FUNCTION_DESCRIPTION_END
