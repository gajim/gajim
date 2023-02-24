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
        t_text10 = 'Romeo, asd'
        t_text11 = 'Romeo,'
        t_text12 = 'Romeo,hi'
        t_text13 = '@Romeo'
        t_text14 = '#Romeo'

        f_text1 = ''
        f_text2 = 'RomeoDoes this work?'
        f_text3 = 'nRomeo'
        f_text4 = 'nRomeoa'
        f_text_url_1 = 'https://romeo.tld'
        f_text_url_2 = 'https://romeo.tld message'
        f_text_url_3 = 'https://test.tld/where-is-romeo'

        self.assertTrue(message_needs_highlight(t_text1, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text2, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text3, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text4, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text5, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text6, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text7, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text8, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text9, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text10, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text11, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text12, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text13, NICK, JID))
        self.assertTrue(message_needs_highlight(t_text14, NICK, JID))

        self.assertFalse(message_needs_highlight(f_text1, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text2, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text3, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text4, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text_url_1, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text_url_2, NICK, JID))
        self.assertFalse(message_needs_highlight(f_text_url_3, NICK, JID))
