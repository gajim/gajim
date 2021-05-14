; File encoding 'UTF-8 with BOM'

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"


Name "Gajim"
OutFile "Gajim-Portable.exe"
SetCompressor /final /solid lzma
SetCompressorDictSize 32

!define myAppName "Gajim"

InstallDir "$PROFILE\Gajim"
RequestExecutionLevel user
BrandingText "Gajim Setup"

!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\orange-install.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "..\misc\nsis_header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "..\misc\nsis_wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "..\misc\nsis_wizard.bmp"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\COPYING"
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
LangString INST_NotEmpty ${LANG_ENGLISH} "It looks like you already installed Gajim in this directory. A cleanup is necessary before installing. Your user data will not be touched. Cleanup now?"


; French
LangString NAME_Emoticons ${LANG_FRENCH} "Emoticônes"
LangString NAME_Iconsets ${LANG_FRENCH} "Bibliothèque d'icônes"
LangString NAME_Languages ${LANG_FRENCH} "Langues"
LangString NAME_SecLanguagesOther ${LANG_FRENCH} "Autre"
LangString NAME_Themes ${LANG_FRENCH} "Thèmes"
LangString DESC_SecGajim ${LANG_FRENCH} "Installer les fichiers principaux de Gajim."
LangString INST_NotEmpty ${LANG_FRENCH} "It looks like you already installed Gajim in this directory. A cleanup is necessary before installing. Your user data will not be touched. Cleanup now?"


; German
LangString NAME_Emoticons ${LANG_GERMAN} "Emojis"
LangString NAME_Iconsets ${LANG_GERMAN} "Iconsets"
LangString NAME_Languages ${LANG_GERMAN} "Sprachen"
LangString NAME_SecLanguagesOther ${LANG_GERMAN} "Sonstige"
LangString NAME_Themes ${LANG_GERMAN} "Designs"
LangString DESC_SecGajim ${LANG_GERMAN} "Installiert die Hauptdateien von Gajim."
LangString INST_NotEmpty ${LANG_GERMAN} "Anscheinend ist Gajim bereits in diesem Verzeichnis installiert. Vor der Installation ist es notwendig das Verzeichnis aufzuräumen. Deine Benutzerdaten bleiben erhalten. Jetzt aufräumen?"


; Italian
LangString NAME_Emoticons ${LANG_ITALIAN} "Emoticons"
LangString NAME_Iconsets ${LANG_ITALIAN} "Set di icone"
LangString NAME_Languages ${LANG_ITALIAN} "Lingue"
LangString NAME_SecLanguagesOther ${LANG_ITALIAN} "Altre"
LangString NAME_Themes ${LANG_ITALIAN} "Temi"
LangString DESC_SecGajim ${LANG_ITALIAN} "Installa i file principali di Gajim."
LangString INST_NotEmpty ${LANG_ITALIAN} "It looks like you already installed Gajim in this directory. A cleanup is necessary before installing. Your user data will not be touched. Cleanup now?"


; Russian
LangString NAME_Emoticons ${LANG_RUSSIAN} "Смайлики"
LangString NAME_Iconsets ${LANG_RUSSIAN} "Темы иконок"
LangString NAME_Languages ${LANG_RUSSIAN} "Языки"
LangString NAME_SecLanguagesOther ${LANG_RUSSIAN} "Другое"
LangString NAME_Themes ${LANG_RUSSIAN} "Темы"
LangString DESC_SecGajim ${LANG_RUSSIAN} "Установка основных файлов Gajim."
LangString INST_NotEmpty ${LANG_RUSSIAN} "It looks like you already installed Gajim in this directory. A cleanup is necessary before installing. Your user data will not be touched. Cleanup now?"


; Hebrew
LangString NAME_Emoticons ${LANG_HEBREW} "רגשונים"
LangString NAME_Iconsets ${LANG_HEBREW} "מערכי צלמית"
LangString NAME_Languages ${LANG_HEBREW} "שפות"
LangString NAME_SecLanguagesOther ${LANG_HEBREW} "אחרות"
LangString NAME_Themes ${LANG_HEBREW} "ערכאות נושא"
LangString DESC_SecGajim ${LANG_HEBREW} "מתקין קבצי Gajim עיקריים."
LangString INST_NotEmpty ${LANG_HEBREW} "It looks like you already installed Gajim in this directory. A cleanup is necessary before installing. Your user data will not be touched. Cleanup now?"

Section "Gajim" SecGajim
    SectionIn RO

    SetOutPath "$INSTDIR"

    ${If} ${FileExists} "$InstDir\bin\Gajim.exe"
        MessageBox MB_YESNO $(INST_NotEmpty) IDYES cleanup
        Abort
    cleanup:
        RMDir /r "$InstDir\bin"
        RMDir /r "$InstDir\etc"
        RMDir /r "$InstDir\lib"
        RMDir /r "$InstDir\share"
        RMDir /r "$InstDir\ssl"
    ${EndIf}

    File /r "${ARCH}\*.*"

    SetOutPath "$INSTDIR\bin"
    CreateShortCut "$INSTDIR\Gajim-Portable.lnk" "$INSTDIR\bin\Gajim.exe" \
    "" "" "" SW_SHOWNORMAL "" "Gajim Portable"
    CreateShortCut "$INSTDIR\Gajim-Portable-Debug.lnk" "$INSTDIR\bin\Gajim-Debug.exe" \
    "" "" "" SW_SHOWNORMAL "" "Gajim Portable Debug"
    FileOpen $0 "is_portable" w
    FileClose $0

SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecGajim} $(DESC_SecGajim)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function .onInit
    !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd
