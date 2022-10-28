# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
#                    Norman Rasmussen <norman AT rasmussen.co.za>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    James Newton <redshodan AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

from typing import Any
from typing import Dict
from typing import Optional
from typing import Union

import sys
import time
import logging
from functools import partial
from threading import Thread

from gi.repository import Gtk
from gi.repository import GLib

from nbxmpp import idlequeue
from nbxmpp import Hashes2
from nbxmpp import JID

from gajim.common import app
from gajim.common import exceptions
from gajim.common import proxy65_manager
from gajim.common import socks5
from gajim.common import helpers

from gajim.common.events import FileCompleted
from gajim.common.events import FileHashError
from gajim.common.events import FileProgress
from gajim.common.events import FileError
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.structs import OutgoingMessage
from gajim.common.i18n import _
from gajim.common.const import FTState
from gajim.common.file_props import FileProp
from gajim.common.types import ChatContactT

from gajim.common.modules.httpupload import HTTPFileTransfer

from gajim.gui.dialogs import ErrorDialog
from gajim.gui.filechoosers import FileChooserDialog
from gajim.gui.file_transfer_send import SendFileDialog
from gajim.gui.filetransfer import FileTransfersWindow
from gajim.gui.control import ChatControl
from gajim.plugins.repository import PluginRepository

log = logging.getLogger('gajim.interface')


