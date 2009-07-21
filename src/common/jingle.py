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

# note: if there will be more types of sessions (possibly file transfer,
# video...), split this file

import gajim
import gobject
import xmpp
import urllib

from common import helpers

import logging
log = logging.getLogger('gajim.c.jingle')

def timeout_add_and_call(timeout, callable, *args, **kwargs):
	''' Call a callback once. If it returns True, add a timeout handler to call it more times.
	Helper function. '''
	if callable(*args, **kwargs):
		return gobject.timeout_add(timeout, callable, *args, **kwargs)
	return -1	# gobject.source_remove will not object

class JingleStates(object):
	''' States in which jingle session may exist. '''
	ended=0
	pending=1
	active=2

class Error(Exception): pass
class WrongState(Error): pass
class NoSuchSession(Error): pass

class JingleSession(object):
	''' This represents one jingle session. '''
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

		self.accepted=True	# is this session accepted by user

		# callbacks to call on proper contents
		# use .prepend() to add new callbacks, especially when you're going
		# to send error instead of ack
		self.callbacks={
			'content-accept':	[self.__contentAcceptCB, self.__broadcastCB, self.__defaultCB],
			'content-add':		[self.__defaultCB],
			'content-modify':	[self.__defaultCB],
			'content-remove':	[self.__defaultCB],
			'session-accept':	[self.__contentAcceptCB, self.__broadcastCB, self.__defaultCB],
			'session-info':		[self.__defaultCB],
			'session-initiate':	[self.__sessionInitiateCB, self.__broadcastCB, self.__defaultCB],
			'session-terminate':	[self.__broadcastAllCB, self.__defaultCB],
			'transport-info':	[self.__broadcastCB, self.__defaultCB],
			'iq-result':		[],
			'iq-error':		[],
		}

	''' Interaction with user '''
	def approveSession(self):
		''' Called when user accepts session in UI (when we aren't the initiator).'''
		self.accepted=True
		self.acceptSession()

	def declineSession(self):
		''' Called when user declines session in UI (when we aren't the initiator,
		or when the user wants to stop session completly. '''
		self.__sessionTerminate()

	''' Middle-level functions to manage contents. Handle local content
	cache and send change notifications. '''
	def addContent(self, name, content, creator='we'):
		''' Add new content to session. If the session is active,
		this will send proper stanza to update session. 
		The protocol prohibits changing that when pending.
		Creator must be one of ('we', 'peer', 'initiator', 'responder')'''
		assert creator in ('we', 'peer', 'initiator', 'responder')

		if self.state==JingleStates.pending:
			raise WrongState

		if (creator=='we' and self.weinitiate) or (creator=='peer' and not self.weinitiate):
			creator='initiator'
		elif (creator=='peer' and self.weinitiate) or (creator=='we' and not self.weinitiate):
			creator='responder'
		content.creator = creator
		content.name = name
		self.contents[(creator,name)]=content

		if self.state==JingleStates.active:
			pass # TODO: send proper stanza, shouldn't be needed now

	def removeContent(self, creator, name):
		''' We do not need this now '''
		pass

	def modifyContent(self, creator, name, *someother):
		''' We do not need this now '''
		pass

	def acceptSession(self):
		''' Check if all contents and user agreed to start session. '''
		if not self.weinitiate and self.accepted and \
		all(c.negotiated for c in self.contents.itervalues()):
			self.__sessionAccept()
	''' Middle-level function to do stanza exchange. '''
	def startSession(self):
		''' Start session. '''
		self.__sessionInitiate()

	def sendSessionInfo(self): pass

	''' Session callbacks. '''
	def stanzaCB(self, stanza):
		''' A callback for ConnectionJingle. It gets stanza, then
		tries to send it to all internally registered callbacks.
		First one to raise xmpp.NodeProcessed breaks function.'''
		jingle = stanza.getTag('jingle')
		error = stanza.getTag('error')
		if error:
			# it's an iq-error stanza
			action = 'iq-error'
		elif jingle:
			# it's a jingle action
			action = jingle.getAttr('action')
		else:
			# it's an iq-result (ack) stanza
			action = 'iq-result'

		callables = self.callbacks[action]

		try:
			for callable in callables:
				callable(stanza=stanza, jingle=jingle, error=error, action=action)
		except xmpp.NodeProcessed:
			pass

	def __defaultCB(self, stanza, jingle, error, action):
		''' Default callback for action stanzas -- simple ack
		and stop processing. '''
		response = stanza.buildReply('result')
		self.connection.connection.send(response)

	def __contentAcceptCB(self, stanza, jingle, error, action):
		''' Called when we get content-accept stanza or equivalent one
		(like session-accept).'''
		# check which contents are accepted
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']

	def __sessionInitiateCB(self, stanza, jingle, error, action):
		''' We got a jingle session request from other entity,
		therefore we are the receiver... Unpack the data,
		inform the user. '''
		self.initiator = jingle['initiator']
		self.responder = self.ourjid
		self.peerjid = self.initiator
		self.accepted = False	# user did not accept this session yet

		# TODO: If the initiator is unknown to the receiver (e.g., via presence
		# subscription) and the receiver has a policy of not communicating via
		# Jingle with unknown entities, it SHOULD return a <service-unavailable/>
		# error.

		# Lets check what kind of jingle session does the peer want
		fail = True
		contents = []
		for element in jingle.iterTags('content'):
			# checking what kind of session this will be
			desc_ns = element.getTag('description').getNamespace()
			tran_ns = element.getTag('transport').getNamespace()
			if desc_ns==xmpp.NS_JINGLE_RTP and tran_ns==xmpp.NS_JINGLE_ICE_UDP:
				# we've got voip content
				self.addContent(element['name'], JingleVoiP(self), 'peer')
				contents.append(('VOIP',))
				fail = False
			if desc_ns==xmpp.NS_JINGLE_XHTML and tran_ns==xmpp.NS_JINGLE_SXE:
				# we've got whiteboard content
				self.addContent(element['name'], JingleWhiteboard(self), 'peer')
				contents.append(('WHITEBOARD',))
				fail = False

		# If there's no content we understand...
		if fail:
			# TODO: we should send <unsupported-content/> inside too
			# TODO: delete this instance
			self.connection.connection.send(
				xmpp.Error(stanza, xmpp.NS_STANZAS + 'feature-not-implemented'))
			self.connection.deleteJingle(self)
			raise xmpp.NodeProcessed

		self.state = JingleStates.pending

		# Send event about starting a session
		self.connection.dispatch('JINGLE_INCOMING', (self.initiator, self.sid, contents))

	def __broadcastCB(self, stanza, jingle, error, action):
		''' Broadcast the stanza contents to proper content handlers. '''
		for content in jingle.iterTags('content'):
			name = content['name']
			creator = content['creator']
			cn = self.contents[(creator, name)]
			cn.stanzaCB(stanza, content, error, action)

	def __broadcastAllCB(self, stanza, jingle, error, action):
		''' Broadcast the stanza to all content handlers. '''
		for content in self.contents.itervalues():
			content.stanzaCB(stanza, None, error, action)

	def on_p2psession_error(self, *anything): pass

	''' Methods that make/send proper pieces of XML. They check if the session
	is in appropriate state. '''
	def __makeJingle(self, action):
		stanza = xmpp.Iq(typ='set', to=xmpp.JID(self.peerjid))
		jingle = stanza.addChild('jingle', attrs={'action': action,
			'initiator': self.initiator, 'responder': self.responder,
			'sid': self.sid}, namespace = xmpp.NS_JINGLE)
		return stanza, jingle

	def __appendContent(self, jingle, content):
		''' Append <content/> element to <jingle/> element,
		with (full=True) or without (full=False) <content/>
		children. '''
		jingle.addChild('content',
			attrs={'name': content.name, 'creator': content.creator})

	def __appendContents(self, jingle):
		''' Append all <content/> elements to <jingle/>.'''
		# TODO: integrate with __appendContent?
		# TODO: parameters 'name', 'content'?
		for content in self.contents.values():
			self.__appendContent(jingle, content)

	def __sessionInitiate(self):
		assert self.state==JingleStates.ended
		stanza, jingle = self.__makeJingle('session-initiate')
		self.__appendContents(jingle)
		self.__broadcastCB(stanza, jingle, None, 'session-initiate-sent')
		self.connection.connection.send(stanza)

	def __sessionAccept(self):
		assert self.state==JingleStates.pending
		stanza, jingle = self.__makeJingle('session-accept')
		self.__appendContents(jingle)
		self.__broadcastCB(stanza, jingle, None, 'session-accept-sent')
		self.connection.connection.send(stanza)
		self.state=JingleStates.active

	def __sessionInfo(self, payload=None):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__makeJingle('session-info')
		if payload:
			jingle.addChild(node=payload)
		self.connection.connection.send(stanza)

	def __sessionTerminate(self):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__makeJingle('session-terminate')
		self.__broadcastAllCB(stanza, jingle, None, 'session-terminate-sent')
		self.connection.connection.send(stanza)

	def __contentAdd(self):
		assert self.state==JingleStates.active

	def __contentAccept(self):
		assert self.state!=JingleStates.ended

	def __contentModify(self):
		assert self.state!=JingleStates.ended

	def __contentRemove(self):
		assert self.state!=JingleStates.ended

	def sendContentAccept(self, content):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__makeJingle('content-accept')
		jingle.addChild(node=content)
		self.connection.connection.send(stanza)

	def sendTransportInfo(self, content):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__makeJingle('transport-info')
		jingle.addChild(node=content)
		self.connection.connection.send(stanza)

	'''Callbacks'''
	def sessionTerminateCB(self, stanza): pass

