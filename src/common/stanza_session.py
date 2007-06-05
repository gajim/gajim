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

	def get_control(self, advanced_notif_num = None):
		account = self.conn.name
		highest_contact = gajim.contacts.get_contact_with_highest_priority(account, str(self.jid))
		contact = gajim.contacts.get_contact(account, self.jid.getStripped(), self.jid.getResource())
		if isinstance(contact, list):
			# there was no resource (maybe we're reading unread messages after shutdown). just take the first one for now :/
			contact = contact[0]

		ctrl = gajim.interface.msg_win_mgr.get_control(str(self.jid), account, self.thread_id)
#		if not ctrl:
#			if highest_contact and contact.resource == highest_contact.resource and not str(self.jid) == gajim.get_jid_from_account(account):
#				ctrl = gajim.interface.msg_win_mgr.get_control(self.jid.getStripped(), account, self.thread_id)

		if not ctrl and helpers.allow_popup_window(account, advanced_notif_num):
			gajim.new_chat(contact, account, resource = resource_for_chat, session = self)

		return ctrl
