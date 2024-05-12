# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0085: Chat State Notifications

from __future__ import annotations

from typing import Any

import time
from collections import defaultdict
from functools import wraps
from itertools import chain

from gi.repository import GLib
from nbxmpp.const import Chatstate as State
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Presence
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import types
from gajim.common.const import ClientState
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.structs import OutgoingMessage

INACTIVE_AFTER = 60
PAUSED_AFTER = 10
REMOTE_PAUSED_AFTER = 30


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
            StanzaHandler(
                name='presence',
                callback=self._presence_received,
                typ='error',
                priority=50,
            ),
            StanzaHandler(
                name='presence',
                callback=self._presence_received,
                typ='unavailable',
                priority=50,
            ),
            StanzaHandler(
                name='message',
                typ='chat',
                callback=self._process_chatstate,
                ns=Namespace.CHATSTATES,
                priority=46,
            ),
            StanzaHandler(
                name='message',
                typ='groupchat',
                callback=self._process_groupchat_chatstate,
                ns=Namespace.CHATSTATES,
                priority=46,
            ),
        ]

        # Our current chatstate with a specific contact
        self._chatstates: dict[JID, State] = {}

        # The current chatstate we received from a contact
        self._remote_chatstate: dict[JID, State] = {}
        # Cache set of participants that are composing for group chats,
        # to avoid having to iterate over all their chat states to determine
        # who is typing a message.
        self._muc_composers: dict[JID, set[GroupchatParticipant]] = defaultdict(set)

        self._remote_composing_timeouts: dict[tuple[JID, str], int] = {}

        self._last_keyboard_activity: dict[JID, float] = {}
        self._last_mouse_activity: dict[JID, float] = {}
        self._timeout_id = None
        self._delay_timeout_ids: dict[JID, int] = {}
        self._blocked: list[JID] = []
        self._enabled = False

        self._client.connect_signal('state-changed', self._on_client_state_changed)
        self._client.connect_signal('resume-failed', self._on_client_resume_failed)

    def _on_client_resume_failed(
        self, _client: types.Client, _signal_name: str
    ) -> None:
        self._set_enabled(False)

    def _on_client_state_changed(
        self, _client: types.Client, _signal_name: str, state: ClientState
    ) -> None:
        if state.is_disconnected:
            self._set_enabled(False)
        elif state.is_connected:
            self._set_enabled(True)

    def _set_enabled(self, value: bool) -> None:
        if self._enabled == value:
            return

        self._log.info('Chatstate module %s', 'enabled' if value else 'disabled')
        self._enabled = value

        if value:
            self._timeout_id = GLib.timeout_add_seconds(2, self._check_last_interaction)
        else:
            self.cleanup()
            self._client.get_module('Contacts').force_chatstate_update()

    @ensure_enabled
    def _presence_received(
        self, _con: types.xmppClient, _stanza: Presence, properties: PresenceProperties
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

    def _raise_if_necessary(self, properties: MessageProperties) -> None:
        if properties.chatstate != State.ACTIVE:
            raise NodeProcessed

    def _process_chatstate(
        self, _con: types.xmppClient, _stanza: Any, properties: MessageProperties
    ) -> None:
        if not properties.has_chatstate:
            return

        if (
            properties.is_self_message
            or properties.is_mam_message
            or properties.is_carbon_message
            and properties.carbon.is_sent
        ):
            return self._raise_if_necessary(properties)

        jid = properties.jid
        assert jid is not None

        m_type = 'chat'
        state = properties.chatstate
        self._remote_chatstate[jid] = state

        self._log.info('Recv: %-10s - %s (%s)', state, jid, m_type)

        contact = self._get_contact(jid)
        self._set_composing_timeout(contact, m_type, state)

        contact.notify('chatstate-update')

        return self._raise_if_necessary(properties)

    def _process_groupchat_chatstate(
        self, _con: types.xmppClient, _stanza: Any, properties: MessageProperties
    ) -> None:
        if not properties.has_chatstate:
            return

        jid = properties.jid
        assert jid is not None

        if properties.is_mam_message or jid.is_bare:
            return self._raise_if_necessary(properties)

        contact = self._get_contact(jid)
        assert isinstance(contact, GroupchatParticipant)
        if contact.is_self:
            return self._raise_if_necessary(properties)

        m_type = 'groupchat'
        state = properties.chatstate
        self._log.info('Recv: %-10s - %s (%s)', state, jid, m_type)

        self._set_composing_timeout(contact, m_type, state)

        muc = contact.room

        if state == State.COMPOSING:
            self._muc_composers[muc.jid].add(contact)
        else:
            self._muc_composers[muc.jid].discard(contact)

        muc.notify('chatstate-update')

        self._raise_if_necessary(properties)

    def _set_composing_timeout(
        self, contact: types.ContactT, m_type: str, state: State
    ) -> None:
        self._remove_remote_composing_timeout(contact, m_type)
        if state != State.COMPOSING:
            return

        # the spec does not cover any timeout for the composing action,
        # but if a contact's client does not send another chat state,
        # we don't want the GUI to show that they are "composing" forever
        self._remote_composing_timeouts[
            (contact.jid, m_type)
        ] = GLib.timeout_add_seconds(
            REMOTE_PAUSED_AFTER, self._on_remote_composing_timeout, contact, m_type
        )

    def _on_remote_composing_timeout(
        self, contact: types.ContactT, m_type: str
    ) -> None:
        self._remote_composing_timeouts.pop((contact.jid, m_type), None)
        self._log.info(
            'Set to ACTIVE after timeout has been reached - %s (%s)', contact, m_type
        )

        if m_type == 'groupchat':
            assert isinstance(contact, GroupchatParticipant)
            self._muc_composers[contact.room.jid].discard(contact)
            contact.room.notify('chatstate-update')
        else:
            self._remote_chatstate[contact.jid] = State.ACTIVE
            contact.notify('chatstate-update')

    def get_composers(self, jid: JID) -> list[GroupchatParticipant]:
        '''
        List of group chat participants that are composing (=typing) for a MUC.
        '''
        return list(self._muc_composers[jid])

    def _remove_remote_composing_timeout(self, contact: types.ContactT, m_type: str):
        source_id = self._remote_composing_timeouts.pop((contact.jid, m_type), None)
        if source_id is not None:
            self._log.debug(
                'Removing remote composing timeout of %s (%s)', contact, m_type
            )
            GLib.source_remove(source_id)

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

    def get_remote_chatstate(self, jid: JID) -> State | None:
        return self._remote_chatstate.get(jid)

    @ensure_enabled
    def set_active(self, contact: types.ChatContactT) -> None:
        if contact.settings.get('send_chatstate') == 'disabled':
            return
        self._last_mouse_activity[contact.jid] = time.time()
        self._chatstates[contact.jid] = State.ACTIVE

    def get_active_chatstate(self, contact: types.ChatContactT) -> str | None:
        # determines if we add 'active' on outgoing messages
        if contact.settings.get('send_chatstate') == 'disabled':
            return None

        if not contact.is_groupchat:
            # Don’t send chatstates to ourself
            if self._client.is_own_jid(contact.jid):
                return None

            if not contact.supports(Namespace.CHATSTATES):
                return None

        self.set_active(contact)
        return 'active'

    @ensure_enabled
    def block_chatstates(self, contact: types.ChatContactT, block: bool) -> None:
        # Block sending chatstates to a contact
        # Used for example if we cycle through the MUC nick list, which
        # produces a lot of buffer 'changed' signals from the input textview.
        # This would lead to sending ACTIVE -> COMPOSING -> ACTIVE ...
        if block:
            self._blocked.append(contact.jid)
        else:
            self._blocked.remove(contact.jid)

    @ensure_enabled
    def set_chatstate_delayed(self, contact: types.ChatContactT, state: State) -> None:
        # Used when we go from Composing -> Active after deleting all text
        # from the Textview. We delay the Active state because maybe the
        # User starts writing again.

        # Don’t send chatstates to ourself
        if self._client.is_own_jid(contact.jid):
            return

        self.remove_delay_timeout(contact)
        self._delay_timeout_ids[contact.jid] = GLib.timeout_add_seconds(
            2, self.set_chatstate, contact, state
        )

    @ensure_enabled
    def set_chatstate(self, contact: types.ChatContactT, state: State) -> None:
        # Don’t send chatstates to ourself
        if self._client.is_own_jid(contact.jid):
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
                self._log.info('Send last state: %-10s - %s', State.ACTIVE, contact)

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

    def _send_chatstate(self, contact: types.ChatContactT, chatstate: State) -> None:
        message = OutgoingMessage(
            account=self._account,
            contact=contact,
            chatstate=chatstate.value,
            play_sound=False,
        )

        self._client.send_message(message)

    @ensure_enabled
    def set_mouse_activity(self, contact: types.ChatContactT, was_paused: bool) -> None:
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

    def remove_all_timeouts(self) -> None:
        for timeout in chain(
            self._delay_timeout_ids.values(), self._remote_composing_timeouts.values()
        ):
            GLib.source_remove(timeout)
        self._delay_timeout_ids.clear()
        self._remote_composing_timeouts.clear()

    def cleanup(self) -> None:
        BaseModule.cleanup(self)
        self.remove_all_timeouts()
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        self._chatstates.clear()
        self._remote_chatstate.clear()
        self._last_keyboard_activity.clear()
        self._last_mouse_activity.clear()
        self._blocked = []
