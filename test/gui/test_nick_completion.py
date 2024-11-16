# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock

from gajim.common import app
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.completion.nickname import NicknameCompletionProvider


class Test(unittest.TestCase):
    def test_generate_suggestions(self):

        def _get_mock_participant(nick: str) -> GroupchatParticipant:
            participant = MagicMock(spec_set=GroupchatParticipant)
            participant.name = nick
            return participant

        def _get_resource(nick: str) -> GroupchatParticipant:
            return _get_mock_participant(nick)

        participant_names = [
            'Hugo',
            'Herbert',
            'Robert',
            'Daisy',
            'xavier',
            '7user',
        ]

        participants: list[GroupchatParticipant] = []
        for name in participant_names:
            participants.append(_get_mock_participant(name))

        gen = NicknameCompletionProvider()
        groupchat_contact = MagicMock(spec_set=GroupchatContact)
        groupchat_contact.get_participants = MagicMock(return_value=participants)
        groupchat_contact.get_resource = MagicMock(side_effect=_get_resource)

        results = gen._generate_suggestions(groupchat_contact)  # type: ignore
        self.assertEqual(
            [result.name for result in results],
            ['Harry', 'Joe', '7user', 'Daisy', 'Herbert', 'Hugo', 'Robert', 'xavier'],
        )


app.get_client = MagicMock()

app.storage.archive = MagicMock()
app.storage.archive.get_recent_muc_nicks = MagicMock(return_value=['Harry', 'Joe'])

if __name__ == '__main__':
    unittest.main()
