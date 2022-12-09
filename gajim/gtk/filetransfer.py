# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
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

from __future__ import annotations

from typing import Optional

import os
import time
import logging
from functools import partial
from enum import IntEnum
from enum import unique
from datetime import datetime
from datetime import timezone
from pathlib import Path

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import ged
from gajim.common import helpers
from gajim.common.events import FileRequestSent
from gajim.common.events import Notification
from gajim.common.const import KindConstant
from gajim.common.i18n import _
from gajim.common.file_props import FilesProp
from gajim.common.file_props import FileProp
from gajim.common.helpers import open_file
from gajim.common.helpers import file_is_locked
from gajim.common.helpers import AdditionalDataDict
from gajim.common.modules.bytestream import is_transfer_active
from gajim.common.modules.bytestream import is_transfer_paused
from gajim.common.modules.bytestream import is_transfer_stopped
from gajim.common.modules.contacts import BareContact
from gajim.common import types

from .dialogs import DialogButton
from .dialogs import ConfirmationDialog
from .dialogs import ErrorDialog
from .filechoosers import FileSaveDialog
from .tooltips import FileTransfersTooltip
from .builder import get_builder
from .util import format_eta

log = logging.getLogger('gajim.gui.filetransfer')


@unique
class Column(IntEnum):
    IMAGE = 0
    LABELS = 1
    FILE = 2
    TIME = 3
    PROGRESS = 4
    PERCENT = 5
    PULSE = 6
    SID = 7


