# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.structs import VoiceRequest

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT


class VoiceRequestsButton(Gtk.Button):
    def __init__(self) -> None:
        Gtk.Button.__init__(self)
        self.set_tooltip_text(_('Pending Voice Requests'))
        self.set_visible(False)
        image = Gtk.Image.new_from_icon_name('dialog-question-symbolic')
        self.set_child(image)
        self.get_style_context().add_class('pulse-opacity')
        self.get_style_context().add_class('suggested-action')
        self.connect('clicked', self._on_button_clicked)

    def switch_contact(self, contact: ChatContactT) -> None:
        if not isinstance(contact, GroupchatContact):
            self._contact = None
            self.set_visible(False)
            self.hide()
            return

        self._contact = contact
        self._update()

    def _update(self) -> None:
        self.set_visible(False)
        self.hide()

        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module('MUC').get_voice_requests(
            self._contact)
        if voice_requests:
            self.show()

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
        desc_label.set_wrap_mode(Pango.WrapMode.WORD)
        desc_label.set_margin_bottom(6)
        menu_box.append(desc_label)

        for request in voice_requests:
            request_box = Gtk.Box(spacing=12)

            name_label = Gtk.Label(label=request.nick)
            name_label.set_width_chars(10)
            name_label.set_max_width_chars(20)
            name_label.set_ellipsize(Pango.EllipsizeMode.END)
            name_label.set_xalign(0)
            request_box.append(name_label)

            decline_button = Gtk.Button.new_from_icon_name(
                'process-stop-symbolic')
            decline_button.set_tooltip_text(_('Decline'))
            decline_button.connect(
                'clicked',
                self._on_decline,
                request,
                self._contact)
            request_box.append(decline_button)

            approve_button = Gtk.Button.new_from_icon_name(
                'feather-check-symbolic')
            approve_button.set_tooltip_text(_('Approve'))
            approve_button.connect(
                'clicked',
                self._on_approve,
                request,
                self._contact)
            request_box.append(approve_button)

            if voice_requests.index(request) > 0:
                menu_box.append(Gtk.Separator())

            menu_box.append(request_box)

        popover = Gtk.PopoverMenu()
        popover.get_style_context().add_class('padding-6')
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_child(menu_box)
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
