# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import logging

from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.const import AdHocStatus
from nbxmpp.modules.account_invite import parse_account_invite
from nbxmpp.structs import AdHocCommand
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import XmppUriQuery
from gajim.common.helpers import generate_qr_code
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT
from gajim.common.util.uri import get_xmpp_link_uri

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.address_share_popover")


@Gtk.Template(string=get_ui_string("address_share_popover.ui"))
class AddressSharePopover(Gtk.Popover, SignalManager):
    __gtype_name__ = "AddressSharePopover"

    _stack: Gtk.Stack = Gtk.Template.Child()
    _share_instructions: Gtk.Label = Gtk.Template.Child()
    _qr_code_image: Gtk.Image = Gtk.Template.Child()
    _generate_invite_button: Gtk.Button = Gtk.Template.Child()
    _copy_web_address_button: Gtk.Button = Gtk.Template.Child()
    _jid_label: Gtk.Label = Gtk.Template.Child()
    _copy_jid_button: Gtk.Button = Gtk.Template.Child()

    mode = GObject.Property(
        type=str, default="contact", flags=GObject.ParamFlags.READWRITE
    )

    def __init__(self) -> None:
        Gtk.Popover.__init__(self)
        SignalManager.__init__(self)

        self._connect(self._copy_jid_button, "clicked", self._on_copy_jid_clicked)
        self._connect(
            self._generate_invite_button, "clicked", self._on_generate_clicked
        )
        self._connect(
            self._copy_web_address_button, "clicked", self._on_copy_web_address_clicked
        )

    def set_contact(self, contact: ChatContactT) -> None:
        self._contact = contact

        self._stack.set_visible_child_name(self.mode)

        self._jid_label.set_text(str(contact.jid))

        if isinstance(contact, GroupchatContact):
            share_text = _("Scan this QR code to join %s.")
            if contact.muc_context == "private":
                share_text = _("%s can be joined by invite only.")

        else:
            share_text = _("Scan this QR code to start a chat with %s.")

        self._share_instructions.set_text(share_text % contact.name)

        if isinstance(contact, GroupchatContact) and contact.muc_context == "private":
            # Don't display QR code for private MUCs (they require an invite)
            self._qr_code_image.set_visible(False)
            return

        self._set_qr_code()

    def _set_qr_code(self, web_url: str | None = None) -> None:
        if web_url is None:
            web_url = self._get_web_share_url()

        self._qr_code_image.set_from_paintable(
            generate_qr_code(web_url) if web_url else None
        )
        self._qr_code_image.set_visible(bool(web_url))

    def _on_generate_clicked(self) -> None:
        client = app.get_client(self._contact.account)
        if not client.state.is_available:
            return

        command = client.get_module("AdHocCommands").get_command(
            "urn:xmpp:invite#invite"
        )
        if command is None:
            log.warning("Unable to find urn:xmpp:invite#invite command")
            return

        client.get_module("AdHocCommands").execute_command(
            command, callback=self._on_invite_received
        )

    def _on_invite_received(self, task: Task) -> None:
        try:
            command = cast(AdHocCommand, task.finish())
        except Exception as error:
            print("catch", error)
            return

        if command.status != AdHocStatus.COMPLETED or command.data is None:
            log.error("command ended unexpected")
            return

        try:
            invite_result = parse_account_invite(command.data)
        except Exception as error:
            log.error(error)

        self._set_qr_code(invite_result.uri)

    def _get_share_uri(self) -> str:
        jid = self._contact.get_address()
        if self._contact.is_groupchat:
            return jid.to_iri(XmppUriQuery.JOIN.value)
        else:
            client = app.get_client(self._contact.account)
            return client.get_module("OMEMO").compose_trust_uri(jid)

    def _get_web_share_url(self) -> str | None:
        jid = self._contact.get_address()
        return get_xmpp_link_uri(jid, groupchat=self._contact.is_groupchat)

    def _on_copy_jid_clicked(self, _button: Gtk.Button) -> None:
        self.get_clipboard().set(self._get_share_uri())
        self.popdown()

    def _on_copy_web_address_clicked(self, _button: Gtk.Button) -> None:
        if url := self._get_web_share_url():
            self.get_clipboard().set(url)
        self.popdown()
