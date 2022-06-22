import unittest
from unittest.mock import MagicMock

from gajim import gui
gui.init('gtk')

from gajim.gui.groupchat_nick_completion import GroupChatNickCompletion


class Test(unittest.TestCase):

    def test_generate_suggestions(self):
        contact = MagicMock()
        message_input = MagicMock()
        gen = GroupChatNickCompletion('testacc', contact, message_input)

        l = ['aaaa', 'fooo', 'xxxxz', 'xaaaz']
        for n in l:
            gen.record_message(n, False)
        l2 = ['xxx'] + l
        r = gen._generate_suggestions(nicks=l2, beginning='x')
        self.assertEqual(r, ['xaaaz', 'xxxxz', 'xxx'])

        r = gen._generate_suggestions(
            nicks=l2,
            beginning='m'
        )
        self.assertEqual(r, [])

        for n in ['xaaaz', 'xxxxz']:
            gen.record_message(n, True)

        r = gen._generate_suggestions(
            nicks=l2,
            beginning='x'
        )
        self.assertEqual(r, ['xxxxz', 'xaaaz', 'xxx'])
        r = gen._generate_suggestions(
            nicks=l2,
            beginning=''
        )
        self.assertEqual(r, ['xxxxz', 'xaaaz', 'aaaa', 'fooo', 'xxx'])

        l2[1] = 'bbbb'

        old_name = 'aaaa'
        new_name = 'bbbb'

        for lst in (gen._attention_list, gen._sender_list):
            for idx, contact in enumerate(lst):
                if contact == old_name:
                    lst[idx] = new_name

        r = gen._generate_suggestions(
            nicks=l2,
            beginning=''
        )
        self.assertEqual(r, ['xxxxz', 'xaaaz', 'bbbb', 'fooo', 'xxx'])


if __name__ == '__main__':
    unittest.main()
