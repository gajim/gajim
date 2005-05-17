## setup_win32.py (run me as python setup_win32.py py2exe)
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2005 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

'''
import sys

try:
    import modulefinder
    import win32com
    for p in win32com.__path__[1:]:
        modulefinder.AddPackagePath("win32com", p)
    for extra in ["win32com.shell"]: #,"win32com.mapi"
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    # no build path setup, no worries.
    pass
'''

from distutils.core import setup
import py2exe
import glob

includes = ['encodings', 'encodings.utf-8',]

opts = {
    'py2exe': {
        'includes': 'pango,atk,gobject,plugins,plugins.gtkgui,plugins.logger,encodings,encodings.*',
        'dll_excludes': [
            'iconv.dll','intl.dll','libatk-1.0-0.dll',
            'libgdk_pixbuf-2.0-0.dll','libgdk-win32-2.0-0.dll',
            'libglib-2.0-0.dll','libgmodule-2.0-0.dll',
            'libgobject-2.0-0.dll','libgthread-2.0-0.dll',
            'libgtk-win32-2.0-0.dll','libpango-1.0-0.dll',
            'libpangowin32-1.0-0.dll'
        ],
        'optimize': '2', # python -OO
    }
}

setup(
    name = 'Gajim',
    version = '0.7',
    description = 'A Jabber client written in PyGTK',
    windows = [{'script': 'src/gajim.py',
                'icon_resources': [(1, 'gajim.ico')]}],
    options=opts,

# one can just copy src and data folder in the target_dir so one doesn't have to hack this
#    data_files=[('src/', glob.glob('src/gtkgui.glade')),
#                ('data/icons/sun', glob.glob('data/icons/sun/*.*')),
#                ('data/emoticons', glob.glob('data/emoticons/*.*')),
#                ('data/pixmaps', glob.glob('data/pixmaps/*.*')),
#                ('sounds', glob.glob('data/sounds/*.*')),
#                ('Messages/fr/LC_MESSAGES', glob.glob('Messages/fr/LC_MESSAGES/*.mo'))
#    ],
)
