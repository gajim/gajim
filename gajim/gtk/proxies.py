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

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.util import get_builder


class ManageProxies:
    def __init__(self):
        self._ui = get_builder('manage_proxies_window.ui')
        self.window = self._ui.manage_proxies_window
        self.window.set_transient_for(app.app.get_active_window())

        self.init_list()
        self.block_signal = False
        self._ui.connect_signals(self)
        self.window.show_all()

        # hide the BOSH fields by default
        self.show_bosh_fields()
        self._ui.boshuri_entry.hide()
        self._ui.boshuri_label.hide()
        self._ui.boshuseproxy_checkbutton.hide()

    def show_bosh_fields(self, show=True):
        if show:
            self._ui.boshuri_entry.show()
            self._ui.boshuri_label.show()
            self._ui.boshuseproxy_checkbutton.show()
            act = self._ui.boshuseproxy_checkbutton.get_active()
            self._ui.proxyhost_entry.set_sensitive(act)
            self._ui.proxyport_entry.set_sensitive(act)
        else:
            self._ui.boshuseproxy_checkbutton.hide()
            self._ui.boshuseproxy_checkbutton.set_active(True)
            self.on_boshuseproxy_checkbutton_toggled(
                self._ui.boshuseproxy_checkbutton)
            self._ui.boshuri_entry.hide()
            self._ui.boshuri_label.hide()

    def fill_proxies_treeview(self):
        model = self._ui.proxies_treeview.get_model()
        model.clear()
        iter_ = model.append()
        model.set(iter_, 0, _('None'))
        for proxy in app.config.get_per('proxies'):
            iter_ = model.append()
            model.set(iter_, 0, proxy)

    def init_list(self):
        self._ui.remove_proxy_button.set_sensitive(False)
        self._ui.proxytype_combobox.set_sensitive(False)
        self._ui.proxy_table.set_sensitive(False)
        model = Gtk.ListStore(str)
        self._ui.proxies_treeview.set_model(model)
        col = Gtk.TreeViewColumn('Proxies')
        self._ui.proxies_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', 0)
        self.fill_proxies_treeview()
        self._ui.proxytype_combobox.set_active(0)

    def on_add_proxy_button_clicked(self, _widget):
        model = self._ui.proxies_treeview.get_model()
        proxies = app.config.get_per('proxies')
        i = 1
        while 'proxy' + str(i) in proxies:
            i += 1
        iter_ = model.append()
        model.set(iter_, 0, 'proxy' + str(i))
        app.config.add_per('proxies', 'proxy' + str(i))
        self._ui.proxies_treeview.set_cursor(model.get_path(iter_))

    def on_remove_proxy_button_clicked(self, _widget):
        sel = self._ui.proxies_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        proxy = model[iter_][0]
        if proxy == _('None'):
            return
        model.remove(iter_)
        app.config.del_per('proxies', proxy)
        self._ui.remove_proxy_button.set_sensitive(False)
        self.block_signal = True
        self.on_proxies_treeview_cursor_changed(self._ui.proxies_treeview)
        self.block_signal = False

    def on_useauth_checkbutton_toggled(self, widget):
        if self.block_signal:
            return
        act = widget.get_active()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'useauth', act)
        self._ui.proxyuser_entry.set_sensitive(act)
        self._ui.proxypass_entry.set_sensitive(act)

    def on_boshuseproxy_checkbutton_toggled(self, widget):
        if self.block_signal:
            return
        act = widget.get_active()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_useproxy', act)
        self._ui.proxyhost_entry.set_sensitive(act)
        self._ui.proxyport_entry.set_sensitive(act)

    def on_proxies_treeview_cursor_changed(self, widget):
        #FIXME: check if off proxy settings are correct (see
        # http://trac.gajim.org/changeset/1921#file2 line 1221

        self.block_signal = True
        self._ui.proxyhost_entry.set_text('')
        self._ui.proxyport_entry.set_text('')
        self._ui.proxyuser_entry.set_text('')
        self._ui.proxypass_entry.set_text('')
        self._ui.boshuri_entry.set_text('')

        sel = widget.get_selection()
        if sel:
            (model, iter_) = sel.get_selected()
        else:
            iter_ = None
        if not iter_:
            self._ui.proxyname_entry.set_text('')
            self._ui.proxytype_combobox.set_sensitive(False)
            self._ui.proxy_table.set_sensitive(False)
            self.block_signal = False
            return

        proxy = model[iter_][0]
        self._ui.proxyname_entry.set_text(proxy)

        if proxy == _('None'): # special proxy None
            self.show_bosh_fields(False)
            self._ui.proxyname_entry.set_editable(False)
            self._ui.proxyname_entry.set_sensitive(False)
            self._ui.remove_proxy_button.set_sensitive(False)
            self._ui.proxytype_combobox.set_sensitive(False)
            self._ui.proxy_table.set_sensitive(False)
        else:
            proxytype = app.config.get_per('proxies', proxy, 'type')

            self.show_bosh_fields(proxytype == 'bosh')

            self._ui.proxyname_entry.set_editable(True)
            self._ui.proxyname_entry.set_sensitive(True)
            self._ui.remove_proxy_button.set_sensitive(True)
            self._ui.proxytype_combobox.set_sensitive(True)
            self._ui.proxy_table.set_sensitive(True)

            self._ui.boshuri_entry.set_text(
                app.config.get_per('proxies', proxy, 'bosh_uri'))
            self._ui.boshuseproxy_checkbutton.set_active(
                app.config.get_per('proxies', proxy, 'bosh_useproxy'))
            if proxytype == 'bosh':
                act = self._ui.boshuseproxy_checkbutton.get_active()
                self._ui.proxyhost_entry.set_sensitive(act)
                self._ui.proxyport_entry.set_sensitive(act)

            self._ui.proxyhost_entry.set_text(
                app.config.get_per('proxies', proxy, 'host'))
            self._ui.proxyport_entry.set_text(
                str(app.config.get_per('proxies', proxy, 'port')))
            self._ui.proxyuser_entry.set_text(
                app.config.get_per('proxies', proxy, 'user'))
            self._ui.proxypass_entry.set_text(
                app.config.get_per('proxies', proxy, 'pass'))

            types = ['http', 'socks5', 'bosh']
            self._ui.proxytype_combobox.set_active(types.index(proxytype))

            self._ui.useauth_checkbutton.set_active(
                app.config.get_per('proxies', proxy, 'useauth'))
            act = self._ui.useauth_checkbutton.get_active()
            self._ui.proxyuser_entry.set_sensitive(act)
            self._ui.proxypass_entry.set_sensitive(act)
        self.block_signal = False

    def on_proxies_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self.on_remove_proxy_button_clicked(widget)

    def on_proxyname_entry_changed(self, widget):
        if self.block_signal:
            return
        sel = self._ui.proxies_treeview.get_selection()
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

    def on_proxytype_combobox_changed(self, _widget):
        if self.block_signal:
            return
        types = ['http', 'socks5', 'bosh']
        type_ = self._ui.proxytype_combobox.get_active()
        self.show_bosh_fields(types[type_] == 'bosh')
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'type', types[type_])

    def on_boshuri_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_uri', value)

    def on_proxyhost_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'host', value)

    def on_proxyport_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'port', value)

    def on_proxyuser_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'user', value)

    def on_proxypass_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'pass', value)

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def _on_destroy(self, *args):
        window_pref = app.get_app_window('Preferences')
        window_accounts = app.get_app_window('AccountsWindow')
        if window_pref is not None:
            window_pref.update_proxy_list()
        if window_accounts is not None:
            window_accounts.update_proxy_list()
        del app.interface.instances['manage_proxies']
