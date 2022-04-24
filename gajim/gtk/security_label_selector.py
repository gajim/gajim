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
from typing import cast
from typing import Optional

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import ged
from gajim.common.events import SecCatalogReceived
from gajim.common.types import ChatContactT
from gajim.common.i18n import _


class SecurityLabelSelector(Gtk.ComboBox):
    def __init__(self, account: str, contact: ChatContactT) -> None:
        Gtk.ComboBox.__init__(self, no_show_all=True)
        self._account = account
        self._client = app.get_client(account)
        self._contact = contact

        self.set_valign(Gtk.Align.CENTER)
        self.set_tooltip_text(_('Select a security label for your message…'))

        label_store = Gtk.ListStore(str)
        self.set_model(label_store)
        label_cell_renderer = Gtk.CellRendererText()
        label_cell_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        label_cell_renderer.set_property('max-width-chars', 14)
        self.pack_start(label_cell_renderer, True)
        self.add_attribute(label_cell_renderer, 'text', 0)

        app.ged.register_event_handler(
            'sec-catalog-received', ged.GUI1, self._sec_labels_received)

        self.connect('destroy', self._on_destroy)
        jid = self._contact.jid.bare
        if self._client.get_module('SecLabels').supported:
            self._client.get_module('SecLabels').request_catalog(jid)

    def _on_destroy(self, _widget: SecurityLabelSelector) -> None:
        app.ged.remove_event_handler('sec-catalog-received',
                                     ged.GUI1,
                                     self._sec_labels_received)

    def _sec_labels_received(self, event: SecCatalogReceived) -> None:
        if event.account != self._account:
            return

        if event.jid != self._contact.jid.bare:
            return

        if not app.settings.get_account_setting(
                self._account, 'enable_security_labels'):
            return

        model = cast(Gtk.ListStore, self.get_model())
        model.clear()

        selection = 0
        label_list = event.catalog.get_label_names()
        default = event.catalog.default
        for index, label in enumerate(label_list):
            model.append([label])
            if label == default:
                selection = index

        self.set_active(selection)
        self.set_no_show_all(False)
        self.show_all()

    def get_seclabel(self) -> Optional[str]:
        index = self.get_active()
        if index == -1:
            return None

        jid = self._contact.jid.bare
        catalog = self._client.get_module('SecLabels').get_catalog(jid)
        labels, label_list = catalog.labels, catalog.get_label_names()
        label_name = label_list[index]
        label = labels[label_name]
        return label
