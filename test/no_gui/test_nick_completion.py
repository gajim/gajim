import unittest
from unittest.mock import MagicMock

from gajim import gui
gui.init('gtk')

from gajim.gui.groupchat_nick_completion import GroupChatNickCompletion


class Test(unittest.TestCase):

    def test_generate_suggestions(self):
        gen = GroupChatNickCompletion()
        contact = MagicMock()
        contact.jid = 'test'
        gen.switch_contact(contact)

        list_1 = ['aaaa', 'fooo', 'xxxxz', 'xaaaz']
        for name in list_1:
            gen._process_message(name, False, contact.jid)
        list_2 = list_1 + ['xxx']
        r = gen._generate_suggestions(nicks=list_2, beginning='x')
        self.assertEqual(r, ['xaaaz', 'xxx', 'xxxxz'])

        r = gen._generate_suggestions(
            nicks=list_2,
            beginning='m'
        )
        self.assertEqual(r, [])

        for name in ['xaaaz', 'xxxxz']:
            gen._process_message(name, True, contact.jid)

        r = gen._generate_suggestions(
            nicks=list_2,
            beginning='x'
        )
        self.assertEqual(r, ['xaaaz', 'xxx', 'xxxxz'])
        r = gen._generate_suggestions(
            nicks=list_2,
            beginning=''
        )
        self.assertEqual(r, ['aaaa', 'fooo', 'xaaaz', 'xxx', 'xxxxz'])


if __name__ == '__main__':
    unittest.main()
