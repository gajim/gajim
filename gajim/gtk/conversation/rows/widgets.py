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

from typing import TYPE_CHECKING
from typing import Optional

from datetime import datetime

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import GLib
import cairo

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import Q_
from gajim.common.helpers import is_retraction_allowed
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT

if TYPE_CHECKING:
    from .message import MessageRow

from ...menus import get_groupchat_participant_menu
from ...util import wrap_with_event_box
from ...util import get_cursor
from ...util import GajimPopover


class SimpleLabel(Gtk.Label):
    def __init__(self) -> None:
        Gtk.Label.__init__(self)
        self.set_selectable(True)
        self.set_line_wrap(True)
        self.set_xalign(0)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)


@wrap_with_event_box
class MoreMenuButton(Gtk.Button):
    def __init__(self,
                 row: MessageRow,
                 contact: ChatContactT,
                 name: str
                 ) -> None:

        Gtk.Button.__init__(self)
        self.set_valign(Gtk.Align.START)
        self.set_halign(Gtk.Align.END)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_hexpand(True)

        self.get_style_context().add_class('conversation-more-button')

        self._row = row
        self._contact = contact
        self._name = name

        image = Gtk.Image.new_from_icon_name(
            'feather-more-horizontal-symbolic', Gtk.IconSize.BUTTON)
        self.add(image)
        self.connect('clicked', self._on_click)

    def _on_click(self, _button: Gtk.Button) -> None:
        show_retract = False
        if isinstance(self._contact, GroupchatContact):
            if not self._contact.is_joined:
                self._create_popover()
                return

            contact = self._contact.get_resource(self._name)
            self_contact = self._contact.get_self()
            assert self_contact is not None
            is_allowed = is_retraction_allowed(self_contact, contact)

            disco_info = app.storage.cache.get_last_disco_info(
                self._contact.jid)
            assert disco_info is not None

            if disco_info.has_message_moderation and is_allowed:
                show_retract = True

        show_correction = False
        if self._row.message_id is not None:
            show_correction = app.window.is_message_correctable(
                self._contact, self._row.message_id)

        self._create_popover(show_retract,
                             show_correction)

    def _create_popover(self,
                        show_retract: bool = False,
                        show_correction: bool = False
                        ) -> None:

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.get_style_context().add_class('padding-6')

        quote_enabled = True
        if isinstance(self._contact, GroupchatContact):
            if self._contact.is_joined:
                self_contact = self._contact.get_self()
                assert self_contact is not None
                quote_enabled = not self_contact.role.is_visitor
            else:
                quote_enabled = False

        quote_button = Gtk.ModelButton()
        quote_button.set_halign(Gtk.Align.START)
        quote_button.connect('clicked', self._row.on_quote_message)
        quote_button.set_label(Q_('?Message row action:Quote…'))
        quote_button.set_image(Gtk.Image.new_from_icon_name(
            'mail-reply-sender-symbolic', Gtk.IconSize.MENU))
        quote_button.set_sensitive(quote_enabled)
        menu_box.add(quote_button)

        copy_button = Gtk.ModelButton()
        copy_button.set_halign(Gtk.Align.START)
        copy_button.connect('clicked', self._row.on_copy_message)
        copy_button.set_label(Q_('?Message row action:Copy'))
        copy_button.set_image(Gtk.Image.new_from_icon_name(
            'edit-copy-symbolic', Gtk.IconSize.MENU))
        menu_box.add(copy_button)

        select_button = Gtk.ModelButton()
        select_button.set_halign(Gtk.Align.START)
        select_button.connect('clicked', self._on_activate_message_selection)
        select_button.set_label(Q_('?Message row action:Select Messages…'))
        select_button.set_image(Gtk.Image.new_from_icon_name(
            'edit-select-symbolic', Gtk.IconSize.MENU))
        menu_box.add(select_button)

        if show_correction:
            correct_button = Gtk.ModelButton()
            correct_button.set_halign(Gtk.Align.START)
            correct_button.connect(
                'clicked', self._row.on_correct_message)
            correct_button.set_label(Q_('?Message row action:Correct…'))
            correct_button.set_image(Gtk.Image.new_from_icon_name(
                'document-edit-symbolic', Gtk.IconSize.MENU))
            menu_box.add(correct_button)

        if show_retract:
            retract_button = Gtk.ModelButton()
            retract_button.set_halign(Gtk.Align.START)
            retract_button.connect(
                'clicked', self._row.on_retract_message)
            retract_button.set_label(Q_('?Message row action:Retract…'))
            retract_button.set_image(Gtk.Image.new_from_icon_name(
                'edit-undo-symbolic', Gtk.IconSize.MENU))
            menu_box.add(retract_button)

        menu_box.show_all()

        popover = Gtk.PopoverMenu()
        popover.add(menu_box)
        popover.set_relative_to(self)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.connect('closed', self._on_closed)
        popover.popup()

    def _on_activate_message_selection(self, _button: Gtk.ModelButton) -> None:
        app.window.activate_action(
            'activate-message-selection',
            GLib.Variant('u', self._row.log_line_id or 0))

    @staticmethod
    def _on_closed(popover: Gtk.Popover) -> None:
        GLib.idle_add(popover.destroy)


class DateTimeLabel(Gtk.Label):
    def __init__(self, timestamp: datetime) -> None:
        Gtk.Label.__init__(self)

        time_format = app.settings.get('chat_timestamp_format')
        if timestamp.date() < datetime.today().date():
            date_format = app.settings.get('date_timestamp_format')
            time_format = f'{time_format} - {date_format}'
        timestamp_formatted = timestamp.strftime(time_format)

        self.set_text(timestamp_formatted)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.END)
        self.set_margin_start(6)
        self.set_margin_end(3)
        self.get_style_context().add_class('conversation-meta')
        self.set_tooltip_text(timestamp.strftime('%a, %d %b %Y - %X'))


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
        self._marker_image.set_tooltip_text(Q_('?Message state:Received'))

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

            if event.button == 1:
                app.window.activate_action('mention', GLib.Variant('s', name))
            elif event.button == 3:
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
