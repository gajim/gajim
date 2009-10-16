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

#TODO:
# * things in XEP 0166, including:
#   - 'senders' attribute of 'content' element
#   - security preconditions
#   * actions:
#     - content-modify
#     - description-info, session-info
#     - security-info
#     - transport-accept, transport-reject
#   * sid/content related:
#      - tiebreaking
#      - if there already is a session, use it
# * things in XEP 0176, including:
#      - http://xmpp.org/extensions/xep-0176.html#protocol-restarts
#      - http://xmpp.org/extensions/xep-0176.html#fallback
# * XEP 0177 (raw udp)

# * UI:
#   - make state and codec informations available to the user
#   - video integration
#   * config:
#     - codecs
#     - STUN

# * DONE: figure out why it doesn't work with pidgin:
#     That's a bug in pidgin: http://xmpp.org/extensions/xep-0176.html#protocol-checks

# * timeout

# * split this file in several modules
#   For example, a file dedicated for XEP0166, one for XEP0176,
#   and one for XEP0167

# * handle different kinds of sink and src elements

import gajim
import xmpp
import helpers

import farsight, gst

def get_first_gst_element(elements):
	''' Returns, if it exists, the first available element of the list. '''
	for name in elements:
		factory = gst.element_factory_find(name)
		if factory:
			return factory.create()

#FIXME: Move it to JingleSession.States?
class JingleStates(object):
	''' States in which jingle session may exist. '''
	ended = 0
	pending = 1
	active = 2

#FIXME: Move it to JingleTransport.Type?
class TransportType(object):
	''' Possible types of a JingleTransport '''
	datagram = 1
	streaming = 2

class OutOfOrder(Exception):
	''' Exception that should be raised when an action is received when in the wrong state. '''

class TieBreak(Exception):
	''' Exception that should be raised in case of a tie, when we overrule the other action. '''

