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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0191: Blocking Command

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import is_error_result

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.modules.base import BaseModule


class Blocking(BaseModule):

    _nbxmpp_extends = 'Blocking'
    _nbxmpp_methods = [
        'block',
        'unblock',
        'get_blocking_list',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.blocked = []

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._blocking_push_received,
                          typ='set',
                          ns=Namespace.BLOCKING),
        ]

        self._register_callback('get_blocking_list',
                                self._blocking_list_received)

        self.supported = False

    def pass_disco(self, info):
        if Namespace.BLOCKING not in info.features:
            return

        self.supported = True
        app.nec.push_incoming_event(
            NetworkEvent('feature-discovered',
                         account=self._account,
                         feature=Namespace.BLOCKING))

        self._log.info('Discovered blocking: %s', info.jid)

    def _blocking_list_received(self, result):
        if is_error_result(result):
            self._log.info(result)
            return

        self.blocked = result.blocking_list
        app.nec.push_incoming_event(
            BlockingEvent(None, conn=self._con, changed=self.blocked))

    def _blocking_push_received(self, _con, stanza, _properties):
        reply = stanza.buildReply('result')
        children = reply.getChildren()
        for child in children:
            reply.delChild(child)
        self._nbxmpp().send(reply)

        changed_list = []

        unblock = stanza.getTag('unblock', namespace=Namespace.BLOCKING)
        if unblock is not None:
            items = unblock.getTags('item')
            if not items:
                # Unblock all
                changed_list = list(self.blocked)
                self.blocked = []
                for jid in self.blocked:
                    self._presence_probe(jid)
                self._log.info('Unblock all Push')
                raise nbxmpp.NodeProcessed

            for item in items:
                # Unblock some contacts
                jid = item.getAttr('jid')
                changed_list.append(jid)
                if jid not in self.blocked:
                    continue
                self.blocked.remove(jid)
                self._presence_probe(jid)
                self._log.info('Unblock Push: %s', jid)

        block = stanza.getTag('block', namespace=Namespace.BLOCKING)
        if block is not None:
            for item in block.getTags('item'):
                jid = item.getAttr('jid')
                if jid in self.blocked:
                    continue
                changed_list.append(jid)
                self.blocked.append(jid)
                self._set_contact_offline(jid)
                self._log.info('Block Push: %s', jid)

        app.nec.push_incoming_event(
            BlockingEvent(None, conn=self._con, changed=changed_list))

        raise nbxmpp.NodeProcessed

    def _set_contact_offline(self, jid: str) -> None:
        contact_list = app.contacts.get_contacts(self._account, jid)
        for contact in contact_list:
            contact.show = 'offline'

    def _presence_probe(self, jid: str) -> None:
        self._log.info('Presence probe: %s', jid)
        # Send a presence Probe to get the current Status
        probe = nbxmpp.Presence(jid, 'probe', frm=self._con.get_own_jid())
        self._nbxmpp().send(probe)


class BlockingEvent(NetworkIncomingEvent):
    name = 'blocking'


def get_instance(*args, **kwargs):
    return Blocking(*args, **kwargs), 'Blocking'
