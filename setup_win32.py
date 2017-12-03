## setup_win32.py (run me as python setup_win32.py build_exe)
##
## Copyright (C) 2003-2017 Yann Leboulanger <asterix AT lagaule.org>
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
import sys

sys.path.append('src')
# Use local gtk folder instead of the one in PATH that is not latest gtk
# if 'gtk' in os.listdir('.'):
#     sys.path.append('gtk/bin')

# probably not necessary anymore
# includes 'dumbdbm', 'dbhash', 'bsddb',
# 'gtk.keysyms', 'goocanvas' 'numbers', 'HTMLParser'

options = {
   'build_exe': {
        'includes': ['new', 'win32com.server', 'win32com.client', 'HTMLParser'],
        'packages': ['pkg_resources', 'cffi', 'gtk',
                     'cryptography', 'Crypto', 'PIL', 'qrcode',
                     'axolotl', 'google', 'common', 'keyring'],
        'excludes': ['Tkinter', 'unittest', 'psutil'],
   }
}


setup(
    name='Gajim',
    version='0.16.9',
    description='A full featured Jabber client',
    author='Gajim Development Team',
    url='http://gajim.org/',
    download_url='http://gajim.org/downloads.php',
    license='GPL',
    options=options,
    executables=[
        Executable(
            'src/gajim.py', base='Win32GUI',
            icon='data/pixmaps/gajim.ico'),
        Executable(
            'src/history_manager.py', base='Win32GUI',
            icon='data/pixmaps/gajim.ico')],
)
