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
from gajim.common.i18n import _
from gajim.common.helpers import AdditionalDataDict
from gajim.common.nec import NetworkEvent
from gajim.common.const import KindConstant
from gajim.common.modules.util import get_eme_message
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml
from gajim.common.connection_handlers_events import MessageErrorEvent


log = logging.getLogger('gajim.c.z.connection_handlers_zeroconf')

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
               'invisible']


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

        timestamp = time.time()
        session.last_receive = timestamp

        additional_data = AdditionalDataDict()
        parse_oob(properties, additional_data)

        if properties.is_encrypted:
            additional_data['encrypted'] = properties.encrypted.additional_data
        else:
            if properties.eme is not None:
                msgtxt = get_eme_message(properties.eme)

        if type_ == 'error':
            if not msgtxt:
                msgtxt = _('message')
            self._log_error_message(stanza, msgtxt, jid, timestamp)
            error_msg = stanza.getErrorMsg() or msgtxt
            msgtxt = None if error_msg == msgtxt else msgtxt
            app.nec.push_incoming_event(
                MessageErrorEvent(None,
                                  conn=self,
                                  fjid=fjid,
                                  error_code=stanza.getErrorCode(),
                                  error_msg=error_msg,
                                  msg=msgtxt,
                                  time_=timestamp,
                                  session=session,
                                  stanza=stanza))

            return

        event_attr = {
            'conn': self,
            'stanza': stanza,
            'account': self.name,
            'id_': id_,
            'encrypted': False,
            'additional_data': additional_data,
            'forwarded': False,
            'sent': False,
            'timestamp': time.time(),
            'fjid': fjid,
            'jid': jid,
            'resource': resource,
            'unique_id': id_,
            'message_id': properties.id,
            'correct_id': parse_correction(properties),
            'mtype': type_,
            'msgtxt': msgtxt,
            'thread_id': thread_id,
            'session': session,
            'self_message': False,
            'muc_pm': False,
            'gc_control': None,
            'attention': properties.attention,
            'xhtml': parse_xhtml(properties),
            'user_nick': properties.nickname,
            'subject': None,
            'popup': False,
            'msg_log_id': None,
            'displaymarking': None,
            'stanza_id': id_,
        }

        app.nec.push_incoming_event(
            NetworkEvent('decrypted-message-received', **event_attr))

    def _log_error_message(self, stanza, msgtxt, jid, timestamp):
        error_msg = stanza.getErrorMsg() or msgtxt
        if app.config.should_log(self.name, jid):
            app.logger.insert_into_logs(self.name,
                                        jid,
                                        timestamp,
                                        KindConstant.ERROR,
                                        message=error_msg)
