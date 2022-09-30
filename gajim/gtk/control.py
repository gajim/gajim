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

from gi.repository import Gtk
from gi.repository import GLib

from nbxmpp import JID
from nbxmpp.const import StatusCode
from nbxmpp.structs import MucSubject
from nbxmpp.modules.security_labels import Displaymarking

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common import helpers
from gajim.common import types
from gajim.common.helpers import get_file_path_from_dnd_dropped_uri
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.ged import EventHelper
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import get_retraction_text
from gajim.common.const import KindConstant
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.storage.archive import ConversationRow
from gajim.gtk.conversation.view import ConversationView

from gajim.gui.conversation.jump_to_end_button import JumpToEndButton
from gajim.gui.builder import get_builder
from gajim.gui.groupchat_roster import GroupchatRoster
from gajim.gui.groupchat_state import GroupchatState

log = logging.getLogger('gajim.gui.control')


class ChatControl(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)

        self.handlers: dict[int, Any] = {}

        self._contact = None
        self._client = None

        self._ui = get_builder('chat_control.ui')

        self._scrolled_view = ConversationView()
        self._scrolled_view.connect('autoscroll-changed',
                                    self._on_autoscroll_changed)
        self._scrolled_view.connect('request-history',
                                    self._fetch_n_lines_history, 20)
        self._ui.conv_view_overlay.add(self._scrolled_view)

        self._groupchat_state = GroupchatState()
        self._ui.conv_view_overlay.add_overlay(self._groupchat_state)

        self._jump_to_end_button = JumpToEndButton()
        self._jump_to_end_button.connect('clicked', self._on_jump_to_end)
        self._ui.conv_view_overlay.add_overlay(self._jump_to_end_button)

        self._roster = GroupchatRoster()

        self._ui.conv_view_box.add(self._roster)

        # Used with encryption plugins
        self.sendmessage = False

        self.widget = cast(Gtk.Box, self._ui.get_object('control_box'))
        self.widget.show_all()

    @property
    def contact(self) -> types.ChatContactT:
        assert self._contact is not None
        return self._contact

    @property
    def account(self) -> str:
        # Compatibility with Plugins for Gajim < 1.5
        assert self._contact is not None
        return self._contact.account

    @property
    def room_jid(self) -> str:
        # Compatibility with Plugins for Gajim < 1.5
        assert self._contact is not None
        return str(self._contact.jid)

    @property
    def client(self) -> types.Client:
        assert self._client is not None
        return self._client

    def is_loaded(self, account: str, jid: JID) -> bool:
        if self._contact is None:
            return False
        return self.contact.account == account and self.contact.jid == jid

    def has_active_chat(self) -> bool:
        return self._contact is not None

    def get_group_chat_roster(self) -> GroupchatRoster:
        return self._roster

    def clear(self) -> None:
        log.info('Clear')

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = None
        self._client = None
        self._scrolled_view.clear()
        self._groupchat_state.clear()
        self._roster.clear()
        self.unregister_events()

    def switch_contact(self, contact: Union[BareContact,
                                            GroupchatContact,
                                            GroupchatParticipant]) -> None:

        log.info('Switch to %s (%s)', contact.jid, contact.account)
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = contact

        self._client = app.get_client(contact.account)

        self._jump_to_end_button.switch_contact(contact)
        self._scrolled_view.switch_contact(contact)
        self._groupchat_state.switch_contact(contact)
        self._roster.switch_contact(contact)

        self._register_events()

        if isinstance(contact, GroupchatParticipant):
            contact.multi_connect({
                'user-status-show-changed':
                    self._on_participant_status_show_changed,
            })

        elif isinstance(contact, GroupchatContact):
            contact.multi_connect({
                'user-joined': self._on_user_joined,
                'user-left': self._on_user_left,
                'user-affiliation-changed': self._on_user_affiliation_changed,
                'user-role-changed': self._on_user_role_changed,
                'user-status-show-changed': self._on_user_status_show_changed,
                'user-nickname-changed': self._on_user_nickname_changed,
                'room-kicked': self._on_room_kicked,
                'room-destroyed': self._on_room_destroyed,
                'room-config-finished': self._on_room_config_finished,
                'room-config-changed': self._on_room_config_changed,
                'room-presence-error': self._on_room_presence_error,
                'room-subject': self._on_room_subject,
            })

        self._client.get_module('Chatstate').set_active(contact)

        transfers = self._client.get_module('HTTPUpload').get_running_transfers(
            contact)
        if transfers is not None:
            for transfer in transfers:
                self.add_file_transfer(transfer)

        if isinstance(contact, GroupchatContact):
            if (not app.settings.get('show_subject_on_join') or
                    contact.is_joining):
                return

            muc_data = self._client.get_module('MUC').get_muc_data(
                str(contact.jid))
            if muc_data is not None and muc_data.subject is not None:
                self._scrolled_view.add_muc_subject(
                    muc_data.subject, muc_data.last_subject_timestamp)

    def _register_events(self) -> None:
        if self.has_events_registered():
            return

        self.register_events([
            ('presence-received', ged.GUI2, self._on_presence_received),
            ('message-sent', ged.GUI2, self._on_message_sent),
            ('message-received', ged.GUI2, self._on_message_received),
            ('mam-message-received', ged.GUI2, self._on_mam_message_received),
            ('gc-message-received', ged.GUI2, self._on_gc_message_received),
            ('message-updated', ged.GUI2, self._on_message_updated),
            ('message-moderated', ged.GUI2, self._on_message_moderated),
            ('receipt-received', ged.GUI2, self._on_receipt_received),
            ('displayed-received', ged.GUI2, self._on_displayed_received),
            ('message-error', ged.GUI2, self._on_message_error),
            ('call-stopped', ged.GUI2, self._on_call_stopped),
            ('jingle-request-received',
             ged.GUI2, self._on_jingle_request_received),
            ('file-request-received', ged.GUI2, self._on_file_request_event),
            ('file-request-sent', ged.GUI2, self._on_file_request_event),
        ])

    def _is_event_processable(self, event: Any) -> bool:
        if self._contact is None:
            return False

        if event.account != self._contact.account:
            return False

        if event.jid != self._contact.jid:
            return False
        return True

    def _on_presence_received(self, event: events.PresenceReceived) -> None:
        if not self._is_event_processable(event):
            return

        if not app.settings.get('print_status_in_chats'):
            return

        contact = self.client.get_module('Contacts').get_contact(event.fjid)
        if isinstance(contact, BareContact):
            return
        self._scrolled_view.add_user_status(self.contact.name,
                                            contact.show.value,
                                            contact.status)

    def _on_message_sent(self, event: events.MessageSent) -> None:
        if not self._is_event_processable(event):
            return

        if not event.message:
            return

        if self.contact.is_groupchat:
            return

        message_id = event.message_id

        if event.label:
            displaymarking = event.label.displaymarking
        else:
            displaymarking = None

        if event.correct_id:
            self._scrolled_view.correct_message(
                event.correct_id, event.message, self.get_our_nick())
            return

        self.add_message(event.message,
                         'outgoing',
                         tim=event.timestamp,
                         displaymarking=displaymarking,
                         message_id=message_id,
                         additional_data=event.additional_data)

    def _on_message_received(self, event: events.MessageReceived) -> None:
        if not self._is_event_processable(event):
            return

        if self.is_groupchat:
            return

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

    def _on_mam_message_received(self,
                                 event: events.MamMessageReceived) -> None:

        if not self._is_event_processable(event):
            return

        if isinstance(self.contact, GroupchatContact):

            if not event.properties.type.is_groupchat:
                return
            if event.archive_jid != self.contact.jid:
                return
            self.add_muc_message(event.msgtxt,
                                 tim=event.properties.mam.timestamp,
                                 contact=event.properties.muc_nickname,
                                 message_id=event.properties.id,
                                 stanza_id=event.stanza_id,
                                 additional_data=event.additional_data)

        else:

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
                             additional_data=event.additional_data)

    def _on_gc_message_received(self, event: events.GcMessageReceived) -> None:
        if not self._is_event_processable(event):
            return

        if event.properties.muc_nickname is None:
            # message from server
            self.add_muc_message(event.msgtxt,
                                 tim=event.properties.timestamp,
                                 displaymarking=event.displaymarking,
                                 additional_data=event.additional_data)
        else:
            self.add_muc_message(event.msgtxt,
                                 tim=event.properties.timestamp,
                                 contact=event.properties.muc_nickname,
                                 displaymarking=event.displaymarking,
                                 message_id=event.properties.id,
                                 stanza_id=event.stanza_id,
                                 additional_data=event.additional_data)

    def _on_message_updated(self, event: events.MessageUpdated) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.correct_message(
            event.correct_id, event.msgtxt, event.nickname)

    def _on_message_moderated(self, event: events.MessageModerated) -> None:
        if not self._is_event_processable(event):
            return

        text = get_retraction_text(
            self.contact.account,
            event.moderation.moderator_jid,
            event.moderation.reason)
        self._scrolled_view.show_message_retraction(
            event.moderation.stanza_id, text)

    def _on_receipt_received(self, event: events.ReceiptReceived) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.show_receipt(event.receipt_id)

    def _on_displayed_received(self, event: events.DisplayedReceived) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.set_read_marker(event.marker_id)

    def _on_message_error(self, event: events.MessageError) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.show_error(event.message_id, event.error)

    def _on_call_stopped(self, event: events.CallStopped) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.update_call_rows()

    def _on_jingle_request_received(self,
                                    event: events.JingleRequestReceived
                                    ) -> None:

        if not self._is_event_processable(event):
            return

        active_jid = app.call_manager.get_active_call_jid()
        # Don't add a second row if contact upgrades to video
        if active_jid is None:
            self.add_call_message(event=event)

    def _on_file_request_event(self,
                               event: Union[events.FileRequestReceivedEvent,
                                            events.FileRequestSent]
                               ) -> None:

        if not self._is_event_processable(event):
            return

        self.add_jingle_file_transfer(event=event)

    @property
    def is_chat(self) -> bool:
        return isinstance(self.contact, BareContact)

    @property
    def is_privatechat(self) -> bool:
        return isinstance(self.contact, GroupchatParticipant)

    @property
    def is_groupchat(self) -> bool:
        return isinstance(self.contact, GroupchatContact)

    def mark_as_read(self, send_marker: bool = True) -> None:
        self._jump_to_end_button.reset_unread_count()

    def _on_autoscroll_changed(self,
                               _widget: ConversationView,
                               autoscroll: bool
                               ) -> None:

        if not autoscroll:
            self._jump_to_end_button.toggle(True)
            return

        self._jump_to_end_button.toggle(False)
        if app.window.is_chat_active(self.contact.account, self.contact.jid):
            app.window.mark_as_read(self.contact.account, self.contact.jid)

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
        if isinstance(self.contact, GroupchatParticipant):
            muc_data = self.client.get_module('MUC').get_muc_data(
                self.contact.jid.bare)
            if muc_data is not None:
                return muc_data.nick

        return app.nicks[self.contact.account]

    def _allow_add_message(self) -> bool:
        return self._scrolled_view.get_lower_complete()

    def add_command_output(self, text: str, is_error: bool) -> None:
        self._scrolled_view.add_command_output(text, is_error)

    def add_info_message(self,
                         text: str,
                         timestamp: Optional[float] = None
                         ) -> None:

        self._scrolled_view.add_info_message(text, timestamp)

    def add_file_transfer(self, transfer: HTTPFileTransfer) -> None:
        self._scrolled_view.add_file_transfer(transfer)

    def add_jingle_file_transfer(self,
                                 event: Union[
                                     events.FileRequestReceivedEvent,
                                     events.FileRequestSent,
                                     None]
                                 ) -> None:
        if self._allow_add_message():
            self._scrolled_view.add_jingle_file_transfer(event)

    def add_call_message(self, event: events.JingleRequestReceived) -> None:
        if self._allow_add_message():
            self._scrolled_view.add_call_message(event=event)

    def _add_message(self,
                     text: str,
                     kind: str,
                     name: str,
                     tim: float,
                     displaymarking: Optional[Displaymarking] = None,
                     msg_log_id: Optional[int] = None,
                     message_id: Optional[str] = None,
                     stanza_id: Optional[str] = None,
                     additional_data: Optional[AdditionalDataDict] = None
                     ) -> None:

        if additional_data is None:
            additional_data = AdditionalDataDict()

        if self._allow_add_message():
            self._scrolled_view.add_message(
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
                    self._scrolled_view.scroll_to_end()
                else:
                    self._jump_to_end_button.add_unread_count()
        else:
            self._jump_to_end_button.add_unread_count()

    def reset_view(self) -> None:
        self._scrolled_view.reset()

    def get_autoscroll(self) -> bool:
        return self._scrolled_view.get_autoscroll()

    def scroll_to_message(self, log_line_id: int, timestamp: float) -> None:
        row = self._scrolled_view.get_row_by_log_line_id(log_line_id)
        if row is None:
            # Clear view and reload conversation around timestamp
            self._scrolled_view.block_signals(True)
            self.reset_view()
            before, at_after = app.storage.archive.get_conversation_around(
                self.contact.account, self.contact.jid, timestamp)
            self.add_messages(before)
            self.add_messages(at_after)

        GLib.idle_add(
            self._scrolled_view.scroll_to_message_and_highlight,
            log_line_id)
        GLib.idle_add(self._scrolled_view.block_signals, False)

    def _fetch_n_lines_history(self,
                               _scrolled: Gtk.ScrolledWindow,
                               before: bool,
                               n_lines: int
                               ) -> None:

        self._scrolled_view.block_signals(True)

        if before:
            row = self._scrolled_view.get_first_message_row()
        else:
            row = self._scrolled_view.get_last_message_row()

        if row is None:
            timestamp = time.time()
        else:
            timestamp = row.db_timestamp

        messages = app.storage.archive.get_conversation_before_after(
            self.contact.account,
            self.contact.jid,
            before,
            timestamp,
            n_lines)

        if not messages:
            self._scrolled_view.set_history_complete(before, True)
            self._scrolled_view.block_signals(False)
            return

        self.add_messages(messages)

        if len(messages) < n_lines:
            self._scrolled_view.set_history_complete(before, True)

        # if self._scrolled_view.get_autoscroll():
        #    if self._scrolled_view.reduce_message_count(before):
        #        self._scrolled_view.set_history_complete(before, False)

        assert self._contact is not None
        for event in app.storage.events.load(self._contact, before, timestamp):
            if isinstance(event, events.MUCUserJoined):
                self._process_muc_user_joined(event)

            elif isinstance(event, events.MUCUserLeft):
                self._process_muc_user_left(event)

            elif isinstance(event, events.MUCNicknameChanged):
                self._process_muc_nickname_changed(event)

            elif isinstance(event, events.MUCRoomKicked):
                self._process_muc_room_kicked(event)

            elif isinstance(event, events.MUCUserAffiliationChanged):
                self._process_muc_user_affiliation_changed(event)

            elif isinstance(event, events.MUCUserRoleChanged):
                self._process_muc_user_role_changed(event)

            elif isinstance(event, events.MUCUserStatusShowChanged):
                self._process_muc_user_status_show_changed(event)

            elif isinstance(event, events.MUCRoomConfigChanged):
                self._process_muc_room_config_changed(event)

            elif isinstance(event, events.MUCRoomConfigFinished):
                self._process_muc_room_config_finished(event)

            elif isinstance(event, events.MUCRoomPresenceError):
                self._process_muc_room_presence_error(event)

            elif isinstance(event, events.MUCRoomDestroyed):
                self._process_muc_room_destroyed(event)
            else:
                raise ValueError('Unknown event: %s' % event)

        self._scrolled_view.block_signals(False)

    def add_messages(self, messages: list[ConversationRow]):
        for msg in messages:
            if msg.kind in (KindConstant.FILE_TRANSFER_INCOMING,
                            KindConstant.FILE_TRANSFER_OUTGOING):
                if msg.additional_data.get_value('gajim', 'type') == 'jingle':
                    self._scrolled_view.add_jingle_file_transfer(
                        db_message=msg)
                continue

            if msg.kind in (KindConstant.CALL_INCOMING,
                            KindConstant.CALL_OUTGOING):
                self._scrolled_view.add_call_message(db_message=msg)
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
                        self.contact.account, retracted_by, reason)

            self._scrolled_view.add_message(
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

    def add_message(self,
                    text: str,
                    kind: str,
                    tim: float,
                    displaymarking: Optional[Displaymarking] = None,
                    msg_log_id: Optional[int] = None,
                    stanza_id: Optional[str] = None,
                    message_id: Optional[str] = None,
                    additional_data: Optional[AdditionalDataDict] = None
                    ) -> None:

        if kind == 'incoming':
            name = self.contact.name
        else:
            name = self.get_our_nick()

        self._add_message(text,
                          kind,
                          name,
                          tim,
                          displaymarking=displaymarking,
                          msg_log_id=msg_log_id,
                          message_id=message_id,
                          stanza_id=stanza_id,
                          additional_data=additional_data)

    def _on_user_nickname_changed(self,
                                  _contact: types.GroupchatContact,
                                  _signal_name: str,
                                  event: events.MUCNicknameChanged,
                                  _old_contact: types.GroupchatParticipant,
                                  _new_contact: types.GroupchatParticipant
                                  ) -> None:

        self._process_muc_nickname_changed(event)

    def _process_muc_nickname_changed(self,
                                      event: events.MUCNicknameChanged
                                      ) -> None:

        if event.is_self:
            message = _('You are now known as %s') % event.new_name
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=event.old_name,
                                                new_nick=event.new_name)
        self.add_info_message(message, event.timestamp)

    def _on_room_kicked(self,
                        _contact: GroupchatContact,
                        _signal_name: str,
                        event: events.MUCRoomKicked
                        ) -> None:

        self._process_muc_room_kicked(event)

    def _process_muc_room_kicked(self, event: events.MUCRoomKicked) -> None:
        status_codes = event.status_codes or []

        reason = event.reason
        reason = '' if reason is None else f': {reason}'

        actor = event.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(
            actor=actor)

        # Group Chat: We have been removed from the room by Alice: reason
        message = _('You have been removed from the '
                    'group chat{actor}{reason}')

        if StatusCode.REMOVED_ERROR in status_codes:
            # Handle 333 before 307, some MUCs add both
            # Group Chat: Server kicked us because of an server error
            message = _('You have left due '
                        'to an error{reason}').format(reason=reason)

        elif StatusCode.REMOVED_KICKED in status_codes:
            # Group Chat: We have been kicked by Alice: reason
            message = _('You have been '
                        'kicked{actor}{reason}').format(actor=actor,
                                                        reason=reason)

        elif StatusCode.REMOVED_BANNED in status_codes:
            # Group Chat: We have been banned by Alice: reason
            message = _('You have been '
                        'banned{actor}{reason}').format(actor=actor,
                                                        reason=reason)

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            # Group Chat: We were removed because of an affiliation change
            reason = _(': Affiliation changed')
            message = message.format(actor=actor, reason=reason)

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            # Group Chat: Room configuration changed
            reason = _(': Group chat configuration changed to members-only')
            message = message.format(actor=actor, reason=reason)

        elif StatusCode.REMOVED_SERVICE_SHUTDOWN in status_codes:
            # Group Chat: Kicked because of server shutdown
            reason = ': System shutdown'
            message = message.format(actor=actor, reason=reason)

        else:
            # No formatted message available
            return

        self.add_info_message(message, event.timestamp)

    def _on_user_affiliation_changed(self,
                                     _contact: GroupchatContact,
                                     _signal_name: str,
                                     user_contact: GroupchatParticipant,
                                     event: events.MUCUserAffiliationChanged
                                     ) -> None:

        self._process_muc_user_affiliation_changed(event)

    def _process_muc_user_affiliation_changed(
            self,
            event: events.MUCUserAffiliationChanged) -> None:

        affiliation = helpers.get_uf_affiliation(event.affiliation)

        reason = event.reason
        reason = '' if reason is None else f': {reason}'

        actor = event.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(
            actor=actor)

        if event.is_self:
            message = _('** Your Affiliation has been set to '
                        '{affiliation}{actor}{reason}').format(
                            affiliation=affiliation,
                            actor=actor,
                            reason=reason)
        else:
            message = _('** Affiliation of {nick} has been set to '
                        '{affiliation}{actor}{reason}').format(
                            nick=event.nick,
                            affiliation=affiliation,
                            actor=actor,
                            reason=reason)

        self.add_info_message(message, event.timestamp)

    def _on_user_role_changed(self,
                              _contact: GroupchatContact,
                              _signal_name: str,
                              user_contact: GroupchatParticipant,
                              event: events.MUCUserRoleChanged
                              ) -> None:

        self._process_muc_user_role_changed(event)

    def _process_muc_user_role_changed(self,
                                       event: events.MUCUserRoleChanged
                                       ) -> None:

        role = helpers.get_uf_role(event.role)
        nick = event.nick

        reason = event.reason
        reason = '' if reason is None else f': {reason}'

        actor = event.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        if event.is_self:
            message = _('** Your Role has been set to '
                        '{role}{actor}{reason}').format(role=role,
                                                        actor=actor,
                                                        reason=reason)
        else:
            message = _('** Role of {nick} has been set to '
                        '{role}{actor}{reason}').format(nick=nick,
                                                        role=role,
                                                        actor=actor,
                                                        reason=reason)
        self.add_info_message(message, event.timestamp)

    def _on_user_status_show_changed(self,
                                     contact: GroupchatContact,
                                     _signal_name: str,
                                     _user_contact: GroupchatParticipant,
                                     event: events.MUCUserStatusShowChanged
                                     ) -> None:

        self._process_muc_user_status_show_changed(event)

    def _on_participant_status_show_changed(
            self,
            contact: GroupchatParticipant,
            _signal_name: str,
            event: events.MUCUserStatusShowChanged) -> None:

        self._process_muc_user_status_show_changed(event)

    def _process_muc_user_status_show_changed(
            self,
            event: events.MUCUserStatusShowChanged) -> None:

        if isinstance(self._contact, GroupchatContact):
            contact = self._contact
        elif isinstance(self._contact, GroupchatParticipant):
            contact = self._contact.room
        else:
            raise AssertionError

        if not contact.settings.get('print_status'):
            return

        nick = event.nick
        status = event.status
        status = '' if not status else f' - {status}'
        show = helpers.get_uf_show(event.show_value)

        if event.is_self:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)

        else:
            message = _('{nick} is now {show}{status}').format(
                nick=nick,
                show=show,
                status=status)

        self.add_info_message(message, event.timestamp)

    def _on_room_config_changed(self,
                                _contact: GroupchatContact,
                                _signal_name: str,
                                event: events.MUCRoomConfigChanged
                                ) -> None:

        self._process_muc_room_config_changed(event)

    def _process_muc_room_config_changed(self,
                                         event: events.MUCRoomConfigChanged
                                         ) -> None:

        # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify
        status_codes = event.status_codes
        changes: list[str] = []

        if StatusCode.SHOWING_UNAVAILABLE in status_codes:
            changes.append(_('Group chat now shows unavailable members'))

        if StatusCode.NOT_SHOWING_UNAVAILABLE in status_codes:
            changes.append(_('Group chat now does not show '
                             'unavailable members'))

        if StatusCode.CONFIG_NON_PRIVACY_RELATED in status_codes:
            changes.append(_('A setting not related to privacy has been '
                             'changed'))
            self.client.get_module('Discovery').disco_muc(self.contact.jid)

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            # Can be a presence
            # (see chg_contact_status in groupchat_control.py)
            changes.append(_('Conversations are stored on the server'))

        if StatusCode.CONFIG_NO_ROOM_LOGGING in status_codes:
            changes.append(_('Conversations are not stored on the server'))

        if StatusCode.CONFIG_NON_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now non-anonymous'))

        if StatusCode.CONFIG_SEMI_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now semi-anonymous'))

        if StatusCode.CONFIG_FULL_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now fully anonymous'))

        for message in changes:
            self.add_info_message(message, event.timestamp)

    def _on_room_config_finished(self,
                                 _contact: GroupchatContact,
                                 _signal_name: str,
                                 event: events.MUCRoomConfigFinished
                                 ) -> None:
        self._process_muc_room_config_finished(event)

    def _process_muc_room_config_finished(self,
                                          event: events.MUCRoomConfigFinished
                                          ) -> None:

        self.add_info_message(_('A new group chat has been created'))

    def _on_room_presence_error(self,
                                _contact: GroupchatContact,
                                _signal_name: str,
                                event: events.MUCRoomPresenceError
                                ) -> None:

        self._process_muc_room_presence_error(event)

    def _process_muc_room_presence_error(self,
                                         event: events.MUCRoomPresenceError
                                         ) -> None:

        error_message = to_user_string(event.error)
        self.add_info_message(_('Error: %s') % error_message)

    def _on_room_destroyed(self,
                           _contact: GroupchatContact,
                           _signal_name: str,
                           event: events.MUCRoomDestroyed
                           ) -> None:

        self._process_muc_room_destroyed(event)

    def _process_muc_room_destroyed(self,
                                    event: events.MUCRoomDestroyed
                                    ) -> None:

        reason = event.reason
        reason = '' if reason is None else f': {reason}'

        message = _('Group chat has been destroyed')

        if event.alternate is not None:
            message += '\n' + _('You can join this group chat instead: '
                                'xmpp:%s?join') % str(event.alternate)

        self.add_info_message(message, event.timestamp)

    def _on_user_joined(self,
                        _contact: GroupchatContact,
                        _signal_name: str,
                        _user_contact: GroupchatParticipant,
                        event: events.MUCUserJoined
                        ) -> None:

        self._process_muc_user_joined(event)

    def _process_muc_user_joined(self, event: events.MUCUserJoined) -> None:
        assert isinstance(self.contact, GroupchatContact)

        if not event.is_self:
            if self.contact.is_joined:
                self._scrolled_view.add_muc_user_joined(event)
            return

        status_codes = event.status_codes or []

        message = None
        if not self.contact.is_joined:
            # We just joined the room
            message = _('You (%s) joined the group chat') % event.nick

        if StatusCode.NON_ANONYMOUS in status_codes:
            message = _('Any participant is allowed to see your full '
                        'XMPP Address')

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            message = _('Conversations are stored on the server')

        if StatusCode.NICKNAME_MODIFIED in status_codes:
            message = _('The server has assigned or modified your '
                        'nickname in this group chat')

        if message is not None:
            self.add_info_message(message, event.timestamp)

    def _on_user_left(self,
                      _contact: GroupchatContact,
                      _signal_name: str,
                      _user_contact: GroupchatParticipant,
                      event: events.MUCUserLeft
                      ) -> None:

        self._process_muc_user_left(event)

    def _process_muc_user_left(self, event: events.MUCUserLeft) -> None:
        if event.is_self:
            return

        status_codes = event.status_codes or []
        nick = event.nick

        if StatusCode.REMOVED_ERROR in status_codes:
            # Handle 333 before 307, some MUCs add both
            self._scrolled_view.add_muc_user_left(event, error=True)
            return

        reason = event.reason
        reason = '' if reason is None else f': {reason}'

        actor = event.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(
            actor=actor)

        message = _('{nick} has been removed from the group '
                    'chat{by}{reason}')

        if StatusCode.REMOVED_KICKED in status_codes:
            message = _('{nick} has been '
                        'kicked{actor}{reason}').format(nick=nick,
                                                        actor=actor,
                                                        reason=reason)

        elif StatusCode.REMOVED_BANNED in status_codes:
            message = _('{nick} has been '
                        'banned{actor}{reason}').format(nick=nick,
                                                        actor=actor,
                                                        reason=reason)

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            reason = _(': Affiliation changed')
            message = message.format(nick=nick, by=actor, reason=reason)

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            reason = _(': Group chat configuration changed to members-only')
            message = message.format(nick=nick, by=actor, reason=reason)

        else:
            self._scrolled_view.add_muc_user_left(event)
            return

        self.add_info_message(message, event.timestamp)

    def add_muc_message(self,
                        text: str,
                        tim: float,
                        contact: str = '',
                        displaymarking: Optional[Displaymarking] = None,
                        message_id: Optional[str] = None,
                        stanza_id: Optional[str] = None,
                        additional_data: Optional[AdditionalDataDict] = None,
                        ) -> None:

        assert isinstance(self._contact, GroupchatContact)

        if contact == self._contact.nickname:
            kind = 'outgoing'
        else:
            kind = 'incoming'
            # muc-specific chatstate

        self._add_message(text,
                          kind,
                          contact,
                          tim,
                          displaymarking=displaymarking,
                          message_id=message_id,
                          stanza_id=stanza_id,
                          additional_data=additional_data)

    def _on_room_subject(self,
                         contact: GroupchatContact,
                         _signal_name: str,
                         subject: MucSubject
                         ) -> None:

        if (app.settings.get('show_subject_on_join') or
                not contact.is_joining):
            self._scrolled_view.add_muc_subject(subject)
