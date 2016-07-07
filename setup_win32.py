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
import site

site_dir = site.getsitepackages()[1]
include_dll_path = os.path.join(site_dir, "gnome")
sys.path.append('src')

# Collect the list of missing dll when cx_freeze builds the app
missing_dll = ['libgtk-3-0.dll',
               'libgdk-3-0.dll',
               'libatk-1.0-0.dll',
               'libcairo-gobject-2.dll',
               'libgdk_pixbuf-2.0-0.dll',
               'libjpeg-8.dll',
               'libpango-1.0-0.dll',
               'libpangocairo-1.0-0.dll',
               'libpangoft2-1.0-0.dll',
               'libpangowin32-1.0-0.dll',
               'libgnutls-26.dll',
               'libp11-kit-0.dll',
               'libaerial-0.dll',
'libgstrtp-1.0-0.dll',
'libcurl-4.dll',
'libgstrtsp-1.0-0.dll',
'libdb-4.8.dll',
'libgstrtspserver-1.0-0.dll',
'libfarstream-0.2-2.dll',
'libgstsdp-1.0-0.dll',
'libfftw3.dll',
'libgsttag-1.0-0.dll',
'libfluidsynth-1.dll',
'libgsturidownloader-1.0-0.dll',
'libgraphene-1.0-0.dll',
'libgstvalidate-1.0-0.dll',
'libgssdp-1.0-3.dll',
'libgstvalidate-default-overrides-1.0-0.dll',
'libgstallocators-1.0-0.dll',
'libgstvideo-1.0-0.dll',
'libgstapp-1.0-0.dll',
'libgupnp-1.0-4.dll',
'libgstaudio-1.0-0.dll',
'libgupnp-igd-1.0-4.dll',
'libgstbadbase-1.0-0.dll',
'libidn-11.dll',
'libgstbadvideo-1.0-0.dll',
'libjack.dll',
'libgstbase-1.0-0.dll',
'libjasper-1.dll',
'libgstbasecamerabinsrc-1.0-0.dll',
'libnice-10.dll',
'libgstcheck-1.0-0.dll',
'libnotify-4.dll',
'libgstcodecparsers-1.0-0.dll',
'libopenexr-2.dll',
'libgstcontroller-1.0-0.dll',
'libopenjp2.dll',
'libgstfft-1.0-0.dll',
'liborc-0.4-0.dll',
'libgstgl-1.0-0.dll',
'liborc-test-0.4-0.dll',
'libgstinsertbin-1.0-0.dll',
'libproxy.dll',
'libgstmpegts-1.0-0.dll',
'librsvg-2-2.dll',
'libgstnet-1.0-0.dll',
'libsoup-2.4-1.dll',
'libgstpbutils-1.0-0.dll',
'libsqlite3-0.dll',
'libgstphotography-1.0-0.dll',
'libvisual-0.4-0.dll',
'libgstreamer-1.0-0.dll',
'libwebp-5.dll',
'libgstriff-1.0-0.dll',
]

# We need to add all the libraries too (for themes, etc..)
gtk_libs = {
 'etc': ['dbus-1', 'fonts', 'gtk-3.0', 'pango'],
 'lib': ['aspell-0.60', 'enchant', 'farstream-0.2', 'gdbus-2.0', 'gdk-pixbuf-2.0', 'gio', 'girepository-1.0', 'gobject-introspection', 'gstreamer-1.0', 'gtk-3.0', 'libcanberra-0.30'],
 'share': ['dbus-1', 'enchant', 'farstream', 'fonts', 'gir-1.0', 'glib-2.0', 'gobject-introspection-1.0', 'gst-plugins-bad', 'gst-plugins-base', 'gstreamer-1.0', 'gupnp-av', 'gupnp-dlna-2.0', 'icons', 'ssl', 'themes', 'xml'],
}

# Create the list of includes as cx_freeze likes
include_files = []
for dll in missing_dll:
    include_files.append((os.path.join(include_dll_path, dll), dll))
  
# Let's add gtk libraries folders and files
for folder in gtk_libs:
    for lib in gtk_libs[folder]:
        folder_lib = os.path.join(folder, lib)
        include_files.append((os.path.join(include_dll_path, folder_lib), folder_lib))
# Let's add gtk locales that we support in Gajim
for language in next(os.walk('po'))[1]:
    target_dir = os.path.join('share', 'locale', language)
    language_dir = os.path.join(include_dll_path, target_dir)
    if os.path.isdir(language_dir):
        include_files.append((language_dir, target_dir))

options = {
    'build_exe': {
        'compressed': False,
        'includes': ['gi', 'Crypto.PublicKey.DSA', 'Crypto.Hash.HMAC',
            'numbers', 'win32com.client', 'win32com.server'
        ],
        'packages': ['gi', 'cffi', 'cryptography'],
        'base': 'Win32GUI',
        'include_files': include_files,
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
    options=options,
    executables=[Executable('src/gajim.py', icon='data/pixmaps/gajim.ico'),
		Executable('src/history_manager.py', icon='data/pixmaps/gajim.ico')],
)
