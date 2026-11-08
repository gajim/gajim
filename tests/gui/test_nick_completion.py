# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from gajim.common import app
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatOfflineParticipant
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.completion.nickname import NicknameCompletionProvider


class NickCompletionTest(unittest.TestCase):
    def setUp(self) -> None:
        app.window = MagicMock()
        app.window.get_scale_factor = MagicMock(return_value=1)
        app.get_client = MagicMock()
        app.storage.archive = MagicMock()
        app.storage.archive.get_recent_muc_nicks = MagicMock(
            return_value=["Harry", "Joe", "Bhuga"]
        )

    def tearDown(self) -> None:
        del app.storage.archive
        app.get_client = None
        app.window = None

    def test_generate_suggestions(self):
        def _get_mock_participant(nick: str) -> GroupchatParticipant:
            participant = MagicMock(spec_set=GroupchatParticipant)
            participant.name = nick
            return participant

        def _get_mock_offline_member(nick: str) -> GroupchatOfflineParticipant:
            participant = MagicMock(spec_set=GroupchatOfflineParticipant)
            participant.name = nick
            return participant

        def _get_resource(nick: str) -> GroupchatParticipant:
            return _get_mock_participant(nick)

        participant_names = [
            "xavier",
            "Hugo",
            "Rhugbert",
            "Ahugo",
        ]

        offline_members_names = [
            "Yhuga",
        ]

        participants: list[GroupchatParticipant] = []
        for name in participant_names:
            participants.append(_get_mock_participant(name))

        offline_members: list[GroupchatOfflineParticipant] = []
        for name in offline_members_names:
            offline_members.append(_get_mock_offline_member(name))

        groupchat_contact = MagicMock(spec_set=GroupchatContact)
        groupchat_contact.get_participants = MagicMock(return_value=participants)
        groupchat_contact.get_offline_members = MagicMock(return_value=offline_members)
        groupchat_contact.get_resource = MagicMock(side_effect=_get_resource)

        provider = NicknameCompletionProvider()
        provider.populate("@hug", groupchat_contact)
        model, _widget_cls = provider.get_model()

        results = [i.nickname for i in model]
        self.assertEqual(
            results,
            ["Hugo", "Ahugo", "Bhuga", "Rhugbert", "Yhuga"],
        )


if __name__ == "__main__":
    unittest.main()
