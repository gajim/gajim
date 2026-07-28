# -*- mode: python -*-

import typing

import sys
import glob
import os

if typing.TYPE_CHECKING:
    from PyInstaller.building.api import EXE, PYZ, COLLECT
    from PyInstaller.building.build_main import Analysis


cwd = os.getcwd()
icon = os.path.join(cwd, "mac", "Gajim.icns")
block_cipher = None

info_plist = {
    "CFBundleDisplayName": "Gajim",
    "NSHighResolutionCapable": True,
    "CFBundleURLTypes": [
        {"CFBundleURLName": "XMPP URI", "CFBundleURLSchemes": ["xmpp"]}
    ],
    "NSUIElement": True,
}

sys.path.insert(0, os.path.join(cwd))

modules = glob.glob("gajim/common/modules/*.py")
modules_list = [
    os.path.basename(f)[:-3] for f in modules if not f.endswith("__init__.py")
]
hiddenimports = ["gajim.common.modules." + m for m in modules_list]

sys.path.pop(0)

gst_include_plugins = [
    "app",
    "applemedia",
    "audioconvert",
    "audiofx",
    "audioparsers",
    "audioresample",
    "audiotestsrc",
    "autodetect",
    "base",
    "coreelements",
    "flac",
    "gtk4",
    "id3demux",
    "isomp4",
    "level",
    "matroska",
    "mpg123",
    "ogg",
    "opengl",
    "opus",
    "osxaudio",
    "playback",
    "png",
    "videoconvertscale",
    "videofilter",
    "videoparsersbad",
    "videotestsrc",
    "volume",
    "vpx",
    "wavenc",
    "wavparse",
    "webp",
    "ximagesrc",
]

a = Analysis(
    ["launch.py"],
    pathex=[cwd],
    datas=[("gajim", "gajim")],
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(os.getcwd(), "mac", "hooks")],
    hooksconfig={
        "gi": {
            "module-versions": {"Gtk": "4.0", "GtkSource": "5"},
        },
        "gstreamer": {
            "include_plugins": gst_include_plugins,
        },
    },
    runtime_hooks=[],
    excludes=["PIL._imagingft"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="launch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="launch"
)

app = BUNDLE(  # pyright: ignore
    coll,
    name="Gajim.app",
    icon=icon,
    info_plist=info_plist,
    bundle_identifier="org.gajim.gajim",
)
