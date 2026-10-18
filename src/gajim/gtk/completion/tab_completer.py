# SPDX-FileCopyrightText: Dino <https://github.com/dino/dino>
# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

"""Tab-based nickname completion for group chats.

The algorithm is modeled after Dino's tab completer for group chat
occupants:
https://github.com/dino/dino/blob/8d49d83b3b45ab22d7b9d945c4b32296b07cb49e/main/src/ui/chat_input/occupants_tab_completer.vala

- With given prefix: Complete from occupant list (nicks that have
  recently written something first, then the remaining nicks sorted
  lexicographically)
- W/o prefix: Complete from received messages (most recent first)
- At most MAX_COMPLETIONS nicks are taken from the message history
- Words are delimited by spaces and newlines, at the start of the input
  and in the middle of a text. The completed word extends to the next
  word boundary, so the cursor can also be placed inside a word.
- Tab completes the next suggestion, Shift+Tab the previous one, both
  wrapping around. The session ends as soon as the input text or the
  cursor position changes.
- If the completed word is the whole input so far, it is followed by the
  "refer to nick" character ("," by default) and a space, otherwise by
  a single space. A space directly following the word is replaced by the
  suffix, a newline is kept as is.

The message input view must be created with accepts-tab set to False.
Otherwise, the view handles the tab key internally before this completer's
key controller is notified. In a group chat without candidates, the tab
key press is not taken over and nothing is inserted. Outside of group
chats, the completer inserts a tab character to keep the previous
behavior.
"""

from __future__ import annotations

from typing import Final
from typing import TYPE_CHECKING

import logging

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT

if TYPE_CHECKING:
    from gajim.gtk.message_input import MessageInputTextView

log = logging.getLogger("gajim.gtk.completion.tab_completer")


MAX_COMPLETIONS: Final = 10


