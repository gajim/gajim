# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.events import MucInvitation
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.util.muc import get_group_chat_nick

from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.groupchat_nick_chooser import GroupChatNickChooser
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.widgets import AccountBadge


@Gtk.Template(string=get_ui_string("groupchat_invitation.ui"))
class GroupChatInvitation(Gtk.Box, SignalManager):
    __gtype_name__ = "GroupChatInvitation"

    _inviter_avatar: Gtk.Image = Gtk.Template.Child()
    _inviter_name_label: Gtk.Label = Gtk.Template.Child()
    _account_badge: AccountBadge = Gtk.Template.Child()

    _info_box: Gtk.Box = Gtk.Template.Child()

    _actions_box: Gtk.Box = Gtk.Template.Child()
    _decline_button: Gtk.Button = Gtk.Template.Child()
    _join_button: Gtk.Button = Gtk.Template.Child()
    _nick_chooser: GroupChatNickChooser = Gtk.Template.Child()

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
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._client = app.get_client(account)
        self._room_jid = str(event.muc)
        self._from = str(event.from_)
        self._password = event.password

        muc_info_box = GroupChatInfoScrolled(account, minimal=True)
        muc_info_box.set_hexpand(True)
        muc_info_box.set_from_disco_info(event.info)
        self._info_box.append(muc_info_box)

        contact = self._client.get_module("Contacts").get_contact(event.from_.bare)
        assert isinstance(contact, BareContact | GroupchatContact)
        self._inviter_avatar.set_from_paintable(
            contact.get_avatar(AvatarSize.SMALL, self.get_scale_factor())
        )
        self._inviter_name_label.set_text(contact.name)

        enabled_accounts = app.get_enabled_accounts_with_labels()
        self._account_badge.set_account(account)
        self._account_badge.set_visible(len(enabled_accounts) > 1)

        self._connect(self._decline_button, "clicked", self._on_decline)
        self._connect(self._join_button, "clicked", self._on_join)

        self._nick_chooser.set_text(get_group_chat_nick(self._account, event.info.jid))

        self._join_button.grab_focus()

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
        self._actions_box.set_sensitive(False)
