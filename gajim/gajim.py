# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from typing import Optional

import os
import platform
import signal
import sqlite3
import sys
from ctypes import byref
from ctypes import CDLL
from ctypes import create_string_buffer
from ctypes.util import find_library
from types import FrameType

from packaging.version import Version as V

_MIN_NBXMPP_VER = '4.0.1'
_MIN_GTK_VER = '3.24.30'
_MIN_CAIRO_VER = '1.16.0'
_MIN_PYGOBJECT_VER = '3.42.0'
_MIN_GLIB_VER = '2.60.0'
_MIN_PANGO_VER = '1.50.0'
_MIN_SQLITE_VER = '3.33.0'


def check_version(dep_name: str, current_ver: str, min_ver: str) -> None:
    if V(current_ver) < V(min_ver):
        sys.exit('Gajim needs %s >= %s (found %s) to run. '
                 'Quitting...' % (dep_name, min_ver, current_ver))


def _check_required_deps() -> None:
    error_message = 'Gajim needs %s to run. Quitting… (Error: %s)'

    try:
        import nbxmpp
    except ImportError as error:
        sys.exit(error_message % ('python-nbxmpp', error))

    try:
        import gi
    except ImportError as error:
        sys.exit(error_message % ('pygobject', error))

    try:
        gi.require_versions({'GLib': '2.0',
                             'Gio': '2.0',
                             'Gtk': '3.0',
                             'GtkSource': '4',
                             'GObject': '2.0',
                             'Pango': '1.0',
                             'PangoCairo': '1.0'})
    except ValueError as error:
        sys.exit('Missing dependency: %s' % error)

    try:
        import cairo
    except ImportError as error:
        sys.exit(error_message % ('pycairo', error))

    from gi.repository import Gtk
    gtk_ver = '%s.%s.%s' % (Gtk.get_major_version(),
                            Gtk.get_minor_version(),
                            Gtk.get_micro_version())

    from gi.repository import GLib
    glib_ver = '.'.join(map(str, [GLib.MAJOR_VERSION,
                                  GLib.MINOR_VERSION,
                                  GLib.MICRO_VERSION]))

    from gi.repository import Pango

    check_version('python-nbxmpp', nbxmpp.__version__, _MIN_NBXMPP_VER)
    check_version('pygobject', gi.__version__, _MIN_PYGOBJECT_VER)
    check_version('libcairo', cairo.cairo_version_string(), _MIN_CAIRO_VER)
    check_version('pycairo', cairo.version, _MIN_CAIRO_VER)
    check_version('gtk3', gtk_ver, _MIN_GTK_VER)
    check_version('glib', glib_ver, _MIN_GLIB_VER)
    check_version('pango', Pango.version_string(), _MIN_PANGO_VER)
    check_version('sqlite', sqlite3.sqlite_version, _MIN_SQLITE_VER)


def _init_gui(gui: str) -> None:
    if gui == 'GTK':
        _init_gtk()


def _set_env_vars() -> None:
    # Disable legacy ciphers in cryptography
    os.environ['CRYPTOGRAPHY_OPENSSL_NO_LEGACY'] = '1'

    if sys.platform != 'win32':
        return

    if 'GTK_CSD' in os.environ:
        # Respect user settings
        return

    os.environ['GTK_CSD'] = '0'


def _init_gtk() -> None:
    from gajim.gtk import exception
    exception.init()


def _run_app() -> None:
    from gajim.gtk.application import GajimApplication
    application = GajimApplication()

    def sigint_cb(num: int, stack: Optional[FrameType]) -> None:
        print(' SIGINT/SIGTERM received')
        application.quit()

    # ^C exits the application normally
    signal.signal(signal.SIGINT, sigint_cb)
    signal.signal(signal.SIGTERM, sigint_cb)
    if sys.platform != 'win32':
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    application.run(sys.argv)


def _set_proc_title() -> None:
    sysname = platform.system()
    if sysname in ('Linux', 'FreeBSD', 'OpenBSD', 'NetBSD'):
        libc = CDLL(find_library('c'))

        # The constant defined in <linux/prctl.h> which is used to set the name
        # of the process.
        PR_SET_NAME = 15

        if sysname == 'Linux':
            proc_name = b'gajim'
            buff = create_string_buffer(len(proc_name) + 1)
            buff.value = proc_name
            libc.prctl(PR_SET_NAME, byref(buff), 0, 0, 0)
        elif sysname in ('FreeBSD', 'OpenBSD', 'NetBSD'):
            libc.setproctitle('gajim')


def main() -> None:
    if sys.platform != 'win32':
        if os.geteuid() == 0:
            sys.exit('You must not launch gajim as root, it is insecure.')

    _check_required_deps()
    _set_proc_title()
    _set_env_vars()
    _init_gui('GTK')
    _run_app()
