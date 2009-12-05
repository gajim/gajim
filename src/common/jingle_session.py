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

"""
Handles Jingle sessions (XEP 0166)
"""

#TODO:
# * 'senders' attribute of 'content' element
# * security preconditions
# * actions:
#   - content-modify
#   - session-info
#   - security-info
#   - transport-accept, transport-reject
#   - Tie-breaking
# * timeout

import gajim #Get rid of that?
import xmpp
from jingle_transport import get_jingle_transport
from jingle_content import get_jingle_content, JingleContentSetupException

# FIXME: Move it to JingleSession.States?
class JingleStates(object):
	"""
	States in which jingle session may exist
	"""
	ended = 0
	pending = 1
	active = 2

class OutOfOrder(Exception):
	"""
	Exception that should be raised when an action is received when in the wrong
	state
	"""

class TieBreak(Exception):
	"""
	Exception that should be raised in case of a tie, when we overrule the other
	action
	"""

class JingleSession(object):
	"""
	This represents one jingle session, that is, one or more content types
	negotiated between an initiator and a responder.
	"""

	def __init__(self, con, weinitiate, jid, sid=None):
		"""
		con -- connection object,
		weinitiate -- boolean, are we the initiator?
		jid - jid of the other entity
		"""
		self.contents = {} # negotiated contents
		self.connection = con # connection to use
		# our full jid
		#FIXME: Get rid of gajim here?
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
			'content-accept':	[self.__on_content_accept, self.__broadcast,
				self.__ack],
			'content-add':		[self.__on_content_add, self.__broadcast,
				self.__ack], #TODO
			'content-modify':	[self.__ack], #TODO
			'content-reject':	[self.__ack, self.__on_content_remove], #TODO
			'content-remove':	[self.__ack, self.__on_content_remove],
			'description-info':	[self.__broadcast, self.__ack], #TODO
			'security-info':	[self.__ack], #TODO
			'session-accept':	[self.__on_session_accept, self.__on_content_accept,
				self.__broadcast, self.__ack],
			'session-info':		[self.__on_session_info, self.__broadcast, self.__ack],
			'session-initiate':	[self.__on_session_initiate, self.__broadcast,
				self.__ack],
			'session-terminate':	[self.__on_session_terminate, self.__broadcast_all,
				self.__ack],
			'transport-info':	[self.__broadcast, self.__ack],
			'transport-replace':	[self.__broadcast, self.__on_transport_replace], #TODO
			'transport-accept':	[self.__ack], #TODO
			'transport-reject':	[self.__ack], #TODO
			'iq-result':		[],
			'iq-error':		[self.__on_error],
		}

	def approve_session(self):
		"""
		Called when user accepts session in UI (when we aren't the initiator)
		"""
		self.accept_session()

	def decline_session(self):
		"""
		Called when user declines session in UI (when we aren't the initiator)
		"""
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
		"""
		Called when user stops or cancel session in UI
		"""
		reason = xmpp.Node('reason')
		if self.state == JingleStates.active:
			reason.addChild('success')
		else:
			reason.addChild('cancel')
		self._session_terminate(reason)

	def get_content(self, media=None):
		if media is None:
			return

		for content in self.contents.values():
			if content.media == media:
				return content

	def add_content(self, name, content, creator='we'):
		"""
		Add new content to session. If the session is active, this will send
		proper stanza to update session

		Creator must be one of ('we', 'peer', 'initiator', 'responder')
		"""
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
		"""
		We do not need this now
		"""
		#TODO:
		if (creator, name) in self.contents:
			content = self.contents[(creator, name)]
			if len(self.contents) > 1:
				self.__content_remove(content)
			self.contents[(creator, name)].destroy()
		if len(self.contents) == 0:
			self.end_session()

	def modify_content(self, creator, name, *someother):
		"""
		We do not need this now
		"""
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
		"""
		Return True when all codecs and candidates are ready (for all contents)
		"""
		return (all((content.is_ready() for content in self.contents.itervalues()))
			and self.accepted)

	def accept_session(self):
		"""
		Mark the session as accepted
		"""
		self.accepted = True
		self.on_session_state_changed()

	def start_session(self):
		"""
		Mark the session as ready to be started
		"""
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

	def on_stanza(self, stanza):
		"""
		A callback for ConnectionJingle. It gets stanza, then tries to send it to
		all internally registered callbacks. First one to raise
		xmpp.NodeProcessed breaks function
		"""
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
			# FIXME: If we aren't initiated and it's not a session-initiate...
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
			# FIXME
			self.__send_error(stanza, 'unexpected-request', 'out-of-order')

	def __ack(self, stanza, jingle, error, action):
		"""
		Default callback for action stanzas -- simple ack and stop processing
		"""
		response = stanza.buildReply('result')
		self.connection.connection.send(response)

	def __on_error(self, stanza, jingle, error, action):
		# FIXME
		text = error.getTagData('text')
		jingle_error = None
		xmpp_error = None
		for child in error.getChildren():
			if child.getNamespace() == xmpp.NS_JINGLE_ERRORS:
				jingle_error = child.getName()
			elif child.getNamespace() == xmpp.NS_STANZAS:
				xmpp_error = child.getName()
		self.__dispatch_error(xmpp_error, jingle_error, text)
		# FIXME: Not sure when we would want to do that...
		if xmpp_error == 'item-not-found':
			self.connection.delete_jingle_session(self.peerjid, self.sid)

	def __on_transport_replace(self, stanza, jingle, error, action):
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']
			if (creator, name) in self.contents:
				transport_ns = content.getTag('transport').getNamespace()
				if transport_ns == xmpp.JINGLE_ICE_UDP:
					# FIXME: We don't manage anything else than ICE-UDP now...
					# What was the previous transport?!?
					# Anyway, content's transport is not modifiable yet
					pass
				else:
					stanza, jingle = self.__make_jingle('transport-reject')
					content = jingle.setTag('content', attrs={'creator': creator,
						'name': name})
					content.setTag('transport', namespace=transport_ns)
					self.connection.connection.send(stanza)
					raise xmpp.NodeProcessed
			else:
				# FIXME: This ressource is unknown to us, what should we do?
				# For now, reject the transport
				stanza, jingle = self.__make_jingle('transport-reject')
				c = jingle.setTag('content', attrs={'creator': creator,
					'name': name})
				c.setTag('transport', namespace=transport_ns)
				self.connection.connection.send(stanza)
				raise xmpp.NodeProcessed

	def __on_session_info(self, stanza, jingle, error, action):
		# TODO: ringing, active, (un)hold, (un)mute
		payload = jingle.getPayload()
		if payload:
			self.__send_error(stanza, 'feature-not-implemented', 'unsupported-info')
			raise xmpp.NodeProcessed

	def __on_content_remove(self, stanza, jingle, error, action):
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']
			if (creator, name) in self.contents:
				content = self.contents[(creator, name)]
				# TODO: this will fail if content is not an RTP content
				self.connection.dispatch('JINGLE_DISCONNECTED',
					(self.peerjid, self.sid, content.media, 'removed'))
				content.destroy()
		if not self.contents:
			reason = xmpp.Node('reason')
			reason.setTag('success')
			self._session_terminate(reason)

	def __on_session_accept(self, stanza, jingle, error, action):
		# FIXME
		if self.state != JingleStates.pending:
			raise OutOfOrder
		self.state = JingleStates.active

	def __on_content_accept(self, stanza, jingle, error, action):
		"""
		Called when we get content-accept stanza or equivalent one (like
		session-accept)
		"""
		# check which contents are accepted
		for content in jingle.iterTags('content'):
			creator = content['creator']
			# TODO
			name = content['name']

	def __on_content_add(self, stanza, jingle, error, action):
		if self.state == JingleStates.ended:
			raise OutOfOrder

		parse_result = self.__parse_contents(jingle)
		contents = parse_result[0]
		rejected_contents = parse_result[1]

		for name, creator in rejected_contents:
			# TODO
			content = JingleContent()
			self.add_content(name, content, creator)
			self.__content_reject(content)
			self.contents[(content.creator, content.name)].destroy()

		self.connection.dispatch('JINGLE_INCOMING', (self.peerjid, self.sid,
			contents))

	def __on_session_initiate(self, stanza, jingle, error, action):
		"""
		We got a jingle session request from other entity, therefore we are the
		receiver... Unpack the data, inform the user
		"""
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
		contents, contents_rejected, reason = self.__parse_contents(jingle)

		# If there's no content we understand...
		if not contents:
			# TODO: http://xmpp.org/extensions/xep-0166.html#session-terminate
			reason = xmpp.Node('reason')
			reason.setTag(reason)
			self.__ack(stanza, jingle, error, action)
			self._session_terminate(reason)
			raise xmpp.NodeProcessed

		self.state = JingleStates.pending

		# Send event about starting a session
		self.connection.dispatch('JINGLE_INCOMING', (self.peerjid, self.sid,
			contents))

	def __broadcast(self, stanza, jingle, error, action):
		"""
		Broadcast the stanza contents to proper content handlers
		"""
		for content in jingle.iterTags('content'):
			name = content['name']
			creator = content['creator']
			cn = self.contents[(creator, name)]
			cn.on_stanza(stanza, content, error, action)

	def __on_session_terminate(self, stanza, jingle, error, action):
		self.connection.delete_jingle_session(self.peerjid, self.sid)
		reason, text = self.__reason_from_stanza(jingle)
		if reason not in ('success', 'cancel', 'decline'):
			self.__dispatch_error(reason, reason, text)
		if text:
			text = '%s (%s)' % (reason, text)
		else:
			# TODO
			text = reason
		self.connection.dispatch('JINGLE_DISCONNECTED',
			(self.peerjid, self.sid, None, text))

	def __broadcast_all(self, stanza, jingle, error, action):
		"""
		Broadcast the stanza to all content handlers
		"""
		for content in self.contents.itervalues():
			content.on_stanza(stanza, None, error, action)

	def __parse_contents(self, jingle):
		# TODO: Needs some reworking
		contents = []
		contents_rejected = []
		reasons = set()

		for element in jingle.iterTags('content'):
			transport = get_jingle_transport(element.getTag('transport'))
			content_type = get_jingle_content(element.getTag('description'))
			if content_type:
				try:
					if transport:
						content = content_type(self, transport)
						self.add_content(element['name'],
							content, 'peer')
						contents.append((content.media,))
					else:
						reasons.add('unsupported-transports')
						contents_rejected.append((element['name'], 'peer'))
				except JingleContentSetupException:
					reasons.add('failed-application')
			else:
				contents_rejected.append((element['name'], 'peer'))
				failed.add('unsupported-applications')

		failure_reason = None

		# Store the first reason of failure
		for reason in ('failed-application', 'unsupported-transports',
			'unsupported-applications'):
			if reason in reasons:
				failure_reason = reason
				break

		return (contents, contents_rejected, failure_reason)

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
		"""
		Append <content/> element to <jingle/> element, with (full=True) or
		without (full=False) <content/> children
		"""
		jingle.addChild('content',
			attrs={'name': content.name, 'creator': content.creator})

	def __append_contents(self, jingle):
		"""
		Append all <content/> elements to <jingle/>
		"""
		# TODO: integrate with __appendContent?
		# TODO: parameters 'name', 'content'?
		for content in self.contents.values():
			self.__append_content(jingle, content)

	def __session_initiate(self):
		assert self.state == JingleStates.ended
		stanza, jingle = self.__make_jingle('session-initiate')
		self.__append_contents(jingle)
		self.__broadcast(stanza, jingle, None, 'session-initiate-sent')
		self.connection.connection.send(stanza)
		self.state = JingleStates.pending

	def __session_accept(self):
		assert self.state == JingleStates.pending
		stanza, jingle = self.__make_jingle('session-accept')
		self.__append_contents(jingle)
		self.__broadcast(stanza, jingle, None, 'session-accept-sent')
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
		self.__broadcast_all(stanza, jingle, None, 'session-terminate-sent')
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
		# TODO: test
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-add')
		self.__append_content(jingle, content)
		self.__broadcast(stanza, jingle, None, 'content-add-sent')
		self.connection.connection.send(stanza)

	def __content_accept(self, content):
		# TODO: test
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-accept')
		self.__append_content(jingle, content)
		self.__broadcast(stanza, jingle, None, 'content-accept-sent')
		self.connection.connection.send(stanza)

	def __content_reject(self, content):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-reject')
		self.__append_content(jingle, content)
		self.connection.connection.send(stanza)
		# TODO: this will fail if content is not an RTP content
		self.connection.dispatch('JINGLE_DISCONNECTED',
			(self.peerjid, self.sid, content.media, 'rejected'))

	def __content_modify(self):
		assert self.state != JingleStates.ended

	def __content_remove(self, content):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__make_jingle('content-remove')
		self.__append_content(jingle, content)
		self.connection.connection.send(stanza)
		# TODO: this will fail if content is not an RTP content
		self.connection.dispatch('JINGLE_DISCONNECTED',
			(self.peerjid, self.sid, content.media, 'removed'))

	def content_negociated(self, media):
		self.connection.dispatch('JINGLE_CONNECTED', (self.peerjid, self.sid,
			media))

# vim: se ts=3: