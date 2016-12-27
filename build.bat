rmdir /S /Q ..\gajim_built

xcopy . ..\gajim_built /e /i
xcopy ..\gajim-plugins\plugin_installer ..\gajim_built\plugins\plugin_installer /e /i
cd ..\gajim_built

c:\python27\python.exe setup_win32.py build_exe

move build\exe.win32-2.7 .
rename exe.win32-2.7 bin

xcopy ..\gtk bin\gtk /e /i

for %%l in (po\*.po) do mkdir po\%%~nl & mkdir po\%%~nl\LC_MESSAGES & msgfmt -o po\%%~nl\LC_MESSAGES\gajim.mo %%l

"C:\Program Files (x86)\NSIS\makensis" gajim.nsi

cd ..
