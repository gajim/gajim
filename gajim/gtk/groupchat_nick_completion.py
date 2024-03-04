# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gi.repository import Gdk
from gi.repository import GtkSource

from gajim.common import app
from gajim.common import ged
from gajim.common.events import GcMessageReceived
from gajim.common.ged import EventHelper
from gajim.common.helpers import jid_is_blocked
from gajim.common.modules.contacts import GroupchatContact

log = logging.getLogger('gajim.gtk.groupchat_nick_completion')


class GroupChatNickCompletion(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)

        self._contact: GroupchatContact | None = None

        self._suggestions: list[str] = []
        self._last_key_tab = False

        self.register_event(
            'gc-message-received', ged.GUI2, self._on_gc_message_received)

    def switch_contact(self, contact: GroupchatContact) -> None:
        self._suggestions.clear()
        self._last_key_tab = False
        self._contact = contact

    def process_key_press(self,
                          source_view: GtkSource.View,
                          event: Gdk.EventKey
                          ) -> bool:

        if (event.get_state() & Gdk.ModifierType.SHIFT_MASK or
                event.get_state() & Gdk.ModifierType.CONTROL_MASK or
                event.keyval not in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Tab)):
            self._last_key_tab = False
            return False

        message_buffer = source_view.get_buffer()
        start_iter, end_iter = message_buffer.get_bounds()
        cursor_position = message_buffer.get_insert()
        end_iter = message_buffer.get_iter_at_mark(cursor_position)
        text = message_buffer.get_text(start_iter, end_iter, False)

        if text.split():
            # Store last word for autocompletion
            prefix = text.split()[-1]
        else:
            prefix = ''

        # Configurable string to be displayed after the nick:
        # e.g. "user," or "user:"
        ref_ext = app.settings.get('gc_refer_to_nick_char')
        has_ref_ext = False

        # Default suffix to 1: space printed after completion
        suffix_len = 1

        if ref_ext and text.endswith(ref_ext + ' '):
            has_ref_ext = True
            suffix_len = len(ref_ext + ' ')

        if not self._last_key_tab or not self._suggestions:
            self._suggestions = self._generate_suggestions(prefix)

        if not self._suggestions:
            self._last_key_tab = True
            return False

        if (self._last_key_tab and
                text[:-suffix_len].endswith(self._suggestions[0])):
            # Cycle suggestions list
            self._suggestions.append(self._suggestions[0])
            prefix = self._suggestions.pop(0)

        if len(text.split()) < 2 or has_ref_ext:
            suffix = ref_ext + ' '
        else:
            suffix = ' '

        start_iter = end_iter.copy()
        if (self._last_key_tab and has_ref_ext or (text and text[-1] == ' ')):
            # Mind the added space from last completion;
            # ref_ext may also consist of more than one char
            start_iter.backward_chars(len(prefix) + len(suffix))
        else:
            start_iter.backward_chars(len(prefix))

        assert self._contact is not None
        client = app.get_client(self._contact.account)
        client.get_module('Chatstate').block_chatstates(self._contact, True)

        message_buffer.delete(start_iter, end_iter)
        completion = self._suggestions[0]
        message_buffer.insert_at_cursor(completion + suffix)

        client.get_module('Chatstate').block_chatstates(self._contact, False)

        self._last_key_tab = True

        return True

    def _generate_suggestions(self, prefix: str) -> list[str]:
        def _nick_matching(nick: str) -> bool:
            assert self._contact is not None
            if nick == self._contact.nickname:
                return False

            participant = self._contact.get_resource(nick)
            if jid_is_blocked(self._contact.account, str(participant.jid)):
                return False

            if prefix == '':
                return True

            return nick.lower().startswith(prefix.lower())

        assert self._contact is not None
        # Get recent nicknames from DB. This enables us to suggest
        # nicknames even if no message arrived since Gajim was started.
        recent_nicknames = app.storage.archive.get_recent_muc_nicks(
            self._contact)

        matches: list[str] = []
        for nick in recent_nicknames:
            if _nick_matching(nick):
                matches.append(nick)

        # Add all other MUC participants
        other_nicks: list[str] = []
        for contact in self._contact.get_participants():
            if _nick_matching(contact.name):
                if contact.name not in matches:
                    other_nicks.append(contact.name)
        other_nicks.sort(key=str.lower)

        return matches + other_nicks

    def _on_gc_message_received(self, event: GcMessageReceived) -> None:
        if self._contact is None:
            return

        if event.room_jid != self._contact.jid:
            return

        if not self._last_key_tab:
            # Clear suggestions if not actively using them
            # (new messages may have new nicks)
            self._suggestions.clear()
