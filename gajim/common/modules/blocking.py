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
from functools import wraps

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.blocking')


def ensure_online(func):
    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        if not app.account_is_connected(self._account):
            return
        return func(self, *args, **kwargs)
    return func_wrapper


class Blocking:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.blocked = []

        self.handlers = [
            ('iq', self._blocking_push_received, 'set', nbxmpp.NS_BLOCKING)
        ]

        self.supported = False

        self._nbmxpp_methods = [
            'block',
            'unblock',
        ]

    def __getattr__(self, key):
        if key not in self._nbmxpp_methods:
            raise AttributeError
        if not app.account_is_connected(self._account):
            log.warning('Account %s not connected, cant use %s',
                        self._account, key)
            return
        module = self._con.connection.get_module('Blocking')
        return getattr(module, key)

    def pass_disco(self, from_, _identities, features, _data, _node):
        if nbxmpp.NS_BLOCKING not in features:
            return

        self.supported = True
        app.nec.push_incoming_event(
            NetworkEvent('feature-discovered',
                         account=self._account,
                         feature=nbxmpp.NS_BLOCKING))

        log.info('Discovered blocking: %s', from_)

    @ensure_online
    def get_blocking_list(self, callback=None):
        log.info('Request list')
        if callback is None:
            callback = self._blocking_list_received

        self._con.connection.get_module('Blocking').get_blocking_list(
            callback=callback)

    def _blocking_list_received(self, result):
        if result.is_error:
            log.info('Error: %s', result.error)
            return

        self.blocked = result.blocking_list
        app.nec.push_incoming_event(
            BlockingEvent(None, conn=self._con, changed=self.blocked))

    def _blocking_push_received(self, _con, stanza):
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

    def _set_contact_offline(self, jid: str) -> None:
        contact_list = app.contacts.get_contacts(self._account, jid)
        for contact in contact_list:
            contact.show = 'offline'

    def _presence_probe(self, jid: str) -> None:
        log.info('Presence probe: %s', jid)
        # Send a presence Probe to get the current Status
        probe = nbxmpp.Presence(jid, 'probe', frm=self._con.get_own_jid())
        self._con.connection.send(probe)


class BlockingEvent(NetworkIncomingEvent):
    name = 'blocking'


def get_instance(*args, **kwargs):
    return Blocking(*args, **kwargs), 'Blocking'
