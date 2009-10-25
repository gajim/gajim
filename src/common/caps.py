# -*- coding:utf-8 -*-
## src/common/caps.py
##
## Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
##                    Travis Shirk <travis AT pobox.com>
## Copyright (C) 2007-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
## Copyright (C) 2008-2009 Stephan Erb <steve-e AT h3c.de>
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

'''
Module containing all XEP-115 (Entity Capabilities) related classes 

Basic Idea:
CapsCache caches features to hash relationships. The cache is queried
through EntityCapabilities objects which are hold by contact instances. 

EntityCapabilities represent the client of contacts. It is set on the receive
of a presence. The respective jid is then queried with a disco if the advertised
client/hash is unknown.
''' 

import gajim
import helpers


class AbstractEntityCapabilities(object):
	'''
	Base class representing a client and its capabilities as advertised by
	a caps tag in a presence
	'''
	
	def __init__(self, caps_cache, caps_hash, node):
		self._caps_cache = caps_cache
		self._hash = caps_hash
		self._node = node
		
	def query_client_of_jid_if_unknown(self, connection, jid):
		'''
		Asynchronously query the give jid for its (node, ver, exts) caps data
		using a disco query.
		
		Query will only be sent if the data is not already cached.
		'''
		q = self._lookup_in_cache()
		if q.queried == 0:
			self._discover(connection, jid)
			q.queried = 1
		
	def contains_feature(self, feature):
		''' Returns true if these capabilities contain the given feature '''
		features = self._lookup_in_cache().features
		
		if feature in features or features == []:
			return True
		else:
			return False
			
	def _discover(self, connection, jid):
		''' To be implemented by subclassess '''
		raise NotImplementedError()
	
	def _lookup_in_cache(self):
		''' To be implemented by subclassess '''
		raise NotImplementedError()
					

class EntityCapabilities(AbstractEntityCapabilities):
	''' The current XEP-115 implementation '''
	
	def __init__(self, caps_cache, caps_hash, node, hash_method):
		AbstractEntityCapabilities.__init__(self, caps_cache, caps_hash, node)
		assert hash_method != 'old'
		self._hash_method = hash_method
	
	def _lookup_in_cache(self):
		return self._caps_cache[(self._hash_method, self._hash)]
	
	def _discover(self, connection, jid):
		connection.discoverInfo(jid, '%s#%s' % (self._node, self._hash))
				
	
class OldEntityCapabilities(AbstractEntityCapabilities):
	''' Old XEP-115 implemtation. Kept around for background competability.  '''
	
	def __init__(self, caps_cache, caps_hash, node):
		AbstractEntityCapabilities.__init__(self, caps_cache, caps_hash, node)

	def _lookup_in_cache(self):
		return self._caps_cache[('old', self._node + '#' + self._hash)]
	
	def _discover(self, connection, jid):
		connection.discoverInfo(jid)
		
		
class NullEntityCapabilities(AbstractEntityCapabilities):
	'''
	This is a NULL-Object to streamline caps handling is a client has not
	advertised any caps or has advertised them in an improper way. 
	
	Assumes everything is supported.
	''' 
	
	def __init__(self):
		pass
	
	def query_client_of_jid_if_unknown(self, connection, jid):
		pass
	
	def contains_feature(self, feature):
		return True


