# Copyright (C) 2009 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

# XEP-0115: Entity Capabilities

import nbxmpp
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import DiscoIdentity
from nbxmpp.util import is_error_result
from nbxmpp.util import compute_caps_hash

from gajim.common import caps_cache
from gajim.common import app
from gajim.common.const import COMMON_FEATURES
from gajim.common.helpers import get_optional_features
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule


class Caps(BaseModule):

    _nbxmpp_extends = 'EntityCaps'
    _nbxmpp_methods = [
        'caps',
        'set_caps'
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._entity_caps,
                          ns=nbxmpp.NS_CAPS,
                          priority=51),
        ]

        self._capscache = caps_cache.capscache
        self._create_suitable_client_caps = \
            caps_cache.create_suitable_client_caps

        self._identities = [
            DiscoIdentity(category='client', type='pc', name='Gajim')
        ]

    def _entity_caps(self, _con, _stanza, properties):
        if properties.type.is_error or properties.type.is_unavailable:
            return

        if properties.is_self_presence:
            return

        jid = str(properties.jid)

        hash_method = properties.entity_caps.hash
        node = properties.entity_caps.node
        caps_hash = properties.entity_caps.ver

        self._log.info(
            'Received from %s, type: %s, method: %s, node: %s, hash: %s',
            jid, properties.type, hash_method, node, caps_hash)

        client_caps = self._create_suitable_client_caps(
            node, caps_hash, hash_method, jid)

        # Type is None means 'available'
        if properties.type.is_available and client_caps.hash_method == 'no':
            self._capscache.forget_caps(client_caps)
            client_caps = self._create_suitable_client_caps(
                node, caps_hash, hash_method)
        else:
            self._capscache.query_client_of_jid_if_unknown(
                self._con, jid, client_caps)

        self._update_client_caps_of_contact(properties.jid, client_caps)

        app.nec.push_incoming_event(
            NetworkEvent('caps-update',
                         account=self._account,
                         fjid=jid,
                         jid=properties.jid.getBare()))

    def _update_client_caps_of_contact(self, from_, client_caps):
        contact = self._get_contact_or_gc_contact_for_jid(from_)
        if contact is not None:
            contact.client_caps = client_caps
        else:
            self._log.info('Received Caps from unknown contact %s', from_)

    def _get_contact_or_gc_contact_for_jid(self, from_):
        contact = app.contacts.get_contact_from_full_jid(self._account,
                                                         str(from_))

        if contact is None:
            room_jid, resource = from_.getStripped(), from_.getResource()
            contact = app.contacts.get_gc_contact(
                self._account, room_jid, resource)
        return contact

    def contact_info_received(self, info):
        """
        callback to update our caps cache with queried information after
        we have retrieved an unknown caps hash via a disco
        """

        if is_error_result(info):
            self._log.info(info)
            return

        bare_jid = info.jid.getBare()

        contact = self._get_contact_or_gc_contact_for_jid(info.jid)
        if not contact:
            self._log.info('Received Disco from unknown contact %s', info.jid)
            return

        lookup = contact.client_caps.get_cache_lookup_strategy()
        cache_item = lookup(self._capscache)

        if cache_item.is_valid():
            # we already know that the hash is fine and have already cached
            # the identities and features
            return

        try:
            compute_caps_hash(info)
        except Exception as error:
            self._log.warning('Disco info malformed: %s %s',
                              contact.get_full_jid(), error)
            node = caps_hash = hash_method = None
            contact.client_caps = self._create_suitable_client_caps(
                node, caps_hash, hash_method)
        else:
            cache_item.set_and_store(info)

        app.nec.push_incoming_event(
            NetworkEvent('caps-update',
                         account=self._account,
                         fjid=str(info.jid),
                         jid=bare_jid))

    def update_caps(self):
        if not app.account_is_connected(self._account):
            return

        optional_features = get_optional_features(self._account)
        self.set_caps(self._identities,
                      COMMON_FEATURES + optional_features,
                      'https://gajim.org')

        if not app.account_is_available(self._account):
            return

        app.connections[self._account].change_status(
            app.connections[self._account].status,
            app.connections[self._account].status_message)


def get_instance(*args, **kwargs):
    return Caps(*args, **kwargs), 'Caps'
