# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import MucInvitation
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.util.muc import get_group_chat_nick

from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.groupchat_nick import NickChooser
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.widgets import AccountBadge
from gajim.gtk.widgets import GajimAppWindow


class GroupChatInvitationDialog(GajimAppWindow):
    def __init__(self, account: str, event: MucInvitation) -> None:
        GajimAppWindow.__init__(
            self,
            name="GroupChatInvitationDialog",
            title=_("Group Chat Invitation"),
            default_width=450,
            default_height=500,
        )

        self.account = account

        invitation_widget = GroupChatInvitation(account, event)
        self._connect(invitation_widget, "accepted", self._on_invitation_widget_action)
        self._connect(invitation_widget, "declined", self._on_invitation_widget_action)
        self.set_child(invitation_widget)

    def _on_invitation_widget_action(self, _widget: GroupChatInvitation) -> None:
        self.close()

    def _cleanup(self) -> None:
        pass


class GroupChatInvitation(Gtk.Box, SignalManager):

    __gsignals__ = {
        "accepted": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (),
        ),
        "declined": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (),
        ),
    }

    def __init__(self, account: str, event: MucInvitation) -> None:
        Gtk.Box.__init__(self, halign=Gtk.Align.CENTER)
        SignalManager.__init__(self)

        self._account = account
        self._client = app.get_client(account)
        self._room_jid = str(event.muc)
        self._from = str(event.from_)
        self._password = event.password

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.FILL
        )

        muc_info_box = GroupChatInfoScrolled(account, minimal=True)
        muc_info_box.set_from_disco_info(event.info)
        main_box.append(muc_info_box)

        separator = Gtk.Separator()
        main_box.append(separator)

        contact = self._client.get_module("Contacts").get_contact(event.from_.bare)
        assert isinstance(contact, BareContact | GroupchatContact)
        contact_label = Gtk.Label(label=contact.name, wrap=True)
        contact_label.add_css_class("title-3")
        contact_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.CENTER
        )
        contact_box.append(contact_label)
        main_box.append(contact_box)

        enabled_accounts = app.get_enabled_accounts_with_labels()
        if len(enabled_accounts) > 1:
            account_badge = AccountBadge(account)
            account_badge.set_valign(Gtk.Align.CENTER)
            contact_box.append(account_badge)

        invitation_label = Gtk.Label(
            label=_("has invited you to a group chat.\nDo you want to join?"),
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
            max_width_chars=50,
            wrap=True,
        )
        main_box.append(invitation_label)

        decline_button = Gtk.Button.new_with_mnemonic(_("_Decline"))
        decline_button.set_halign(Gtk.Align.START)
        decline_button.set_margin_end(24)
        self._connect(decline_button, "clicked", self._on_decline)

        self._nick_chooser = NickChooser()
        self._nick_chooser.set_text(get_group_chat_nick(self._account, event.info.jid))

        join_button = Gtk.Button.new_with_mnemonic(_("_Join"))
        join_button.set_halign(Gtk.Align.END)
        join_button.add_css_class("suggested-action")
        self._connect(join_button, "clicked", self._on_join)

        join_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.END, hexpand=True
        )
        join_box.add_css_class("linked")
        join_box.append(self._nick_chooser)
        join_box.append(join_button)

        self._button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            margin_top=6,
            vexpand=True,
            valign=Gtk.Align.END,
        )
        self._button_box.prepend(decline_button)
        self._button_box.append(join_box)

        main_box.append(self._button_box)
        self.append(main_box)

        join_button.grab_focus()

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def _on_join(self, _button: Gtk.Button) -> None:
        nickname = self._nick_chooser.get_text()
        app.window.show_add_join_groupchat(
            self._account, self._room_jid, nickname=nickname
        )
        self.emit("accepted")

    def _on_decline(self, _button: Gtk.Button) -> None:
        self._client.get_module("MUC").decline(self._room_jid, self._from)
        self.emit("declined")

    def disable_buttons(self) -> None:
        self._button_box.set_sensitive(False)
