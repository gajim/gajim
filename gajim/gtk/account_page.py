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

from typing import Any
from typing import Union

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Gtk

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.events import AccountConnected
from gajim.common.events import AccountDisconnected
from gajim.common.events import SubscribePresenceReceived
from gajim.common.events import UnsubscribedPresenceReceived
from gajim.common.events import MucInvitation
from gajim.common.events import MucDecline
from gajim.common.i18n import _

from .roster import Roster
from .status_message_selector import StatusMessageSelector
from .status_selector import StatusSelector
from .notification_manager import NotificationManager
from .builder import get_builder
from .util import open_window
from .util import EventHelper


ROSTER_MENU_DICT = {
    'show-offline': _('Show Offline Contacts'),
    'sort-by-show': _('Sort by Status'),
}


class AccountPage(Gtk.Box, EventHelper):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)

        self._account = account
        self._jid = app.get_jid_from_account(account)
        client = app.get_client(account)
        self._contact = client.get_module('Contacts').get_contact(self._jid)
        self._contact.connect('avatar-update', self._on_avatar_update)

        self._ui = get_builder('account_page.ui')
        self.add(self._ui.paned)

        self._status_selector = StatusSelector(account=account)
        self._status_selector.set_halign(Gtk.Align.CENTER)
        self._ui.account_action_box.add(self._status_selector)

        self._status_message_selector = StatusMessageSelector(account=account)
        self._status_message_selector.set_halign(Gtk.Align.CENTER)
        self._ui.status_message_box.add(self._status_message_selector)

        self._notification_manager = NotificationManager(account)
        self._ui.account_box.add(self._notification_manager)

        self._roster = Roster(account)
        self._ui.roster_box.add(self._roster)

        self._ui.paned.set_position(app.settings.get('chat_handle_position'))
        self._ui.paned.connect('button-release-event', self._on_button_release)

        roster_menu = Gio.Menu()
        for action, label in ROSTER_MENU_DICT.items():
            roster_menu.append(label, f'win.{action}')
        self._ui.roster_menu_button.set_menu_model(roster_menu)

        self._ui.connect_signals(self)

        # pylint: disable=line-too-long
        self.register_events([
            ('subscribe-presence-received', ged.GUI1, self._subscribe_received),
            ('unsubscribed-presence-received',
             ged.GUI1, self._unsubscribed_received),
            ('muc-invitation', ged.GUI1, self._muc_invitation_received),
            ('muc-decline', ged.GUI1, self._muc_invitation_declined),
            ('account-connected', ged.GUI2, self._on_account_state),
            ('account-disconnected', ged.GUI2, self._on_account_state),
        ])
        # pylint: enable=line-too-long

        self.update()
        self.show_all()
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, _widget: AccountPage) -> None:
        app.check_finalize(self)

    def _on_avatar_update(self, *args: Any) -> None:
        self.update()

    def _on_edit_profile(self, _button: Gtk.Button) -> None:
        open_window('ProfileWindow', account=self._account)

    def _on_account_settings(self, _button: Gtk.Button) -> None:
        window = open_window('AccountsWindow')
        window.select_account(self._account)

    def _on_adhoc_commands(self, _button: Gtk.Button) -> None:
        server_jid = JID.from_string(self._jid).domain
        open_window('AdHocCommands', account=self._account, jid=server_jid)

    def _on_account_state(self,
                          event: Union[AccountConnected, AccountDisconnected]
                          ) -> None:

        if event.account != self._account:
            return

        self._ui.adhoc_commands_button.set_sensitive(
            app.account_is_connected(event.account))

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

        surface = self._contact.get_avatar(AvatarSize.ACCOUNT_PAGE,
                                           self.get_scale_factor(),
                                           add_show=False)
        self._ui.avatar_image.set_from_surface(surface)

        self._status_selector.update()

    def _subscribe_received(self, event: SubscribePresenceReceived) -> None:
        if event.account != self._account:
            return
        self._notification_manager.add_subscription_request(event)

    def _unsubscribed_received(self,
                               event: UnsubscribedPresenceReceived
                               ) -> None:
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
