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
''' Handles the jingle signalling protocol. '''

import gajim
import xmpp

# ugly hack
import sys, dl, gst
sys.setdlopenflags(dl.RTLD_NOW | dl.RTLD_GLOBAL)
import farsight
sys.setdlopenflags(dl.RTLD_NOW | dl.RTLD_LOCAL)
FARSIGHT_MEDIA_TYPE_AUDIO=0
FARSIGHT_STREAM_DIRECTION_BOTH=3
FARSIGHT_NETWORK_PROTOCOL_UDP=0
FARSIGHT_CANDIDATE_TYPE_LOCAL=0

import meta

class JingleStates(object):
	''' States in which jingle session may exist. '''
	ended=0
	pending=1
	active=2

class Exception(object): pass
class WrongState(Exception): pass
class NoCommonCodec(Exception): pass

class JingleSession(object):
	''' This represents one jingle session. '''
	__metaclass__=meta.VerboseClassType
	def __init__(self, con, weinitiate, jid, sid=None):
		''' con -- connection object,
		    weinitiate -- boolean, are we the initiator?
		    jid - jid of the other entity'''
		self.contents={}	# negotiated contents
		self.connection=con	# connection to use
		# our full jid
		self.ourjid=gajim.get_jid_from_account(self.connection.name)+'/'+con.server_resource
		self.peerjid=jid	# jid we connect to
		# jid we use as the initiator
		self.initiator=weinitiate and self.ourjid or self.peerjid
		# jid we use as the responder
		self.responder=weinitiate and self.peerjid or self.ourjid
		# are we an initiator?
		self.weinitiate=weinitiate
		# what state is session in? (one from JingleStates)
		self.state=JingleStates.ended
		if not sid:
			sid=con.connection.getAnID()
		self.sid=sid		# sessionid

		# callbacks to call on proper contents
		# use .prepend() to add new callbacks, especially when you're going
		# to send error instead of ack
		self.callbacks={
			'content-accept':	[self.__contentAcceptCB, self.__defaultCB],
			'content-add':		[self.__defaultCB],
			'content-modify':	[self.__defaultCB],
			'content-remove':	[self.__defaultCB],
			'session-accept':	[self.__contentAcceptCB, self.__defaultCB],
			'session-info':		[self.__defaultCB],
			'session-initiate':	[self.__sessionInitiateCB, self.__defaultCB],
			'session-terminate':	[self.__defaultCB],
			'transport-info':	[self.__defaultCB],
			'iq-result':		[],
			'iq-error':		[],
		}

		# for making streams using farsight
		self.p2psession = farsight.farsight_session_factory_make('rtp')
		self.p2psession.connect('error', self.on_p2psession_error)

	''' Middle-level functions to manage contents. Handle local content
	cache and send change notifications. '''
	def addContent(self, name, content, initiator='we'):
		''' Add new content to session. If the session is active,
		this will send proper stanza to update session. 
		The protocol prohibits changing that when pending.
		Initiator must be one of ('we', 'peer', 'initiator', 'responder')'''
		if self.state==JingleStates.pending:
			raise WrongState

		if (initiator=='we' and self.weinitiate) or (initiator=='peer' and not self.weinitiate):
			initiator='initiator'
		elif (initiator=='peer' and self.weinitiate) or (initiator=='we' and not self.weinitiate):
			initiator='responder'
		content.creator = initiator
		content.name = name
		self.contents[(initiator,name)]=content

		if self.state==JingleStates.active:
			pass # TODO: send proper stanza, shouldn't be needed now

	def removeContent(self, creator, name):
		''' We do not need this now '''
		pass

	def modifyContent(self, creator, name, *someother):
		''' We do not need this now '''
		pass

	''' Middle-level function to do stanza exchange. '''
	def startSession(self):
		''' Start session. '''
		self.__sessionInitiate()

	def sendSessionInfo(self): pass
	def sendTransportInfo(self): pass

	''' Callbacks. '''
	def stanzaCB(self, stanza):
		''' A callback for ConnectionJingle. It gets stanza, then
		tries to send it to all internally registered callbacks.
		First one to raise xmpp.NodeProcessed breaks function.'''
		jingle = stanza.getTag('jingle')
		error = stanza.getTag('error')
		if error:
			# it's an iq-error stanza
			callables = 'iq-error'
		elif jingle:
			# it's a jingle action
			action = jingle.getAttr('action')
			callables = action
		else:
			# it's an iq-result (ack) stanza
			callables = 'iq-result'

		callables = self.callbacks[callables]

		try:
			for callable in callables:
				callable(stanza=stanza, jingle=jingle, error=error)
		except xmpp.NodeProcessed:
			pass

	def __defaultCB(self, stanza, jingle, error):
		''' Default callback for action stanzas -- simple ack
		and stop processing. '''
		response = stanza.buildReply('result')
		self.connection.connection.send(response)

	def __contentAcceptCB(self, stanza, jingle, error):
		''' Called when we get content-accept stanza or equivalent one
		(like session-accept).'''
		# check which contents are accepted, call their callbacks
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']
			

	def __sessionInitiateCB(self, stanza, jingle, error):
		''' We got a jingle session request from other entity,
		therefore we are the receiver... Unpack the data. '''
		self.initiator = jingle['initiator']
		self.responder = self.ourjid
		self.jid = self.initiator

		fail = True
		for element in jingle.iterTags('content'):
			# checking what kind of session this will be
			desc_ns = element.getTag('description').getNamespace()
			tran_ns = element.getTag('transport').getNamespace()
			if desc_ns==xmpp.NS_JINGLE_AUDIO and tran_ns==xmpp.NS_JINGLE_ICE_UDP:
				# we've got voip content
				self.addContent(element['name'], JingleVoiP(self, node=element), 'peer')
				fail = False

		if fail:
			# TODO: we should send <unsupported-content/> inside too
			self.connection.connection.send(
				xmpp.Error(stanza, xmpp.NS_STANZAS + 'feature-not-implemented'))
			self.connection.deleteJingle(self)
			raise xmpp.NodeProcessed

		self.state = JingleStates.pending

	def on_p2psession_error(self, *anything):
		print "Farsight session error!"

	''' Methods that make/send proper pieces of XML. They check if the session
	is in appropriate state. '''
	def __makeJingle(self, action):
		stanza = xmpp.Iq(typ='set', to=xmpp.JID(self.peerjid))
		jingle = stanza.addChild('jingle', attrs={
			'xmlns': 'http://www.xmpp.org/extensions/xep-0166.html#ns',
			'action': action,
			'initiator': self.initiator,
			'responder': self.responder,
			'sid': self.sid})
		return stanza, jingle

	def __appendContent(self, jingle, content, full=True):
		''' Append <content/> element to <jingle/> element,
		with (full=True) or without (full=False) <content/>
		children. '''
		if full:
			jingle.addChild(node=content.toXML())
		else:
			jingle.addChild('content',
				attrs={'name': content.name, 'creator': content.creator})

	def __appendContents(self, jingle, full=True):
		''' Append all <content/> elements to <jingle/>.'''
		# TODO: integrate with __appendContent?
		# TODO: parameters 'name', 'content'?
		for content in self.contents.values():
			self.__appendContent(jingle, content, full=full)

	def __sessionInitiate(self):
		assert self.state==JingleStates.ended
		stanza, jingle = self.__makeJingle('session-initiate')
		self.__appendContents(jingle)
		self.connection.connection.send(stanza)

	def __sessionAccept(self):
		assert self.state==JingleStates.pending
		stanza, jingle = self.__jingle('session-accept')
		self.__appendContents(jingle, False)
		self.connection.connection.send(stanza)
		self.state=JingleStates.active

	def __sessionInfo(self, payload=None):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__jingle('session-info')
		if payload:
			jingle.addChild(node=payload)
		self.connection.connection.send(stanza)

	def __sessionTerminate(self):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__jingle('session-terminate')
		self.connection.connection.send(stanza)

	def __contentAdd(self):
		assert self.state==JingleStates.active

	def __contentAccept(self):
		assert self.state!=JingleStates.ended

	def __contentModify(self):
		assert self.state!=JingleStates.ended

	def __contentRemove(self):
		assert self.state!=JingleStates.ended

	def __transportInfo(self):
		assert self.state!=JingleStates.ended

	'''Callbacks'''
	def sessionTerminateCB(self, stanza): pass

