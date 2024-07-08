import unittest
from unittest.mock import MagicMock

from gajim.common import app

from gajim.gtk.groupchat_nick_completion import GroupChatNickCompletion


class Test(unittest.TestCase):

    def test_generate_suggestions(self):
        participant_names = [
            'Hugo',
            'Herbert',
            'Robert',
            'Daisy',
            'xavier',
            '7user',
        ]

        participants: list[MagicMock] = []
        for name in participant_names:
            participant = MagicMock()
            participant.name = name
            participants.append(participant)

        app.get_client = MagicMock()

        app.storage.archive = MagicMock()
        app.storage.archive.get_recent_muc_nicks = MagicMock(
            return_value=['Daisy', 'Robert'])

        gen = GroupChatNickCompletion()
        contact = MagicMock()
        contact.get_participants = MagicMock(return_value=participants)

        gen.switch_contact(contact)

        r = gen._generate_suggestions(prefix='h')  # type: ignore
        self.assertEqual(r, ['Herbert', 'Hugo'])

        r = gen._generate_suggestions(prefix='')  # type: ignore
        self.assertEqual(r, ['Daisy', 'Robert', '7user', 'Herbert', 'Hugo', 'xavier'])

        r = gen._generate_suggestions(prefix='m')  # type: ignore
        self.assertEqual(r, [])


if __name__ == '__main__':
    unittest.main()
