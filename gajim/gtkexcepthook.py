# -*- coding:utf-8 -*-
## gajim/gtkexcepthook.py
##
## Copyright (C) 2016-2018 Philipp Hörist <philipp AT hoerist.com>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
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
import traceback
import threading
import webbrowser
import platform
from io import StringIO
from urllib.parse import urlencode

import nbxmpp
import gajim
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

if __name__ == '__main__':
    glade_file = os.path.join('data', 'gui', 'exception_dialog.ui')
else:
    from gajim.common import configpaths
    glade_file = os.path.join(configpaths.get('GUI'), 'exception_dialog.ui')


_exception_in_progress = threading.Lock()

ISSUE_TEXT = '''## Versions
- OS: {}
- GTK+ Version: {}
- PyGObject Version: {}
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
        builder = Gtk.Builder()
        builder.add_from_file(glade_file)
        self.dialog = builder.get_object("ExceptionDialog")
        builder.connect_signals(self)
        builder.get_object("report_btn").grab_focus()
        self.exception_view = builder.get_object("exception_view")
        buffer_ = self.exception_view.get_buffer()
        trace = StringIO()
        traceback.print_exception(type_, value, tb, None, trace)
        self.text = self.get_issue_text(trace.getvalue())
        buffer_.set_text(self.text)
        self.exception_view.set_editable(False)
        self.dialog.show()

    def on_report_clicked(self, *args):
        issue_url = 'https://dev.gajim.org/gajim/gajim/issues/new'
        params = {'issue[description]': self.text}
        url = '{}?{}'.format(issue_url, urlencode(params))
        webbrowser.open(url, new=2)

    def on_close_clicked(self, *args):
        self.dialog.destroy()

    def get_issue_text(self, traceback_text):
        gtk_ver = '%i.%i.%i' % (
            Gtk.get_major_version(),
            Gtk.get_minor_version(),
            Gtk.get_micro_version())
        gobject_ver = '.'.join(map(str, GObject.pygobject_version))

        return ISSUE_TEXT.format(get_os_info(),
                                 gtk_ver,
                                 gobject_ver,
                                 nbxmpp.__version__,
                                 gajim.__version__,
                                 traceback_text)


def init():
    if os.name == 'nt' or not sys.stderr.isatty():
        sys.excepthook = _hook


def get_os_info():
    if os.name == 'nt' or sys.platform == 'darwin':
        return platform.system() + " " + platform.release()
    elif os.name == 'posix':
        try:
            import distro
            return distro.name(pretty=True)
        except ImportError:
            return platform.system()
    return ''

# this is just to assist testing (python3 gtkexcepthook.py)
if __name__ == '__main__':
    init()
    print(sys.version)
    ExceptionDialog(None, None, None)
    Gtk.main()
