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

import os
import sys
import time
import logging
from functools import partial
from threading import Thread
from importlib.util import find_spec

from gi.repository import Gtk
from gi.repository import GLib

from nbxmpp import idlequeue
from nbxmpp import Hashes2
from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common import exceptions
from gajim.common import proxy65_manager
from gajim.common import socks5
from gajim.common import helpers
from gajim.common import passwords

from gajim.common.events import AccountEnabled
from gajim.common.events import AccountDisabled
from gajim.common.events import FileCompleted
from gajim.common.events import FileHashError
from gajim.common.events import FileProgress
from gajim.common.events import FileError
from gajim.common.events import MucAdded
from gajim.common.events import PasswordRequired
from gajim.common.helpers import ask_for_status_message
from gajim.common.structs import OutgoingMessage
from gajim.common.i18n import _
from gajim.common.client import Client
from gajim.common.preview import PreviewManager
from gajim.common.const import FTState
from gajim.common.file_props import FileProp

from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.httpupload import HTTPFileTransfer

from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ErrorDialog
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.filechoosers import FileChooserDialog
from gajim.gui.filetransfer import FileTransfersWindow
from gajim.gui.menus import build_accounts_menu
from gajim.gui.util import get_app_window
from gajim.gui.util import get_app_windows
from gajim.gui.util import get_color_for_account
from gajim.gui.util import open_window
from gajim.gui.types import ControlT

log = logging.getLogger('gajim.interface')

ContactT = Union[BareContact, GroupchatContact, GroupchatParticipant]


