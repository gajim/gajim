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

from typing import Any
from typing import Dict  # pylint: disable=unused-import
from typing import List  # pylint: disable=unused-import
from typing import Optional
from typing import Tuple

import time
from functools import wraps

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from gi.repository import GLib

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.const import Chatstate as State
from gajim.common.structs import OutgoingMessage
from gajim.common.modules.base import BaseModule

from gajim.common.types import ContactT
from gajim.common.types import ConnectionT


INACTIVE_AFTER = 60
PAUSED_AFTER = 10


def ensure_enabled(func):
    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        if not self.enabled:
            return None
        return func(self, *args, **kwargs)
    return func_wrapper


class Chatstate(BaseModule):
    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._presence_received),
            StanzaHandler(name='message',
                          callback=self._process_chatstate,
                          ns=Namespace.CHATSTATES,
                          priority=46),
        ]

        # Our current chatstate with a specific contact
        self._chatstates = {}  # type: Dict[str, State]

        self._last_keyboard_activity = {}  # type: Dict[str, float]
        self._last_mouse_activity = {}  # type: Dict[str, float]
        self._timeout_id = None
        self._delay_timeout_ids = {}  # type: Dict[str, str]
        self._blocked = []  # type: List[str]
        self._enabled = False

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
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
            self._chatstates = {}
            self._last_keyboard_activity = {}
            self._last_mouse_activity = {}
            self._blocked = []

    @ensure_enabled
    def _presence_received(self,
                           _con: ConnectionT,
                           stanza: nbxmpp.Presence,
                           _properties: Any) -> None:
        if stanza.getType() not in ('unavailable', 'error'):
            return

        full_jid = stanza.getFrom()
        if full_jid is None or self._con.get_own_jid().bare_match(full_jid):
            # Presence from ourself
            return

        contact = app.contacts.get_gc_contact(
            self._account, full_jid.bare, full_jid.resource)
        if contact is None:
            contact = app.contacts.get_contact_from_full_jid(
                self._account, str(full_jid))
        if contact is None:
            return

        if contact.chatstate is None:
            return

        if contact.is_gc_contact:
            jid = contact.get_full_jid()
        else:
            jid = contact.jid

        contact.chatstate = None
        self._chatstates.pop(jid, None)
        self._last_mouse_activity.pop(jid, None)
        self._last_keyboard_activity.pop(jid, None)

        self._log.info('Reset chatstate for %s', jid)

        app.nec.push_outgoing_event(
            NetworkEvent('chatstate-received',
                         account=self._account,
                         contact=contact))

    def _process_chatstate(self, _con, _stanza, properties):
        if not properties.has_chatstate:
            return

        if (properties.is_self_message or
                properties.type.is_groupchat or
                properties.is_mam_message or
                properties.is_carbon_message and properties.carbon.is_sent):
            return

        if properties.is_muc_pm:
            contact = app.contacts.get_gc_contact(
                self._account,
                properties.jid.bare,
                properties.jid.resource)
        else:
            contact = app.contacts.get_contact_from_full_jid(
                self._account, str(properties.jid))
        if contact is None:
            return

        contact.chatstate = properties.chatstate.value
        self._log.info('Recv: %-10s - %s', properties.chatstate, properties.jid)
        app.nec.push_outgoing_event(
            NetworkEvent('chatstate-received',
                         account=self._account,
                         contact=contact))

    @ensure_enabled
    def _check_last_interaction(self) -> GLib.SOURCE_CONTINUE:
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
                    contact = app.contacts.get_contact(self._account, jid)
                    if contact is None:
                        room, nick = app.get_room_and_nick_from_fjid(jid)
                        contact = app.contacts.get_gc_contact(
                            self._account, room, nick)
                        if contact is not None:
                            contact = contact.as_contact()
                        else:
                            # Contact not found, maybe we left the group chat
                            # or the contact was removed from the roster
                            self._log.info(
                                'Contact %s not found, reset chatstate', jid)
                            self._chatstates.pop(jid, None)
                            self._last_mouse_activity.pop(jid, None)
                            self._last_keyboard_activity.pop(jid, None)
                            continue
                self.set_chatstate(contact, new_chatstate)

        return GLib.SOURCE_CONTINUE

    @ensure_enabled
    def set_active(self, contact: ContactT) -> None:
        if contact.settings.get('send_chatstate') == 'disabled':
            return
        self._last_mouse_activity[contact.jid] = time.time()
        self._chatstates[contact.jid] = State.ACTIVE

    def get_active_chatstate(self, contact: ContactT) -> Optional[str]:
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
    def block_chatstates(self, contact: ContactT, block: bool) -> None:
        # Block sending chatstates to a contact
        # Used for example if we cycle through the MUC nick list, which
        # produces a lot of text-changed signals from the textview. This
        # Would lead to sending ACTIVE -> COMPOSING -> ACTIVE ...
        if block:
            self._blocked.append(contact.jid)
        else:
            self._blocked.remove(contact.jid)

    @ensure_enabled
    def set_chatstate_delayed(self, contact: ContactT, state: State) -> None:
        # Used when we go from Composing -> Active after deleting all text
        # from the Textview. We delay the Active state because maybe the
        # User starts writing again.
        self.remove_delay_timeout(contact)
        self._delay_timeout_ids[contact.jid] = GLib.timeout_add_seconds(
            2, self.set_chatstate, contact, state)

    @ensure_enabled
    def set_chatstate(self, contact: ContactT, state: State) -> None:
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
                self._log.info('Disabled for %s', contact.jid)
                self._log.info('Send last state: %-10s - %s',
                               State.ACTIVE, contact.jid)

                self._send_chatstate(contact, str(State.ACTIVE))

            self._chatstates.pop(contact.jid, None)
            self._last_mouse_activity.pop(contact.jid, None)
            self._last_keyboard_activity.pop(contact.jid, None)
            return

        if not contact.is_groupchat:
            # Don’t leak presence to contacts
            # which are not allowed to see our status
            if not contact.is_pm_contact:
                if contact and contact.sub in ('to', 'none'):
                    self._log.info('Contact not subscribed: %s', contact.jid)
                    return

            if contact.show == 'offline':
                self._log.info('Contact offline: %s', contact.jid)
                return

            if not contact.supports(Namespace.CHATSTATES):
                self._log.info('Chatstates not supported: %s', contact.jid)
                return

        if state in (State.ACTIVE, State.COMPOSING):
            self._last_mouse_activity[contact.jid] = time.time()

        if setting == 'composing_only':
            if state in (State.INACTIVE, State.GONE):
                state = State.ACTIVE

        if current_state == state:
            return

        self._log.info('Send: %-10s - %s', state, contact.jid)

        self._send_chatstate(contact, str(state))

        self._chatstates[contact.jid] = state

    def _send_chatstate(self, contact, chatstate):
        type_ = 'groupchat' if contact.is_groupchat else 'chat'
        message = OutgoingMessage(account=self._account,
                                  contact=contact,
                                  message=None,
                                  type_=type_,
                                  chatstate=chatstate,
                                  play_sound=False)

        self._con.send_message(message)

    @ensure_enabled
    def set_mouse_activity(self, contact: ContactT, was_paused: bool) -> None:
        if contact.settings.get('send_chatstate') == 'disabled':
            return
        self._last_mouse_activity[contact.jid] = time.time()
        if self._chatstates.get(contact.jid) == State.INACTIVE:
            if was_paused:
                self.set_chatstate(contact, State.PAUSED)
            else:
                self.set_chatstate(contact, State.ACTIVE)

    @ensure_enabled
    def set_keyboard_activity(self, contact: ContactT) -> None:
        self._last_keyboard_activity[contact.jid] = time.time()

    def remove_delay_timeout(self, contact):
        timeout = self._delay_timeout_ids.get(contact.jid)
        if timeout is not None:
            GLib.source_remove(timeout)
            del self._delay_timeout_ids[contact.jid]

    def remove_all_delay_timeouts(self):
        for timeout in self._delay_timeout_ids.values():
            GLib.source_remove(timeout)
        self._delay_timeout_ids = {}

    def cleanup(self):
        self.remove_all_delay_timeouts()
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)


def get_instance(*args: Any, **kwargs: Any) -> Tuple[Chatstate, str]:
    return Chatstate(*args, **kwargs), 'Chatstate'
