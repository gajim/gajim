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

from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from .status_selector import StatusSelector
from .util import open_window


class AccountPage(Gtk.Box):
    def __init__(self, account):
        Gtk.Box.__init__(self)
        self.get_style_context().add_class('account-page')

        self._account = account

        self._account_label = Gtk.Label()
        self._account_label.get_style_context().add_class('large-header')

        self._status_selector = StatusSelector()
        self._status_selector.set_halign(Gtk.Align.CENTER)

        settings_button = Gtk.Button(label=_('Settings'))
        settings_button.set_halign(Gtk.Align.CENTER)
        settings_button.connect('clicked', self._on_settings)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_hexpand(True)
        box.add(self._account_label)
        box.add(settings_button)
        box.add(self._status_selector)

        self.add(box)
        self.show_all()
        self.update()

    def _on_settings(self, _button):
        window = open_window('AccountsWindow')
        window.select_account(self._account)

    def update(self):
        account_label = app.settings.get_account_setting(
            self._account, 'account_label')
        self._account_label.set_text(account_label)
        self._status_selector.update()
