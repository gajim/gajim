# -*- mode: python -*-

block_cipher = None

cwd = os.getcwd()
icon = os.path.join(cwd, "mac", "Gajim.icns")

info_plist = {
    "CFBundleDisplayName": "Gajim",
    "NSHighResolutionCapable": True,
    "CFBundleURLTypes": [{"CFBundleURLName": "XMPP URI",
                          "CFBundleURLSchemes": ["xmpp"]}],
    "NSUIElement": True
}

import sys
import glob
import platform

# Hidden libs to add because we remove PIL._imagingft to avoid non-system versions
hidden_libs = ['libsoup-*.dylib', 'libgtksourceview-*.dylib']

# Get homebrew lib path according to system arch
if platform.machine() == 'x86_64':
	lib_path = '/usr/local/lib/'
elif platform.machine() == 'arm64':
	lib_path = '/opt/homebrew/lib/'

# Select the last libs found
hidden_binaries = []
for lib_name in hidden_libs:
	lib_file = glob.glob(lib_path + lib_name)[-1]
	hidden_binaries.append((lib_file, '.'))

# Collect GI-repository typelibs
gi_typelib_files = glob.glob(lib_path + 'girepository-*/*.typelib')
for lib_file in gi_typelib_files:
	hidden_binaries.append((lib_file, 'gi_typelibs/'))

sys.path.insert(0, os.path.join(cwd))

modules = glob.glob("gajim/common/modules/*.py")
modules_list = [os.path.basename(f)[:-3] for f in modules if not f.endswith("__init__.py")]
hiddenimports = ['gajim.common.modules.' + m for m in modules_list]

sys.path.pop(0)

a = Analysis(['launch.py'],
             pathex=[cwd],
             binaries=hidden_binaries,
             datas=[('gajim', 'gajim')],
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=['PIL._imagingft'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='launch',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='launch')
app = BUNDLE(coll,
             name='Gajim.app',
             icon=icon,
             info_plist=info_plist,
             bundle_identifier='org.gajim.gajim')
