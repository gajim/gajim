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
from datetime import datetime

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .base import BaseRow

from ...dialogs import ErrorDialog
from ...util import EventHelper
from ...util import get_builder


class FileTransferRow(BaseRow, EventHelper):
    def __init__(self, account, transfer):
        BaseRow.__init__(self, account)
        EventHelper.__init__(self)

        self.type = 'file-transfer'
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        self._destroyed = False

        if app.settings.get('use_kib_mib'):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._start_time = time.time()
        self._pulse = GLib.timeout_add(100, self._pulse_progressbar)

        self._transfer = transfer
        self._transfer.connect('state-changed', self._on_transfer_state_change)
        self._transfer.connect('progress', self._on_transfer_progress)

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_hexpand(True)
        timestamp_widget.set_halign(Gtk.Align.END)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self._ui = get_builder('file_transfer.ui')
        self.grid.attach(self._ui.transfer_box, 1, 0, 1, 1)
        self._ui.file_name.set_text(transfer.filename)

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self.show_all()

    def _on_destroy(self, *args):
        self._destroyed = True

        if self._transfer.state.is_active:
            self._transfer.cancel()

        self._transfer = None
        if self._pulse is not None:
            GLib.source_remove(self._pulse)

    def _on_cancel_clicked(self, _button):
        self.destroy()

    def _on_transfer_state_change(self, transfer, _signal_name, state):
        if self._destroyed:
            return

        if state.is_error:
            ErrorDialog(_('Error'),
                        transfer.error_text,
                        transient_for=app.window)
            self.destroy()

        if state.is_finished or state.is_cancelled:
            self.destroy()
            return

        description = transfer.get_state_description()
        if description:
            self._ui.transfer_description.set_text(description)

    def _pulse_progressbar(self):
        self._ui.progress_bar.pulse()
        return True

    def _on_transfer_progress(self, transfer, _signal_name):
        if self._destroyed:
            return
        if self._pulse is not None:
            GLib.source_remove(self._pulse)
            self._pulse = None

        time_now = time.time()

        size_total = GLib.format_size_full(transfer.size, self._units)
        self._ui.file_size.set_text(size_total)

        bytes_sec = round(transfer.seen / (time_now - self._start_time), 1)
        speed = f'{GLib.format_size_full(bytes_sec, self._units)}/s'
        self._ui.transfer_progress.set_tooltip_text(_('Speed: %s') % speed)

        if bytes_sec == 0:
            eta = '∞'
        else:
            eta = self._format_eta(round(
                (transfer.size - transfer.seen) / bytes_sec))

        progress = float(transfer.seen) / transfer.size
        self._ui.transfer_progress.set_text(
            _('%(progress)s %% (%(time)s remaining)') % {
                'progress': round(progress * 100),
                'time': eta})

        self._ui.progress_bar.set_fraction(progress)

    @staticmethod
    def _format_eta(time_):
        times = {'minutes': 0, 'seconds': 0}
        time_ = int(time_)
        times['seconds'] = time_ % 60
        if time_ >= 60:
            time_ /= 60
            times['minutes'] = round(time_ % 60)
            return _('%(minutes)s min %(seconds)s sec') % times
        return _('%s sec') % times['seconds']
