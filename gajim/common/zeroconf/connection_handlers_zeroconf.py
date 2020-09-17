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

from gajim.common import app

from gajim.common import connection_handlers
from gajim.common.helpers import AdditionalDataDict
from gajim.common.nec import NetworkEvent
from gajim.common.modules.util import get_eme_message
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml


log = logging.getLogger('gajim.c.z.connection_handlers_zeroconf')


class ConnectionHandlersZeroconf(connection_handlers.ConnectionHandlersBase):
    def __init__(self):
        connection_handlers.ConnectionHandlersBase.__init__(self)

    def _messageCB(self, con, stanza, properties):
        """
        Called when we receive a message
        """
        if properties.type.is_error:
            return
        log.info('Zeroconf MessageCB')

        # Don’t trust from attr set by sender
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

        msgtxt = stanza.getBody()

        session = self.get_or_create_session(fjid, properties.thread)

        if properties.thread and not session.received_thread_id:
            session.received_thread_id = True

        timestamp = time.time()
        session.last_receive = timestamp

        additional_data = AdditionalDataDict()
        parse_oob(properties, additional_data)
        parse_xhtml(properties, additional_data)

        if properties.is_encrypted:
            additional_data['encrypted'] = properties.encrypted.additional_data
        else:
            if properties.eme is not None:
                msgtxt = get_eme_message(properties.eme)

        event_attr = {
            'conn': self,
            'stanza': stanza,
            'account': self.name,
            'additional_data': additional_data,
            'timestamp': time.time(),
            'fjid': fjid,
            'jid': jid,
            'resource': resource,
            'unique_id': id_,
            'correct_id': parse_correction(properties),
            'msgtxt': msgtxt,
            'session': session,
            'gc_control': None,
            'popup': False,
            'msg_log_id': None,
            'displaymarking': None,
            'stanza_id': id_,
            'properties': properties,
        }

        app.nec.push_incoming_event(
            NetworkEvent('decrypted-message-received', **event_attr))

    def _message_error_received(self, _con, _stanza, properties):
        log.info(properties.error)

        app.storage.archive.set_message_error(app.get_jid_from_account(self.name),
                                     properties.jid,
                                     properties.id,
                                     properties.error)

        app.nec.push_incoming_event(
            NetworkEvent('message-error',
                         account=self.name,
                         jid=properties.jid,
                         message_id=properties.id,
                         error=properties.error))
