# -*- mode: python ; coding: utf-8 -*-


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
    "wasapi",
]


a = Analysis(
    ['launch.py'],
    pathex=[],
    binaries=[
        ("C:\\msys64\\ucrt64\\bin\\gdbus.exe", "."),
        ("C:\\msys64\\ucrt64\\lib\\enchant-2\\enchant_winspell.dll", "share\\enchant-2"),
    ],
    datas=[
        ("../src/gajim/data", "gajim/data"),
    ],
    hiddenimports=[
        "gi.repository.GdkWin32",
        "gi.repository.Spelling",
    ],
    hookspath=["win/hooks"],
    hooksconfig={
        "gi": {
            "module-versions": {"Gtk": "4.0", "GtkSource": "5"},
        },
        "gstreamer": {
            "include_plugins": gst_include_plugins,
        },
    },
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='launch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='launch',
)
