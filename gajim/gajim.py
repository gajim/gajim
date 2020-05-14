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


import os
import sys
import signal
import platform
from ctypes import CDLL, byref, create_string_buffer
from ctypes.util import find_library
from distutils.version import LooseVersion as V

from gajim.common import i18n

_MIN_NBXMPP_VER = '0.9.94'
_MIN_GTK_VER = '3.22.27'
_MIN_CAIRO_VER = '1.16.0'
_MIN_PYGOBJECT_VER = '3.32.0'


def check_version(dep_name, current_ver, min_ver):
    if V(current_ver) < V(min_ver):
        sys.exit('Gajim needs %s >= %s to run. '
                 'Quitting...' % (dep_name, min_ver))


def _check_required_deps():
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

    check_version('python-nbxmpp', nbxmpp.__version__, _MIN_NBXMPP_VER)
    check_version('pygobject', gi.__version__, _MIN_PYGOBJECT_VER)
    check_version('libcairo', cairo.cairo_version_string(), _MIN_CAIRO_VER)
    check_version('python-cairo', cairo.version, _MIN_CAIRO_VER)
    check_version('gtk3', gtk_ver, _MIN_GTK_VER)


def _init_gui(gui):
    if gui == 'GTK':
        _init_gtk()


def _disable_csd():
    if sys.platform != 'win32':
        return

    if 'GTK_OSD' in os.environ:
        # Respect user settings
        return

    os.environ['GTK_CSD'] = '0'


def _init_gtk():
    from gajim.gtk import exception
    exception.init()

    i18n.initialize_direction_mark()

    from gajim.application import GajimApplication

    application = GajimApplication()
    _install_sginal_handlers(application)
    application.run(sys.argv)


def _set_proc_title():
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


def _install_sginal_handlers(application):
    def sigint_cb(num, stack):
        print('SIGINT/SIGTERM received')
        application.quit()
    # ^C exits the application normally
    signal.signal(signal.SIGINT, sigint_cb)
    signal.signal(signal.SIGTERM, sigint_cb)
    if sys.platform != 'win32':
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def main():
    if sys.platform != 'win32':
        if os.geteuid() == 0:
            sys.exit('You must not launch gajim as root, it is insecure.')

    _check_required_deps()
    _set_proc_title()
    _disable_csd()
    _init_gui('GTK')
