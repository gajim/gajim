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

from common.xmpp import NS_CAPS
from common import gajim
from common import helpers


class ConnectionCaps(object):

	def __init__(self, account, dispatch_event, capscache, client_caps_factory):
		self._account = account
		self._dispatch_event = dispatch_event
		self._capscache = capscache
		self._create_suitable_client_caps = client_caps_factory

	def _capsPresenceCB(self, con, presence):
		"""
		XMMPPY callback method to handle retrieved caps info
		"""
		try:
			jid = helpers.get_full_jid_from_iq(presence)
		except:
			log.info("Ignoring invalid JID in caps presenceCB")
			return

		client_caps = self._extract_client_caps_from_presence(presence)
		self._capscache.query_client_of_jid_if_unknown(self, jid, client_caps)
		self._update_client_caps_of_contact(jid, client_caps)

		self._dispatch_event('CAPS_RECEIVED', (jid,))

	def _extract_client_caps_from_presence(self, presence):
		caps_tag = presence.getTag('c', namespace=NS_CAPS)
		if caps_tag:
			hash_method, node, caps_hash = caps_tag['hash'], caps_tag['node'], caps_tag['ver']
		else:
			hash_method = node = caps_hash = None
		return self._create_suitable_client_caps(node, caps_hash, hash_method)

	def _update_client_caps_of_contact(self, jid, client_caps):
		contact = self._get_contact_or_gc_contact_for_jid(jid)
		if contact:
			contact.client_caps = client_caps
		else:
			log.info("Received Caps from unknown contact %s" % jid)

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

			self._dispatch_event('CAPS_RECEIVED', (jid,))

		
# vim: se ts=3:
