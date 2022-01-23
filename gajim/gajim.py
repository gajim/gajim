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

from types import FrameType
from typing import Optional

import os
import sys
import signal
import platform
from ctypes import CDLL, byref, create_string_buffer
from ctypes.util import find_library
from packaging.version import Version as V

import gajim.gui
from gajim.common import i18n


_MIN_NBXMPP_VER = '2.99.0'
_MIN_GTK_VER = '3.22.27'
_MIN_CAIRO_VER = '1.16.0'
_MIN_PYGOBJECT_VER = '3.32.0'
_MIN_GLIB_VER = '2.60.0'


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
                             'Soup': '2.4'})
    except ValueError as error:
        sys.exit('Missing dependency: %s' % error)

    try:
        import cairo
    except ImportError as error:
        sys.exit(error_message % ('python-cairo', error))

    from gi.repository import Gtk
    gtk_ver = '%s.%s.%s' % (Gtk.get_major_version(),
                            Gtk.get_minor_version(),
                            Gtk.get_micro_version())

    from gi.repository import GLib
    glib_ver = '.'.join(map(str, [GLib.MAJOR_VERSION,
                                  GLib.MINOR_VERSION,
                                  GLib.MICRO_VERSION]))

    check_version('python-nbxmpp', nbxmpp.__version__, _MIN_NBXMPP_VER)
    check_version('pygobject', gi.__version__, _MIN_PYGOBJECT_VER)
    check_version('libcairo', cairo.cairo_version_string(), _MIN_CAIRO_VER)
    check_version('python-cairo', cairo.version, _MIN_CAIRO_VER)
    check_version('gtk3', gtk_ver, _MIN_GTK_VER)
    check_version('glib', glib_ver, _MIN_GLIB_VER)


def _init_gui(gui: str) -> None:
    if gui == 'GTK':
        _init_gtk()


def _disable_csd() -> None:
    if sys.platform != 'win32':
        return

    if 'GTK_CSD' in os.environ:
        # Respect user settings
        return

    os.environ['GTK_CSD'] = '0'


def _init_gtk() -> None:
    gajim.gui.init('gtk')

    from gajim.gui import exception
    exception.init()

    i18n.initialize_direction_mark()


def _run_app() -> None:
    from gajim.gui.application import GajimApplication
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
            buff = create_string_buffer(len(proc_name)+1)
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
    _disable_csd()
    _init_gui('GTK')
    _run_app()
