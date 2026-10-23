# -*- mode: python ; coding: utf-8 -*-

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

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
    "typefindfunctions",
    "videoconvertscale",
    "videofilter",
    "videoparsersbad",
    "videotestsrc",
    "volume",
    "vpx",
    "wasapi",
    "wavenc",
    "wavparse",
    "webp",
    "ximagesrc",
]


a = Analysis(
    ['launch.py'],
    binaries=[
        ("C:\\msys64\\ucrt64\\lib\\enchant-2\\enchant_winspell.dll", "lib\\enchant-2"),
    ],
    datas=[  # typos: ignore
        ("../../src/gajim/data", "gajim/data"),
    ],
    hooksconfig={
        "gi": {
            "module-versions": {"Gtk": "4.0", "GtkSource": "5"},
        },
        "gstreamer": {
            "include_plugins": gst_include_plugins,
        },
    },
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    console=True,
    debug=False,
    disable_windowed_traceback=False,
    exclude_binaries=True,
    icon="gajim.ico",
    name="Gajim",
    strip=False,
    upx=False,
    version="version.txt"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,  # typos: ignore
    strip=False,
    upx=False,
    name="win",
)