class Interface:
    def __init__(self):
        app.interface = self
        app.thread_interface = ThreadInterface

        app.idlequeue = idlequeue.get_idlequeue()
        # resolve and keep current record of resolved hosts
        app.socks5queue = socks5.SocksQueue(
            app.idlequeue,
            self.handle_event_file_rcv_completed,
            self.handle_event_file_progress,
            self.handle_event_file_error)

        self._last_ft_progress_update: float = 0

        app.proxy65_manager = proxy65_manager.Proxy65Manager(app.idlequeue)

        self._register_core_handlers()

        self.instances: dict[str, Any] = {}

        for acc in app.settings.get_active_accounts():
            app.automatic_rooms[acc] = {}
            app.to_be_removed[acc] = []
            app.nicks[acc] = app.settings.get_account_setting(acc, 'name')

    # Jingle File Transfer
    @staticmethod
    def handle_event_file_error(title: str, message: str) -> None:
        # TODO: integrate this better
        ErrorDialog(title, message)

    def handle_event_file_progress(self,
                                   _account: str,
                                   file_props: FileProp
                                   ) -> None:
        if time.time() - self._last_ft_progress_update < 0.5:
            # Update progress every 500ms only
            return

        self._last_ft_progress_update = time.time()
        app.ged.raise_event(FileProgress(file_props=file_props))

    def handle_event_file_rcv_completed(self,
                                        account: str,
                                        file_props: FileProp
                                        ) -> None:
        jid = JID.from_string(file_props.receiver)
        if file_props.error != 0:
            self.instances['file_transfers'].set_status(file_props, 'stop')

        if (not file_props.completed and (
                file_props.stalled or file_props.paused)):
            return

        if file_props.type_ == 'r':  # We receive a file
            app.socks5queue.remove_receiver(file_props.sid, True, True)
            if file_props.session_type != 'jingle':
                return

            if file_props.hash_ and file_props.error == 0:
                # We compare hashes in a new thread
                self.hashThread = Thread(
                    target=self.__compare_hashes,
                    args=(account, file_props))
                self.hashThread.start()
            else:
                # We didn't get the hash, sender probably doesn't support that
                if file_props.error == 0:
                    app.ged.raise_event(
                        FileCompleted(file_props=file_props,
                                      account=account,
                                      jid=jid.bare))
                else:
                    app.ged.raise_event(
                        FileError(file_props=file_props,
                                  account=account,
                                  jid=jid.bare))

                # End jingle session
                # TODO: Only if there are no other parallel downloads in
                # this session
                client = app.get_client(account)
                session = client.get_module('Jingle').get_jingle_session(
                    jid=None, sid=file_props.sid)
                if session:
                    session.end_session()
        else:  # We send a file
            app.socks5queue.remove_sender(file_props.sid, True, True)
            if file_props.error == 0:
                app.ged.raise_event(
                    FileCompleted(file_props=file_props,
                                  account=account,
                                  jid=jid.bare))
            else:
                app.ged.raise_event(
                    FileError(file_props=file_props,
                              account=account,
                              jid=jid.bare))

    @staticmethod
    def __compare_hashes(account: str, file_props: FileProp) -> None:
        hashes = Hashes2()
        try:
            file_ = open(file_props.file_name, 'rb')
        except Exception:
            return
        log.debug('Computing file hash')
        hash_ = hashes.calculateHash(file_props.algo, file_)
        file_.close()
        # File is corrupt if the calculated hash differs from the received hash
        jid = JID.from_string(file_props.sender)
        if file_props.hash_ == hash_:
            app.ged.raise_event(
                FileCompleted(file_props=file_props,
                              account=account,
                              jid=jid.bare))
        else:
            # Wrong hash, we need to get the file again!
            file_props.error = -10
            app.ged.raise_event(
                FileHashError(file_props=file_props,
                              account=account,
                              jid=jid.bare))
        # End jingle session
        client = app.get_client(account)
        session = client.get_module('Jingle').get_jingle_session(
            jid=None, sid=file_props.sid)
        if session:
            session.end_session()

    def send_httpupload(self,
                        chat_control: ChatControl,
                        path: Optional[str] = None
                        ) -> None:
        if path is not None:
            self._send_httpupload(chat_control, path)
            return

        accept_cb = partial(self._on_file_dialog_ok, chat_control)
        FileChooserDialog(accept_cb,
                          select_multiple=True,
                          transient_for=app.window)

    def _on_file_dialog_ok(self,
                           chat_control: ChatControl,
                           paths: list[str]
                           ) -> None:
        for path in paths:
            self._send_httpupload(chat_control, path)

    def _send_httpupload(self, chat_control: ChatControl, path: str) -> None:
        client = app.get_client(chat_control.contact.account)
        encryption = chat_control.contact.settings.get('encryption') or None
        try:
            transfer = client.get_module('HTTPUpload').make_transfer(
                path,
                encryption,
                chat_control.contact,
                chat_control.is_groupchat)
        except exceptions.FileError as error:
            ErrorDialog(_('Could not Open File'), str(error))
            return

        transfer.connect('cancel', self._on_cancel_upload)
        transfer.connect('state-changed',
                         self._on_http_upload_state_changed)
        chat_control.add_file_transfer(transfer)
        client.get_module('HTTPUpload').start_transfer(transfer)

    def _on_http_upload_state_changed(self,
                                      transfer: HTTPFileTransfer,
                                      _signal_name: str,
                                      state: FTState
                                      ) -> None:
        # Note: This has to be a bound method in order to connect the signal
        if state.is_finished:
            uri = transfer.get_transformed_uri()

            type_ = 'chat'
            if transfer.is_groupchat:
                type_ = 'groupchat'

            message = OutgoingMessage(account=transfer.account,
                                      contact=transfer.contact,
                                      message=uri,
                                      type_=type_,
                                      oob_url=uri)

            client = app.get_client(transfer.account)
            client.send_message(message)

    def _on_cancel_upload(self,
                          transfer: HTTPFileTransfer,
                          _signal_name: str
                          ) -> None:
        # Note: This has to be a bound method in order to connect the signal
        client = app.get_client(transfer.account)
        client.get_module('HTTPUpload').cancel_transfer(transfer)

    def _get_pref_ft_method(self, contact: ChatContactT) -> Optional[str]:
        ft_pref = app.settings.get_account_setting(contact.account,
                                                   'filetransfer_preference')
        httpupload = app.window.get_action_enabled('send-file-httpupload')
        jingle = app.window.get_action_enabled('send-file-jingle')

        if isinstance(contact, GroupchatContact):
            if httpupload:
                return 'httpupload'
            return None

        if httpupload and jingle:
            return ft_pref

        if httpupload:
            return 'httpupload'

        if jingle:
            return 'jingle'
        return None

    def start_file_transfer(self,
                            contact: ChatContactT,
                            path: Optional[str] = None,
                            method: Optional[str] = None
                            ) -> None:

        if method is None:
            method = self._get_pref_ft_method(contact)
            if method is None:
                return

        control = app.window.get_control()
        if not control.has_active_chat():
            return

        if path is None:
            if method == 'httpupload':
                self.send_httpupload(control)
                return
            if method == 'jingle':
                self.instances['file_transfers'].show_file_send_request(
                    contact.account, contact)
            return

        if method == 'httpupload':
            self.send_httpupload(control, path)
        else:
            assert isinstance(contact, BareContact)
            send_callback = partial(
                self.instances['file_transfers'].send_file,
                contact.account,
                contact)
            SendFileDialog(contact, send_callback, app.window, [path])

    @staticmethod
    def create_groupchat(account: str,
                         room_jid: str,
                         config: Dict[str, Union[str, bool]]
                         ) -> None:
        if app.window.chat_exists(account, JID.from_string(room_jid)):
            log.error('Trying to create groupchat '
                      'which is already added as chat')
            return

        client = app.get_client(account)
        client.get_module('MUC').create(room_jid, config)

    @staticmethod
    def show_add_join_groupchat(account: str,
                                jid: str,
                                nickname: Optional[str] = None,
                                password: Optional[str] = None
                                ) -> None:
        if not app.window.chat_exists(account, JID.from_string(jid)):
            client = app.get_client(account)
            client.get_module('MUC').join(
                jid, nick=nickname, password=password)

        app.window.add_group_chat(account, JID.from_string(jid), select=True)

    @staticmethod
    def start_chat_from_jid(account: str,
                            jid: str,
                            message: Optional[str] = None
                            ) -> None:

        jid_ = JID.from_string(jid)
        if app.window.chat_exists(account, jid_):
            app.window.select_chat(account, jid_)
            if message is not None:
                message_input = app.window.get_chat_stack().get_message_input()
                message_input.insert_text(message)
            return

        app.app.activate_action(
            'start-chat', GLib.Variant('as', [str(jid), message or '']))

    def autoconnect(self) -> None:
        '''
        Auto connect at startup
        '''

        for client in app.get_clients():
            account = client.account
            if not app.settings.get_account_setting(account,
                                                    'autoconnect'):
                continue

            status = 'online'
            status_message = ''

            if app.settings.get_account_setting(account, 'restore_last_status'):
                status = app.settings.get_account_setting(
                    account, 'last_status')
                status_message = app.settings.get_account_setting(
                    account, 'last_status_msg')
                status_message = helpers.from_one_line(status_message)

            client.change_status(status, status_message)

    def change_status(self,
                      status: str,
                      account: Optional[str] = None
                      ) -> None:

        if status is None:
            status = helpers.get_global_show()

        if account is not None:
            self._change_status(account, status)
            return

        for client in app.get_clients():
            if not app.settings.get_account_setting(client.account,
                                                    'sync_with_global_status'):
                continue

            self._change_status(client.account, status)

    @staticmethod
    def _change_status(account: str, status: str) -> None:
        client = app.get_client(account)
        message = client.status_message

        if status == 'offline':
            # TODO delete pep
            # self.delete_pep(app.get_jid_from_account(account), account)
            pass

        client.change_status(status, message)

    def process_connections(self) -> bool:
        '''
        Called each foo (200) milliseconds. Check for idlequeue timeouts
        '''
        try:
            app.idlequeue.process()
        except Exception:
            # Otherwise, an exception will stop our loop

            if sys.platform == 'win32':
                # On Windows process() calls select.select(), so we need this
                # executed as often as possible.
                # Adding it directly with GLib.idle_add() causes Gajim to use
                # too much CPU time. That's why its added with 1ms timeout.
                # On Linux only alarms are checked in process(), so we use
                # a bigger timeout
                timeout, in_seconds = 1, None
            else:
                timeout, in_seconds = app.idlequeue.PROCESS_TIMEOUT

            if in_seconds:
                GLib.timeout_add_seconds(timeout, self.process_connections)
            else:
                GLib.timeout_add(timeout, self.process_connections)
            raise
        return True  # renew timeout (loop for ever)

    @staticmethod
    def save_config() -> None:
        app.settings.save()

    def save_avatar(self, data: bytes) -> Optional[str]:
        return app.app.avatar_storage.save_avatar(data)

    def avatar_exists(self, filename: str) -> bool:
        return app.app.avatar_storage.get_avatar_path(filename) is not None

    def run(self, _application: Gtk.Application) -> None:
        # Creating plugin manager
        from gajim import plugins
        app.plugin_manager = plugins.PluginManager()
        app.plugin_manager.init_plugins()

        app.plugin_repository = PluginRepository()

        for client in app.get_clients():
            client.get_module('Roster').load_roster()

        # get instances for windows/dialogs that will show_all()/hide()
        self.instances['file_transfers'] = FileTransfersWindow()

        GLib.timeout_add(100, self.autoconnect)
        if sys.platform == 'win32':
            timeout, in_seconds = 20, None
        else:
            timeout, in_seconds = app.idlequeue.PROCESS_TIMEOUT

        if in_seconds:
            GLib.timeout_add_seconds(timeout, self.process_connections)
        else:
            GLib.timeout_add(timeout, self.process_connections)

        def remote_init():
            if app.settings.get('remote_control'):
                try:
                    from gajim.common.dbus import remote_control
                    remote_control.GajimRemote()
                except Exception:
                    log.exception('Failed to init remote control')

        GLib.timeout_add_seconds(5, remote_init)


class ThreadInterface:
    def __init__(self, func, func_args=(), callback=None, callback_args=()):
        '''
        Call a function in a thread
        '''
        def thread_function(func, func_args, callback, callback_args):
            output = func(*func_args)
            if callback:
                GLib.idle_add(callback, output, *callback_args)

        Thread(target=thread_function,
               args=(func,
                     func_args,
                     callback,
                     callback_args)).start()