class JingleSession(object):
	''' This represents one jingle session. '''
	def __init__(self, con, weinitiate, jid, sid=None):
		''' con -- connection object,
			 weinitiate -- boolean, are we the initiator?
			 jid - jid of the other entity'''
		self.contents = {} # negotiated contents
		self.connection = con # connection to use
		# our full jid
		self.ourjid = gajim.get_jid_from_account(self.connection.name) + '/' + \
			con.server_resource
		self.peerjid = jid # jid we connect to
		# jid we use as the initiator
		self.initiator = weinitiate and self.ourjid or self.peerjid
		# jid we use as the responder
		self.responder = weinitiate and self.peerjid or self.ourjid
		# are we an initiator?
		self.weinitiate = weinitiate
		# what state is session in? (one from JingleStates)
		self.state = JingleStates.ended
		if not sid:
			sid = con.connection.getAnID()
		self.sid = sid # sessionid

		self.accepted = True # is this session accepted by user

		# callbacks to call on proper contents
		# use .prepend() to add new callbacks, especially when you're going
		# to send error instead of ack
		self.callbacks = {
			'content-accept':	[self.__contentAcceptCB, self.__broadcastCB,
				self.__defaultCB],
			'content-add':		[self.__contentAddCB, self.__broadcastCB,
				self.__defaultCB], #TODO
			'content-modify':	[self.__defaultCB], #TODO
			'content-reject':	[self.__defaultCB, self.__contentRemoveCB], #TODO
			'content-remove':	[self.__defaultCB, self.__contentRemoveCB],
			'description-info':	[self.__broadcastCB, self.__defaultCB], #TODO
			'security-info':	[self.__defaultCB], #TODO
			'session-accept':	[self.__sessionAcceptCB, self.__contentAcceptCB,
				self.__broadcastCB, self.__defaultCB],
			'session-info':		[self.__sessionInfoCB, self.__broadcastCB, self.__defaultCB],
			'session-initiate':	[self.__sessionInitiateCB, self.__broadcastCB,
				self.__defaultCB],
			'session-terminate':	[self.__sessionTerminateCB, self.__broadcastAllCB,
				self.__defaultCB],
			'transport-info':	[self.__broadcastCB, self.__defaultCB],
			'transport-replace':	[self.__broadcastCB, self.__transportReplaceCB], #TODO
			'transport-accept':	[self.__defaultCB], #TODO
			'transport-reject':	[self.__defaultCB], #TODO
			'iq-result':		[],
			'iq-error':		[self.__errorCB],
		}

	''' Interaction with user '''
	def approve_session(self):
		''' Called when user accepts session in UI (when we aren't the initiator).
		'''
		self.accept_session()

	def decline_session(self):
		''' Called when user declines session in UI (when we aren't the initiator)
		'''
		reason = xmpp.Node('reason')
		reason.addChild('decline')
		self._session_terminate(reason)

	def approve_content(self, media):
		content = self.get_content(media)
		if content:
			content.accepted = True
			self.on_session_state_changed(content)

	def reject_content(self, media):
		content = self.get_content(media)
		if content:
			if self.state == JingleStates.active:
				self.__content_reject(content)
			content.destroy()
			self.on_session_state_changed()

	def end_session(self):
		''' Called when user stops or cancel session in UI. '''
		reason = xmpp.Node('reason')
		if self.state == JingleStates.active:
			reason.addChild('success')
		else:
			reason.addChild('cancel')
		self._session_terminate(reason)

	''' Middle-level functions to manage contents. Handle local content
	cache and send change notifications. '''
	def get_content(self, media=None):
		if media == 'audio':
			cls = JingleVoIP
		elif media == 'video':
			cls = JingleVideo
		#elif media == None:
		#	cls = JingleContent
		else:
			return None

		for content in self.contents.values():
			if isinstance(content, cls):
				return content

	def add_content(self, name, content, creator='we'):
		''' Add new content to session. If the session is active,
		this will send proper stanza to update session. 
		Creator must be one of ('we', 'peer', 'initiator', 'responder')'''
		assert creator in ('we', 'peer', 'initiator', 'responder')

		if (creator == 'we' and self.weinitiate) or (creator == 'peer' and \
		not self.weinitiate):
			creator = 'initiator'
		elif (creator == 'peer' and self.weinitiate) or (creator == 'we' and \
		not self.weinitiate):
			creator = 'responder'
		content.creator = creator
		content.name = name
		self.contents[(creator, name)] = content

		if (creator == 'initiator') == self.weinitiate:
			# The content is from us, accept it
			content.accepted = True

	def remove_content(self, creator, name):
		''' We do not need this now '''
		#TODO:
		if (creator, name) in self.contents:
			content = self.contents[(creator, name)]
			if len(self.contents) > 1:
				self.__content_remove(content)
			self.contents[(creator, name)].destroy()
		if len(self.contents) == 0:
			self.end_session()

	def modify_content(self, creator, name, *someother):
		''' We do not need this now '''
		pass

	def on_session_state_changed(self, content=None):
		if self.state == JingleStates.ended:
			# Session not yet started, only one action possible: session-initiate
			if self.is_ready() and self.weinitiate:
				self.__session_initiate()
		elif self.state == JingleStates.pending:
			# We can either send a session-accept or a content-add
			if self.is_ready() and not self.weinitiate:
				self.__session_accept()
			elif content and (content.creator == 'initiator') == self.weinitiate:
				self.__content_add(content)
			elif content and self.weinitiate:
				self.__content_accept(content)
		elif self.state == JingleStates.active:
			# We can either send a content-add or a content-accept
			if not content:
				return
			if (content.creator == 'initiator') == self.weinitiate:
				# We initiated this content. It's a pending content-add.
				self.__content_add(content)
			else:
				# The other side created this content, we accept it.
				self.__content_accept(content)

	def is_ready(self):
		''' Returns True when all codecs and candidates are ready
		(for all contents). '''
		return (all((content.is_ready() for content in self.contents.itervalues()))
			and self.accepted)

	''' Middle-level function to do stanza exchange. '''
	def accept_session(self):
		''' Mark the session as accepted. '''
		self.accepted = True
		self.on_session_state_changed()

	def start_session(self):
		''' Mark the session as ready to be started. '''
		self.accepted = True
		self.on_session_state_changed()

	def send_session_info(self):
		pass

	def send_content_accept(self, content):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-accept')
		jingle.addChild(node=content)
		self.connection.connection.send(stanza)

	def send_transport_info(self, content):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('transport-info')
		jingle.addChild(node=content)
		self.connection.connection.send(stanza)

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
			if action not in self.callbacks:
				self.__send_error(stanza, 'bad_request')
				return
			#FIXME: If we aren't initiated and it's not a session-initiate...
			if action != 'session-initiate' and self.state == JingleStates.ended:
				self.__send_error(stanza, 'item-not-found', 'unknown-session')
				return
		else:
			# it's an iq-result (ack) stanza
			action = 'iq-result'

		callables = self.callbacks[action]

		try:
			for callable in callables:
				callable(stanza=stanza, jingle=jingle, error=error, action=action)
		except xmpp.NodeProcessed:
			pass
		except TieBreak:
			self.__send_error(stanza, 'conflict', 'tiebreak')
		except OutOfOrder:
			self.__send_error(stanza, 'unexpected-request', 'out-of-order')#FIXME

	def __defaultCB(self, stanza, jingle, error, action):
		''' Default callback for action stanzas -- simple ack
		and stop processing. '''
		response = stanza.buildReply('result')
		self.connection.connection.send(response)

	def __errorCB(self, stanza, jingle, error, action):
		#FIXME
		text = error.getTagData('text')
		jingle_error = None
		xmpp_error = None
		for child in error.getChildren():
			if child.getNamespace() == xmpp.NS_JINGLE_ERRORS:
				jingle_error = child.getName()
			elif child.getNamespace() == xmpp.NS_STANZAS:
				xmpp_error = child.getName()
		self.__dispatch_error(xmpp_error, jingle_error, text)
		#FIXME: Not sure when we would want to do that...
		if xmpp_error == 'item-not-found':
			self.connection.delete_jingle_session(self.peerjid, self.sid)

	def __transportReplaceCB(self, stanza, jingle, error, action):
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']
			if (creator, name) in self.contents:
				transport_ns = content.getTag('transport').getNamespace()
				if transport_ns == xmpp.JINGLE_ICE_UDP:
					#FIXME: We don't manage anything else than ICE-UDP now...
					#What was the previous transport?!?
					#Anyway, content's transport is not modifiable yet
					pass
				else:
					stanza, jingle = self.__make_jingle('transport-reject')
					content = jingle.setTag('content', attrs={'creator': creator,
						'name': name})
					content.setTag('transport', namespace=transport_ns)
					self.connection.connection.send(stanza)
					raise xmpp.NodeProcessed
			else:
				#FIXME: This ressource is unknown to us, what should we do?
				#For now, reject the transport
				stanza, jingle = self.__make_jingle('transport-reject')
				c = jingle.setTag('content', attrs={'creator': creator,
					'name': name})
				c.setTag('transport', namespace=transport_ns)
				self.connection.connection.send(stanza)
				raise xmpp.NodeProcessed

	def __sessionInfoCB(self, stanza, jingle, error, action):
		#TODO: ringing, active, (un)hold, (un)mute
		payload = jingle.getPayload()
		if len(payload) > 0:
			self.__send_error(stanza, 'feature-not-implemented', 'unsupported-info')
			raise xmpp.NodeProcessed

	def __contentRemoveCB(self, stanza, jingle, error, action):
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']
			if (creator, name) in self.contents:
				content = self.contents[(creator, name)]
				#TODO: this will fail if content is not an RTP content
				self.connection.dispatch('JINGLE_DISCONNECTED',
					(self.peerjid, self.sid, content.media, 'removed'))
				content.destroy()
		if len(self.contents) == 0:
			reason = xmpp.Node('reason')
			reason.setTag('success')
			self._session_terminate(reason)

	def __sessionAcceptCB(self, stanza, jingle, error, action):
		if self.state != JingleStates.pending: #FIXME
			raise OutOfOrder
		self.state = JingleStates.active

	def __contentAcceptCB(self, stanza, jingle, error, action):
		''' Called when we get content-accept stanza or equivalent one
		(like session-accept).'''
		# check which contents are accepted
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']#TODO...

	def __contentAddCB(self, stanza, jingle, error, action):
		if self.state == JingleStates.ended:
			raise OutOfOrder

		parse_result = self.__parse_contents(jingle)
		contents = parse_result[2]
		rejected_contents = parse_result[3]

		for name, creator in rejected_contents:
			#TODO:
			content = JingleContent()
			self.add_content(name, content, creator)
			self.__content_reject(content)
			self.contents[(content.creator, content.name)].destroy()

		self.connection.dispatch('JINGLE_INCOMING', (self.peerjid, self.sid,
			contents))

	def __sessionInitiateCB(self, stanza, jingle, error, action):
		''' We got a jingle session request from other entity,
		therefore we are the receiver... Unpack the data,
		inform the user. '''

		if self.state != JingleStates.ended:
			raise OutOfOrder

		self.initiator = jingle['initiator']
		self.responder = self.ourjid
		self.peerjid = self.initiator
		self.accepted = False	# user did not accept this session yet

		# TODO: If the initiator is unknown to the receiver (e.g., via presence
		# subscription) and the receiver has a policy of not communicating via
		# Jingle with unknown entities, it SHOULD return a <service-unavailable/>
		# error.

		# Lets check what kind of jingle session does the peer want
		contents_ok, transports_ok, contents, pouet = self.__parse_contents(jingle)

		# If there's no content we understand...
		if not contents_ok:
			# TODO: http://xmpp.org/extensions/xep-0166.html#session-terminate
			reason = xmpp.Node('reason')
			reason.setTag('unsupported-applications')
			self.__defaultCB(stanza, jingle, error, action)
			self._session_terminate(reason)
			raise xmpp.NodeProcessed

		if not transports_ok:
			# TODO: http://xmpp.org/extensions/xep-0166.html#session-terminate
			reason = xmpp.Node('reason')
			reason.setTag('unsupported-transports')
			self.__defaultCB(stanza, jingle, error, action)
			self._session_terminate(reason)
			raise xmpp.NodeProcessed

		self.state = JingleStates.pending

		# Send event about starting a session
		self.connection.dispatch('JINGLE_INCOMING', (self.peerjid, self.sid,
			contents))

	def __broadcastCB(self, stanza, jingle, error, action):
		''' Broadcast the stanza contents to proper content handlers. '''
		for content in jingle.iterTags('content'):
			name = content['name']
			creator = content['creator']
			cn = self.contents[(creator, name)]
			cn.stanzaCB(stanza, content, error, action)

	def __sessionTerminateCB(self, stanza, jingle, error, action):
		self.connection.delete_jingle_session(self.peerjid, self.sid)
		reason, text = self.__reason_from_stanza(jingle)
		if reason not in ('success', 'cancel', 'decline'):
			self.__dispatch_error(reason, reason, text)
		if text:
			text = '%s (%s)' % (reason, text)
		else:
			text = reason#TODO
		self.connection.dispatch('JINGLE_DISCONNECTED',
			(self.peerjid, self.sid, None, text))

	def __broadcastAllCB(self, stanza, jingle, error, action):
		''' Broadcast the stanza to all content handlers. '''
		for content in self.contents.itervalues():
			content.stanzaCB(stanza, None, error, action)

	''' Internal methods. '''
	def __parse_contents(self, jingle):
		#TODO: Needs some reworking
		contents = []
		contents_rejected = []
		contents_ok = False
		transports_ok = False

		for element in jingle.iterTags('content'):
			desc = element.getTag('description')
			desc_ns = desc.getNamespace()
			tran_ns = element.getTag('transport').getNamespace()
			if desc_ns == xmpp.NS_JINGLE_RTP and desc['media'] in ('audio', 'video'):
				contents_ok = True
				#TODO: Everything here should be moved somewhere else
				if tran_ns == xmpp.NS_JINGLE_ICE_UDP:
					if desc['media'] == 'audio':
						self.add_content(element['name'], JingleVoIP(self), 'peer')
					else:
						self.add_content(element['name'], JingleVideo(self), 'peer')
					contents.append((desc['media'],))
					transports_ok = True
				else:
					contents_rejected.append((element['name'], 'peer'))
			else:
				contents_rejected.append((element['name'], 'peer'))

		return (contents_ok, transports_ok, contents, contents_rejected)

	def __dispatch_error(self, error, jingle_error=None, text=None):
		if jingle_error:
			error = jingle_error
		if text:
			text = '%s (%s)' % (error, text)
		else:
			text = error
		self.connection.dispatch('JINGLE_ERROR', (self.peerjid, self.sid, text))

	def __reason_from_stanza(self, stanza):
		reason = 'success'
		reasons = ['success', 'busy', 'cancel', 'connectivity-error',
			'decline', 'expired', 'failed-application', 'failed-transport',
			'general-error', 'gone', 'incompatible-parameters', 'media-error',
			'security-error', 'timeout', 'unsupported-applications',
			'unsupported-transports']
		tag = stanza.getTag('reason')
		if tag:
			text = tag.getTagData('text')
			for r in reasons:
				if tag.getTag(r):
					reason = r
					break
		return (reason, text)

	''' Methods that make/send proper pieces of XML. They check if the session
	is in appropriate state. '''
	def __make_jingle(self, action):
		stanza = xmpp.Iq(typ='set', to=xmpp.JID(self.peerjid))
		attrs = {'action': action,
			'sid': self.sid}
		if action == 'session-initiate':
			attrs['initiator'] = self.initiator
		elif action == 'session-accept':
			attrs['responder'] = self.responder
		jingle = stanza.addChild('jingle', attrs=attrs, namespace=xmpp.NS_JINGLE)
		return stanza, jingle

	def __send_error(self, stanza, error, jingle_error=None, text=None):
		err = xmpp.Error(stanza, error)
		err.setNamespace(xmpp.NS_STANZAS)
		if jingle_error:
			err.setTag(jingle_error, namespace=xmpp.NS_JINGLE_ERRORS)
		if text:
			err.setTagData('text', text)
		self.connection.connection.send(err)
		self.__dispatch_error(error, jingle_error, text)

	def __append_content(self, jingle, content):
		''' Append <content/> element to <jingle/> element,
		with (full=True) or without (full=False) <content/>
		children. '''
		jingle.addChild('content',
			attrs={'name': content.name, 'creator': content.creator})

	def __append_contents(self, jingle):
		''' Append all <content/> elements to <jingle/>.'''
		# TODO: integrate with __appendContent?
		# TODO: parameters 'name', 'content'?
		for content in self.contents.values():
			self.__append_content(jingle, content)

	def __session_initiate(self):
		assert self.state == JingleStates.ended
		stanza, jingle = self.__make_jingle('session-initiate')
		self.__append_contents(jingle)
		self.__broadcastCB(stanza, jingle, None, 'session-initiate-sent')
		self.connection.connection.send(stanza)
		self.state = JingleStates.pending

	def __session_accept(self):
		assert self.state == JingleStates.pending
		stanza, jingle = self.__make_jingle('session-accept')
		self.__append_contents(jingle)
		self.__broadcastCB(stanza, jingle, None, 'session-accept-sent')
		self.connection.connection.send(stanza)
		self.state = JingleStates.active

	def __session_info(self, payload=None):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('session-info')
		if payload:
			jingle.addChild(node=payload)
		self.connection.connection.send(stanza)

	def _session_terminate(self, reason=None):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('session-terminate')
		if reason is not None:
			jingle.addChild(node=reason)
		self.__broadcastAllCB(stanza, jingle, None, 'session-terminate-sent')
		self.connection.connection.send(stanza)
		reason, text = self.__reason_from_stanza(jingle)
		if reason not in ('success', 'cancel', 'decline'):
			self.__dispatch_error(reason, reason, text)
		if text:
			text = '%s (%s)' % (reason, text)
		else:
			text = reason
		self.connection.delete_jingle_session(self.peerjid, self.sid)
		self.connection.dispatch('JINGLE_DISCONNECTED',
			(self.peerjid, self.sid, None, text))

	def __content_add(self, content):
		#TODO: test
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-add')
		self.__append_content(jingle, content)
		self.__broadcastCB(stanza, jingle, None, 'content-add-sent')
		self.connection.connection.send(stanza)

	def __content_accept(self, content):
		#TODO: test
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-accept')
		self.__append_content(jingle, content)
		self.__broadcastCB(stanza, jingle, None, 'content-accept-sent')
		self.connection.connection.send(stanza)

	def __content_reject(self, content):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-reject')
		self.__append_content(jingle, content)
		self.connection.connection.send(stanza)
		#TODO: this will fail if content is not an RTP content
		self.connection.dispatch('JINGLE_DISCONNECTED',
			(self.peerjid, self.sid, content.media, 'rejected'))

	def __content_modify(self):
		assert self.state != JingleStates.ended

	def __content_remove(self, content):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-remove')
		self.__append_content(jingle, content)
		self.connection.connection.send(stanza)
		#TODO: this will fail if content is not an RTP content
		self.connection.dispatch('JINGLE_DISCONNECTED',
			(self.peerjid, self.sid, content.media, 'removed'))

	def content_negociated(self, media):
		self.connection.dispatch('JINGLE_CONNECTED', (self.peerjid, self.sid,
			media))

