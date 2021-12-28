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

import typing
from typing import Union

from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import GLib

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import is_retraction_allowed
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from ...util import wrap_with_event_box

if typing.TYPE_CHECKING:
    from .message import MessageRow


ContactT = Union[BareContact, GroupchatContact, GroupchatParticipant]


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
                 contact: ContactT,
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
            disco_info = app.storage.cache.get_last_disco_info(
                self._contact.jid)
            assert disco_info is not None

            contact = self._contact.get_resource(self._name)
            self_contact = self._contact.get_self()
            assert self_contact is not None

            is_allowed = is_retraction_allowed(self_contact, contact)
            if disco_info.has_message_moderation and is_allowed:
                show_retract = True
        self._create_popover(show_retract)

    def _create_popover(self, show_retract: bool) -> None:
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.get_style_context().add_class('padding-6')

        quote_button = Gtk.ModelButton()
        quote_button.set_halign(Gtk.Align.START)
        quote_button.connect('clicked', self._row.on_quote_message)
        quote_button.set_label(_('Quote…'))
        quote_button.set_image(Gtk.Image.new_from_icon_name(
            'mail-reply-sender-symbolic', Gtk.IconSize.MENU))
        menu_box.add(quote_button)

        copy_button = Gtk.ModelButton()
        copy_button.set_halign(Gtk.Align.START)
        copy_button.connect('clicked', self._row.on_copy_message)
        copy_button.set_label(_('Copy'))
        copy_button.set_image(Gtk.Image.new_from_icon_name(
            'edit-copy-symbolic', Gtk.IconSize.MENU))
        menu_box.add(copy_button)

        if show_retract:
            retract_button = Gtk.ModelButton()
            retract_button.set_halign(Gtk.Align.START)
            retract_button.connect(
                'clicked', self._row.on_retract_message)
            retract_button.set_label(_('Retract'))
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