class Codec(object):
	''' This class keeps description of a single codec. '''
	def __init__(self, name, id=None, **params):
		''' Create new codec description. '''
		self.name = name
		self.id = id
		self.attrs = {'name': self.name, 'id': self.id, 'channels': 1}
		for key in ('channels', 'clockrate', 'maxptime', 'ptime'):
			if key in params:
				self.attrs[key]=params[key]
				del params[key]
		self.params = params

	def __eq__(a, b):
		''' Compare two codec descriptions. '''
		# TODO: check out what should be tested...
		if a.name!=b.name: return False
		# ...
		return True

	def toXML(self):
		return xmpp.Node('payload',
			attrs=self.attrs,
			payload=(xmpp.Node('parameter', {'name': k, 'value': v}) for k,v in self.params))

class JingleAudioSession(object):
	__metaclass__=meta.VerboseClassType
	def __init__(self, content, fromNode):
		self.content = content

		self.initiator_codecs=[]
		self.responder_codecs=[]

		if fromNode:
			# read all codecs peer understand
			for payload in fromNode.iterTags('payload-type'):
				attrs = fromNode.getAttrs().copy()
				for param in fromNode.iterTags('parameter'):
					attrs[param['name']]=param['value']
				self.initiator_codecs.append(Codec(**attrs))

	def sessionInitiateCB(self, stanza, ourcontent):
		pass

	''' "Negotiation" of codecs... simply presenting what *we* can do, nothing more... '''
	def getOurCodecs(self, other=None):
		''' Get a list of codecs we support. Try to get them in the same
		order as the codecs of our peer. If other!=None, raise
		a NoCommonCodec error if no codecs both sides support (None means
		we are initiating the connection and we don't know the other
		peer's codecs.) '''
		# for now we "understand" only one codec -- speex with clockrate 16000
		# so we have an easy job to do... (codecs sorted in order of preference)
		supported_codecs=[
			Codec('speex', clockrate='16000'),
		]

		other_l = other if other is not None else []
		our_l = supported_codecs[:]
		out = []
		ids = range(128)
		for codec in other_l:
			if codec in our_l:
				out.append(codec)
				our_l.remove(codec)
				try: ids.remove(codec.id)
				except ValueError: pass	# when id is not a dynamic one

		if other is not None and len(out)==0:
			raise NoCommonCodec

		for codec in our_l:
			if not codec.id or codec.id not in ids:
				codec.id = ids.pop()
			out.append(codec)

		return out

	''' Methods for making proper pieces of XML. '''
	def __codecsList(self, codecs):
		''' Prepares a description element with codecs given as a parameter. '''
		return xmpp.Node(xmpp.NS_JINGLE_AUDIO+' description',
			payload=(codec.toXML() for codec in codecs))

	def toXML(self):
		if not self.initiator_codecs:
			# we are the initiator, so just send our codecs
			self.initiator_codecs = self.getOurCodecs()
			return self.__codecsList(self.initiator_codecs)
		else:
			# we are the responder, we SHOULD adjust our codec list
			self.responder_codecs = self.getOurCodecs(self.initiator_codecs)
			return self.__codecsList(self.responder_codecs)

