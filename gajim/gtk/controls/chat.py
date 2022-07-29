# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Nikos Kouremenos <kourem AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
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

from typing import ClassVar
from typing import Type
from typing import Optional

import logging

from nbxmpp import JID
from nbxmpp.const import Chatstate
from nbxmpp.modules.security_labels import Displaymarking

from gajim.common import app
from gajim.common import events
from gajim.common.i18n import _
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import KindConstant
from gajim.common.modules.contacts import BareContact

from gajim.gui.controls.base import BaseControl
from gajim.gui.const import ControlType

from gajim.command_system.implementation.hosts import ChatCommands
from gajim.command_system.framework import CommandHost

log = logging.getLogger('gajim.gui.controls.chat')


class ChatControl(BaseControl):
    '''
    A control for standard 1-1 chat
    '''
    _type = ControlType.CHAT

    # Set a command host to bound to. Every command given through a chat will be
    # processed with this command host.
    COMMAND_HOST: ClassVar[Type[CommandHost]] = ChatCommands

    def __init__(self, account: str, jid: JID) -> None:
        BaseControl.__init__(self,
                             'chat_control',
                             account,
                             jid)
        # PluginSystem: adding GUI extension point for this ChatControl
        # instance object
        app.plugin_manager.gui_extension_point('chat_control', self)

    @property
    def jid(self) -> JID:
        return self.contact.jid

    def _on_mam_message_received(self,
                                 event: events.MamMessageReceived) -> None:
        if event.properties.is_muc_pm:
            if not event.properties.jid == self.contact.jid:
                return
        else:
            if not event.properties.jid.bare_match(self.contact.jid):
                return

        kind = 'incoming'
        if event.kind == KindConstant.CHAT_MSG_SENT:
            kind = 'outgoing'

        self.add_message(event.msgtxt,
                         kind,
                         tim=event.properties.mam.timestamp,
                         message_id=event.properties.id,
                         stanza_id=event.stanza_id,
                         additional_data=event.additional_data,
                         notify=False)

    def _on_message_received(self, event: events.MessageReceived) -> None:
        if not event.msgtxt:
            return

        kind = 'incoming'
        if event.properties.is_sent_carbon:
            kind = 'outgoing'

        self.add_message(event.msgtxt,
                         kind,
                         tim=event.properties.timestamp,
                         displaymarking=event.displaymarking,
                         msg_log_id=event.msg_log_id,
                         message_id=event.properties.id,
                         stanza_id=event.stanza_id,
                         additional_data=event.additional_data)

    def _on_message_sent(self, event: events.MessageSent) -> None:
        if not event.message:
            return

        message_id = event.message_id

        if event.label:
            displaymarking = event.label.displaymarking
        else:
            displaymarking = None

        if event.correct_id:
            self.conversation_view.correct_message(
                event.correct_id, event.message, self.get_our_nick())
            return

        self.add_message(event.message,
                         'outgoing',
                         tim=event.timestamp,
                         displaymarking=displaymarking,
                         message_id=message_id,
                         additional_data=event.additional_data)

    def _on_receipt_received(self, event: events.ReceiptReceived) -> None:
        self.conversation_view.show_receipt(event.receipt_id)

    def _on_displayed_received(self, event: events.DisplayedReceived) -> None:
        self.conversation_view.set_read_marker(event.marker_id)

    def _on_ping_event(self, event: events.PingEventT) -> None:
        if self.contact != event.contact:
            return
        if isinstance(event, events.PingSent):
            self.add_info_message(_('Ping?'))
        elif isinstance(event, events.PingReply):
            self.add_info_message(
                _('Pong! (%s seconds)') % event.seconds)
        else:
            self.add_info_message(event.error)

    def add_message(self,
                    text: str,
                    kind: str,
                    tim: float,
                    displaymarking: Optional[Displaymarking] = None,
                    msg_log_id: Optional[int] = None,
                    stanza_id: Optional[str] = None,
                    message_id: Optional[str] = None,
                    additional_data: Optional[AdditionalDataDict] = None,
                    notify: bool = True
                    ) -> None:

        if kind == 'incoming':
            name = self.contact.name
        else:
            name = self.get_our_nick()

        BaseControl.add_message(self,
                                text,
                                kind,
                                name,
                                tim,
                                notify,
                                displaymarking=displaymarking,
                                msg_log_id=msg_log_id,
                                message_id=message_id,
                                stanza_id=stanza_id,
                                additional_data=additional_data)

    def shutdown(self) -> None:
        # PluginSystem: removing GUI extension points connected with ChatControl
        # instance object
        app.plugin_manager.remove_gui_extension_point('chat_control', self)

        # Send 'gone' chatstate
        self._client.get_module('Chatstate').set_chatstate(
            self.contact, Chatstate.GONE)

        super(ChatControl, self).shutdown()
        app.check_finalize(self)

    def _on_presence_received(self, event: events.PresenceReceived) -> None:
        if not app.settings.get('print_status_in_chats'):
            return

        contact = self._client.get_module('Contacts').get_contact(event.fjid)
        if isinstance(contact, BareContact):
            return
        self.conversation_view.add_user_status(self.contact.name,
                                               contact.show.value,
                                               contact.status)
