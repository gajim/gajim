# Contributors for this file:
#      - Yann Leboulanger <asterix@lagaule.org>
#      - Nikos Kouremenos <nkour@jabber.org>
#      - Dimitur Kirov <dkirov@gmail.com>
#      - Travis Shirk <travis@pobox.com>
# - Stefan Bethge <stefan@lanpartei.de>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

import time
import logging

import nbxmpp

from gajim.common import app

from gajim.common import connection_handlers
from gajim.common.i18n import _
from gajim.common.helpers import AdditionalDataDict
from gajim.common.nec import NetworkIncomingEvent, NetworkEvent
from gajim.common.const import KindConstant
from gajim.common.modules.user_nickname import parse_nickname
from gajim.common.modules.util import get_eme_message
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_attention
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml
from gajim.common.connection_handlers_events import MessageErrorEvent


log = logging.getLogger('gajim.c.z.connection_handlers_zeroconf')

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
               'invisible']


class ZeroconfMessageReceivedEvent(NetworkIncomingEvent):
    name = 'message-received'


class DecryptedMessageReceivedEvent(NetworkIncomingEvent):
    name = 'decrypted-message-received'



class ConnectionHandlersZeroconf(connection_handlers.ConnectionHandlersBase):
    def __init__(self):
        connection_handlers.ConnectionHandlersBase.__init__(self)

    def _messageCB(self, con, stanza, properties):
        """
        Called when we receive a message
        """
        log.info('Zeroconf MessageCB')

        # Dont trust from attr set by sender
        stanza.setFrom(con._owner.to)

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
            'additional_data': AdditionalDataDict(),
            'forwarded': False,
            'sent': False,
            'timestamp': time.time(),
            'fjid': fjid,
            'jid': jid,
            'resource': resource,
            'unique_id': id_,
            'message_id': properties.id,
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
            if properties.eme is not None:
                event.msgtxt = get_eme_message(properties.eme)
            self._on_message_decrypted(event)

    def _on_message_decrypted(self, event):
        try:
            self.get_module('Receipts').delegate(event)
            self.get_module('Chatstate').delegate(event)
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
            'stanza_id': event.unique_id
        }

        parse_oob(event)

        for name, value in event_attr.items():
            setattr(event, name, value)

        if event.mtype == 'error':
            if not event.msgtxt:
                event.msgtxt = _('message')
            self._log_error_message(event)
            error_msg = event.stanza.getErrorMsg() or event.msgtxt
            msgtxt = None if error_msg == event.msgtxt else event.msgtxt
            app.nec.push_incoming_event(
                MessageErrorEvent(None,
                                  conn=self,
                                  fjid=event.fjid,
                                  error_code=event.stanza.getErrorCode(),
                                  error_msg=error_msg,
                                  msg=msgtxt,
                                  time_=event.timestamp,
                                  session=event.session,
                                  stanza=event.stanza))

            return

        app.nec.push_incoming_event(
            DecryptedMessageReceivedEvent(None, **vars(event)))

    def _log_error_message(self, event):
        error_msg = event.stanza.getErrorMsg() or event.msgtxt
        if app.config.should_log(self.name, event.jid):
            app.logger.insert_into_logs(self.name,
                                        event.jid,
                                        event.timestamp,
                                        KindConstant.ERROR,
                                        message=error_msg,
                                        subject=event.subject)
