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
Handles Jingle contents (XEP 0166)
"""

import xmpp

contents = {}

def get_jingle_content(node):
	namespace = node.getNamespace()
	if namespace in contents:
		return contents[namespace](node)


class JingleContentSetupException(Exception):
	"""
	Exception that should be raised when a content fails to setup.
	"""


class JingleContent(object):
	"""
	An abstraction of content in Jingle sessions
	"""

	def __init__(self, session, transport):
		self.session = session
		self.transport = transport
		# will be filled by JingleSession.add_content()
		# don't uncomment these lines, we will catch more buggy code then
		# (a JingleContent not added to session shouldn't send anything)
		#self.creator = None
		#self.name = None
		self.accepted = False
		self.sent = False

		self.media = None

		self.senders = 'both' #FIXME
		self.allow_sending = True # Used for stream direction, attribute 'senders'

		self.callbacks = {
			# these are called when *we* get stanzas
			'content-accept': [self.__on_transport_info],
			'content-add': [self.__on_transport_info],
			'content-modify': [],
			'content-reject': [],
			'content-remove': [],
			'description-info': [],
			'security-info': [],
			'session-accept': [self.__on_transport_info],
			'session-info': [],
			'session-initiate': [self.__on_transport_info],
			'session-terminate': [],
			'transport-info': [self.__on_transport_info],
			'transport-replace': [],
			'transport-accept': [],
			'transport-reject': [],
			'iq-result': [],
			'iq-error': [],
			# these are called when *we* sent these stanzas
			'content-accept-sent': [self.__fill_jingle_stanza],
			'content-add-sent': [self.__fill_jingle_stanza],
			'session-initiate-sent': [self.__fill_jingle_stanza],
			'session-accept-sent': [self.__fill_jingle_stanza],
			'session-terminate-sent': [],
		}

	def is_ready(self):
		return self.accepted and not self.sent

	def add_remote_candidates(self, candidates):
		"""
		Add a list of candidates to the list of remote candidates
		"""
		pass

	def on_stanza(self, stanza, content, error, action):
		"""
		Called when something related to our content was sent by peer
		"""
		if action in self.callbacks:
			for callback in self.callbacks[action]:
				callback(stanza, content, error, action)

	def __on_transport_info(self, stanza, content, error, action):
		"""
		Got a new transport candidate
		"""
		candidates = self.transport.parse_transport_stanza(
			content.getTag('transport'))
		if candidates:
			self.add_remote_candidates(candidates)

	def __content(self, payload=[]):
		"""
		Build a XML content-wrapper for our data
		"""
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator},
			payload=payload)

	def send_candidate(self, candidate):
		"""
		Send a transport candidate for a previously defined transport.
		"""
		content = self.__content()
		content.addChild(self.transport.make_transport([candidate]))
		self.session.send_transport_info(content)

	def __fill_jingle_stanza(self, stanza, content, error, action):
		"""
		Add our things to session-initiate stanza
		"""
		self._fill_content(content)
		self.sent = True
		content.addChild(node=self.transport.make_transport())

	def destroy(self):
		self.callbacks = None
		del self.session.contents[(self.creator, self.name)]

# vim: se ts=3:
