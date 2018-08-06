# -*- coding:utf-8 -*-
## src/config.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
##                         Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 James Newton <redshodan AT gmail.com>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from gajim import gtkgui_helpers
from gajim import dialogs
from gajim import dataforms_widget
from gajim import gui_menu_builder
from gajim.gtk import ConfirmationDialog
from gajim.gtk import ConfirmationDialogDoubleRadio
from gajim.gtk import ErrorDialog
from gajim.gtk import InputDialog
from gajim.common import helpers
from gajim.common import app


#---------- ManageProxiesWindow class -------------#
class ManageProxiesWindow:
    def __init__(self, transient_for=None):
        self.xml = gtkgui_helpers.get_gtk_builder('manage_proxies_window.ui')
        self.window = self.xml.get_object('manage_proxies_window')
        self.window.set_transient_for(transient_for)
        self.proxies_treeview = self.xml.get_object('proxies_treeview')
        self.proxyname_entry = self.xml.get_object('proxyname_entry')
        self.proxytype_combobox = self.xml.get_object('proxytype_combobox')

        self.init_list()
        self.block_signal = False
        self.xml.connect_signals(self)
        self.window.show_all()
        # hide the BOSH fields by default
        self.show_bosh_fields()

    def show_bosh_fields(self, show=True):
        if show:
            self.xml.get_object('boshuri_entry').show()
            self.xml.get_object('boshuri_label').show()
            self.xml.get_object('boshuseproxy_checkbutton').show()
        else:
            cb = self.xml.get_object('boshuseproxy_checkbutton')
            cb.hide()
            cb.set_active(True)
            self.on_boshuseproxy_checkbutton_toggled(cb)
            self.xml.get_object('boshuri_entry').hide()
            self.xml.get_object('boshuri_label').hide()


    def fill_proxies_treeview(self):
        model = self.proxies_treeview.get_model()
        model.clear()
        iter_ = model.append()
        model.set(iter_, 0, _('None'))
        for p in app.config.get_per('proxies'):
            iter_ = model.append()
            model.set(iter_, 0, p)

    def init_list(self):
        self.xml.get_object('remove_proxy_button').set_sensitive(False)
        self.proxytype_combobox.set_sensitive(False)
        self.xml.get_object('proxy_table').set_sensitive(False)
        model = Gtk.ListStore(str)
        self.proxies_treeview.set_model(model)
        col = Gtk.TreeViewColumn('Proxies')
        self.proxies_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', 0)
        self.fill_proxies_treeview()
        self.xml.get_object('proxytype_combobox').set_active(0)

    def on_manage_proxies_window_destroy(self, widget):
        if 'accounts' in app.interface.instances:
            app.interface.instances['accounts'].\
                    update_proxy_list()
        del app.interface.instances['manage_proxies']

    def on_add_proxy_button_clicked(self, widget):
        model = self.proxies_treeview.get_model()
        proxies = app.config.get_per('proxies')
        i = 1
        while ('proxy' + str(i)) in proxies:
            i += 1
        iter_ = model.append()
        model.set(iter_, 0, 'proxy' + str(i))
        app.config.add_per('proxies', 'proxy' + str(i))
        self.proxies_treeview.set_cursor(model.get_path(iter_))

    def on_remove_proxy_button_clicked(self, widget):
        sel = self.proxies_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        proxy = model[iter_][0]
        model.remove(iter_)
        app.config.del_per('proxies', proxy)
        self.xml.get_object('remove_proxy_button').set_sensitive(False)
        self.block_signal = True
        self.on_proxies_treeview_cursor_changed(self.proxies_treeview)
        self.block_signal = False

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_useauth_checkbutton_toggled(self, widget):
        if self.block_signal:
            return
        act = widget.get_active()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'useauth', act)
        self.xml.get_object('proxyuser_entry').set_sensitive(act)
        self.xml.get_object('proxypass_entry').set_sensitive(act)

    def on_boshuseproxy_checkbutton_toggled(self, widget):
        if self.block_signal:
            return
        act = widget.get_active()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_useproxy', act)
        self.xml.get_object('proxyhost_entry').set_sensitive(act)
        self.xml.get_object('proxyport_entry').set_sensitive(act)

    def on_proxies_treeview_cursor_changed(self, widget):
        #FIXME: check if off proxy settings are correct (see
        # http://trac.gajim.org/changeset/1921#file2 line 1221
        proxyhost_entry = self.xml.get_object('proxyhost_entry')
        proxyport_entry = self.xml.get_object('proxyport_entry')
        proxyuser_entry = self.xml.get_object('proxyuser_entry')
        proxypass_entry = self.xml.get_object('proxypass_entry')
        boshuri_entry = self.xml.get_object('boshuri_entry')
        useauth_checkbutton = self.xml.get_object('useauth_checkbutton')
        boshuseproxy_checkbutton = self.xml.get_object('boshuseproxy_checkbutton')
        self.block_signal = True
        proxyhost_entry.set_text('')
        proxyport_entry.set_text('')
        proxyuser_entry.set_text('')
        proxypass_entry.set_text('')
        boshuri_entry.set_text('')

        #boshuseproxy_checkbutton.set_active(False)
        #self.on_boshuseproxy_checkbutton_toggled(boshuseproxy_checkbutton)

        #useauth_checkbutton.set_active(False)
        #self.on_useauth_checkbutton_toggled(useauth_checkbutton)

        sel = widget.get_selection()
        if sel:
            (model, iter_) = sel.get_selected()
        else:
            iter_ = None
        if not iter_:
            self.xml.get_object('proxyname_entry').set_text('')
            self.xml.get_object('proxytype_combobox').set_sensitive(False)
            self.xml.get_object('proxy_table').set_sensitive(False)
            self.block_signal = False
            return

        proxy = model[iter_][0]
        self.xml.get_object('proxyname_entry').set_text(proxy)

        if proxy == _('None'): # special proxy None
            self.show_bosh_fields(False)
            self.proxyname_entry.set_editable(False)
            self.xml.get_object('remove_proxy_button').set_sensitive(False)
            self.xml.get_object('proxytype_combobox').set_sensitive(False)
            self.xml.get_object('proxy_table').set_sensitive(False)
        else:
            proxytype = app.config.get_per('proxies', proxy, 'type')

            self.show_bosh_fields(proxytype=='bosh')

            self.proxyname_entry.set_editable(True)
            self.xml.get_object('remove_proxy_button').set_sensitive(True)
            self.xml.get_object('proxytype_combobox').set_sensitive(True)
            self.xml.get_object('proxy_table').set_sensitive(True)
            proxyhost_entry.set_text(app.config.get_per('proxies', proxy,
                    'host'))
            proxyport_entry.set_text(str(app.config.get_per('proxies',
                    proxy, 'port')))
            proxyuser_entry.set_text(app.config.get_per('proxies', proxy,
                    'user'))
            proxypass_entry.set_text(app.config.get_per('proxies', proxy,
                    'pass'))
            boshuri_entry.set_text(app.config.get_per('proxies', proxy,
                    'bosh_uri'))
            types = ['http', 'socks5', 'bosh']
            self.proxytype_combobox.set_active(types.index(proxytype))
            boshuseproxy_checkbutton.set_active(
                    app.config.get_per('proxies', proxy, 'bosh_useproxy'))
            useauth_checkbutton.set_active(
                    app.config.get_per('proxies', proxy, 'useauth'))
        self.block_signal = False

    def on_proxies_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self.on_remove_proxy_button_clicked(widget)

    def on_proxyname_entry_changed(self, widget):
        if self.block_signal:
            return
        sel = self.proxies_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        old_name = model.get_value(iter_, 0)
        new_name = widget.get_text()
        if new_name == '':
            return
        if new_name == old_name:
            return
        config = app.config.get_per('proxies', old_name)
        app.config.del_per('proxies', old_name)
        app.config.add_per('proxies', new_name)
        for option in config:
            app.config.set_per('proxies', new_name, option, config[option])
        model.set_value(iter_, 0, new_name)

    def on_proxytype_combobox_changed(self, widget):
        if self.block_signal:
            return
        types = ['http', 'socks5', 'bosh']
        type_ = self.proxytype_combobox.get_active()
        self.show_bosh_fields(types[type_]=='bosh')
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'type', types[type_])

    def on_proxyhost_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'host', value)

    def on_proxyport_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'port', value)

    def on_proxyuser_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'user', value)

    def on_boshuri_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_uri', value)

    def on_proxypass_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'pass', value)


