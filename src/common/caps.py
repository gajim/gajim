##
## Copyright (C) 2006 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

from itertools import *
import xmpp
import xmpp.features_nb
import gajim

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
			def __init__(ciself, node, version, ext=None):
				# cached into db
				ciself.node = node
				ciself.version = version
				ciself.features = set()
				ciself.ext = ext
				ciself.exts = {}

				# set of tuples: (category, type, name)
				# (dictionaries are not hashable, so cannot be in sets)
				ciself.identities = set()

				# not cached into db:
				# have we sent the query?
				# 0 == not queried
				# 1 == queried
				# 2 == got the answer
				ciself.queried = 0

			class CacheQuery(object):
				def __init__(cqself, proxied):
					cqself.proxied=proxied

				def __getattr__(cqself, obj):
					if obj!='exts': return getattr(cqself.proxied[0], obj)
					return set(chain(ci.features for ci in cqself.proxied))

			def __getitem__(ciself, exts):
				if not exts:	# (), [], None, False, whatever
					return ciself
				if isinstance(exts, basestring):
					exts=(exts,)
				if len(exts)==1:
					ext=exts[0]
					if ext in ciself.exts:
						return ciself.exts[ext]
					x=CacheItem(ciself.node, ciself.version, ext)
					ciself.exts[ext]=x
					return x
				proxied = [ciself]
				proxied.extend(ciself[(e,)] for e in exts)
				return ciself.CacheQuery(proxied)

			def update(ciself, identities, features):
				# NOTE: self refers to CapsCache object, not to CacheItem
				self.identities=identities
				self.features=features
				self.logger.add_caps_entry(
					ciself.node, ciself.version, ciself.ext,
					identities, features)

		self.__CacheItem = CacheItem

		# prepopulate data which we are sure of; note: we do not log these info
		gajimnode = 'http://gajim.org/caps'

		gajimcaps=self[(gajimnode, '0.11.1')]
		gajimcaps.category='client'
		gajimcaps.type='pc'
		gajimcaps.features=set((xmpp.NS_BYTESTREAM, xmpp.NS_SI,
			xmpp.NS_FILE, xmpp.NS_MUC, xmpp.NS_COMMANDS,
			xmpp.NS_DISCO_INFO, xmpp.NS_PING, xmpp.NS_TIME_REVISED))
		gajimcaps['cstates'].features=set((xmpp.NS_CHATSTATES,))
		gajimcaps['xhtml'].features=set((xmpp.NS_XHTML_IM,))

		# TODO: older gajim versions

		# start logging data from the net
		self.logger = logger

	def load_from_db(self):
		# get data from logger...
		if self.logger is not None:
			for node, ver, ext, identities, features in self.logger.iter_caps_data():
				x=self[(node, ver, ext)]
				x.identities=identities
				x.features=features
				x.queried=2

	def __getitem__(self, caps):
		node_version = caps[:2]
		if node_version in self.__cache:
			return self.__cache[node_version][caps[2]]
		node, version = self.__names.setdefault(caps[0], caps[0]), caps[1]
		x=self.__CacheItem(node, version)
		self.__cache[(node, version)]=x
		return x

	def preload(self, account, jid, node, ver, exts):
		''' Preload data about (node, ver, exts) caps using disco
		query to jid using proper connection. Don't query if
		the data is already in cache. '''
		q=self[(node, ver, ())]
		qq=q

		if q.queried==0:
			# do query for bare node+version pair
			# this will create proper object
			q.queried=1
			account.discoverInfo(jid, '%s#%s' % (node, ver))

		for ext in exts:
			qq=q[ext]
			if qq.queried==0:
				# do query for node+version+ext triple
				qq.queried=1
				account.discoverInfo(jid, '%s#%s' % (node, ext))

gajim.capscache = CapsCache(gajim.logger)

class ConnectionCaps(object):
	''' This class highly depends on that it is a part of Connection class. '''
	def _capsPresenceCB(self, con, presence):
		''' Handle incoming presence stanzas... This is a callback
		for xmpp registered in connection_handlers.py'''

		# get the caps element
		caps=presence.getTag('c')
		if not caps: return

		node, ver=caps['node'], caps['ver']
		if node is None or ver is None:
			# improper caps in stanza, ignoring
			return

		try:
			exts=caps['ext'].split(' ')
		except AttributeError:
			# no exts means no exts, a perfectly valid case
			exts=[]

		# we will put these into proper Contact object and ask
		# for disco... so that disco will learn how to interpret
		# these caps

		jid=str(presence.getFrom())

		# start disco query...
		gajim.capscache.preload(self, jid, node, ver, exts)

		contact=gajim.contacts.get_contact_from_full_jid(self.name, jid)
		if contact in [None, []]:
			return	# TODO: a way to put contact not-in-roster into Contacts
		elif isinstance(contact, list):
			contact = contact[0]

		# overwriting old data
		contact.caps_node=node
		contact.caps_ver=ver
		contact.caps_exts=exts

	def _capsDiscoCB(self, jid, node, identities, features, data):
		contact=gajim.contacts.get_contact_from_full_jid(self.name, jid)
		if not contact: return
		if not contact.caps_node: return # we didn't asked for that?
		if not node.startswith(contact.caps_node+'#'): return
		node, ext = node.split('#')
		if ext==contact.caps_ver:	# this can be also version (like '0.9')
			exts=None
		else:
			exts=(ext,)

		# if we don't have this info already...
		caps=gajim.capscache[(node, contact.caps_ver, exts)]
		if caps.queried==2: return

		identities=set((i['category'], i['type'], i.get('name')) for i in identities)
		caps.update(identities, features)

