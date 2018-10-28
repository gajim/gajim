# Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
#
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

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import ged
from gajim.common.modules import dataforms
from gajim.common.i18n import _

from gajim import vcard
from gajim import config
from gajim import dataforms_widget

from gajim.gtk.util import get_builder
from gajim.gtk.add_contact import AddNewContactWindow


class SearchWindow:
    def __init__(self, account, jid):
        self.account = account
        self.jid = jid

        self._ui = get_builder('search_window.ui')
        self.window = self._ui.search_window

        self._ui.search_button.set_sensitive(False)

        self._ui.connect_signals(self)
        self.window.show_all()
        self.request_form()
        self.pulse_id = GLib.timeout_add(80, self.pulse_callback)

        self.is_form = None

        # Is there a jid column in results ? if -1: no, else column number
        self.jid_column = -1

        app.ged.register_event_handler('search-form-received',
                                       ged.GUI1,
                                       self._nec_search_form_received)
        app.ged.register_event_handler('search-result-received',
                                       ged.GUI1,
                                       self._nec_search_result_received)

    def request_form(self):
        con = app.connections[self.account]
        con.get_module('Search').request_search_fields(self.jid)

    def pulse_callback(self):
        self._ui.progressbar.pulse()
        return True

    def on_search_window_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def on_search_window_destroy(self, _widget):
        if self.pulse_id:
            GLib.source_remove(self.pulse_id)
        del app.interface.instances[self.account]['search'][self.jid]
        app.ged.remove_event_handler('search-form-received',
                                     ged.GUI1,
                                     self._nec_search_form_received)
        app.ged.remove_event_handler('search-result-received',
                                     ged.GUI1,
                                     self._nec_search_result_received)

    def on_close_button_clicked(self, _button):
        self.window.destroy()

    def on_search_button_clicked(self, _button):
        con = app.connections[self.account]
        if self.is_form:
            self.data_form_widget.data_form.type_ = 'submit'
            con.get_module('Search').send_search_form(
                self.jid, self.data_form_widget.data_form.get_purged(), True)
        else:
            infos = self.data_form_widget.get_infos()
            if 'instructions' in infos:
                del infos['instructions']
            con.get_module('Search').send_search_form(self.jid, infos, False)

        self._ui.search_vbox.remove(self.data_form_widget)

        self._ui.progressbar.show()
        self._ui.label.set_text(_('Waiting for results'))
        self._ui.label.show()
        self.pulse_id = GLib.timeout_add(80, self.pulse_callback)
        self._ui.search_button.hide()

    def on_add_contact_button_clicked(self, _widget):
        (model, iter_) = self.result_treeview.get_selection().get_selected()
        if not iter_:
            return
        jid = model[iter_][self.jid_column]
        AddNewContactWindow(self.account, jid)

    def on_information_button_clicked(self, _widget):
        (model, iter_) = self.result_treeview.get_selection().get_selected()
        if not iter_:
            return
        jid = model[iter_][self.jid_column]
        if jid in app.interface.instances[self.account]['infos']:
            app.interface.instances[self.account]['infos'][jid].window.present()
        else:
            contact = app.contacts.create_contact(jid=jid, account=self.account)
            app.interface.instances[self.account]['infos'][jid] = \
                    vcard.VcardWindow(contact, self.account)

    def _nec_search_form_received(self, obj):
        if self.pulse_id:
            GLib.source_remove(self.pulse_id)
        self._ui.progressbar.hide()
        self._ui.label.hide()

        if obj.is_dataform:
            self.is_form = True
            self.data_form_widget = dataforms_widget.DataFormWidget()
            self.dataform = dataforms.extend_form(node=obj.data)
            self.data_form_widget.set_sensitive(True)
            try:
                self.data_form_widget.data_form = self.dataform
            except dataforms.Error:
                self._ui.label.set_text(_('Error in received dataform'))
                self._ui.label.show()
                return
            if self.data_form_widget.title:
                self.window.set_title(
                    '%s - Search - Gajim' % self.data_form_widget.title)
        else:
            self.is_form = False
            self.data_form_widget = config.FakeDataForm(obj.data)

        self.data_form_widget.show_all()
        self._ui.search_vbox.pack_start(self.data_form_widget, True, True, 0)
        self._ui.search_button.set_sensitive(True)

    def on_result_treeview_cursor_changed(self, treeview):
        if self.jid_column == -1:
            return
        (model, iter_) = treeview.get_selection().get_selected()
        if not iter_:
            return
        if model[iter_][self.jid_column]:
            self._ui.add_contact_button.set_sensitive(True)
            self._ui.information_button.set_sensitive(True)
        else:
            self._ui.add_contact_button.set_sensitive(False)
            self._ui.information_button.set_sensitive(False)

    def _nec_search_result_received(self, obj):
        if self.pulse_id:
            GLib.source_remove(self.pulse_id)
        self._ui.progressbar.hide()
        self._ui.label.hide()

        if not obj.is_dataform:
            if not obj.data:
                self._ui.label.set_text(_('No result'))
                self._ui.label.show()
                return
            # We suppose all items have the same fields
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            self.result_treeview = Gtk.TreeView()
            self.result_treeview.connect(
                'cursor-changed', self.on_result_treeview_cursor_changed)
            sw.add(self.result_treeview)
            # Create model
            fieldtypes = [str]*len(obj.data[0])
            model = Gtk.ListStore(*fieldtypes)
            # Copy data to model
            for item in obj.data:
                model.append(item.values())
            # Create columns
            counter = 0
            for field in obj.data[0].keys():
                self.result_treeview.append_column(
                    Gtk.TreeViewColumn(field,
                                       Gtk.CellRendererText(),
                                       text=counter))
                if field == 'jid':
                    self.jid_column = counter
                counter += 1
            self.result_treeview.set_model(model)
            sw.show_all()
            self._ui.search_vbox.pack_start(sw, True, True, 0)
            if self.jid_column > -1:
                self._ui.add_contact_button.show()
                self._ui.information_button.show()
            return

        self.dataform = dataforms.extend_form(node=obj.data)
        if not self.dataform.items:
            # No result
            self._ui.label.set_text(_('No result'))
            self._ui.label.show()
            return

        self.data_form_widget.set_sensitive(True)
        try:
            self.data_form_widget.data_form = self.dataform
        except dataforms.Error:
            self._ui.label.set_text(_('Error in received dataform'))
            self._ui.label.show()
            return

        self.result_treeview = self.data_form_widget.records_treeview
        selection = self.result_treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        self.result_treeview.connect(
            'cursor-changed', self.on_result_treeview_cursor_changed)

        counter = 0
        for field in self.dataform.reported.iter_fields():
            if field.var == 'jid':
                self.jid_column = counter
                break
            counter += 1
        self._ui.search_vbox.pack_start(self.data_form_widget, True, True, 0)
        self.data_form_widget.show()
        if self.jid_column > -1:
            self._ui.add_contact_button.show()
            self._ui.information_button.show()
        if self.data_form_widget.title:
            self.window.set_title(
                '%s - Search - Gajim' % self.data_form_widget.title)
