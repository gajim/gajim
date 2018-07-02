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

        self._pep_handlers = {}
        self._store_publish_modules = []

    def register_pep_handler(self, namespace, notify_handler, retract_handler):
        if namespace in self._pep_handlers:
            self._pep_handlers[namespace].append(
                (notify_handler, retract_handler))
        else:
            self._pep_handlers[namespace] = [(notify_handler, retract_handler)]
        if notify_handler:
            module_instance = notify_handler.__self__
            if hasattr(module_instance, 'send_stored_publish'):
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


class PEPEvent:

    name = ''

    def __init__(self, con, account):
        self.__account = account
        self.__con = con

    def _update_contacts(self, jid, user_pep):
        for contact in app.contacts.get_contacts(self.__account, str(jid)):
            if user_pep:
                contact.pep[self.name] = user_pep
            else:
                contact.pep.pop(self.name, None)

        if jid == self.__con.get_own_jid().getStripped():
            if user_pep:
                self.__con.pep[self.name] = user_pep
            else:
                self.__con.pep.pop(self.name, None)


class AbstractPEP:

    type_ = PEPEventType

    def __eq__(self, other):
        return other == self.type_

    def __bool__(self):
        return self._pep_specific_data is not None

    def __str__(self):
        return str(self._pep_specific_data)


class PEPReceivedEvent(NetworkIncomingEvent):
    name = 'pep-received'
    base_network_events = []
