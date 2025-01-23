# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import TRUST_SYMBOL_DATA
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.archive.const import MessageState
from gajim.common.types import ChatContactT

from gajim.gtk.emoji_chooser import EmojiChooser
from gajim.gtk.menus import get_groupchat_participant_menu
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.widgets import GajimPopover

if TYPE_CHECKING:
    from gajim.gtk.conversation.rows.message import MessageRow


class SimpleLabel(Gtk.Label):
    def __init__(self) -> None:
        Gtk.Label.__init__(self)
        self.set_selectable(True)
        self.set_xalign(0)
        self.set_wrap(True)
        self.set_wrap_mode(Pango.WrapMode.WORD_CHAR)


class MessageRowActions(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(
            self,
            halign=Gtk.Align.END,
            valign=Gtk.Align.START,
            margin_start=40,
            margin_end=40,
            visible=False,
        )
        self.add_css_class("background")

        self._message_row: MessageRow | None = None
        self._contact: ChatContactT | None = None

        self._has_cursor = False
        self._is_menu_open = False

        self._timeout_id: int | None = None

        self._reaction_buttons: list[Gtk.Button | Gtk.MenuButton] = []

        for emoji in ["👍", "❤", "🤣"]:
            button = QuickReactionButton(emoji)
            button.connect("clicked", self._on_quick_reaction_button_clicked)
            self._reaction_buttons.append(button)

        choose_reaction_button = Gtk.MenuButton(
            icon_name="lucide-smile-plus-symbolic",
            tooltip_text=_("Add Reaction…"),
            visible=False,
        )
        choose_reaction_button.set_create_popup_func(self._on_emoji_create_popover)

        self._reaction_buttons.append(choose_reaction_button)

        self._reply_button = Gtk.Button.new_from_icon_name("lucide-reply-symbolic")
        self._reply_button.set_visible(False)
        self._reply_button.set_tooltip_text(_("Reply…"))
        self._reply_button.connect("clicked", self._on_reply_clicked)

        self._more_popover = Gtk.PopoverMenu()
        self._more_popover.connect("closed", self._on_popover_closed)

        self._more_button = Gtk.MenuButton(
            icon_name="feather-more-horizontal-symbolic", popover=self._more_popover
        )
        self._more_button.set_create_popup_func(self._on_create_more_popover)

        box = Gtk.Box()
        box.add_css_class("linked")

        for button in self._reaction_buttons:
            box.append(button)

        box.append(self._reply_button)
        box.append(self._more_button)

        self.append(box)

        hover_controller = Gtk.EventControllerMotion()
        hover_controller.connect("enter", self._on_cursor_enter)
        hover_controller.connect("leave", self._on_cursor_leave)
        self.add_controller(hover_controller)

        scroll_controller = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_controller.connect("scroll", self._on_scroll)
        self.add_controller(scroll_controller)

    def hide_actions(self) -> None:
        if self._is_menu_open:
            return

        # Set a 10ms timeout, which gives us enough time to inhibit hiding
        # if the cursor enters (cursor changes from row to MessageRowActions)
        self._hide_with_timeout()

    def update(self, y_coord: float, message_row: MessageRow) -> None:
        if self._is_menu_open:
            return

        self._message_row = message_row

        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        self_height = self.get_height()
        y_coord = max(y_coord, self_height)

        # Subtract some space to let MessageRowActions 'flow' above the row,
        # but make sure to make offset smaller than row height.
        offset = 12
        if self._message_row.is_merged:
            offset = min(28, self_height - 6)

        adjusted_y_coord = y_coord - offset
        adjusted_y_coord = max(adjusted_y_coord, 0)

        self.set_margin_top(int(adjusted_y_coord))

        message_row_width = self._message_row.get_width()
        reactions_visible = self._message_row.can_react()

        for button in self._reaction_buttons:
            if (
                isinstance(button, QuickReactionButton)
                and reactions_visible
                and message_row_width < 600
            ):
                # Don't show QuickReactionButtons on narrow screens
                button.set_visible(False)
                continue

            button.set_visible(reactions_visible)

        self._reply_button.set_visible(self._message_row.can_reply())
        self.set_visible(True)

    def switch_contact(self, contact: ChatContactT) -> None:
        self._message_row = None
        self._contact = contact

    def _hide_with_timeout(self) -> None:
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)

        self._timeout_id = GLib.timeout_add(10, self._hide)

    def _hide(self) -> None:
        self._timeout_id = None

        if self._has_cursor or self._message_row is None:
            return

        self._message_row.remove_css_class("conversation-row-hover")

        self.set_visible(False)

    def _on_cursor_enter(
        self,
        controller: Gtk.EventControllerMotion,
        _x: int,
        _y: int,
    ) -> None:

        self._has_cursor = True

        if self._is_menu_open:
            return

        if self._message_row is not None:
            # message_row may be None if MessageRowActions are entered without
            # hovering a MessageRow before (e.g. by switching chats via shortcut)
            self._message_row.add_css_class("conversation-row-hover")

    def _on_cursor_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._has_cursor = False

        if self._is_menu_open:
            # A popover triggers a leave event,
            # but we don't want to hide MessageRowActions
            return

        if self._message_row is not None:
            self._message_row.remove_css_class("conversation-row-hover")

    def _on_scroll(
        self,
        scroll_controller: Gtk.EventControllerScroll,
        _dx: float,
        dy: float,
    ) -> bool:
        if dy < 0:
            app.window.activate_action("win.scroll-view-up")
        else:
            app.window.activate_action("win.scroll-view-down")
        return Gdk.EVENT_PROPAGATE

    def _on_reply_clicked(self, _button: Gtk.Button) -> None:
        if self._message_row is None:
            return

        app.window.activate_action("win.reply", GLib.Variant("u", self._message_row.pk))

    def _on_quick_reaction_button_clicked(self, button: QuickReactionButton) -> None:
        self._send_reaction(button.emoji)

    def _on_emoji_create_popover(self, button: Gtk.MenuButton) -> None:
        self._is_menu_open = True
        emoji_chooser = app.window.get_emoji_chooser()
        button.set_popover(emoji_chooser)
        emoji_chooser.set_emoji_picked_func(self._on_reaction_added)
        emoji_chooser.connect_after("closed", self._on_popover_closed)

    def _on_reaction_added(self, _widget: EmojiChooser, emoji: str) -> None:
        # Remove emoji variant selectors
        emoji = emoji.strip("\uFE0E\uFE0F")
        self._send_reaction(emoji, toggle=False)

    def _send_reaction(self, emoji: str, toggle: bool = True) -> None:
        if self._message_row is None:
            return

        self._message_row.send_reaction(emoji, toggle)

    def _on_create_more_popover(self, button: Gtk.MenuButton) -> None:
        if self._message_row is None:
            return

        self._is_menu_open = True

        menu = self._message_row.get_chat_row_menu()
        self._more_popover.set_menu_model(menu)

    def _on_popover_closed(self, popover: Gtk.PopoverMenu) -> None:
        if isinstance(popover, EmojiChooser):
            popover.disconnect_by_func(self._on_popover_closed)

        if self._message_row is not None:
            self._message_row.remove_css_class("conversation-row-hover")

        self._is_menu_open = False
        self._hide_with_timeout()


class QuickReactionButton(Gtk.Button):
    def __init__(self, emoji: str) -> None:

        self.emoji = emoji

        # Add emoji presentation selector, otherwise depending on the font
        # emojis might be displayed in its text variant
        emoji_presentation_form = f"{emoji}\uFE0F"

        Gtk.Button.__init__(
            self,
            label=emoji_presentation_form,
            tooltip_text=_("React with %s") % emoji_presentation_form,
            visible=False,
        )

        self.remove_css_class("text-button")
        self.add_css_class("image-button")


class DateTimeLabel(Gtk.Label):
    def __init__(self, timestamp: datetime) -> None:
        Gtk.Label.__init__(self)

        format_string = app.settings.get("time_format")
        if timestamp.date() < datetime.today().date():
            format_string = app.settings.get("date_time_format")

        self.set_text(timestamp.strftime(format_string))
        self.set_selectable(True)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.END)
        self.set_margin_start(6)
        self.set_margin_end(3)
        self.add_css_class("conversation-meta")
        format_string = app.settings.get("date_time_format")
        self.set_tooltip_text(timestamp.strftime(format_string))


class NicknameLabel(Gtk.Label):
    def __init__(self, name: str, from_us: bool) -> None:
        Gtk.Label.__init__(self)

        self.set_selectable(True)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_valign(Gtk.Align.END)
        self.add_css_class("conversation-nickname")
        self.set_text(name)

        if from_us:
            css_class = "gajim-outgoing-nickname"
        else:
            css_class = "gajim-incoming-nickname"

        self.add_css_class(css_class)


class MessageIcons(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=3)

        self._encryption_image = Gtk.Image()
        self._encryption_image.set_visible(False)
        self._encryption_image.set_margin_end(6)

        self._security_label = Gtk.Label()
        self._security_label.set_visible(False)
        self._security_label.set_margin_end(6)
        self._security_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._security_label.set_max_width_chars(20)

        self._correction_image = Gtk.Image.new_from_icon_name("document-edit-symbolic")
        self._correction_image.set_visible(False)
        self._correction_image.add_css_class("dim-label")

        self._message_state_image = Gtk.Image()
        self._message_state_image.set_visible(False)
        self._message_state_image.add_css_class("dim-label")

        self._marker_image = Gtk.Image.new_from_icon_name("feather-check-symbolic")
        self._marker_image.set_visible(False)
        self._marker_image.add_css_class("dim-label")
        self._marker_image.set_tooltip_text(p_("Message state", "Received"))

        self._error_image = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        self._error_image.add_css_class("warning-color")
        self._error_image.set_visible(False)

        self.append(self._encryption_image)
        self.append(self._security_label)
        self.append(self._correction_image)
        self.append(self._message_state_image)
        self.append(self._marker_image)
        self.append(self._error_image)

    def set_encryption_icon_visible(self, visible: bool) -> None:
        self._encryption_image.set_visible(visible)

    def set_encrytion_icon_data(self, icon: str, color: str, tooltip: str) -> None:
        for trust_data in TRUST_SYMBOL_DATA.values():
            self._encryption_image.remove_css_class(trust_data[2])

        self._encryption_image.add_css_class(color)
        self._encryption_image.set_from_icon_name(icon)
        self._encryption_image.set_tooltip_markup(tooltip)

    def set_security_label_visible(self, visible: bool) -> None:
        self._security_label.set_visible(visible)

    def set_security_label_data(self, tooltip: str, markup: str) -> None:
        self._security_label.set_tooltip_text(tooltip)
        self._security_label.set_markup(markup)

    def set_receipt_icon_visible(self, visible: bool) -> None:
        if not app.settings.get("positive_184_ack"):
            return
        self._marker_image.set_visible(visible)

    def set_message_state_icon(self, state: MessageState) -> None:
        if state == MessageState.PENDING:
            icon_name = "feather-clock-symbolic"
            tooltip_text = _("Pending")
        else:
            icon_name = "feather-check-symbolic"
            tooltip_text = _("Received")
        self._message_state_image.set_from_icon_name(icon_name)
        self._message_state_image.set_tooltip_text(tooltip_text)
        self._message_state_image.set_visible(True)

    def hide_message_state_icon(self):
        self._message_state_image.set_visible(False)

    def set_correction_icon_visible(self, visible: bool) -> None:
        self._correction_image.set_visible(visible)

    def set_correction_tooltip(self, text: str) -> None:
        self._correction_image.set_tooltip_text(text)

    def set_error_icon_visible(self, visible: bool) -> None:
        self._error_image.set_visible(visible)

    def set_error_tooltip(self, text: str) -> None:
        self._error_image.set_tooltip_text(text)


class AvatarBox(Gtk.Box, SignalManager):
    def __init__(self, contact: ChatContactT) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self.set_size_request(AvatarSize.ROSTER, -1)
        self.set_valign(Gtk.Align.START)

        self._contact = contact
        self._name = ""

        self._image = Gtk.Image(pixel_size=AvatarSize.ROSTER)
        self.append(self._image)

        if self._contact.is_groupchat:
            self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        self._menu_popover = GajimPopover(None)
        self.append(self._menu_popover)

        gesture_left_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        self._connect(gesture_left_click, "pressed", self._on_avatar_clicked)
        self.add_controller(gesture_left_click)

        gesture_right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_right_click, "pressed", self._on_avatar_clicked)
        self.add_controller(gesture_right_click)

    def do_unroot(self):
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def set_from_paintable(self, texture: Gdk.Texture | None) -> None:
        self._image.set_from_paintable(texture)

    def set_name(self, name: str) -> None:
        self._name = name

    def set_merged(self, merged: bool) -> None:
        self._image.set_visible(not merged)

    def _on_avatar_clicked(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:
        if not isinstance(self._contact, GroupchatContact):
            return Gdk.EVENT_STOP

        if gesture_click.get_current_button() == Gdk.BUTTON_PRIMARY:
            app.window.activate_action("win.mention", GLib.Variant("s", self._name))
        elif gesture_click.get_current_button() == Gdk.BUTTON_SECONDARY:
            self._show_participant_menu(self._name, x, y)

        return Gdk.EVENT_STOP

    def _show_participant_menu(self, nick: str, x: float, y: float) -> None:
        assert isinstance(self._contact, GroupchatContact)
        if not self._contact.is_joined:
            return

        self_contact = self._contact.get_self()
        assert self_contact is not None

        if nick == self_contact.name:
            # Don’t show menu for us
            return

        contact = self._contact.get_resource(nick)
        menu = get_groupchat_participant_menu(
            self._contact.account, self_contact, contact
        )

        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x, y)
        self._menu_popover.popup()
