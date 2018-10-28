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

from gajim import dataforms_widget

from gajim.gtk.util import get_builder
from gajim.gtk.dialogs import InputDialog


class GroupchatConfig:
    def __init__(self, account, room_jid, form=None):
        self.account = account
        self.room_jid = room_jid
        self.form = form
        self.remove_button = {}
        self.affiliation_treeview = {}
        self.start_users_dict = {} # list at the beginning
        self.affiliation_labels = {
            'outcast': _('Ban List'),
            'member': _('Member List'),
            'owner': _('Owner List'),
            'admin':_('Administrator List')
        }

        self._ui = get_builder('data_form_window.ui', ['data_form_window'])
        self.window = self._ui.data_form_window
        self.window.set_transient_for(app.interface.roster.window)

        if self.form:
            self.data_form_widget = dataforms_widget.DataFormWidget(self.form)
            # hide scrollbar of this data_form_widget, we already have in this
            # widget
            sw = self.data_form_widget.xml.get_object(
                'single_form_scrolledwindow')
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
            if self.form.title:
                self._ui.title_label.set_text(self.form.title)
            else:
                self._ui.title_hseparator.set_no_show_all(True)
                self._ui.title_hseparator.hide()

            self.data_form_widget.show()
            self._ui.config_vbox.pack_start(self.data_form_widget, True, True, 0)
        else:
            self._ui.title_label.set_no_show_all(True)
            self._ui.title_label.hide()
            self._ui.title_hseparator.set_no_show_all(True)
            self._ui.title_hseparator.hide()
            self._ui.config_hseparator.set_no_show_all(True)
            self._ui.config_hseparator.hide()

        # Draw the edit affiliation list things
        add_on_vbox = self._ui.add_on_vbox

        for affiliation in self.affiliation_labels:
            self.start_users_dict[affiliation] = {}
            hbox = Gtk.HBox(spacing=5)
            add_on_vbox.pack_start(hbox, False, True, 0)

            label = Gtk.Label(label=self.affiliation_labels[affiliation])
            hbox.pack_start(label, False, True, 0)

            bb = Gtk.HButtonBox()
            bb.set_layout(Gtk.ButtonBoxStyle.END)
            bb.set_spacing(5)
            hbox.pack_start(bb, True, True, 0)
            add_button = Gtk.Button(stock=Gtk.STOCK_ADD)
            add_button.connect(
                'clicked', self.on_add_button_clicked, affiliation)
            bb.pack_start(add_button, True, True, 0)
            self.remove_button[affiliation] = Gtk.Button(stock=Gtk.STOCK_REMOVE)
            self.remove_button[affiliation].set_sensitive(False)
            self.remove_button[affiliation].connect(
                'clicked', self.on_remove_button_clicked, affiliation)
            bb.pack_start(self.remove_button[affiliation], True, True, 0)

            # jid, reason, nick, role
            liststore = Gtk.ListStore(str, str, str, str)
            self.affiliation_treeview[affiliation] = Gtk.TreeView(liststore)
            self.affiliation_treeview[affiliation].get_selection().set_mode(
                Gtk.SelectionMode.MULTIPLE)
            self.affiliation_treeview[affiliation].connect(
                'cursor-changed',
                self.on_affiliation_treeview_cursor_changed,
                affiliation)
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(_('JID'), renderer)
            col.add_attribute(renderer, 'text', 0)
            col.set_resizable(True)
            col.set_sort_column_id(0)
            self.affiliation_treeview[affiliation].append_column(col)

            if affiliation == 'outcast':
                renderer = Gtk.CellRendererText()
                renderer.set_property('editable', True)
                renderer.connect('edited', self.on_cell_edited)
                col = Gtk.TreeViewColumn(_('Reason'), renderer)
                col.add_attribute(renderer, 'text', 1)
                col.set_resizable(True)
                col.set_sort_column_id(1)
                self.affiliation_treeview[affiliation].append_column(col)
            elif affiliation == 'member':
                renderer = Gtk.CellRendererText()
                col = Gtk.TreeViewColumn(_('Nick'), renderer)
                col.add_attribute(renderer, 'text', 2)
                col.set_resizable(True)
                col.set_sort_column_id(2)
                self.affiliation_treeview[affiliation].append_column(col)
                renderer = Gtk.CellRendererText()
                col = Gtk.TreeViewColumn(_('Role'), renderer)
                col.add_attribute(renderer, 'text', 3)
                col.set_resizable(True)
                col.set_sort_column_id(3)
                self.affiliation_treeview[affiliation].append_column(col)

            sw = Gtk.ScrolledWindow()
            sw.add(self.affiliation_treeview[affiliation])
            add_on_vbox.pack_start(sw, True, True, 0)
            con = app.connections[self.account]
            con.get_module('MUC').get_affiliation(self.room_jid, affiliation)

        self._ui.connect_signals(self)
        self.window.connect('delete-event', self.on_cancel_button_clicked)
        self.window.show_all()

    def on_cancel_button_clicked(self, *args):
        if self.form:
            con = app.connections[self.account]
            con.get_module('MUC').cancel_config(self.room_jid)
        self.window.destroy()

    def on_cell_edited(self, _cell, path, new_text):
        model = self.affiliation_treeview['outcast'].get_model()
        new_text = new_text
        iter_ = model.get_iter(path)
        model[iter_][1] = new_text

    def on_add_button_clicked(self, _widget, affiliation):
        if affiliation == 'outcast':
            title = _('Banning…')
            #You can move '\n' before user@domain if that line is TOO BIG
            prompt = _('<b>Whom do you want to ban?</b>\n\n')
        elif affiliation == 'member':
            title = _('Adding Member…')
            prompt = _('<b>Whom do you want to make a member?</b>\n\n')
        elif affiliation == 'owner':
            title = _('Adding Owner…')
            prompt = _('<b>Whom do you want to make an owner?</b>\n\n')
        else:
            title = _('Adding Administrator…')
            prompt = _('<b>Whom do you want to make an administrator?</b>\n\n')
        prompt += _(
            'Can be one of the following:\n'
            '1. user@domain/resource (only that resource matches).\n'
            '2. user@domain (any resource matches).\n'
            '3. domain/resource (only that resource matches).\n'
            '4. domain (the domain itself matches, as does any user@domain,\n'
            'domain/resource, or address containing a subdomain).')

        def on_ok(jid):
            if not jid:
                return
            model = self.affiliation_treeview[affiliation].get_model()
            model.append((jid, '', '', ''))
        InputDialog(title, prompt, ok_handler=on_ok)

    def on_remove_button_clicked(self, _widget, affiliation):
        selection = self.affiliation_treeview[affiliation].get_selection()
        model, paths = selection.get_selected_rows()
        row_refs = []
        for path in paths:
            row_refs.append(Gtk.TreeRowReference.new(model, path))
        for row_ref in row_refs:
            path = row_ref.get_path()
            iter_ = model.get_iter(path)
            model.remove(iter_)
        self.remove_button[affiliation].set_sensitive(False)

    def on_affiliation_treeview_cursor_changed(self, _widget, affiliation):
        self.remove_button[affiliation].set_sensitive(True)

    def affiliation_list_received(self, users_dict):
        """
        Fill the affiliation treeview
        """
        for jid in users_dict:
            affiliation = users_dict[jid]['affiliation']
            if affiliation not in self.affiliation_labels.keys():
                # Unknown affiliation or 'none' affiliation, do not show it
                continue
            self.start_users_dict[affiliation][jid] = users_dict[jid]
            tv = self.affiliation_treeview[affiliation]
            model = tv.get_model()
            reason = users_dict[jid].get('reason', '')
            nick = users_dict[jid].get('nick', '')
            role = users_dict[jid].get('role', '')
            model.append((jid, reason, nick, role))

    def on_data_form_window_destroy(self, _widget):
        del app.interface.instances[self.account]['gc_config'][self.room_jid]

    def on_ok_button_clicked(self, _widget):
        if self.form:
            form = self.data_form_widget.data_form
            con = app.connections[self.account]
            con.get_module('MUC').set_config(self.room_jid, form)
        for affiliation in self.affiliation_labels:
            users_dict = {}
            actual_jid_list = []
            model = self.affiliation_treeview[affiliation].get_model()
            iter_ = model.get_iter_first()
            # add new jid
            while iter_:
                jid = model[iter_][0]
                actual_jid_list.append(jid)
                if jid not in self.start_users_dict[affiliation] or \
                (affiliation == 'outcast' and 'reason' in self.start_users_dict[
                affiliation][jid] and self.start_users_dict[affiliation][jid]\
                ['reason'] != model[iter_][1]):
                    users_dict[jid] = {'affiliation': affiliation}
                    if affiliation == 'outcast':
                        users_dict[jid]['reason'] = model[iter_][1]
                iter_ = model.iter_next(iter_)
            # remove removed one
            for jid in self.start_users_dict[affiliation]:
                if jid not in actual_jid_list:
                    users_dict[jid] = {'affiliation': 'none'}
            if users_dict:
                con = app.connections[self.account]
                con.get_module('MUC').set_affiliation(
                    self.room_jid, users_dict)
        self.window.destroy()
