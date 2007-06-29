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

#import logger
#import gajim
from itertools import *
import gajim
import xmpp
import xmpp.features_nb

#from meta import VerboseClassType

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
	>>> cc[caps].category
	'client'
	>>> cc[caps].type
	'pc'
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
	>>> cc[newcaps].category='client'
	>>> cc[newcaps].type='pc'
	>>> cc[newcaps].features+=muc # same as:
	>>> cc[newcaps]+=muc
	>>> cc[newcaps]['csn']+=chatstates # adding data as if ext was 'csn'
	# warning: no feature removal!
	'''
#	__metaclass__ = VerboseClassType
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
		class CacheQuery(object):
#			__metaclass__ = VerboseClassType
			def __init__(cqself, proxied):
				cqself.proxied=proxied

			def __getattr__(cqself, obj):
				if obj!='exts': return getattr(cqself.proxied[0], obj)
				return set(chain(ci.features for ci in cqself.proxied))

		class CacheItem(object):
			''' TODO: logging data into db '''
#			__metaclass__ = VerboseClassType
			def __init__(ciself, node, version, ext=None):
				# cached into db
				ciself.node = node
				ciself.version = version
				ciself.features = set()
				ciself.exts = {}

				# set of tuples: (category, type, name)
				ciself.identities = set()

				ciself.cache = self

				# not cached into db:
				# have we sent the query?
				# 0 == not queried
				# 1 == queried
				# 2 == got the answer
				ciself.queried = 0

			def __iadd__(ciself, newfeature):
				newfeature=self.__names.setdefault(newfeature, newfeature)
				ciself.features.add(newfeature)

			def __getitem__(ciself, exts):
				if len(exts)==0:
					return ciself
				if len(exts)==1:
					ext=exts[0]
					if ext in ciself.exts:
						return ciself.exts[ext]
					x=CacheItem(ciself.node, ciself.version, ext)
					ciself.exts[ext]=x
					return x
				proxied = [ciself]
				proxied.extend(ciself[(e,)] for e in exts)
				return CacheQuery(proxied)

		self.__CacheItem = CacheItem

		# prepopulate data which we are sure of; note: we do not log these info
		gajim = 'http://gajim.org/caps'

		gajimcaps=self[(gajim, '0.11.1')]
		gajimcaps.category='client'
		gajimcaps.type='pc'
		gajimcaps.features=set((xmpp.NS_BYTESTREAM, xmpp.NS_SI,
			xmpp.NS_FILE, xmpp.NS_MUC, xmpp.NS_COMMANDS,
			xmpp.NS_DISCO_INFO, xmpp.NS_PING, xmpp.NS_TIME_REVISED))
		gajimcaps['cstates'].features=set((xmpp.NS_CHATSTATES,))
		gajimcaps['xhtml'].features=set((xmpp.NS_XHTML_IM,))

		# TODO: older gajim versions

		# start logging data from the net
		self.__logger = logger

		# get data from logger...
		if self.__logger is not None:
			for node, version, category, type_, name in self.__logger.get_caps_cache():
				x=self.__clients[(node, version)]
				x.category=category
				x.type=type_
				x.name=name
			for node, version, ext, feature in self.__logger.get_caps_features_cache():
				self.__clients[(node, version)][ext]+=feature

	def __getitem__(self, caps):
		node_version = caps[:2]
		if node_version in self.__cache:
			return self.__cache[node_version][caps[2]]
		node, version = self.__names.setdefault(caps[0], caps[0]), caps[1]
		x=self.__CacheItem(node, version)
		self.__cache[(node, version)]=x
		return x

	def preload(self, con, jid, node, ver, exts):
		''' Preload data about (node, ver, exts) caps using disco
		query to jid using proper connection. Don't query if
		the data is already in cache. '''
		q=self[(node, ver, ())]
		qq=q
		def callback(identities, features):
			try:
				qq.identities=set(
					(i['category'], i['type'], i.get('name'))
					for i in identities)
				qq.features=set(self.__names[f] for f in features)
				qq.queried=2
				print 'Got features!'
				print '%s/%s:' % (qq.node, qq.version)
				print '%s\n%s' % (qq.identities, qq.features)
			except KeyError: # improper answer, ignore
				qq.queried=0

		if q.queried==0:
			# do query for bare node+version pair
			# this will create proper object
			q.queried=1
			xmpp.features_nb.discoverInfo(con, jid, '%s#%s' % (node, ver), callback)

		for ext in exts:
			qq=q[ext]
			if qq.queried==0:
				# do query for node+version+ext triple
				qq.queried=1
				xmpp.features_nb.discoverInfo(con, jid,
					'%s#%s' % (node, ext), callback)

capscache = CapsCache()

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
		capscache.preload(con, jid, node, ver, exts)

		contact=gajim.contacts.get_contact_from_full_jid(self.name, jid)
		if contact in [None, []]:
			return	# TODO: a way to put contact not-in-roster into Contacts
		elif isinstance(contact, list):
			contact = contact[0]

		# overwriting old data
		contact.caps_node=node
		contact.caps_ver=ver
		contact.caps_exts=exts