class FileTransfersWindow:
    def __init__(self):
        self.files_props = {'r': {}, 's': {}}
        self.height_diff = 0

        self._last_progress_update = 0

        self._ui = get_builder('filetransfers.ui')
        self.window = self._ui.file_transfers_window
        self._ui.notify_ft_complete.set_active(
            app.settings.get('notify_on_file_complete'))
        self.model = Gtk.ListStore(str, str, str, str, str, int, int, str)
        self._ui.transfers_list.set_model(self.model)
        col = Gtk.TreeViewColumn()

        render_pixbuf = Gtk.CellRendererPixbuf()

        col.pack_start(render_pixbuf, True)
        render_pixbuf.set_property('xpad', 6)
        render_pixbuf.set_property('ypad', 6)
        render_pixbuf.set_property('yalign', 0.5)
        col.add_attribute(render_pixbuf, 'icon_name', 0)
        self._ui.transfers_list.append_column(col)

        col = Gtk.TreeViewColumn(_('File'))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'markup', Column.LABELS)
        renderer.set_property('xalign', 0.0)
        renderer.set_property('yalign', 0.0)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'markup', Column.FILE)
        renderer.set_property('xalign', 0.0)
        renderer.set_property('yalign', 0.0)
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        col.set_resizable(True)
        col.set_min_width(160)
        col.set_expand(True)
        self._ui.transfers_list.append_column(col)

        col = Gtk.TreeViewColumn(_('Time'))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'markup', Column.TIME)
        renderer.set_property('yalign', 0.5)
        renderer.set_property('xalign', 0.5)
        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        renderer.set_property('xalign', 0.5)
        col.set_resizable(True)
        col.set_min_width(70)
        self._ui.transfers_list.append_column(col)

        col = Gtk.TreeViewColumn(_('Progress'))
        renderer = Gtk.CellRendererProgress()
        renderer.set_property('yalign', 0.5)
        renderer.set_property('xalign', 0.5)
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'text', Column.PROGRESS)
        col.add_attribute(renderer, 'value', Column.PERCENT)
        col.add_attribute(renderer, 'pulse', Column.PULSE)
        col.set_resizable(False)
        col.set_fixed_width(150)
        self._ui.transfers_list.append_column(col)

        self.icons = {
            'upload': 'go-up-symbolic',
            'download': 'go-down-symbolic',
            'stop': 'process-stop-symbolic',
            'waiting': 'emblem-synchronizing-symbolic',
            'pause': 'media-playback-pause-symbolic',
            'continue': 'media-playback-start-symbolic',
            'ok': 'emblem-ok-symbolic',
            'computing': 'system-run-symbolic',
            'hash_error': 'network-error-symbolic',
        }

        if app.settings.get('use_kib_mib'):
            self.units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self.units = GLib.FormatSizeFlags.DEFAULT

        self._ui.transfers_list.get_selection().set_mode(
            Gtk.SelectionMode.SINGLE)
        self._ui.transfers_list.get_selection().connect(
            'changed', self._selection_changed)

        # Tooltip
        self._ui.transfers_list.connect('query-tooltip', self._query_tooltip)
        self._ui.transfers_list.set_has_tooltip(True)
        self.tooltip = FileTransfersTooltip()

        self._ui.connect_signals(self)

        app.ged.register_event_handler(
            'file-completed', ged.GUI1, self._file_completed)
        app.ged.register_event_handler(
            'file-hash-error', ged.GUI1, self._file_hash_error)
        app.ged.register_event_handler(
            'file-send-error', ged.GUI1, self._file_send_error)
        app.ged.register_event_handler(
            'file-request-error', ged.GUI1, self._file_request_error)
        app.ged.register_event_handler(
            'file-request-received', ged.GUI1, self._file_request_received)
        app.ged.register_event_handler(
            'file-progress', ged.GUI1, self._file_progress)
        app.ged.register_event_handler(
            'file-error', ged.GUI1, self._file_error)
        app.ged.register_event_handler(
            'jingle-ft-cancelled-received',
            ged.GUI1,
            self._file_transfer_cancelled)

    def _file_completed(self, event):
        self.set_status(event.file_props, 'ok')
        self.set_progress(
            event.file_props.type_,
            event.file_props.sid,
            event.file_props.received_len)

        if not app.settings.get('notify_on_file_complete'):
            return

        app.ged.raise_event(
            Notification(account=event.account,
                         jid=event.jid,
                         type='file-transfer',
                         sub_type='file-completed',
                         title=_('File Transfer Completed'),
                         text=_('File: %s') % event.file_props.name))

    def _file_error(self, event):
        self.set_status(event.file_props, 'stop')

    def _file_hash_error(self, event):
        self.set_status(event.file_props, 'hash_error')
        if self.window.get_property('visible'):
            self.show_hash_error(event.jid, event.file_props, event.account)

    def _file_send_error(self, event):
        self.set_status(event.file_props, 'stop')

        if app.window.is_chat_active(event.account, event.jid):
            return

        app.ged.raise_event(
            Notification(account=event.account,
                         jid=event.jid,
                         type='file-transfer',
                         sub_type='file-send-error',
                         title=_('File Transfer Failed'),
                         text=_('File: %s') % event.file_props.name))

    def _file_request_error(self, event):
        self.set_status(event.file_props, 'stop')
        errno = event.file_props.error
        account = event.conn.name

        if self.window.get_property('visible'):
            if errno in (-4, -5):
                self.show_stopped(event.jid, event.file_props, event.error_msg)
            return

        if errno in (-4, -5):
            sub_type = 'file-error'
        else:
            sub_type = 'file-request-error'

        if app.window.is_chat_active(account, event.jid):
            return

        text = _('File: %s') % event.file_props.name
        app.ged.raise_event(
            Notification(account=account,
                         jid=event.jid,
                         type='file-transfer',
                         sub_type=sub_type,
                         title=_('File Transfer Failed'),
                         text=text))

    def _file_request_received(self, event):
        client = app.get_client(event.account)
        contact = client.get_module('Contacts').get_contact(event.jid)

        if event.file_props.session_type == 'jingle':
            jingle = event.stanza.getTag('jingle')
            content = jingle.getTag('content')
            description = content.getTag('description')
            request = description.getTag('request')
            if request:
                # If we get a request instead
                self.add_transfer(event.account, contact, event.file_props)
                return

        if app.window.is_chat_active(event.account, event.jid):
            return

        text = _('%s wants to send you a file') % contact.name
        app.ged.raise_event(
            Notification(account=event.account,
                         jid=event.jid,
                         type='file-transfer',
                         sub_type='file-request-received',
                         title=_('File Offered'),
                         text=text))

    def _file_transfer_cancelled(self, event):
        file_props = None
        # get the file_props of our session
        file_props = FilesProp.getFileProp(event.conn.name, event.sid)
        if not file_props:
            return

        self.set_status(file_props, 'stop')
        file_props.error = -4  # is it the right error code?
        if self.window.get_property('visible'):
            self.show_stopped(event.jid,
                              file_props,
                              'Peer cancelled the transfer')

    def _query_tooltip(self, widget, x_pos, y_pos, keyboard_mode, tooltip):
        try:
            x_pos, y_pos = widget.convert_widget_to_bin_window_coords(
                x_pos, y_pos)
            row = widget.get_path_at_pos(x_pos, y_pos)[0]
        except TypeError:
            self.tooltip.clear_tooltip()
            return False
        if not row:
            self.tooltip.clear_tooltip()
            return False

        iter_ = None
        try:
            model = widget.get_model()
            iter_ = model.get_iter(row)
        except Exception:
            self.tooltip.clear_tooltip()
            return False

        sid = self.model[iter_][Column.SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])

        value, widget = self.tooltip.get_tooltip(file_props, sid)
        tooltip.set_custom(widget)
        return value

    def find_transfer_by_jid(self, account, jid):
        '''
        Find all transfers with peer 'jid' that belong to 'account'
        '''
        active_transfers = [[], []]  # ['senders', 'receivers']
        allfp = FilesProp.getAllFileProp()
        for file_props in allfp:
            if file_props.type_ == 's' and file_props.tt_account == account:
                # 'account' is the sender
                receiver_jid = file_props.receiver.split('/')[0]
                if jid == receiver_jid and not is_transfer_stopped(file_props):
                    active_transfers[0].append(file_props)
            elif file_props.type_ == 'r' and file_props.tt_account == account:
                # 'account' is the recipient
                sender_jid = file_props.sender.split('/')[0]
                if jid == sender_jid and not is_transfer_stopped(file_props):
                    active_transfers[1].append(file_props)
            else:
                raise Exception('file_props has no type')
        return active_transfers

    def show_stopped(self, jid, file_props, error_msg=''):
        if file_props.type_ == 'r':
            file_name = os.path.basename(file_props.file_name)
        else:
            file_name = file_props.name
        sectext = '\t' + _('Filename: %s') % GLib.markup_escape_text(file_name)
        sectext += '\n\t' + _('Recipient: %s') % jid
        if error_msg:
            sectext += '\n\t' + _('Error message: %s') % error_msg
        ErrorDialog(_('File transfer stopped'), sectext)
        self._ui.transfers_list.get_selection().unselect_all()

    def show_hash_error(self,
                        jid: JID,
                        file_props: FileProp,
                        account: str
                        ) -> None:
        def _on_yes():
            # Delete old file
            os.remove(file_props.file_name)

            # Request the file to the sender
            sid = helpers.get_random_string()
            new_file_props = FilesProp.getNewFileProp(account, sid)
            new_file_props.file_name = file_props.file_name
            new_file_props.name = file_props.name
            new_file_props.desc = file_props.desc
            new_file_props.size = file_props.size
            new_file_props.date = file_props.date
            new_file_props.hash_ = file_props.hash_
            new_file_props.type_ = 'r'
            tsid = client.get_module('Jingle').start_file_transfer(
                str(jid), new_file_props, True)

            new_file_props.transport_sid = tsid
            self.add_transfer(account, contact, new_file_props)

        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)

        if file_props.type_ == 'r':
            file_name = os.path.basename(file_props.file_name)
        else:
            file_name = file_props.name
        ConfirmationDialog(
            _('File Transfer Error'),
            _('File Transfer Error'),
            _('The file %s has been received, but it seems to have '
              'been damaged along the way.\n'
              'Do you want to download it again?') % file_name,
            [DialogButton.make('Cancel',
                               text=_('_No')),
             DialogButton.make('Accept',
                               text=_('_Download Again'),
                               callback=_on_yes)]).show()

    def send_file(self,
                  account: str,
                  contact: types.ResourceContact,
                  resource_jid: JID,
                  file_path: str,
                  file_desc: str = ''
                  ) -> bool:
        '''
        Start the real transfer(upload) of the file
        '''
        if file_is_locked(file_path):
            pritext = _('Gajim can not read this file')
            sextext = _('Another process is using this file.')
            ErrorDialog(pritext, sextext)
            return False

        file_name = os.path.split(file_path)[1]
        file_props = self.get_send_file_props(
            account,
            resource_jid,
            file_path,
            file_name,
            file_desc)
        if file_props is None:
            return False

        # Insert file request into DB
        additional_data = AdditionalDataDict()
        additional_data.set_value('gajim', 'type', 'jingle')
        additional_data.set_value('gajim', 'sid', file_props.sid)
        app.storage.archive.insert_into_logs(
            account,
            contact.jid.bare,
            time.time(),
            KindConstant.FILE_TRANSFER_OUTGOING,
            additional_data=additional_data)

        client = app.get_client(account)
        client.get_module('Jingle').start_file_transfer(
            str(resource_jid), file_props)
        app.ged.raise_event(
            FileRequestSent(file_props=file_props,
                            account=account,
                            jid=contact.jid))
        self.add_transfer(account, contact, file_props)

        return True

    def _start_receive(self, file_path, account, contact, file_props):
        file_dir = os.path.dirname(file_path)
        if file_dir:
            app.settings.set('last_save_dir', file_dir)
        file_props.file_name = file_path
        file_props.type_ = 'r'
        self.add_transfer(account, contact, file_props)
        client = app.get_client(account)
        client.get_module('Bytestream').send_file_approval(file_props)

    def on_file_request_accepted(self,
                                 account: str,
                                 contact: BareContact,
                                 file_props: FileProp
                                 ) -> None:
        def _on_accepted(account, contact, file_props, file_path):
            if os.path.exists(file_path):
                app.settings.set('last_save_dir', os.path.dirname(file_path))

                # Check if we have write permissions
                if not os.access(file_path, os.W_OK):
                    file_name = GLib.markup_escape_text(
                        os.path.basename(file_path))
                    ErrorDialog(
                        _('Cannot overwrite existing file "%s"') % file_name,
                        _('A file with this name already exists and you do '
                          'not have permission to overwrite it.'))
                    return

            # File does not exist yet
            dirname = os.path.dirname(file_path)
            if not os.access(dirname, os.W_OK) and os.name != 'nt':
                # read-only bit is used to mark special folder under
                # windows, not to mark that a folder is read-only.
                # See ticket #3587
                ErrorDialog(
                    _('Directory "%s" is not writable') % dirname,
                    _('You do not have permissions to create files '
                      'in this directory.'))
                return
            self._start_receive(file_path, account, contact, file_props)

        # Show file save as dialog
        client = app.get_client(account)
        accept_cb = partial(_on_accepted, account, contact, file_props)
        cancel_cb = partial(
            client.get_module('Bytestream').send_file_rejection, file_props)
        FileSaveDialog(accept_cb,
                       cancel_cb,
                       path=app.settings.get('last_save_dir'),
                       file_name=file_props.name)

    def set_status(self, file_props, status):
        '''
        Change the status of a transfer to state 'status'
        '''
        iter_ = self.get_iter_by_sid(file_props.type_, file_props.sid)
        if iter_ is None:
            return

        if status == 'stop':
            file_props.stopped = True
        elif status == 'ok':
            file_props.completed = True
            text = self._format_percent(100)
            received_size = GLib.format_size_full(
                int(file_props.received_len), self.units)
            full_size = GLib.format_size_full(file_props.size, self.units)
            text += received_size + '/' + full_size
            self.model.set(iter_, Column.PROGRESS, text)
            self.model.set(iter_, Column.PULSE, GLib.MAXINT32)
        elif status == 'computing':
            self.model.set(iter_, Column.PULSE, 1)
            text = _('Checking file…') + '\n'
            received_size = GLib.format_size_full(
                int(file_props.received_len), self.units)
            full_size = GLib.format_size_full(file_props.size, self.units)
            text += received_size + '/' + full_size
            self.model.set(iter_, Column.PROGRESS, text)

            def _pulse():
                pulse_value = self.model.get(iter_, Column.PULSE)[0]
                if pulse_value == GLib.MAXINT32:
                    return False
                self.model.set(iter_, Column.PULSE, pulse_value + 1)
                return True
            GLib.timeout_add(100, _pulse)
        elif status == 'hash_error':
            text = _('File error') + '\n'
            received_size = GLib.format_size_full(
                int(file_props.received_len), self.units)
            full_size = GLib.format_size_full(file_props.size, self.units)
            text += received_size + '/' + full_size
            self.model.set(iter_, Column.PROGRESS, text)
            self.model.set(iter_, Column.PULSE, GLib.MAXINT32)
        self.model.set(iter_, Column.IMAGE, self.icons[status])
        path = self.model.get_path(iter_)
        self._select_func(path)

    def _format_percent(self, percent):
        '''
        Add extra spaces from both sides of the percent, so that progress
        string has always a fixed size
        '''
        _str = '          '
        if percent != 100.:
            _str += ' '
        if percent < 10:
            _str += ' '
        _str += str(percent) + '%          \n'
        return _str

    def _get_eta_and_speed(self, full_size, transferred_size, file_props):
        if not file_props.transferred_size:
            return 0., 0.

        if file_props.elapsed_time == 0:
            return 0., 0.

        if len(file_props.transferred_size) == 1:
            speed = round(float(transferred_size) / file_props.elapsed_time)
        else:
            # first and last are (time, transferred_size)
            first = file_props.transferred_size[0]
            last = file_props.transferred_size[-1]
            transferred = last[1] - first[1]
            tim = last[0] - first[0]
            if tim == 0:
                return 0., 0.
            speed = round(float(transferred) / tim)
        if speed == 0.:
            return 0., 0.
        remaining_size = full_size - transferred_size
        eta = remaining_size / speed
        return eta, speed

    def _remove_transfer(self, iter_, sid, file_props):
        self.model.remove(iter_)
        if not file_props:
            return
        if file_props.tt_account:
            # file transfer is set
            account = file_props.tt_account
            if account in app.settings.get_active_accounts():
                # there is a connection to the account
                client = app.get_client(account)
                client.get_module('Bytestream').remove_transfer(file_props)

        FilesProp.deleteFileProp(file_props)
        del file_props

    def _file_progress(self, event):
        self.set_progress(
            event.file_props.type_,
            event.file_props.sid,
            event.file_props.received_len)

    def set_progress(self, typ, sid, transferred_size, iter_=None):
        '''
        Change the progress of a transfer with new transferred size
        '''
        if time.time() - self._last_progress_update < 0.5:
            # Update window every 500ms only
            return
        self._last_progress_update = time.time()

        file_props = FilesProp.getFilePropByType(typ, sid)
        if file_props is None:
            return

        full_size = file_props.size
        if full_size == 0:
            percent = 0
        else:
            percent = round(float(transferred_size) / full_size * 100, 1)
        if iter_ is None:
            iter_ = self.get_iter_by_sid(typ, sid)
        if iter_ is not None:
            just_began = False
            if self.model[iter_][Column.PERCENT] == 0 and int(percent > 0):
                just_began = True
            text = self._format_percent(percent)
            if transferred_size == 0:
                text += '0'
            else:
                text += GLib.format_size_full(transferred_size, self.units)
            text += '/' + GLib.format_size_full(full_size, self.units)
            # Kb/s

            # remaining time
            if file_props.offset:
                transferred_size -= file_props.offset
                full_size -= file_props.offset

            if file_props.elapsed_time > 0:
                file_props.transferred_size.append((file_props.last_time,
                                                   transferred_size))
            if len(file_props.transferred_size) > 6:
                file_props.transferred_size.pop(0)
            eta, speed = self._get_eta_and_speed(full_size, transferred_size,
                                                 file_props)

            self.model.set(iter_, Column.PROGRESS, text)
            self.model.set(iter_, Column.PERCENT, int(percent))
            text = format_eta(eta)
            text += '\n'
            # Translators:
            # This should make the string KB/s,
            # where 'KB' part is taken from %s.
            # Only the 's' after / (which means second) should be translated.
            text += _('(%(filesize_unit)s/s)') % {
                'filesize_unit': GLib.format_size_full(speed, self.units)}
            self.model.set(iter_, Column.TIME, text)

            # try to guess what should be the status image
            if file_props.type_ == 'r':
                status = 'download'
            else:
                status = 'upload'
            if file_props.paused is True:
                status = 'pause'
            elif file_props.stalled is True:
                status = 'waiting'
            if file_props.connected is False:
                status = 'stop'
            self.model.set(iter_, 0, self.icons[status])
            if transferred_size == full_size:
                # If we are receiver and this is a jingle session
                if (file_props.type_ == 'r' and
                        file_props.session_type == 'jingle' and
                        file_props.hash_):
                    # Show that we are computing the hash
                    self.set_status(file_props, 'computing')
                else:
                    self.set_status(file_props, 'ok')
            elif just_began:
                path = self.model.get_path(iter_)
                self._select_func(path)

    def get_iter_by_sid(self, typ, sid):
        '''
        Return iter to the row, which holds file transfer, identified by the
        session id
        '''
        iter_ = self.model.get_iter_first()
        while iter_:
            if typ + sid == self.model[iter_][Column.SID]:
                return iter_
            iter_ = self.model.iter_next(iter_)

    @staticmethod
    def __convert_date(epoch: float) -> str:
        # Converts date-time from seconds from epoch to iso 8601
        dt = datetime.fromtimestamp(epoch, timezone.utc)
        return dt.isoformat() + 'Z'

    def get_send_file_props(self,
                            account: str,
                            resource_jid: JID,
                            file_path: str,
                            file_name: str,
                            file_desc: str = ''
                            ) -> Optional[FileProp]:
        '''
        Create new file_props object and set initial file transfer
        properties in it
        '''
        if os.path.isfile(file_path):
            stat = os.stat(file_path)
        else:
            ErrorDialog(
                _('Invalid File'),
                _('File: %s') % file_path)
            return None

        if stat[6] == 0:
            ErrorDialog(
                _('Invalid File'),
                _('It is not possible to send empty files'))
            return None

        file_props = FilesProp.getNewFileProp(
            account,
            sid=helpers.get_random_string())
        mod_date = os.path.getmtime(file_path)
        file_props.file_name = file_path
        file_props.name = file_name
        file_props.date = self.__convert_date(mod_date)
        file_props.type_ = 's'
        file_props.desc = file_desc
        file_props.elapsed_time = 0
        file_props.size = stat[6]
        file_props.sender = account
        file_props.receiver = str(resource_jid)
        file_props.tt_account = account
        return file_props

    def add_transfer(self, account, contact, file_props):
        '''
        Add new transfer to FT window and show the FT window
        '''
        if file_props is None:
            return

        file_props.elapsed_time = 0
        iter_ = self.model.prepend()
        if file_props.type_ == 'r':
            text_labels = '\n<b>' + _('Sender: ') + '</b>'
        else:
            text_labels = '\n<b>' + _('Recipient: ') + '</b>'

        if file_props.type_ == 'r':
            file_name = os.path.split(file_props.file_name)[1]
        else:
            file_name = file_props.name
        text_props = GLib.markup_escape_text(file_name) + '\n'
        text_props += contact.name
        self.model.set(iter_,
                       1,
                       text_labels,
                       2,
                       text_props,
                       Column.PULSE,
                       -1,
                       Column.SID,
                       file_props.type_ + file_props.sid)
        self.set_progress(file_props.type_, file_props.sid, 0, iter_)
        if file_props.started is False:
            status = 'waiting'
        elif file_props.type_ == 'r':
            status = 'download'
        else:
            status = 'upload'
        file_props.tt_account = account
        self.set_status(file_props, status)
        self._set_cleanup_sensitivity()

    def _on_transfers_list_row_activated(self, widget, path, col):
        # try to open the containing folder
        self._on_open_folder_menuitem_activate(widget)

    def _set_cleanup_sensitivity(self):
        '''
        Check if there are transfer rows and set cleanup_button sensitive, or
        insensitive if model is empty
        '''
        if not self.model:
            self._ui.cleanup_button.set_sensitive(False)
        else:
            self._ui.cleanup_button.set_sensitive(True)

    def _set_all_insensitive(self):
        '''
        Make all buttons/menuitems insensitive
        '''
        self._ui.pause_resume_button.set_sensitive(False)
        self._ui.pause_resume_menuitem.set_sensitive(False)
        self._ui.remove_menuitem.set_sensitive(False)
        self._ui.cancel_button.set_sensitive(False)
        self._ui.cancel_menuitem.set_sensitive(False)
        self._ui.open_folder_menuitem.set_sensitive(False)
        self._set_cleanup_sensitivity()

    def _set_buttons_sensitive(self, path, is_row_selected):
        '''
        Make buttons/menuitems sensitive as appropriate to the state of file
        transfer located at path 'path'
        '''
        if path is None:
            self._set_all_insensitive()
            return
        current_iter = self.model.get_iter(path)
        sid = self.model[current_iter][Column.SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        self._ui.remove_menuitem.set_sensitive(is_row_selected)
        self._ui.open_folder_menuitem.set_sensitive(is_row_selected)
        is_stopped = False
        if is_transfer_stopped(file_props):
            is_stopped = True
        self._ui.cancel_button.set_sensitive(not is_stopped)
        self._ui.cancel_menuitem.set_sensitive(not is_stopped)
        if not is_row_selected:
            # No selection, disable the buttons
            self._set_all_insensitive()
        elif not is_stopped and file_props.continue_cb:
            if is_transfer_active(file_props):
                # File transfer is active
                self._toggle_pause_continue(True)
                self._ui.pause_resume_button.set_sensitive(True)
                self._ui.pause_resume_menuitem.set_sensitive(True)
            elif is_transfer_paused(file_props):
                # File transfer is paused
                self._toggle_pause_continue(False)
                self._ui.pause_resume_button.set_sensitive(True)
                self._ui.pause_resume_menuitem.set_sensitive(True)
            else:
                self._ui.pause_resume_button.set_sensitive(False)
                self._ui.pause_resume_menuitem.set_sensitive(False)
        else:
            self._ui.pause_resume_button.set_sensitive(False)
            self._ui.pause_resume_menuitem.set_sensitive(False)
        return True

    def _selection_changed(self, args):
        '''
        Selection has changed - change the sensitivity of the buttons/menuitems
        '''
        selection = args
        selected = selection.get_selected_rows()
        if selected[1] != []:
            selected_path = selected[1][0]
            self._select_func(selected_path)
        else:
            self._set_all_insensitive()

    def _select_func(self, path):
        is_selected = False
        selected = self._ui.transfers_list.get_selection().get_selected_rows()
        if selected[1] != []:
            selected_path = selected[1][0]
            if selected_path == path:
                is_selected = True
        self._set_buttons_sensitive(path, is_selected)
        self._set_cleanup_sensitivity()
        return True

    def _on_cleanup_button_clicked(self, widget):
        i = len(self.model) - 1
        while i >= 0:
            iter_ = self.model.get_iter((i))
            sid = self.model[iter_][Column.SID]
            file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
            if is_transfer_stopped(file_props):
                self._remove_transfer(iter_, sid, file_props)
            i -= 1
        self._ui.transfers_list.get_selection().unselect_all()
        self._set_all_insensitive()

    def _toggle_pause_continue(self, status):
        if status:
            self._ui.pause_resume_button.set_icon_name(
                'media-playback-pause-symbolic')
        else:
            self._ui.pause_resume_button.set_icon_name(
                'media-playback-start-symbolic')

    def _on_pause_resume_button_clicked(self, widget):
        selected = self._ui.transfers_list.get_selection().get_selected()
        if selected is None or selected[1] is None:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][Column.SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        if is_transfer_paused(file_props):
            file_props.last_time = time.time()
            file_props.paused = False
            status_types = {'r': 'download', 's': 'upload'}
            self.set_status(file_props, status_types[sid[0]])
            self._toggle_pause_continue(True)
            if file_props.continue_cb:
                file_props.continue_cb()
        elif is_transfer_active(file_props):
            file_props.paused = True
            self.set_status(file_props, 'pause')
            # Reset that to compute speed only when we resume
            file_props.transferred_size = []
            self._toggle_pause_continue(False)

    def _on_cancel_button_clicked(self, widget):
        selected = self._ui.transfers_list.get_selection().get_selected()
        if selected is None or selected[1] is None:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][Column.SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        self.cancel_transfer(file_props)

    def cancel_transfer(self, file_props: FileProp) -> None:
        # TODO: does not cancel transfer somehow
        account = file_props.tt_account
        if account is None or account not in app.settings.get_active_accounts():
            return
        client = app.get_client(account)
        # Check if we are in a IBB transfer
        if file_props.direction:
            client.get_module('IBB').send_close(file_props)
        client.get_module('Bytestream').disconnect_transfer(file_props)
        self.set_status(file_props, 'stop')

    def _on_notify_ft_complete_toggled(self, widget, *args):
        app.settings.set('notify_on_file_complete', widget.get_active())

    def _on_file_transfers_dialog_delete_event(self, widget, event):
        self.window.hide()
        return True  # Do NOT destroy window

    def _show_context_menu(self, event, iter_):
        # change the sensitive property of the buttons and menuitems
        if iter_:
            path = self.model.get_path(iter_)
            self._set_buttons_sensitive(path, True)

        if event.type == Gdk.EventType.KEY_PRESS:
            event_button = 0
        else:
            event_button = event.button

        self._ui.file_transfers_menu.show_all()
        self._ui.file_transfers_menu.popup(
            None,
            self._ui.transfers_list,
            None,
            None,
            event_button,
            event.time)

    def _on_transfers_list_key_press_event(self, widget, event):
        '''
        When a key is pressed in the treeviews
        '''
        iter_ = None
        try:
            iter_ = self._ui.transfers_list.get_selection().get_selected()[1]
        except TypeError:
            self._ui.transfers_list.get_selection().unselect_all()

        if iter_ is not None:
            path = self.model.get_path(iter_)
            self._ui.transfers_list.get_selection().select_path(path)

        if event.keyval == Gdk.KEY_Menu:
            self._show_context_menu(event, iter_)
            return True

    def _on_transfers_list_button_release_event(self, widget, event):
        # hide tooltip, no matter the button is pressed
        path = None
        try:
            path = self._ui.transfers_list.get_path_at_pos(int(event.x),
                                                           int(event.y))[0]
        except TypeError:
            self._ui.transfers_list.get_selection().unselect_all()
        if path is None:
            self._set_all_insensitive()
        else:
            self._select_func(path)

    def _on_transfers_list_button_press_event(self, widget, event):
        # hide tooltip, no matter the button is pressed
        path, iter_ = None, None
        try:
            path = self._ui.transfers_list.get_path_at_pos(int(event.x),
                                                           int(event.y))[0]
        except TypeError:
            self._ui.transfers_list.get_selection().unselect_all()
        if event.button == 3:  # Right click
            if path:
                self._ui.transfers_list.get_selection().select_path(path)
                iter_ = self.model.get_iter(path)
            self._show_context_menu(event, iter_)
            if path:
                return True

    def _on_open_folder_menuitem_activate(self, widget):
        selected = self._ui.transfers_list.get_selection().get_selected()
        if not selected or not selected[1]:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][Column.SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        if not file_props.file_name:
            return

        folder = Path(file_props.file_name).parent
        open_file(folder)

    def _on_cancel_menuitem_activate(self, widget):
        self._on_cancel_button_clicked(widget)

    def _on_continue_menuitem_activate(self, widget):
        self._on_pause_resume_button_clicked(widget)

    def _on_pause_resume_menuitem_activate(self, widget):
        self._on_pause_resume_button_clicked(widget)

    def _on_remove_menuitem_activate(self, widget):
        selected = self._ui.transfers_list.get_selection().get_selected()
        if not selected or not selected[1]:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][Column.SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        self._remove_transfer(s_iter, sid, file_props)
        self._set_all_insensitive()

    def _on_file_transfers_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:  # ESCAPE
            self.window.hide()
