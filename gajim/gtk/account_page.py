# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import ClientState
from gajim.common.modules.contacts import BareContact

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_account_menu
from gajim.gtk.menus import get_roster_view_menu
from gajim.gtk.roster import Roster
from gajim.gtk.status_message_selector import StatusMessageSelector
from gajim.gtk.status_selector import StatusSelector
from gajim.gtk.util import EventHelper
from gajim.gtk.util import open_window


class AccountPage(Gtk.Box, EventHelper):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)

        self._account = account
        client = app.get_client(account)
        jid = client.get_own_jid().bare
        self._contact = client.get_module('Contacts').get_contact(jid)
        self._contact.connect('avatar-update', self._on_avatar_update)

        self._ui = get_builder('account_page.ui')
        self.add(self._ui.paned)

        self._ui.our_jid_label.set_text(jid)

        self._status_selector = StatusSelector(account=account)
        self._status_selector.set_halign(Gtk.Align.CENTER)
        self._ui.status_box.add(self._status_selector)

        self._status_message_selector = StatusMessageSelector(account=account)
        self._status_message_selector.set_halign(Gtk.Align.CENTER)
        self._ui.status_box.add(self._status_message_selector)

        # TODO: move
        # self._ui.notifications_menu_button.set_menu_model(
        #     get_account_notifications_menu(account))

        self._roster = Roster(account)
        self._ui.roster_box.add(self._roster)

        self._ui.paned.set_position(app.settings.get('chat_handle_position'))
        self._ui.paned.connect('button-release-event', self._on_button_release)

        self._ui.roster_menu_button.set_menu_model(get_roster_view_menu())
        self._ui.account_page_menu_button.set_menu_model(
            get_account_menu(account))

        self._ui.connect_signals(self)

        client.connect_signal('state-changed', self._on_client_state_changed)

        app.settings.connect_signal(
            'account_label',
            self._on_account_label_changed,
            account)

        self.update()
        self.show_all()
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, _widget: AccountPage) -> None:
        self._contact.disconnect_all_from_obj(self)
        app.settings.disconnect_signals(self)
        app.check_finalize(self)

    def _on_account_label_changed(self, value: str, *args: Any) -> None:
        self.update()

    def _on_avatar_update(self, *args: Any) -> None:
        self.update()

    def _on_account_settings(self, _button: Gtk.Button) -> None:
        window = open_window('AccountsWindow')
        window.select_account(self._account)

    def _on_client_state_changed(self,
                                 client: Client,
                                 _signal_name: str,
                                 state: ClientState
                                 ) -> None:

        jid = client.get_own_jid().bare
        self._ui.our_jid_label.set_text(jid)

    def _on_search_changed(self, widget: Gtk.SearchEntry) -> None:
        text = widget.get_text().lower()
        self._roster.set_search_string(text)

    @staticmethod
    def _on_button_release(paned: Gtk.Paned, event: Gdk.EventButton) -> None:
        if event.window != paned.get_handle_window():
            return
        position = paned.get_position()
        app.settings.set('chat_handle_position', position)

    def get_roster(self) -> Roster:
        return self._roster

    def update(self) -> None:
        account_label = app.settings.get_account_setting(
            self._account, 'account_label')
        self._ui.account_label.set_text(account_label)

        assert isinstance(self._contact, BareContact)
        surface = self._contact.get_avatar(AvatarSize.ACCOUNT_PAGE,
                                           self.get_scale_factor(),
                                           add_show=False)
        self._ui.avatar_image.set_from_surface(surface)

        self._status_selector.update()
