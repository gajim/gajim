# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from collections.abc import Callable
from datetime import datetime

import cairo
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

from gajim.gtk.menus import get_groupchat_participant_menu
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import get_cursor
from gajim.gtk.util import wrap_with_event_box


class SimpleLabel(Gtk.Label):
    def __init__(self) -> None:
        Gtk.Label.__init__(self)
        self.set_selectable(True)
        self.set_line_wrap(True)
        self.set_xalign(0)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)


@wrap_with_event_box
class MoreMenuButton(Gtk.Button):
    def __init__(self, on_click_handler: Callable[[Gtk.Button], Any]) -> None:
        Gtk.Button.__init__(self)
        self.set_valign(Gtk.Align.START)
        self.set_halign(Gtk.Align.END)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_hexpand(True)

        self.get_style_context().add_class('conversation-more-button')

        image = Gtk.Image.new_from_icon_name(
            'feather-more-horizontal-symbolic', Gtk.IconSize.BUTTON)
        self.add(image)

        self._click_handler_id = self.connect('clicked', on_click_handler)
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, _buton: MoreMenuButton) -> None:
        self.disconnect(self._click_handler_id)


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
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=3)

        self._encryption_image = Gtk.Image()
        self._encryption_image.set_no_show_all(True)
        self._encryption_image.set_margin_end(6)

        self._security_label = Gtk.Label()
        self._security_label.set_no_show_all(True)
        self._security_label.set_margin_end(6)
        self._security_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._security_label.set_max_width_chars(20)

        self._correction_image = Gtk.Image.new_from_icon_name(
            'document-edit-symbolic', Gtk.IconSize.MENU)
        self._correction_image.set_no_show_all(True)
        self._correction_image.get_style_context().add_class('dim-label')

        self._group_chat_message_state_image = Gtk.Image()
        self._group_chat_message_state_image.set_no_show_all(True)
        self._group_chat_message_state_image.get_style_context().add_class(
            'dim-label')

        self._marker_image = Gtk.Image.new_from_icon_name(
            'feather-check-symbolic', Gtk.IconSize.MENU)
        self._marker_image.set_no_show_all(True)
        self._marker_image.get_style_context().add_class('dim-label')
        self._marker_image.set_tooltip_text(p_('Message state', 'Received'))

        self._error_image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.MENU)
        self._error_image.get_style_context().add_class('warning-color')
        self._error_image.set_no_show_all(True)

        self.add(self._encryption_image)
        self.add(self._security_label)
        self.add(self._correction_image)
        self.add(self._group_chat_message_state_image)
        self.add(self._marker_image)
        self.add(self._error_image)
        self.show_all()

    def set_encryption_icon_visible(self, visible: bool) -> None:
        self._encryption_image.set_visible(visible)

    def set_encrytion_icon_data(self,
                                icon: str,
                                color: str,
                                tooltip: str
                                ) -> None:

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

    def set_group_chat_message_state_icon(self, state: MessageState) -> None:
        if state == MessageState.PENDING:
            icon_name = 'feather-clock-symbolic'
            tooltip_text = _('Pending')
        else:
            icon_name = 'feather-check-symbolic'
            tooltip_text = _('Received')
        self._group_chat_message_state_image.set_from_icon_name(
            icon_name, Gtk.IconSize.MENU)
        self._group_chat_message_state_image.set_tooltip_text(tooltip_text)
        self._group_chat_message_state_image.show()

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

    def _on_avatar_clicked(self,
                           _widget: Gtk.Widget,
                           event: Gdk.EventButton,
                           ) -> int:

        if event.type == Gdk.EventType.BUTTON_PRESS:
            if not isinstance(self._contact, GroupchatContact):
                return Gdk.EVENT_STOP

            if event.button == Gdk.BUTTON_PRIMARY:
                app.window.activate_action(
                    'mention', GLib.Variant('s', self._name))
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
        menu = get_groupchat_participant_menu(self._contact.account,
                                              self_contact,
                                              contact)

        popover = GajimPopover(menu, relative_to=self, event=event)
        popover.popup()
