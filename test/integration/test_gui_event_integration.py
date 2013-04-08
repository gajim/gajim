'''
Tests for the miscellaneous functions scattered throughout src/gajim.py
'''
import unittest

import lib
lib.setup_env()

import nbxmpp

from common import gajim
from common import contacts as contacts_module
from common import caps_cache
from gajim import Interface

from gajim_mocks import *
gajim.logger = MockLogger()

Interface()

import time
from data import *

import roster_window
import plugins
import notify

class TestStatusChange(unittest.TestCase):
    '''tests gajim.py's incredibly complex presence handling'''

    def setUp(self):

        gajim.connections = {}
        gajim.contacts = contacts_module.LegacyContactsAPI()
        gajim.interface.roster = roster_window.RosterWindow()
        gajim.plugin_manager = plugins.PluginManager()
        gajim.logger = MockLogger()
        caps_cache.initialize(gajim.logger)

        for acc in contacts:
            gajim.connections[acc] = MockConnection(acc)

            gajim.interface.roster.fill_contacts_and_groups_dicts(contacts[acc],
                    acc)
            gajim.interface.roster.add_account(acc)
            gajim.interface.roster.add_account_contacts(acc)

        self.assertEqual(0, len(notify.notifications))

    def tearDown(self):
        notify.notifications = []
        for acc in contacts:
            gajim.connections[acc].cleanup()

    def contact_comes_online(self, account, jid, resource, prio,
    should_popup=True):
        '''a remote contact comes online'''
        xml = """<presence from='%s/%s' id='123'><priority>%s</priority>
            <c node='http://gajim.org' ver='pRCD6cgQ4SDqNMCjdhRV6TECx5o='
            hash='sha-1' xmlns='http://jabber.org/protocol/caps'/>
            <status>I'm back!</status>
            </presence>
        """ % (jid, resource, prio)
        msg = nbxmpp.protocol.Presence(node=nbxmpp.simplexml.XML2Node(xml))
        gajim.connections[account]._presenceCB(None, msg)

        contact = None
        for c in gajim.contacts.get_contacts(account, jid):
            if c.resource == resource:
                contact = c
                break

        self.assertEqual('online', contact.show)
        self.assertEqual("I'm back!", contact.status)
        self.assertEqual(prio, contact.priority)

        # the most recent notification is that the contact connected
        if should_popup:
            self.assertEqual('Contact Signed In',
                notify.notifications[-1].popup_event_type)
        else:
            self.assertEqual('', notify.notifications[-1].popup_event_type)

    def contact_goes_offline(self, account, jid, resource, prio,
    still_exists = True):
        '''a remote contact goes offline.'''
        xml = """<presence type='unavailable' from='%s/%s' id='123'>
            <priority>%s</priority>
            <c node='http://gajim.org' ver='pRCD6cgQ4SDqNMCjdhRV6TECx5o='
            hash='sha-1' xmlns='http://jabber.org/protocol/caps'/>
            <status>Goodbye!</status>
            </presence>
        """ % (jid, resource, prio)
        msg = nbxmpp.protocol.Presence(node=nbxmpp.simplexml.XML2Node(xml))
        gajim.connections[account]._presenceCB(None, msg)

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

        self.assertEqual('Contact Signed Out',
            notify.notifications[-1].popup_event_type)

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

        self.contact_comes_online(account1, jid, 'highprio', 50,
            should_popup=False)

        # old session was dropped
        self.assertEqual(None, ctrl.session)

    def test_two_resources_higher_goes_offline(self):
        jid = 'default1@gajim.org'

        self.contact_comes_online(account1, jid, 'lowprio', 1)
        self.contact_comes_online(account1, jid, 'highprio', 50,
            should_popup=False)

        ctrl = self.user_starts_chatting(jid, account1)

        self.contact_goes_offline(account1, jid, 'highprio', 50,
            still_exists=False)

        # old session was dropped
        self.assertEqual(None, ctrl.session)

    def test_two_resources_higher_comes_online_with_esession(self):
        jid = 'default1@gajim.org'

        self.contact_comes_online(account1, jid, 'lowprio', 1)

        ctrl = self.user_starts_esession(jid, 'lowprio', account1)

        self.contact_comes_online(account1, jid, 'highprio', 50,
            should_popup=False)

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