class FakeDataForm(Gtk.Table, object):
    """
    Class for forms that are in XML format <entry1>value1</entry1> infos in a
    table {entry1: value1}
    """

    def __init__(self, infos, selectable=False):
        GObject.GObject.__init__(self)
        self.infos = infos
        self.selectable = selectable
        self.entries = {}
        self._draw_table()

    def _draw_table(self):
        """
        Draw the table
        """
        nbrow = 0
        if 'instructions' in self.infos:
            nbrow = 1
            self.resize(rows = nbrow, columns = 2)
            label = Gtk.Label(label=self.infos['instructions'])
            if self.selectable:
                label.set_selectable(True)
            self.attach(label, 0, 2, 0, 1, 0, 0, 0, 0)
        for name in self.infos.keys():
            if name in ('key', 'instructions', 'x', 'registered'):
                continue
            if not name:
                continue

            nbrow = nbrow + 1
            self.resize(rows = nbrow, columns = 2)
            label = Gtk.Label(label=name.capitalize() + ':')
            self.attach(label, 0, 1, nbrow - 1, nbrow, 0, 0, 0, 0)
            entry = Gtk.Entry()
            entry.set_activates_default(True)
            if self.infos[name]:
                entry.set_text(self.infos[name])
            if name == 'password':
                entry.set_visibility(False)
            self.attach(entry, 1, 2, nbrow - 1, nbrow, 0, 0, 0, 0)
            self.entries[name] = entry
            if nbrow == 1:
                entry.grab_focus()

    def get_infos(self):
        for name in self.entries.keys():
            self.infos[name] = self.entries[name].get_text()
        return self.infos

