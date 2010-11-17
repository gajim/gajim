# -*- coding:utf-8 -*-
## src/common/protocol/caps.py
##
## Copyright (C) 2009 Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

"""
Module containing the network portion of XEP-115 (Entity Capabilities)
"""

import logging
log = logging.getLogger('gajim.c.p.caps')

from common import gajim
from common import ged
from common import helpers
from common.connection_handlers_events import CapsPresenceReceivedEvent, \
    CapsDiscoReceivedEvent, CapsReceivedEvent


class ConnectionCaps(object):

    def __init__(self, account, dispatch_event, capscache, client_caps_factory):
        self._account = account
        self._dispatch_event = dispatch_event
        self._capscache = capscache
        self._create_suitable_client_caps = client_caps_factory
        gajim.nec.register_incoming_event(CapsPresenceReceivedEvent)
        gajim.nec.register_incoming_event(CapsReceivedEvent)
        gajim.ged.register_event_handler('caps-presence-received', ged.GUI1, 
            self._nec_caps_presence_received)

    def caps_change_account_name(self, new_name):
        self._account = new_name

    def _nec_caps_presence_received(self, obj):
        obj.client_caps = self._create_suitable_client_caps(obj.node,
            obj.caps_hash, obj.hash_method)
        self._capscache.query_client_of_jid_if_unknown(self, obj.fjid,
            obj.client_caps)
        self._update_client_caps_of_contact(obj)

    def _update_client_caps_of_contact(self, obj):
        contact = self._get_contact_or_gc_contact_for_jid(obj.fjid)
        if contact:
            contact.client_caps = obj.client_caps
        else:
            log.info('Received Caps from unknown contact %s' % obj.fjid)

    def _get_contact_or_gc_contact_for_jid(self, jid):
        contact = gajim.contacts.get_contact_from_full_jid(self._account, jid)
        if contact is None:
            room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
            contact = gajim.contacts.get_gc_contact(self._account, room_jid, nick)
        return contact

    def _capsDiscoCB(self, jid, node, identities, features, dataforms):
        """
        XMMPPY callback to update our caps cache with queried information after
        we have retrieved an unknown caps hash and issued a disco
        """
        contact = self._get_contact_or_gc_contact_for_jid(jid)
        if not contact:
            log.info("Received Disco from unknown contact %s" % jid)
            return

        lookup = contact.client_caps.get_cache_lookup_strategy()
        cache_item = lookup(self._capscache)

        if cache_item.is_valid():
            # we already know that the hash is fine and have already cached
            # the identities and features
            return
        else:
            validate = contact.client_caps.get_hash_validation_strategy()
            hash_is_valid = validate(identities, features, dataforms)

            if hash_is_valid:
                cache_item.set_and_store(identities, features)
            else:
                node = caps_hash = hash_method = None
                contact.client_caps = self._create_suitable_client_caps(node,
                        caps_hash, hash_method)
                log.info("Computed and retrieved caps hash differ." +
                        "Ignoring caps of contact %s" % contact.get_full_jid())

            j, r = gajim.get_room_and_nick_from_fjid(jid)
            gajim.nec.push_incoming_event(CapsDiscoReceivedEvent(None,
                conn=self, fjid=jid, jid=j, resource=r,
                client_caps=contact.client_caps))
