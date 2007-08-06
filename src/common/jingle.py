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

import xmpp

class JingleStates(object):
	''' States in which jingle session may exist. '''
	ended=0
	pending=1
	active=2

class WrongState(exception): pass
class NoCommonCodec(exception): pass

class JingleSession(object):
	''' This represents one jingle session. '''
	def __init__(self, con, weinitiate, jid):
		''' con -- connection object,
		    weinitiate -- boolean, are we the initiator?
		    jid - jid of the other entity'''
		self.contents={}	# negotiated contents
		self.connection=con	# connection to use
		# our full jid
		self.ourjid=gajim.get_full_jid_from_account(self.connection.name)
		self.jid=jid		# jid we connect to
		# jid we use as the initiator
		self.initiator=weinitiate and self.ourjid or self.jid
		# jid we use as the responder
		self.responder=weinitiate and self.jid or self.ourjid
		# are we an initiator?
		self.weinitiate=weinitiate
		# what state is session in? (one from JingleStates)
		self.state=JingleStates.ended
		self.sid=con.getAnID()	# sessionid

		# callbacks to call on proper contents
		# use .prepend() to add new callbacks
		self.callbacks=dict((key, [self.__defaultCB]) for key in
			('content-accept', 'content-add', 'content-modify',
			 'content-remove', 'session-accept', 'session-info',
			 'session-initiate', 'session-terminate',
			 'transport-info'))
		self.callbacks['iq-result']=[]
		self.callbacks['iq-error']=[]

	''' Middle-level functions to manage contents. Handle local content
	cache and send change notifications. '''
	def addContent(self, name, description, transport, profile=None):
		''' Add new content to session. If the session is active,
		this will send proper stanza to update session. 
		The protocol prohibits changing that when pending.'''
		if self.state==JingleStates.pending:
			raise WrongState

		content={'creator': 'initiator',
			'name': name,
			'description': description,
			'transport': transport}
		if profile is not None:
			content['profile']=profile
		self.contents[('initiator', name)]=content

		if self.state==JingleStates.active:
			pass # TODO: send proper stanza, shouldn't be needed now

	''' Middle-level function to do stanza exchange. '''
	def startSession(self):
		''' Start session. '''
		self.__sessionInitiate(self)

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
		else if jingle:
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
		self.connection.send(response)
		raise xmpp.NodeProcessed

	''' Methods that make/send proper pieces of XML. They check if the session
	is in appropriate state. '''
	def makeJingle(self, action):
		stanza = xmpp.Iq(typ='set', to=xmpp.JID(self.jid))
		jingle = stanza.addChild('jingle', attrs=
			'xmlns': 'http://www.xmpp.org/extensions/xep-0166.html#ns',
			'action': action,
			'initiator': self.initiator,
			'responder': self.responder,
			'sid': self.sid})
		return stanza, jingle

	def appendContent(self, jingle, content, full=True):
		''' Append <content/> element to <jingle/> element,
		with (full=True) or without (full=False) <content/>
		children. '''
		c=jingle.addChild('content', attrs={
			'creator': content['creator'],
			'name': content['name']})
		if 'profile' in content:
			c['profile']=content['profile']
		if full:
			c.addChild(node=content['description'])
			c.addChild(node=content['transport'])
		return c

	def appendContents(self, jingle, full=True):
		''' Append all <content/> elements to <jingle/>.'''
		# TODO: integrate with __appendContent?
		# TODO: parameters 'name', 'content'?
		for content in self.contents.values():
			self.__appendContent(jingle, content, full=full)

	def __sessionInitiate(self):
		assert self.state==JingleStates.ended

	def __sessionAccept(self):
		assert self.state==JingleStates.pending
		stanza, jingle = self.__jingle('session-accept')
		self.__appendContents(jingle, False)
		self.connection.send(stanza)
		self.state=JingleStates.active

	def __sessionInfo(self, payload=None):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__jingle('session-info')
		if payload:
			jingle.addChild(node=payload)
		self.connection.send(stanza)

	def __sessionTerminate(self):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__jingle('session-terminate')
		self.connection.send(stanza)

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
	def sessionInitiateCB(self, stanza):
		''' We got a jingle session request from other entity,
		therefore we are the receiver... Unpack the data. '''
		jingle = stanza.getTag('jingle')
		self.initiator = jingle['initiator']
		self.responder = self.ourjid
		self.jid = self.initiator
		self.state = JingleStates.pending
		self.sid = jingle['sid']
		for element in jingle.iterTags('content'):
			content={'creator': 'initiator',
				'name': element['name']
				'description': element.getTag('description'),
				'transport': element.getTag('transport')}
			if element.has_attr('profile'):
				content['profile']=element['profile']
			self.contents[('initiator', content['name'])]=content

	def sessionTerminateCB(self, stanza): pass

class JingleAudioSession(object):
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

	def __init__(self, con, weinitiate, jid):
		JingleSession.__init__(self, con, weinitiate, jid)
		if weinitiate:
			pass #add voice content
		self.callbacks['session-initiate'].prepend(

		self.initiator_codecs=[]
		self.responder_codecs=[]

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
		for codec in other:
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
		return xmpp.Node('description',
			xmlns=xmpp.NS_JINGLE_AUDIO,
			payload=(codec.toXML() for codec in codecs))

class JingleICEUDPSession(object):
	def __init__(self, con, weinitiate, jid):
		pass

class JingleVoiP(JingleSession):
	''' Jingle VoiP sessions consist of audio content transported
	over an ICE UDP protocol. '''
	def __init__(*data):
		JingleAudioSession.__init__(*data)
		JingleICEUDPSession.__init__(*data)

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
		self.__sessions[(jingle.jid, jingle.sid)]=jingle

	def deleteJingle(self, jingle):
		''' Remove a jingle session from a jingle stanza dispatcher '''
		del self.__session[(jingle.jid, jingle.sid)]

	def _jingleCB(self, con, stanza):
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
		sid = jingle.getAttr('sid')

		# do we need to create a new jingle object
		if (jid, sid) not in self.__sessions:
			# we should check its type here...
			newjingle = JingleAudioSession(con=self, weinitiate=False, jid=jid)
			self.addJingle(newjingle)

		# we already have such session in dispatcher...
		return self.__sessions[(jid, sid)].stanzaCB(stanza)

	def addJingleIqCallback(jid, id, jingle):
		self.__iq_responses[(jid, id)]=jingle
