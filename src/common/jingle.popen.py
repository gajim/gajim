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
import gobject

import sys, dl, gst, gobject
sys.setdlopenflags(dl.RTLD_NOW | dl.RTLD_GLOBAL)
import farsight


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
			'content-accept':	[self.__contentAcceptCB, self.__broadcastCB, self.__defaultCB],
			'content-add':		[self.__defaultCB],
			'content-modify':	[self.__defaultCB],
			'content-remove':	[self.__defaultCB],
			'session-accept':	[self.__contentAcceptCB, self.__broadcastCB, self.__defaultCB],
			'session-info':		[self.__defaultCB],
			'session-initiate':	[self.__sessionInitiateCB, self.__broadcastCB, self.__defaultCB],
			'session-terminate':	[self.__defaultCB],
			'transport-info':	[self.__broadcastCB, self.__defaultCB],
			'iq-result':		[],
			'iq-error':		[],
		}

	''' Middle-level functions to manage contents. Handle local content
	cache and send change notifications. '''
	def addContent(self, name, content, creator='we'):
		''' Add new content to session. If the session is active,
		this will send proper stanza to update session. 
		The protocol prohibits changing that when pending.
		Creator must be one of ('we', 'peer', 'initiator', 'responder')'''
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

	''' Middle-level function to do stanza exchange. '''
	def startSession(self):
		''' Start session. '''
		self.__sessionInitiate()

	def sendSessionInfo(self): pass

	''' Callbacks. '''
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
		therefore we are the receiver... Unpack the data. '''
		self.initiator = jingle['initiator']
		self.responder = self.ourjid
		self.peerjid = self.initiator

		fail = True
		for element in jingle.iterTags('content'):
			# checking what kind of session this will be
			desc_ns = element.getTag('description').getNamespace()
			tran_ns = element.getTag('transport').getNamespace()
			if desc_ns==xmpp.NS_JINGLE_AUDIO and tran_ns==xmpp.NS_JINGLE_ICE_UDP:
				# we've got voip content
				self.addContent(element['name'], JingleVoiP(self), 'peer')
				fail = False

		if fail:
			# TODO: we should send <unsupported-content/> inside too
			self.connection.connection.send(
				xmpp.Error(stanza, xmpp.NS_STANZAS + 'feature-not-implemented'))
			self.connection.deleteJingle(self)
			raise xmpp.NodeProcessed

		self.state = JingleStates.pending

	def __broadcastCB(self, stanza, jingle, error, action):
		''' Broadcast the stanza contents to proper content handlers. '''
		for content in jingle.iterTags('content'):
			name = content['name']
			creator = content['creator']
			cn = self.contents[(creator, name)]
			cn.stanzaCB(stanza, content, error, action)

	def on_p2psession_error(self, *anything):
		print self.weinitiate, "Farsight session error!"

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

	def sendTransportInfo(self, content):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__makeJingle('transport-info')
		jingle.addChild(node=content)
		self.connection.connection.send(stanza)

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
		return xmpp.Node('payload-type',
			attrs=self.attrs,
			payload=(xmpp.Node('parameter', {'name': k, 'value': v}) for k,v in self.params))

class JingleAudioSession(object):
#	__metaclass__=meta.VerboseClassType
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

class JingleContent(object):
	''' An abstraction of content in Jingle sessions. '''
	def __init__(self, session, node=None):
		self.session = session
		# will be filled by JingleSession.add_content()
		# don't uncomment these lines, we will catch more buggy code then
		# (a JingleContent not added to session shouldn't send anything)
		#self.creator = None
		#self.name = None

class JingleVoiP(JingleContent):
	''' Jingle VoiP sessions consist of audio content transported
	over an ICE UDP protocol. '''
#	__metaclass__=meta.VerboseClassType
	def __init__(self, session, node=None):
		JingleContent.__init__(self, session, node)
		self.got_codecs = False
		self.codecs = []

		#if node is None:
		#	self.audio = JingleAudioSession(self)
		#else:
		#	self.audio = JingleAudioSession(self, node.getTag('content'))
		#self.transport = JingleICEUDPSession(self)
		self.setupStream()

	def stanzaCB(self, stanza, content, error, action):
		''' Called when something related to our content was sent by peer. '''
		callbacks = {
			'content-accept': [self.__getRemoteCodecsCB],
			'content-add': [],
			'content-modify': [],
			'content-remove': [],
			'session-accept': [self.__getRemoteCodecsCB],
			'session-info': [],
			'session-initiate': [self.__getRemoteCodecsCB],
			'session-terminate': [],
			'transport-info': [self.__transportInfoCB],
			'iq-result': [],
			'iq-error': [],
		}[action]
		for callback in callbacks:
			callback(stanza, content, error, action)

	def __getRemoteCodecsCB(self, stanza, content, error, action):
		if self.got_codecs: return

		codecs = []
		for codec in content.getTag('description').iterTags('payload-type'):
			c = {'id': int(codec['id']),
			     'encoding_name': codec['name'],
			     'media_type': farsight.MEDIA_TYPE_AUDIO,
			     'channels': 1,
			     'params': dict((p['name'], p['value']) for p in codec.iterTags('parameter'))}
			if 'channels' in codec: c['channels']=codec['channels']
			codecs.append(c)
			self.p2pin.write('%d %d %s %d %d %d\n' % (1, farsight.MEDIA_TYPE_AUDIO,
				codec['encoding_name'], codec['id'], codec['clock_rate'], codec['channels']))
		if len(codecs)==0: return

		print self.session.weinitiate, "#farsight_stream_set_remote_codecs"
		#self.p2pstream.set_remote_codecs(codecs)
		self.p2pin.write('%d %d %s %d %d %d\n' % (1, farsight.MEDIA_TYPE_AUDIO,
			'LAST', 0, 0, 0))
		self.got_codecs=True

	def __transportInfoCB(self, stanza, content, error, action):
		''' Got a new transport candidate. '''
		candidates = []
		for candidate in content.getTag('transport').iterTags('candidate'):
			cand={
			#	'candidate_id':	str(self.session.connection.connection.getAnID()),
				'candidate_id':	candidate['cid'],
				'component':	int(candidate['component']),
				'ip':		candidate['ip'],
				'port':		int(candidate['port']),
				'proto':	candidate['protocol']=='udp' and farsight.NETWORK_PROTOCOL_UDP \
						or farsight.NETWORK_PROTOCOL_TCP,
				'proto_subtype':'RTP',
				'proto_profile':'AVP',
				'preference':	float(candidate['priority'])/100000,
			#	'type':		farsight.CANDIDATE_TYPE_LOCAL,
				'type':		int(candidate['type']),
			}
			if 'ufrag' in candidate: cand['username']=candidate['ufrag']
			if 'pwd' in candidate: cand['password']=candidate['pwd']

			self.p2pin.write('%d %d %s %s %d %s %s\n' % (0, int(candidate['type']), candidate['cid'], candidate['ip'], int(candidate['port']), candidate['ufrag'], candidate['pwd']))
			candidates.append(cand)
		print self.session.weinitiate, "#add_remote_candidate"
		#self.p2pstream.add_remote_candidate(candidates)

	def toXML(self):
		''' Return proper XML for <content/> element. '''
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator, 'profile': 'RTP/AVP'},
			payload=[
				xmpp.Node(xmpp.NS_JINGLE_AUDIO+' description', payload=self.iterCodecs()),
				xmpp.Node(xmpp.NS_JINGLE_ICE_UDP+' transport')
			])

	def __content(self, payload=[]):
		''' Build a XML content-wrapper for our data. '''
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator, 'profile': 'RTP/AVP'},
			payload=payload)

	def new_data(self, *things):
		buf = self.p2pout.readline()
		print "RECV: %r"%buf
		msg = buf.split(' ')
		try:
			type = int(msg.pop(0))
		except:
			return True
		#print msg
		if type==0:
			media_type, id, ip, port, username, password = msg[:6]
			media_type=int(media_type)
			port=int(port)
			#print "Received %d %s %s %d %s %s" % (media_type, id, ip, port, username, password)
			self.send_candidate({'candidate_id': id, 'component': 1, 'ip': ip,
				'port': port, 'username': username, 'password': password,
				'proto': farsight.NETWORK_PROTOCOL_UDP, 'proto_subtype': 'RTP',
				'proto_profile': 'AVP', 'preference': 1.0, 'type': 0})
		elif type==1:
			media_type, encoding_name, pt, clock_rate, channels=msg[:5]
			media_type=int(media_type)
			pt=int(pt)
			clock_rate=int(clock_rate)
			channels=int(channels)

			#print "Received %d %s %d %d %d" % (media_type, encoding_name, pt, clock_rate, channels)
			if encoding_name!='LAST':
				self.codecs.append((media_type, encoding_name, pt, clock_rate, channels))
			else:
				self.got_codecs=True
		return True

	def setupStream(self):
		import popen2
		self.p2pout, self.p2pin = popen2.popen2('/home/liori/Projekty/SoC/trunk/src/common/jingle-handler.py')
		gobject.io_add_watch(self.p2pout, gobject.IO_IN, self.new_data)
		while not self.got_codecs:
			self.new_data()
		return
		print self.session.weinitiate, "#farsight_session_create_stream"
		self.p2pstream = self.session.p2psession.create_stream(
			farsight.MEDIA_TYPE_AUDIO, farsight.STREAM_DIRECTION_BOTH)
		self.p2pstream.set_property('transmitter', 'libjingle')
		self.p2pstream.connect('error', self.on_p2pstream_error)
		self.p2pstream.connect('new-active-candidate-pair', self.on_p2pstream_new_active_candidate_pair)
		self.p2pstream.connect('codec-changed', self.on_p2pstream_codec_changed)
		self.p2pstream.connect('native-candidates-prepared', self.on_p2pstream_native_candidates_prepared)
		self.p2pstream.connect('state-changed', self.on_p2pstream_state_changed)
		self.p2pstream.connect('new-native-candidate', self.on_p2pstream_new_native_candidate)

		self.p2pstream.set_remote_codecs(self.p2pstream.get_local_codecs())

		print self.session.weinitiate, "#farsight_stream_prepare_transports"
		self.p2pstream.prepare_transports()

		print self.session.weinitiate, "#farsight_stream_set_active_codec"
		self.p2pstream.set_active_codec(8)	#???

		sink = gst.element_factory_make('alsasink')
		sink.set_property('sync', False)
		sink.set_property('latency-time', 20000)
		sink.set_property('buffer-time', 80000)

		src = gst.element_factory_make('audiotestsrc')
		src.set_property('blocksize', 320)
		#src.set_property('latency-time', 20000)
		src.set_property('is-live', True)

		print self.session.weinitiate, "#farsight_stream_set_sink"
		self.p2pstream.set_sink(sink)
		print self.session.weinitiate, "#farsight_stream_set_source"
		self.p2pstream.set_source(src)

	def on_p2pstream_error(self, *whatever): pass
	def on_p2pstream_new_active_candidate_pair(self, stream, native, remote):
		print self.session.weinitiate, "##new_active_candidate_pair"
		#print "New native candidate pair: %s, %s" % (native, remote)
	def on_p2pstream_codec_changed(self, stream, codecid):
		print self.session.weinitiate, "##codec_changed"
		#print "Codec changed: %d" % codecid
	def on_p2pstream_native_candidates_prepared(self, *whatever):
		print self.session.weinitiate, "##native_candidates_prepared"
		#print "Native candidates prepared: %r" % whatever
		for candidate in self.p2pstream.get_native_candidate_list():
			self.send_candidate(candidate)
	def on_p2pstream_state_changed(self, stream, state, dir):
		print self.session.weinitiate, "##state_changed"
		#print "State: %d, Dir: %d" % (state, dir)
		if state==farsight.STREAM_STATE_CONNECTED:
			print self.session.weinitiate, "#farsight_stream_signal_native_candidates_prepared"
			stream.signal_native_candidates_prepared()
			print self.session.weinitiate, "#farsight_stream_start"
			stream.start()
	def on_p2pstream_new_native_candidate(self, p2pstream, candidate_id):
		print self.session.weinitiate, "##new_native_candidate"
		print self.session.weinitiate, "#get_native_candidate"
		candidates = p2pstream.get_native_candidate(candidate_id)
		print self.session.weinitiate, "#!", repr(candidates)

		for candidate in candidates:
			self.send_candidate(candidate)
	def send_candidate(self, candidate):
		attrs={
			'cid': candidate['candidate_id'],
			'component': candidate['component'],
			'foundation': '1', # hack
			'generation': '0',
			'type': candidate['type'],
			'ip': candidate['ip'],
			'network': '0',
			'port': candidate['port'],
			'priority': int(100000*candidate['preference']), # hack
			'protocol': candidate['proto']==farsight.NETWORK_PROTOCOL_UDP and 'udp' or 'tcp',
		}
		if 'username' in candidate: attrs['ufrag']=candidate['username']
		if 'password' in candidate: attrs['pwd']=candidate['password']
		c=self.__content()
		t=c.addChild(xmpp.NS_JINGLE_ICE_UDP+' transport')
		t.addChild('candidate', attrs=attrs)
		self.session.sendTransportInfo(c)

	def iterCodecs(self):
		for codec in self.codecs:
			media_type, encoding_name, pt, clock_rate, channels=codec
			yield xmpp.Node('payload-type', {
				'name': encoding_name,
				'id': pt,
				'channels': channels,
				'clock_rate': clock_rate})
		
#		print self.session.weinitiate, "#farsight_stream_get_local_codecs"
#		codecs=self.p2pstream.get_local_codecs()
#		for codec in codecs:
#			a = {'name': codec['encoding_name'],
#			     'id': codec['id'],
#			     'channels': 1}
#			if 'clock_rate' in codec: a['clockrate']=codec['clock_rate']
#			if 'optional_params' in codec:
#				p = (xmpp.Node('parameter', {'name': name, 'value': value})
#				     for name, value in codec['optional_params'].iteritems())
#			else:	p = ()
#			yield xmpp.Node('payload-type', a, p)

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
