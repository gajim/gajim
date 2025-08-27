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

from gajim.gtk.util.classes import SignalManager


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

        image = Gtk.Image.new_from_icon_name("lucide-circle-question-mark-symbolic")
        inner_box.append(image)

        self.add_css_class("pulse-opacity")
        self.add_css_class("suggested-action")

        self._popover = Gtk.Popover(width_request=400, height_request=400)
        self._popover.add_css_class("p-6")

        inner_box.append(self._popover)

        self._connect(self, "clicked", self._on_button_clicked)

    def switch_contact(self, contact: ChatContactT) -> None:
        if not isinstance(contact, GroupchatContact):
            self._contact = None
            self.set_visible(False)
            self.set_visible(False)
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
        self.set_visible(False)

        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module("MUC").get_voice_requests(self._contact)
        if voice_requests:
            self.set_visible(True)

    def _on_button_clicked(self, _button: VoiceRequestsButton) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module("MUC").get_voice_requests(self._contact)
        if not voice_requests:
            return

        self._update_content()
        self._popover.popup()

    def _update_content(self) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        voice_requests = client.get_module("MUC").get_voice_requests(self._contact)

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.add_css_class("p-12")
        menu_box.set_hexpand(True)

        desc_label = Gtk.Label(
            label=_("Participants asking for voice:"),
            max_width_chars=35,
            wrap=True,
            margin_bottom=6,
        )
        desc_label.add_css_class("dimmed")
        menu_box.append(desc_label)

        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, hexpand=True, vexpand=True
        )
        menu_box.append(scrolled)

        requests_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled.set_child(requests_box)

        for request in voice_requests:
            request_box = Gtk.Box(spacing=12)
            requests_box.append(request_box)

            name_label = Gtk.Label(
                label=f"{request.nick} ({request.jid.bare})",
                hexpand=True,
                max_width_chars=30,
                ellipsize=Pango.EllipsizeMode.MIDDLE,
                xalign=0,
                tooltip_text=str(request.jid.bare),
            )
            request_box.append(name_label)

            decline_button = Gtk.Button.new_from_icon_name("lucide-circle-x-symbolic")
            decline_button.set_tooltip_text(_("Decline"))
            self._connect(
                decline_button, "clicked", self._on_decline, request, self._contact
            )
            request_box.append(decline_button)

            approve_button = Gtk.Button.new_from_icon_name("lucide-check-symbolic")
            approve_button.set_tooltip_text(_("Approve"))
            self._connect(
                approve_button, "clicked", self._on_approve, request, self._contact
            )
            request_box.append(approve_button)

        self._popover.set_child(menu_box)

    def _on_approve(
        self,
        _button: Gtk.Button,
        voice_request: VoiceRequest,
        contact: GroupchatContact,
    ) -> None:

        client = app.get_client(contact.account)
        client.get_module("MUC").approve_voice_request(contact, voice_request)
        self._update()
        self._update_content()

    def _on_decline(
        self,
        _button: Gtk.Button,
        voice_request: VoiceRequest,
        contact: GroupchatContact,
    ) -> None:

        client = app.get_client(contact.account)
        client.get_module("MUC").decline_voice_request(contact, voice_request)
        self._update()
        self._update_content()
