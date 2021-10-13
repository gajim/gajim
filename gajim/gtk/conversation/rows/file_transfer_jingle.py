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
from datetime import datetime

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.helpers import open_file
from gajim.common.i18n import _

from .base import BaseRow
from ...util import get_builder
from ...util import format_eta


class FileTransferJingleRow(BaseRow):
    def __init__(self, account, contact, event):
        BaseRow.__init__(self, account)

        self.type = 'file-transfer'
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        self._contact = contact
        self._file_props = event.file_props
        self._start_time = 0

        if app.settings.get('use_kib_mib'):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_hexpand(True)
        timestamp_widget.set_halign(Gtk.Align.END)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self._ui = get_builder('file_transfer_jingle.ui')
        self.grid.attach(self._ui.transfer_box, 1, 0, 1, 1)

        self._ui.connect_signals(self)

        # pylint: disable=line-too-long
        app.ged.register_event_handler('file-completed', ged.GUI1, self.process_event)
        app.ged.register_event_handler('file-hash-error', ged.GUI1, self.process_event)
        app.ged.register_event_handler('file-send-error', ged.GUI1, self.process_event)
        app.ged.register_event_handler('file-request-error', ged.GUI1, self.process_event)
        app.ged.register_event_handler('file-progress', ged.GUI1, self.process_event)
        app.ged.register_event_handler('file-error', ged.GUI1, self.process_event)
        app.ged.register_event_handler('jingle-error-received', ged.GUI1, self.process_event)
        app.ged.register_event_handler('jingle-ft-cancelled-received', ged.GUI1, self.process_event)
        # pylint: enable=line-too-long

        self.show_all()

        self._display_transfer_info(event)

    def _display_transfer_info(self, event):
        if event.name == 'file-request-sent':
            self._ui.action_stack.set_visible_child_name('progress')
            self._ui.progress_label.set_text(_('Waiting…'))

        self._ui.transfer_action.set_text(_('File Offered…'))

        file_name = GLib.markup_escape_text(self._file_props.name)
        if self._file_props.mime_type:
            file_name = f'{file_name} ({self._file_props.mime_type})'
        self._ui.file_name.set_text(file_name)
        self._ui.file_name.set_tooltip_text(file_name)

        if self._file_props.desc:
            desc = GLib.markup_escape_text(self._file_props.desc)
            self._ui.file_description.set_text(desc)
            self._ui.file_description.set_tooltip_text(desc)
        else:
            self._ui.file_description.hide()

        self._ui.file_size.set_text(
            GLib.format_size_full(self._file_props.size, self._units))

    def process_event(self, event):
        if event.name == 'jingle-error-received':
            if event.sid != self._file_props.sid:
                return
            self._ui.action_stack.set_visible_child_name('error')
            self._ui.transfer_action.set_text(_('File Transfer Cancelled'))
            self._ui.error_label.set_text(event.reason)
            return

        if event.name == 'jingle-ft-cancelled-received':
            if event.sid != self._file_props.sid:
                return
            self._ui.action_stack.set_visible_child_name('error')
            self._ui.transfer_action.set_text(_('File Transfer Cancelled'))
            self._ui.error_label.set_text(
                _('%(name)s cancelled the transfer (%(reason)s)') % {
                    'name': self._contact.name,
                    'reason': event.reason})
            return

        if event.file_props.sid != self._file_props.sid:
            return

        if event.name == 'file-completed':
            self._show_completed()
        elif event.name == 'file-error':
            self._show_error(event)
        elif event.name == 'file-hash-error':
            self._ui.action_stack.set_visible_child_name('hash-error')
            self._ui.transfer_action.set_text(_('File Verification Failed'))
        elif event.name in ('file-request-error', 'file-send-error'):
            self._ui.action_stack.set_visible_child_name('error')
            self._ui.transfer_action.set_text(_('File Transfer Cancelled'))
            error_text = _('Connection with %s could not be '
                           'established.') % self._contact.name
            if event.error_msg:
                error_text = f'{error_text} ({event.error_msg})'
            self._ui.error_label.set_text(error_text)

        elif event.name == 'file-progress':
            self._update_progress(event.file_props)

    def _update_progress(self, file_props):
        self._ui.action_stack.set_visible_child_name('progress')
        self._ui.transfer_action.set_text(_('Transferring File…'))

        time_now = time.time()
        full_size = file_props.size

        if file_props.type_ == 's':
            # We're sending a file
            if self._start_time == 0:
                self._start_time = time.time()
            transferred_size = file_props.transfered_size[-1][1]
        else:
            # We're receiving a file
            transferred_size = file_props.received_len

        if full_size == 0:
            return

        bytes_sec = round(transferred_size / (time_now - self._start_time), 1)
        speed = f'{GLib.format_size_full(bytes_sec, self._units)}/s'
        self._ui.progress_label.set_tooltip_text(_('Speed: %s') % speed)

        if bytes_sec == 0:
            eta = '∞'
        else:
            eta = format_eta(round(
                (full_size - transferred_size) / bytes_sec))

        progress = float(transferred_size) / full_size
        self._ui.progress_label.set_text(
            _('%(progress)s %% (%(time)s remaining)') % {
                'progress': round(progress * 100),
                'time': eta})

        self._ui.progress_bar.set_fraction(progress)

    def _show_error(self, event):
        self._ui.action_stack.set_visible_child_name('error')
        self._ui.transfer_action.set_text(_('File Transfer Stopped'))
        if event.file_props.error == -1:
            self._ui.error_label.set_text(
                _('%s stopped the transfer') % self._contact.name)
        elif event.file_props.error == -6:
            self._ui.error_label.set_text(_('Error opening file'))
        elif event.file_props.error == -12:
            self._ui.error_label.set_text(_('SSL certificate error'))
        else:
            self._ui.error_label.set_text(_('An error occurred'))

    def _show_completed(self):
        self._ui.action_stack.set_visible_child_name('complete')
        self._ui.transfer_action.set_text(_('File Transfer Completed'))

    def _on_accept_file_request(self, _widget):
        app.interface.instances['file_transfers'].on_file_request_accepted(
            self._account, self._contact, self._file_props)
        self._start_time = time.time()

    def _on_reject_file_request(self, _widget):
        self._client.get_module('Bytestream').send_file_rejection(
            self._file_props)
        self._ui.action_stack.set_visible_child_name('rejected')
        self._ui.transfer_action.set_text(_('File Transfer Cancelled'))

    def _on_open_file(self, _widget):
        if os.path.exists(self._file_props.file_name):
            open_file(self._file_props.file_name)

    def _on_open_folder(self, _widget):
        path = os.path.split(self._file_props.file_name)[0]
        if os.path.exists(path) and os.path.isdir(path):
            open_file(path)

    def _on_bad_hash_retry(self, _widget):
        app.interface.instances['file_transfers'].show_hash_error(
            self._contact.jid,
            self._file_props,
            self._account)

    def _on_cancel_transfer(self, _widget):
        app.interface.instances['file_transfers'].cancel_transfer(
            self._file_props)

    def _on_show_transfers(self, _widget):
        file_transfers = app.interface.instances['file_transfers']
        if file_transfers.window.get_property('visible'):
            file_transfers.window.present()
        else:
            file_transfers.window.show_all()
