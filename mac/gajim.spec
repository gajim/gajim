# -*- mode: python -*-

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import typing

import glob
import os

if typing.TYPE_CHECKING:
    from PyInstaller.building.api import EXE, PYZ, COLLECT
    from PyInstaller.building.build_main import Analysis


modules = glob.glob("../src/gajim/common/modules/*.py")
modules_list = [
    os.path.basename(f)[:-3] for f in modules if not f.endswith("__init__.py")
]
hiddenimports = ["gajim.common.modules." + m for m in modules_list]

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
    pathex=[os.getcwd()],
    datas=[("../src/gajim", "gajim")],  # typos: ignore
    hiddenimports=hiddenimports,
    hookspath=["hooks"],
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
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="launch"  # typos: ignore
)

app = BUNDLE(  # type: ignore
    coll,
    name="Gajim.app",
    icon="Gajim.icns",
    info_plist={
        "CFBundleDisplayName": "Gajim",
        "NSHighResolutionCapable": True,
        "CFBundleURLTypes": [
            {"CFBundleURLName": "XMPP URI", "CFBundleURLSchemes": ["xmpp"]}
        ],
        "NSUIElement": True,
    },
    bundle_identifier="org.gajim.gajim",
)
