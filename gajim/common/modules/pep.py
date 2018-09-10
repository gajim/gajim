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

# XEP-0163: Personal Eventing Protocol

import logging

import nbxmpp

from gajim.common import app
from gajim.common.exceptions import StanzaMalformed
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.const import PEPHandlerType, PEPEventType

log = logging.getLogger('gajim.c.m.pep')


class PEP:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('message', self._pep_event_received,
             'headline', nbxmpp.NS_PUBSUB_EVENT)
        ]

        self.supported = False
        self._pep_handlers = {}
        self._store_publish_modules = []

    def pass_disco(self, from_, identities, features, data, node):
        for identity in identities:
            if identity['category'] == 'pubsub':
                if identity.get('type') == 'pep':
                    log.info('Discovered PEP support: %s', from_)
                    self.supported = True

    def register_pep_handler(self, namespace, notify_handler, retract_handler):
        if namespace in self._pep_handlers:
            self._pep_handlers[namespace].append(
                (notify_handler, retract_handler))
        else:
            self._pep_handlers[namespace] = [(notify_handler, retract_handler)]
        if notify_handler:
            module_instance = notify_handler.__self__
            if module_instance.store_publish:
                if module_instance not in self._store_publish_modules:
                    self._store_publish_modules.append(module_instance)

    def _pep_event_received(self, conn, stanza):
        jid = stanza.getFrom()
        event = stanza.getTag('event', namespace=nbxmpp.NS_PUBSUB_EVENT)
        items = event.getTag('items')
        if items is None:
            log.warning('Malformed PEP event (no items node): %s', stanza)
            raise nbxmpp.NodeProcessed

        namespace = items.getAttr('node')
        if namespace is None:
            log.warning('Malformed PEP event (no node attr): %s', stanza)
            raise nbxmpp.NodeProcessed

        log.info('PEP notification received: %s %s', jid, namespace)

        handlers = self._pep_handlers.get(namespace, None)
        if handlers is None:
            # Old Fallback
            from gajim.common.connection_handlers_events import PEPReceivedEvent as OldPEPReceivedEvent
            app.nec.push_incoming_event(
                OldPEPReceivedEvent(None, conn=self._con, stanza=stanza))
            raise nbxmpp.NodeProcessed
        else:
            # Check if this is a retraction
            retract = items.getTag('retract')
            if retract is not None:
                for handler in handlers:
                    handler[PEPHandlerType.RETRACT](jid, retract.getID())
                    raise nbxmpp.NodeProcessed

            # Check if we have items
            items_ = items.getTags('item')
            if items_ is None:
                log.warning('Malformed PEP event received: %s', stanza)
                raise nbxmpp.NodeProcessed
            for handler in handlers:
                handler[PEPHandlerType.NOTIFY](jid, items_[0])
                raise nbxmpp.NodeProcessed

    def send_stored_publish(self):
        for module in self._store_publish_modules:
            module.send_stored_publish()

    def reset_stored_publish(self):
        for module in self._store_publish_modules:
            module.reset_stored_publish()


class AbstractPEPModule:
    def __init__(self, con, account):
        self._account = account
        self._con = con

        self._stored_publish = None

        self._con.get_module('PEP').register_pep_handler(
            self.namespace,
            self._pep_notify_received,
            self._pep_retract_received)

    def _pep_notify_received(self, jid, item):
        try:
            data = self._extract_info(item)
        except StanzaMalformed as error:
            log.warning('%s, %s: %s', jid, error, item)
            return

        self._log.info('Received: %s %s', jid, data)
        self._push_event(jid, self.pep_class(data))

    def _pep_retract_received(self, jid, id_):
        self._log.info('Retract: %s %s', jid, id_)
        self._push_event(jid, self.pep_class(None))

    def _extract_info(self, item):
        '''To be implemented by subclasses'''
        raise NotImplementedError

    def _build_node(self, data):
        '''To be implemented by subclasses'''
        raise NotImplementedError

    def _push_event(self, jid, user_pep):
        self._notification_received(jid, user_pep)
        app.nec.push_incoming_event(
            PEPReceivedEvent(None, conn=self._con,
                             jid=str(jid),
                             pep_type=self.name,
                             user_pep=user_pep))

    def _notification_received(self, jid, user_pep):
        for contact in app.contacts.get_contacts(self._account, str(jid)):
            if user_pep:
                contact.pep[self.name] = user_pep
            else:
                contact.pep.pop(self.name, None)

        if jid == self._con.get_own_jid().getStripped():
            if user_pep:
                self._con.pep[self.name] = user_pep
            else:
                self._con.pep.pop(self.name, None)

    def send_stored_publish(self):
        if self._stored_publish is not None:
            self._log.info('Send stored publish')
            self.send(self._stored_publish)
            self._stored_publish = None

    def reset_stored_publish(self):
        self._log.info('Reset stored publish')
        self._stored_publish = None

    def send(self, data):
        if not self._con.get_module('PEP').supported:
            return

        if self._con.connected == 1:
            # We are connecting, save activity and send it later
            self._stored_publish = data
            return

        if data:
            self._log.info('Send: %s', data)
        else:
            self._log.info('Remove')

        item = self._build_node(data)

        self._con.get_module('PubSub').send_pb_publish(
            '', self.namespace, item, 'current')

    def retract(self):
        if not self._con.get_module('PEP').supported:
            return
        self.send(None)
        self._con.get_module('PubSub').send_pb_retract(
            '', self.namespace, 'current')


class AbstractPEPData:

    type_ = PEPEventType

    def asMarkupText(self):
        '''SHOULD be implemented by subclasses'''
        return ''

    def __eq__(self, other):
        return other == self.type_

    def __bool__(self):
        return self._pep_specific_data is not None

    def __str__(self):
        return str(self._pep_specific_data)


class PEPReceivedEvent(NetworkIncomingEvent):
    name = 'pep-received'


def get_instance(*args, **kwargs):
    return PEP(*args, **kwargs), 'PEP'
