import gajim

from common import xmpp
from common import helpers

import random
import string

class StanzaSession:
	def __init__(self, conn, jid, thread_id, type):
		self.conn = conn

		if isinstance(jid, str) or isinstance(jid, unicode):
			self.jid = xmpp.JID(jid)
		else:
			self.jid = jid

		self.type = type

		if thread_id:
			self.received_thread_id = True
			self.thread_id = thread_id
		else:
			self.received_thread_id = False
			if type == 'normal':
				self.thread_id = None
			else:
				self.thread_id = self.generate_thread_id()

		self.last_send = 0

	def generate_thread_id(self):
		return "".join([random.choice(string.letters) for x in xrange(0,32)])
