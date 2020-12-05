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

import time

from gi.repository import Gtk
from gi.repository import GLib

from gajim.common import app
from gajim.common.i18n import _

from .util import get_builder
from .util import EventHelper


class FileTransferProgress(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, transfer):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_name('FileTransferProgress')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('File Transfer'))

        self._destroyed = False
        self._transfer = transfer
        self._transfer.connect('state-changed', self._on_transfer_state_change)
        self._transfer.connect('progress', self._on_transfer_progress)

        if app.settings.get('use_kib_mib'):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._start_time = time.time()

        self._ui = get_builder('filetransfer_progress.ui')
        self._ui.file_name_label.set_text(transfer.filename)
        self.add(self._ui.box)

        self._pulse = GLib.timeout_add(100, self._pulse_progressbar)
        self.show_all()

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

    def _on_transfer_state_change(self, transfer, _signal_name, state):
        if state.is_finished or state.is_error:
            self.destroy()
            return

        description = transfer.get_state_description()
        if description:
            self._ui.label.set_text(description)

    def _pulse_progressbar(self):
        self._ui.progressbar.pulse()
        return True

    def _on_cancel_button_clicked(self, _widget):
        self.destroy()

    def _on_destroy(self, *args):
        self._transfer.cancel()
        self._transfer.disconnect(self)
        self._transfer = None
        self._destroyed = True
        if self._pulse is not None:
            GLib.source_remove(self._pulse)

    def _on_transfer_progress(self, transfer, _signal_name):
        if self._destroyed:
            return
        if self._pulse is not None:
            GLib.source_remove(self._pulse)
            self._pulse = None

        time_now = time.time()
        bytes_sec = round(transfer.seen / (time_now - self._start_time), 1)

        size_progress = GLib.format_size_full(transfer.seen, self._units)
        size_total = GLib.format_size_full(transfer.size, self._units)
        speed = '%s/s' % GLib.format_size_full(bytes_sec, self._units)

        if bytes_sec == 0:
            eta = '∞'
        else:
            eta = self._format_eta(
                round((transfer.size - transfer.seen) / bytes_sec))

        self._ui.progress_label.set_text(
            _('%(progress)s of %(total)s') % {
                'progress': size_progress,
                'total': size_total})

        self._ui.speed_label.set_text(speed)
        self._ui.eta_label.set_text(eta)
        self._ui.progressbar.set_fraction(float(transfer.seen) / transfer.size)

    @staticmethod
    def _format_eta(time_):
        times = {'minutes': 0, 'seconds': 0}
        time_ = int(time_)
        times['seconds'] = time_ % 60
        if time_ >= 60:
            time_ /= 60
            times['minutes'] = round(time_ % 60)

        return _('%(minutes)s min %(seconds)s sec') % times
