## setup_win32.py (run me as python setup_win32.py py2exe -O2)
##
## Copyright (C) 2003-2007 Yann Leboulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from distutils.core import setup
import py2exe
import glob
import sys
import os

sys.path.append('src')
# Use local gtk folder instead of the one in PATH that is not latest gtk
if 'gtk' in os.listdir('.'):
    sys.path.append('gtk/bin')
includes = ['encodings', 'encodings.utf-8',]

opts = {
    'py2exe': {
        'includes': 'pango,atk,gobject,cairo,pangocairo,gtk.keysyms,encodings,encodings.*', #',docutils.readers.*,docutils.writers.html4css1',
        'dll_excludes': [
            'iconv.dll','intl.dll','libatk-1.0-0.dll',
            'libgdk_pixbuf-2.0-0.dll','libgdk-win32-2.0-0.dll',
            'libglib-2.0-0.dll','libgmodule-2.0-0.dll',
            'libgobject-2.0-0.dll','libgthread-2.0-0.dll',
            'libgtk-win32-2.0-0.dll','libpango-1.0-0.dll',
            'libpangowin32-1.0-0.dll','libcairo-2.dll',
            'libpangocairo-1.0-0.dll','libpangoft2-1.0-0.dll',
        ],
    }
}

setup(
    name = 'Gajim',
    version = '0.11.4.4-svn',
    description = 'A full featured Jabber client',
    author = 'Gajim Development Team',
    url = 'http://www.gajim.org/',
    download_url = 'http://www.gajim.org/downloads.php',
    license = 'GPL',
    
    windows = [{'script': 'src/gajim.py',
                'icon_resources': [(1, 'data/pixmaps/gajim.ico')]},
               {'script': 'src/history_manager.py',
                'icon_resources': [(1, 'data/pixmaps/gajim.ico')]}],
    options=opts,

    data_files=[('.', glob.glob('src/gtkgui.glade')),
                ('.', glob.glob('src/history_manager.glade')),
    ],
)
