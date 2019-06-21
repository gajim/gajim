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

import os
import time

from gi.repository import Gtk
from gi.repository import GLib

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _

from gajim.gtk.util import get_builder


class HTTPUploadProgressWindow(Gtk.ApplicationWindow):
    def __init__(self, file):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('HTTPUploadProgressWindow')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('File Transfer'))

        self.event = file.event
        self.file = file
        self._ui = get_builder('httpupload_progress_dialog.ui')
        file_name = os.path.basename(file.path)
        self._ui.file_name_label.set_text(file_name)
        self._start_time = time.time()

        self.add(self._ui.box)

        self.pulse = GLib.timeout_add(100, self._pulse_progressbar)
        self.show_all()

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)
        app.ged.register_event_handler('httpupload-progress', ged.CORE,
                                       self._on_httpupload_progress)

    def _on_httpupload_progress(self, obj):
        if self.file != obj.file:
            return

        if obj.status == 'request':
            self._ui.label.set_text(_('Requesting HTTP File Upload Slot…'))
        elif obj.status == 'close':
            self.destroy()
        elif obj.status == 'upload':
            self._ui.label.set_text(_('Uploading via HTTP File Upload…'))
        elif obj.status == 'update':
            self._update_progress(obj.seen, obj.total)
        elif obj.status == 'encrypt':
            self._ui.label.set_text(_('Encrypting file…'))

    def _pulse_progressbar(self):
        self._ui.progressbar.pulse()
        return True

    def _on_cancel_upload_button_clicked(self, widget):
        self.destroy()

    def _on_destroy(self, *args):
        self.event.set()
        if self.pulse:
            GLib.source_remove(self.pulse)
        app.ged.remove_event_handler('httpupload-progress', ged.CORE,
                                     self._on_httpupload_progress)

    def _update_progress(self, seen, total):
        if self.event.isSet():
            return
        if self.pulse:
            GLib.source_remove(self.pulse)
            self.pulse = None

        size_total = round(total / (1024 * 1024), 1)
        size_progress = round(seen / (1024 * 1024), 1)

        time_now = time.time()
        mbytes_sec = round(size_progress / (time_now - self._start_time), 1)
        eta = self._format_eta(
            round((size_total - size_progress) / mbytes_sec))

        self._ui.progressbar.set_fraction(float(seen) / total)

        self._ui.progress_label.set_text(
            _('%(progress)s of %(total)s MiB') % {
                'progress': str(size_progress),
                'total': str(size_total)})

        self._ui.speed_label.set_text(_('%s MiB/s') % str(mbytes_sec))
        self._ui.eta_label.set_text(str(eta))

    def _format_eta(self, time_):
        times = {'minutes': 0, 'seconds': 0}
        time_ = int(time_)
        times['seconds'] = time_ % 60
        if time_ >= 60:
            time_ /= 60
            times['minutes'] = time_ % 60

        return _('%(minutes)s min %(seconds)s sec') % times
