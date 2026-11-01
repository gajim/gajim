# -*- mode: python ; coding: utf-8 -*-

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path
import subprocess

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


CWD = Path.cwd().resolve()
UCRT64_DIR = subprocess.check_output(["cygpath", "-w", os.environ["MSYSTEM_PREFIX"]], text=True).strip()


a = Analysis(
    ['launch.py'],
    binaries=[
        (f"{UCRT64_DIR}/lib/enchant-2/enchant_winspell.dll", "lib/enchant-2"),
    ],
    datas=[  # typos: ignore
        (f"{CWD}/src/gajim/data", "gajim/data"),
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
