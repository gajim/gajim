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

from typing import Any
from typing import Optional
from typing import Union
from typing import cast

import os
import logging
import time
import uuid

from gi.repository import Gtk
from gi.repository import GLib

from nbxmpp import JID
from nbxmpp.modules.security_labels import Displaymarking

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.helpers import message_needs_highlight
from gajim.common.helpers import get_file_path_from_dnd_dropped_uri
from gajim.common.i18n import _
from gajim.common.ged import EventHelper
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import get_retraction_text
from gajim.common.const import KindConstant
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.preview_helpers import filename_from_uri
from gajim.common.preview_helpers import guess_simple_file_type
from gajim.common.storage.archive import ConversationRow

from gajim.gui.conversation.view import ConversationView
from gajim.gui.conversation.scrolled import ScrolledView
from gajim.gui.conversation.jump_to_end_button import JumpToEndButton
from gajim.gui.builder import get_builder
from gajim.gui.util import set_urgency_hint
from gajim.gui.const import ControlType

from gajim.command_system.implementation.middleware import ChatCommandProcessor
from gajim.command_system.implementation.middleware import CommandTools

# The members of these modules are not referenced directly anywhere in this
# module, but still they need to be kept around. Importing them automatically
# registers the contained CommandContainers with the command system, thereby
# populating the list of available commands.
from gajim.command_system.implementation import standard  # noqa: F401
from gajim.command_system.implementation import execute  # noqa: F401


log = logging.getLogger('gajim.gui.controls.base')


class BaseControl(ChatCommandProcessor, CommandTools, EventHelper):
    '''
    A base class containing a banner, ConversationView, MessageInputTextView
    '''

    _type: Optional[ControlType] = None

    def __init__(self, widget_name: str, account: str, jid: JID) -> None:
        EventHelper.__init__(self)

        self.handlers: dict[int, Any] = {}

        self.account = account

        self._client = app.get_client(account)

        groupchat = self._type != ControlType.CHAT
        self.contact = self._client.get_module('Contacts').get_contact(
            jid, groupchat=groupchat)
        self._connect_contact_signals()

        self.control_id: str = str(uuid.uuid4())

        self.xml = get_builder('chat_control.ui')
        self.widget = cast(Gtk.Box, self.xml.get_object('control_box'))

        # Create ConversationView and connect signals
        self.conversation_view = ConversationView(self.account, self.contact)

        self._scrolled_view = ScrolledView()
        self._scrolled_view.add(self.conversation_view)
        self._scrolled_view.set_focus_vadjustment(Gtk.Adjustment())

        self.xml.conv_view_overlay.add(self._scrolled_view)

        self._jump_to_end_button = JumpToEndButton(self.contact)
        self._jump_to_end_button.connect('clicked', self._on_jump_to_end)
        self.xml.conv_view_overlay.add_overlay(self._jump_to_end_button)

        self._scrolled_view.connect('autoscroll-changed',
                                    self._on_autoscroll_changed)
        self._scrolled_view.connect('request-history',
                                    self.fetch_n_lines_history, 20)

        # Keeps track of whether the ConversationView is populated
        self._chat_loaded: bool = False

        # XEP-0333 Chat Markers
        self.last_msg_id: Optional[str] = None

        # XEP-0172 User Nickname
        # TODO:
        self.user_nick: Optional[str] = None

        self._client.get_module('Chatstate').set_active(self.contact)

        self.encryption: Optional[str] = self.get_encryption_state()
        self.conversation_view.encryption_enabled = self.encryption is not None

        # PluginSystem: adding GUI extension point for BaseControl
        # instance object (also subclasses, eg. ChatControl or GroupchatControl)
        app.plugin_manager.gui_extension_point('chat_control_base', self)

        self.register_events([
            ('ping-sent', ged.GUI1, self._on_ping_event),
            ('ping-reply', ged.GUI1, self._on_ping_event),
            ('ping-error', ged.GUI1, self._on_ping_event),
        ])

        # This is basically a very nasty hack to surpass the inability
        # to properly use the super, because of the old code.
        CommandTools.__init__(self)

    def _connect_contact_signals(self) -> None:
        '''
        Derived types MAY implement this
        '''

    def process_event(self, event: events.ApplicationEvent) -> None:
        if event.account != self.account:
            return

        if event.jid not in (self.contact.jid, self.contact.jid.bare):
            return

        file_transfer_events = (
            events.FileRequestReceivedEvent,
            events.FileRequestSent
        )

        if isinstance(event, file_transfer_events):
            self.add_jingle_file_transfer(event=event)
            return

        if isinstance(event, events.JingleRequestReceived):
            active_jid = app.call_manager.get_active_call_jid()
            # Don't add a second row if contact upgrades to video
            if active_jid is None:
                self.add_call_message(event=event)
            return

        if isinstance(event, events.CallStopped):
            self.conversation_view.update_call_rows()
            return

        if isinstance(event, events.MessageReceived) and not self.is_groupchat:
            self._on_message_received(event)
            return

        if isinstance(event, events.MessageSent):
            self._on_message_sent(event)
            return

        if isinstance(event, events.MessageError):
            self._on_message_error(event)
            return

        method_name = event.name.replace('-', '_')
        method_name = f'_on_{method_name}'
        getattr(self, method_name)(event)

    def _on_message_sent(self, event: events.MessageSent) -> None:
        '''
        Derived types MAY implement this
        '''

    def _on_message_received(self, event: events.MessageReceived) -> None:
        '''
        Derived types MAY implement this
        '''

    def _on_message_error(self, event: events.MessageError) -> None:
        self.conversation_view.show_error(event.message_id, event.error)

    def _on_message_updated(self, event: events.MessageUpdated) -> None:
        self.conversation_view.correct_message(
            event.correct_id, event.msgtxt, event.nickname)

    def _on_message_moderated(self, event: events.MessageModerated) -> None:
        text = get_retraction_text(
            self.account,
            event.moderation.moderator_jid,
            event.moderation.reason)
        self.conversation_view.show_message_retraction(
            event.moderation.stanza_id, text)

    @property
    def type(self) -> ControlType:
        assert self._type is not None
        return self._type

    @property
    def is_chat(self) -> bool:
        assert self._type is not None
        return self._type.is_chat

    @property
    def is_privatechat(self) -> bool:
        assert self._type is not None
        return self._type.is_privatechat

    @property
    def is_groupchat(self) -> bool:
        assert self._type is not None
        return self._type.is_groupchat

    def _on_ping_event(self, event: events.PingEventT) -> None:
        raise NotImplementedError

    def mark_as_read(self, send_marker: bool = True) -> None:
        self._jump_to_end_button.reset_unread_count()

        if send_marker and self.last_msg_id is not None:
            # XEP-0333 Send <displayed> marker
            self._client.get_module('ChatMarkers').send_displayed_marker(
                self.contact,
                self.last_msg_id,
                str(self._type))
            self.last_msg_id = None

    def set_encryption_state(self, encryption: Optional[str]) -> None:
        self.encryption = encryption
        self.conversation_view.encryption_enabled = encryption is not None
        self.contact.settings.set('encryption', self.encryption or '')

    def get_encryption_state(self) -> Optional[str]:
        state = self.contact.settings.get('encryption')
        if not state:
            return None
        if state not in app.plugin_manager.encryption_plugins:
            self.set_encryption_state(None)
            return None
        return state

    def shutdown(self) -> None:
        # remove_gui_extension_point() is called on shutdown, but also when
        # a plugin is getting disabled. Plugins don’t know the difference.
        # Plugins might want to remove their widgets on
        # remove_gui_extension_point(), so delete the objects only afterwards.
        app.plugin_manager.remove_gui_extension_point('chat_control_base', self)

        self._client.disconnect_all_from_obj(self)
        self.contact.disconnect_all_from_obj(self)

        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
        self.handlers.clear()

        self.conversation_view.destroy()
        self._scrolled_view.destroy()

        del self.conversation_view
        del self._scrolled_view

        self.widget.destroy()
        del self.widget

        del self.xml

        self.unregister_events()

    def _on_autoscroll_changed(self,
                               _widget: ScrolledView,
                               autoscroll: bool
                               ) -> None:
        if not autoscroll:
            self._jump_to_end_button.toggle(True)
            return

        self._jump_to_end_button.toggle(False)
        if app.window.is_chat_active(self.account, self.contact.jid):
            app.window.mark_as_read(self.account, self.contact.jid)

    def _on_jump_to_end(self, _button: Gtk.Button) -> None:
        self.reset_view()

    def drag_data_file_transfer(self, selection: Gtk.SelectionData) -> None:
        # we may have more than one file dropped
        uri_splitted = selection.get_uris()
        for uri in uri_splitted:
            path = get_file_path_from_dnd_dropped_uri(uri)
            if not os.path.isfile(path):  # is it a file?
                self.add_info_message(
                    _('The following file could not be accessed and was '
                      'not uploaded: %s') % path)
                continue

            app.interface.start_file_transfer(self.contact, path)

    def get_our_nick(self) -> str:
        return app.nicks[self.account]

    def _allow_add_message(self) -> bool:
        # Only add messages if the view is already populated
        return self.is_chat_loaded and self._scrolled_view.get_lower_complete()

    def add_info_message(self, text: str) -> None:
        self.conversation_view.add_info_message(text)

    def add_file_transfer(self, transfer: HTTPFileTransfer) -> None:
        self.conversation_view.add_file_transfer(transfer)

    def add_jingle_file_transfer(self,
                                 event: Union[
                                     events.FileRequestReceivedEvent,
                                     events.FileRequestSent,
                                     None]
                                 ) -> None:
        if self._allow_add_message():
            self.conversation_view.add_jingle_file_transfer(event)

    def add_call_message(self, event: events.JingleRequestReceived) -> None:
        if self._allow_add_message():
            self.conversation_view.add_call_message(event=event)

    def add_message(self,
                    text: str,
                    kind: str,
                    name: str,
                    tim: float,
                    notify: bool,
                    displaymarking: Optional[Displaymarking] = None,
                    msg_log_id: Optional[int] = None,
                    message_id: Optional[str] = None,
                    stanza_id: Optional[str] = None,
                    additional_data: Optional[AdditionalDataDict] = None
                    ) -> None:

        if additional_data is None:
            additional_data = AdditionalDataDict()

        chat_active = app.window.is_chat_active(
            self.account, self.contact.jid)

        if self._allow_add_message():
            self.conversation_view.add_message(
                text,
                kind,
                name,
                tim,
                display_marking=displaymarking,
                message_id=message_id,
                stanza_id=stanza_id,
                log_line_id=msg_log_id,
                additional_data=additional_data)

            if not self._scrolled_view.get_autoscroll():
                if kind == 'outgoing':
                    self.reset_view()
                else:
                    self._jump_to_end_button.add_unread_count()
        else:
            self._jump_to_end_button.add_unread_count()

        if message_id and kind == 'incoming':
            if self.is_groupchat:
                self.last_msg_id = stanza_id or message_id
            else:
                self.last_msg_id = message_id

        if kind == 'incoming':
            if notify:
                # Issue notification
                self._notify(name, text, tim, additional_data)

            if not chat_active and notify:
                if self.is_groupchat:
                    needs_highlight = message_needs_highlight(
                        text,
                        self.contact.nickname,
                        self._client.get_own_jid().bare)
                    if needs_highlight or self.contact.can_notify():
                        set_urgency_hint(app.window, True)
                else:
                    set_urgency_hint(app.window, True)

    def _notify(self,
                name: str,
                text: str,
                tim: Optional[float],
                additional_data: AdditionalDataDict
                ) -> None:
        if app.window.is_chat_active(self.account, self.contact.jid):
            if self._scrolled_view.get_autoscroll():
                return

        title = _('New message from %s') % name

        is_previewable = app.preview_manager.is_previewable(
            text, additional_data)
        if is_previewable:
            if text.startswith('geo:'):
                text = _('Location')
            else:
                file_name = filename_from_uri(text)
                _icon, file_type = guess_simple_file_type(text)
                text = f'{file_type} ({file_name})'

        sound: Optional[str] = None
        msg_type = 'chat-message'
        if self.is_chat:
            msg_type = 'chat-message'
            sound = 'first_message_received'

        if self.is_groupchat:
            msg_type = 'group-chat-message'
            title += f' ({self.contact.name})'
            needs_highlight = message_needs_highlight(
                text, self.contact.nickname, self._client.get_own_jid().bare)
            if needs_highlight:
                sound = 'muc_message_highlight'
            else:
                sound = 'muc_message_received'

            if not self.contact.can_notify() and not needs_highlight:
                return

        if self.is_privatechat:
            room_contact = self._client.get_module('Contacts').get_contact(
                self.contact.jid.bare)
            msg_type = 'private-chat-message'
            title += f' (private in {room_contact.name})'
            sound = 'first_message_received'

        # Is it a history message? Don't want sound-floods when we join.
        if tim is not None and time.mktime(time.localtime()) - tim > 1:
            sound = None

        if app.settings.get('notification_preview_message'):
            if text.startswith('/me') or text.startswith('/me\n'):
                text = f'* {name} {text[3:]}'

        app.ged.raise_event(
            events.Notification(account=self.account,
                                jid=self.contact.jid,
                                type='incoming-message',
                                sub_type=msg_type,
                                title=title,
                                text=text,
                                sound=sound))

    def load_messages(self) -> None:
        if self._chat_loaded:
            return

        self.fetch_n_lines_history(self._scrolled_view, True, 20)

    @property
    def is_chat_loaded(self) -> bool:
        return self._chat_loaded

    def reset_view(self) -> None:
        self._chat_loaded = False
        self.conversation_view.clear()
        self._scrolled_view.reset()

    def get_autoscroll(self) -> bool:
        return self._scrolled_view.get_autoscroll()

    def scroll_to_message(self, log_line_id: int, timestamp: float) -> None:
        row = self.conversation_view.get_row_by_log_line_id(log_line_id)
        if row is None:
            # Clear view and reload conversation around timestamp
            self.conversation_view.lock()
            self.reset_view()
            before, at_after = app.storage.archive.get_conversation_around(
                self.account, self.contact.jid, timestamp)
            self.add_messages(before)
            self.add_messages(at_after)

        GLib.idle_add(
            self.conversation_view.scroll_to_message_and_highlight,
            log_line_id)
        GLib.idle_add(self.conversation_view.unlock)

    def fetch_n_lines_history(self,
                              _scrolled: Gtk.ScrolledWindow,
                              before: bool,
                              n_lines: int
                              ) -> None:
        if self.conversation_view.locked:
            return

        self.conversation_view.lock()
        if before:
            row = self.conversation_view.get_first_message_row()
        else:
            row = self.conversation_view.get_last_message_row()
        if row is None:
            timestamp = time.time()
        else:
            timestamp = row.db_timestamp

        messages = app.storage.archive.get_conversation_before_after(
            self.account,
            self.contact.jid,
            before,
            timestamp,
            n_lines)

        self._chat_loaded = True

        if not messages:
            self._scrolled_view.set_history_complete(before, True)
            self.conversation_view.unlock()
            return

        self.add_messages(messages)

        if len(messages) < n_lines:
            self._scrolled_view.set_history_complete(before, True)

        # if self._scrolled_view.get_autoscroll():
        #    if self.conversation_view.reduce_message_count(before):
        #        self._scrolled_view.set_history_complete(before, False)

        self.conversation_view.unlock()

    def add_messages(self, messages: list[ConversationRow]):
        for msg in messages:
            if msg.kind in (KindConstant.FILE_TRANSFER_INCOMING,
                            KindConstant.FILE_TRANSFER_OUTGOING):
                if msg.additional_data.get_value('gajim', 'type') == 'jingle':
                    self.conversation_view.add_jingle_file_transfer(
                        db_message=msg)
                continue

            if msg.kind in (KindConstant.CALL_INCOMING,
                            KindConstant.CALL_OUTGOING):
                self.conversation_view.add_call_message(db_message=msg)
                continue

            if not msg.message:
                continue

            message_text = msg.message

            contact_name = msg.contact_name
            kind = 'incoming'
            if msg.kind in (
                    KindConstant.SINGLE_MSG_RECV, KindConstant.CHAT_MSG_RECV):
                kind = 'incoming'
                contact_name = self.contact.name
            elif msg.kind == KindConstant.GC_MSG:
                kind = 'incoming'
            elif msg.kind in (
                    KindConstant.SINGLE_MSG_SENT, KindConstant.CHAT_MSG_SENT):
                kind = 'outgoing'
                contact_name = self.get_our_nick()
            else:
                log.warning('kind attribute could not be processed'
                            'while adding message')

            if msg.additional_data is not None:
                retracted_by = msg.additional_data.get_value('retracted', 'by')
                if retracted_by is not None:
                    reason = msg.additional_data.get_value(
                        'retracted', 'reason')
                    message_text = get_retraction_text(
                        self.account, retracted_by, reason)

            self.conversation_view.add_message(
                message_text,
                kind,
                contact_name,
                msg.time,
                additional_data=msg.additional_data,
                message_id=msg.message_id,
                stanza_id=msg.stanza_id,
                log_line_id=msg.log_line_id,
                marker=msg.marker,
                error=msg.error)
