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
from gajim.gtk.util import get_app_window


class ManageProxies(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('ManageProxies')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(500, -1)
        self.set_show_menubar(False)
        self.set_title(_('Manage Proxies'))

        self._ui = get_builder('manage_proxies.ui')
        self.add(self._ui.box)

        self._init_list()
        self._block_signal = False

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)
        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    @staticmethod
    def _on_destroy(*args):
        # Window callbacks for updating proxy comboboxes
        window_pref = get_app_window('Preferences')
        window_accounts = get_app_window('AccountsWindow')
        if window_pref is not None:
            window_pref.update_proxy_list()
        if window_accounts is not None:
            window_accounts.update_proxy_list()

    def _show_bosh_fields(self, show=True):
        if show:
            self._ui.boshuri_entry.show()
            self._ui.boshuri_label.show()
            self._ui.bosh_useproxy_checkbutton.show()
            act = self._ui.bosh_useproxy_checkbutton.get_active()
            self._ui.proxyhost_entry.set_sensitive(act)
            self._ui.proxyport_entry.set_sensitive(act)
        else:
            self._ui.boshuri_entry.hide()
            self._ui.boshuri_label.hide()
            self._ui.bosh_useproxy_checkbutton.hide()
            self._ui.proxyhost_entry.set_sensitive(True)
            self._ui.proxyport_entry.set_sensitive(True)

    def _fill_proxies_treeview(self):
        model = self._ui.proxies_treeview.get_model()
        model.clear()
        for proxy in app.config.get_per('proxies'):
            iter_ = model.append()
            model.set(iter_, 0, proxy)

    def _init_list(self):
        self._ui.remove_proxy_button.set_sensitive(False)
        self._ui.settings_grid.set_sensitive(False)
        model = Gtk.ListStore(str)
        self._ui.proxies_treeview.set_model(model)
        col = Gtk.TreeViewColumn('Proxies')
        self._ui.proxies_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', 0)
        self._fill_proxies_treeview()
        self._ui.proxytype_combobox.set_active(0)

    def _on_add_proxy_button_clicked(self, _widget):
        model = self._ui.proxies_treeview.get_model()
        proxies = app.config.get_per('proxies')
        i = 1
        while 'proxy' + str(i) in proxies:
            i += 1
        iter_ = model.append()
        model.set(iter_, 0, 'proxy' + str(i))
        app.config.add_per('proxies', 'proxy' + str(i))
        self._ui.proxies_treeview.set_cursor(model.get_path(iter_))

    def _on_remove_proxy_button_clicked(self, _widget):
        sel = self._ui.proxies_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        proxy = model[iter_][0]
        model.remove(iter_)
        app.config.del_per('proxies', proxy)
        self._ui.remove_proxy_button.set_sensitive(False)
        self._block_signal = True
        self._on_proxies_treeview_cursor_changed(self._ui.proxies_treeview)
        self._block_signal = False

    def _on_useauth_toggled(self, widget):
        if self._block_signal:
            return
        act = widget.get_active()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'useauth', act)
        self._ui.proxyuser_entry.set_sensitive(act)
        self._ui.proxypass_entry.set_sensitive(act)

    def _on_bosh_useproxy_toggled(self, checkbutton):
        if self._block_signal:
            return
        act = checkbutton.get_active()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_useproxy', act)
        self._ui.proxyhost_entry.set_sensitive(act)
        self._ui.proxyport_entry.set_sensitive(act)

    def _on_proxies_treeview_cursor_changed(self, widget):
        self._block_signal = True
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
            self._ui.settings_grid.set_sensitive(False)
            self._block_signal = False
            return

        proxy = model[iter_][0]
        self._ui.proxyname_entry.set_text(proxy)

        proxytype = app.config.get_per('proxies', proxy, 'type')

        self._show_bosh_fields(proxytype == 'bosh')

        self._ui.remove_proxy_button.set_sensitive(True)
        self._ui.proxyname_entry.set_editable(True)

        self._ui.settings_grid.set_sensitive(True)

        self._ui.boshuri_entry.set_text(
            app.config.get_per('proxies', proxy, 'bosh_uri'))
        self._ui.bosh_useproxy_checkbutton.set_active(
            app.config.get_per('proxies', proxy, 'bosh_useproxy'))
        if proxytype == 'bosh':
            act = self._ui.bosh_useproxy_checkbutton.get_active()
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

        self._block_signal = False

    def _on_proxies_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self._on_remove_proxy_button_clicked(widget)

    def _on_proxyname_entry_changed(self, widget):
        if self._block_signal:
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

    def _on_proxytype_combobox_changed(self, _widget):
        if self._block_signal:
            return
        types = ['http', 'socks5', 'bosh']
        type_ = self._ui.proxytype_combobox.get_active()
        self._ui.proxyhost_entry.set_sensitive(True)
        self._ui.proxyport_entry.set_sensitive(True)
        self._show_bosh_fields(types[type_] == 'bosh')
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'type', types[type_])

    def _on_boshuri_entry_changed(self, entry):
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_uri', value)

    def _on_proxyhost_entry_changed(self, entry):
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'host', value)

    def _on_proxyport_entry_changed(self, entry):
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'port', value)

    def _on_proxyuser_entry_changed(self, entry):
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'user', value)

    def _on_proxypass_entry_changed(self, entry):
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'pass', value)