class JingleContent(object):
	''' An abstraction of content in Jingle sessions. '''
	def __init__(self, session, node=None):
		self.session = session
		# will be filled by JingleSession.add_content()
		# don't uncomment these lines, we will catch more buggy code then
		# (a JingleContent not added to session shouldn't send anything)
		#self.creator = None
		#self.name = None
		self.negotiated = False		# is this content already negotiated?

class JingleWhiteboard(JingleContent):
	''' Jingle Whiteboard sessions consist of xhtml content'''
	def __init__(self, session, control=None):
		JingleContent.__init__(self, session)
		self.negotiated = True # there is nothing to negotiate
		self.last_rid = 0
		self.control = control

	def stanzaCB(self, stanza, content, error, action):
		''' Called when something related to our content was sent by peer. '''
		callbacks = {
			# these are called when *we* get stanzas
			'session-accept': [self.__sessionAcceptCB],
			'session-info': [],
			'session-initiate': [],
			'session-terminate': [self.__stop],
			'transport-info': [],
			'iq-result': [],
			'iq-error': [],
			'edit': [self.__editCB],
			# these are called when *we* sent these stanzas
			'session-initiate-sent': [self.__sessionInitiateSentCB],
			'session-accept-sent': [self.__sessionInitiateSentCB],
			'session-terminate-sent': [self.__stop],
		}[action]
		for callback in callbacks:
			callback(stanza, content, error, action)

	def __editCB(self, stanza, content, error, action):
		log.debug('got a whiteboard edit')
		#TODO: extract data, draw it. We have self.control which point to the ChatControl

	def __sessionAcceptCB(self, stanza, content, error, action):
		log.debug('session accepted')
		self.session.connection.dispatch('WHITEBOARD_ACCEPTED',
			(self.session.peerjid, self.session.sid))

	def generate_rids(self, x):
		# generates x number of rids and returns in list

		rids = []
		for x in range(x):
			rids.append(str(self.last_rid))
			self.last_rid += 1
		return rids

	def send_items(self, items, rids):
		# recieves dict items and a list of rids of items to send
		# TODO: is there a less clumsy way that doesn't involve passing
		# whole list

		self.session.connection.send_whiteboard_node(self.session.peerjid,
			self.session.sid, items, rids)

	def encode(self, xml):
		# encodes it sendable string
		return 'data:text/xml,' + urllib.quote(xml)

	def __sessionInitiateSentCB(self, stanza, content, error, action):
		''' Add our things to session-initiate stanza. '''
		content.addChild(xmpp.NS_JINGLE_XHTML + ' description')
		c = content.addChild(xmpp.NS_JINGLE_SXE + ' transport')
		c.setTagData('host', self.session.initiator)

	def __stop(self, *things):
		pass