class CapsCache(object):
	''' This object keeps the mapping between caps data and real disco
	features they represent, and provides simple way to query that info.
	
	It is application-wide, that is there's one object for all
	connections.
	
	Goals:
	 * handle storing/retrieving info from database
	 * cache info in memory
	 * expose simple interface
	 
	Properties:
	 * one object for all connections (move to logger.py?)
	 * store info efficiently (a set() of urls -- we can assume there won't be
	   too much of these, ensure that (X,Y,Z1) and (X,Y,Z2) has different
	   features.
	'''
	def __init__(self, logger=None):
		''' Create a cache for entity capabilities. '''
		# our containers:
		# __cache is a dictionary mapping: pair of hash method and hash maps
		#   to CapsCacheItem object
		# __CacheItem is a class that stores data about particular
		#   client (hash method/hash pair)
		self.__cache = {}

		class CacheItem(object):
			# __names is a string cache; every string long enough is given
			#   another object, and we will have plenty of identical long
			#   strings. therefore we can cache them
			__names = {}
			
			def __init__(self, hash_method, hash_, logger):
				# cached into db
				self.hash_method = hash_method
				self.hash = hash_
				self._features = []
				self._identities = []
				self._logger = logger

				# not cached into db:
				# have we sent the query?
				# 0 == not queried
				# 1 == queried
				# 2 == got the answer
				self.queried = 0

			def _get_features(self):
				return self._features

			def _set_features(self, value):
				self._features = []
				for feature in value:
					self._features.append(self.__names.setdefault(feature, feature))
					
			features = property(_get_features, _set_features)

			def _get_identities(self):
				list_ = []
				for i in self._identities:
					# transforms it back in a dict
					d = dict()
					d['category'] = i[0]
					if i[1]:
						d['type'] = i[1]
					if i[2]:
						d['xml:lang'] = i[2]
					if i[3]:
						d['name'] = i[3]
					list_.append(d)
				return list_
			
			def _set_identities(self, value):
				self._identities = []
				for identity in value:
					# dict are not hashable, so transform it into a tuple
					t = (identity['category'], identity.get('type'),
						identity.get('xml:lang'), identity.get('name'))
					self._identities.append(self.__names.setdefault(t, t))
					
			identities = property(_get_identities, _set_identities)

			def update(self, identities, features):
				# NOTE: self refers to CapsCache object, not to CacheItem
				self.identities=identities
				self.features=features
				self._logger.add_caps_entry(self.hash_method, self.hash,
					identities, features)

		self.__CacheItem = CacheItem

		# prepopulate data which we are sure of; note: we do not log these info

		for account in gajim.connections:
			gajimcaps = self[('sha-1', gajim.caps_hash[account])]
			gajimcaps.identities = [gajim.gajim_identity]
			gajimcaps.features = gajim.gajim_common_features + \
				gajim.gajim_optional_features[account]

		# start logging data from the net
		self.logger = logger

	def initialize_from_db(self):
		# get data from logger...
		if self.logger is not None:
			for hash_method, hash_, identities, features in \
			self.logger.iter_caps_data():
				x = self[(hash_method, hash_)]
				x.identities = identities
				x.features = features
				x.queried = 2

	def __getitem__(self, caps):
		if caps in self.__cache:
			return self.__cache[caps]

		hash_method, hash_ = caps

		x = self.__CacheItem(hash_method, hash_, self.logger)
		self.__cache[(hash_method, hash_)] = x
		return x

	def preload(self, con, jid, node, hash_method, hash_):
		''' Preload data about (node, ver, exts) caps using disco
		query to jid using proper connection. Don't query if
		the data is already in cache. '''
		if hash_method == 'old':
			q = self[(hash_method, node + '#' + hash_)]
		else:
			q = self[(hash_method, hash_)]

		if q.queried==0:
			# do query for bare node+hash pair
			# this will create proper object
			q.queried=1
			if hash_method == 'old':
				con.discoverInfo(jid)
			else:
				con.discoverInfo(jid, '%s#%s' % (node, hash_))

	def is_supported(self, contact, feature):
		if not contact:
			return False

		# Unfortunately, if all resources are offline, the contact
		# includes the last resource that was online. Check for its
		# show, so we can be sure it's existant. Otherwise, we still
		# return caps for a contact that has no resources left.
		if contact.show == 'offline':
			return False

		# FIXME: We assume everything is supported if we got no caps.
		#	 This is the "Asterix way", after 0.12 release, I will
		#	 likely implement a fallback to disco (could be disabled
		#	 for mobile users who pay for traffic)
		if contact.caps_hash_method == 'old':
			features = self[(contact.caps_hash_method, contact.caps_node + '#' + \
				contact.caps_hash)].features
		else:
			features = self[(contact.caps_hash_method, contact.caps_hash)].features
		if feature in features or features == []:
			return True

		return False

gajim.capscache = CapsCache(gajim.logger)

class ConnectionCaps(object):
	''' This class highly depends on that it is a part of Connection class. '''
	def _capsPresenceCB(self, con, presence):
		''' Handle incoming presence stanzas... This is a callback
		for xmpp registered in connection_handlers.py'''

		# we will put these into proper Contact object and ask
		# for disco... so that disco will learn how to interpret
		# these caps
		pm_ctrl = None
		try:
			jid = helpers.get_full_jid_from_iq(presence)
		except:
			# Bad jid
			return
		contact = gajim.contacts.get_contact_from_full_jid(self.name, jid)
		if contact is None:
			room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
			contact = gajim.contacts.get_gc_contact(
				self.name, room_jid, nick)
			pm_ctrl = gajim.interface.msg_win_mgr.get_control(jid, self.name)
			if contact is None:
				# TODO: a way to put contact not-in-roster
				# into Contacts
				return

		# get the caps element
		caps = presence.getTag('c')
		if not caps:
			contact.caps_node = None
			contact.caps_hash = None
			contact.caps_hash_method = None
			return

		hash_method, node, hash_ = caps['hash'], caps['node'], caps['ver']

		if hash_method is None and node and hash_:
			# Old XEP-115 implentation
			hash_method = 'old'

		if hash_method is None or node is None or hash_ is None:
			# improper caps in stanza, ignoring
			contact.caps_node = None
			contact.caps_hash = None
			contact.hash_method = None
			return

		# start disco query...
		gajim.capscache.preload(self, jid, node, hash_method, hash_)

		# overwriting old data
		contact.caps_node = node
		contact.caps_hash_method = hash_method
		contact.caps_hash = hash_
		if pm_ctrl:
			pm_ctrl.update_contact()

	def _capsDiscoCB(self, jid, node, identities, features, dataforms):
		contact = gajim.contacts.get_contact_from_full_jid(self.name, jid)
		if not contact:
			room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
			contact = gajim.contacts.get_gc_contact(self.name, room_jid, nick)
			if contact is None:
				return
		if not contact.caps_node:
			return # we didn't asked for that?
		if contact.caps_hash_method != 'old':
			computed_hash = helpers.compute_caps_hash(identities, features,
				dataforms=dataforms, hash_method=contact.caps_hash_method)
			if computed_hash != contact.caps_hash:
				# wrong hash, forget it
				contact.caps_node = ''
				contact.caps_hash_method = ''
				contact.caps_hash = ''
				return
			# if we don't have this info already...
			caps = gajim.capscache[(contact.caps_hash_method, contact.caps_hash)]
		else:
			# if we don't have this info already...
			caps = gajim.capscache[(contact.caps_hash_method, contact.caps_node + \
				'#' + contact.caps_hash)]
		if caps.queried == 2:
			return

		caps.update(identities, features)

# vim: se ts=3:
