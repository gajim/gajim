rmdir /S /Q gajim_built

mkdir gajim_built
hg archive gajim_built
xcopy ..\gajim-plugins\plugin_installer gajim_built\plugins\plugin_installer /e /i

copy msgfmt.exe gajim_built
copy gettextsrc.dll gajim_built
copy gettextlib.dll gajim_built
copy msvcr90.dll gajim_built

cd gajim_built

REM for libglade-2.0.0.dll
PATH=..\src\gtk\bin;%PATH%

c:\python27\python.exe setup_win32.py build_exe

move build\exe.win32-2.7 .
rename exe.win32-2.7 bin

copy ..\LIBEAY32.dll bin
copy ..\SSLEAY32.dll bin

REM for snarl plugin
xcopy ..\win32com bin\win32com /e /i

mkdir bin\gtk
cd ../src/gtk
hg archive ..\..\gajim_built\bin\gtk
cd ../../gajim_built/

REM for msgfmt
PATH=bin\gtk\bin;%PATH%

for %%l in (po\*.po) do mkdir po\%%~nl & mkdir po\%%~nl\LC_MESSAGES & msgfmt -o po\%%~nl\LC_MESSAGES\gajim.mo %%l

"C:\Program Files (x86)\NSIS\makensis" gajim.nsi

cd ..