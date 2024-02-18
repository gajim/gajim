# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import sys
from functools import partial
from urllib.parse import urlparse

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import events
from gajim.common.commands import ChatCommands
from gajim.common.const import CallType
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.structs import OutgoingMessage
from gajim.common.types import ChatContactT
from gajim.common.util.muc import message_needs_highlight
from gajim.common.util.preview import filename_from_uri
from gajim.common.util.preview import format_geo_coords
from gajim.common.util.preview import guess_simple_file_type
from gajim.common.util.preview import split_geo_uri
from gajim.common.util.text import remove_invalid_xml_chars

from gajim.gtk.activity_page import ActivityPage
from gajim.gtk.chat_banner import ChatBanner
from gajim.gtk.chat_function_page import ChatFunctionPage
from gajim.gtk.chat_function_page import FunctionMode
from gajim.gtk.control import ChatControl
from gajim.gtk.dialogs import SimpleDialog
from gajim.gtk.message_actions_box import MessageActionsBox
from gajim.gtk.message_input import MessageInputTextView
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import allow_send_message
from gajim.gtk.util.window import open_window

log = logging.getLogger("gajim.gtk.chatstack")


class ChatStack(Gtk.Stack, EventHelper, SignalManager):
    def __init__(self):
        Gtk.Stack.__init__(self, hexpand=True, vexpand=True)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._current_contact: ChatContactT | None = None
        self._last_quoted_id: int | None = None

        self.add_named(ChatPlaceholderBox(), "empty")

        self._activity_page = ActivityPage()
        self.add_named(self._activity_page, "activity")

        self._chat_function_page = ChatFunctionPage()
        self._chat_function_page.connect("finish", self._on_function_finished)
        self._chat_function_page.connect("message", self._on_function_message)
        self.add_named(self._chat_function_page, "function")

        self._chat_banner = ChatBanner()
        self._chat_control = ChatControl()
        self._message_action_box = MessageActionsBox()

        app.commands.connect("command-error", self._on_command_signal)
        app.commands.connect("command-not-found", self._on_command_signal)
        app.commands.connect("command-result", self._on_command_signal)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self._chat_banner)
        box.append(Gtk.Separator(margin_start=6, margin_end=6))
        box.append(self._chat_control.widget)
        box.append(self._message_action_box)

        dnd_icon = Gtk.Image.new_from_icon_name("mail-attachment-symbolic")
        dnd_icon.set_vexpand(True)
        dnd_icon.set_valign(Gtk.Align.END)
        dnd_icon.set_pixel_size(64)

        dnd_label = Gtk.Label(label=_("Drop files here"))
        dnd_label.set_max_width_chars(40)
        dnd_label.set_vexpand(True)
        dnd_label.set_valign(Gtk.Align.START)
        dnd_label.add_css_class("bold16")

        self._drop_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._drop_area.set_visible(False)
        self._drop_area.set_hexpand(True)
        self._drop_area.set_vexpand(True)
        self._drop_area.add_css_class("solid-background")
        self._drop_area.append(dnd_icon)
        self._drop_area.append(dnd_label)

        overlay = Gtk.Overlay()
        overlay.add_overlay(self._drop_area)
        overlay.set_child(box)

        # TODO: support dnd for contacts (MUC invitations)
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        self._connect(drop_target, "accept", self._on_drop_accept)
        self._connect(drop_target, "drop", self._on_file_drop)
        self._connect(drop_target, "enter", self._on_drag_enter)
        self._connect(drop_target, "leave", self._on_drag_leave)
        overlay.add_controller(drop_target)

        self.add_named(overlay, "controls")

        self._connect_actions()

        self.register_events(
            [
                ("message-received", 85, self._on_message_received),
                ("muc-disco-update", 85, self._on_muc_disco_update),
                ("account-connected", 85, self._on_account_state),
                ("account-disconnected", 85, self._on_account_state),
            ]
        )

    def do_unroot(self) -> None:
        Gtk.Stack.do_unroot(self)
        self._disconnect_all()
        self.unregister_events()
        app.check_finalize(self)

    def _get_current_contact(self) -> ChatContactT:
        assert self._current_contact is not None
        return self._current_contact

    def process_escape(self) -> bool:
        if self.get_visible_child_name() == "function":
            self._chat_function_page.process_escape()
            return True

        if self._chat_control.process_escape():
            return True

        return self._message_action_box.process_escape()

    def get_chat_control(self) -> ChatControl:
        return self._chat_control

    def get_message_action_box(self) -> MessageActionsBox:
        return self._message_action_box

    def get_message_input(self) -> MessageInputTextView:
        return self._message_action_box.msg_textview

    def show_chat(self, account: str, jid: JID) -> None:
        # Store (preserve) primary clipboard and restore it after switching
        clipboard = self.get_primary_clipboard()
        if clipboard.get_content() is not None:
            clipboard.read_text_async(
                None, self._on_primary_clipboard_read_text_finished
            )

        self._last_quoted_id = None

        if self._current_contact is not None:
            self._current_contact.disconnect_all_from_obj(self)

        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        self._current_contact = contact

        app.preview_manager.clear_previews()

        self._chat_banner.switch_contact(self._current_contact)
        self._chat_control.switch_contact(self._current_contact)
        self._message_action_box.switch_contact(self._current_contact)

        self._update_base_actions(self._current_contact)

        if isinstance(self._current_contact, GroupchatContact):
            self._current_contact.multi_connect(
                {
                    "user-joined": self._on_user_joined,
                    "user-role-changed": self._on_user_role_changed,
                    "user-affiliation-changed": self._on_user_affiliation_changed,
                    "state-changed": self._on_muc_state_changed,
                    "room-password-required": self._on_room_password_required,
                    "room-captcha-challenge": self._on_room_captcha_challenge,
                    "room-captcha-error": self._on_room_captcha_error,
                    "room-creation-failed": self._on_room_creation_failed,
                    "room-join-failed": self._on_room_join_failed,
                    "room-config-failed": self._on_room_config_failed,
                }
            )
            self._update_group_chat_actions(self._current_contact)

        elif isinstance(self._current_contact, GroupchatParticipant):
            self._update_participant_actions(self._current_contact)

        else:
            self._update_chat_actions(self._current_contact)

        if isinstance(self._current_contact, GroupchatContact):
            muc_data = client.get_module("MUC").get_muc_data(self._current_contact.jid)
            if muc_data is not None:
                if muc_data.state.is_captcha_request:
                    self._show_chat_function_page(FunctionMode.CAPTCHA_REQUEST)
                    return

                if muc_data.state.is_password_request:
                    self._show_chat_function_page(FunctionMode.PASSWORD_REQUEST)
                    return

                if not muc_data.state.is_joined:
                    if muc_data.error == "captcha-failed":
                        self._show_chat_function_page(
                            FunctionMode.CAPTCHA_ERROR, muc_data.error_text
                        )
                        return
                    if muc_data.error == "join-failed":
                        self._show_chat_function_page(
                            FunctionMode.JOIN_FAILED, muc_data.error_text
                        )
                        return
                    if muc_data.error == "creation-failed":
                        self._show_chat_function_page(
                            FunctionMode.CREATION_FAILED, muc_data.error_text
                        )
                        return

        self.set_transition_type(Gtk.StackTransitionType.NONE)
        self.set_visible_child_name("controls")

        app.plugin_manager.extension_point("switch_contact", self._current_contact)

        GLib.idle_add(self._message_action_box.msg_textview.grab_focus_delayed)

    def _on_primary_clipboard_read_text_finished(
        self,
        clipboard: Gdk.Clipboard,
        result: Gio.AsyncResult,
    ) -> None:
        text = clipboard.read_text_finish(result)
        if text is None:
            return

        # Reset primary clipboard to what it was before switching chats,
        # otherwise it gets overridden.
        clipboard.set(text)

    def show_activity_page(self) -> None:
        self._activity_page.set_visible_child_name("default")
        self.set_visible_child_name("activity")

    def _on_room_password_required(
        self, _contact: GroupchatContact, _signal_name: str
    ) -> None:

        self._show_chat_function_page(FunctionMode.PASSWORD_REQUEST)

    def _on_room_captcha_challenge(
        self, contact: GroupchatContact, _signal_name: str
    ) -> None:

        self._show_chat_function_page(FunctionMode.CAPTCHA_REQUEST)

    def _on_room_captcha_error(
        self, _contact: GroupchatContact, _signal_name: str, error: str
    ) -> None:

        self._show_chat_function_page(FunctionMode.CAPTCHA_ERROR, error)

    def _on_room_creation_failed(
        self, _contact: GroupchatContact, _signal_name: str, error: str
    ) -> None:

        self._show_chat_function_page(FunctionMode.CREATION_FAILED, error)

    def _on_room_join_failed(
        self, _contact: GroupchatContact, _signal_name: str, error: str
    ) -> None:

        self._show_chat_function_page(FunctionMode.JOIN_FAILED, error)

    def _on_room_config_failed(
        self, _contact: GroupchatContact, _signal_name: str, error: str
    ) -> None:

        self._show_chat_function_page(FunctionMode.CONFIG_FAILED)

    def _on_muc_state_changed(
        self, contact: GroupchatContact, _signal_name: str
    ) -> None:
        self._update_group_chat_actions(contact)

    def _on_user_joined(
        self,
        contact: GroupchatContact,
        _signal_name: str,
        _user_contact: GroupchatParticipant,
        _event: events.MUCUserJoined,
    ) -> None:

        self._update_group_chat_actions(contact)

    def _on_user_role_changed(
        self,
        contact: GroupchatContact,
        _signal_name: str,
        _user_contact: GroupchatParticipant,
        _event: events.MUCUserRoleChanged,
    ) -> None:

        self._update_group_chat_actions(contact)

    def _on_user_affiliation_changed(
        self,
        contact: GroupchatContact,
        _signal_name: str,
        _user_contact: GroupchatParticipant,
        _event: events.MUCUserAffiliationChanged,
    ) -> None:
        self._update_group_chat_actions(contact)

    def _on_muc_disco_update(self, event: events.MucDiscoUpdate) -> None:
        if not isinstance(self._current_contact, GroupchatContact):
            return

        if event.jid != self._current_contact.jid:
            return

        self._update_group_chat_actions(self._current_contact)

    def _on_account_state(
        self, event: events.AccountConnected | events.AccountDisconnected
    ) -> None:

        if self._current_contact is None:
            return

        if event.account != self._current_contact.account:
            return

        self._update_base_actions(self._current_contact)

        if isinstance(self._current_contact, GroupchatContact):
            self._update_group_chat_actions(self._current_contact)
        elif isinstance(self._current_contact, GroupchatParticipant):
            self._update_participant_actions(self._current_contact)
        else:
            self._update_chat_actions(self._current_contact)

    def _on_message_received(self, event: events.MessageReceived) -> None:
        if event.from_mam:
            return

        if app.window.is_chat_active(event.account, event.jid):
            if event.message.id is None:
                return

            client = app.get_client(event.account)
            contact = client.get_module("Contacts").get_contact(event.jid)
            assert isinstance(
                contact, BareContact | GroupchatContact | GroupchatParticipant
            )
            client.get_module("ChatMarkers").send_displayed_marker(
                contact, event.message.id, event.message.stanza_id
            )
            return

        message = event.message
        if message.direction == ChatDirection.OUTGOING:
            return

        if event.m_type == MessageType.GROUPCHAT:
            client = app.get_client(event.account)
            contact = client.get_module("Contacts").get_contact(
                event.jid, groupchat=True
            )
            assert isinstance(contact, GroupchatContact)
            # MUC messages may be received after some delay, so make sure we
            # don't issue notifications for our own messages.
            self_contact = contact.get_self()
            if self_contact is not None and self_contact.name == message.resource:
                return

        self._issue_notification(event.account, message)

    def _issue_notification(self, account: str, data: Message) -> None:

        text = data.text
        assert text is not None

        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact(data.remote.jid)

        title = _("New message from")

        is_previewable = app.preview_manager.is_previewable(text, data.oob)
        if is_previewable:
            scheme = urlparse(text).scheme
            if scheme == "geo":
                location = split_geo_uri(text)
                text = format_geo_coords(float(location.lat), float(location.lon))
            else:
                file_name = filename_from_uri(text)
                _icon, file_type = guess_simple_file_type(text)
                text = f"{file_type} ({file_name})"

        sound: str | None = None
        msg_type = "chat-message"
        if isinstance(contact, BareContact):
            msg_type = "chat-message"
            title += f" {contact.name}"
            sound = "first_message_received"
            app.window.set_urgency_hint(True)

        if isinstance(contact, GroupchatContact):
            msg_type = "group-chat-message"
            title += f" {data.resource} ({contact.name})"
            assert contact.nickname is not None
            needs_highlight = message_needs_highlight(
                text, contact.nickname, client.get_own_jid().bare
            )
            if needs_highlight:
                sound = "muc_message_highlight"
            else:
                sound = "muc_message_received"

            if not contact.can_notify() and not needs_highlight:
                return

            app.window.set_urgency_hint(True)

        if isinstance(contact, GroupchatParticipant):
            msg_type = "private-chat-message"
            title += f" {contact.name} (private in {contact.room.name})"
            sound = "first_message_received"

        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        if app.settings.get("notification_preview_message"):
            if text.startswith("/me "):
                name = contact.name
                if isinstance(contact, GroupchatContact):
                    name = data.resource
                text = f"* {name} {text[3:]}"
        else:
            text = ""

        if isinstance(contact, GroupchatContact):
            resource = data.resource
        else:
            resource = None

        app.ged.raise_event(
            events.Notification(
                account=contact.account,
                jid=contact.jid,
                type="incoming-message",
                sub_type=msg_type,
                title=title,
                text=text,
                sound=sound,
                resource=resource,
            )
        )

    def _connect_actions(self) -> None:
        actions = [
            "send-file",
            "send-file-httpupload",
            # 'send-file-jingle',
            "show-contact-info",
            "start-video-call",
            "start-voice-call",
            "send-message",
            "muc-change-nickname",
            "muc-invite",
            "muc-contact-info",
            "muc-execute-command",
            "muc-ban",
            "muc-kick",
            "muc-change-role",
            "muc-change-affiliation",
            "muc-request-voice",
            "quote-next",
            "quote-prev",
        ]

        for action in actions:
            action = app.window.lookup_action(action)
            assert action is not None
            action.connect("activate", self._on_action)

    def _update_base_actions(self, contact: ChatContactT) -> None:
        client = app.get_client(contact.account)
        online = app.account_is_connected(contact.account)

        app.window.get_action("send-message").set_enabled(
            allow_send_message(self._message_action_box.msg_textview.has_text, contact)
        )

        httpupload = app.window.get_action("send-file-httpupload")
        httpupload.set_enabled(online and client.get_module("HTTPUpload").available)

        # jingle = app.window.get_action('send-file-jingle')
        # jingle.set_enabled(online and contact.is_jingle_available)

        app.window.get_action("send-file").set_enabled(
            # jingle.get_enabled() or
            httpupload.get_enabled()
        )

        app.window.get_action("correct-message").set_enabled(online)

    def _update_chat_actions(self, contact: BareContact) -> None:
        online = app.account_is_connected(contact.account)

        app.window.get_action("start-voice-call").set_enabled(
            online and contact.supports_audio and sys.platform != "win32"
        )
        app.window.get_action("start-video-call").set_enabled(
            online and contact.supports_video and sys.platform != "win32"
        )

    def _update_group_chat_actions(self, contact: GroupchatContact) -> None:
        joined = contact.is_joined
        is_visitor = False
        if joined:
            self_contact = contact.get_self()
            assert self_contact
            is_visitor = self_contact.role.is_visitor

        app.window.get_action("muc-change-nickname").set_enabled(joined)
        app.window.get_action("muc-contact-info").set_enabled(joined)
        app.window.get_action("muc-execute-command").set_enabled(joined)
        app.window.get_action("muc-ban").set_enabled(joined)
        app.window.get_action("muc-kick").set_enabled(joined)
        app.window.get_action("muc-change-role").set_enabled(joined)
        app.window.get_action("muc-change-affiliation").set_enabled(joined)
        app.window.get_action("muc-invite").set_enabled(joined)

        app.window.get_action("muc-request-voice").set_enabled(is_visitor)

        app.window.get_action("moderate-message").set_enabled(joined)
        app.window.get_action("moderate-all-messages").set_enabled(joined)

    def _update_participant_actions(self, contact: GroupchatParticipant) -> None:
        pass

    def _on_action(self, action: Gio.SimpleAction, param: GLib.Variant | None) -> None:

        if self.get_visible_child_name() != "controls":
            return

        action_name = action.get_name()
        contact = self._current_contact
        if contact is None:
            return

        account = contact.account
        client = app.get_client(account)
        jid = contact.jid

        if action_name == "send-message":
            self._on_send_message()

        elif action_name == "start-voice-call":
            app.call_manager.start_call(account, jid, CallType.AUDIO)

        elif action_name == "start-video-call":
            app.call_manager.start_call(account, jid, CallType.VIDEO)

        elif action_name.startswith("send-file"):
            method = None
            name = action.get_name()
            if "httpupload" in name:
                method = "httpupload"

            # if 'jingle' in name:
            #     method = 'jingle'

            uris = None
            if param is not None:
                uris = param.get_strv() or None
            self._show_chat_function_page(FunctionMode.SEND_FILE, method, uris)

        elif action_name == "show-contact-info":
            if isinstance(contact, GroupchatContact):
                open_window("GroupchatDetails", contact=contact)
            else:
                open_window("ContactInfo", account=contact.account, contact=contact)

        elif action_name == "muc-contact-info":
            assert param is not None
            nick = param.get_string()
            assert isinstance(contact, GroupchatContact)
            resource_contact = contact.get_resource(nick)
            open_window("ContactInfo", account=account, contact=resource_contact)

        elif action_name == "muc-invite":
            self._show_chat_function_page(FunctionMode.INVITE)

        elif action_name == "muc-change-nickname":
            self._show_chat_function_page(FunctionMode.CHANGE_NICKNAME)

        elif action_name == "muc-execute-command":
            nick = None
            if param is not None:
                nick = param.get_string()
            if nick:
                assert isinstance(contact, GroupchatContact)
                resource_contact = contact.get_resource(nick)
                jid = resource_contact.jid
            open_window("AdHocCommands", account=account, jids=[jid])

        elif action_name == "muc-kick":
            assert param is not None
            kick_nick = param.get_string()
            self._show_chat_function_page(FunctionMode.KICK, data=kick_nick)

        elif action_name == "muc-ban":
            assert param is not None
            ban_jid = param.get_string()
            self._show_chat_function_page(FunctionMode.BAN, data=ban_jid)

        elif action_name == "muc-change-role":
            assert param is not None
            assert isinstance(contact, GroupchatContact)
            nick, role = param.get_strv()
            client.get_module("MUC").set_role(
                contact.jid,
                nick,
                role,
                callback=partial(
                    self._on_affiliation_or_role_change, contact, jid, role
                ),
            )

        elif action_name == "muc-change-affiliation":
            assert param is not None
            assert isinstance(contact, GroupchatContact)
            jid, affiliation = param.get_strv()
            client.get_module("MUC").set_affiliation(
                contact.jid,
                {jid: {"affiliation": affiliation}},
                callback=partial(
                    self._on_affiliation_or_role_change, contact, jid, affiliation
                ),
            )

        elif action_name == "muc-request-voice":
            client.get_module("MUC").request_voice(contact.jid)

        elif action_name.startswith("quote-"):
            view = self._chat_control.get_conversation_view()
            if action_name == "quote-prev":
                row = view.get_prev_message_row(self._last_quoted_id)
            else:
                row = view.get_next_message_row(self._last_quoted_id)

            if row is not None:
                self._last_quoted_id = row.pk
                self._message_action_box.insert_as_quote(row.get_text(), clear=True)

    def _on_affiliation_or_role_change(
        self,
        muc: GroupchatContact,
        jid: JID | str,
        affiliation_or_role: str,
        task: Task,
    ) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            log.error("Error on affiliation/role change request: %s", error)
            if self._current_contact == muc:
                self._chat_control.add_info_message(
                    _(
                        "An error occurred while trying to make "
                        "{occupant_jid} {affiliation_or_role}: {error}"
                    ).format(
                        occupant_jid=jid,
                        affiliation_or_role=affiliation_or_role,
                        error=str(error),
                    )
                )
            else:
                error_message = (
                    _(
                        "An error occurred while trying to make "
                        "{occupant_jid} {affiliation_or_role} in group "
                        '"{group}"'
                    ).format(
                        occupant_jid=jid,
                        affiliation_or_role=affiliation_or_role,
                        group=muc.name,
                    ),
                )
                SimpleDialog(_("Error"), f"{error_message}\n{error}")
        else:
            log.debug("Affiliation/role change success: %s", result)

    def _on_drag_enter(
        self,
        _drop_target: Gtk.DropTarget,
        _x: float,
        _y: float,
    ) -> Gdk.DragAction:
        self._drop_area.set_visible(True)
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, _drop_target: Gtk.DropTarget) -> None:
        self._drop_area.set_visible(False)

    def _on_drop_accept(self, _target: Gtk.DropTarget, drop: Gdk.Drop) -> bool:
        formats = drop.get_formats()
        return bool(formats.contain_gtype(Gdk.FileList))

    def _on_file_drop(
        self, _target: Gtk.DropTarget, value: Gdk.FileList | None, _x: float, _y: float
    ) -> bool:
        if value is None:
            log.debug("Drop received, but value is None")
            return False

        log.debug("Drop received: %s", value)
        files = value.get_files()
        if not files:
            return False

        if self._chat_control.has_active_chat():
            self._chat_control.drag_data_file_transfer(
                [file.get_uri() for file in files]
            )
            self._drop_area.set_visible(False)
            return True

        return False

    def _show_chat_function_page(
        self,
        function_mode: FunctionMode,
        data: str | None = None,
        files: list[str] | None = None,
    ) -> None:

        assert self._current_contact is not None
        self._chat_function_page.set_mode(
            self._current_contact, function_mode, data, files
        )
        self.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        self.set_visible_child_name("function")

    def _on_function_finished(
        self, _function_page: ChatFunctionPage, close_control: bool
    ) -> None:
        if close_control:
            self._close_control()
            self.set_visible_child_name("empty")
            self.set_transition_type(Gtk.StackTransitionType.NONE)
            return

        self.set_visible_child_name("controls")
        self.set_transition_type(Gtk.StackTransitionType.NONE)

    def _on_function_message(
        self, _function_page: ChatFunctionPage, message: str
    ) -> None:

        self._chat_control.add_info_message(message)

    def _on_send_message(self) -> None:
        message = self._message_action_box.get_text()
        if message.startswith("//"):
            # Escape sequence for chat commands
            message = message[1:]

        contact = self._current_contact
        assert contact is not None

        client = app.get_client(contact.account)

        encryption = contact.settings.get("encryption")
        if encryption == "OMEMO":
            if not client.get_module("OMEMO").check_send_preconditions(contact):
                return

        elif encryption:
            if encryption not in app.plugin_manager.encryption_plugins:
                SimpleDialog(
                    _("Encryption Error"), _("Missing necessary encryption plugin")
                )
                return

            self._chat_control.sendmessage = True
            app.plugin_manager.extension_point(
                "send_message" + encryption, self._chat_control
            )
            if not self._chat_control.sendmessage:
                return

        message = remove_invalid_xml_chars(message)
        if message in ("", "\n"):
            return

        label = self._message_action_box.get_seclabel()
        correct_id = self._message_action_box.get_correction_id()
        reply_data = self._message_action_box.get_message_reply()

        chatstate = client.get_module("Chatstate").get_active_chatstate(contact)

        message_ = OutgoingMessage(
            account=contact.account,
            contact=contact,
            text=message,
            chatstate=chatstate,
            sec_label=label,
            control=self._chat_control,
            correct_id=correct_id,
            reply_data=reply_data,
        )

        client.send_message(message_)

        self._message_action_box.reset_state_after_send()

        self._last_quoted_id = None

    def get_last_message_id(self, contact: ChatContactT) -> str | None:
        return self._message_action_box.get_last_message_id(contact)

    def _close_control(self) -> None:
        assert self._current_contact is not None
        app.window.activate_action(
            "win.remove-chat",
            GLib.Variant(
                "as", [self._current_contact.account, str(self._current_contact.jid)]
            ),
        )

    def clear(self) -> None:
        if self._current_contact is not None:
            self._current_contact.disconnect_all_from_obj(self)

        app.preview_manager.clear_previews()

        self._last_quoted_id = None
        self.set_visible_child_name("empty")
        self._chat_banner.clear()
        self._message_action_box.clear()
        self._chat_control.clear()

    def _on_command_signal(
        self, _chat_commands: ChatCommands, signal_name: str, text: str
    ) -> None:

        is_error = signal_name != "command-result"
        self._chat_control.add_command_output(text, is_error)


class ChatPlaceholderBox(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.set_valign(Gtk.Align.CENTER)
        image = Gtk.Image.new_from_icon_name("gajim-symbolic")
        image.set_pixel_size(100)
        image.set_opacity(0.2)
        self.append(image)

        button = Gtk.Button(label=_("Start Chatting…"))
        button.set_halign(Gtk.Align.CENTER)
        button.connect("clicked", self._on_start_chatting)
        self.append(button)

    def _on_start_chatting(self, _button: Gtk.Button) -> None:
        app.app.activate_action("start-chat", GLib.Variant("as", ["", ""]))