class Interface:
    def __init__(self):
        app.interface = self
        app.thread_interface = ThreadInterface

        self.handlers = {}

        self.preview_manager = PreviewManager()

        app.idlequeue = idlequeue.get_idlequeue()
        # resolve and keep current record of resolved hosts
        app.socks5queue = socks5.SocksQueue(
            app.idlequeue,
            self.handle_event_file_rcv_completed,
            self.handle_event_file_progress,
            self.handle_event_file_error)

        self._last_ft_progress_update: float = 0

        app.proxy65_manager = proxy65_manager.Proxy65Manager(app.idlequeue)

        self._create_core_handlers_list()
        self._register_core_handlers()

        app.ged.register_event_handler('muc-added',
                                       ged.CORE,
                                       self._on_muc_added)

        self.instances = {}

        for acc in app.connections:
            self.instances[acc] = {
                'infos': {},
                'disco': {}
            }
            app.automatic_rooms[acc] = {}
            app.newly_added[acc] = []
            app.to_be_removed[acc] = []
            app.nicks[acc] = app.settings.get_account_setting(acc, 'name')
            app.block_signed_in_notifications[acc] = True

    def _create_core_handlers_list(self) -> None:
        # pylint: disable=line-too-long
        self.handlers = {
            'iq-error-received': [self.handle_event_iq_error],
            'http-auth-received': [self.handle_event_http_auth],
            'password-required': [self.handle_event_password_required],
            'client-cert-passphrase': [self.handle_event_client_cert_passphrase],
            'signed-in': [self.handle_event_signed_in],
            'presence-received': [self.handle_event_presence],
            'our-show': [self.handle_event_status],
            'message-sent': [self.handle_event_msgsent],
            'message-not-sent': [self.handle_event_msgnotsent],
            'read-state-sync': [self.handle_event_read_state_sync],
        }
        # pylint: enable=line-too-long

    def _register_core_handlers(self) -> None:
        """
        Register core handlers in Global Events Dispatcher (GED).

        This is part of rewriting whole events handling system to use GED.
        """
        for event_name, event_handlers in self.handlers.items():
            for event_handler in event_handlers:
                prio = ged.GUI1
                if isinstance(event_handler, tuple):
                    prio = event_handler[1]
                    event_handler = event_handler[0]
                app.ged.register_event_handler(
                    event_name,
                    prio,
                    event_handler)

    @staticmethod
    def handle_event_iq_error(event):
        ctrl = app.window.get_control(event.account, event.properties.jid.bare)
        if ctrl and ctrl.is_groupchat:
            ctrl.add_info_message(f'Error: {event.properties.error}')

    @staticmethod
    def handle_event_http_auth(event):
        # ('HTTP_AUTH', account, (method, url, transaction_id, iq_obj, msg))
        def _response(answer: str) -> None:
            event.conn.get_module('HTTPAuth').build_http_auth_answer(
                event.stanza, answer)

        account = event.conn.name
        message = _('HTTP (%(method)s) Authorization '
                    'for %(url)s (ID: %(id)s)') % {
                        'method': event.method,
                        'url': event.url,
                        'id': event.iq_id}
        sec_msg = _('Do you accept this request?')
        if app.get_number_of_connected_accounts() > 1:
            sec_msg = _('Do you accept this request (account: %s)?') % account
        if event.msg:
            sec_msg = event.msg + '\n' + sec_msg
        message = message + '\n' + sec_msg

        ConfirmationDialog(
            _('Authorization Request'),
            _('HTTP Authorization Request'),
            message,
            [DialogButton.make('Cancel',
                               text=_('_No'),
                               callback=_response,
                               args=['no']),
             DialogButton.make('Accept',
                               callback=_response,
                               args=['yes'])]).show()

    @staticmethod
    def handle_event_client_cert_passphrase(event):
        open_window('PasswordDialog', account=event.conn.name, event=event)

    @staticmethod
    def handle_event_password_required(event: PasswordRequired) -> None:
        open_window('PasswordDialog', account=event.conn.name, event=event)

    @staticmethod
    def handle_event_signed_in(event):
        """
        SIGNED_IN event is emitted when we sign in, so handle it
        """
        # ('SIGNED_IN', account, ())
        # block signed in notifications for 30 seconds

        # Add our own JID into the DB
        app.storage.archive.insert_jid(event.conn.get_own_jid().bare)
        account = event.conn.name
        app.block_signed_in_notifications[account] = True

        pep_supported = event.conn.get_module('PEP').supported

        if event.conn.get_module('MAM').available:
            event.conn.get_module('MAM').request_archive_on_signin()

        # enable location listener
        if (pep_supported and app.is_installed('GEOCLUE') and
                app.settings.get_account_setting(account, 'publish_location')):
            pass
            # location.enable()

        if ask_for_status_message(event.conn.status, signin=True):
            app.window.show_account_page(account)

    def handle_event_presence(self, event):
        # TODO:
        # 'NOTIFY' (account, (jid, status, status message, resource,
        # priority, timestamp))
        #
        # Contact changed show
        account = event.conn.name
        jid = event.jid

        if app.jid_is_transport(jid):
            # It must be an agent

            # transport just signed in/out, don't show
            # popup notifications for 30s
            account_jid = account + '/' + jid
            app.block_signed_in_notifications[account_jid] = True
            GLib.timeout_add_seconds(30, self._unblock_signed_in_notifications,
                                     account_jid)

        ctrl = app.window.get_control(account, jid)
        if ctrl and ctrl.session and len(event.contact_list) > 1:
            ctrl.remove_session(ctrl.session)

    def handle_event_status(self, event):
        if event.show in ('offline', 'error'):
            # TODO: Close all account windows
            pass

        if event.show == 'offline':
            app.block_signed_in_notifications[event.account] = True
        else:
            # 30 seconds after we change our status to sth else than offline
            # we stop blocking notifications of any kind
            # this prevents from getting the roster items as 'just signed in'
            # contacts. 30 seconds should be enough time
            GLib.timeout_add_seconds(30,
                                     self._unblock_signed_in_notifications,
                                     event.account)

    @staticmethod
    def _unblock_signed_in_notifications(account: str) -> None:
        app.block_signed_in_notifications[account] = False

    @staticmethod
    def handle_event_msgsent(event):
        if not event.play_sound:
            return

        enabled = app.settings.get_soundevent_settings(
            'message_sent')['enabled']
        if enabled:
            if isinstance(event.jid, list) and len(event.jid) > 1:
                return
            helpers.play_sound('message_sent', event.account)

    @staticmethod
    def handle_event_msgnotsent(event):
        # ('MSGNOTSENT', account, (jid, ierror_msg, msg, time, session))
        msg = _('error while sending %(message)s ( %(error)s )') % {
            'message': event.message,
            'error': event.error}
        if not event.session:
            # No session. This can happen when sending a message from
            # gajim-remote
            log.warning(msg)
            return
        event.session.roster_message(
            event.jid,
            msg,
            event.time_,
            event.conn.name,
            msg_type='error')

    @staticmethod
    def handle_event_read_state_sync(event):
        if event.type.is_groupchat:
            jid = event.jid.bare
        else:
            jid = event.jid

        control = app.window.get_control(event.account, jid)
        if control is None:
            log.warning('No ChatControl found')
            return

        if event.marker_id != control.last_msg_id:
            return

        app.window.mark_as_read(event.account, jid, send_marker=False)

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
                        chat_control: ControlT,
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
                           chat_control: ControlT,
                           paths: list[str]
                           ) -> None:
        for path in paths:
            self._send_httpupload(chat_control, path)

    def _send_httpupload(self, chat_control: ControlT, path: str) -> None:
        client = app.get_client(chat_control.account)
        try:
            transfer = client.get_module('HTTPUpload').make_transfer(
                path,
                chat_control.encryption,
                chat_control.contact,
                chat_control.is_groupchat)
        except exceptions.FileError as error:
            ErrorDialog(_('Could not Open File'), error)
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
                control = app.window.get_control(account, jid_)
                if control is None:
                    return
                control.msg_textview.insert_text(message)
            return

        # TODO: handle message arg in StartChat
        app.app.activate_action('start-chat', GLib.Variant('s', str(jid)))

    @staticmethod
    def _on_muc_added(event: MucAdded) -> None:
        if app.window.chat_exists(event.account, JID.from_string(event.jid)):
            return

        app.window.add_group_chat(event.account, JID.from_string(event.jid))

    @staticmethod
    def create_account(account: str,
                       username: str,
                       domain: str,
                       password: str,
                       proxy_name: str,
                       custom_host: str,
                       anonymous:bool = False
                       ) -> None:

        account_label = f'{username}@{domain}'
        if anonymous:
            username = 'anon'
            account_label = f'anon@{domain}'

        config = {}
        config['active'] = False
        config['name'] = username
        config['resource'] = f'gajim.{helpers.get_random_string(8)}'
        config['account_label'] = account_label
        config['account_color'] = get_color_for_account(f'{username}@{domain}')
        config['hostname'] = domain
        config['savepass'] = True
        config['anonymous_auth'] = anonymous
        config['autoconnect'] = True
        config['sync_with_global_status'] = True

        if proxy_name is not None:
            config['proxy'] = proxy_name

        use_custom_host = custom_host is not None
        config['use_custom_host'] = use_custom_host
        if custom_host:
            host, _protocol, type_ = custom_host
            host, port = host.rsplit(':', maxsplit=1)
            config['custom_port'] = int(port)
            config['custom_host'] = host
            config['custom_type'] = type_.value

        app.settings.add_account(account)
        for opt, value in config.items():
            app.settings.set_account_setting(account, opt, value)

        # Password module depends on existing config
        passwords.save_password(account, password)

        app.css_config.refresh()

        # Action must be added before account window is updated
        app.app.add_account_actions(account)

        window = get_app_window('AccountsWindow')
        if window is not None:
            window.add_account(account)

    def enable_account(self, account: str) -> None:
        app.connections[account] = Client(account)

        app.plugin_manager.register_modules_for_account(
            app.connections[account])

        app.ged.register_event_handler(
            'muc-added', ged.CORE, self._on_muc_added)

        # update variables
        self.instances[account] = {
            'infos': {},
            'disco': {}
        }

        app.automatic_rooms[account] = {}
        app.newly_added[account] = []
        app.to_be_removed[account] = []
        app.nicks[account] = app.settings.get_account_setting(account,
                                                                  'name')
        app.block_signed_in_notifications[account] = True

        app.settings.set_account_setting(account, 'active', True)
        build_accounts_menu()
        app.app.update_app_actions_state()

        app.ged.raise_event(AccountEnabled(account=account))

        app.connections[account].change_status('online', '')
        window = get_app_window('AccountsWindow')
        if window is not None:
            GLib.idle_add(window.enable_account, account, True)

    def disable_account(self, account: str) -> None:
        for win in get_app_windows(account):
            # Close all account specific windows, except the RemoveAccount
            # dialog. It shows if the removal was successful.
            if type(win).__name__ == 'RemoveAccount':
                continue
            win.destroy()

        app.settings.set_account_setting(account, 'roster_version', '')
        app.settings.set_account_setting(account, 'active', False)
        build_accounts_menu()
        app.app.update_app_actions_state()

        app.ged.raise_event(AccountDisabled(account=account))

        app.connections[account].cleanup()
        del app.connections[account]
        del self.instances[account]
        del app.nicks[account]
        del app.block_signed_in_notifications[account]
        del app.automatic_rooms[account]
        del app.to_be_removed[account]
        del app.newly_added[account]

    def remove_account(self, account: str) -> None:
        if app.settings.get_account_setting(account, 'active'):
            self.disable_account(account)

        app.storage.cache.remove_roster(account)
        # Delete password must be before del_per() because it calls set_per()
        # which would recreate the account with defaults values if not found
        passwords.delete_password(account)
        app.settings.remove_account(account)
        app.app.remove_account_actions(account)

        window = get_app_window('AccountsWindow')
        if window is not None:
            window.remove_account(account)

    def autoconnect(self) -> None:
        """
        Auto connect at startup
        """

        for account, con in app.connections.items():
            if not app.settings.get_account_setting(account, 'autoconnect'):
                continue

            status = 'online'
            status_message = ''

            if app.settings.get_account_setting(account, 'restore_last_status'):
                status = app.settings.get_account_setting(
                    account, 'last_status')
                status_message = app.settings.get_account_setting(
                    account, 'last_status_msg')
                status_message = helpers.from_one_line(status_message)

            con.change_status(status, status_message)

    def change_status(self,
                      status: str,
                      account: Optional[str] = None
                      ) -> None:
        ask = ask_for_status_message(status)

        if status is None:
            status = helpers.get_global_show()

        if ask:
            if account is None:
                app.window.show_app_page()
            else:
                app.window.show_account_page(account)
            return

        if account is not None:
            self._change_status(account, status)
            return

        for acc in app.connections:
            if not app.settings.get_account_setting(acc,
                                                    'sync_with_global_status'):
                continue

            self._change_status(acc, status)

    def change_account_status(self, account: str, status: str) -> None:
        ask = ask_for_status_message(status)

        client = app.get_client(account)
        if status is None:
            status = client.status

        if ask:
            app.window.show_account_page(account)
            return

        self._change_status(account, status)

    @staticmethod
    def _change_status(account: str, status: str) -> None:
        client = app.get_client(account)
        message = client.status_message
        if status != 'offline':
            app.settings.set_account_setting(account, 'last_status', status)
            app.settings.set_account_setting(
                account,
                'last_status_msg',
                helpers.to_one_line(message))

        if status == 'offline':
            # TODO delete pep
            # self.delete_pep(app.get_jid_from_account(account), account)
            pass

        client.change_status(status, message)

    def process_connections(self) -> bool:
        """
        Called each foo (200) milliseconds. Check for idlequeue timeouts
        """
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

    def get_avatar(self,
                   contact: ContactT,
                   size: int,
                   scale: int,
                   show: Optional[str] = None,
                   pixbuf: bool = False,
                   style: str = 'circle') -> Any:
        if pixbuf:
            return app.app.avatar_storage.get_pixbuf(
                contact, size, scale, show, style=style)
        return app.app.avatar_storage.get_surface(
            contact, size, scale, show, style=style)

    def avatar_exists(self, filename: str) -> bool:
        return app.app.avatar_storage.get_avatar_path(filename) is not None

    @staticmethod
    def create_ipython_window() -> None:
        # Check if IPython is installed
        ipython = find_spec('IPython')
        is_installed = ipython is not None
        if not is_installed:
            # Abort early to avoid tracebacks
            print('IPython is not installed')
            return
        try:
            from gajim.dev.ipython_view import IPythonView
        except ImportError:
            print('ipython_view not found')
            return
        from gi.repository import Pango

        if os.name == 'nt':
            font = 'Lucida Console 9'
        else:
            font = 'Luxi Mono 10'

        window = Gtk.Window()
        window.set_title(_('Gajim: IPython Console'))
        window.set_size_request(750, 550)
        window.set_resizable(True)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        view = IPythonView()
        view.override_font(Pango.FontDescription(font))
        view.set_wrap_mode(Gtk.WrapMode.CHAR)
        sw.add(view)
        window.add(sw)
        window.show_all()

        def _on_delete(win, _event):
            win.hide()
            return True
        window.connect('delete_event', _on_delete)
        view.updateNamespace({'gajim': app})
        app.ipython_window = window

    def run(self, _application: Gtk.Application) -> None:
        # Creating plugin manager
        from gajim import plugins
        app.plugin_manager = plugins.PluginManager()
        app.plugin_manager.init_plugins()

        for con in app.connections.values():
            con.get_module('Roster').load_roster()

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
                    from gajim import remote_control
                    remote_control.GajimRemote()
                except Exception:
                    pass
        GLib.timeout_add_seconds(5, remote_init)


class ThreadInterface:
    def __init__(self, func, func_args=(), callback=None, callback_args=()):
        """
        Call a function in a thread
        """
        def thread_function(func, func_args, callback, callback_args):
            output = func(*func_args)
            if callback:
                GLib.idle_add(callback, output, *callback_args)

        Thread(target=thread_function,
               args=(func,
                     func_args,
                     callback,
                     callback_args)).start()
