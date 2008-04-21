##
## Copyright (C) 2006 Gajim Team
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

from itertools import *
import xmpp
import xmpp.features_nb
import gajim
import helpers

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

	Connections with other objects: (TODO)

	Interface:

	# object creation
	>>> cc=CapsCache(logger_object)

	>>> caps=('http://exodus.jabberstudio.org/caps', '0.9', None) # node, ver, ext
	>>> muc='http://jabber.org/protocol/muc'
	>>> chatstates='http://jabber.org/protocol/chatstates'

	# retrieving data
	>>> muc in cc[caps].features
	True
	>>> muc in cc[caps]
	True
	>>> chatstates in cc[caps]
	False
	>>> cc[caps].identities
	set({'category':'client', 'type':'pc'})
	>>> x=cc[caps] # more efficient if making several queries for one set of caps
	ATypicalBlackBoxObject
	>>> muc in x
	True
	>>> x.node
	'http://exodus.jabberstudio.org/caps'

	# retrieving data (multiple exts case)
	>>> caps=('http://gajim.org/caps', '0.9', ('csn', 'ft'))
	>>> muc in cc[caps]
	True

	# setting data
	>>> newcaps=('http://exodus.jabberstudio.org/caps', '0.9a', None)
	>>> cc[newcaps].identities.add({'category':'client', 'type':'pc', 'name':'Gajim'})
	>>> cc[newcaps].features+=muc # same as:
	>>> cc[newcaps]+=muc
	>>> cc[newcaps]['csn']+=chatstates # adding data as if ext was 'csn'
	# warning: no feature removal!
	'''
	def __init__(self, logger=None):
		''' Create a cache for entity capabilities. '''
		# our containers:
		# __names is a string cache; every string long enough is given
		#   another object, and we will have plenty of identical long
		#   strings. therefore we can cache them
		#   TODO: maybe put all known xmpp namespace strings here
		#   (strings given in xmpppy)?
		# __cache is a dictionary mapping: pair of node and version maps
		#   to CapsCacheItem object
		# __CacheItem is a class that stores data about particular
		#   client (node/version pair)
		self.__names = {}
		self.__cache = {}

		class CacheItem(object):
			''' TODO: logging data into db '''
			def __init__(ciself, hash_method, hash):
				# cached into db
				ciself.hash_method = hash_method
				ciself.hash = hash
				ciself._features = []
				ciself._identities = []

				# not cached into db:
				# have we sent the query?
				# 0 == not queried
				# 1 == queried
				# 2 == got the answer
				ciself.queried = 0

			def _get_features(ciself):
				return ciself._features
			def _set_features(ciself, value):
				ciself._features = []
				for feature in value:
					ciself._features.append(self.__names.setdefault(feature,
						feature))
			features = property(ciself._get_features, ciself._set_features)

			def _get_identities(ciself):
				return ciself._identities
			def _set_identities(ciself, value):
				ciself._identities = []
				for identity in value:
					ciself._identities.append(self.__names.setdefault(identity,
						identity))
			identities = property(ciself._get_identities, ciself._set_identities)

			def update(ciself, identities, features):
				# NOTE: self refers to CapsCache object, not to CacheItem
				ciself.identities=identities
				ciself.features=features
				self.logger.add_caps_entry(ciself.hash_method, ciself.hash,
					identities, features)

		self.__CacheItem = CacheItem

		# prepopulate data which we are sure of; note: we do not log these info

		gajimcaps = self[('sha-1', gajim.caps_hash)]
		gajimcaps.identities = [gajim.gajim_identity]
		gajimcaps.features = gajim.gajim_common_features + \
			gajim.gajim_optional_features

		# start logging data from the net
		self.logger = logger

	def load_from_db(self):
		# get data from logger...
		if self.logger is not None:
			for hash_method, hash, identities, features in \
			self.logger.iter_caps_data():
				x = self[(hash_method, hash)]
				x.identities = identities
				x.features = features
				x.queried = 2

	def __getitem__(self, caps):
		if caps in self.__cache:
			return self.__cache[caps]
		hash_method, hash = caps[0], caps[1]
		x = self.__CacheItem(hash_method, hash)
		self.__cache[(hash_method, hash)] = x
		return x

	def preload(self, con, jid, node, hash_method, hash):
		''' Preload data about (node, ver, exts) caps using disco
		query to jid using proper connection. Don't query if
		the data is already in cache. '''
		q = self[(hash_method, hash)]

		if q.queried==0:
			# do query for bare node+hash pair
			# this will create proper object
			q.queried=1
			con.discoverInfo(jid, '%s#%s' % (node, hash))

gajim.capscache = CapsCache(gajim.logger)

class ConnectionCaps(object):
	''' This class highly depends on that it is a part of Connection class. '''
	def _capsPresenceCB(self, con, presence):
		''' Handle incoming presence stanzas... This is a callback
		for xmpp registered in connection_handlers.py'''

		# get the caps element
		caps = presence.getTag('c')
		if not caps:
			return

		hash_method, node, hash = caps['hash'], caps['node'], caps['ver']
		if hash_method is None or node is None or hash is None:
			# improper caps in stanza, ignoring
			return

		# we will put these into proper Contact object and ask
		# for disco... so that disco will learn how to interpret
		# these caps

		jid=str(presence.getFrom())

		# start disco query...
		gajim.capscache.preload(self, jid, node, hash_method, hash)

		contact=gajim.contacts.get_contact_from_full_jid(self.name, jid)
		if contact in [None, []]:
			return	# TODO: a way to put contact not-in-roster into Contacts
		elif isinstance(contact, list):
			contact = contact[0]

		# overwriting old data
		contact.caps_node = node
		contact.caps_hash_method = hash_method
		contact.caps_hash = hash

	def _capsDiscoCB(self, jid, node, identities, features, dataforms):
		contact = gajim.contacts.get_contact_from_full_jid(self.name, jid)
		if not contact:
			return
		if not contact.caps_node:
			return # we didn't asked for that?
		if not node.startswith(contact.caps_node + '#'):
			return
		node, hash = node.split('#', 1)
		computed_hash = helpers.compute_caps_hash(identities, features,
			contact.caps_hash_method)
		if computed_hash != hash:
			# wrong hash, forget it
			contact.caps_node = ''
			contact.caps_hash_method = ''
			contact.caps_hash = ''
			return

		# if we don't have this info already...
		caps = gajim.capscache[(contact.caps_hash_method, hash)]
		if caps.queried == 2:
			return

		caps.update(identities, features)
