# -*- coding:utf-8 -*-
## src/gajim.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
##                    Norman Rasmussen <norman AT rasmussen.co.za>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
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

import sys
import os

if '--version' in sys.argv or '-V' in sys.argv:
    from common.defs import version
    print(version)
    sys.exit(0)

WINDEV = False
if '--windev' in sys.argv or '-w' in sys.argv:
    WINDEV = True

if os.name == 'nt' and not WINDEV:
    import warnings
    log_path = os.path.join(os.environ['APPDATA'], 'Gajim')
    if not os.path.exists(log_path):
        os.mkdir(log_path, 0o700)
    log_file = os.path.join(log_path, 'gajim.log')

    class MyStd(object):
        _file = None
        _error = None

        def write(self, text):
            if self._file is None and self._error is None:
                try:
                    self._file = open(log_file, 'a')
                except Exception as details:
                    self._error = details
            if self._file is not None:
                self._file.write(text)
                self._file.flush()

        def flush(self):
            if self._file is not None:
                self._file.flush()

        def isatty(self):
            return False

    outerr = MyStd()
    sys.stdout = outerr
    sys.stderr = outerr
    warnings.filterwarnings(action='ignore')


# Test here for all required versions so we dont have to
# test multiple times in every module. nbxmpp also needs GLib.
import gi
gi.require_version('GLib', '2.0')
gi.require_version('Gio', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GObject', '2.0')
gi.require_version('Pango', '1.0')

MIN_NBXMPP_VER = "0.5.3"

try:
    import nbxmpp
except ImportError:
    print('Gajim needs python-nbxmpp to run. Quiting...')
    sys.exit(1)

from distutils.version import LooseVersion as V
if V(nbxmpp.__version__) < V(MIN_NBXMPP_VER):
    print('Gajim needs python-nbxmpp >= %s to run. Quiting...' % MIN_NBXMPP_VER)
    sys.exit(1)

from application import GajimApplication

app = GajimApplication()
app.run(sys.argv)
