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

_MIN_NBXMPP_VER = "0.9.91"
_MIN_GTK_VER = "3.22.0"


def _check_required_deps():
    try:
        import nbxmpp
    except ImportError:
        print('Gajim needs python-nbxmpp to run. Quitting…')
        sys.exit(1)

    if V(nbxmpp.__version__) < V(_MIN_NBXMPP_VER):
        print('Gajim needs python-nbxmpp >= %s to run. '
              'Quitting...' % _MIN_NBXMPP_VER)
        sys.exit(1)


def _init_gui(gui):
    if gui == 'GTK':
        _init_gtk()


def _init_gtk():
    import gi
    gi.require_version('GLib', '2.0')
    gi.require_version('Gio', '2.0')
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    gi.require_version('GObject', '2.0')
    gi.require_version('Pango', '1.0')

    from gi.repository import Gtk
    gtk_ver = '%s.%s.%s' % (Gtk.get_major_version(),
                            Gtk.get_minor_version(),
                            Gtk.get_micro_version())
    if V(gtk_ver) < V(_MIN_GTK_VER):
        print('Gajim needs GTK+ >= %s to run. '
              'Quitting...' % _MIN_GTK_VER)
        sys.exit(1)

    from gajim.gtk import exception
    exception.init()

    i18n.initialize_direction_mark()

    from gajim.application import GajimApplication

    # Fix bug in 3.24.1 with flickering tooltips
    if sys.platform in ('darwin', 'win32'):
        settings = Gtk.Settings.get_default()
        settings.set_property('gtk-cursor-theme-size', 16)

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
    if os.name != 'nt':
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def main():
    if sys.platform != 'win32':
        if os.geteuid() == 0:
            sys.exit("You must not launch gajim as root, it is insecure.")

    _check_required_deps()
    _set_proc_title()
    _init_gui('GTK')
