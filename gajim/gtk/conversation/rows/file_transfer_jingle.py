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

from __future__ import annotations

from typing import Union
from typing import Optional

import logging
import os
import time
from datetime import datetime

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.events import FileRequestReceivedEvent
from gajim.common.events import FileRequestSent
from gajim.common.events import FileCompleted
from gajim.common.events import FileProgress
from gajim.common.events import FileError
from gajim.common.events import FileHashError
from gajim.common.events import FileSendError
from gajim.common.events import FileRequestError
from gajim.common.events import JingleErrorReceived
from gajim.common.events import JingleFtCancelledReceived
from gajim.common.file_props import FileProp
from gajim.common.file_props import FilesProp
from gajim.common.helpers import open_file
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.storage.archive import ConversationRow

from .base import BaseRow
from ...builder import get_builder
from ...util import format_eta

TransferEventT = Union[FileRequestReceivedEvent, FileRequestSent]

log = logging.getLogger('gajim.gui.conversation.rows.file_transfer_jingle')


class FileTransferJingleRow(BaseRow):
    def __init__(self,
                 account: str,
                 contact: BareContact,
                 event: Optional[TransferEventT] = None,
                 db_message: Optional[ConversationRow] = None
                 ) -> None:
        BaseRow.__init__(self, account)

        self.type = 'file-transfer'

        if db_message is not None:
            timestamp = db_message.time
        else:
            timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        self._contact = contact

        if db_message is not None:
            sid = db_message.additional_data.get_value('gajim', 'sid')
            assert sid is not None
            self._file_props = FilesProp.getFilePropBySid(sid)
            if self._file_props is None:
                log.debug('File prop not found for SID: %s', sid)
        else:
            assert event is not None
            self._file_props = event.file_props
        self._start_time = 0

        if app.settings.get('use_kib_mib'):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        avatar_placeholder.set_valign(Gtk.Align.START)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        if db_message is not None:
            if db_message.kind == KindConstant.FILE_TRANSFER_INCOMING:
                contact = self._contact
                is_self = True
            else:
                contact = self._client.get_module('Contacts').get_contact(
                    str(self._client.get_own_jid().bare))
                is_self = False
        else:
            if isinstance(event, FileRequestSent):
                contact = self._client.get_module('Contacts').get_contact(
                    str(self._client.get_own_jid().bare))
                is_self = False
            else:
                contact = self._contact
                is_self = True

        scale = self.get_scale_factor()
        avatar = contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
        assert not isinstance(avatar, GdkPixbuf.Pixbuf)
        avatar_image = Gtk.Image.new_from_surface(avatar)
        avatar_placeholder.add(avatar_image)

        name_widget = self.create_name_widget(contact.name, is_self)
        name_widget.set_halign(Gtk.Align.START)
        name_widget.set_valign(Gtk.Align.START)
        self.grid.attach(name_widget, 1, 0, 1, 1)

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_hexpand(True)
        timestamp_widget.set_halign(Gtk.Align.END)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self._ui = get_builder('file_transfer_jingle.ui')
        self.grid.attach(self._ui.transfer_box, 1, 1, 1, 1)

        self._ui.connect_signals(self)

        self.show_all()

        if db_message is not None:
            self._reconstruct_transfer()
        else:
            assert event is not None
            self._display_transfer_info(event.name)

        if self._file_props is None:
            return

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

    def _reconstruct_transfer(self) -> None:
        self._show_file_infos()
        if self._file_props is None:
            self._ui.transfer_action.set_text(_('File Transfer'))
            self._ui.error_label.set_text(_('No info available'))
            self._ui.action_stack.set_visible_child_name('error')
            return

        if self._file_props.completed:
            self._show_completed()
            return

        if self._file_props.stopped:
            self._ui.action_stack.set_visible_child_name('error')
            self._ui.transfer_action.set_text(_('File Transfer Stopped'))
            self._ui.error_label.set_text('')
            return

        if self._file_props.error is not None:
            self._show_error(self._file_props)
            return

        self._ui.transfer_action.set_text(_('File Offered…'))

    def _display_transfer_info(self, event_name: str) -> None:
        if event_name == 'file-request-sent':
            self._ui.action_stack.set_visible_child_name('progress')
            self._ui.progress_label.set_text(_('Waiting…'))

        self._ui.transfer_action.set_text(_('File Offered…'))
        self._show_file_infos()

    def _show_file_infos(self) -> None:
        if self._file_props is None:
            self._ui.file_name.hide()
            self._ui.file_description.hide()
            self._ui.file_size.hide()
            return

        file_name = GLib.markup_escape_text(str(self._file_props.name))
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

    def process_event(self, event: TransferEventT) -> None:
        if isinstance(event, JingleErrorReceived):
            if event.sid != self._file_props.sid:
                return
            self._ui.action_stack.set_visible_child_name('error')
            self._ui.transfer_action.set_text(_('File Transfer Cancelled'))
            self._ui.error_label.set_text(event.reason)
            return

        if isinstance(event, JingleFtCancelledReceived):
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

        if isinstance(event, FileCompleted):
            self._show_completed()
        elif isinstance(event, FileError):
            self._show_error(event.file_props)
        elif isinstance(event, FileHashError):
            self._ui.action_stack.set_visible_child_name('hash-error')
            self._ui.transfer_action.set_text(_('File Verification Failed'))
        elif (isinstance(event, FileRequestError) or
                isinstance(event, FileSendError)):
            self._ui.action_stack.set_visible_child_name('error')
            self._ui.transfer_action.set_text(_('File Transfer Cancelled'))
            error_text = _('Connection with %s could not be '
                           'established.') % self._contact.name
            if event.error_msg:
                error_text = f'{error_text} ({event.error_msg})'
            self._ui.error_label.set_text(error_text)

        elif isinstance(event, FileProgress):
            self._update_progress(event.file_props)

    def _update_progress(self, file_props: FileProp) -> None:
        self._ui.action_stack.set_visible_child_name('progress')
        self._ui.transfer_action.set_text(_('Transferring File…'))

        time_now = time.time()
        full_size = file_props.size

        if file_props.type_ == 's':
            # We're sending a file
            if self._start_time == 0:
                self._start_time = time_now
                return
            if not file_props.transfered_size:
                return
            transferred_size = file_props.transfered_size[-1][1]
        else:
            # We're receiving a file
            transferred_size = file_props.received_len

        if full_size == 0:
            return

        bytes_sec = int(
            round(transferred_size / (time_now - self._start_time), 1))
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

    def _show_error(self, file_props: FileProp) -> None:
        self._ui.action_stack.set_visible_child_name('error')
        self._ui.transfer_action.set_text(_('File Transfer Stopped'))
        if file_props.error == -1:
            self._ui.error_label.set_text(
                _('%s stopped the transfer') % self._contact.name)
        elif file_props.error == -6:
            self._ui.error_label.set_text(_('Error opening file'))
        elif file_props.error == -12:
            self._ui.error_label.set_text(_('SSL certificate error'))
        else:
            self._ui.error_label.set_text(_('An error occurred'))

    def _show_completed(self) -> None:
        self._ui.action_stack.set_visible_child_name('complete')
        self._ui.transfer_action.set_text(_('File Transfer Completed'))

    def _on_accept_file_request(self, _button: Gtk.Button) -> None:
        app.interface.instances['file_transfers'].on_file_request_accepted(
            self._account, self._contact, self._file_props)
        self._start_time = time.time()

    def _on_reject_file_request(self, _button: Gtk.Button) -> None:
        self._client.get_module('Bytestream').send_file_rejection(
            self._file_props)
        self._file_props.stopped = True
        self._ui.action_stack.set_visible_child_name('rejected')
        self._ui.transfer_action.set_text(_('File Transfer Cancelled'))

    def _on_open_file(self, _button: Gtk.Button) -> None:
        if os.path.exists(self._file_props.file_name):
            open_file(self._file_props.file_name)

    def _on_open_folder(self, _button: Gtk.Button) -> None:
        path = os.path.split(self._file_props.file_name)[0]
        if os.path.exists(path) and os.path.isdir(path):
            open_file(path)

    def _on_bad_hash_retry(self, _button: Gtk.Button) -> None:
        app.interface.instances['file_transfers'].show_hash_error(
            self._contact.jid,
            self._file_props,
            self._account)

    def _on_cancel_transfer(self, _button: Gtk.Button) -> None:
        app.interface.instances['file_transfers'].cancel_transfer(
            self._file_props)

    def _on_show_transfers(self, _button: Gtk.Button) -> None:
        file_transfers = app.interface.instances['file_transfers']
        if file_transfers.window.get_property('visible'):
            file_transfers.window.present()
        else:
            file_transfers.window.show_all()