#TODO:
#class JingleTransport(object):
#	''' An abstraction of a transport in Jingle sessions. '''
#	def __init__(self):
#		pass


class JingleContent(object):
	''' An abstraction of content in Jingle sessions. '''
	def __init__(self, session, node=None):
		self.session = session
		# will be filled by JingleSession.add_content()
		# don't uncomment these lines, we will catch more buggy code then
		# (a JingleContent not added to session shouldn't send anything)
		#self.creator = None
		#self.name = None
		self.accepted = False
		self.sent = False
		self.candidates = [] # Local transport candidates
		self.remote_candidates = [] # Remote transport candidates

		self.senders = 'both' #FIXME
		self.allow_sending = True # Used for stream direction, attribute 'senders'

		self.callbacks = {
			# these are called when *we* get stanzas
			'content-accept': [self.__transportInfoCB],
			'content-add': [self.__transportInfoCB],
			'content-modify': [],
			'content-reject': [],
			'content-remove': [],
			'description-info': [],
			'security-info': [],
			'session-accept': [self.__transportInfoCB],
			'session-info': [],
			'session-initiate': [self.__transportInfoCB],
			'session-terminate': [],
			'transport-info': [self.__transportInfoCB],
			'transport-replace': [],
			'transport-accept': [],
			'transport-reject': [],
			'iq-result': [],
			'iq-error': [],
			# these are called when *we* sent these stanzas
			'content-accept-sent': [self.__fillJingleStanza],
			'content-add-sent': [self.__fillJingleStanza],
			'session-initiate-sent': [self.__fillJingleStanza],
			'session-accept-sent': [self.__fillJingleStanza],
			'session-terminate-sent': [],
		}

	def is_ready(self):
		#print '[%s] %s, %s' % (self.media, self.candidates_ready,
		#	self.p2psession.get_property('codecs-ready'))
		return (self.accepted and self.candidates_ready and not self.sent
			and self.p2psession.get_property('codecs-ready'))

	def stanzaCB(self, stanza, content, error, action):
		''' Called when something related to our content was sent by peer. '''
		if action in self.callbacks:
			for callback in self.callbacks[action]:
				callback(stanza, content, error, action)

	def __transportInfoCB(self, stanza, content, error, action):
		''' Got a new transport candidate. '''
		candidates = []
		transport = content.getTag('transport')
		for candidate in transport.iterTags('candidate'):
			cand = farsight.Candidate()
			cand.component_id = int(candidate['component'])
			cand.ip = str(candidate['ip'])
			cand.port = int(candidate['port'])
			cand.foundation = str(candidate['foundation'])
			#cand.type = farsight.CANDIDATE_TYPE_LOCAL
			cand.priority = int(candidate['priority'])

			if candidate['protocol'] == 'udp':
				cand.proto = farsight.NETWORK_PROTOCOL_UDP
			else:
				# we actually don't handle properly different tcp options in jingle
				cand.proto = farsight.NETWORK_PROTOCOL_TCP

			cand.username = str(transport['ufrag'])
			cand.password = str(transport['pwd'])

			#FIXME: huh?
			types = {'host': farsight.CANDIDATE_TYPE_HOST,
						'srflx': farsight.CANDIDATE_TYPE_SRFLX,
						'prflx': farsight.CANDIDATE_TYPE_PRFLX,
						'relay': farsight.CANDIDATE_TYPE_RELAY,
						'multicast': farsight.CANDIDATE_TYPE_MULTICAST}
			if 'type' in candidate and candidate['type'] in types:
				cand.type = types[candidate['type']]
			else:
				print 'Unknown type %s', candidate['type']
			candidates.append(cand)
		#FIXME: connectivity should not be etablished yet
		# Instead, it should be etablished after session-accept!
		if len(candidates) > 0:
			if self.sent:
				self.p2pstream.set_remote_candidates(candidates)
			else:
				self.remote_candidates.extend(candidates)
			#self.p2pstream.set_remote_candidates(candidates)
			#print self.media, self.creator, self.name, candidates

	def __content(self, payload=[]):
		''' Build a XML content-wrapper for our data. '''
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator},
			payload=payload)

	def __candidate(self, candidate):
		types = {farsight.CANDIDATE_TYPE_HOST: 'host',
			farsight.CANDIDATE_TYPE_SRFLX: 'srflx',
			farsight.CANDIDATE_TYPE_PRFLX: 'prflx',
			farsight.CANDIDATE_TYPE_RELAY: 'relay',
			farsight.CANDIDATE_TYPE_MULTICAST: 'multicast'}
		attrs = {
			'component': candidate.component_id,
			'foundation': '1', # hack
			'generation': '0',
			'ip': candidate.ip,
			'network': '0',
			'port': candidate.port,
			'priority': int(candidate.priority), # hack
		}
		if candidate.type in types:
			attrs['type'] = types[candidate.type]
		if candidate.proto == farsight.NETWORK_PROTOCOL_UDP:
			attrs['protocol'] = 'udp'
		else:
			# we actually don't handle properly different tcp options in jingle
			attrs['protocol'] = 'tcp'
		return xmpp.Node('candidate', attrs=attrs)

	def iter_candidates(self):
		for candidate in self.candidates:
			yield self.__candidate(candidate)

	def send_candidate(self, candidate):
		content = self.__content()
		transport = content.addChild(xmpp.NS_JINGLE_ICE_UDP + ' transport')

		if candidate.username and candidate.password:
			transport['ufrag'] = candidate.username
			transport['pwd'] = candidate.password

		transport.addChild(node=self.__candidate(candidate))
		self.session.send_transport_info(content)

	def __fillJingleStanza(self, stanza, content, error, action):
		''' Add our things to session-initiate stanza. '''
		self._fillContent(content)

		self.sent = True

		if self.candidates and self.candidates[0].username and \
		self.candidates[0].password:
			attrs = {'ufrag': self.candidates[0].username,
				'pwd': self.candidates[0].password}
		else:
			attrs = {}
		content.addChild(xmpp.NS_JINGLE_ICE_UDP + ' transport', attrs=attrs,
			payload=self.iter_candidates())

	def destroy(self):
		self.callbacks = None
		del self.session.contents[(self.creator, self.name)]