class JingleVoiP(JingleContent):
	''' Jingle VoiP sessions consist of audio content transported
	over an ICE UDP protocol. '''
	def __init__(self, session, node=None):
		JingleContent.__init__(self, session, node)
		self.got_codecs = False

		#if node is None:
		#	self.audio = JingleAudioSession(self)
		#else:
		#	self.audio = JingleAudioSession(self, node.getTag('content'))
		#self.transport = JingleICEUDPSession(self)
		self.setupStream()

	def stanzaCB(self, stanza, content, error, action):
		''' Called when something related to our content was sent by peer. '''
		callbacks = {
			# these are called when *we* get stanzas
			'content-accept': [self.__getRemoteCodecsCB],
			'content-add': [],
			'content-modify': [],
			'content-remove': [],
			'session-accept': [self.__getRemoteCodecsCB, self.__startMic],
			'session-info': [],
			'session-initiate': [self.__getRemoteCodecsCB],
			'session-terminate': [self.__stop],
			'transport-info': [self.__transportInfoCB],
			'iq-result': [],
			'iq-error': [],
			# these are called when *we* sent these stanzas
			'session-initiate-sent': [self.__sessionInitiateSentCB],
			'session-accept-sent': [self.__startMic],
			'session-terminate-sent': [self.__stop],
		}[action]
		for callback in callbacks:
			callback(stanza, content, error, action)

	def __sessionInitiateSentCB(self, stanza, content, error, action):
		''' Add our things to session-initiate stanza. '''
		content.setAttr('profile', 'RTP/AVP')
		content.addChild(xmpp.NS_JINGLE_RTP+' description', payload=self.iterCodecs())
		content.addChild(xmpp.NS_JINGLE_ICE_UDP+' transport')

	def __getRemoteCodecsCB(self, stanza, content, error, action):
		''' Get peer codecs from what we get from peer. '''
		if self.got_codecs: return

		codecs = []
		for codec in content.getTag('description').iterTags('payload-type'):
			c = {'id': int(codec['id']),
				'encoding_name': codec['name'],
				'media_type': farsight.MEDIA_TYPE_AUDIO,
				'channels': 1,
				'params': dict((p['name'], p['value']) for p in codec.iterTags(
					'parameter'))}
			if 'channels' in codec: c['channels']=codec['channels']
			codecs.append(c)
		if len(codecs)==0: return

		self.p2pstream.set_remote_codecs(codecs)
		self.got_codecs=True

	def __transportInfoCB(self, stanza, content, error, action):
		''' Got a new transport candidate. '''
		candidates = []
		for candidate in content.getTag('transport').iterTags('candidate'):
			cand={
				'candidate_id':	self.session.connection.connection.getAnID(),
				'component':	int(candidate['component']),
				'ip':		candidate['ip'],
				'port':		int(candidate['port']),
				'proto_subtype':'RTP',
				'proto_profile':'AVP',
				'preference':	float(candidate['priority'])/100000,
				'type':		farsight.CANDIDATE_TYPE_LOCAL,
			}
			if candidate['protocol']=='udp':
				cand['proto']=farsight.NETWORK_PROTOCOL_UDP
			else:
				# we actually don't handle properly different tcp options in jingle
				cand['proto']=farsight.NETWORK_PROTOCOL_TCP
			if 'ufrag' in candidate:
				cand['username']=candidate['ufrag']
			if 'pwd' in candidate:
				cand['password']=candidate['pwd']

			candidates.append(cand)
		self.p2pstream.add_remote_candidate(candidates)

	def toXML(self):
		''' Return proper XML for <content/> element. '''
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator, 'profile': 'RTP/AVP'},
			payload=[
				xmpp.Node(xmpp.NS_JINGLE_RTP+' description', payload=self.iterCodecs()),
				xmpp.Node(xmpp.NS_JINGLE_ICE_UDP+' transport')
			])

	def __content(self, payload=[]):
		''' Build a XML content-wrapper for our data. '''
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator, 'profile': 'RTP/AVP'},
			payload=payload)

	def on_p2pstream_error(self, *whatever): pass
	def on_p2pstream_new_active_candidate_pair(self, stream, native, remote): pass
	def on_p2pstream_codec_changed(self, stream, codecid): pass
	def on_p2pstream_native_candidates_prepared(self, *whatever):
		pass

	def on_p2pstream_state_changed(self, stream, state, dir):
		if state==farsight.STREAM_STATE_CONNECTED:
			stream.signal_native_candidates_prepared()
			stream.start()
			self.pipeline.set_state(gst.STATE_PLAYING)

			self.negotiated = True
			if not self.session.weinitiate:
				self.session.sendContentAccept(self.__content((xmpp.Node('description', payload=self.iterCodecs()),)))
			self.session.acceptSession()

	def on_p2pstream_new_native_candidate(self, p2pstream, candidate_id):
		candidates = p2pstream.get_native_candidate(candidate_id)

		for candidate in candidates:
			self.send_candidate(candidate)

	def send_candidate(self, candidate):
		attrs={
			'component': candidate['component'],
			'foundation': '1', # hack
			'generation': '0',
			'ip': candidate['ip'],
			'network': '0',
			'port': candidate['port'],
			'priority': int(100000*candidate['preference']), # hack
		}
		if candidate['proto']==farsight.NETWORK_PROTOCOL_UDP:
			attrs['protocol']='udp'
		else:
			# we actually don't handle properly different tcp options in jingle
			attrs['protocol']='tcp'
		if 'username' in candidate: attrs['ufrag']=candidate['username']
		if 'password' in candidate: attrs['pwd']=candidate['password']
		c=self.__content()
		t=c.addChild(xmpp.NS_JINGLE_ICE_UDP+' transport')
		t.addChild('candidate', attrs=attrs)
		self.session.sendTransportInfo(c)

	def iterCodecs(self):
		codecs=self.p2pstream.get_local_codecs()
		for codec in codecs:
			a = {'name': codec['encoding_name'],
				'id': codec['id'],
				'channels': 1}
			if 'clock_rate' in codec: a['clockrate']=codec['clock_rate']
			if 'optional_params' in codec:
				p = (xmpp.Node('parameter', {'name': name, 'value': value})
					for name, value in codec['optional_params'].iteritems())
			else:	p = ()
			yield xmpp.Node('payload-type', a, p)

	''' Things to control the gstreamer's pipeline '''
	def setupStream(self):
		# the pipeline
		self.pipeline = gst.Pipeline()

		# the network part
		self.p2pstream = self.session.p2psession.create_stream(
			farsight.MEDIA_TYPE_AUDIO, farsight.STREAM_DIRECTION_BOTH)
		self.p2pstream.set_pipeline(self.pipeline)
		self.p2pstream.set_property('transmitter', 'libjingle')
		self.p2pstream.connect('error', self.on_p2pstream_error)
		self.p2pstream.connect('new-active-candidate-pair', self.on_p2pstream_new_active_candidate_pair)
		self.p2pstream.connect('codec-changed', self.on_p2pstream_codec_changed)
		self.p2pstream.connect('native-candidates-prepared', self.on_p2pstream_native_candidates_prepared)
		self.p2pstream.connect('state-changed', self.on_p2pstream_state_changed)
		self.p2pstream.connect('new-native-candidate', self.on_p2pstream_new_native_candidate)

		self.p2pstream.set_remote_codecs(self.p2pstream.get_local_codecs())

		self.p2pstream.prepare_transports()

		self.p2pstream.set_active_codec(8)	#???

		# the local parts
		# TODO: use gconfaudiosink?
		sink = gst.element_factory_make('alsasink')
		sink.set_property('sync', False)
		sink.set_property('latency-time', 20000)
		sink.set_property('buffer-time', 80000)
		self.pipeline.add(sink)

		self.src_signal = gst.element_factory_make('audiotestsrc')
		self.src_signal.set_property('blocksize', 320)
		self.src_signal.set_property('freq', 440)
		self.pipeline.add(self.src_signal)

		# TODO: use gconfaudiosrc?
		self.src_mic = gst.element_factory_make('alsasrc')
		self.src_mic.set_property('blocksize', 320)
		self.pipeline.add(self.src_mic)

		self.mic_volume = gst.element_factory_make('volume')
		self.mic_volume.set_property('volume', 0)
		self.pipeline.add(self.mic_volume)

		self.adder = gst.element_factory_make('adder')
		self.pipeline.add(self.adder)

		# link gst elements
		self.src_signal.link(self.adder)
		self.src_mic.link(self.mic_volume)
		self.mic_volume.link(self.adder)

		# this will actually start before the pipeline will be started.
		# no worries, though; it's only a ringing sound
		def signal():
			while True:
				self.src_signal.set_property('volume', 0.5)
				yield True # wait 750 ms
				yield True # wait 750 ms
				self.src_signal.set_property('volume', 0)
				yield True # wait 750 ms
		self.signal_cb_id = timeout_add_and_call(750, signal().__iter__().next)

		self.p2pstream.set_sink(sink)
		self.p2pstream.set_source(self.adder)

	def __startMic(self, *things):
		gobject.source_remove(self.signal_cb_id)
		self.src_signal.set_property('volume', 0)
		self.mic_volume.set_property('volume', 1)

	def __stop(self, *things):
		self.pipeline.set_state(gst.STATE_NULL)
		gobject.source_remove(self.signal_cb_id)

	def __del__(self):
		self.__stop()

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
		try:
			jid = helpers.get_full_jid_from_iq(stanza)
		except helpers.InvalidFormat:
			self.dispatch('ERROR', (_('Invalid Jabber ID'),
				_('A message from a non-valid JID arrived, it has been ignored.')))
		id = stanza.getID()

		if (jid, id) in self.__iq_responses.keys():
			self.__iq_responses[(jid, id)].stanzaCB(stanza)
			del self.__iq_responses[(jid, id)]
			raise xmpp.NodeProcessed

		jingle = stanza.getTag('jingle')
		if not jingle:
			return
		sid = jingle.getAttr('sid')

		# do we need to create a new jingle object
		if (jid, sid) not in self.__sessions:
			newjingle = JingleSession(con=self, weinitiate=False, jid=jid, sid=sid)
			self.addJingle(newjingle)

		# we already have such session in dispatcher...
		self.__sessions[(jid, sid)].stanzaCB(stanza)

		raise xmpp.NodeProcessed

	def _whiteboardCB(self, con, msg):
		# Handles whiteboard messages
		log.debug('_whiteboardCB')
		try:
			jid = helpers.get_full_jid_from_iq(msg)
		except helpers.InvalidFormat:
			self.dispatch('ERROR', (_('Invalid Jabber ID'),
				_('A message from a non-valid JID arrived, it has been ignored.')))

		sxe = msg.getTag('sxe')
		if not sxe:
			return
		sid = sxe.getAttr('session')
		if (jid, sid) not in self.__sessions:
			newjingle = JingleSession(con=self, weinitiate=False, jid=jid, sid=sid)
			self.addJingle(newjingle)

		# we already have such session in dispatcher...
		session = self.__sessions[(jid, sid)]
		cn = session.contents[('initiator', 'xhtml')]
		error = msg.getTag('error')
		if error:
			action = 'iq-error'
		else:
			action = 'edit'

		cn.stanzaCB(msg, sxe, error, action)

		raise xmpp.NodeProcessed

	def addJingleIqCallback(self, jid, id, jingle):
		self.__iq_responses[(jid, id)]=jingle

	def startVoiP(self, jid):
		jingle = JingleSession(self, weinitiate=True, jid=jid)
		self.addJingle(jingle)
		jingle.addContent('voice', JingleVoiP(jingle))
		jingle.startSession()

	def startWhiteboard(self, jid, control):
		jingle = JingleSession(self, weinitiate=True, jid=jid)
		self.addJingle(jingle)
		jingle.addContent('xhtml', JingleWhiteboard(jingle, control))
		jingle.startSession()

	def getJingleSession(self, jid, sid):
		try:
			return self.__sessions[(jid, sid)]
		except KeyError:
			raise NoSuchSession
