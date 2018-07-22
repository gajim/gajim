##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##      - Yann Leboulanger <asterix@lagaule.org>
##      - Nikos Kouremenos <nkour@jabber.org>
##      - Dimitur Kirov <dkirov@gmail.com>
##      - Travis Shirk <travis@pobox.com>
## - Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import time

import nbxmpp

from gajim.common import app

from gajim.common.protocol.bytestream import ConnectionSocks5BytestreamZeroconf
from gajim.common.zeroconf.zeroconf import Constant
from gajim.common import connection_handlers
from gajim.common.nec import NetworkIncomingEvent, NetworkEvent
from gajim.common.modules.user_nickname import parse_nickname
from gajim.common.modules.chatstates import parse_chatstate
from gajim.common.modules.misc import parse_eme
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_attention
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml

import logging
log = logging.getLogger('gajim.c.z.connection_handlers_zeroconf')

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
               'invisible']
# kind of events we can wait for an answer
AGENT_REMOVED = 'agent_removed'


class ZeroconfMessageReceivedEvent(NetworkIncomingEvent):
    name = 'message-received'


class DecryptedMessageReceivedEvent(NetworkIncomingEvent):
    name = 'decrypted-message-received'


class ConnectionVcard:
    def add_sha(self, p, *args):
        return p

    def add_caps(self, p):
        return p


class ConnectionHandlersZeroconf(ConnectionVcard,
ConnectionSocks5BytestreamZeroconf,
connection_handlers.ConnectionHandlersBase,
connection_handlers.ConnectionJingle):
    def __init__(self):
        ConnectionVcard.__init__(self)
        ConnectionSocks5BytestreamZeroconf.__init__(self)
        connection_handlers.ConnectionJingle.__init__(self)
        connection_handlers.ConnectionHandlersBase.__init__(self)

    def _messageCB(self, ip, con, stanza):
        """
        Called when we receive a message
        """
        log.debug('Zeroconf MessageCB')

        app.nec.push_incoming_event(NetworkEvent(
            'raw-message-received',
            conn=self,
            stanza=stanza,
            account=self.name))

        type_ = stanza.getType()
        if type_ is None:
            type_ = 'normal'

        id_ = stanza.getID()

        fjid = str(stanza.getFrom())

        if fjid is None:
            for key in self.connection.zeroconf.contacts:
                if ip == self.connection.zeroconf.contacts[key][
                        Constant.ADDRESS]:
                    fjid = key
                    break

        jid, resource = app.get_room_and_nick_from_fjid(fjid)

        thread_id = stanza.getThread()
        msgtxt = stanza.getBody()

        session = self.get_or_create_session(fjid, thread_id)

        if thread_id and not session.received_thread_id:
            session.received_thread_id = True

        session.last_receive = time.time()

        event_attr = {
            'conn': self,
            'stanza': stanza,
            'account': self.name,
            'id_': id_,
            'encrypted': False,
            'additional_data': {},
            'forwarded': False,
            'sent': False,
            'timestamp': time.time(),
            'fjid': fjid,
            'jid': jid,
            'resource': resource,
            'unique_id': id_,
            'mtype': type_,
            'msgtxt': msgtxt,
            'thread_id': thread_id,
            'session': session,
            'self_message': False,
            'muc_pm': False,
            'gc_control': None}

        event = ZeroconfMessageReceivedEvent(None, **event_attr)
        app.nec.push_incoming_event(event)

        app.plugin_manager.extension_point(
            'decrypt', self, event, self._on_message_decrypted)
        if not event.encrypted:
            eme = parse_eme(event.stanza)
            if eme is not None:
                event.msgtxt = eme
            self._on_message_decrypted(event)

    def _on_message_decrypted(self, event):
        try:
            self.get_module('Receipts').delegate(event)
        except nbxmpp.NodeProcessed:
            return

        event_attr = {
            'popup': False,
            'msg_log_id': None,
            'subject': None,
            'displaymarking': None,
            'form_node': None,
            'attention': parse_attention(event.stanza),
            'correct_id': parse_correction(event.stanza),
            'user_nick': parse_nickname(event.stanza),
            'xhtml': parse_xhtml(event.stanza),
            'chatstate': parse_chatstate(event.stanza),
            'stanza_id': event.unique_id
        }

        parse_oob(event.stanza, event.additional_data)

        for name, value in event_attr.items():
            setattr(event, name, value)

        if event.mtype == 'error':
            if not event.msgtxt:
                event.msgtxt = _('message')
            self.dispatch_error_message(
                event.stanza, event.msgtxt,
                event.session, event.fjid, event.timestamp)
            return

        app.nec.push_incoming_event(
            DecryptedMessageReceivedEvent(None, **vars(event)))

    def store_metacontacts(self, tags):
        """
        Fake empty method
        """
        # serverside metacontacts are not supported with zeroconf
        # (there is no server)
        pass
