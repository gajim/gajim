# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Optional
from typing import TYPE_CHECKING

import logging

from nbxmpp.structs import PresenceProperties

from gi.repository import Gdk

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.events import GcMessageReceived
from gajim.common.ged import EventHelper
from gajim.common.helpers import jid_is_blocked
from gajim.common.helpers import message_needs_highlight

if TYPE_CHECKING:
    from .message_input import MessageInputTextView

log = logging.getLogger('gajim.gui.groupchat_nick_completion')


class GroupChatNickCompletion(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)

        self._account: Optional[str] = None
        self._contact: Optional[types.GroupchatContactT] = None

        self._sender_list: list[str] = []
        self._highlight_list: list[str] = []
        self._nick_hits: list[str] = []
        self._last_key_tab = False

        self._nick_data: dict[str, tuple[list[str], list[str]]] = {}

        self.register_event(
            'gc-message-received', ged.GUI1, self._on_gc_message_received)

    def switch_contact(self, contact: types.GroupchatContactT) -> None:
        self._nick_hits.clear()
        self._last_key_tab = False

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)
            self._nick_data[str(self._contact.jid)] = (
                self._sender_list, self._highlight_list)

        nick_data = self._nick_data.get(str(contact.jid))
        if nick_data is None:
            self._sender_list.clear()
            self._highlight_list.clear()
        else:
            self._sender_list, self._highlight_list = nick_data

        self._account = contact.account
        self._contact = contact
        self._contact.connect(
            'user-nickname-changed', self._on_user_nickname_changed)

    def _on_user_nickname_changed(self,
                                  _contact: types.GroupchatContact,
                                  _signal_name: str,
                                  old_contact: types.GroupchatParticipant,
                                  new_contact: types.GroupchatParticipant,
                                  properties: PresenceProperties
                                  ) -> None:

        if properties.is_muc_self_presence:
            return

        old_name = old_contact.name
        new_name = new_contact.name

        log.debug('Contact %s renamed to %s', old_name, new_name)
        for lst in (self._highlight_list, self._sender_list):
            for idx, contact in enumerate(lst):
                if contact == old_name:
                    lst[idx] = new_name

    def _on_gc_message_received(self, event: GcMessageReceived) -> None:
        if event.properties.muc_nickname is None:
            # Message from server
            return

        client = app.get_client(event.account)
        gc_contact = client.get_module('Contacts').get_contact(
            event.room_jid)

        participant_nick = event.properties.muc_nickname
        if participant_nick == gc_contact.nickname:
            return

        highlight = message_needs_highlight(
            event.msgtxt, gc_contact.nickname, client.get_own_jid().bare)
        self._process_message(participant_nick, highlight, event.room_jid)

    def _process_message(self,
                         participant_nick: str,
                         highlight: bool,
                         room_jid: str
                         ) -> None:
        nick_data = self._nick_data.get(room_jid)
        if nick_data is None:
            return

        sender_list, highlight_list = nick_data
        if highlight:
            try:
                highlight_list.remove(participant_nick)
            except ValueError:
                pass
            if len(highlight_list) > 6:
                highlight_list.pop(0)  # remove older
            highlight_list.append(participant_nick)

        # TODO implement it in a more efficient way
        # Currently it's O(n*m + n*s), where n is the number of participants and
        # m is the number of messages processed, s - the number of times the
        # suggestions are requested
        #
        # A better way to do it would be to keep a dict: contact -> timestamp
        # with expected O(1) insert, and sort it by timestamps in O(n log n)
        # for each suggestion (currently generating the suggestions is O(n))
        # this would give the expected complexity of O(m + s * n log n)
        try:
            sender_list.remove(participant_nick)
        except ValueError:
            pass
        sender_list.append(participant_nick)

    def _generate_suggestions(self,
                              nicks: list[str],
                              beginning: str
                              ) -> list[str]:
        '''
        Generate the order of suggested MUC autocompletions

        `nicks` is the list of contacts currently participating in a MUC
        `beginning` is the text already typed by the user
        '''
        def _nick_matching(nick: str) -> bool:
            assert self._contact
            return (nick != self._contact.nickname and
                    nick.lower().startswith(beginning.lower()))

        if beginning == '':
            # empty message, so just suggest recent mentions
            potential_matches = self._highlight_list
        else:
            # nick partially typed, try completing it
            potential_matches = self._sender_list

        potential_matches_set = set(potential_matches)
        log.debug('Priority matches: %s', potential_matches_set)

        matches = [n for n in potential_matches if _nick_matching(n)]
        # the most recent nick is the last one on the list
        matches.reverse()

        # handle people who have not posted/mentioned us
        other_nicks = [
            n for n in nicks
            if _nick_matching(n) and n not in potential_matches_set
        ]
        other_nicks.sort(key=str.lower)
        log.debug('Other matches: %s', other_nicks)

        return matches + other_nicks

    def process_key_press(self,
                          textview: MessageInputTextView,
                          event: Gdk.EventKey
                          ) -> bool:
        if (event.get_state() & Gdk.ModifierType.SHIFT_MASK or
                event.get_state() & Gdk.ModifierType.CONTROL_MASK or
                event.keyval not in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Tab)):
            self._last_key_tab = False
            return False

        message_buffer = textview.get_buffer()
        start_iter, end_iter = message_buffer.get_bounds()
        cursor_position = message_buffer.get_insert()
        end_iter = message_buffer.get_iter_at_mark(cursor_position)
        text = message_buffer.get_text(start_iter, end_iter, False)

        text_split = text.split()

        # check if tab is pressed with empty message
        if text_split:  # if there are any words
            begin = text_split[-1]  # last word we typed
        else:
            begin = ''

        gc_refer_to_nick_char = app.settings.get('gc_refer_to_nick_char')
        with_refer_to_nick_char = False
        after_nick_len = 1  # the space that is printed after we type [Tab]

        # first part of this if : works fine even if refer_to_nick_char
        if (gc_refer_to_nick_char and
                text.endswith(gc_refer_to_nick_char + ' ')):
            with_refer_to_nick_char = True
            after_nick_len = len(gc_refer_to_nick_char + ' ')
        if (self._nick_hits and self._last_key_tab and
                text[:-after_nick_len].endswith(self._nick_hits[0])):
            # we should cycle
            # Previous nick in list may had a space inside, so we check text
            # and not text_split and store it into 'begin' var
            self._nick_hits.append(self._nick_hits[0])
            begin = self._nick_hits.pop(0)
        else:
            assert self._contact
            list_nick = self._contact.get_user_nicknames()
            list_nick = list(filter(self._jid_not_blocked, list_nick))

            log.debug('Nicks to be considered for autosuggestions: %s',
                      list_nick)
            self._nick_hits = self._generate_suggestions(
                nicks=list_nick, beginning=begin)
            log.debug('Nicks filtered for autosuggestions: %s',
                      self._nick_hits)
            if not self._nick_hits:
                self._last_key_tab = True
                return False

        if self._nick_hits:
            shell_like_completion = app.settings.get('shell_like_completion')

            if len(text_split) < 2 or with_refer_to_nick_char:
                # This is the 1st word of the line or no word or we are
                # cycling at the beginning, possibly with a space in one nick
                add = gc_refer_to_nick_char + ' '
            else:
                add = ' '
            start_iter = end_iter.copy()
            if (self._last_key_tab and
                    with_refer_to_nick_char or (text and text[-1] == ' ')):
                # have to accommodate for the added space from last completion
                # gc_refer_to_nick_char may be more than one char!
                start_iter.backward_chars(len(begin) + len(add))
            elif self._last_key_tab and not shell_like_completion:
                # have to accommodate for the added space from last
                # completion
                start_iter.backward_chars(
                    len(begin) + len(gc_refer_to_nick_char))
            else:
                start_iter.backward_chars(len(begin))

            assert self._account
            client = app.get_client(self._account)
            client.get_module('Chatstate').block_chatstates(
                self._contact, True)

            message_buffer.delete(start_iter, end_iter)
            # get a shell-like completion
            # if there's more than one nick for this completion, complete
            # only the part that all these nicks have in common
            if shell_like_completion and len(self._nick_hits) > 1:
                end = False
                completion = ''
                add = ''  # if nick is not complete, don't add anything
                while not end and len(completion) < len(self._nick_hits[0]):
                    completion = self._nick_hits[0][:len(completion) + 1]
                    for nick in self._nick_hits:
                        if completion.lower() not in nick.lower():
                            end = True
                            completion = completion[:-1]
                            break
                # if the current nick matches a COMPLETE existing nick,
                # and if the user tab TWICE, complete that nick (with the
                # "add")
                if self._last_key_tab:
                    for nick in self._nick_hits:
                        if nick == completion:
                            # The user seems to want this nick, so
                            # complete it as if it were the only nick
                            # available
                            add = gc_refer_to_nick_char + ' '
            else:
                completion = self._nick_hits[0]
            message_buffer.insert_at_cursor(completion + add)

            client.get_module('Chatstate').block_chatstates(
                self._contact, False)

        self._last_key_tab = True
        return True

    def _jid_not_blocked(self, resource: str) -> bool:
        assert self._account
        assert self._contact
        resource_contact = self._contact.get_resource(resource)
        return not jid_is_blocked(
            self._account, str(resource_contact.jid))
