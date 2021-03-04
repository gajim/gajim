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

from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from .roster import Roster
from .status_selector import StatusSelector
from .util import get_builder
from .util import open_window

ROSTER_MENU_DICT = {
    'show-offline': _('Show Offline Contacts'),
}


class AccountPage(Gtk.Box):
    def __init__(self, account):
        Gtk.Box.__init__(self)
        self._account = account

        self._ui = get_builder('account_page.ui')
        self.add(self._ui.paned)

        self._status_selector = StatusSelector()
        self._status_selector.set_halign(Gtk.Align.CENTER)
        self._ui.account_box.add(self._status_selector)

        self._roster = Roster(account)
        self._ui.roster_box.add(self._roster)

        self._ui.paned.set_position(app.settings.get('chat_handle_position'))
        self._ui.paned.connect('button-release-event', self._on_button_release)

        roster_menu = Gio.Menu()
        for action, label in ROSTER_MENU_DICT.items():
            roster_menu.append(label, f'win.{action}-{account}')
        self._ui.roster_menu_button.set_menu_model(roster_menu)

        self._ui.connect_signals(self)
        self.show_all()

        self.update()

    def _on_account_settings(self, _button):
        window = open_window('AccountsWindow')
        window.select_account(self._account)

    def _on_search_changed(self, widget):
        text = widget.get_text().lower()
        print(text)

    @staticmethod
    def _on_button_release(paned, event):
        if event.window != paned.get_handle_window():
            return
        position = paned.get_position()
        app.settings.set('chat_handle_position', position)

    def get_roster(self):
        return self._roster

    def update(self):
        account_label = app.settings.get_account_setting(
            self._account, 'account_label')
        self._ui.account_label.set_text(account_label)
        self._status_selector.update()

    def process_event(self, event):
        self._roster.process_event(event)
