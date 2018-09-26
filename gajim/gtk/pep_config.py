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
from gajim.common import ged
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import WarningDialog
from gajim.gtk.util import get_builder


class ManagePEPServicesWindow:
    def __init__(self, account):
        self.xml = get_builder('manage_pep_services_window.ui')
        self.window = self.xml.get_object('manage_pep_services_window')
        self.window.set_transient_for(app.interface.roster.window)
        self.xml.get_object('configure_button').set_sensitive(False)
        self.xml.get_object('delete_button').set_sensitive(False)
        self.xml.connect_signals(self)
        self.account = account
        self._con = app.connections[self.account]

        self.init_services()
        self.xml.get_object('services_treeview').get_selection().connect(
            'changed', self.on_services_selection_changed)

        app.ged.register_event_handler(
            'pubsub-config-received', ged.GUI1, self._nec_pep_config_received)

        self.window.show_all()

    def on_manage_pep_services_window_destroy(self, widget):
        del app.interface.instances[self.account]['pep_services']
        app.ged.remove_event_handler(
            'pubsub-config-received', ged.GUI1, self._nec_pep_config_received)

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_services_selection_changed(self, sel):
        self.xml.get_object('configure_button').set_sensitive(True)
        self.xml.get_object('delete_button').set_sensitive(True)

    def init_services(self):
        self.treeview = self.xml.get_object('services_treeview')
        # service, access_model, group
        self.treestore = Gtk.ListStore(str)
        self.treeview.set_model(self.treestore)

        col = Gtk.TreeViewColumn('Service')
        self.treeview.append_column(col)

        cellrenderer_text = Gtk.CellRendererText()
        col.pack_start(cellrenderer_text, True)
        col.add_attribute(cellrenderer_text, 'text', 0)

        jid = self._con.get_own_jid().getStripped()
        self._con.get_module('Discovery').disco_items(
            jid, success_cb=self._items_received, error_cb=self._items_error)

    def _items_received(self, from_, node, items):
        jid = self._con.get_own_jid().getStripped()
        for item in items:
            if item['jid'] == jid and 'node' in item:
                self.treestore.append([item['node']])

    def _items_error(self, from_, error):
        ErrorDialog('Error', error)

    def node_removed(self, jid, node):
        if jid != app.get_jid_from_account(self.account):
            return
        model = self.treeview.get_model()
        iter_ = model.get_iter_first()
        while iter_:
            if model[iter_][0] == node:
                model.remove(iter_)
                break
            iter_ = model.iter_next(iter_)

    def node_not_removed(self, jid, node, msg):
        if jid != app.get_jid_from_account(self.account):
            return
        WarningDialog(
            _('PEP node was not removed'),
            _('PEP node %(node)s was not removed: %(message)s') % {
                'node': node, 'message': msg})

    def on_delete_button_clicked(self, widget):
        selection = self.treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        node = model[iter_][0]
        our_jid = app.get_jid_from_account(self.account)
        con = app.connections[self.account]
        con.get_module('PubSub').send_pb_delete(our_jid, node,
                                                on_ok=self.node_removed,
                                                on_fail=self.node_not_removed)

    def on_configure_button_clicked(self, widget):
        selection = self.treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        node = model[iter_][0]
        our_jid = app.get_jid_from_account(self.account)
        con = app.connections[self.account]
        con.get_module('PubSub').request_pb_configuration(our_jid, node)

    def _nec_pep_config_received(self, obj):
        def on_ok(form, node):
            form.type_ = 'submit'
            our_jid = app.get_jid_from_account(self.account)
            con = app.connections[self.account]
            con.get_module('PubSub').send_pb_configure(our_jid, node, form)
        from gajim.dialogs import DataFormWindow
        window = DataFormWindow(obj.form, (on_ok, obj.node))
        title = _('Configure %s') % obj.node
        window.set_title(title)
        window.show_all()
