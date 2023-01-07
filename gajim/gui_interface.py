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

import logging
import sys
import time
from threading import Thread

from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import Hashes2
from nbxmpp import idlequeue
from nbxmpp import JID

from gajim.common import app
from gajim.common import proxy65_manager
from gajim.common import socks5
from gajim.common.events import FileCompleted
from gajim.common.events import FileError
from gajim.common.events import FileHashError
from gajim.common.events import FileProgress
from gajim.common.file_props import FileProp

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.filetransfer import FileTransfersWindow

log = logging.getLogger('gajim.interface')


class Interface:
    def __init__(self):
        app.interface = self

        app.idlequeue = idlequeue.get_idlequeue()
        # resolve and keep current record of resolved hosts
        app.socks5queue = socks5.SocksQueue(
            app.idlequeue,
            self.handle_event_file_rcv_completed,
            self.handle_event_file_progress,
            self.handle_event_file_error)

        self._last_ft_progress_update: float = 0

        app.proxy65_manager = proxy65_manager.Proxy65Manager(app.idlequeue)

        self.instances: dict[str, Any] = {}

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

    def run(self, _application: Gtk.Application) -> None:
        # get instances for windows/dialogs that will show_all()/hide()
        self.instances['file_transfers'] = FileTransfersWindow()

        if sys.platform == 'win32':
            timeout, in_seconds = 20, None
        else:
            timeout, in_seconds = app.idlequeue.PROCESS_TIMEOUT

        if in_seconds:
            GLib.timeout_add_seconds(timeout, self.process_connections)
        else:
            GLib.timeout_add(timeout, self.process_connections)
