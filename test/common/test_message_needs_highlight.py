import unittest

from gajim.common import app
from gajim.common.helpers import message_needs_highlight

app.settings.set('muc_highlight_words', 'test;gajim')
JID = 'juliet@xmppserver'
NICK = 'Romeo'


class HighlightTest(unittest.TestCase):
    '''Tests for message_needs_highlight'''

    def test_highlight(self):
        t_text1 = 'Romeo: Does this work?'
        t_text2 = 'Romeo:Does this work?'
        t_text3 = 'Romeo Does this work?'
        t_text4 = 'Does this work, romeo?'
        t_text5 = 'Does this work,Romeo?'
        t_text6 = 'Are you using Gajim?'
        t_text7 = 'Did you test this?'
        t_text8 = 'Hi romeo'
        t_text9 = 'My address is juliet@xmppserver'

        f_text1 = 'RomeoDoes this work?'
        f_text2 = ''
        f_text3 = 'https://romeo.tld'
        f_text4 = 'https://romeo.tld message'
        f_text5 = 'https://test.tld/where-is-romeo'

        self.assertTrue(message_needs_highlight(t_text1, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text2, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text3, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text4, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text5, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text6, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text7, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text8, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text9, NICK, JID))

        self.assertFalse(message_needs_highlight(f_text1, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text2, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text3, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text4, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text5, NICK, JID))
