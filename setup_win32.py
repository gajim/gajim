## setup_win32.py (run me as python setup_win32.py py2exe -O2)
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from cx_Freeze import setup, Executable
import glob
import sys
import os

sys.path.append('src')
# Use local gtk folder instead of the one in PATH that is not latest gtk
if 'gtk' in os.listdir('.'):
    sys.path.append('gtk/bin')

options = {
   'build_exe': {
       'includes': ['Gdk.KEY_, 'dumbdbm', 'dbhash', 'bsddb', 'new',
            'goocanvas', 'Crypto.PublicKey.DSA', 'Crypto.Hash.HMAC',
            'numbers', 'win32com.client', 'win32com.server', 'HTMLParser'],
       'base': 'Win32GUI',
	   'bin_excludes': [
            'iconv.dll', 'intl.dll', 'libatk-1.0-0.dll',
            'libgdk_pixbuf-2.0-0.dll', 'libgdk-win32-2.0-0.dll',
			'libgio-2.0-0.dll',
            'libglib-2.0-0.dll', 'libgmodule-2.0-0.dll',
            'libgobject-2.0-0.dll', 'libgthread-2.0-0.dll',
            'libgtk-win32-2.0-0.dll', 'libpango-1.0-0.dll',
            'libpangowin32-1.0-0.dll', 'libcairo-2.dll',
            'libpangocairo-1.0-0.dll', 'libpangoft2-1.0-0.dll',
            'libfarstream-0.1-0.dll', 'libgcc_s_dw2-1.dll',
            'libgstbase-0.10-0.dll', 'libgstcontroller-0.10-0.dll',
            'libgstdataprotocol-0.10-0.dll', 'libgstinterfaces-0.10-0.dll',
            'libgstnet-0.10-0.dll', 'libgstreamer-0.10-0.dll',
            'libiconv-2.dll', 'libxml2.dll', 'libxml2-2.dll',
        ],
   }
}


setup(
    name='Gajim',
    version='0.15.1',
    description='A full featured Jabber client',
    author='Gajim Development Team',
    url='http://gajim.org/',
    download_url='http://gajim.org/downloads.php',
    license='GPL',
    options=options,
    executables=[Executable('src/gajim.py', icon='data/pixmaps/gajim.ico'),
		Executable('src/history_manager.py', icon='data/pixmaps/gajim.ico')],
)
