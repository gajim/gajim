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

from typing import Any
from typing import Optional

from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.helpers import get_global_status_message
from gajim.common.helpers import to_one_line
from gajim.common.i18n import _


class StatusMessageSelector(Gtk.Box):
    def __init__(self, account: Optional[str] = None) -> None:
        Gtk.Box.__init__(self)
        self.get_style_context().add_class('linked')
        self._account = account

        self._entry = Gtk.Entry()
        self._entry.set_size_request(200, -1)
        self._entry.set_property('show-emoji-icon', True)
        self._entry.set_placeholder_text(_('Status message…'))
        self._entry.connect('activate', self._set_status_message)
        self._entry.connect('changed', self._on_changed)

        self._button = Gtk.Button.new_from_icon_name(
            'object-select-symbolic', Gtk.IconSize.BUTTON)
        self._button.set_tooltip_text(_('Set status message'))
        self._button.connect('clicked', self._set_status_message)
        self.add(self._entry)
        self.add(self._button)
        self.show_all()
        app.ged.register_event_handler('our-show', ged.POSTGUI, self.update)

    def _on_changed(self, _entry: Gtk.Entry) -> None:
        self._button.set_sensitive(True)

    def _set_status_message(self, *args: Any) -> None:
        self._button.set_sensitive(False)
        message = self._entry.get_text()
        message = to_one_line(message)
        if self._account is not None:
            client = app.get_client(self._account)
            client.change_status(client.status, message)
        else:
            for account in app.connections:
                if not app.settings.get_account_setting(
                        account, 'sync_with_global_status'):
                    continue
                client = app.get_client(account)
                client.change_status(client.status, message)

    def update(self, *args: Any) -> None:
        if self._account is None:
            message = get_global_status_message()
        else:
            if self._account not in app.connections:
                return
            client = app.get_client(self._account)
            message = client.status_message

        self._entry.set_text(message)