class OccupantsTabCompleter:
    def __init__(self, message_input: MessageInputTextView) -> None:
        self._message_input = message_input
        self._contact: ChatContactT | None = None

        self._completions: list[str] = []
        self._active = False
        self._index = -1
        # State captured at the last completion, used to detect whether the
        # user has typed or moved the cursor since then (which ends the
        # session) and to keep cycling the same anchor spot.
        self._anchor = 0
        # End of the input region that is replaced by the completion
        self._end = 0
        self._applied_text = ""
        self._applied_cursor = 0

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        message_input.add_controller(controller)

    def switch_contact(self, contact: ChatContactT | None) -> None:
        self._contact = contact
        self._reset()

    def _reset(self) -> None:
        self._completions = []
        self._active = False
        self._index = -1
        self._anchor = 0
        self._end = 0
        self._applied_text = ""
        self._applied_cursor = 0

    def _session_is_valid(self, text: str, cursor: int) -> bool:
        # The session is only valid while the buffer still exactly matches
        # what was produced by the last completion. Any keystroke or cursor
        # movement invalidates it.
        return self._applied_text == text and self._applied_cursor == cursor

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        is_tab = keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab)
        has_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if is_tab and has_ctrl:
            # Ctrl+Tab and Ctrl+Shift+Tab are reserved for switching chats
            if self._active:
                self._reset()
            return Gdk.EVENT_PROPAGATE

        if is_tab and not has_ctrl:
            contact = self._contact
            if isinstance(contact, GroupchatContact):
                buf = self._message_input.get_buffer()
                start, end = self._get_word_bounds()
                word = buf.get_text(start, end, False)
                cursor = buf.get_iter_at_mark(buf.get_insert()).get_offset()
                text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

                if not self._active or not self._session_is_valid(text, cursor):
                    # (Re)start the session: either the first Tab of a new
                    # word, or the input has changed since the last
                    # completion, so the previous session is stale.
                    self._reset()
                    if word == "":
                        self._completions = self._generate_completions_from_messages(
                            None
                        )
                    else:
                        self._completions = self._generate_completions_from_occupants(
                            word
                        )

                    if not self._completions:
                        # No candidates: do nothing, but keep the focus in
                        # the input (do not propagate the Tab to GTK's
                        # focus navigation).
                        return Gdk.EVENT_STOP

                    self._active = True
                    self._index = -1
                    self._anchor = start.get_offset()
                    self._end = end.get_offset()

                # Shift+Tab goes backwards; on X11 Shift+Tab is reported
                # as Tab with the shift modifier set
                backwards = keyval == Gdk.KEY_ISO_Left_Tab or bool(
                    state & Gdk.ModifierType.SHIFT_MASK
                )
                self._apply_next_completion(backwards)
                return Gdk.EVENT_STOP

            # Not a group chat, insert a tab character
            self._message_input.get_buffer().insert_at_cursor("\t")
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _get_word_bounds(self) -> tuple[Gtk.TextIter, Gtk.TextIter]:
        buf = self._message_input.get_buffer()
        cursor = buf.get_iter_at_mark(buf.get_insert())

        # The word is delimited by the last space or newline
        # before the cursor
        last_boundary = -1
        for char in (" ", "\n"):
            result = cursor.backward_search(
                char,
                Gtk.TextSearchFlags.TEXT_ONLY | Gtk.TextSearchFlags.CASE_INSENSITIVE,
            )
            if result is not None:
                last_boundary = max(last_boundary, result[0].get_offset())

        start = buf.get_iter_at_offset(last_boundary + 1)

        # The word extends to the next space or newline after the
        # cursor, so that the cursor can also be placed inside the word
        next_boundary: int | None = None
        for char in (" ", "\n"):
            result = cursor.forward_search(
                char,
                Gtk.TextSearchFlags.TEXT_ONLY | Gtk.TextSearchFlags.CASE_INSENSITIVE,
            )
            if result is not None:
                offset = result[0].get_offset()
                if next_boundary is None or offset < next_boundary:
                    next_boundary = offset

        if next_boundary is not None:
            end = buf.get_iter_at_offset(next_boundary)
        else:
            end = buf.get_end_iter()

        return start, end

    def _apply_next_completion(self, backwards: bool) -> None:
        buf = self._message_input.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

        refer_char = app.settings.get("gc_refer_to_nick_char")
        new_text, self._index, cursor_offset = self._compute_next_completion(
            text,
            self._anchor,
            self._end,
            self._completions,
            self._index,
            backwards,
            refer_char,
        )

        buf.set_text(new_text)
        buf.place_cursor(buf.get_iter_at_offset(cursor_offset))

        self._applied_text = new_text
        self._applied_cursor = cursor_offset
        self._end = cursor_offset

    @staticmethod
    def _compute_next_completion(
        text: str,
        start_index: int,
        end_index: int,
        completions: list[str],
        index: int,
        backwards: bool,
        refer_char: str,
    ) -> tuple[str, int, int]:
        """Compute the text after cycling to the next or previous
        completion.

        The region between start_index and end_index is replaced by the
        new completion, followed by the suffix.

        Returns (new_text, new_index, new_cursor_offset).
        """
        if backwards:
            index = max(index, 0) - 1
            if index < 0:
                index = len(completions) - 1
        else:
            index = (index + 1) % len(completions)

        completion = completions[index]

        if start_index == 0:
            # The completed word is the whole input so far, so it is
            # treated as a mention of the participant
            suffix = f"{refer_char} "
        else:
            suffix = " "

        # A word boundary character directly after the word is not
        # duplicated: a space is replaced by the suffix, a newline is
        # kept as is (without appending the suffix)
        if end_index < len(text) and text[end_index] == "\n":
            return (
                text[:start_index] + completion + text[end_index:],
                index,
                start_index + len(completion),
            )

        if end_index < len(text) and text[end_index] == " ":
            # The space is replaced by the suffix
            end_index += 1

        new_text = text[:start_index] + completion + suffix + text[end_index:]
        return new_text, index, start_index + len(completion) + len(suffix)

    def _generate_completions_from_messages(
        self, prefix: str | None = None
    ) -> list[str]:
        contact = self._contact
        assert isinstance(contact, GroupchatContact)

        # Nicks from received messages, most recent first; the storage
        # layer returns at most MAX_COMPLETIONS nicks
        ret: list[str] = []
        for nick in app.storage.archive.get_recent_muc_nicks(
            contact.account, contact.jid, limit=MAX_COMPLETIONS
        ):
            if not nick or nick == contact.nickname:
                continue

            if prefix is not None and not nick.lower().startswith(prefix.lower()):
                continue

            if nick in ret:
                continue

            ret.append(nick)
        return ret

    def _generate_completions_from_occupants(self, prefix: str) -> list[str]:
        contact = self._contact
        assert isinstance(contact, GroupchatContact)

        # First suggest nicks that have recently written something
        ret = self._generate_completions_from_messages(prefix)

        # Then, suggest other nicks in lexicographical order
        other_nicks = sorted(
            participant.name
            for participant in contact.get_participants()
            if participant.name != contact.nickname
            and participant.name.lower().startswith(prefix.lower())
            and participant.name not in ret
        )
        ret.extend(other_nicks)
        return ret
