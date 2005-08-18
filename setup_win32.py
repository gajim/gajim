## setup_win32.py (run me as python setup_win32.py py2exe)
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
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

from distutils.core import setup
import py2exe
import glob
import sys

sys.path.append('src')
includes = ['encodings', 'encodings.utf-8',]

opts = {
    'py2exe': {
        'includes': 'pango,atk,gobject,encodings,encodings.*',
        'dll_excludes': [
            'iconv.dll','intl.dll','libatk-1.0-0.dll',
            'libgdk_pixbuf-2.0-0.dll','libgdk-win32-2.0-0.dll',
            'libglib-2.0-0.dll','libgmodule-2.0-0.dll',
            'libgobject-2.0-0.dll','libgthread-2.0-0.dll',
            'libgtk-win32-2.0-0.dll','libpango-1.0-0.dll',
            'libpangowin32-1.0-0.dll'
        ],
    }
}

setup(
    name = 'Gajim',
    version = '8',
    description = 'A Jabber client written in PyGTK',
    windows = [{'script': 'src/gajim.py',
                'icon_resources': [(1, 'data/pixmaps/gajim.ico')]}],
    options=opts,

    data_files=[('.', glob.glob('src/gtkgui.glade')),
    ],
)
