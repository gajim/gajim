# -*- coding:utf-8 -*-
## src/gtkexcepthook.py
##
## Copyright (C) 2016 Philipp Hörist <philipp AT hoerist.com>
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
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from io import StringIO
from gajim.common import configpaths

glade_file = os.path.join(configpaths.get('GUI'), 'exception_dialog.ui')

_exception_in_progress = threading.Lock()


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
        buffer_.set_text(trace.getvalue())
        self.exception_view.set_editable(False)
        self.dialog.run()

    def on_report_clicked(self, *args):
        url = 'https://dev.gajim.org/gajim/gajim/issues'
        webbrowser.open(url, new=2)

    def on_close_clicked(self, *args):
        self.dialog.destroy()


def init():
    # gdb/kdm etc if we use startx this is not True
    if os.name == 'nt' or not sys.stderr.isatty():
        # FIXME: maybe always show dialog?
        sys.excepthook = _hook

# this is just to assist testing (python gtkexcepthook.py)
if __name__ == '__main__':
    init()
    print(sys.version)
    raise Exception()
