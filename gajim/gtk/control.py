# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import datetime as dt
import logging
import time
from collections.abc import Sequence

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import Affiliation
from nbxmpp.const import StatusCode
from nbxmpp.structs import MucSubject

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common import types
from gajim.common.const import XmppUriQuery
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.models import Message
from gajim.common.util.status import get_uf_show
from gajim.common.util.user_strings import get_uf_affiliation
from gajim.common.util.user_strings import get_uf_role

from gajim.gtk.builder import get_builder
from gajim.gtk.conversation.jump_to_end_button import JumpToEndButton
from gajim.gtk.conversation.message_selection import MessageSelection
from gajim.gtk.conversation.rows.widgets import MessageRowActions
from gajim.gtk.conversation.view import ConversationView
from gajim.gtk.groupchat_roster import GroupchatRoster
from gajim.gtk.groupchat_state import GroupchatState

HistoryRowT = events.ApplicationEvent | Message

REQUEST_LINES_COUNT = 20

log = logging.getLogger("gajim.gtk.control")


class ChatControl(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)

        self.handlers: dict[int, Any] = {}
        self._contact = None
        self._client = None

        self._ui = get_builder("chat_control.ui")

        self._message_row_actions = MessageRowActions()
        self._ui.conv_view_overlay.add_overlay(self._message_row_actions)

        self._scrolled_view = ConversationView(self._message_row_actions)
        self._scrolled_view.connect("autoscroll-changed", self._on_autoscroll_changed)
        self._scrolled_view.connect("request-history", self._request_history)
        self._ui.conv_view_overlay.set_child(self._scrolled_view)

        self._groupchat_state = GroupchatState()
        self._ui.conv_view_overlay.add_overlay(self._groupchat_state)

        self._message_selection = MessageSelection()
        self._message_selection.connect("copy", self._on_copy_selection)
        self._message_selection.connect("cancel", self._reset_message_selection)
        self._ui.conv_view_overlay.add_overlay(self._message_selection)

        self._jump_to_end_button = JumpToEndButton()
        self._jump_to_end_button.connect("clicked", self._on_jump_to_end)
        self._ui.conv_view_overlay.add_overlay(self._jump_to_end_button)

        self._roster = GroupchatRoster()
        self._ui.conv_view_paned.set_end_child(self._roster)

        # Used with encryption plugins
        self.sendmessage = False

        self.widget = self._ui.control_box

        app.ged.register_event_handler(
            "register-actions", ged.GUI1, self._on_register_actions
        )

    def _on_register_actions(self, _event: events.RegisterActions) -> None:
        app.window.get_action("activate-message-selection").connect(
            "activate", self._on_activate_message_selection
        )
        app.window.get_action("jump-to-message").connect(
            "activate", self._on_jump_to_message
        )

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

    @property
    def is_chat(self) -> bool:
        return isinstance(self.contact, BareContact)

    @property
    def is_privatechat(self) -> bool:
        return isinstance(self.contact, GroupchatParticipant)

    @property
    def is_groupchat(self) -> bool:
        return isinstance(self.contact, GroupchatContact)

    def is_loaded(self, account: str, jid: JID) -> bool:
        if self._contact is None:
            return False
        return self.contact.account == account and self.contact.jid == jid

    def has_active_chat(self) -> bool:
        return self._contact is not None

    def get_group_chat_roster(self) -> GroupchatRoster:
        return self._roster

    def get_conversation_view(self) -> ConversationView:
        return self._scrolled_view

    def add_command_output(self, text: str, is_error: bool) -> None:
        self._scrolled_view.add_command_output(text, is_error)

    def add_info_message(self, text: str, timestamp: dt.datetime | None = None) -> None:

        self._scrolled_view.add_info_message(text, timestamp)

    def drag_data_file_transfer(self, paths: list[str]) -> None:
        app.window.activate_action("win.send-file", GLib.Variant("as", paths))

    def clear(self) -> None:
        log.info("Clear")

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = None
        self._client = None
        self._scrolled_view.clear()
        self._groupchat_state.clear()
        self._roster.clear()
        self.unregister_events()

    def remove_message(self, pk: int) -> None:
        self._scrolled_view.remove_message(pk)

    def reset_view(self) -> None:
        self._scrolled_view.reset()

    def view_is_at_bottom(self) -> bool:
        return self._scrolled_view.get_autoscroll()

    def scroll_to_message(self, pk: int, timestamp: dt.datetime) -> None:
        row = self._scrolled_view.get_row_by_pk(pk)
        if row is None:
            # Clear view and reload conversation around timestamp
            self._scrolled_view.reset()
            self._scrolled_view.block_signals(True)
            messages = app.storage.archive.get_conversation_around_timestamp(
                self.contact.account, self.contact.jid, timestamp
            )
            self._add_messages(messages)
            self._scrolled_view.set_history_complete(False, False)

        GLib.idle_add(self._scrolled_view.block_signals, False)
        GLib.idle_add(self._scrolled_view.scroll_to_message_and_highlight, pk)

    def mark_as_read(self) -> None:
        self._jump_to_end_button.reset_unread_count()

    def process_escape(self) -> bool:
        message_selection_active = self._message_selection.get_visible()
        if message_selection_active:
            self._reset_message_selection()
            return True

        return False

    def switch_contact(
        self, contact: BareContact | GroupchatContact | GroupchatParticipant
    ) -> None:

        log.info("Switch to %s (%s)", contact.jid, contact.account)
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = contact

        self._client = app.get_client(contact.account)

        self._jump_to_end_button.switch_contact(contact)
        self._message_row_actions.switch_contact(contact)
        self._scrolled_view.switch_contact(contact)
        self._request_history(None, True)
        self._groupchat_state.switch_contact(contact)
        self._roster.switch_contact(contact)

        self._reset_message_selection()

        self._register_events()

        if isinstance(contact, GroupchatParticipant):
            contact.multi_connect(
                {
                    "user-status-show-changed": self._on_participant_status_show_changed,  # noqa: E501
                }
            )

        elif isinstance(contact, GroupchatContact):
            contact.multi_connect(
                {
                    "user-joined": self._on_user_joined,
                    "user-left": self._on_user_left,
                    "user-affiliation-changed": self._on_user_affiliation_changed,
                    "user-role-changed": self._on_user_role_changed,
                    "user-hats-changed": self._on_user_hats_changed,
                    "user-status-show-changed": self._on_user_status_show_changed,
                    "user-nickname-changed": self._on_user_nickname_changed,
                    "room-kicked": self._on_room_kicked,
                    "room-destroyed": self._on_room_destroyed,
                    "room-voice-request-error": self._on_room_voice_request_error,
                    "room-config-finished": self._on_room_config_finished,
                    "room-config-changed": self._on_room_config_changed,
                    "room-presence-error": self._on_room_presence_error,
                    "room-subject": self._on_room_subject,
                    "room-affiliation-changed": self._on_room_affiliation_changed,
                }
            )

        self._client.get_module("Chatstate").set_active(contact)

        transfers = self._client.get_module("HTTPUpload").get_running_transfers(contact)
        if transfers is not None:
            for transfer in transfers:
                self._add_file_transfer(transfer)

        if isinstance(contact, GroupchatContact):
            if not app.settings.get("show_subject_on_join") or contact.is_joining:
                return

            muc_data = self._client.get_module("MUC").get_muc_data(contact.jid)
            if muc_data is not None and muc_data.subject is not None:
                self._scrolled_view.add_muc_subject(
                    muc_data.subject, muc_data.last_subject_timestamp
                )

        self.widget.set_visible(True)

    def _register_events(self) -> None:
        if self.has_events_registered():
            return

        self.register_events(
            [
                ("presence-received", ged.GUI2, self._on_presence_received),
                ("message-sent", ged.GUI2, self._on_message_sent),
                ("message-deleted", ged.GUI2, self._on_message_deleted),
                ("message-acknowledged", ged.GUI2, self._on_message_acknowledged),
                ("message-received", ged.GUI2, self._on_message_received),
                ("message-corrected", ged.GUI2, self._on_message_corrected),
                ("message-moderated", ged.GUI2, self._on_message_moderated),
                ("message-retracted", ged.GUI2, self._on_message_retracted),
                ("receipt-received", ged.GUI2, self._on_receipt_received),
                ("displayed-received", ged.GUI2, self._on_displayed_received),
                ("reaction-updated", ged.GUI2, self._on_reaction_updated),
                ("message-error", ged.GUI2, self._on_message_error),
                ("call-stopped", ged.GUI2, self._on_call_stopped),
                ("jingle-request-received", ged.GUI2, self._on_jingle_request_received),
                ("http-upload-started", ged.GUI2, self._on_http_upload_started),
                ("http-upload-error", ged.GUI2, self._on_http_upload_error),
                ("encryption-check", ged.GUI2, self._on_encryption_info),
                ("muc-user-block-changed", ged.GUI2, self._on_muc_user_block_changed),
                # TODO Jingle FT
                # ('file-request-received', ged.GUI2, self._on_file_request_event),
                # ('file-request-sent', ged.GUI2, self._on_file_request_event),
            ]
        )

    def _is_event_processable(self, event: Any) -> bool:
        if self._contact is None:
            return False

        if event.account != self._contact.account:
            return False

        if event.jid is None:
            return True

        return event.jid == self._contact.jid

    def _on_presence_received(self, event: events.PresenceReceived) -> None:
        if not self._is_event_processable(event):
            return

        if not app.settings.get("print_status_in_chats"):
            return

        contact = self.client.get_module("Contacts").get_contact(event.fjid)
        if isinstance(contact, BareContact | GroupchatContact):
            return

        self._scrolled_view.add_user_status(
            self.contact.name, contact.show.value, contact.status
        )

    def _on_message_sent(self, event: events.MessageSent) -> None:
        if not self._is_event_processable(event):
            return

        self._add_message(event.message)

    def _on_message_deleted(self, event: events.MessageDeleted) -> None:
        if not self._is_event_processable(event):
            return

        self.remove_message(event.pk)

    def _on_message_acknowledged(self, event: events.MessageAcknowledged) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.acknowledge_message(event)

    def _on_message_received(self, event: events.MessageReceived) -> None:
        if not self._is_event_processable(event):
            return

        self._add_message(event.message)

    def _on_message_corrected(self, event: events.MessageCorrected) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.correct_message(event)

    def _on_message_moderated(self, event: events.MessageModerated) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.update_retractions(event.moderation.stanza_id)

    def _on_message_retracted(self, event: events.MessageRetracted) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.update_retractions(event.retraction.id)

    def _on_receipt_received(self, event: events.ReceiptReceived) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.set_receipt(event.receipt_id)

    def _on_displayed_received(self, event: events.DisplayedReceived) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.set_read_marker(event.marker_id)

    def _on_reaction_updated(self, event: events.ReactionUpdated) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.update_reactions(event.reaction_id)

    def _on_message_error(self, event: events.MessageError) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.show_error(event.message_id, event.error)

    def _on_call_stopped(self, event: events.CallStopped) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.update_call_rows()

    def _on_jingle_request_received(self, event: events.JingleRequestReceived) -> None:

        if not self._is_event_processable(event):
            return

        if not any(item in ("audio", "video") for item in event.contents):
            # This is not a call
            return

        active_jid = app.call_manager.get_active_call_jid()
        # Don't add a second row if contact upgrades to video
        if active_jid is None:
            self._add_call_message(event=event)

    def _on_file_request_event(
        self, event: events.FileRequestReceivedEvent | events.FileRequestSent
    ) -> None:

        if not self._is_event_processable(event):
            return

        self._add_jingle_file_transfer(event=event)

    def _on_http_upload_started(self, event: events.HTTPUploadStarted) -> None:
        self._add_file_transfer(event.transfer)

    def _on_http_upload_error(self, event: events.HTTPUploadError) -> None:
        self.add_info_message(event.error_msg)

    def _on_encryption_info(self, event: events.EncryptionInfo) -> None:
        if not self._is_event_processable(event):
            return

        if self._allow_add_message():
            self._scrolled_view.add_encryption_info(event)

    def _on_muc_user_block_changed(self, event: events.MucUserBlockChanged) -> None:
        if not self._is_event_processable(event):
            return

        self._scrolled_view.update_blocked_muc_users()

    def _on_autoscroll_changed(
        self, _widget: ConversationView, autoscroll: bool
    ) -> None:

        if not autoscroll:
            self._jump_to_end_button.toggle(True)
            return

        self._jump_to_end_button.toggle(False)

        if not self.has_active_chat():
            # This signal can be toggled without an active chat, see #12226
            return

        if app.window.is_chat_active(self.contact.account, self.contact.jid):
            app.window.mark_as_read(self.contact.account, self.contact.jid)

    def _on_activate_message_selection(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:

        pk = param.get_uint32()
        self._scrolled_view.enable_row_selection(pk)
        self._message_selection.set_visible(True)

    def _reset_message_selection(self, *args: Any) -> None:
        self._scrolled_view.disable_row_selection()
        self._message_selection.set_visible(False)

    def _on_copy_selection(self, _widget: MessageSelection) -> None:
        self._scrolled_view.copy_selected_messages()

    def _on_jump_to_message(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:

        pk, timestamp = param.unpack()
        self.scroll_to_message(pk, dt.datetime.fromtimestamp(timestamp, dt.UTC))

    def _on_jump_to_end(self, _button: Gtk.Button) -> None:
        self.reset_view()

    def _get_our_nick(self) -> str:
        if isinstance(self.contact, GroupchatParticipant):
            muc_data = self.client.get_module("MUC").get_muc_data(
                self.contact.jid.new_as_bare()
            )
            if muc_data is not None:
                return muc_data.nick

        return app.nicks[self.contact.account]

    def _allow_add_message(self) -> bool:
        return self._scrolled_view.get_lower_complete()

    def _add_file_transfer(self, transfer: HTTPFileTransfer) -> None:
        self._scrolled_view.add_file_transfer(transfer)

    def _add_jingle_file_transfer(
        self, event: events.FileRequestReceivedEvent | events.FileRequestSent | None
    ) -> None:
        if self._allow_add_message():
            self._scrolled_view.add_jingle_file_transfer(event)

    def _add_call_message(self, event: events.JingleRequestReceived) -> None:
        if self._allow_add_message():
            self._scrolled_view.add_call_message(event=event)

    def _add_message(self, message: Message) -> None:
        # TODO: Unify with _add_db_row()
        if self._allow_add_message():
            self._scrolled_view.add_message_from_db(message)

            if not self.view_is_at_bottom():
                if message.direction == ChatDirection.OUTGOING:
                    self._scrolled_view.scroll_to_end()
                else:
                    self._jump_to_end_button.add_unread_count()
        else:
            self._jump_to_end_button.add_unread_count()

    def _add_db_row(self, message: Message):
        if message.filetransfers:
            self._scrolled_view.add_jingle_file_transfer(message=message)
            return

        if message.call is not None:
            self._scrolled_view.add_call_message(message=message)
            return

        self._scrolled_view.add_message_from_db(message)

    def _add_messages(self, messages: list[Message]):
        for msg in messages:
            self._add_db_row(msg)

    def _request_messages(self, before: bool) -> Sequence[Message]:
        if before:
            row = self._scrolled_view.get_first_row()
        else:
            row = self._scrolled_view.get_last_row()

        if row is None:
            timestamp = dt.datetime.now(dt.UTC)
        else:
            timestamp = dt.datetime.fromtimestamp(row.db_timestamp, dt.UTC)

        return app.storage.archive.get_conversation_before_after(
            self.contact.account,
            self.contact.jid,
            before,
            timestamp,
            REQUEST_LINES_COUNT,
        )

    def _request_events(self, before: bool) -> list[events.ApplicationEvent]:
        if before:
            row = self._scrolled_view.get_first_event_row()
        else:
            row = self._scrolled_view.get_last_event_row()

        if row is None:
            timestamp = time.time()
        else:
            timestamp = row.db_timestamp

        assert self._contact is not None
        return app.storage.events.load(
            self._contact, before, timestamp, REQUEST_LINES_COUNT
        )

    def _request_history(self, _widget: Any, before: bool) -> None:

        self._scrolled_view.block_signals(True)

        messages = self._request_messages(before)
        event_rows = self._request_events(before)
        rows = self._sort_request_rows(messages, event_rows, before)

        assert self._contact is not None
        for row in rows:
            if not isinstance(row, events.ApplicationEvent):
                self._add_messages([row])

            elif isinstance(row, events.MUCUserJoined):
                self._process_muc_user_joined(row)

            elif isinstance(row, events.MUCUserLeft):
                self._process_muc_user_left(row)

            elif isinstance(row, events.MUCNicknameChanged):
                self._process_muc_nickname_changed(row)

            elif isinstance(row, events.MUCRoomKicked):
                self._process_muc_room_kicked(row)

            elif isinstance(row, events.MUCUserAffiliationChanged):
                self._process_muc_user_affiliation_changed(row)

            elif isinstance(row, events.MUCAffiliationChanged):
                self._process_room_affiliation_changed(row)

            elif isinstance(row, events.MUCUserRoleChanged):
                self._process_muc_user_role_changed(row)

            elif isinstance(row, events.MUCUserHatsChanged):
                self._process_muc_user_hats_changed(row)

            elif isinstance(row, events.MUCUserStatusShowChanged):
                self._process_muc_user_status_show_changed(row)

            elif isinstance(row, events.MUCRoomConfigChanged):
                self._process_muc_room_config_changed(row)

            elif isinstance(row, events.MUCRoomConfigFinished):
                self._process_muc_room_config_finished(row)

            elif isinstance(row, events.MUCRoomPresenceError):
                self._process_muc_room_presence_error(row)

            elif isinstance(row, events.MUCRoomDestroyed):
                self._process_muc_room_destroyed(row)

            elif isinstance(row, events.MUCRoomVoiceRequestError):
                self._process_muc_room_voice_request_error(row)

            else:
                raise ValueError("Unknown event: %s" % type(row))

        if len(rows) < REQUEST_LINES_COUNT:
            self._scrolled_view.set_history_complete(before, True)

        self._scrolled_view.block_signals(False)

    @staticmethod
    def _sort_request_rows(
        messages: Sequence[Message],
        event_rows: list[events.ApplicationEvent],
        before: bool,
    ) -> list[HistoryRowT]:

        def sort_func(obj: HistoryRowT) -> float:
            return obj.timestamp  # pyright: ignore

        assert isinstance(messages, list)

        rows = messages + event_rows
        rows.sort(key=sort_func, reverse=before)
        return rows

    def _on_user_nickname_changed(
        self,
        _contact: types.GroupchatContact,
        _signal_name: str,
        event: events.MUCNicknameChanged,
        _old_contact: types.GroupchatParticipant,
        _new_contact: types.GroupchatParticipant,
    ) -> None:

        self._process_muc_nickname_changed(event)

    def _process_muc_nickname_changed(self, event: events.MUCNicknameChanged) -> None:

        if event.is_self:
            message = _("You are now known as %s") % event.new_name
        else:
            message = _("{nick} is now known as {new_nick}").format(
                nick=event.old_name, new_nick=event.new_name
            )
        self.add_info_message(message, event.timestamp)

    def _on_room_kicked(
        self, _contact: GroupchatContact, _signal_name: str, event: events.MUCRoomKicked
    ) -> None:

        self._process_muc_room_kicked(event)

    def _process_muc_room_kicked(self, event: events.MUCRoomKicked) -> None:
        status_codes = event.status_codes or []

        reason = event.reason
        reason = "" if reason is None else _("(reason: %s)") % reason

        actor = event.actor

        # Group Chat: We have been removed from the room by Alice: reason
        message = _("You have been removed from this group chat")
        if actor:
            message = _("You have been removed from this group chat by %s") % actor

        if StatusCode.REMOVED_ERROR in status_codes:
            # Handle 333 before 307, some MUCs add both
            # Group Chat: Server kicked us because of an server error
            message = _("You have left due to an error")

        elif StatusCode.REMOVED_KICKED in status_codes:
            # Group Chat: We have been kicked by Alice: reason
            message = _("You have been kicked")
            if actor:
                message = _("You have been kicked by %s") % actor

        elif StatusCode.REMOVED_BANNED in status_codes:
            # Group Chat: We have been banned by Alice: reason
            message = _("You have been banned")
            if actor:
                message = _("You have been banned by %s") % actor

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            # Group Chat: We were removed because of an affiliation change
            reason = _("(reason: affiliation changed)")

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            # Group Chat: Room configuration changed
            reason = _("(reason: group chat configuration changed to members-only)")

        elif StatusCode.REMOVED_SERVICE_SHUTDOWN in status_codes:
            # Group Chat: Kicked because of server shutdown
            reason = _("(reason: system shutdown)")
        else:
            # No formatted message available
            return

        message = f"{message} {reason}"

        self.add_info_message(message, event.timestamp)

    def _on_user_affiliation_changed(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        user_contact: GroupchatParticipant,
        event: events.MUCUserAffiliationChanged,
    ) -> None:

        self._process_muc_user_affiliation_changed(event)

    def _process_muc_user_affiliation_changed(
        self, event: events.MUCUserAffiliationChanged
    ) -> None:
        actor = event.actor
        # Group Chat: You have been kicked by Alice
        actor = "" if actor is None else _("(changed by %s)") % actor

        reason = event.reason
        reason = "" if reason is None else _("(reason: %s)") % reason

        if event.is_self:
            message = self.__format_affiliation_change_self(
                affiliation=event.affiliation, actor=actor, reason=reason
            )
        else:
            message = self.__format_affiliation_change_other(
                nick=event.nick,
                affiliation=event.affiliation,
                actor=actor,
                reason=reason,
            )

        self.add_info_message(message, event.timestamp)

    def _on_room_affiliation_changed(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        event: events.MUCAffiliationChanged,
    ) -> None:
        self._process_room_affiliation_changed(event)

    def _process_room_affiliation_changed(
        self,
        event: events.MUCAffiliationChanged,
    ) -> None:
        self.add_info_message(
            self.__format_affiliation_change_other(event.nick, event.affiliation),
            event.timestamp,
        )

    @staticmethod
    def __format_affiliation_change_self(
        affiliation: Affiliation, actor: str = "", reason: str = ""
    ) -> str:
        uf_affiliation = get_uf_affiliation(affiliation)

        if affiliation.value == "outcast":
            message = _("You have been banned")
            if actor:
                message = _("You have been banned by %s") % actor
            return f"{message} {reason}"

        if affiliation.value in ("owner", "admin", "member"):
            message = _("You are now %(affiliation)s of this group chat") % {
                "affiliation": uf_affiliation
            }
        else:
            # "none"
            message = _("Your affiliations to this group chat have been removed")

        return f"{message} {actor} {reason}"

    @staticmethod
    def __format_affiliation_change_other(
        nick: str, affiliation: Affiliation, actor: str = "", reason: str = ""
    ) -> str:
        uf_affiliation = get_uf_affiliation(affiliation)

        if affiliation.value == "outcast":
            message = _("%s has been banned") % nick
            if actor:
                message = _("%(nick)s has been banned by %(actor)s") % {
                    "nick": nick,
                    "actor": actor,
                }
            return f"{message} {reason}"

        if affiliation.value in ("owner", "admin", "member"):
            message = _("%(nick)s is now %(affiliation)s of this group chat") % {
                "nick": nick,
                "affiliation": uf_affiliation,
            }
        else:
            # "none"
            message = _(
                "Affiliations of %(nick)s to this group chat have been removed"
            ) % {"nick": nick}

        return f"{message} {actor} {reason}"

    def _on_user_role_changed(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        user_contact: GroupchatParticipant,
        event: events.MUCUserRoleChanged,
    ) -> None:

        self._process_muc_user_role_changed(event)

    def _process_muc_user_role_changed(self, event: events.MUCUserRoleChanged) -> None:

        uf_role = get_uf_role(event.role)
        nick = event.nick

        if event.is_self:
            if event.role.value in ("moderator", "participant", "visitor"):
                message = _("You are now %(role)s of this group chat") % {
                    "role": uf_role
                }
            else:
                message = _("Your roles in this group chat have been removed")
        else:
            if event.role.value in ("moderator", "participant", "visitor"):
                message = _("%(user)s is now %(role)s of this group chat") % {
                    "user": nick,
                    "role": uf_role,
                }
            else:
                message = _("Roles of %s have been removed in this group chat") % nick

        actor = event.actor
        # Group Chat: You have been kicked by Alice
        actor = "" if actor is None else _("(changed by %s)") % actor

        reason = event.reason
        reason = "" if reason is None else _("(reason: %s)") % reason

        self.add_info_message(f"{message} {actor} {reason}", event.timestamp)

    def _on_user_hats_changed(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        user_contact: GroupchatParticipant,
        event: events.MUCUserHatsChanged,
    ) -> None:

        self._process_muc_user_hats_changed(event)

    def _process_muc_user_hats_changed(self, event: events.MUCUserHatsChanged) -> None:

        if event.hats:
            hats = ", ".join(event.hats)
            if event.is_self:
                message = _("You now have the following hats: %s") % hats
            else:
                message = _("%(user)s now has the following hats: %(hats)s") % {
                    "user": event.nick,
                    "hats": hats,
                }
        else:
            if event.is_self:
                message = _("All of your hats have been removed")
            else:
                message = _("All hats of %s have been removed") % event.nick

        self.add_info_message(message, event.timestamp)

    def _on_user_status_show_changed(
        self,
        contact: GroupchatContact,
        _signal_name: str,
        _user_contact: GroupchatParticipant,
        event: events.MUCUserStatusShowChanged,
    ) -> None:

        self._process_muc_user_status_show_changed(event)

    def _on_participant_status_show_changed(
        self,
        contact: GroupchatParticipant,
        _signal_name: str,
        event: events.MUCUserStatusShowChanged,
    ) -> None:

        self._process_muc_user_status_show_changed(event)

    def _process_muc_user_status_show_changed(
        self, event: events.MUCUserStatusShowChanged
    ) -> None:

        if isinstance(self._contact, GroupchatContact):
            contact = self._contact
        elif isinstance(self._contact, GroupchatParticipant):
            contact = self._contact.room
        else:
            raise AssertionError

        if not contact.settings.get("print_status"):
            return

        nick = event.nick
        status = event.status
        status = "" if not status else f" - {status}"
        show = get_uf_show(event.show_value)

        if event.is_self:
            message = _("You are now {show}{status}").format(show=show, status=status)

        else:
            message = _("{nick} is now {show}{status}").format(
                nick=nick, show=show, status=status
            )

        self.add_info_message(message, event.timestamp)

    def _on_room_config_changed(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        event: events.MUCRoomConfigChanged,
    ) -> None:

        self._process_muc_room_config_changed(event)

    def _process_muc_room_config_changed(
        self, event: events.MUCRoomConfigChanged
    ) -> None:

        # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify
        status_codes = event.status_codes
        changes: list[str] = []

        if StatusCode.SHOWING_UNAVAILABLE in status_codes:
            changes.append(_("Group chat now shows unavailable members"))

        if StatusCode.NOT_SHOWING_UNAVAILABLE in status_codes:
            changes.append(_("Group chat now does not show unavailable members"))

        if StatusCode.CONFIG_NON_PRIVACY_RELATED in status_codes:
            changes.append(_("A setting not related to privacy has been changed"))
            self.client.get_module("Discovery").disco_muc(self.contact.jid)

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            # Can be a presence
            # (see chg_contact_status in groupchat_control.py)
            changes.append(_("Conversations are stored on the server"))

        if StatusCode.CONFIG_NO_ROOM_LOGGING in status_codes:
            changes.append(_("Conversations are not stored on the server"))

        if StatusCode.CONFIG_NON_ANONYMOUS in status_codes:
            changes.append(_("Group chat is now non-anonymous"))

        if StatusCode.CONFIG_SEMI_ANONYMOUS in status_codes:
            changes.append(_("Group chat is now semi-anonymous"))

        if StatusCode.CONFIG_FULL_ANONYMOUS in status_codes:
            changes.append(_("Group chat is now fully anonymous"))

        for message in changes:
            self.add_info_message(message, event.timestamp)

    def _on_room_config_finished(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        event: events.MUCRoomConfigFinished,
    ) -> None:
        self._process_muc_room_config_finished(event)

    def _process_muc_room_config_finished(
        self, event: events.MUCRoomConfigFinished
    ) -> None:

        self.add_info_message(_("A new group chat has been created"), event.timestamp)

    def _on_room_presence_error(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        event: events.MUCRoomPresenceError,
    ) -> None:

        self._process_muc_room_presence_error(event)

    def _process_muc_room_presence_error(
        self, event: events.MUCRoomPresenceError
    ) -> None:

        self.add_info_message(_("Error: %s") % event.error, event.timestamp)

    def _on_room_destroyed(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        event: events.MUCRoomDestroyed,
    ) -> None:

        self._process_muc_room_destroyed(event)

    def _process_muc_room_destroyed(self, event: events.MUCRoomDestroyed) -> None:

        reason = event.reason
        reason = "" if reason is None else _("(reason: %s)") % reason

        message = _("Group chat has been destroyed")
        message = f"{message} {reason}"

        if event.alternate is not None:
            message += "\n" + _("You can join this group chat instead: %s") % (
                event.alternate.to_iri(XmppUriQuery.JOIN.value)
            )

        self.add_info_message(message, event.timestamp)

    def _on_room_voice_request_error(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        event: events.MUCRoomVoiceRequestError,
    ) -> None:

        self._process_muc_room_voice_request_error(event)

    def _process_muc_room_voice_request_error(
        self, event: events.MUCRoomVoiceRequestError
    ) -> None:
        self.add_info_message(event.error, event.timestamp)

    def _on_user_joined(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        _user_contact: GroupchatParticipant,
        event: events.MUCUserJoined,
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
            message = _("You (%s) joined the group chat") % event.nick

        if StatusCode.NON_ANONYMOUS in status_codes:
            message = _("Any participant is allowed to see your full XMPP Address")

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            message = _("Conversations are stored on the server")

        if StatusCode.NICKNAME_MODIFIED in status_codes:
            message = _(
                "The server has assigned or modified your "
                "nickname in this group chat"
            )

        if message is not None:
            self.add_info_message(message, event.timestamp)

    def _on_user_left(
        self,
        _contact: GroupchatContact,
        _signal_name: str,
        _user_contact: GroupchatParticipant,
        event: events.MUCUserLeft,
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

        message = _("%s has been removed from this group chat") % nick

        actor = event.actor
        if StatusCode.REMOVED_KICKED in status_codes:
            message = _("%s has been kicked") % nick
            if actor:
                message = _("%(nick)s has been kicked by %(actor)s") % {
                    "nick": nick,
                    "actor": actor,
                }

        elif StatusCode.REMOVED_BANNED in status_codes:
            message = _("%s has been banned") % nick
            if actor:
                message = _("%(nick)s has been banned by %(actor)s") % {
                    "nick": nick,
                    "actor": actor,
                }

        reason = event.reason
        if reason:
            reason = _("(reason: %s)") % reason
            message = f"{message} {reason}"

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            reason = _("(reason: affiliation changed)")
            message = f"{message} {reason}"

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            reason = _("(reason: group chat configuration changed to members-only)")
            message = f"{message} {reason}"

        else:
            self._scrolled_view.add_muc_user_left(event)
            return

        self.add_info_message(message, event.timestamp)

    def _on_room_subject(
        self, contact: GroupchatContact, _signal_name: str, subject: MucSubject
    ) -> None:

        if app.settings.get("show_subject_on_join") or not contact.is_joining:
            self._scrolled_view.add_muc_subject(subject)
