# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import ClientState
from gajim.common.events import MucDecline
from gajim.common.events import MucInvitation
from gajim.common.events import SubscribePresenceReceived
from gajim.common.events import UnsubscribedPresenceReceived
from gajim.common.ged import EventHelper
from gajim.common.modules.contacts import BareContact

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_account_menu
from gajim.gtk.menus import get_account_notifications_menu
from gajim.gtk.notification_manager import NotificationManager
from gajim.gtk.status_message_selector import StatusMessageSelector
from gajim.gtk.status_selector import StatusSelector
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.window import open_window


class AccountPage(Gtk.Box, EventHelper, SignalManager):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._client = app.get_client(account)

        jid = self._client.get_own_jid().bare
        self._contact = self._client.get_module("Contacts").get_contact(jid)
        self._contact.connect("avatar-update", self._on_avatar_update)

        self._ui = get_builder("account_page.ui")
        self.append(self._ui.scrolled)

        self._connect(
            self._ui.account_settings_button, "clicked", self._on_account_settings
        )

        self._ui.our_jid_label.set_text(jid)

        self._status_selector = StatusSelector(account=account)
        self._status_selector.set_halign(Gtk.Align.CENTER)
        self._ui.status_box.append(self._status_selector)

        self._status_message_selector = StatusMessageSelector(account=account)
        self._status_message_selector.set_halign(Gtk.Align.CENTER)
        self._ui.status_box.append(self._status_message_selector)

        self._notification_manager = NotificationManager(account)
        self._ui.account_box.append(self._notification_manager)

        self._ui.notifications_menu_button.set_menu_model(
            get_account_notifications_menu(account)
        )

        self._ui.account_page_menu_button.set_menu_model(get_account_menu(account))

        self._client.connect_signal("state-changed", self._on_client_state_changed)

        app.settings.connect_signal(
            "account_label", self._on_account_label_changed, account
        )

        # pylint: disable=line-too-long
        self.register_events(
            [
                ("subscribe-presence-received", ged.GUI1, self._subscribe_received),
                (
                    "unsubscribed-presence-received",
                    ged.GUI1,
                    self._unsubscribed_received,
                ),
                ("muc-invitation", ged.GUI1, self._muc_invitation_received),
                ("muc-decline", ged.GUI1, self._muc_invitation_declined),
            ]
        )
        # pylint: enable=line-too-long

        self.update()

    def do_unroot(self) -> None:
        self._disconnect_all()
        self.unregister_events()
        self._contact.disconnect_all_from_obj(self)
        self._client.disconnect_all_from_obj(self)
        app.settings.disconnect_signals(self)
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _on_account_label_changed(self, _value: str, *args: Any) -> None:
        self.update()

    def _on_avatar_update(self, *args: Any) -> None:
        self.update()

    def _on_account_settings(self, _button: Gtk.Button) -> None:
        window = open_window("AccountsWindow")
        window.select_account(self._account)

    def _on_client_state_changed(
        self, client: Client, _signal_name: str, state: ClientState
    ) -> None:

        jid = client.get_own_jid().bare
        self._ui.our_jid_label.set_text(jid)

    def update(self) -> None:
        account_label = app.settings.get_account_setting(self._account, "account_label")
        self._ui.account_label.set_text(account_label)

        assert isinstance(self._contact, BareContact)
        texture = self._contact.get_avatar(
            AvatarSize.ACCOUNT_PAGE, self.get_scale_factor(), add_show=False
        )
        self._ui.avatar_image.set_pixel_size(AvatarSize.ACCOUNT_PAGE)
        self._ui.avatar_image.set_from_paintable(texture)

        self._status_selector.update()

    def _subscribe_received(self, event: SubscribePresenceReceived) -> None:
        if event.account != self._account:
            return
        self._notification_manager.add_subscription_request(event)

    def _unsubscribed_received(self, event: UnsubscribedPresenceReceived) -> None:
        if event.account != self._account:
            return
        self._notification_manager.add_unsubscribed(event)

    def _muc_invitation_received(self, event: MucInvitation) -> None:
        if event.account != self._account:
            return
        self._notification_manager.add_invitation_received(event)

    def _muc_invitation_declined(self, event: MucDecline) -> None:
        if event.account != self._account:
            return
        self._notification_manager.add_invitation_declined(event)
