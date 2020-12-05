# Copyright (C) 2016-2018 Philipp Hörist <philipp AT hoerist.com>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
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

import sys
import os
import traceback
import threading
import webbrowser
import platform
from io import StringIO
from urllib.parse import urlencode

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import GLib

import nbxmpp

import gajim
from gajim.common import configpaths
from .util import get_builder


_exception_in_progress = threading.Lock()

ISSUE_TEXT = '''## Versions
- OS: {}
- GTK Version: {}
- PyGObject Version: {}
- GLib Version : {}
- python-nbxmpp Version: {}
- Gajim Version: {}

## Traceback
```
{}
```
## Steps to reproduce the problem
...'''


def _hook(type_, value, tb):
    if not _exception_in_progress.acquire(False):
        # Exceptions have piled up, so we use the default exception
        # handler for such exceptions
        sys.__excepthook__(type_, value, tb)
        return

    ExceptionDialog(type_, value, tb)
    _exception_in_progress.release()


class ExceptionDialog():
    def __init__(self, type_, value, tb):
        path = configpaths.get('GUI') / 'exception_dialog.ui'
        self._ui = get_builder(path.resolve())
        self._ui.connect_signals(self)

        self._ui.report_btn.grab_focus()

        buffer_ = self._ui.exception_view.get_buffer()
        trace = StringIO()
        traceback.print_exception(type_, value, tb, None, trace)
        self.text = self.get_issue_text(trace.getvalue())
        buffer_.set_text(self.text)
        print(self.text, file=sys.stderr)

        self._ui.exception_view.set_editable(False)
        self._ui.exception_dialog.show()

    def on_report_clicked(self, *args):
        issue_url = 'https://dev.gajim.org/gajim/gajim/issues/new'
        params = {'issue[description]': self.text}
        url = '{}?{}'.format(issue_url, urlencode(params))
        webbrowser.open(url, new=2)

    def on_close_clicked(self, *args):
        self._ui.exception_dialog.destroy()

    @staticmethod
    def get_issue_text(traceback_text):
        gtk_ver = '%i.%i.%i' % (
            Gtk.get_major_version(),
            Gtk.get_minor_version(),
            Gtk.get_micro_version())
        gobject_ver = '.'.join(map(str, GObject.pygobject_version))
        glib_ver = '.'.join(map(str, [GLib.MAJOR_VERSION,
                                      GLib.MINOR_VERSION,
                                      GLib.MICRO_VERSION]))

        return ISSUE_TEXT.format(get_os_info(),
                                 gtk_ver,
                                 gobject_ver,
                                 glib_ver,
                                 nbxmpp.__version__,
                                 gajim.__version__,
                                 traceback_text)


def init():
    if os.name == 'nt' or not sys.stderr.isatty():
        sys.excepthook = _hook


def get_os_info():
    if os.name == 'nt' or sys.platform == 'darwin':
        return platform.system() + " " + platform.release()
    if os.name == 'posix':
        try:
            import distro
            return distro.name(pretty=True)
        except ImportError:
            return platform.system()
    return ''