class JingleRTPContent(JingleContent):
	def __init__(self, session, media, node=None):
		JingleContent.__init__(self, session, node)
		self.media = media
		self.farsight_media = {'audio': farsight.MEDIA_TYPE_AUDIO,
								'video': farsight.MEDIA_TYPE_VIDEO}[media]
		self.got_codecs = False

		self.candidates_ready = False # True when local candidates are prepared

		self.callbacks['session-initiate'] += [self.__getRemoteCodecsCB]
		self.callbacks['content-add'] += [self.__getRemoteCodecsCB]
		self.callbacks['content-accept'] += [self.__getRemoteCodecsCB,
			self.__contentAcceptCB]
		self.callbacks['session-accept'] += [self.__getRemoteCodecsCB,
			self.__contentAcceptCB]
		self.callbacks['session-accept-sent'] += [self.__contentAcceptCB]
		self.callbacks['content-accept-sent'] += [self.__contentAcceptCB]
		self.callbacks['session-terminate'] += [self.__stop]
		self.callbacks['session-terminate-sent'] += [self.__stop]

	def setup_stream(self):
		# pipeline and bus
		self.pipeline = gst.Pipeline()
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self._on_gst_message)

		# conference
		self.conference = gst.element_factory_make('fsrtpconference')
		self.conference.set_property("sdes-cname", self.session.ourjid)
		self.pipeline.add(self.conference)
		self.funnel = None

		self.p2psession = self.conference.new_session(self.farsight_media)

		participant = self.conference.new_participant(self.session.peerjid)
		#FIXME: Consider a workaround, here... 
		# pidgin and telepathy-gabble don't follow the XEP, and it won't work
		# due to bad controlling-mode
		params = {'controlling-mode': self.session.weinitiate,# 'debug': False}
			'stun-ip': '69.0.208.27', 'debug': False}

		self.p2pstream = self.p2psession.new_stream(participant,
			farsight.DIRECTION_RECV, 'nice', params)

	def _fillContent(self, content):
		content.addChild(xmpp.NS_JINGLE_RTP + ' description',
			attrs={'media': self.media}, payload=self.iter_codecs())

	def _setup_funnel(self):
		self.funnel = gst.element_factory_make('fsfunnel')
		self.pipeline.add(self.funnel)
		self.funnel.set_state(gst.STATE_PLAYING)
		self.sink.set_state(gst.STATE_PLAYING)
		self.funnel.link(self.sink)

	def _on_src_pad_added(self, stream, pad, codec):
		if not self.funnel:
			self._setup_funnel()
		pad.link(self.funnel.get_pad('sink%d'))

	def _on_gst_message(self, bus, message):
		if message.type == gst.MESSAGE_ELEMENT:
			name = message.structure.get_name()
			if name == 'farsight-new-active-candidate-pair':
				pass
			elif name == 'farsight-recv-codecs-changed':
				pass
			elif name == 'farsight-codecs-changed':
				if self.is_ready():
					self.session.on_session_state_changed(self)
				#TODO: description-info
			elif name == 'farsight-local-candidates-prepared':
				self.candidates_ready = True
				if self.is_ready():
					self.session.on_session_state_changed(self)
			elif name == 'farsight-new-local-candidate':
				candidate = message.structure['candidate']
				self.candidates.append(candidate)
				if self.candidates_ready:
					#FIXME: Is this case even possible?
					self.send_candidate(candidate)
			elif name == 'farsight-component-state-changed':
				state = message.structure['state']
				print message.structure['component'], state
				if state == farsight.STREAM_STATE_FAILED:
					reason = xmpp.Node('reason')
					reason.setTag('failed-transport')
					self.session._session_terminate(reason)
			elif name == 'farsight-error':
				print 'Farsight error #%d!' % message.structure['error-no']
				print 'Message: %s' % message.structure['error-msg']
				print 'Debug: %s' % message.structure['debug-msg']
			else:
				print name

	def __contentAcceptCB(self, stanza, content, error, action):
		if self.accepted:
			if len(self.remote_candidates) > 0:
				self.p2pstream.set_remote_candidates(self.remote_candidates)
				self.remote_candidates = []
			#TODO: farsight.DIRECTION_BOTH only if senders='both'
			self.p2pstream.set_property('direction', farsight.DIRECTION_BOTH)
			self.session.content_negociated(self.media)

	def __getRemoteCodecsCB(self, stanza, content, error, action):
		''' Get peer codecs from what we get from peer. '''
		if self.got_codecs:
			return

		codecs = []
		for codec in content.getTag('description').iterTags('payload-type'):
			c = farsight.Codec(int(codec['id']), codec['name'],
				self.farsight_media, int(codec['clockrate']))
			if 'channels' in codec:
				c.channels = int(codec['channels'])
			else:
				c.channels = 1
			c.optional_params = [(str(p['name']), str(p['value'])) for p in \
				codec.iterTags('parameter')]
			codecs.append(c)

		if len(codecs) > 0:
			#FIXME: Handle this case:
			# glib.GError: There was no intersection between the remote codecs and
			# the local ones
			self.p2pstream.set_remote_codecs(codecs)
			self.got_codecs = True

	def iter_codecs(self):
		codecs = self.p2psession.get_property('codecs')
		for codec in codecs:
			attrs = {'name': codec.encoding_name,
				'id': codec.id,
				'channels': codec.channels}
			if codec.clock_rate:
				attrs['clockrate'] = codec.clock_rate
			if codec.optional_params:
				payload = (xmpp.Node('parameter', {'name': name, 'value': value})
					for name, value in codec.optional_params)
			else:	payload = ()
			yield xmpp.Node('payload-type', attrs, payload)

	def __stop(self, *things):
		self.pipeline.set_state(gst.STATE_NULL)

	def __del__(self):
		self.__stop()

	def destroy(self):
		JingleContent.destroy(self)
		self.p2pstream.disconnect_by_func(self._on_src_pad_added)
		self.pipeline.get_bus().disconnect_by_func(self._on_gst_message)


