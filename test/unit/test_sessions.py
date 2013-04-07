import unittest

import time

import lib
lib.setup_env()


import notify

from common import gajim
from common import nec
from common import ged
from common.nec import NetworkEvent
from common.connection_handlers_events import MessageReceivedEvent
from common.connection_handlers_events import DecryptedMessageReceivedEvent
import nbxmpp

from common.stanza_session import StanzaSession
from session import ChatControlSession
from roster_window import RosterWindow

from mock import Mock, expectParams
from gajim_mocks import *

gajim.interface = MockInterface()


# name to use for the test account
account_name = 'test'

class TestStanzaSession(unittest.TestCase):
    ''' Testclass for common/stanzasession.py '''

    def setUp(self):
        self.jid = nbxmpp.JID('test@example.org/Gajim')
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


class TestChatControlSession(unittest.TestCase):
    ''' Testclass for session.py '''

    @classmethod
    def setUpClass(cls):
        gajim.nec = nec.NetworkEventsController()
        cls.conn = MockConnection(account_name, {'send_stanza': None})
        gajim.logger = MockLogger()
        gajim.default_session_type = ChatControlSession

    def setUp(self):
        gajim.notification = notify.Notification()

        # no notifications have been sent
        self.assertEqual(0, len(notify.notifications))

    def tearDown(self):
        gajim.notification.clean()

    def receive_chat_msg(self, jid, msgtxt):
        '''simulate receiving a chat message from jid'''
        msg = nbxmpp.Message()
        msg.setBody(msgtxt)
        msg.setType('chat')

        tim = time.localtime()
        encrypted = False
        xml = """<message from='%s' id='1' type='chat'><body>%s</body>
            <thread>123</thread></message>""" % (jid, msgtxt)
        stanza = nbxmpp.protocol.Message(node=nbxmpp.simplexml.XML2Node(xml))
        self.conn._messageCB(None, stanza)

    # ----- custom assertions -----
    def assert_new_message_notification(self):
        '''a new_message notification has been sent'''
        self.assertEqual(1, len(notify.notifications))
        notif = notify.notifications[-1]
        self.assertEqual('New Message', notif.popup_event_type)

    def assert_first_message_notification(self):
        '''this message was treated as a first message'''
        self.assert_new_message_notification()
        notif = notify.notifications[-1]
        first = notif.first_unread
        self.assert_(first,
            'message should have been treated as a first message')

    def assert_not_first_message_notification(self):
        '''this message was not treated as a first message'''
        self.assert_new_message_notification()
        notif = notify.notifications[-1]
        first = notif.first_unread
        self.assert_(not first,
            'message was unexpectedly treated as a first message')

    # ----- tests -----
    def test_receive_1nocontrol(self):
        '''test receiving a message in a blank state'''
        jid = 'bct@necronomicorp.com'
        fjid = 'bct@necronomicorp.com/Gajim'
        msgtxt = 'testing one'

        self.receive_chat_msg(fjid, msgtxt)

        # session is created
        self.assert_((jid in self.conn.sessions) and (
            '123' in self.conn.sessions[jid]), 'session is not created')
        sess = self.conn.sessions[jid]['123']

        # message was logged
        calls = gajim.logger.mockGetNamedCalls('write')
        self.assertEqual(1, len(calls))

        # no ChatControl was open and autopopup was off
        # so the message goes into the event queue
        self.assertEqual(1, len(gajim.events.get_events(account_name)))

        self.assert_first_message_notification()

        # no control is attached to the session
        self.assertEqual(None, sess.control)

    def test_receive_2already_has_control(self):
        '''test receiving a message with a session already attached to a
        control'''
        jid = 'bct@necronomicorp.com'
        fjid = 'bct@necronomicorp.com/Gajim'
        msgtxt = 'testing two'
        roster = RosterWindow()

        sess = self.conn.sessions[jid]['123']
        sess.control = MockChatControl(fjid, account_name)

        self.receive_chat_msg(fjid, msgtxt)

        # message was logged
        calls = gajim.logger.mockGetNamedCalls('write')
        self.assertEqual(2, len(calls))

        # the message does not go into the event queue
        self.assertEqual(1, len(gajim.events.get_events(account_name)))

        self.assert_not_first_message_notification()

        # message was printed to the control
        calls = sess.control.mockGetNamedCalls('print_conversation')
        self.assertEqual(1, len(calls))

    #def test_received_3orphaned_control(self):
        #'''test receiving a message when a control that doesn't have a session
        #attached exists'''

        #jid = 'bct@necronomicorp.com'
        #fjid = jid + '/Gajim'
        #msgtxt = 'testing three'

        #ctrl = MockChatControl(jid, account_name)
        #gajim.interface.msg_win_mgr = Mock({'get_control': ctrl})
        #gajim.interface.msg_win_mgr.mockSetExpectation('get_control',
                #expectParams(jid, account_name))

        #self.receive_chat_msg(fjid, msgtxt)

        ## message was logged
        #calls = gajim.logger.mockGetNamedCalls('write')
        #self.assertEqual(1, len(calls))

        ## the message does not go into the event queue
        #self.assertEqual(0, len(gajim.events.get_events(account_name)))

        #self.assert_not_first_message_notification()

        ## this session is now attached to that control
        #self.assertEqual(self.sess, ctrl.session)
        #self.assertEqual(ctrl, self.sess.control, 'foo')

        ## message was printed to the control
        #calls = ctrl.mockGetNamedCalls('print_conversation')
        #self.assertEqual(1, len(calls))

if __name__ == '__main__':
    unittest.main()