class GroupchatConfigWindow:

    def __init__(self, account, room_jid, form=None):
        self.account = account
        self.room_jid = room_jid
        self.form = form
        self.remove_button = {}
        self.affiliation_treeview = {}
        self.start_users_dict = {} # list at the beginning
        self.affiliation_labels = {'outcast': _('Ban List'),
            'member': _('Member List'), 'owner': _('Owner List'),
            'admin':_('Administrator List')}

        self.xml = gtkgui_helpers.get_gtk_builder('data_form_window.ui',
            'data_form_window')
        self.window = self.xml.get_object('data_form_window')
        self.window.set_transient_for(app.interface.roster.window)

        if self.form:
            config_vbox = self.xml.get_object('config_vbox')
            self.data_form_widget = dataforms_widget.DataFormWidget(self.form)
            # hide scrollbar of this data_form_widget, we already have in this
            # widget
            sw = self.data_form_widget.xml.get_object(
                'single_form_scrolledwindow')
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
            if self.form.title:
                self.xml.get_object('title_label').set_text(self.form.title)
            else:
                self.xml.get_object('title_hseparator').set_no_show_all(True)
                self.xml.get_object('title_hseparator').hide()

            self.data_form_widget.show()
            config_vbox.pack_start(self.data_form_widget, True, True, 0)
        else:
            self.xml.get_object('title_label').set_no_show_all(True)
            self.xml.get_object('title_label').hide()
            self.xml.get_object('title_hseparator').set_no_show_all(True)
            self.xml.get_object('title_hseparator').hide()
            self.xml.get_object('config_hseparator').set_no_show_all(True)
            self.xml.get_object('config_hseparator').hide()

        # Draw the edit affiliation list things
        add_on_vbox = self.xml.get_object('add_on_vbox')

        for affiliation in self.affiliation_labels.keys():
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
            add_button.connect('clicked', self.on_add_button_clicked,
                affiliation)
            bb.pack_start(add_button, True, True, 0)
            self.remove_button[affiliation] = Gtk.Button(stock=Gtk.STOCK_REMOVE)
            self.remove_button[affiliation].set_sensitive(False)
            self.remove_button[affiliation].connect('clicked',
                    self.on_remove_button_clicked, affiliation)
            bb.pack_start(self.remove_button[affiliation], True, True, 0)

            # jid, reason, nick, role
            liststore = Gtk.ListStore(str, str, str, str)
            self.affiliation_treeview[affiliation] = Gtk.TreeView(liststore)
            self.affiliation_treeview[affiliation].get_selection().set_mode(
                Gtk.SelectionMode.MULTIPLE)
            self.affiliation_treeview[affiliation].connect('cursor-changed',
                self.on_affiliation_treeview_cursor_changed, affiliation)
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

        self.xml.connect_signals(self)
        self.window.connect('delete-event', self.on_cancel_button_clicked)
        self.window.show_all()

    def on_cancel_button_clicked(self, *args):
        if self.form:
            con = app.connections[self.account]
            con.get_module('MUC').cancel_config(self.room_jid)
        self.window.destroy()

    def on_cell_edited(self, cell, path, new_text):
        model = self.affiliation_treeview['outcast'].get_model()
        new_text = new_text
        iter_ = model.get_iter(path)
        model[iter_][1] = new_text

    def on_add_button_clicked(self, widget, affiliation):
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
        prompt += _('Can be one of the following:\n'
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

    def on_remove_button_clicked(self, widget, affiliation):
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

    def on_affiliation_treeview_cursor_changed(self, widget, affiliation):
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

    def on_data_form_window_destroy(self, widget):
        del app.interface.instances[self.account]['gc_config'][self.room_jid]

    def on_ok_button_clicked(self, widget):
        if self.form:
            form = self.data_form_widget.data_form
            con = app.connections[self.account]
            con.get_module('MUC').set_config(self.room_jid, form)
        for affiliation in self.affiliation_labels.keys():
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

#---------- RemoveAccountWindow class -------------#
class RemoveAccountWindow:
    """
    Ask for removing from gajim only or from gajim and server too and do
    removing of the account given
    """

    def on_remove_account_window_destroy(self, widget):
        if self.account in app.interface.instances:
            del app.interface.instances[self.account]['remove_account']

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def __init__(self, account):
        self.account = account
        xml = gtkgui_helpers.get_gtk_builder('remove_account_window.ui')
        self.window = xml.get_object('remove_account_window')
        active_window = app.app.get_active_window()
        self.window.set_transient_for(active_window)
        self.remove_and_unregister_radiobutton = xml.get_object(
                'remove_and_unregister_radiobutton')
        self.window.set_title(_('Removing %s account') % self.account)
        xml.connect_signals(self)
        self.window.show_all()

    def on_remove_button_clicked(self, widget):
        def remove():
            if self.account in app.connections and \
            app.connections[self.account].connected and \
            not self.remove_and_unregister_radiobutton.get_active():
                # change status to offline only if we will not remove this JID from
                # server
                app.connections[self.account].change_status('offline', 'offline')
            if self.remove_and_unregister_radiobutton.get_active():
                if not self.account in app.connections:
                    ErrorDialog(
                        _('Account is disabled'),
                        _('To unregister from a server, account must be '
                        'enabled.'),
                        transient_for=self.window)
                    return
                if not app.connections[self.account].password:
                    def on_ok(passphrase, checked):
                        if passphrase == -1:
                            # We don't remove account cause we canceled pw window
                            return
                        app.connections[self.account].password = passphrase
                        app.connections[self.account].unregister_account(
                                self._on_remove_success)

                    dialogs.PassphraseDialog(
                            _('Password Required'),
                            _('Enter your password for account %s') % self.account,
                            _('Save password'), ok_handler=on_ok,
                            transient_for=self.window)
                    return
                app.connections[self.account].unregister_account(
                        self._on_remove_success)
            else:
                self._on_remove_success(True)

        if self.account in app.connections and \
        app.connections[self.account].connected:
            ConfirmationDialog(
                _('Account "%s" is connected to the server') % self.account,
                _('If you remove it, the connection will be lost.'),
                on_response_ok=remove,
                transient_for=self.window)
        else:
            remove()

    def on_remove_responce_ok(self, is_checked):
        if is_checked[0]:
            self._on_remove_success(True)

    def _on_remove_success(self, res):
        # action of unregistration has failed, we don't remove the account
        # Error message is send by connect_and_auth()
        if not res:
            ConfirmationDialogDoubleRadio(
                    _('Connection to server %s failed') % self.account,
                    _('What would you like to do?'),
                    _('Remove only from Gajim'),
                    _('Don\'t remove anything. I\'ll try again later'),
                    on_response_ok=self.on_remove_responce_ok, is_modal=False,
                    transient_for=self.window)
            return
        # Close all opened windows
        app.interface.roster.close_all(self.account, force=True)
        if self.account in app.connections:
            app.connections[self.account].disconnect(on_purpose=True)
            app.connections[self.account].cleanup()
            del app.connections[self.account]
        app.logger.remove_roster(app.get_jid_from_account(self.account))
        app.config.del_per('accounts', self.account)
        del app.interface.instances[self.account]
        if self.account in app.nicks:
            del app.interface.minimized_controls[self.account]
            del app.nicks[self.account]
            del app.block_signed_in_notifications[self.account]
            del app.groups[self.account]
            app.contacts.remove_account(self.account)
            del app.gc_connected[self.account]
            del app.automatic_rooms[self.account]
            del app.to_be_removed[self.account]
            del app.newly_added[self.account]
            del app.sleeper_state[self.account]
            del app.encrypted_chats[self.account]
            del app.last_message_time[self.account]
            del app.status_before_autoaway[self.account]
            del app.transport_avatar[self.account]
            del app.gajim_optional_features[self.account]
            del app.caps_hash[self.account]
        if len(app.connections) >= 2: # Do not merge accounts if only one exists
            app.interface.roster.regroup = app.config.get('mergeaccounts')
        else:
            app.interface.roster.regroup = False
        app.interface.roster.setup_and_draw_roster()
        app.app.remove_account_actions(self.account)
        gui_menu_builder.build_accounts_menu()
        if 'accounts' in app.interface.instances:
            app.interface.instances['accounts'].remove_account(self.account)
        self.window.destroy()


class ManageSoundsWindow:
    def __init__(self, transient):
        self._builder = gtkgui_helpers.get_gtk_builder(
            'manage_sounds_window.ui')
        self.window = self._builder.get_object('manage_sounds_window')
        self.window.set_transient_for(transient)

        self.sound_button = self._builder.get_object('filechooser')

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self.sound_button.add_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('Wav Sounds'))
        filter_.add_pattern('*.wav')
        self.sound_button.add_filter(filter_)
        self.sound_button.set_filter(filter_)

        self.sound_tree = self._builder.get_object('sounds_treeview')

        self._fill_sound_treeview()

        self._builder.connect_signals(self)

        self.window.show_all()

    def _on_row_changed(self, model, path, iter_):
        sound_event = model[iter_][3]
        app.config.set_per('soundevents', sound_event,
                           'enabled', bool(model[path][0]))
        app.config.set_per('soundevents', sound_event,
                           'path', model[iter_][2])

    def _on_toggle(self, cell, path):
        if self.sound_button.get_filename() is None:
            return
        model = self.sound_tree.get_model()
        model[path][0] = not model[path][0]

    def _fill_sound_treeview(self):
        model = self.sound_tree.get_model()
        model.clear()

        # NOTE: sounds_ui_names MUST have all items of
        # sounds = app.config.get_per('soundevents') as keys
        sounds_dict = {
            'attention_received': _('Attention Message Received'),
            'first_message_received': _('First Message Received'),
            'next_message_received_focused': _('Next Message Received Focused'),
            'next_message_received_unfocused': _('Next Message Received Unfocused'),
            'contact_connected': _('Contact Connected'),
            'contact_disconnected': _('Contact Disconnected'),
            'message_sent': _('Message Sent'),
            'muc_message_highlight': _('Group Chat Message Highlight'),
            'muc_message_received': _('Group Chat Message Received'),
        }

        for config_name, sound_name in sounds_dict.items():
            enabled = app.config.get_per('soundevents', config_name, 'enabled')
            path = app.config.get_per('soundevents', config_name, 'path')
            model.append((enabled, sound_name, path, config_name))

    def _on_cursor_changed(self, treeview):
        model, iter_ = treeview.get_selection().get_selected()
        path_to_snd_file = helpers.check_soundfile_path(model[iter_][2])
        if path_to_snd_file is None:
            self.sound_button.unselect_all()
        else:
            self.sound_button.set_filename(path_to_snd_file)

    def _on_file_set(self, button):
        model, iter_ = self.sound_tree.get_selection().get_selected()

        filename = button.get_filename()
        directory = os.path.dirname(filename)
        app.config.set('last_sounds_dir', directory)
        path_to_snd_file = helpers.strip_soundfile_path(filename)

        # set new path to sounds_model
        model[iter_][2] = path_to_snd_file
        # set the sound to enabled
        model[iter_][0] = True

    def _on_clear(self, *args):
        self.sound_button.unselect_all()
        model, iter_ = self.sound_tree.get_selection().get_selected()
        model[iter_][2] = ''
        model[iter_][0] = False

    def _on_play(self, *args):
        model, iter_ = self.sound_tree.get_selection().get_selected()
        snd_event_config_name = model[iter_][3]
        helpers.play_sound(snd_event_config_name)

    def _on_destroy(self, *args):
        self.window.destroy()
        window = app.get_app_window('Preferences')
        if window is not None:
            window.sounds_preferences = None
