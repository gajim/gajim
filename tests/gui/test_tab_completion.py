# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

# The tests access private methods and attributes of the completer on
# purpose, to test them in isolation
# pyright: reportPrivateUsage=false

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gi.repository import Gdk

from gajim.common import app
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.completion.tab_completer import MAX_COMPLETIONS
from gajim.gtk.completion.tab_completer import OccupantsTabCompleter


def _get_mock_participant(nick: str) -> GroupchatParticipant:
    participant = MagicMock(spec_set=GroupchatParticipant)
    participant.name = nick
    return participant


class TabCompletionTestCase(unittest.TestCase):
    """Install the app globals the completer touches and restore them
    afterwards, so the tests do not leak mock state into other test
    modules.
    """

    def setUp(self) -> None:
        self._old_get_client = app.get_client
        self._old_archive = app.storage.archive
        self._old_settings = app.settings

        app.get_client = MagicMock()
        app.storage.archive = MagicMock()
        app.storage.archive.get_recent_muc_nicks = MagicMock(
            return_value=["Harry", "Joe"]
        )

    def tearDown(self) -> None:
        app.get_client = self._old_get_client
        app.storage.archive = self._old_archive
        app.settings = self._old_settings


class TestGenerateCompletions(TabCompletionTestCase):
    def setUp(self) -> None:
        super().setUp()

        participant_names = [
            "Hugo",
            "Herbert",
            "Robert",
            "Daisy",
            "xavier",
            "7user",
        ]

        participants = [_get_mock_participant(name) for name in participant_names]

        contact = MagicMock(spec_set=GroupchatContact)
        contact.get_participants = MagicMock(return_value=participants)
        # Own nick must never be suggested
        contact.nickname = "Alice"

        gen = OccupantsTabCompleter(MagicMock())
        gen._contact = contact

        self._gen = gen
        self._contact = contact

        self._get_recent_nicks = MagicMock(
            return_value=["Harry", "Joe", "Hugo", "Alice", "Harry"]
        )
        app.storage.archive.get_recent_muc_nicks = self._get_recent_nicks

    def test_generate_completions_from_messages(self) -> None:
        completions = self._gen._generate_completions_from_messages(None)
        # Most recent first, own nick skipped, duplicates removed
        self.assertEqual(completions, ["Harry", "Joe", "Hugo"])

    def test_generate_completions_from_messages_with_prefix(self) -> None:
        completions = self._gen._generate_completions_from_messages("h")
        # Prefix matching is case-insensitive
        self.assertEqual(completions, ["Harry", "Hugo"])

    def test_generate_completions_from_messages_limited(self) -> None:
        # Only the most recent nicks are requested from the message
        # history
        self._gen._generate_completions_from_messages(None)

        self._get_recent_nicks.assert_called_once_with(
            self._contact.account,
            self._contact.jid,
            limit=MAX_COMPLETIONS,
        )

    def test_generate_completions_from_occupants(self) -> None:
        completions = self._gen._generate_completions_from_occupants("")
        # Nicks that have recently written something first, then the
        # remaining nicks in lexicographical order
        self.assertEqual(
            completions,
            [
                "Harry",
                "Joe",
                "Hugo",
                "7user",
                "Daisy",
                "Herbert",
                "Robert",
                "xavier",
            ],
        )

    def test_generate_completions_from_occupants_with_prefix(self) -> None:
        completions = self._gen._generate_completions_from_occupants("h")
        self.assertEqual(completions, ["Harry", "Hugo", "Herbert"])


