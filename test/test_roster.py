import unittest

import lib
lib.setup_env()

from data import *

from mock import Mock, expectParams
from gajim_mocks import *

from common import gajim
from common import zeroconf
import roster_window

gajim.get_jid_from_account = lambda acc: 'myjid@' + acc

class TestRosterWindow(unittest.TestCase):

	def setUp(self):
		gajim.interface = MockInterface()
		self.roster = roster_window.RosterWindow()

		self.C_NAME = roster_window.C_NAME
		self.C_TYPE = roster_window.C_TYPE
		self.C_JID = roster_window.C_JID
		self.C_ACCOUNT = roster_window.C_ACCOUNT

		# Add after creating RosterWindow
		# We want to test the filling explicitly
		for acc in contacts:
			gajim.connections[acc] = MockConnection(acc)

	def tearDown(self):
		self.roster.model.clear()
		for acc in gajim.contacts.get_accounts():
			gajim.contacts.clear_contacts(acc)

	### Custom assertions
	def assert_all_contacts_are_in_roster(self, acc):
		for jid in contacts[acc]:
			self.assert_contact_is_in_roster(jid, acc)

	def assert_contact_is_in_roster(self, jid, account):
		contacts = gajim.contacts.get_contacts(account, jid)
		# check for all resources
		for contact in contacts:
			iters = self.roster._get_contact_iter(jid, account,
				model=self.roster.model)

			if jid != gajim.get_jid_from_account(account):
				# We don't care for groups of SelfContact
				self.assertTrue(len(iters) == len(contact.get_shown_groups()),
					msg='Contact is not in all his groups')

			# Are we big brother?
			bb_jid = None
			bb_account = None
			family = gajim.contacts.get_metacontacts_family(account, jid)
			if family:
				nearby_family, bb_jid, bb_account = \
					self.roster._get_nearby_family_and_big_brother(family, account)

				is_in_nearby_family = (jid, account) in (
					(data['jid'], data['account']) for data in nearby_family)
				self.assertTrue(is_in_nearby_family,
					msg='Contact not in his own nearby family')

			is_big_brother = (bb_jid, bb_account) == (jid, account)

			# check for each group tag
			for titerC in iters:
				self.assertTrue(self.roster.model.iter_is_valid(titerC),
					msg='Contact iter invalid')

				c_model = self.roster.model[titerC]
				self.assertEquals(contact.get_shown_name(), c_model[self.C_NAME],
					msg='Contact name missmatch')
				self.assertEquals(contact.jid, c_model[self.C_JID],
					msg='Jid missmatch')

				if not self.roster.regroup:
					self.assertEquals(account, c_model[self.C_ACCOUNT],
						msg='Account missmatch')

				# Check for correct nesting
				parent_iter = self.roster.model.iter_parent(titerC)
				p_model = self.roster.model[parent_iter]
				if family:
					if is_big_brother:
						self.assertTrue(p_model[self.C_TYPE] == 'group',
							msg='Big Brother is not on top')
					else:
							self.assertTrue(p_model[self.C_TYPE] == 'contact',
								msg='Little Brother brother has no BigB')
				else:
					if jid == gajim.get_jid_from_account(account):
							self.assertTrue(p_model[self.C_TYPE] == 'account',
								msg='SelfContact is not on top')
					else:
						self.assertTrue(p_model[self.C_TYPE] == 'group',
							msg='Contact not found in a group')

	def assert_group_is_in_roster(self, group, account):
		#TODO
		pass

	def assert_account_is_in_roster(self, acc):
		titerA = self.roster._get_account_iter(acc, model=self.roster.model)
		self.assertTrue(self.roster.model.iter_is_valid(titerA),
			msg='Account iter is invalid')

		acc_model = self.roster.model[titerA]
		self.assertEquals(acc_model[self.C_TYPE], 'account',
			msg='No account found')

		if not self.roster.regroup:
			self.assertEquals(acc_model[self.C_ACCOUNT], acc,
				msg='Account not found')

			self_jid = gajim.get_jid_from_account(acc)
			self.assertEquals(acc_model[self.C_JID], self_jid,
				msg='Account JID not found in account row')

	def assert_model_is_in_sync(self):
		#TODO: check that iter_n_children returns the correct numbers
		pass

	# tests
	def test_fill_contacts_and_groups_dicts(self):
		for acc in contacts:
			self.roster.fill_contacts_and_groups_dicts(contacts[acc], acc)

			for jid in contacts[acc]:
				instances = gajim.contacts.get_contacts(acc, jid)

				# Created a contact for each single jid?
				self.assertTrue(len(instances) == 1)

				# Contacts kept their info
				contact = instances[0]
				self.assertEquals(contact.groups, contacts[acc][jid]['groups'],
					msg='Group Missmatch')

				groups = contacts[acc][jid]['groups'] or ['General',]

		# cleanup
		self.roster.model.clear()
		for acc in contacts:
			gajim.contacts.clear_contacts(acc)

	def test_fill_roster_model(self):
		for acc in contacts:
			self.roster.fill_contacts_and_groups_dicts(contacts[acc], acc)

			self.roster.add_account(acc)
			self.assert_account_is_in_roster(acc)

			self.roster.add_account_contacts(acc)
			self.assert_all_contacts_are_in_roster(acc)

		self.assert_model_is_in_sync()


class TestRosterWindowRegrouped(TestRosterWindow):

	def setUp(self):
		gajim.config.set('mergeaccounts', True)
		TestRosterWindow.setUp(self)

	def test_toggle_regroup(self):
		self.roster.regroup = not self.roster.regroup
		self.roster.setup_and_draw_roster()
		self.roster.regroup = not self.roster.regroup
		self.roster.setup_and_draw_roster()


class TestRosterWindowMetaContacts(TestRosterWindowRegrouped):

	def test_receive_metacontact_data(self):
		for complete_data in metacontact_data:
			t_acc = complete_data[0]['account']
			t_jid = complete_data[0]['jid']
			data = complete_data[1:]
			for brother in data:
				acc = brother['account']
				jid = brother['jid']
				gajim.contacts.add_metacontact(t_acc, t_jid, acc, jid)
		self.roster.setup_and_draw_roster()

	def test_connect_new_metacontact(self):
		self.test_fill_roster_model()

		jid = u'coolstuff@gajim.org'
		contact = gajim.contacts.create_contact(jid)
		gajim.contacts.add_contact(account1, contact)
		self.roster.add_contact(jid, account1)
		self.roster.chg_contact_status(contact, 'offline', '', account1)

		gajim.contacts.add_metacontact(account1, u'samejid@gajim.org',
			account1, jid)
		self.roster.chg_contact_status(contact, 'online', '', account1)

		self.assert_model_is_in_sync()



if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
