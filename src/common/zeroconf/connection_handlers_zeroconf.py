##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##	- Yann Leboulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
## - Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import time
import socket

from calendar import timegm

import common.xmpp

from common import helpers
from common import gajim
from common.zeroconf import zeroconf
from common.commands import ConnectionCommands
from common.pep import ConnectionPEP
from common.protocol.bytestream import ConnectionBytestreamZeroconf

import logging
log = logging.getLogger('gajim.c.z.connection_handlers_zeroconf')

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible']
# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'
AGENT_REMOVED = 'agent_removed'
HAS_IDLE = True
try:
	import idle
except Exception:
	log.debug(_('Unable to load idle module'))
	HAS_IDLE = False

from common import connection_handlers
from session import ChatControlSession

class ConnectionVcard(connection_handlers.ConnectionVcard):
	def add_sha(self, p, send_caps = True):
		return p

	def add_caps(self, p):
		return p

	def request_vcard(self, jid = None, is_fake_jid = False):
		pass

	def send_vcard(self, vcard):
		pass


class ConnectionHandlersZeroconf(ConnectionVcard, ConnectionBytestreamZeroconf,
ConnectionCommands, ConnectionPEP, connection_handlers.ConnectionHandlersBase):
	def __init__(self):
		ConnectionVcard.__init__(self)
		ConnectionBytestreamZeroconf.__init__(self)
		ConnectionCommands.__init__(self)
		connection_handlers.ConnectionHandlersBase.__init__(self)

		try:
			idle.init()
		except Exception:
			global HAS_IDLE
			HAS_IDLE = False

	def _messageCB(self, ip, con, msg):
		"""
		Called when we receive a message
		"""
		log.debug('Zeroconf MessageCB')

		frm = msg.getFrom()
		mtype = msg.getType()
		thread_id = msg.getThread()

		if not mtype:
			mtype = 'normal'

		if frm is None:
			for key in self.connection.zeroconf.contacts:
				if ip == self.connection.zeroconf.contacts[key][zeroconf.C_ADDRESS]:
					frm = key

		frm = unicode(frm)

		session = self.get_or_create_session(frm, thread_id)

		if thread_id and not session.received_thread_id:
			session.received_thread_id = True

		if msg.getTag('feature') and msg.getTag('feature').namespace == \
		common.xmpp.NS_FEATURE:
			if gajim.HAVE_PYCRYPTO:
				self._FeatureNegCB(con, msg, session)
			return

		if msg.getTag('init') and msg.getTag('init').namespace == \
		common.xmpp.NS_ESESSION_INIT:
			self._InitE2ECB(con, msg, session)

		encrypted = False
		tim = msg.getTimestamp()
		tim = helpers.datetime_tuple(tim)
		tim = time.localtime(timegm(tim))

		if msg.getTag('c', namespace = common.xmpp.NS_STANZA_CRYPTO):
			encrypted = True

			try:
				msg = session.decrypt_stanza(msg)
			except Exception:
				self.dispatch('FAILED_DECRYPT', (frm, tim))

		msgtxt = msg.getBody()
		subject = msg.getSubject() # if not there, it's None

		# invitations
		invite = None
		encTag = msg.getTag('x', namespace = common.xmpp.NS_ENCRYPTED)

		if not encTag:
			invite = msg.getTag('x', namespace = common.xmpp.NS_MUC_USER)
			if invite and not invite.getTag('invite'):
				invite = None

		if encTag and self.USE_GPG:
			#decrypt
			encmsg = encTag.getData()

			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				decmsg = self.gpg.decrypt(encmsg, keyID)
				# \x00 chars are not allowed in C (so in GTK)
				msgtxt = decmsg.replace('\x00', '')
				encrypted = True

		if mtype == 'error':
			self.dispatch_error_msg(msg, msgtxt, session, frm, tim, subject)
		else:
			# XXX this shouldn't be hardcoded
			if isinstance(session, ChatControlSession):
				session.received(frm, msgtxt, tim, encrypted, msg)
			else:
				session.received(msg)
	# END messageCB

	def store_metacontacts(self, tags):
		"""
		Fake empty method
		"""
		# serverside metacontacts are not supported with zeroconf
		# (there is no server)
		pass

	def _DiscoverItemsGetCB(self, con, iq_obj):
		log.debug('DiscoverItemsGetCB')

		if not self.connection or self.connected < 2:
			return

		if self.commandItemsQuery(con, iq_obj):
			raise common.xmpp.NodeProcessed
		node = iq_obj.getTagAttr('query', 'node')
		if node is None:
			result = iq_obj.buildReply('result')
			self.connection.send(result)
			raise common.xmpp.NodeProcessed
		if node==common.xmpp.NS_COMMANDS:
			self.commandListQuery(con, iq_obj)
			raise common.xmpp.NodeProcessed

# vim: se ts=3:
