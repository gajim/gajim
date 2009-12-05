'''
Tests for the miscellaneous functions scattered throughout src/gajim.py
'''
import unittest

import lib
lib.setup_env()

from common import gajim
from common import contacts as contacts_module
from gajim import Interface

from gajim_mocks import *
gajim.logger = MockLogger()

Interface()

import time
from data import *

import roster_window

import notify

class TestStatusChange(unittest.TestCase):
	'''tests gajim.py's incredibly complex handle_event_notify'''

	def setUp(self):
		
		gajim.connections = {}
		gajim.contacts = contacts_module.LegacyContactsAPI()
		gajim.interface.roster = roster_window.RosterWindow()

		for acc in contacts:
			gajim.connections[acc] = MockConnection(acc)

			gajim.interface.roster.fill_contacts_and_groups_dicts(contacts[acc],
				acc)
			gajim.interface.roster.add_account(acc)
			gajim.interface.roster.add_account_contacts(acc)

		self.assertEqual(0, len(notify.notifications))

	def tearDown(self):
		notify.notifications = []

	def contact_comes_online(self, account, jid, resource, prio):
		'''a remote contact comes online'''
		gajim.interface.handle_event_notify(account, (jid, 'online', "I'm back!",
			resource, prio, None, time.time(), None))

		contact = None
		for c in gajim.contacts.get_contacts(account, jid):
			if c.resource == resource:
				contact = c
				break

		self.assertEqual('online', contact.show)
		self.assertEqual("I'm back!", contact.status)
		self.assertEqual(prio, contact.priority)

		# the most recent notification is that the contact connected
		self.assertEqual('contact_connected', notify.notifications[-1][0])

	def contact_goes_offline(self, account, jid, resource, prio,
	still_exists = True):
		'''a remote contact goes offline.'''
		gajim.interface.handle_event_notify(account, (jid, 'offline', 'Goodbye!',
			resource, prio, None, time.time(), None))

		contact = None
		for c in gajim.contacts.get_contacts(account, jid):
			if c.resource == resource:
				contact = c
				break

		if not still_exists:
			self.assert_(contact is None)
			return

		self.assertEqual('offline', contact.show)
		self.assertEqual('Goodbye!', contact.status)
		self.assertEqual(prio, contact.priority)

		self.assertEqual('contact_disconnected', notify.notifications[-1][0])

	def user_starts_chatting(self, jid, account, resource=None):
		'''the user opens a chat window and starts talking'''
		ctrl = MockChatControl(jid, account)
		win = MockWindow()
		win.new_tab(ctrl)
		gajim.interface.msg_win_mgr._windows['test'] = win

		if resource:
			jid = jid + '/' + resource

		# a basic session is started
		session = gajim.connections[account1].make_new_session(jid,
			'01234567890abcdef', cls=MockSession)
		ctrl.set_session(session)

		return ctrl

	def user_starts_esession(self, jid, resource, account):
		'''the user opens a chat window and starts an encrypted session'''
		ctrl = self.user_starts_chatting(jid, account, resource)
		ctrl.session.status = 'active'
		ctrl.session.enable_encryption = True

		return ctrl

	def test_contact_comes_online(self):
		jid = 'default1@gajim.org'

		# contact is offline initially
		contacts = gajim.contacts.get_contacts(account1, jid)
		self.assertEqual(1, len(contacts))
		self.assertEqual('offline', contacts[0].show)
		self.assertEqual('', contacts[0].status)

		self.contact_comes_online(account1, jid, 'lowprio', 1)

	def test_contact_goes_offline(self):
		jid = 'default1@gajim.org'

		self.contact_comes_online(account1, jid, 'lowprio', 1)

		ctrl = self.user_starts_chatting(jid, account1)
		orig_sess = ctrl.session

		self.contact_goes_offline(account1, jid, 'lowprio', 1)

		# session hasn't changed since we were talking to the bare jid
		self.assertEqual(orig_sess, ctrl.session)

	def test_two_resources_higher_comes_online(self):
		jid = 'default1@gajim.org'

		self.contact_comes_online(account1, jid, 'lowprio', 1)

		ctrl = self.user_starts_chatting(jid, account1)

		self.contact_comes_online(account1, jid, 'highprio', 50)

		# old session was dropped
		self.assertEqual(None, ctrl.session)

	def test_two_resources_higher_goes_offline(self):
		jid = 'default1@gajim.org'

		self.contact_comes_online(account1, jid, 'lowprio', 1)
		self.contact_comes_online(account1, jid, 'highprio', 50)

		ctrl = self.user_starts_chatting(jid, account1)

		self.contact_goes_offline(account1, jid, 'highprio', 50,
			still_exists=False)

		# old session was dropped
		self.assertEqual(None, ctrl.session)

	def test_two_resources_higher_comes_online_with_esession(self):
		jid = 'default1@gajim.org'

		self.contact_comes_online(account1, jid, 'lowprio', 1)

		ctrl = self.user_starts_esession(jid, 'lowprio', account1)

		self.contact_comes_online(account1, jid, 'highprio', 50)

		# session was associated with the low priority full jid, so it should
		# have been removed from the control
		self.assertEqual(None, ctrl.session)

	def test_two_resources_higher_goes_offline_with_esession(self):
		jid = 'default1@gajim.org'

		self.contact_comes_online(account1, jid, 'lowprio', 1)
		self.contact_comes_online(account1, jid, 'highprio', 50)

		ctrl = self.user_starts_esession(jid, 'highprio', account1)

		self.contact_goes_offline(account1, jid, 'highprio', 50,
		still_exists=False)

		# session was associated with the high priority full jid, so it should
		# have been removed from the control
		self.assertEqual(None, ctrl.session)

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
