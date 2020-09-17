import unittest

import lib
lib.setup_env()

import notify
import nbxmpp

from gajim.common import app
from gajim.common import nec
from gajim.common import ged
from gajim.common.nec import NetworkEvent

from gajim.session import ChatControlSession
from gajim.roster_window import RosterWindow

from gajim_mocks import *
from data import account1

app.interface = MockInterface()


# name to use for the test account
account_name = account1


class TestChatControlSession(unittest.TestCase):
    ''' Testclass for session.py '''

    @classmethod
    def setUpClass(cls):
        app.nec = nec.NetworkEventsController()
        cls.conn = MockConnection(account_name, {'send_stanza': None})
        app.logger = MockLogger()
        app.default_session_type = ChatControlSession

    def setUp(self):
        app.notification = notify.Notification()

        # no notifications have been sent
        self.assertEqual(0, len(notify.notifications))

    def tearDown(self):
        app.notification.clean()

    def receive_chat_msg(self, jid, msgtxt):
        '''simulate receiving a chat message from jid'''
        msg = nbxmpp.Message()
        msg.setBody(msgtxt)
        msg.setType('chat')

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
        self.assertTrue(first,
            'message should have been treated as a first message')

    def assert_not_first_message_notification(self):
        '''this message was not treated as a first message'''
        self.assert_new_message_notification()
        notif = notify.notifications[-1]
        first = notif.first_unread
        self.assertTrue(not first,
            'message was unexpectedly treated as a first message')

    # ----- tests -----
    def test_receive_1nocontrol(self):
        '''test receiving a message in a blank state'''
        jid = 'bct@necronomicorp.com'
        fjid = 'bct@necronomicorp.com/Gajim'
        msgtxt = 'testing one'

        self.receive_chat_msg(fjid, msgtxt)

        # session is created
        self.assertTrue((jid in self.conn.sessions) and (
            '123' in self.conn.sessions[jid]), 'session is not created')
        sess = self.conn.sessions[jid]['123']

        # message was logged
        calls = app.storage.archive.mockGetNamedCalls('insert_into_logs')
        self.assertEqual(1, len(calls))

        # no ChatControl was open and autopopup was off
        # so the message goes into the event queue
        self.assertEqual(1, len(app.events.get_events(account_name)))

        self.assert_first_message_notification()

        # no control is attached to the session
        self.assertEqual(None, sess.control)

    def test_receive_2already_has_control(self):
        '''test receiving a message with a session already attached to a
        control'''
        jid = 'bct@necronomicorp.com'
        fjid = 'bct@necronomicorp.com/Gajim'
        msgtxt = 'testing two'
        app.interface.roster = RosterWindow(app.app)

        sess = self.conn.sessions[jid]['123']
        sess.control = MockChatControl(fjid, account_name)

        self.receive_chat_msg(fjid, msgtxt)

        # message was logged
        calls = app.storage.archive.mockGetNamedCalls('insert_into_logs')
        self.assertEqual(2, len(calls))

        # the message does not go into the event queue
        self.assertEqual(1, len(app.events.get_events(account_name)))

        self.assert_not_first_message_notification()

        # message was printed to the control
        calls = sess.control.mockGetNamedCalls('print_conversation')
        self.assertEqual(1, len(calls))
        app.interface.roster.window.destroy()

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
        #calls = gajim.logger.mockGetNamedCalls('insert_into_logs')
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
