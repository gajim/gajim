# setup_win32.py (run me as python setup_win32.py py2exe -O2)
#
# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.
#


import sys
import os
import site
from cx_Freeze import setup, Executable

SITEDIR = site.getsitepackages()[1]
INCLUDE_DLL_PATH = os.path.join(SITEDIR, "gnome")
sys.path.append('src')

# Collect the list of missing dll when cx_freeze builds the app

MISSING_DLL = ['libgtk-3-0.dll',
               'libgdk-3-0.dll',
               'libatk-1.0-0.dll',
               'libgdk_pixbuf-2.0-0.dll',
               'libjpeg-8.dll',
               'libpango-1.0-0.dll',
               'libpangocairo-1.0-0.dll',
               'libpangoft2-1.0-0.dll',
               'libpangowin32-1.0-0.dll',
               'libgnutls-28.dll',
               'libp11-kit-0.dll',
               'libgstrtp-1.0-0.dll',
               'libgstrtsp-1.0-0.dll',
               'libgstrtspserver-1.0-0.dll',
               'libfarstream-0.2-5.dll',
               'libgstsdp-1.0-0.dll',
               'libgsttag-1.0-0.dll',
               'libgssdp-1.0-3.dll',
               'libgstvideo-1.0-0.dll',
               'libgstapp-1.0-0.dll',
               'libgupnp-1.0-4.dll',
               'libgstaudio-1.0-0.dll',
               'libgupnp-igd-1.0-4.dll',
               'libgstbase-1.0-0.dll',
               'libnice-10.dll',
               'librsvg-2-2.dll',
               'libvisual-0.4-0.dll',
               'libwebp-5.dll',
               'libgstriff-1.0-0.dll',
               'libepoxy-0.dll',
               'libharfbuzz-0.dll',
               'libtiff-5.dll',
               'libjasper-1.dll',
               'libgstpbutils-1.0-0.dll',
               'liborc-0.4-0.dll',
               'libgstnet-1.0-0.dll',
               'libsoup-2.4-1.dll',
               'liborc-test-0.4-0.dll',
               'libavcodec-57.dll',
               'libavutil-55.dll',
               'libswresample-2.dll',
               'libavformat-57.dll',
               'libavfilter-6.dll',
               'libgssapi-3.dll',
               'libopenssl.dll',
               'libsqlite3-0.dll',
               'libproxy.dll',
               'libstdc++.dll',
               'libgstfft-1.0-0.dll']


# We need to add all the libraries too (for themes, etc..)
GTK_LIBS = {
    'etc': ['dbus-1', 'fonts', 'gtk-3.0', 'pango'],
    'lib': ['farstream-0.2', 'gdbus-2.0',
            'gdk-pixbuf-2.0', 'gio', 'girepository-1.0',
            'gstreamer-1.0', 'gtk-3.0'],
    'share': ['dbus-1', 'farstream', 'fonts',
              'glib-2.0',
              'gst-plugins-base', 'gstreamer-1.0', 'gupnp-av',
              'gupnp-dlna-2.0', 'icons', 'ssl', 'themes', 'xml']
}


# share 'gobject-introspection-1.0'
# , 'enchant' 'gir-1.0',


#lib 'gobject-introspection'
# 'aspell-0.60', 'enchant',  'gst-plugins-bad',


# Create the list of includes as cx_freeze likes
INCLUDE_FILES = []
for dll in MISSING_DLL:
    INCLUDE_FILES.append((os.path.join(INCLUDE_DLL_PATH, dll), dll))

# Let's add gtk libraries folders and files
for folder in GTK_LIBS:
    for lib in GTK_LIBS[folder]:
        folder_lib = os.path.join(folder, lib)
        INCLUDE_FILES.append((os.path.join(INCLUDE_DLL_PATH, folder_lib),
                              folder_lib))

#Let's add gtk locales that we support in Gajim
for language in next(os.walk('po'))[1]:
    target_dir = os.path.join('share', 'locale', language)
    language_dir = os.path.join(INCLUDE_DLL_PATH, target_dir)
    if os.path.isdir(language_dir):
        INCLUDE_FILES.append((language_dir, target_dir))

OPTIONS = {
    'build_exe': {
        'compressed': False,
        'includes': ['gi', 'Crypto.PublicKey.DSA', 'Crypto.Hash.HMAC',
                     'numbers', 'win32com.client', 'win32com.server',
                     'cryptography', 'pkg_resources'],
        'packages': ['gi', 'cffi', 'cryptography', 'google', 'axolotl',
                     'pkg_resources'],
        'base': 'Win32GUI',
        'include_files': INCLUDE_FILES,
    }
}


setup(
    name='Gajim',
    version='0.16.10',
    description='A full featured Jabber client',
    author='Gajim Development Team',
    url='http://gajim.org/',
    download_url='http://gajim.org/downloads.php',
    license='GPL',
    options=OPTIONS,
    executables=[Executable('src/gajim.py', icon='data/pixmaps/gajim.ico')],
)
