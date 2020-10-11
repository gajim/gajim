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

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.errors import StanzaError

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.helpers import to_user_string

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import WarningDialog
from gajim.gtk.dataform import DataFormDialog
from gajim.gtk.util import get_builder
from gajim.gtk.util import EventHelper


class PEPConfig(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('PEPConfig')
        self.set_default_size(300, 350)
        self.set_resizable(True)
        self.set_transient_for(app.interface.roster.window)

        self._ui = get_builder('manage_pep_services_window.ui')
        self.add(self._ui.manage_pep_services)

        self.account = account
        self.set_title(_('PEP Service Configuration (%s)') % self.account)
        self._con = app.connections[self.account]

        self._init_services()
        self._ui.services_treeview.get_selection().connect(
            'changed', self._on_services_selection_changed)

        self.register_events([
            ('pubsub-config-received', ged.GUI1, self._nec_pep_config_received),
        ])

        self.show_all()
        self.connect('key-press-event', self._on_key_press_event)
        self._ui.connect_signals(self)

    def _on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_services_selection_changed(self, _selection):
        self._ui.configure_button.set_sensitive(True)
        self._ui.delete_button.set_sensitive(True)

    def _init_services(self):
        # service, access_model, group
        self.treestore = Gtk.ListStore(str)
        self.treestore.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self._ui.services_treeview.set_model(self.treestore)

        col = Gtk.TreeViewColumn(_('Service'))
        col.set_sort_column_id(0)
        self._ui.services_treeview.append_column(col)

        cellrenderer_text = Gtk.CellRendererText()
        col.pack_start(cellrenderer_text, True)
        col.add_attribute(cellrenderer_text, 'text', 0)

        jid = self._con.get_own_jid().bare
        self._con.get_module('Discovery').disco_items(
            jid, callback=self._items_received)

    def _items_received(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            ErrorDialog('Error', to_user_string(error))
            return

        jid = result.jid.bare
        for item in result.items:
            if item.jid == jid and item.node is not None:
                self.treestore.append([item.node])

    def _node_removed(self, jid, node):
        if jid != app.get_jid_from_account(self.account):
            return
        model = self._ui.services_treeview.get_model()
        iter_ = model.get_iter_first()
        while iter_:
            if model[iter_][0] == node:
                model.remove(iter_)
                break
            iter_ = model.iter_next(iter_)

    def _node_not_removed(self, jid, node, msg):
        if jid != app.get_jid_from_account(self.account):
            return
        WarningDialog(
            _('PEP node was not removed'),
            _('PEP node %(node)s was not removed:\n%(message)s') % {
                'node': node, 'message': msg})

    def _on_delete_button_clicked(self, _widget):
        selection = self._ui.services_treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        node = model[iter_][0]
        our_jid = app.get_jid_from_account(self.account)
        con = app.connections[self.account]
        con.get_module('PubSub').send_pb_delete(our_jid, node,
                                                on_ok=self._node_removed,
                                                on_fail=self._node_not_removed)

    def _on_configure_button_clicked(self, _widget):
        selection = self._ui.services_treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        node = model[iter_][0]
        our_jid = app.get_jid_from_account(self.account)
        con = app.connections[self.account]
        con.get_module('PubSub').request_pb_configuration(our_jid, node)

    def _on_config_submit(self, form, node):
        our_jid = app.get_jid_from_account(self.account)
        con = app.connections[self.account]
        con.get_module('PubSub').send_pb_configure(our_jid, node, form)

    def _nec_pep_config_received(self, obj):
        DataFormDialog(_('Configure %s') % obj.node,
                       self,
                       obj.form,
                       obj.node,
                       self._on_config_submit)