class JingleICEUDPSession(object):
	__metaclass__=meta.VerboseClassType
	def __init__(self, content):
		self.content = content

	def _sessionInitiateCB(self):
		''' Called when we initiate the session. '''
		pass

	def toXML(self):
		''' ICE-UDP doesn't send much in its transport stanza... '''
		return xmpp.Node(xmpp.NS_JINGLE_ICE_UDP+' transport')

class JingleVoiP(object):
	''' Jingle VoiP sessions consist of audio content transported
	over an ICE UDP protocol. '''
	__metaclass__=meta.VerboseClassType
	def __init__(self, session, node=None):
		self.session = session
		self.codecs = None

		#if node is None:
		#	self.audio = JingleAudioSession(self)
		#else:
		#	self.audio = JingleAudioSession(self, node.getTag('content'))
		#self.transport = JingleICEUDPSession(self)
		self.setupStream()

	def toXML(self):
		''' Return proper XML for <content/> element. '''
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator, 'profile': 'RTP/AVP'},
			payload=[
				xmpp.Node(xmpp.NS_JINGLE_AUDIO+' description', payload=self.getCodecs()),
				xmpp.Node(xmpp.NS_JINGLE_ICE_UDP+' transport')
			])

	def setupStream(self):
		self.p2pstream = self.session.p2psession.create_stream(FARSIGHT_MEDIA_TYPE_AUDIO, FARSIGHT_STREAM_DIRECTION_BOTH)
		self.p2pstream.set_property('transmitter', 'libjingle')
		self.p2pstream.connect('error', self.on_p2pstream_error)
		self.p2pstream.connect('new-active-candidate-pair', self.on_p2pstream_new_active_candidate_pair)
		self.p2pstream.connect('codec-changed', self.on_p2pstream_codec_changed)
		self.p2pstream.connect('native-candidates-prepared', self.on_p2pstream_native_candidates_prepared)
		self.p2pstream.connect('state-changed', self.on_p2pstream_state_changed)
		self.p2pstream.connect('new-native-candidate', self.on_p2pstream_new_native_candidate)
		self.p2pstream.prepare_transports()

	def on_p2pstream_error(self, *whatever): pass
	def on_p2pstream_new_active_candidate_pair(self, *whatever): pass
	def on_p2pstream_codec_changed(self, *whatever): pass
	def on_p2pstream_native_candidates_prepared(self, *whatever): pass
	def on_p2pstream_state_changed(self, *whatever): pass
	def on_p2pstream_new_native_candidate(self, *whatever): pass
	def getCodecs(self):
		codecs=self.p2pstream.get_local_codecs()
		return (xmpp.Node('payload', attrs=a) for a in codecs)