class TestComputeNextCompletion(unittest.TestCase):
    def test_first_completion_in_middle_of_text(self) -> None:
        text = "Hey bo"
        new_text, index, cursor = OccupantsTabCompleter._compute_next_completion(
            text,
            4,  # start of the word being completed
            len(text),  # cursor at the end of the input
            ["Bob", "Bobby"],
            -1,
            False,
            ",",
        )
        self.assertEqual(new_text, "Hey Bob ")
        self.assertEqual(index, 0)
        self.assertEqual(cursor, 8)

    def test_cycle_forward_wraps(self) -> None:
        # "Hey Bob " after the first completion; 4 is the anchor of the
        # session, the offset the completion was inserted at
        text = "Hey Bob "
        new_text, index, _ = OccupantsTabCompleter._compute_next_completion(
            text,
            4,
            len(text),
            ["Bob", "Bobby"],
            0,
            False,
            ",",
        )
        self.assertEqual(new_text, "Hey Bobby ")
        self.assertEqual(index, 1)

        new_text, index, _ = OccupantsTabCompleter._compute_next_completion(
            "Hey Bobby ",
            4,
            len("Hey Bobby "),
            ["Bob", "Bobby"],
            1,
            False,
            ",",
        )
        # Wraps around to the first completion
        self.assertEqual(new_text, "Hey Bob ")
        self.assertEqual(index, 0)

    def test_cycle_backwards_wraps(self) -> None:
        text = "Hey Bob "
        new_text, index, _ = OccupantsTabCompleter._compute_next_completion(
            text,
            4,
            len(text),
            ["Bob", "Bobby"],
            0,
            True,
            ",",
        )
        # Wraps around to the last completion
        self.assertEqual(new_text, "Hey Bobby ")
        self.assertEqual(index, 1)

    def test_completion_at_start_of_text_appends_mention_char(self) -> None:
        new_text, index, cursor = OccupantsTabCompleter._compute_next_completion(
            "bo",
            0,
            2,
            ["Bob", "Bobby"],
            -1,
            False,
            ",",
        )
        # The word is the whole input, so it is treated as a mention
        self.assertEqual(new_text, "Bob, ")
        self.assertEqual(index, 0)
        self.assertEqual(cursor, 5)

        new_text, index, _ = OccupantsTabCompleter._compute_next_completion(
            "Bob, ",
            0,
            len("Bob, "),
            ["Bob", "Bobby"],
            0,
            False,
            ",",
        )
        # Cycles in place, mention char is kept
        self.assertEqual(new_text, "Bobby, ")
        self.assertEqual(index, 1)

    def test_preserves_text_after_cursor(self) -> None:
        new_text, index, cursor = OccupantsTabCompleter._compute_next_completion(
            "Hey bo and hi",
            4,  # start of the word being completed
            6,  # end of the word being completed
            ["Bob", "Bobby"],
            -1,
            False,
            ",",
        )
        # The space after the word is replaced by the suffix instead of
        # being duplicated
        self.assertEqual(new_text, "Hey Bob and hi")
        self.assertEqual(index, 0)
        self.assertEqual(cursor, 8)

    def test_mention_suffix_replaces_following_space(self) -> None:
        new_text, index, cursor = OccupantsTabCompleter._compute_next_completion(
            "bo are you there?",
            0,  # start of the word being completed
            2,  # end of the word being completed
            ["Bob"],
            -1,
            False,
            ",",
        )
        # The word is the whole input so far and is followed by the
        # mention suffix, without duplicating the following space
        self.assertEqual(new_text, "Bob, are you there?")
        self.assertEqual(index, 0)
        self.assertEqual(cursor, 5)

    def test_newline_after_word_is_kept(self) -> None:
        new_text, index, cursor = OccupantsTabCompleter._compute_next_completion(
            "bo\nand hi",
            0,  # start of the word being completed
            2,  # end of the word being completed
            ["Bob"],
            -1,
            False,
            ",",
        )
        # The newline is kept as is, no suffix is appended
        self.assertEqual(new_text, "Bob\nand hi")
        self.assertEqual(index, 0)
        self.assertEqual(cursor, 3)


class FakeTextIter:
    def __init__(self, buffer: FakeTextBuffer, offset: int) -> None:
        self._buffer = buffer
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset

    def backward_search(self, char: str, _flags: int):
        index = self._buffer.text.rfind(char, 0, self._offset)
        if index == -1:
            return None
        return (FakeTextIter(self._buffer, index), None)

    def forward_search(self, char: str, _flags: int):
        index = self._buffer.text.find(char, self._offset)
        if index == -1:
            return None
        return (FakeTextIter(self._buffer, index), None)


class FakeTextBuffer:
    def __init__(self, text: str) -> None:
        self.text = text
        self._insert_offset = len(text)
        self._insert_mark = object()

    def get_start_iter(self) -> FakeTextIter:
        return FakeTextIter(self, 0)

    def get_end_iter(self) -> FakeTextIter:
        return FakeTextIter(self, len(self.text))

    def get_insert(self) -> object:
        return self._insert_mark

    def get_iter_at_mark(self, _mark: object) -> FakeTextIter:
        return FakeTextIter(self, self._insert_offset)

    def get_iter_at_offset(self, offset: int) -> FakeTextIter:
        return FakeTextIter(self, offset)

    def get_text(
        self, start: FakeTextIter, end: FakeTextIter, _include_hidden: bool
    ) -> str:
        return self.text[start.get_offset() : end.get_offset()]

    def set_text(self, new_text: str) -> None:
        self.text = new_text
        self._insert_offset = 0

    def place_cursor(self, text_iter: FakeTextIter) -> None:
        self._insert_offset = text_iter.get_offset()

    def insert_at_cursor(self, new_text: str) -> None:
        self.text = (
            self.text[: self._insert_offset]
            + new_text
            + self.text[self._insert_offset :]
        )
        self._insert_offset += len(new_text)


NO_MODIFIERS = Gdk.ModifierType(0)


