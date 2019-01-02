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

# Iq handler

import logging

import nbxmpp
from nbxmpp.const import Error
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.file_props import FilesProp


log = logging.getLogger('gajim.c.m.iq')


class Iq:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._iq_error_received,
                          typ='error',
                          priority=51),
        ]

    def _iq_error_received(self, _con, _stanza, properties):
        log.info('Error: %s', properties.error)
        if properties.error.type in (Error.JID_MALFORMED,
                                     Error.FORBIDDEN,
                                     Error.NOT_ACCEPTABLE):
            sid = self._get_sid(properties.id)
            file_props = FilesProp.getFileProp(self._account, sid)
            if file_props:
                if properties.error.type == Error.JID_MALFORMED:
                    file_props.error = -3
                else:
                    file_props.error = -4
                app.nec.push_incoming_event(
                    NetworkEvent('file-request-error',
                                 conn=self._con,
                                 jid=properties.jid.getBare(),
                                 file_props=file_props,
                                 error_msg=properties.error.message))
                self._con.disconnect_transfer(file_props)
                raise nbxmpp.NodeProcessed

        if properties.error.type == Error.ITEM_NOT_FOUND:
            sid = self._get_sid(properties.id)
            file_props = FilesProp.getFileProp(self._account, sid)
            if file_props:
                app.nec.push_incoming_event(
                    NetworkEvent('file-send-error',
                                 account=self._account,
                                 jid=str(properties.jid),
                                 file_props=file_props))
                self._con.disconnect_transfer(file_props)
                raise nbxmpp.NodeProcessed

        app.nec.push_incoming_event(
            NetworkEvent('iq-error-received',
                         account=self._account,
                         properties=properties))
        raise nbxmpp.NodeProcessed

    @staticmethod
    def _get_sid(id_):
        sid = id_
        if len(id_) > 3 and id_[2] == '_':
            sid = id_[3:]
        return sid
