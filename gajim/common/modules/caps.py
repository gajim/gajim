# Copyright (C) 2009 Stephan Erb <steve-e AT h3c.de>
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

import logging

import nbxmpp

from gajim.common import caps_cache
from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.presence import parse_show
from gajim.common.modules.presence import parse_type

log = logging.getLogger('gajim.c.m.caps')


class Caps:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('presence', self._presence_received, '', nbxmpp.NS_CAPS)
        ]

        self._capscache = caps_cache.capscache
        self._create_suitable_client_caps = caps_cache.create_suitable_client_caps

    def _presence_received(self, _con, stanza):
        hash_method = node = caps_hash = None

        caps = stanza.getTag('c', namespace=nbxmpp.NS_CAPS)
        if caps is not None:
            hash_method = caps['hash']
            node = caps['node']
            caps_hash = caps['ver']

        from_ = stanza.getFrom()
        full_jid = str(from_)
        show = parse_show(stanza)
        type_ = parse_type(stanza)

        log.info('Received from %s, type: %s, method: %s, node: %s, hash: %s',
                 from_, stanza.getType(), hash_method, node, caps_hash)

        client_caps = self._create_suitable_client_caps(
            node, caps_hash, hash_method, full_jid)

        # Type is None means 'available'
        if stanza.getType() is None and client_caps._hash_method == 'no':
            self._capscache.forget_caps(client_caps)
            client_caps = self._create_suitable_client_caps(
                node, caps_hash, hash_method)
        else:
            self._capscache.query_client_of_jid_if_unknown(
                self._con, full_jid, client_caps)

        self._update_client_caps_of_contact(from_, client_caps)

        # Event is only used by ClientIcons Plugin
        app.nec.push_incoming_event(
            NetworkEvent('caps-presence-received',
                         conn=self._con,
                         fjid=full_jid,
                         jid=from_.getStripped(),
                         resource=from_.getResource(),
                         hash_method=hash_method,
                         node=node,
                         caps_hash=caps_hash,
                         client_caps=client_caps,
                         show=show,
                         ptype=type_,
                         stanza=stanza))

        app.nec.push_incoming_event(NetworkEvent('caps-update',
                                                 conn=self._con,
                                                 fjid=full_jid,
                                                 jid=from_.getStripped()))

    def _update_client_caps_of_contact(self, from_, client_caps):
        contact = self._get_contact_or_gc_contact_for_jid(from_)
        if contact is not None:
            contact.client_caps = client_caps
        else:
            log.info('Received Caps from unknown contact %s', from_)

    def _get_contact_or_gc_contact_for_jid(self, from_):
        contact = app.contacts.get_contact_from_full_jid(self._account,
                                                         str(from_))

        if contact is None:
            room_jid, resource = from_.getStripped(), from_.getResource()
            contact = app.contacts.get_gc_contact(
                self._account, room_jid, resource)
        return contact

    def contact_info_received(self, from_, identities, features, data, node):
        """
        callback to update our caps cache with queried information after
        we have retrieved an unknown caps hash via a disco
        """
        bare_jid = from_.getStripped()

        contact = self._get_contact_or_gc_contact_for_jid(from_)
        if not contact:
            log.info('Received Disco from unknown contact %s', from_)
            return

        lookup = contact.client_caps.get_cache_lookup_strategy()
        cache_item = lookup(self._capscache)

        if cache_item.is_valid():
            # we already know that the hash is fine and have already cached
            # the identities and features
            return

        validate = contact.client_caps.get_hash_validation_strategy()
        hash_is_valid = validate(identities, features, data)

        if hash_is_valid:
            cache_item.set_and_store(identities, features)
        else:
            node = caps_hash = hash_method = None
            contact.client_caps = self._create_suitable_client_caps(
                node, caps_hash, hash_method)
            log.warning(
                'Computed and retrieved caps hash differ. Ignoring '
                'caps of contact %s', contact.get_full_jid())

        app.nec.push_incoming_event(
            NetworkEvent('caps-update',
                         conn=self._con,
                         fjid=str(from_),
                         jid=bare_jid))


def get_instance(*args, **kwargs):
    return Caps(*args, **kwargs), 'Caps'
