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

import logging

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.blocking')


class Blocking:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.blocked = []

        self.handlers = [
            ('iq', self._blocking_push_received, 'set', nbxmpp.NS_BLOCKING)
        ]

    def get_blocking_list(self):
        iq = nbxmpp.Iq('get', nbxmpp.NS_BLOCKING)
        iq.setQuery('blocklist')
        log.info('Request list')
        self._con.connection.SendAndCallForResponse(
            iq, self._blocking_list_received)

    def _blocking_list_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            return

        self.blocked = []
        blocklist = stanza.getTag('blocklist', namespace=nbxmpp.NS_BLOCKING)
        if blocklist is None:
            log.error('No blocklist node')
            return

        for item in blocklist.getTags('item'):
            self.blocked.append(item.getAttr('jid'))
        log.info('Received list: %s', self.blocked)

        app.nec.push_incoming_event(
            BlockingEvent(None, conn=self._con, changed=self.blocked))

    def _blocking_push_received(self, conn, stanza):
        reply = stanza.buildReply('result')
        childs = reply.getChildren()
        for child in childs:
            reply.delChild(child)
        self._con.connection.send(reply)

        changed_list = []

        unblock = stanza.getTag('unblock', namespace=nbxmpp.NS_BLOCKING)
        if unblock is not None:
            items = unblock.getTags('item')
            if not items:
                # Unblock all
                changed_list = list(self.blocked)
                self.blocked = []
                for jid in self.blocked:
                    self._presence_probe(jid)
                log.info('Unblock all Push')
                raise nbxmpp.NodeProcessed

            for item in items:
                # Unblock some contacts
                jid = item.getAttr('jid')
                changed_list.append(jid)
                if jid not in self.blocked:
                    continue
                self.blocked.remove(jid)
                self._presence_probe(jid)
                log.info('Unblock Push: %s', jid)

        block = stanza.getTag('block', namespace=nbxmpp.NS_BLOCKING)
        if block is not None:
            for item in block.getTags('item'):
                jid = item.getAttr('jid')
                if jid in self.blocked:
                    continue
                changed_list.append(jid)
                self.blocked.append(jid)
                self._set_contact_offline(jid)
                log.info('Block Push: %s', jid)

        app.nec.push_incoming_event(
            BlockingEvent(None, conn=self._con, changed=changed_list))

        raise nbxmpp.NodeProcessed

    def _set_contact_offline(self, jid):
        contact_list = app.contacts.get_contacts(self._account, jid)
        for contact in contact_list:
            contact.show = 'offline'

    def _presence_probe(self, jid):
        log.info('Presence probe: %s', jid)
        # Send a presence Probe to get the current Status
        probe = nbxmpp.Presence(jid, 'probe', frm=self._con.get_own_jid())
        self._con.connection.send(probe)

    def block(self, contact_list):
        if not self._con.blocking_supported:
            return
        iq = nbxmpp.Iq('set', nbxmpp.NS_BLOCKING)
        query = iq.setQuery(name='block')

        for contact in contact_list:
            query.addChild(name='item', attrs={'jid': contact.jid})
            log.info('Block: %s', contact.jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_result_handler, {})

    def unblock(self, contact_list):
        if not self._con.blocking_supported:
            return
        iq = nbxmpp.Iq('set', nbxmpp.NS_BLOCKING)
        query = iq.setQuery(name='unblock')

        for contact in contact_list:
            query.addChild(name='item', attrs={'jid': contact.jid})
            log.info('Unblock: %s', contact.jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_result_handler, {})

    def _default_result_handler(self, conn, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.warning('Operation failed: %s', stanza.getError())


class BlockingEvent(NetworkIncomingEvent):
    name = 'blocking'
    base_network_events = []


def get_instance(*args, **kwargs):
    return Blocking(*args, **kwargs), 'Blocking'
