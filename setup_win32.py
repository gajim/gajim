from distutils.core import setup
import py2exe
import glob

includes = ["encodings",
            "encodings.utf-8",]

opts = {
    "py2exe": {
        "includes": "pango,atk,gobject,plugins,plugins.gtkgui,plugins.logger,encodings,encodings.*",
        "dll_excludes": [
            "iconv.dll","intl.dll","libatk-1.0-0.dll",
            "libgdk_pixbuf-2.0-0.dll","libgdk-win32-2.0-0.dll",
            "libglib-2.0-0.dll","libgmodule-2.0-0.dll",
            "libgobject-2.0-0.dll","libgthread-2.0-0.dll",
            "libgtk-win32-2.0-0.dll","libpango-1.0-0.dll",
            "libpangowin32-1.0-0.dll"
        ],
    }
}

setup(
    name = "Gajim",
    description = "A jabber client",
#    console=["runCore.py"],
    windows = [{"script": "runCore.py"}],
    options=opts,
    data_files=[("plugins/gtkgui", glob.glob("plugins/gtkgui/gtkgui.glade")),
                ("plugins/gtkgui/icons/sun", glob.glob("plugins/gtkgui/icons/sun/*.*")),
                ("Messages/fr/LC_MESSAGES", glob.glob("Messages/fr/LC_MESSAGES/*.mo"))
    ],
)
