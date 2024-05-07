# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import MucInvitation
from gajim.common.helpers import get_group_chat_nick
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.groupchat_nick import NickChooser
from gajim.gtk.util import AccountBadge


class GroupChatInvitationDialog(Gtk.ApplicationWindow):
    def __init__(self, account: str, event: MucInvitation) -> None:
        Gtk.ApplicationWindow.__init__(
            self,
            application=app.app,
            window_position=Gtk.WindowPosition.CENTER,
            show_menubar=False,
            type_hint=Gdk.WindowTypeHint.DIALOG,
            title=_('Group Chat Invitation'),
        )

        self.account = account

        self.connect('key-press-event', self._on_key_press)

        invitation_widget = GroupChatInvitation(account, event)
        invitation_widget.connect('accepted', self._on_invitation_widget_action)
        invitation_widget.connect('declined', self._on_invitation_widget_action)
        self.add(invitation_widget)
        self.show_all()

    def _on_invitation_widget_action(self, _widget: GroupChatInvitation) -> None:
        self.destroy()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()


class GroupChatInvitation(Gtk.Box):

    __gsignals__ = {
        'accepted': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            ()
        ),
        'declined': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            ()
        ),
    }

    def __init__(self, account: str, event: MucInvitation) -> None:
        Gtk.Box.__init__(self, halign=Gtk.Align.CENTER)

        self._account = account
        self._client = app.get_client(account)
        self._room_jid = str(event.muc)
        self._from = str(event.from_)
        self._password = event.password

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.FILL
        )
        main_box.get_style_context().add_class('padding-18')

        muc_info_box = GroupChatInfoScrolled(account, minimal=True)
        muc_info_box.set_from_disco_info(event.info)
        main_box.add(muc_info_box)

        separator = Gtk.Separator()
        main_box.add(separator)

        contact = self._client.get_module('Contacts').get_contact(event.from_.bare)
        assert isinstance(contact, BareContact | GroupchatContact)
        contact_label = Gtk.Label(label=contact.name, wrap=True)
        contact_label.get_style_context().add_class('bold16')
        contact_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.CENTER
        )
        contact_box.add(contact_label)
        main_box.add(contact_box)

        enabled_accounts = app.get_enabled_accounts_with_labels()
        if len(enabled_accounts) > 1:
            account_badge = AccountBadge(account)
            contact_box.add(account_badge)

        invitation_label = Gtk.Label(
            label=_('has invited you to a group chat.\nDo you want to join?'),
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
            max_width_chars=50,
            wrap=True,
        )
        main_box.add(invitation_label)

        decline_button = Gtk.Button.new_with_mnemonic(_('_Decline'))
        decline_button.set_halign(Gtk.Align.START)
        decline_button.connect('clicked', self._on_decline)

        self._nick_chooser = NickChooser()
        self._nick_chooser.set_text(get_group_chat_nick(self._account, event.info.jid))

        join_button = Gtk.Button.new_with_mnemonic(_('_Join'))
        join_button.set_halign(Gtk.Align.END)
        join_button.get_style_context().add_class('suggested-action')
        join_button.connect('clicked', self._on_join)

        join_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.END)
        join_box.get_style_context().add_class('linked')
        join_box.add(self._nick_chooser)
        join_box.add(join_button)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, margin_top=6)
        button_box.pack_start(decline_button, False, False, 0)
        button_box.pack_end(join_box, False, False, 0)

        main_box.add(button_box)
        self.add(main_box)

        join_button.set_can_default(True)
        join_button.grab_focus()

        self.show_all()

    def _on_join(self, _button: Gtk.Button) -> None:
        nickname = self._nick_chooser.get_text()
        app.window.show_add_join_groupchat(
            self._account, self._room_jid, nickname=nickname
        )
        self.emit('accepted')

    def _on_decline(self, _button: Gtk.Button) -> None:
        self._client.get_module('MUC').decline(self._room_jid, self._from)
        self.emit('declined')
