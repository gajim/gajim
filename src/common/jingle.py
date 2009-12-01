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
Handles the jingle signalling protocol
"""

#TODO:
# * things in XEP 0176, including:
#      - http://xmpp.org/extensions/xep-0176.html#protocol-restarts
#      - http://xmpp.org/extensions/xep-0176.html#fallback
# * XEP 0177 (raw udp)

# * UI:
#   - make state and codec informations available to the user
#   - video integration
#   * config:
#     - codecs

# * figure out why it doesn't work with pidgin:
#     That's maybe a bug in pidgin:
#       http://xmpp.org/extensions/xep-0176.html#protocol-checks

import xmpp
import helpers

from jingle_session import JingleSession
from jingle_rtp import JingleAudio, JingleVideo


class ConnectionJingle(object):
	"""
	This object depends on that it is a part of Connection class.
	"""

	def __init__(self):
		# dictionary: (jid, sessionid) => JingleSession object
		self.__sessions = {}

		# dictionary: (jid, iq stanza id) => JingleSession object,
		# one time callbacks
		self.__iq_responses = {}

	def add_jingle(self, jingle):
		"""
		Add a jingle session to a jingle stanza dispatcher

		jingle - a JingleSession object.
		"""
		self.__sessions[(jingle.peerjid, jingle.sid)] = jingle

	def delete_jingle_session(self, peerjid, sid):
		"""
		Remove a jingle session from a jingle stanza dispatcher
		"""
		key = (peerjid, sid)
		if key in self.__sessions:
			#FIXME: Move this elsewhere?
			for content in self.__sessions[key].contents.values():
				content.destroy()
			self.__sessions[key].callbacks = []
			del self.__sessions[key]

	def _JingleCB(self, con, stanza):
		"""
		The jingle stanza dispatcher

		Route jingle stanza to proper JingleSession object, or create one if it
		is a new session.

		TODO: Also check if the stanza isn't an error stanza, if so route it
		adequatelly.
		"""
		# get data
		jid = helpers.get_full_jid_from_iq(stanza)
		id = stanza.getID()

		if (jid, id) in self.__iq_responses.keys():
			self.__iq_responses[(jid, id)].on_stanza(stanza)
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
		self.__sessions[(jid, sid)].on_stanza(stanza)

		raise xmpp.NodeProcessed

	def start_audio(self, jid):
		if self.get_jingle_session(jid, media='audio'):
			return self.get_jingle_session(jid, media='audio').sid
		jingle = self.get_jingle_session(jid, media='video')
		if jingle:
			jingle.add_content('voice', JingleAudio(jingle))
		else:
			jingle = JingleSession(self, weinitiate=True, jid=jid)
			self.add_jingle(jingle)
			jingle.add_content('voice', JingleAudio(jingle))
			jingle.start_session()
		return jingle.sid

	def start_video(self, jid):
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

# vim: se ts=3: