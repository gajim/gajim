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

from datetime import datetime

from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import GLib

from gajim.common import app
from gajim.common.i18n import Q_
from gajim.common.helpers import is_retraction_allowed
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT

if TYPE_CHECKING:
    from .message import MessageRow

from ...util import wrap_with_event_box


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
                self._create_popover(show_retract=False)
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
                self._contact.account, self._contact.jid, self._row.message_id)

        self._create_popover(show_retract=show_retract,
                             show_correction=show_correction)

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

        self.set_label(timestamp_formatted)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.END)
        self.set_margin_start(6)
        self.set_margin_end(3)
        self.get_style_context().add_class('conversation-meta')
        self.set_tooltip_text(timestamp.strftime('%a, %d %b %Y - %X'))
