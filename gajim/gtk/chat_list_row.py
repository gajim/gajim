# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal

from datetime import datetime
from urllib.parse import urlparse

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import Draft
from gajim.common.const import RowHeaderType
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.modules.message_util import get_nickname_from_message
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.draft import DraftStorage
from gajim.common.types import ChatContactT
from gajim.common.util.muc import get_groupchat_name
from gajim.common.util.muc import message_needs_highlight
from gajim.common.util.preview import filename_from_uri
from gajim.common.util.preview import format_geo_coords
from gajim.common.util.preview import guess_simple_file_type
from gajim.common.util.preview import split_geo_uri
from gajim.common.util.user_strings import get_moderation_text
from gajim.common.util.user_strings import get_retraction_text
from gajim.common.util.user_strings import get_uf_relative_time

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_chat_list_row_menu
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.widgets import GajimPopover


class ChatListRow(Gtk.ListBoxRow, SignalManager):

    __gsignals__ = {
        "unread-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "context-menu-state-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(
        self,
        workspace_id: str,
        account: str,
        jid: JID,
        type_: Literal["chat", "groupchat", "pm"],
        pinned: bool,
        position: int,
    ) -> None:

        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)

        self.account = account
        self.jid = jid
        self.workspace_id = workspace_id
        self.type = type_
        self.position = position
        self._has_draft = False

        self._conversations_header = RowHeader(RowHeaderType.CONVERSATIONS)
        self._pinned_header = RowHeader(RowHeaderType.PINNED)

        self._client = app.get_client(account)

        self.contact = self._client.get_module("Contacts").get_contact(jid)
        assert isinstance(
            self.contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        self._connect_contact_signals()

        self.contact_name: str = self.contact.name
        self.timestamp: float = 0
        self.stanza_id: str | None = None
        self.message_id: str | None = None

        self._unread_count: int = 0
        self._needs_muc_highlight: bool = False
        self._pinned: bool = pinned

        self.add_css_class("chatlist-row")

        self._ui = get_builder("chat_list_row.ui")
        self.set_child(self._ui.mainbox)

        self._connect(self._ui.close_button, "clicked", self._on_close_button_clicked)

        self._menu_popover = GajimPopover(None)
        self._connect(self._menu_popover, "closed", self._on_context_popover_closed)
        self._ui.mainbox.append(self._menu_popover)

        self._connect(self, "state-flags-changed", self._on_state_flags_changed)

        gesture_middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        self._connect(gesture_middle_click, "pressed", self._on_row_clicked)
        self.add_controller(gesture_middle_click)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_row_clicked)
        self.add_controller(gesture_secondary_click)

        app.settings.connect_signal(
            "mute_until",
            self._on_mute_setting_changed,
            self.contact.account,
            self.contact.jid,
        )
        self._on_mute_setting_changed()

        drag_source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        self._connect(drag_source, "prepare", self._on_prepare)
        self._connect(drag_source, "drag-begin", self._on_drag_begin)
        self._connect(drag_source, "drag-end", self._on_drag_end)
        self.add_controller(drag_source)

        if self.type == "groupchat":
            self._ui.group_chat_indicator.set_visible(True)

        self.update_avatar()
        self.update_name()
        self.update_account_identifier()

        app.storage.drafts.connect("draft-update", self._on_draft_update)

        if isinstance(self.contact, GroupchatContact) and not self.contact.can_notify():
            self._ui.unread_label.add_css_class("unread-counter-silent")

        draft = app.storage.drafts.get(self.contact)
        if not self._set_draft_mode(draft):
            self._display_last_conversation_row()

    def _display_last_conversation_row(self) -> None:
        message = app.storage.archive.get_last_conversation_row(
            self.contact.account, self.contact.jid
        )
        if message is None:
            self.set_visible(True)
            return

        assert isinstance(
            self.contact, BareContact | GroupchatContact | GroupchatParticipant
        )

        if message.text is not None:
            message_text = message.text

            if message.moderation is not None:
                message_text = get_moderation_text(
                    message.moderation.by, message.moderation.reason
                )

            elif message.retraction is not None:
                message_text = get_retraction_text(message.retraction.timestamp)

            elif corrected_message := message.get_last_correction():
                message_text = corrected_message.text
                assert message_text is not None

            # Nickname
            nickname = None
            if (
                message.type == MessageType.CHAT
                and message.direction == ChatDirection.OUTGOING
            ):
                self.set_nick(_("Me"))
                nickname = app.nicks[self.contact.account]

            elif message.type in (MessageType.GROUPCHAT, MessageType.PM):
                nickname = get_nickname_from_message(message) or None
                if message.direction == ChatDirection.OUTGOING:
                    self.set_nick(_("Me"))
                else:
                    self.set_nick(nickname)

            self.set_message_text(message_text, nickname=nickname, oob=message.oob)

            self.set_timestamp(message.timestamp)

            self.stanza_id = message.stanza_id
            self.message_id = message.id

        if message.filetransfers:
            self.set_message_text(_("File"), icon_name="lucide-paperclip-symbolic")
            self.set_timestamp(message.timestamp)

        if message.call is not None:
            self.set_message_text(_("Call"), icon_name="lucide-phone-symbolic")
            self.set_timestamp(message.timestamp)

    @property
    def is_pinned(self) -> bool:
        return self._pinned

    @property
    def has_draft(self) -> bool:
        return self._has_draft

    @property
    def unread_count(self) -> int:
        if (
            isinstance(self.contact, GroupchatContact)
            and not self.contact.can_notify()
            and not self._needs_muc_highlight
        ):
            return 0
        return self._unread_count

    @unread_count.setter
    def unread_count(self, value: int) -> None:
        self._unread_count = value
        self._update_unread()
        self.emit("unread-changed")

    def get_header_type(self) -> RowHeaderType | None:
        header = self.get_header()
        if header is None:
            return None
        assert isinstance(header, RowHeader)
        return header.type

    def set_header_type(self, header_type: RowHeaderType | None) -> None:
        if header_type == self.get_header_type():
            return

        if header_type is None:
            self.set_header(None)

        elif header_type == RowHeaderType.PINNED:
            self.set_header(self._pinned_header)

        else:
            self.set_header(self._conversations_header)

    def clear(self) -> None:
        self.timestamp = 0
        self.stanza_id = None
        self.message_id = None
        self.set_message_text("")
        self.set_nick("")

    def set_message_id(self, message_id: str) -> None:
        self.message_id = message_id

    def set_message_text(
        self,
        text: str,
        nickname: str | None = None,
        icon_name: str | None = None,
        oob: list[mod.OOB] | None = None,
    ) -> None:

        if self._has_draft:
            return

        assert isinstance(
            self.contact, BareContact | GroupchatContact | GroupchatParticipant
        )

        icon = None
        if icon_name is not None:
            icon = Gio.Icon.new_for_string(icon_name)

        if app.preview_manager.is_previewable(text, oob or []):
            scheme = urlparse(text).scheme
            if scheme == "geo":
                location = split_geo_uri(text)
                icon = Gio.Icon.new_for_string("lucide-map-pin-symbolic")
                text = format_geo_coords(float(location.lat), float(location.lon))
            else:
                file_name = filename_from_uri(text)
                icon, file_type = guess_simple_file_type(text)
                text = f"{file_type} ({file_name})"

        text = GLib.markup_escape_text(text)
        if text.startswith("/me ") and nickname is not None:
            nickname = GLib.markup_escape_text(nickname)
            text = text.replace("/me", f"* {nickname}", 1)
            text = f"<i>{text}</i>"

        # Split by newline and display last line (or first, if last is newline)
        lines = text.split("\n")
        text = lines[-1] or lines[0]
        self._ui.message_label.set_markup(text)

        if icon is None:
            self._ui.message_icon.set_visible(False)
        else:
            self._ui.message_icon.set_from_gicon(icon)
            self._ui.message_icon.set_visible(True)

    def set_nick(self, nickname: str | None) -> None:
        self._ui.nick_label.set_visible(bool(nickname))
        self._ui.nick_label.set_text(_("%(nickname)s:") % {"nickname": nickname})

    def get_real_unread_count(self) -> int:
        return self._unread_count

    def set_stanza_id(self, stanza_id: str | None) -> None:
        self.stanza_id = stanza_id

    def set_timestamp(self, timestamp: datetime) -> None:
        self.timestamp = timestamp.timestamp()
        self.update_time()

    def update_account_identifier(self) -> None:
        account_class = app.css_config.get_dynamic_class(self.account)
        self._ui.account_identifier.add_css_class(account_class)
        show = len(app.settings.get_active_accounts()) > 1
        self._ui.account_identifier.set_visible(show)

    def update_avatar(self) -> None:
        scale = self.get_scale_factor()
        assert isinstance(
            self.contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        texture = self.contact.get_avatar(AvatarSize.ROSTER, scale)
        self._ui.avatar_image.set_pixel_size(AvatarSize.ROSTER)
        self._ui.avatar_image.set_from_paintable(texture)

    def update_name(self) -> None:
        assert isinstance(
            self.contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        if self.type == "pm":
            client = app.get_client(self.account)
            muc_name = get_groupchat_name(client, self.jid.new_as_bare())
            self._ui.name_label.set_text(f"{self.contact.name} ({muc_name})")
            return

        self.contact_name = self.contact.name
        if self.jid == self._client.get_own_jid().bare:
            self.contact_name = _("Note to myself")
        self._ui.name_label.set_text(self.contact_name)

    def update_time(self) -> None:
        if self.timestamp == 0:
            return
        self._ui.timestamp_label.set_text(
            get_uf_relative_time(datetime.fromtimestamp(self.timestamp))
        )

    def update_row_state(self) -> None:
        self.update_time()
        self._ui.mute_image.set_visible(self.contact.is_muted)

    def add_unread(self, text: str) -> None:
        assert self.message_id is not None
        self._unread_count += 1
        self._update_unread()
        app.storage.cache.set_unread_count(
            self.account,
            self.jid,
            self.get_real_unread_count(),
            self.message_id,
            self.timestamp,
        )

        if (
            isinstance(self.contact, GroupchatContact)
            and self.contact.nickname is not None
        ):
            if message_needs_highlight(
                text, self.contact.nickname, self._client.get_own_jid().bare
            ):
                self._needs_muc_highlight = True
                self._ui.unread_label.remove_css_class("unread-counter-silent")

        self.emit("unread-changed")

    def reset_unread(self) -> None:
        self._needs_muc_highlight = False
        self._unread_count = 0
        self._update_unread()
        self.emit("unread-changed")

        app.storage.cache.reset_unread_count(self.account, self.jid)

        # Add class again in case we were mentioned previously
        if isinstance(self.contact, GroupchatContact) and not self.contact.can_notify():
            self._ui.unread_label.add_css_class("unread-counter-silent")

    def toggle_pinned(self) -> None:
        self._pinned = not self._pinned

    def _update_unread(self) -> None:
        unread_count = self._get_unread_string(self._unread_count)
        self._ui.unread_label.set_text(unread_count)
        self._ui.unread_label.set_visible(bool(self._unread_count))

    @staticmethod
    def _get_unread_string(count: int) -> str:
        if count < 1000:
            return str(count)
        return "999+"

    def _on_mute_setting_changed(self, *args: Any) -> None:
        self._ui.mute_image.set_visible(self.contact.is_muted)

    def _on_draft_update(
        self,
        _draft_storage: DraftStorage,
        _signal_name: str,
        contact: ChatContactT,
        draft: Draft | None,
    ) -> None:

        if contact != self.contact:
            return

        if not self._set_draft_mode(draft):
            self._display_last_conversation_row()
        self.changed()

    def _set_draft_mode(self, draft: Draft | None) -> bool:
        self._has_draft = draft is not None

        if draft is None:
            self._ui.message_label.remove_css_class("draft")

        else:
            self.set_nick("")
            self._ui.message_label.set_text(_("Draft: %s") % draft.text)
            self._ui.message_label.add_css_class("draft")

        return self._has_draft

    def _on_state_flags_changed(
        self, _row: ChatListRow, _flags: Gtk.StateFlags
    ) -> None:
        state = self.get_state_flags()
        if (state & Gtk.StateFlags.PRELIGHT) != 0:
            self._ui.revealer.set_reveal_child(True)
        else:
            self._ui.revealer.set_reveal_child(False)

    def do_unroot(self) -> None:
        self._disconnect_all()

        app.storage.drafts.disconnect_all_from_obj(self)
        app.settings.disconnect_signals(self)

        self._client.disconnect_all_from_obj(self)
        self.contact.disconnect_all_from_obj(self)
        if isinstance(self.contact, GroupchatParticipant):
            self.contact.room.disconnect_all_from_obj(self)

        del self._menu_popover
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.reset_unread()
        app.window.activate_action(
            "win.remove-chat", GLib.Variant("as", [self.account, str(self.jid)])
        )

    def _on_row_clicked(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:

        if gesture_click.get_current_button() == Gdk.BUTTON_MIDDLE:
            app.window.activate_action(
                "win.remove-chat", GLib.Variant("as", [self.account, str(self.jid)])
            )
        elif gesture_click.get_current_button() == Gdk.BUTTON_SECONDARY:
            self._raise_context_popover(x, y)

        return Gdk.EVENT_STOP

    def _raise_context_popover(self, x: float, y: float):
        menu = get_chat_list_row_menu(
            self.workspace_id, self.account, self.jid, self._pinned
        )

        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x=x, y=y)
        self.emit("context-menu-state-changed", True)
        self._menu_popover.popup()

    def _on_context_popover_closed(self, _popover: Gtk.Popover) -> None:
        self.emit("context-menu-state-changed", False)

    def _on_prepare(
        self, _drag_source: Gtk.DragSource, _x: float, _y: float
    ) -> Gdk.ContentProvider:
        value = GObject.Value()
        value.init(ChatListRow)
        value.set_object(self)

        return Gdk.ContentProvider.new_for_value(value)

    def _on_drag_begin(self, _drag_source: Gtk.DragSource, drag: Gdk.Drag) -> None:
        assert not isinstance(self.contact, ResourceContact)

        is_LTR = bool(self.get_direction() == Gtk.TextDirection.LTR)

        Gtk.DragIcon.set_from_paintable(
            drag,
            Gtk.WidgetPaintable().new(self),
            hot_x=0 if is_LTR else self.get_width(),
            hot_y=0,
        )

        app.window.highlight_dnd_targets(self, True)

    def _on_drag_end(
        self, _drag_source: Gtk.DragSource, _drag: Gdk.Drag, _delete_data: bool
    ) -> None:
        app.window.highlight_dnd_targets(self, False)

    def _connect_contact_signals(self) -> None:
        self.contact.connect("chatstate-update", self._on_chatstate_update)
        if isinstance(self.contact, BareContact):
            self.contact.connect("presence-update", self._on_presence_update)
            self.contact.connect("nickname-update", self._on_nickname_update)
            self.contact.connect("caps-update", self._on_avatar_update)
            self.contact.connect("avatar-update", self._on_avatar_update)

        elif isinstance(self.contact, GroupchatContact):
            self.contact.connect("avatar-update", self._on_avatar_update)
            self.contact.connect("disco-info-update", self._on_disco_info_update)
            self.contact.connect("state-changed", self._on_muc_state_changed)
            self.contact.connect("mam-sync-started", self._on_mam_sync_changed)
            self.contact.connect("mam-sync-finished", self._on_mam_sync_changed)
            self.contact.connect("mam-sync-error", self._on_mam_sync_error)

            self._client.connect_signal("state-changed", self._on_client_state_changed)

        elif isinstance(self.contact, GroupchatParticipant):
            self.contact.connect("user-joined", self._on_muc_user_update)
            self.contact.connect("user-left", self._on_muc_user_update)
            self.contact.connect("user-avatar-update", self._on_muc_user_update)
            self.contact.connect("user-status-show-changed", self._on_muc_user_update)

            self.contact.room.connect("room-left", self._on_muc_update)
            self.contact.room.connect("room-destroyed", self._on_muc_update)
            self.contact.room.connect("room-kicked", self._on_muc_update)

        else:
            raise TypeError("Unknown contact type: %s" % type(self.contact))

    def _on_presence_update(self, _contact: ChatContactT, _signal_name: str) -> None:
        self.update_avatar()

    def _on_avatar_update(self, _contact: ChatContactT, _signal_name: str) -> None:
        self.update_avatar()

    def _on_disco_info_update(self, _contact: ChatContactT, _signal_name: str) -> None:
        self.update_name()

    def _on_client_state_changed(self, *args: Any) -> None:
        self._update_joined_state()

    def _on_muc_state_changed(self, *args: Any) -> None:
        self._update_joined_state()

    def _update_joined_state(self) -> None:
        self._reset_connection_icon()

        assert isinstance(self.contact, GroupchatContact)
        if self.contact.is_joining:
            self._ui.connection_icon.set_from_icon_name("lucide-refresh-cw-symbolic")
            self._ui.connection_icon.add_css_class("spin")
            self._ui.connection_icon.add_css_class("dimmed")
            self._ui.connection_icon.set_tooltip_text(_("Joining Group Chat…"))
            self._ui.connection_icon.set_visible(True)
        elif self.contact.is_not_joined or not self._client.state.is_available:
            self._ui.connection_icon.set_from_icon_name("lucide-zap-symbolic")
            self._ui.connection_icon.add_css_class("warning")
            self._ui.connection_icon.set_tooltip_text(_("Not connected"))
            self._ui.connection_icon.set_visible(True)

    def _on_mam_sync_changed(
        self, _contact: GroupchatContact, signal_name: str
    ) -> None:

        self._reset_connection_icon()

        if signal_name == "mam-sync-started":
            self._ui.connection_icon.set_from_icon_name("lucide-refresh-cw-symbolic")
            self._ui.connection_icon.add_css_class("spin")
            self._ui.connection_icon.add_css_class("accent")
            self._ui.connection_icon.set_tooltip_text(_("Fetching messages…"))
            self._ui.connection_icon.set_visible(True)

    def _on_mam_sync_error(
        self, _contact: GroupchatContact, _signal_name: str, error_text: str
    ) -> None:

        self._reset_connection_icon()
        self._ui.connection_icon.set_from_icon_name("lucide-zap-symbolic")
        self._ui.connection_icon.add_css_class("error")
        self._ui.connection_icon.set_tooltip_text(
            _("There has been an error while trying to fetch messages: %s") % error_text
        )
        self._ui.connection_icon.set_visible(True)

    def _reset_connection_icon(self) -> None:
        self._ui.connection_icon.set_visible(False)
        self._ui.connection_icon.remove_css_class("spin")
        self._ui.connection_icon.remove_css_class("dimmed")
        self._ui.connection_icon.remove_css_class("accent")
        self._ui.connection_icon.remove_css_class("warning")
        self._ui.connection_icon.remove_css_class("error")

    def _on_muc_user_update(
        self, _contact: GroupchatParticipant, _signal_name: str, *args: Any
    ) -> None:
        self.update_avatar()

    def _on_muc_update(
        self, _contact: GroupchatContact, _signal_name: str, *args: Any
    ) -> None:
        self.update_avatar()

    def _on_chatstate_update(self, contact: ChatContactT, _signal_name: str) -> None:
        if contact.is_groupchat:
            assert isinstance(contact, GroupchatContact)
            self._ui.chatstate_image.set_visible(contact.has_composing_participants())
            return

        if contact.chatstate is None:
            self._ui.chatstate_image.set_visible(False)
        else:
            self._ui.chatstate_image.set_visible(contact.chatstate.is_composing)

    def _on_nickname_update(self, _contact: ChatContactT, _signal_name: str) -> None:
        self.update_name()


class RowHeader(Gtk.Box):
    def __init__(self, header_type: RowHeaderType) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.type = header_type

        if header_type == RowHeaderType.CONVERSATIONS:
            text = _("Conversations")
        else:
            text = _("Pinned")

        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)

        self.append(label)

        self.add_css_class("header-box")
        if header_type == RowHeaderType.PINNED:
            self.add_css_class("header-box-first")
