# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.structs import VoiceRequest

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT

from gajim.gtk.util import SignalManager


class VoiceRequestsButton(Gtk.Button, SignalManager):
    def __init__(self) -> None:
        Gtk.Button.__init__(
            self,
            tooltip_text=_("Pending Voice Requests"),
            visible=False,
        )
        SignalManager.__init__(self)

        inner_box = Gtk.Box()
        self.set_child(inner_box)

        image = Gtk.Image.new_from_icon_name("dialog-question-symbolic")
        inner_box.append(image)

        self.add_css_class("pulse-opacity")
        self.add_css_class("suggested-action")

        self._popover = Gtk.Popover()
        inner_box.append(self._popover)

        self._connect(self, "clicked", self._on_button_clicked)

    def switch_contact(self, contact: ChatContactT) -> None:
        if not isinstance(contact, GroupchatContact):
            self._contact = None
            self.set_visible(False)
            self.hide()
            return

        self._contact = contact
        self._update()

    def do_unroot(self) -> None:
        Gtk.Button.do_unroot(self)
        self._disconnect_all()
        del self._popover
        app.check_finalize(self)

    def _update(self) -> None:
        self.set_visible(False)
        self.hide()

        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module("MUC").get_voice_requests(self._contact)
        if voice_requests:
            self.show()

    def _on_button_clicked(self, _button: VoiceRequestsButton) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module("MUC").get_voice_requests(self._contact)
        if not voice_requests:
            return

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.add_css_class("p-12")
        menu_box.set_hexpand(True)

        desc_label = Gtk.Label(label=_("Participants asking for voice:"))
        desc_label.add_css_class("dim-label")
        desc_label.set_max_width_chars(35)
        desc_label.set_wrap(True)
        desc_label.set_wrap_mode(Pango.WrapMode.WORD)
        desc_label.set_margin_bottom(6)
        menu_box.append(desc_label)

        for request in voice_requests:
            request_box = Gtk.Box(spacing=12)

            name_label = Gtk.Label(
                label=f"{request.nick} ({request.jid})",
                hexpand=True,
                max_width_chars=30,
                ellipsize=Pango.EllipsizeMode.MIDDLE,
                xalign=0,
            )
            request_box.append(name_label)

            decline_button = Gtk.Button.new_from_icon_name("process-stop-symbolic")
            decline_button.set_tooltip_text(_("Decline"))
            decline_button.connect("clicked", self._on_decline, request, self._contact)
            request_box.append(decline_button)

            approve_button = Gtk.Button.new_from_icon_name("feather-check-symbolic")
            approve_button.set_tooltip_text(_("Approve"))
            approve_button.connect("clicked", self._on_approve, request, self._contact)
            request_box.append(approve_button)

            if voice_requests.index(request) > 0:
                menu_box.append(Gtk.Separator())

            menu_box.append(request_box)

        self._popover.add_css_class("p-6")
        self._popover.set_child(menu_box)
        self._popover.popup()

    def _on_approve(
        self,
        _button: Gtk.Button,
        voice_request: VoiceRequest,
        contact: GroupchatContact,
    ) -> None:

        client = app.get_client(contact.account)
        client.get_module("MUC").approve_voice_request(contact, voice_request)
        self._update()

    def _on_decline(
        self,
        _button: Gtk.Button,
        voice_request: VoiceRequest,
        contact: GroupchatContact,
    ) -> None:

        client = app.get_client(contact.account)
        client.get_module("MUC").decline_voice_request(contact, voice_request)
        self._update()