class TestOnKeyPressed(TabCompletionTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.buffer = FakeTextBuffer("Hey bo")
        self.message_input = MagicMock()
        self.message_input.get_buffer.return_value = self.buffer

        self.contact = MagicMock(spec_set=GroupchatContact)
        self.contact.nickname = "Alice"
        self.contact.get_participants = MagicMock(
            return_value=[
                _get_mock_participant("Bob"),
                _get_mock_participant("Bobby"),
            ]
        )

        self.completer = OccupantsTabCompleter(self.message_input)
        self.completer.switch_contact(self.contact)

        app.settings = MagicMock()
        app.settings.get = MagicMock(return_value=",")
        app.storage.archive.get_recent_muc_nicks = MagicMock(return_value=[])

    def _press(self, keyval: int, state: Gdk.ModifierType = NO_MODIFIERS) -> bool:
        # The controller argument is not used by the handler
        return self.completer._on_key_pressed(None, keyval, 0, state)  # type: ignore

    def test_tab_in_group_chat_completes_first_candidate(self) -> None:
        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Hey Bob ")

    def test_tab_cycles_forward_and_wraps(self) -> None:
        for expected in ("Hey Bob ", "Hey Bobby ", "Hey Bob "):
            self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
            self.assertEqual(self.buffer.text, expected)

    def test_shift_tab_goes_backwards(self) -> None:
        # On X11, Shift+Tab is reported as Tab with the shift modifier set
        self._press(Gdk.KEY_Tab)
        self._press(Gdk.KEY_Tab, Gdk.ModifierType.SHIFT_MASK)
        self.assertEqual(self.buffer.text, "Hey Bobby ")

    def test_iso_left_tab_goes_backwards(self) -> None:
        # On Wayland, Shift+Tab is reported as ISO_Left_Tab
        self._press(Gdk.KEY_Tab)
        self._press(Gdk.KEY_ISO_Left_Tab)
        self.assertEqual(self.buffer.text, "Hey Bobby ")

    def test_tab_without_candidates_does_nothing(self) -> None:
        self.buffer = FakeTextBuffer("xyz")
        self.message_input.get_buffer.return_value = self.buffer

        # The key press is consumed: nothing is inserted and the input
        # does not lose the focus to the next widget
        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "xyz")
        self.assertFalse(self.completer._active)

    def test_tab_in_bare_chat_inserts_tab_character(self) -> None:
        self.completer.switch_contact(MagicMock(spec_set=BareContact))

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Hey bo\t")

    def test_ctrl_tab_is_propagated(self) -> None:
        self.assertEqual(
            self._press(Gdk.KEY_Tab, Gdk.ModifierType.CONTROL_MASK),
            Gdk.EVENT_PROPAGATE,
        )
        self.assertEqual(self.buffer.text, "Hey bo")
        self.assertFalse(self.completer._active)

    def test_shift_press_keeps_session_active(self) -> None:
        self._press(Gdk.KEY_Tab)
        self.assertTrue(self.completer._active)

        self.assertEqual(self._press(Gdk.KEY_Shift_L), Gdk.EVENT_PROPAGATE)
        self.assertTrue(self.completer._active)

    def test_typing_after_completion_does_not_swallow_text(self) -> None:
        # Regression test: text typed after a completion must not be
        # dropped when Tab is pressed again. The input method consumes
        # typed characters before the key controller sees them, so the
        # session cannot be ended by key events; the buffer content is
        # compared instead.
        self.buffer = FakeTextBuffer("nic")
        self.message_input.get_buffer.return_value = self.buffer
        self.contact.get_participants = MagicMock(
            return_value=[
                _get_mock_participant("Nick"),
                _get_mock_participant("AnotherNick"),
            ]
        )

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Nick, ")

        self.buffer.insert_at_cursor("more text here anot")

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Nick, more text here AnotherNick ")

    def test_typing_after_completion_completes_current_word(self) -> None:
        self._press(Gdk.KEY_Tab)
        self.assertEqual(self.buffer.text, "Hey Bob ")

        self.buffer.insert_at_cursor("and bobb")

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Hey Bob and Bobby ")

    def test_cursor_inside_word_completes_whole_word(self) -> None:
        # The cursor is placed inside the word: the whole word is
        # replaced and the remainder of the word is not orphaned
        self.buffer = FakeTextBuffer("Hey bo and hi")
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(5))
        self.message_input.get_buffer.return_value = self.buffer

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Hey Bob and hi")

    def test_cleared_input_starts_new_session(self) -> None:
        self._press(Gdk.KEY_Tab)
        self.assertEqual(self.buffer.text, "Hey Bob ")

        # The input is cleared, e.g. when a draft is restored
        self.buffer.set_text("")
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(0))
        app.storage.archive.get_recent_muc_nicks = MagicMock(return_value=["Harry"])

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Harry, ")

    def test_cursor_move_ends_session(self) -> None:
        self._press(Gdk.KEY_Tab)
        self.assertEqual(self.buffer.text, "Hey Bob ")

        # The cursor is moved into the first word: the session is over,
        # so Tab does not cycle "Bob" in place anymore
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(3))

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Hey Bob ")

    def test_empty_word_completes_from_messages(self) -> None:
        self.buffer = FakeTextBuffer("Hey ")
        self.message_input.get_buffer.return_value = self.buffer
        app.storage.archive.get_recent_muc_nicks = MagicMock(
            return_value=["Harry", "Joe"]
        )

        self.assertEqual(self._press(Gdk.KEY_Tab), Gdk.EVENT_STOP)
        self.assertEqual(self.buffer.text, "Hey Harry ")


if __name__ == "__main__":
    unittest.main()
