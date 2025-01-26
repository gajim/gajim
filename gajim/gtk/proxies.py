# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.util import get_app_window
from gajim.gtk.widgets import GajimAppWindow


class ManageProxies(GajimAppWindow):
    def __init__(self, transient_for: Gtk.Window | None = None) -> None:
        GajimAppWindow.__init__(
            self,
            name="ManageProxies",
            title=_("Manage Proxies"),
            default_width=500,
            transient_for=transient_for,
            modal=True,
        )

        self._ui = get_builder("manage_proxies.ui")
        self.set_child(self._ui.box)

        liststore = Gtk.ListStore(str)
        liststore.append(["HTTP"])
        liststore.append(["SOCKS5"])
        self._ui.proxytype_combobox.set_model(liststore)

        self._connect(
            self._ui.proxies_treeview,
            "cursor-changed",
            self._on_proxies_treeview_cursor_changed,
        )
        self._connect(
            self._ui.add_proxy_button, "clicked", self._on_add_proxy_button_clicked
        )
        self._connect(
            self._ui.remove_proxy_button,
            "clicked",
            self._on_remove_proxy_button_clicked,
        )
        self._connect(
            self._ui.proxypass_entry, "changed", self._on_proxypass_entry_changed
        )
        self._connect(self._ui.useauth_checkbutton, "toggled", self._on_useauth_toggled)
        self._connect(
            self._ui.proxyport_entry, "changed", self._on_proxyport_entry_changed
        )
        self._connect(
            self._ui.proxyhost_entry, "changed", self._on_proxyhost_entry_changed
        )
        self._connect(
            self._ui.proxytype_combobox, "changed", self._on_proxytype_combobox_changed
        )
        self._connect(
            self._ui.proxyname_entry, "changed", self._on_proxyname_entry_changed
        )

        self._init_list()
        self._block_signal = False

        controller = Gtk.EventControllerKey()
        self._connect(
            self.get_default_controller(),
            "key-pressed",
            self._on_proxies_treeview_key_pressed,
        )
        self._ui.proxies_treeview.add_controller(controller)

    def _cleanup(self) -> None:
        # Window callbacks for updating proxy comboboxes
        window_pref = get_app_window("Preferences")
        window_accounts = get_app_window("AccountsWindow")
        window_account_wizard = get_app_window("AccountWizard")
        if window_pref is not None:
            window_pref.update_proxy_list()
        if window_accounts is not None:
            window_accounts.update_proxy_list()
        if window_account_wizard is not None:
            window_account_wizard.update_proxy_list()

    def _fill_proxies_treeview(self) -> None:
        model = self._ui.proxies_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.clear()
        for proxy in app.settings.get_proxies():
            iter_ = model.append()
            model.set_value(iter_, 0, proxy)

    def _init_list(self) -> None:
        self._ui.remove_proxy_button.set_sensitive(False)
        self._ui.settings_grid.set_sensitive(False)
        model = Gtk.ListStore(str)
        self._ui.proxies_treeview.set_model(model)
        col = Gtk.TreeViewColumn(title=_("Proxies"))
        self._ui.proxies_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 0)
        self._fill_proxies_treeview()
        self._ui.proxytype_combobox.set_active(0)

    def _on_add_proxy_button_clicked(self, _button: Gtk.Button) -> None:
        model = self._ui.proxies_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        proxies = app.settings.get_proxies()
        i = 1
        while "proxy" + str(i) in proxies:
            i += 1

        proxy_name = "proxy" + str(i)
        app.settings.add_proxy(proxy_name)
        iter_ = model.append()
        model.set_value(iter_, 0, proxy_name)
        self._ui.proxies_treeview.set_cursor(model.get_path(iter_))

    def _on_remove_proxy_button_clicked(self, _button: Gtk.Button) -> None:
        self._remove_selected_proxy()

    def _remove_selected_proxy(self) -> None:
        def _remove():
            sel = self._ui.proxies_treeview.get_selection()
            if not sel:
                return
            (model, iter_) = sel.get_selected()
            if not iter_:
                return

            assert isinstance(model, Gtk.ListStore)
            proxy = model[iter_][0]
            model.remove(iter_)
            app.settings.remove_proxy(proxy)
            self._ui.remove_proxy_button.set_sensitive(False)
            self._block_signal = True
            self._on_proxies_treeview_cursor_changed(self._ui.proxies_treeview)
            self._block_signal = False

        ConfirmationDialog(
            _("Remove Proxy?"),
            _("Do you really want to remove this proxy?"),
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Remove", callback=_remove),
            ],
            transient_for=self.window,
        ).show()

    def _on_useauth_toggled(self, checkbutton: Gtk.CheckButton) -> None:
        if self._block_signal:
            return
        act = checkbutton.get_active()
        proxy = self._ui.proxyname_entry.get_text()
        app.settings.set_proxy_setting(proxy, "useauth", act)
        self._ui.proxyuser_entry.set_sensitive(act)
        self._ui.proxypass_entry.set_sensitive(act)

    def _on_proxies_treeview_cursor_changed(self, treeview: Gtk.TreeView) -> None:
        self._block_signal = True
        self._ui.proxyhost_entry.set_text("")
        self._ui.proxyport_entry.set_text("")
        self._ui.proxyuser_entry.set_text("")
        self._ui.proxypass_entry.set_text("")

        sel = treeview.get_selection()
        if not sel:
            self._ui.proxyname_entry.set_text("")
            self._ui.settings_grid.set_sensitive(False)
            self._block_signal = False
            return

        (model, iter_) = sel.get_selected()
        if iter_ is None:
            return

        proxy = model[iter_][0]
        self._ui.proxyname_entry.set_text(proxy)

        self._ui.remove_proxy_button.set_sensitive(True)
        self._ui.proxyname_entry.set_editable(True)

        self._ui.settings_grid.set_sensitive(True)

        settings = app.settings.get_proxy_settings(proxy)

        self._ui.proxyhost_entry.set_text(str(settings["host"]))
        self._ui.proxyport_entry.set_text(str(settings["port"]))
        self._ui.proxyuser_entry.set_text(str(settings["user"]))
        self._ui.proxypass_entry.set_text(str(settings["pass"]))

        types = ["http", "socks5"]
        self._ui.proxytype_combobox.set_active(types.index(str(settings["type"])))

        self._ui.useauth_checkbutton.set_active(bool(settings["useauth"]))
        act = self._ui.useauth_checkbutton.get_active()
        self._ui.proxyuser_entry.set_sensitive(act)
        self._ui.proxypass_entry.set_sensitive(act)

        self._block_signal = False

    def _on_proxies_treeview_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Delete:
            self._remove_selected_proxy()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_proxyname_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._block_signal:
            return
        sel = self._ui.proxies_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        old_name = model.get_value(iter_, 0)
        assert isinstance(old_name, str)
        new_name = entry.get_text()
        if new_name == "":
            return
        if new_name == old_name:
            return

        app.settings.rename_proxy(old_name, new_name)
        assert isinstance(model, Gtk.ListStore)
        model.set_value(iter_, 0, new_name)

    def _on_proxytype_combobox_changed(self, _combobox: Gtk.ComboBox) -> None:
        if self._block_signal:
            return
        types = ["http", "socks5"]
        type_ = self._ui.proxytype_combobox.get_active()
        self._ui.proxyhost_entry.set_sensitive(True)
        self._ui.proxyport_entry.set_sensitive(True)
        proxy = self._ui.proxyname_entry.get_text()
        app.settings.set_proxy_setting(proxy, "type", types[type_])

    def _on_proxyhost_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.settings.set_proxy_setting(proxy, "host", value)

    def _on_proxyport_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._block_signal:
            return
        value = entry.get_text()
        try:
            value = int(value)
        except Exception:
            value = 0
        proxy = self._ui.proxyname_entry.get_text()
        app.settings.set_proxy_setting(proxy, "port", value)

    def _on_proxyuser_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.settings.set_proxy_setting(proxy, "user", value)

    def _on_proxypass_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._block_signal:
            return
        value = entry.get_text()
        proxy = self._ui.proxyname_entry.get_text()
        app.settings.set_proxy_setting(proxy, "pass", value)