class JingleVoIP(JingleRTPContent):
	''' Jingle VoIP sessions consist of audio content transported
	over an ICE UDP protocol. '''
	def __init__(self, session, node=None):
		JingleRTPContent.__init__(self, session, 'audio', node)
		self.setup_stream()


	''' Things to control the gstreamer's pipeline '''
	def setup_stream(self):
		JingleRTPContent.setup_stream(self)

		# Configure SPEEX
		# Workaround for psi (not needed since rev
		# 147aedcea39b43402fe64c533d1866a25449888a):
		#  place 16kHz before 8kHz, as buggy psi versions will take in
		#  account only the first codec

		codecs = [farsight.Codec(farsight.CODEC_ID_ANY, 'SPEEX',
			farsight.MEDIA_TYPE_AUDIO, 16000),
			farsight.Codec(farsight.CODEC_ID_ANY, 'SPEEX',
			farsight.MEDIA_TYPE_AUDIO, 8000)]
		self.p2psession.set_codec_preferences(codecs)

		# the local parts
		# TODO: use gconfaudiosink?
		# sink = get_first_gst_element(['alsasink', 'osssink', 'autoaudiosink'])
		self.sink = gst.element_factory_make('alsasink')
		self.sink.set_property('sync', False)
		#sink.set_property('latency-time', 20000)
		#sink.set_property('buffer-time', 80000)

		# TODO: use gconfaudiosrc?
		src_mic = gst.element_factory_make('alsasrc')
		src_mic.set_property('blocksize', 320)

		self.mic_volume = gst.element_factory_make('volume')
		self.mic_volume.set_property('volume', 1)

		# link gst elements
		self.pipeline.add(self.sink, src_mic, self.mic_volume)
		src_mic.link(self.mic_volume)

		self.mic_volume.get_pad('src').link(self.p2psession.get_property(
			'sink-pad'))
		self.p2pstream.connect('src-pad-added', self._on_src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


class JingleVideo(JingleRTPContent):
	def __init__(self, session, node=None):
		JingleRTPContent.__init__(self, session, 'video', node)
		self.setup_stream()

	''' Things to control the gstreamer's pipeline '''
	def setup_stream(self):
		#TODO: Everything is not working properly:
		# sometimes, one window won't show up,
		# sometimes it'll freeze...
		JingleRTPContent.setup_stream(self)
		# the local parts
		src_vid = gst.element_factory_make('videotestsrc')
		src_vid.set_property('is-live', True)
		videoscale = gst.element_factory_make('videoscale')
		caps = gst.element_factory_make('capsfilter')
		caps.set_property('caps', gst.caps_from_string('video/x-raw-yuv, width=320, height=240'))
		colorspace = gst.element_factory_make('ffmpegcolorspace')

		self.pipeline.add(src_vid, videoscale, caps, colorspace)
		gst.element_link_many(src_vid, videoscale, caps, colorspace)

		self.sink = gst.element_factory_make('xvimagesink')
		self.pipeline.add(self.sink)

		colorspace.get_pad('src').link(self.p2psession.get_property('sink-pad'))
		self.p2pstream.connect('src-pad-added', self._on_src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


class ConnectionJingle(object):
	''' This object depends on that it is a part of Connection class. '''
	def __init__(self):
		# dictionary: (jid, sessionid) => JingleSession object
		self.__sessions = {}

		# dictionary: (jid, iq stanza id) => JingleSession object,
		# one time callbacks
		self.__iq_responses = {}

	def add_jingle(self, jingle):
		''' Add a jingle session to a jingle stanza dispatcher
		jingle - a JingleSession object.
		'''
		self.__sessions[(jingle.peerjid, jingle.sid)] = jingle

	def delete_jingle_session(self, peerjid, sid):
		''' Remove a jingle session from a jingle stanza dispatcher '''
		key = (peerjid, sid)
		if key in self.__sessions:
			#FIXME: Move this elsewhere?
			for content in self.__sessions[key].contents.values():
				content.destroy()
			self.__sessions[key].callbacks = []
			del self.__sessions[key]

	def _JingleCB(self, con, stanza):
		''' The jingle stanza dispatcher.
		Route jingle stanza to proper JingleSession object,
		or create one if it is a new session.
		TODO: Also check if the stanza isn't an error stanza, if so
		route it adequatelly.'''

		# get data
		jid = helpers.get_full_jid_from_iq(stanza)
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
			#TODO: tie-breaking and other things...
			newjingle = JingleSession(con=self, weinitiate=False, jid=jid, sid=sid)
			self.add_jingle(newjingle)

		# we already have such session in dispatcher...
		self.__sessions[(jid, sid)].stanzaCB(stanza)

		raise xmpp.NodeProcessed

	def startVoIP(self, jid):
		if self.get_jingle_session(jid, media='audio'):
			return self.get_jingle_session(jid, media='audio').sid
		jingle = self.get_jingle_session(jid, media='video')
		if jingle:
			jingle.add_content('voice', JingleVoIP(jingle))
		else:
			jingle = JingleSession(self, weinitiate=True, jid=jid)
			self.add_jingle(jingle)
			jingle.add_content('voice', JingleVoIP(jingle))
			jingle.start_session()
		return jingle.sid

	def startVideoIP(self, jid):
		if self.get_jingle_session(jid, media='video'):
			return self.get_jingle_session(jid, media='video').sid
		jingle = self.get_jingle_session(jid, media='audio')
		if jingle:
			jingle.add_content('video', JingleVideo(jingle))
		else:
			jingle = JingleSession(self, weinitiate=True, jid=jid)
			self.add_jingle(jingle)
			jingle.add_content('video', JingleVideo(jingle))
			jingle.start_session()
		return jingle.sid

	def get_jingle_session(self, jid, sid=None, media=None):
		if sid:
			if (jid, sid) in self.__sessions:
				return self.__sessions[(jid, sid)]
			else:
				return None
		elif media:
			if media not in ('audio', 'video'):
				return None
			for session in self.__sessions.values():
				if session.peerjid == jid and session.get_content(media):
					return session

		return None
