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
from typing import Optional
from typing import Tuple

import time
import logging

import nbxmpp
from gi.repository import GLib

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.const import Chatstate as State
from gajim.common.modules.misc import parse_delay
from gajim.common.connection_handlers_events import MessageOutgoingEvent
from gajim.common.connection_handlers_events import GcMessageOutgoingEvent

from gajim.common.types import ContactT
from gajim.common.types import ConnectionT

log = logging.getLogger('gajim.c.m.chatstates')

INACTIVE_AFTER = 60
PAUSED_AFTER = 5


def parse_chatstate(stanza: nbxmpp.Message) -> Optional[str]:
    if parse_delay(stanza) is not None:
        return None

    children = stanza.getChildren()
    for child in children:
        if child.getNamespace() == nbxmpp.NS_CHATSTATES:
            return child.getName()
    return None


class Chatstate:
    def __init__(self, con: ConnectionT) -> None:
        self._con = con
        self._account = con.name

        self.handlers = [
            ('presence', self._presence_received),
        ]
        self._chatstates = {}  # type: Dict[str, State]
        self._last_keyboard_activity = {}  # type: Dict[str, float]
        self._last_mouse_activity = {}  # type: Dict[str, float]

        self._timeout_id = GLib.timeout_add_seconds(
            2, self._check_last_interaction)

    def _presence_received(self,
                           _con: ConnectionT,
                           stanza: nbxmpp.Presence) -> None:
        if stanza.getType() not in ('unavailable', 'error'):
            return

        full_jid = stanza.getFrom()

        if self._con.get_own_jid().bareMatch(full_jid):
            return

        contact = app.contacts.get_gc_contact(
            self._account, full_jid.getStripped(), full_jid.getResource())
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

        log.info('Reset chatstate for %s', jid)

        app.nec.push_outgoing_event(
            NetworkEvent('chatstate-received',
                         account=self._account,
                         contact=contact))

    def delegate(self, event: Any) -> None:
        if self._con.get_own_jid().bareMatch(event.jid) or event.sent:
            # Dont show chatstates from our own resources
            return

        if event.mtype == 'groupchat':
            # Not implemented yet
            return

        chatstate = parse_chatstate(event.stanza)
        if chatstate is None:
            return

        if event.muc_pm:
            contact = app.contacts.get_gc_contact(
                self._account, event.jid, event.resource)
        else:
            contact = app.contacts.get_contact_from_full_jid(
                self._account, event.fjid)
        if contact is None:
            return

        contact.chatstate = chatstate
        log.info('Recv: %-10s - %s', chatstate, event.fjid)
        app.nec.push_outgoing_event(
            NetworkEvent('chatstate-received',
                         account=self._account,
                         contact=contact))

    def _check_last_interaction(self) -> GLib.SOURCE_CONTINUE:
        setting = app.config.get('outgoing_chat_state_notifications')
        if setting in ('composing_only', 'disabled'):
            return GLib.SOURCE_CONTINUE

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
                            self._last_mouse_activity.pop(jid, None)
                            self._last_keyboard_activity.pop(jid, None)
                            continue
                self.set_chatstate(contact, new_chatstate)

        return GLib.SOURCE_CONTINUE

    def set_active(self, jid: str) -> None:
        self._last_mouse_activity[jid] = time.time()
        setting = app.config.get('outgoing_chat_state_notifications')
        if setting == 'disabled':
            return
        self._chatstates[jid] = State.ACTIVE

    def get_active_chatstate(self, contact: ContactT) -> Optional[str]:
        # determines if we add 'active' on outgoing messages
        setting = app.config.get('outgoing_chat_state_notifications')
        if setting == 'disabled':
            return None

        if not contact.is_groupchat():
            # Dont send chatstates to ourself
            if self._con.get_own_jid().bareMatch(contact.jid):
                return None

            if not contact.supports(nbxmpp.NS_CHATSTATES):
                return None

        self.set_active(contact.jid)
        return 'active'

    def set_chatstate(self, contact: ContactT, state: State) -> None:
        current_state = self._chatstates.get(contact.jid)
        setting = app.config.get('outgoing_chat_state_notifications')
        if setting == 'disabled':
            # Send a last 'gone' state after user disabled chatstates
            if current_state is not None:
                log.info('Send: %-10s - %s', State.GONE, contact.jid)
                app.nec.push_outgoing_event(
                    MessageOutgoingEvent(None,
                                         account=self._account,
                                         jid=contact.jid,
                                         chatstate=str(State.GONE)))
            self._chatstates.pop(contact.jid, None)
            self._last_mouse_activity.pop(contact.jid, None)
            self._last_keyboard_activity.pop(contact.jid, None)
            return

        if not contact.is_groupchat():
            # Dont leak presence to contacts
            # which are not allowed to see our status
            if not contact.is_pm_contact:
                if contact and contact.sub in ('to', 'none'):
                    return

            if contact.show == 'offline':
                return

            if not contact.supports(nbxmpp.NS_CHATSTATES):
                return

        if state in (State.ACTIVE, State.COMPOSING):
            self._last_mouse_activity[contact.jid] = time.time()

        if setting == 'composing_only':
            if state in (State.INACTIVE, State.GONE, State.PAUSED):
                state = State.ACTIVE

        if current_state == state:
            return

        # Dont send chatstates to ourself
        if self._con.get_own_jid().bareMatch(contact.jid):
            return

        log.info('Send: %-10s - %s', state, contact.jid)

        event_attrs = {'account': self._account,
                       'jid': contact.jid,
                       'chatstate': str(state)}

        if contact.is_groupchat():
            app.nec.push_outgoing_event(
                GcMessageOutgoingEvent(None, **event_attrs))
        else:
            app.nec.push_outgoing_event(
                MessageOutgoingEvent(None, **event_attrs))

        self._chatstates[contact.jid] = state

    def set_mouse_activity(self, contact: ContactT) -> None:
        self._last_mouse_activity[contact.jid] = time.time()
        setting = app.config.get('outgoing_chat_state_notifications')
        if setting == 'disabled':
            return
        if self._chatstates.get(contact.jid) == State.INACTIVE:
            self.set_chatstate(contact, State.ACTIVE)

    def set_keyboard_activity(self, contact: ContactT) -> None:
        self._last_keyboard_activity[contact.jid] = time.time()

    def cleanup(self):
        GLib.source_remove(self._timeout_id)


def get_instance(*args: Any, **kwargs: Any) -> Tuple[Chatstate, str]:
    return Chatstate(*args, **kwargs), 'Chatstate'
