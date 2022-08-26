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

# XEP-0085: Chat State Notifications

from __future__ import annotations

from typing import Any
from typing import Optional

import time
from functools import wraps

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Presence
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import Chatstate as State

from gi.repository import GLib

from gajim.common import types
from gajim.common.const import ClientState
from gajim.common.structs import OutgoingMessage
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import BareContact

INACTIVE_AFTER = 60
PAUSED_AFTER = 10


def ensure_enabled(func: Any) -> Any:
    @wraps(func)
    def func_wrapper(self: Any, *args: Any, **kwargs: Any):
        # pylint: disable=protected-access
        if not self._enabled:
            return None
        return func(self, *args, **kwargs)
    return func_wrapper


class Chatstate(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._presence_received,
                          typ='error',
                          priority=50),
            StanzaHandler(name='presence',
                          callback=self._presence_received,
                          typ='unavailable',
                          priority=50),
            StanzaHandler(name='message',
                          callback=self._process_chatstate,
                          ns=Namespace.CHATSTATES,
                          priority=46),
        ]

        # Our current chatstate with a specific contact
        self._chatstates: dict[JID, State] = {}

        # The current chatstate we received from a contact
        self._remote_chatstate: dict[JID, State] = {}

        self._last_keyboard_activity: dict[JID, float] = {}
        self._last_mouse_activity: dict[JID, float] = {}
        self._timeout_id = None
        self._delay_timeout_ids: dict[JID, int] = {}
        self._blocked: list[JID] = []
        self._enabled = False

        self._con.connect_signal('state-changed', self._on_client_state_changed)
        self._con.connect_signal('resume-failed', self._on_client_resume_failed)

    def _on_client_resume_failed(self,
                                 _client: types.Client,
                                 _signal_name: str
                                 ) -> None:
        self._set_enabled(False)

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 state: ClientState
                                 ) -> None:
        if state.is_disconnected:
            self._set_enabled(False)
        elif state.is_connected:
            self._set_enabled(True)

    def _set_enabled(self, value: bool) -> None:
        if self._enabled == value:
            return

        self._log.info('Chatstate module %s',
                       'enabled' if value else 'disabled')
        self._enabled = value

        if value:
            self._timeout_id = GLib.timeout_add_seconds(
                2, self._check_last_interaction)
        else:
            self.cleanup()
            self._con.get_module('Contacts').force_chatstate_update()

    @ensure_enabled
    def _presence_received(self,
                           _con: types.xmppClient,
                           _stanza: Presence,
                           properties: PresenceProperties
                           ) -> None:

        if properties.is_self_bare:
            return

        jid = properties.jid

        assert jid is not None
        self._remote_chatstate.pop(jid, None)
        self._chatstates.pop(jid, None)
        self._last_mouse_activity.pop(jid, None)
        self._last_keyboard_activity.pop(jid, None)

        self._log.info('Reset chatstate for %s', jid)

        contact = self._get_contact(jid)
        if contact.is_groupchat:
            return

        contact.notify('chatstate-update')

    def _process_chatstate(self,
                           _con: types.xmppClient,
                           _stanza: Any,
                           properties: MessageProperties
                           ) -> None:
        if properties.type.is_error:
            return

        if not properties.has_chatstate:
            return

        if (properties.is_self_message or
                not properties.type.is_chat or
                properties.is_mam_message or
                properties.is_carbon_message and properties.carbon.is_sent):
            return

        assert properties.jid is not None
        self._remote_chatstate[properties.jid] = properties.chatstate

        self._log.info('Recv: %-10s - %s', properties.chatstate, properties.jid)

        contact = self._get_contact(properties.jid)
        if contact is None:
            return

        contact.notify('chatstate-update')

    @ensure_enabled
    def _check_last_interaction(self) -> bool:
        now = time.time()
        for jid in list(self._last_mouse_activity.keys()):
            time_ = self._last_mouse_activity[jid]
            current_state = self._chatstates.get(jid)
            if current_state is None:
                self._last_mouse_activity.pop(jid, None)
                self._last_keyboard_activity.pop(jid, None)
                continue

            if current_state in (State.GONE, State.INACTIVE):
                continue

            new_chatstate = None
            if now - time_ > INACTIVE_AFTER:
                new_chatstate = State.INACTIVE

            elif current_state == State.COMPOSING:
                key_time = self._last_keyboard_activity[jid]
                if now - key_time > PAUSED_AFTER:
                    new_chatstate = State.PAUSED

            if new_chatstate is not None:
                if self._chatstates.get(jid) != new_chatstate:
                    contact = self._get_contact(jid)
                    self.set_chatstate(contact, new_chatstate)

        return GLib.SOURCE_CONTINUE

    def get_remote_chatstate(self, jid: JID) -> Chatstate:
        return self._remote_chatstate.get(jid)

    @ensure_enabled
    def set_active(self, contact: types.ChatContactT) -> None:
        if contact.settings.get('send_chatstate') == 'disabled':
            return
        self._last_mouse_activity[contact.jid] = time.time()
        self._chatstates[contact.jid] = State.ACTIVE

    def get_active_chatstate(self,
                             contact: types.ChatContactT
                             ) -> Optional[str]:
        # determines if we add 'active' on outgoing messages
        if contact.settings.get('send_chatstate') == 'disabled':
            return None

        if not contact.is_groupchat:
            # Don’t send chatstates to ourself
            if self._con.get_own_jid().bare_match(contact.jid):
                return None

            if not contact.supports(Namespace.CHATSTATES):
                return None

        self.set_active(contact)
        return 'active'

    @ensure_enabled
    def block_chatstates(self,
                         contact: types.ChatContactT,
                         block: bool
                         ) -> None:
        # Block sending chatstates to a contact
        # Used for example if we cycle through the MUC nick list, which
        # produces a lot of buffer 'changed' signals from the input textview.
        # This would lead to sending ACTIVE -> COMPOSING -> ACTIVE ...
        if block:
            self._blocked.append(contact.jid)
        else:
            self._blocked.remove(contact.jid)

    @ensure_enabled
    def set_chatstate_delayed(self,
                              contact: types.ChatContactT,
                              state: State
                              ) -> None:
        # Used when we go from Composing -> Active after deleting all text
        # from the Textview. We delay the Active state because maybe the
        # User starts writing again.

        # Don’t send chatstates to ourself
        if self._con.get_own_jid().bare_match(contact.jid):
            return

        self.remove_delay_timeout(contact)
        self._delay_timeout_ids[contact.jid] = GLib.timeout_add_seconds(
            2, self.set_chatstate, contact, state)

    @ensure_enabled
    def set_chatstate(self, contact: types.ChatContactT, state: State) -> None:
        # Don’t send chatstates to ourself
        if self._con.get_own_jid().bare_match(contact.jid):
            return

        if contact.jid in self._blocked:
            return

        self.remove_delay_timeout(contact)
        current_state = self._chatstates.get(contact.jid)
        setting = contact.settings.get('send_chatstate')
        if setting == 'disabled':
            # Send a last 'active' state after user disabled chatstates
            if current_state is not None:
                self._log.info('Disabled for %s', contact)
                self._log.info('Send last state: %-10s - %s',
                               State.ACTIVE, contact)

                self._send_chatstate(contact, State.ACTIVE)

            self._chatstates.pop(contact.jid, None)
            self._last_mouse_activity.pop(contact.jid, None)
            self._last_keyboard_activity.pop(contact.jid, None)
            return

        if isinstance(contact, BareContact):
            if not contact.is_subscribed:
                self._log.debug('Contact not subscribed: %s', contact)
                return

            if not contact.is_available:
                self._log.debug('Contact offline: %s', contact)
                return

        elif isinstance(contact, GroupchatParticipant):
            if not contact.is_available:
                self._log.debug('Contact offline: %s', contact)
                return

        else:
            if not contact.is_joined:
                self._log.debug('Groupchat not joined: %s', contact)
                return

        if state in (State.ACTIVE, State.COMPOSING):
            self._last_mouse_activity[contact.jid] = time.time()

        if setting == 'composing_only':
            if state in (State.INACTIVE, State.GONE):
                state = State.ACTIVE

        if current_state == state:
            return

        self._log.info('Send: %-10s - %s', state, contact)

        self._send_chatstate(contact, state)

        self._chatstates[contact.jid] = state

    def _send_chatstate(self,
                        contact: types.ChatContactT,
                        chatstate: State
                        ) -> None:
        type_ = 'groupchat' if contact.is_groupchat else 'chat'
        message = OutgoingMessage(account=self._account,
                                  contact=contact,
                                  message=None,
                                  type_=type_,
                                  chatstate=chatstate.value,
                                  play_sound=False)

        self._con.send_message(message)

    @ensure_enabled
    def set_mouse_activity(self,
                           contact: types.ChatContactT,
                           was_paused: bool
                           ) -> None:
        if contact.settings.get('send_chatstate') == 'disabled':
            return
        self._last_mouse_activity[contact.jid] = time.time()
        if self._chatstates.get(contact.jid) == State.INACTIVE:
            if was_paused:
                self.set_chatstate(contact, State.PAUSED)
            else:
                self.set_chatstate(contact, State.ACTIVE)

    @ensure_enabled
    def set_keyboard_activity(self, contact: types.ChatContactT) -> None:
        self._last_keyboard_activity[contact.jid] = time.time()

    def remove_delay_timeout(self, contact: types.ChatContactT) -> None:
        timeout = self._delay_timeout_ids.get(contact.jid)
        if timeout is not None:
            GLib.source_remove(timeout)
            del self._delay_timeout_ids[contact.jid]

    def remove_all_delay_timeouts(self) -> None:
        for timeout in self._delay_timeout_ids.values():
            GLib.source_remove(timeout)
        self._delay_timeout_ids.clear()

    def cleanup(self) -> None:
        self.remove_all_delay_timeouts()
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        self._chatstates.clear()
        self._remote_chatstate.clear()
        self._last_keyboard_activity.clear()
        self._last_mouse_activity.clear()
        self._blocked = []
