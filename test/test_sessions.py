import unittest

import time

import lib
lib.setup_env()

from common import gajim
from common import xmpp

from mock import Mock, expectParams
from gajim_mocks import *

from common.stanza_session import StanzaSession

# name to use for the test account
account_name = 'test'

class TestStanzaSession(unittest.TestCase):
	''' Testclass for common/stanzasession.py '''
	def setUp(self):
		self.jid = 'test@example.org/Gajim'
		self.conn = MockConnection(account_name, {'send_stanza': None})
		self.sess = StanzaSession(self.conn, self.jid, None, 'chat')

	def test_generate_thread_id(self):
		# thread_id is a string
		self.assert_(isinstance(self.sess.thread_id, str))

		# it should be somewhat long, to avoid clashes
		self.assert_(len(self.sess.thread_id) >= 32)

	def test_is_loggable(self):
		# by default a session should be loggable
		# (unless the no_log_for setting says otherwise)
		self.assert_(self.sess.is_loggable())

	def test_terminate(self):
		# termination is sent by default
		self.sess.last_send = time.time()
		self.sess.terminate()

		self.assertEqual(None, self.sess.status)

		calls = self.conn.mockGetNamedCalls('send_stanza')
		msg = calls[0].getParam(0)

		self.assertEqual(msg.getThread(), self.sess.thread_id)

	def test_terminate_without_sending(self):
		# no termination is sent if no messages have been sent in the session
		self.sess.terminate()

		self.assertEqual(None, self.sess.status)

		calls = self.conn.mockGetNamedCalls('send_stanza')
		self.assertEqual(0, len(calls))

	def test_terminate_no_remote_xep_201(self):
		# no termination is sent if only messages without thread ids have been
		# received
		self.sess.last_send = time.time()
		self.sess.last_receive = time.time()
		self.sess.terminate()

		self.assertEqual(None, self.sess.status)

		calls = self.conn.mockGetNamedCalls('send_stanza')
		self.assertEqual(0, len(calls))

from session import ChatControlSession

gajim.interface = MockInterface()

import notify

class TestChatControlSession(unittest.TestCase):
	''' Testclass for session.py '''
	def setUp(self):
		self.jid = 'test@example.org/Gajim'
		self.conn = MockConnection(account_name, {'send_stanza': None})
		self.sess = ChatControlSession(self.conn, self.jid, None)
		gajim.logger = MockLogger()

		# initially there are no events
		self.assertEqual(0, len(gajim.events.get_events(account_name)))

		# no notifications have been sent
		self.assertEqual(0, len(notify.notifications))

	def tearDown(self):
		# remove all events and notifications that were added
		gajim.events._events = {}
		notify.notifications = []

	def receive_chat_msg(self, jid, msgtxt):
		'''simulate receiving a chat message from jid'''
		msg = xmpp.Message()
		msg.setBody(msgtxt)
		msg.setType('chat')

		tim = time.localtime()
		encrypted = False
		self.sess.received(jid, msgtxt, tim, encrypted, msg)

	# ----- custom assertions -----
	def assert_new_message_notification(self):
		'''a new_message notification has been sent'''
		self.assertEqual(1, len(notify.notifications))
		notif = notify.notifications[0]
		self.assertEqual('new_message', notif[0])

	def assert_first_message_notification(self):
		'''this message was treated as a first message'''
		self.assert_new_message_notification()
		notif = notify.notifications[0]
		params = notif[3]
		first = params[1]
		self.assert_(first, 'message should have been treated as a first message')

	def assert_not_first_message_notification(self):
		'''this message was not treated as a first message'''
		self.assert_new_message_notification()
		notif = notify.notifications[0]
		params = notif[3]
		first = params[1]
		self.assert_(not first,
			'message was unexpectedly treated as a first message')

	# ----- tests -----
	def test_receive_nocontrol(self):
		'''test receiving a message in a blank state'''
		jid = 'bct@necronomicorp.com/Gajim'
		msgtxt = 'testing one two three'

		self.receive_chat_msg(jid, msgtxt)

		# message was logged
		calls = gajim.logger.mockGetNamedCalls('write')
		self.assertEqual(1, len(calls))

		# no ChatControl was open and autopopup was off
		# so the message goes into the event queue
		self.assertEqual(1, len(gajim.events.get_events(account_name)))

		self.assert_first_message_notification()

		# no control is attached to the session
		self.assertEqual(None, self.sess.control)

	def test_receive_already_has_control(self):
		'''test receiving a message with a session already attached to a
		control'''

		jid = 'bct@necronomicorp.com/Gajim'
		msgtxt = 'testing one two three'

		self.sess.control = MockChatControl(jid, account_name)

		self.receive_chat_msg(jid, msgtxt)

		# message was logged
		calls = gajim.logger.mockGetNamedCalls('write')
		self.assertEqual(1, len(calls))

		# the message does not go into the event queue
		self.assertEqual(0, len(gajim.events.get_events(account_name)))

		self.assert_not_first_message_notification()

		# message was printed to the control
		calls = self.sess.control.mockGetNamedCalls('print_conversation')
		self.assertEqual(1, len(calls))

	def test_received_orphaned_control(self):
		'''test receiving a message when a control that doesn't have a session
		attached exists'''

		jid = 'bct@necronomicorp.com'
		fjid = jid + '/Gajim'
		msgtxt = 'testing one two three'

		ctrl = MockChatControl(jid, account_name)
		gajim.interface.msg_win_mgr = Mock({'get_control': ctrl})
		gajim.interface.msg_win_mgr.mockSetExpectation('get_control',
			expectParams(jid, account_name))

		self.receive_chat_msg(fjid, msgtxt)

		# message was logged
		calls = gajim.logger.mockGetNamedCalls('write')
		self.assertEqual(1, len(calls))

		# the message does not go into the event queue
		self.assertEqual(0, len(gajim.events.get_events(account_name)))

		self.assert_not_first_message_notification()

		# this session is now attached to that control
		self.assertEqual(self.sess, ctrl.session)
		self.assertEqual(ctrl, self.sess.control, 'foo')

		# message was printed to the control
		calls = ctrl.mockGetNamedCalls('print_conversation')
		self.assertEqual(1, len(calls))

if __name__ == '__main__':
    unittest.main()

# vim: se ts=3:
