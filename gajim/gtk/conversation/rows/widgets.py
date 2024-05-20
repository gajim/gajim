# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

import cairo
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import TRUST_SYMBOL_DATA
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.archive.const import MessageState
from gajim.common.types import ChatContactT

from gajim.gtk.conversation.reactions_bar import AddReactionButton
from gajim.gtk.menus import get_groupchat_participant_menu
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import get_cursor

if TYPE_CHECKING:
    from gajim.gtk.conversation.rows.message import MessageRow


class SimpleLabel(Gtk.Label):
    def __init__(self) -> None:
        Gtk.Label.__init__(self)
        self.set_selectable(True)
        self.set_line_wrap(True)
        self.set_xalign(0)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)


class MessageRowActions(Gtk.EventBox):
    def __init__(self) -> None:
        Gtk.EventBox.__init__(
            self,
            halign=Gtk.Align.END,
            valign=Gtk.Align.START,
            margin_end=40,
            no_show_all=True,
        )
        self._message_row: MessageRow | None = None
        self._contact: ChatContactT | None = None

        self._has_cursor = False
        self._menu_button_clicked = False

        self._timeout_id: int | None = None

        self._default_reaction_button = Gtk.Button(
            label='👍', tooltip_text=_('React with 👍')
        )
        self._default_reaction_button.set_no_show_all(True)
        self._default_reaction_button.connect(
            'clicked', self._on_specific_reaction_button_clicked
        )
        self._default_reaction_button.get_style_context().remove_class('text-button')
        self._default_reaction_button.get_style_context().add_class('image-button')

        self._choose_reaction_button = AddReactionButton()
        self._choose_reaction_button.set_no_show_all(True)
        self._choose_reaction_button.connect(
            'clicked', self._on_choose_reaction_button_clicked)
        self._choose_reaction_button.connect('emoji-added', self._on_reaction_added)

        self._reply_button = Gtk.Button.new_from_icon_name(
            'lucide-reply-symbolic', Gtk.IconSize.BUTTON
        )
        self._reply_button.set_no_show_all(True)
        self._reply_button.set_tooltip_text(_('Reply…'))
        self._reply_button.connect('clicked', self._on_reply_clicked)

        more_button = Gtk.Button.new_from_icon_name(
            'feather-more-horizontal-symbolic', Gtk.IconSize.BUTTON
        )
        more_button.connect('clicked', self._on_more_clicked)

        box = Gtk.Box()
        box.get_style_context().add_class('linked')
        box.add(self._default_reaction_button)
        box.add(self._choose_reaction_button)
        box.add(self._reply_button)
        box.add(more_button)

        self.add(box)

        self.connect('enter-notify-event', self._on_hover)
        self.connect('leave-notify-event', self._on_hover)

    def hide_actions(self) -> None:
        # Set a 10ms timeout, which gives us enough time to inhibit hiding
        # if the cursor enters (cursor changes from row to MessageRowActions)
        self._timeout_id = GLib.timeout_add(10, self._hide)

    def update(self, y_coord: int, message_row: MessageRow) -> None:
        self._message_row = message_row
        self._menu_button_clicked = False

        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        self_height = self.get_allocated_height()
        if y_coord < self_height:
            y_coord = self_height

        # Subtract 12 to let MessageRowActions 'flow' above the row
        adjusted_y_coord = y_coord - 12
        if adjusted_y_coord < 0:
            adjusted_y_coord = 0

        self.set_margin_top(adjusted_y_coord)
        self.set_no_show_all(False)
        self.show_all()

        self._default_reaction_button.set_visible(self._get_reactions_visible())
        self._choose_reaction_button.set_visible(self._get_reactions_visible())
        self._reply_button.set_visible(self._get_reply_visible())

    def switch_contact(self, contact: ChatContactT) -> None:
        self._contact = contact

    def _get_reply_visible(self) -> bool:
        if isinstance(self._contact, GroupchatContact):
            assert self._message_row is not None
            if self._contact.is_joined and self._message_row.stanza_id is not None:
                self_contact = self._contact.get_self()
                assert self_contact is not None
                return not self_contact.role.is_visitor
            else:
                return False

        return True

    def _get_reactions_visible(self) -> bool:
        if (isinstance(self._contact, GroupchatContact) and
                self._contact.muc_context == 'public'):
            return self._contact.supports(Namespace.OCCUPANT_ID)

        return True

    def _hide(self) -> None:
        if self._has_cursor or self._message_row is None:
            return

        self._message_row.get_style_context().remove_class('conversation-row-hover')

        self._timeout_id = None
        self._menu_button_clicked = False

        self.hide()

    def _on_hover(self, _eventbox: MessageRowActions, event: Gdk.EventCrossing) -> bool:
        if event.type == Gdk.EventType.ENTER_NOTIFY:
            self._has_cursor = True
            self._menu_button_clicked = False
            assert self._message_row is not None
            self._message_row.get_style_context().add_class('conversation-row-hover')

        if (
            event.type == Gdk.EventType.LEAVE_NOTIFY
            and event.detail != Gdk.NotifyType.INFERIOR
        ):

            self._has_cursor = False
            self._timeout_id = None

            if self._menu_button_clicked:
                # A popover triggers a leave event,
                # but we don't want to hide MessageRowActions
                return True

            assert self._message_row is not None
            self._message_row.get_style_context().remove_class('conversation-row-hover')

            self.hide()

        return True

    def _on_reply_clicked(self, _button: Gtk.Button) -> None:
        assert self._message_row is not None
        app.window.activate_action('reply', GLib.Variant('u', self._message_row.pk))

    def _on_specific_reaction_button_clicked(self, button: Gtk.Button) -> None:
        self._send_reaction(button.get_label())

    def _on_choose_reaction_button_clicked(self, _button: AddReactionButton) -> None:
        self._menu_button_clicked = True

    def _on_reaction_added(self, _widget: AddReactionButton, emoji: str) -> None:
        self._menu_button_clicked = False
        self._send_reaction(emoji, toggle=False)

    def _send_reaction(self, emoji: str, toggle: bool = True) -> None:
        assert self._message_row is not None
        self._message_row.send_reaction(emoji, toggle)

    def _on_more_clicked(self, button: Gtk.Button) -> None:
        assert self._message_row is not None
        self._menu_button_clicked = True
        self._message_row.show_chat_row_menu(self, button)


class DateTimeLabel(Gtk.Label):
    def __init__(self, timestamp: datetime) -> None:
        Gtk.Label.__init__(self)

        format_string = app.settings.get('time_format')
        if timestamp.date() < datetime.today().date():
            format_string = app.settings.get('date_time_format')

        self.set_text(timestamp.strftime(format_string))
        self.set_selectable(True)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.END)
        self.set_margin_start(6)
        self.set_margin_end(3)
        self.get_style_context().add_class('conversation-meta')
        format_string = app.settings.get('date_time_format')
        self.set_tooltip_text(timestamp.strftime(format_string))


class NicknameLabel(Gtk.Label):
    def __init__(self, name: str, from_us: bool) -> None:
        Gtk.Label.__init__(self)

        self.set_selectable(True)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_valign(Gtk.Align.END)
        self.get_style_context().add_class('conversation-nickname')
        self.set_text(name)

        if from_us:
            css_class = 'gajim-outgoing-nickname'
        else:
            css_class = 'gajim-incoming-nickname'

        self.get_style_context().add_class(css_class)


class MessageIcons(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=3)

        self._encryption_image = Gtk.Image()
        self._encryption_image.set_no_show_all(True)
        self._encryption_image.set_margin_end(6)

        self._security_label = Gtk.Label()
        self._security_label.set_no_show_all(True)
        self._security_label.set_margin_end(6)
        self._security_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._security_label.set_max_width_chars(20)

        self._correction_image = Gtk.Image.new_from_icon_name(
            'document-edit-symbolic', Gtk.IconSize.MENU
        )
        self._correction_image.set_no_show_all(True)
        self._correction_image.get_style_context().add_class('dim-label')

        self._message_state_image = Gtk.Image()
        self._message_state_image.set_no_show_all(True)
        self._message_state_image.get_style_context().add_class('dim-label')

        self._marker_image = Gtk.Image.new_from_icon_name(
            'feather-check-symbolic', Gtk.IconSize.MENU
        )
        self._marker_image.set_no_show_all(True)
        self._marker_image.get_style_context().add_class('dim-label')
        self._marker_image.set_tooltip_text(p_('Message state', 'Received'))

        self._error_image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.MENU
        )
        self._error_image.get_style_context().add_class('warning-color')
        self._error_image.set_no_show_all(True)

        self.add(self._encryption_image)
        self.add(self._security_label)
        self.add(self._correction_image)
        self.add(self._message_state_image)
        self.add(self._marker_image)
        self.add(self._error_image)
        self.show_all()

    def set_encryption_icon_visible(self, visible: bool) -> None:
        self._encryption_image.set_visible(visible)

    def set_encrytion_icon_data(self, icon: str, color: str, tooltip: str) -> None:

        context = self._encryption_image.get_style_context()
        for trust_data in TRUST_SYMBOL_DATA.values():
            context.remove_class(trust_data[2])

        context.add_class(color)
        self._encryption_image.set_from_icon_name(icon, Gtk.IconSize.MENU)
        self._encryption_image.set_tooltip_markup(tooltip)

    def set_security_label_visible(self, visible: bool) -> None:
        self._security_label.set_visible(visible)

    def set_security_label_data(self, tooltip: str, markup: str) -> None:
        self._security_label.set_tooltip_text(tooltip)
        self._security_label.set_markup(markup)

    def set_receipt_icon_visible(self, visible: bool) -> None:
        if not app.settings.get('positive_184_ack'):
            return
        self._marker_image.set_visible(visible)

    def set_message_state_icon(self, state: MessageState) -> None:
        if state == MessageState.PENDING:
            icon_name = 'feather-clock-symbolic'
            tooltip_text = _('Pending')
        else:
            icon_name = 'feather-check-symbolic'
            tooltip_text = _('Received')
        self._message_state_image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        self._message_state_image.set_tooltip_text(tooltip_text)
        self._message_state_image.show()

    def hide_message_state_icon(self):
        self._message_state_image.hide()

    def set_correction_icon_visible(self, visible: bool) -> None:
        self._correction_image.set_visible(visible)

    def set_correction_tooltip(self, text: str) -> None:
        self._correction_image.set_tooltip_markup(text)

    def set_error_icon_visible(self, visible: bool) -> None:
        self._error_image.set_visible(visible)

    def set_error_tooltip(self, text: str) -> None:
        self._error_image.set_tooltip_markup(text)


class AvatarBox(Gtk.EventBox):
    def __init__(self, contact: ChatContactT) -> None:
        Gtk.EventBox.__init__(self)
        self.set_size_request(AvatarSize.ROSTER, -1)
        self.set_valign(Gtk.Align.START)

        self._contact = contact
        self._name = ''

        self._image = Gtk.Image()
        self.add(self._image)

        if self._contact.is_groupchat:
            self.connect('realize', self._on_realize)

        self.connect('button-press-event', self._on_avatar_clicked)

    def set_from_surface(self, surface: cairo.ImageSurface | None) -> None:
        self._image.set_from_surface(surface)

    def set_name(self, name: str) -> None:
        self._name = name

    def set_merged(self, merged: bool) -> None:
        self._image.set_no_show_all(merged)
        self._image.set_visible(not merged)

    @staticmethod
    def _on_realize(event_box: Gtk.EventBox) -> None:
        window = event_box.get_window()
        if window is not None:
            window.set_cursor(get_cursor('pointer'))

    def _on_avatar_clicked(
        self,
        _widget: Gtk.Widget,
        event: Gdk.EventButton,
    ) -> int:

        if event.type == Gdk.EventType.BUTTON_PRESS:
            if not isinstance(self._contact, GroupchatContact):
                return Gdk.EVENT_STOP

            if event.button == Gdk.BUTTON_PRIMARY:
                app.window.activate_action('mention', GLib.Variant('s', self._name))
            elif event.button == Gdk.BUTTON_SECONDARY:
                self._show_participant_menu(self._name, event)

        return Gdk.EVENT_STOP

    def _show_participant_menu(self, nick: str, event: Gdk.EventButton) -> None:
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

        popover = GajimPopover(menu, relative_to=self, event=event)
        popover.popup()
