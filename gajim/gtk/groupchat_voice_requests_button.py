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

from typing import cast

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from nbxmpp.structs import VoiceRequest

from gajim.common import app
from gajim.common.types import ChatContactT
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact


class VoiceRequestsButton(Gtk.Button):
    def __init__(self) -> None:
        Gtk.Button.__init__(self)
        self.set_tooltip_text(_('Pending Voice Requests'))
        self.set_no_show_all(True)
        image = Gtk.Image.new_from_icon_name(
            'dialog-question-symbolic', Gtk.IconSize.BUTTON)
        self.add(image)
        self.get_style_context().add_class('pulse-opacity')
        self.get_style_context().add_class('suggested-action')
        self.connect('clicked', self._on_button_clicked)

    def switch_contact(self, contact: ChatContactT) -> None:
        if not isinstance(contact, GroupchatContact):
            self._contact = None
            self.set_no_show_all(True)
            self.hide()
            return

        self._contact = contact
        self._update()

    def _update(self) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module('MUC').get_voice_requests(
            self._contact)
        self.hide()
        if voice_requests:
            self.set_no_show_all(False)
            self.show_all()

    def _on_button_clicked(self, _button: VoiceRequestsButton) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module('MUC').get_voice_requests(
            self._contact)
        if not voice_requests:
            return

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.get_style_context().add_class('padding-12')
        menu_box.set_hexpand(True)

        desc_label = Gtk.Label(label=_('Participants asking for voice:'))
        desc_label.get_style_context().add_class('dim-label')
        desc_label.set_max_width_chars(35)
        desc_label.set_line_wrap(True)
        desc_label.set_margin_bottom(6)
        menu_box.add(desc_label)

        for request in cast(list[VoiceRequest], voice_requests):
            request_box = Gtk.Box(spacing=12)

            name_label = Gtk.Label(label=request.nick)
            name_label.set_width_chars(10)
            name_label.set_max_width_chars(20)
            name_label.set_ellipsize(Pango.EllipsizeMode.END)
            name_label.set_xalign(0)
            request_box.add(name_label)

            decline_button = Gtk.Button.new_from_icon_name(
                'process-stop-symbolic', Gtk.IconSize.BUTTON)
            decline_button.set_tooltip_text(_('Decline'))
            decline_button.connect(
                'clicked',
                self._on_decline,
                request,
                self._contact)
            request_box.pack_end(decline_button, False, False, 0)

            approve_button = Gtk.Button.new_from_icon_name(
                'feather-check-symbolic', Gtk.IconSize.BUTTON)
            approve_button.set_tooltip_text(_('Approve'))
            approve_button.connect(
                'clicked',
                self._on_approve,
                request,
                self._contact)
            request_box.pack_end(approve_button, False, False, 0)

            if voice_requests.index(request) > 0:
                menu_box.add(Gtk.Separator())

            menu_box.add(request_box)

        menu_box.show_all()

        popover = Gtk.PopoverMenu()
        popover.get_style_context().add_class('padding-6')
        popover.set_relative_to(self)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.add(menu_box)
        popover.connect('closed', self._on_closed)
        popover.popup()

    @staticmethod
    def _on_closed(popover: Gtk.Popover) -> None:
        GLib.idle_add(popover.destroy)

    def _on_approve(self,
                    _button: Gtk.Button,
                    voice_request: VoiceRequest,
                    contact: GroupchatContact
                    ) -> None:

        client = app.get_client(contact.account)
        client.get_module('MUC').approve_voice_request(
            contact, voice_request)
        self._update()

    def _on_decline(self,
                    _button: Gtk.Button,
                    voice_request: VoiceRequest,
                    contact: GroupchatContact
                    ) -> None:

        client = app.get_client(contact.account)
        client.get_module('MUC').decline_voice_request(
            contact, voice_request)
        self._update()