class ConnectionJingle(object):
	''' This object depends on that it is a part of Connection class. '''
	def __init__(self):
		# dictionary: (jid, sessionid) => JingleSession object
		self.__sessions = {}

		# dictionary: (jid, iq stanza id) => JingleSession object,
		# one time callbacks
		self.__iq_responses = {}

	def addJingle(self, jingle):
		''' Add a jingle session to a jingle stanza dispatcher
		jingle - a JingleSession object.
		'''
		self.__sessions[(jingle.peerjid, jingle.sid)]=jingle

	def deleteJingle(self, jingle):
		''' Remove a jingle session from a jingle stanza dispatcher '''
		del self.__session[(jingle.peerjid, jingle.sid)]

	def _JingleCB(self, con, stanza):
		''' The jingle stanza dispatcher.
		Route jingle stanza to proper JingleSession object,
		or create one if it is a new session.
		TODO: Also check if the stanza isn't an error stanza, if so
		route it adequatelly.'''

		# get data
		jid = stanza.getFrom()
		id = stanza.getID()

		if (jid, id) in self.__iq_responses.keys():
			self.__iq_responses[(jid, id)].stanzaCB(stanza)
			del self.__iq_responses[(jid, id)]
			raise xmpp.NodeProcessed

		jingle = stanza.getTag('jingle')
		if not jingle: return
		sid = jingle.getAttr('sid')

		# do we need to create a new jingle object
		if (jid, sid) not in self.__sessions:
			# TODO: we should check its type here...
			newjingle = JingleSession(con=self, weinitiate=False, jid=jid, sid=sid)
			self.addJingle(newjingle)

		# we already have such session in dispatcher...
		self.__sessions[(jid, sid)].stanzaCB(stanza)

		raise xmpp.NodeProcessed

	def addJingleIqCallback(self, jid, id, jingle):
		self.__iq_responses[(jid, id)]=jingle

	def startVoiP(self, jid):
		jingle = JingleSession(self, weinitiate=True, jid=jid)
		self.addJingle(jingle)
		jingle.addContent('voice', JingleVoiP(jingle))
		jingle.startSession()
