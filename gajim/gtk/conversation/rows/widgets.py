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
from typing import Callable
from typing import Optional

from datetime import datetime

import cairo
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import p_
from gajim.common.modules.contacts import GroupchatContact
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
        self.connect('clicked', on_click_handler)


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
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self._correction_image = Gtk.Image.new_from_icon_name(
            'document-edit-symbolic', Gtk.IconSize.MENU)
        self._correction_image.set_no_show_all(True)
        self._correction_image.get_style_context().add_class('dim-label')

        self._marker_image = Gtk.Image()
        self._marker_image.set_no_show_all(True)
        self._marker_image.get_style_context().add_class('dim-label')

        self._error_image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.MENU)
        self._error_image.get_style_context().add_class('warning-color')
        self._error_image.set_no_show_all(True)

        self.add(self._correction_image)
        self.add(self._marker_image)
        self.add(self._error_image)
        self.show_all()

    def set_receipt_icon_visible(self, visible: bool) -> None:
        if not app.settings.get('positive_184_ack'):
            return
        self._marker_image.set_visible(visible)
        self._marker_image.set_from_icon_name(
            'feather-check-symbolic', Gtk.IconSize.MENU)
        self._marker_image.set_tooltip_text(p_('Message state', 'Received'))

    def set_correction_icon_visible(self, visible: bool) -> None:
        self._correction_image.set_visible(visible)

    def set_correction_tooltip(self, text: str) -> None:
        self._correction_image.set_tooltip_markup(text)

    def set_error_icon_visible(self, visible: bool) -> None:
        self._error_image.set_visible(visible)

    def set_error_tooltip(self, text: str) -> None:
        self._error_image.set_tooltip_markup(text)


class AvatarBox(Gtk.EventBox):
    def __init__(self,
                 contact: ChatContactT,
                 name: str,
                 avatar: Optional[cairo.ImageSurface],
                 ) -> None:

        Gtk.EventBox.__init__(self)

        self.set_size_request(AvatarSize.ROSTER, -1)
        self.set_valign(Gtk.Align.START)

        self._contact = contact

        self._image = Gtk.Image.new_from_surface(avatar)
        self.add(self._image)

        if self._contact.is_groupchat:
            self.connect('realize', self._on_realize)

        self.connect('button-press-event',
                     self._on_avatar_clicked, name)

    def set_from_surface(self, surface: Optional[cairo.ImageSurface]) -> None:
        self._image.set_from_surface(surface)

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
                           name: str
                           ) -> int:

        if event.type == Gdk.EventType.BUTTON_PRESS:
            if not isinstance(self._contact, GroupchatContact):
                return Gdk.EVENT_STOP

            if event.button == Gdk.BUTTON_PRIMARY:
                app.window.activate_action('mention', GLib.Variant('s', name))
            elif event.button == Gdk.BUTTON_SECONDARY:
                self._show_participant_menu(name, event)

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
