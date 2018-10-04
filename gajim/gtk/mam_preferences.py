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

import logging

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _

from gajim.gtk.util import get_builder
from gajim.gtk.dialogs import HigDialog

log = logging.getLogger('gajim.gtk.mam_preferences')


class MamPreferences(Gtk.ApplicationWindow):
    def __init__(self, account):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Archiving Preferences for %s') % account)

        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press)

        self.account = account
        self._con = app.connections[account]

        self._builder = get_builder('mam_preferences.ui')
        self.add(self._builder.get_object('preferences_grid'))

        self._default = self._builder.get_object('default_cb')
        self._pref_store = self._builder.get_object('preferences_store')
        self._overlay = self._builder.get_object('overlay')
        self._spinner = Gtk.Spinner()
        self._overlay.add_overlay(self._spinner)

        app.ged.register_event_handler('mam-prefs-received', ged.GUI1,
                                       self._mam_prefs_received)
        app.ged.register_event_handler('mam-prefs-saved', ged.GUI1,
                                       self._mam_prefs_saved)
        app.ged.register_event_handler('mam-prefs-error', ged.GUI1,
                                       self._mam_prefs_error)

        self._set_grid_state(False)
        self._builder.connect_signals(self)
        self.show_all()

        self._activate_spinner()

        self._con.get_module('MAM').request_mam_preferences()

    def _mam_prefs_received(self, obj):
        if obj.conn.name != self.account:
            return
        self._disable_spinner()
        self._set_grid_state(True)

        self._default.set_active_id(obj.default)
        self._pref_store.clear()
        for item in obj.rules:
            self._pref_store.append(item)

    def _mam_prefs_saved(self, obj):
        if obj.conn.name != self.account:
            return

        self._disable_spinner()

        def on_ok(dialog):
            self.destroy()
        dialog = HigDialog(
            self, Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
            _('Success!'), _('Your Archiving Preferences have been saved!'),
            on_response_ok=on_ok, on_response_cancel=on_ok)
        dialog.popup()

    def _mam_prefs_error(self, obj=None):
        if obj and obj.conn.name != self.account:
            return

        self._disable_spinner()

        if not obj:
            msg = _('No response from the Server')
        else:
            msg = _('Error received: {}').format(obj.error_msg)

        dialog = HigDialog(
            self, Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
            _('Error!'), msg)
        dialog.popup()
        self._set_grid_state(True)

    def _set_grid_state(self, state):
        self._builder.get_object('preferences_grid').set_sensitive(state)

    def _jid_edited(self, renderer, path, new_text):
        iter_ = self._pref_store.get_iter(path)
        self._pref_store.set_value(iter_, 0, new_text)

    def _pref_toggled(self, renderer, path):
        iter_ = self._pref_store.get_iter(path)
        current_value = self._pref_store[iter_][1]
        self._pref_store.set_value(iter_, 1, not current_value)

    def _on_add(self, button):
        self._pref_store.append(['', False])

    def _on_remove(self, button):
        pref_view = self._builder.get_object('pref_view')
        mod, paths = pref_view.get_selection().get_selected_rows()
        for path in paths:
            iter_ = mod.get_iter(path)
            self._pref_store.remove(iter_)

    def _on_save(self, button):
        self._activate_spinner()
        self._set_grid_state(False)
        items = []
        default = self._default.get_active_id()
        for item in self._pref_store:
            items.append((item[0].lower(), item[1]))
        self._con.get_module('MAM').set_mam_preferences(items, default)

    def _activate_spinner(self):
        self._spinner.show()
        self._spinner.start()

    def _disable_spinner(self):
        self._spinner.hide()
        self._spinner.stop()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_destroy(self, widget):
        app.ged.remove_event_handler('mam-prefs-received', ged.GUI1,
                                     self._mam_prefs_received)
        app.ged.remove_event_handler('mam-prefs-saved', ged.GUI1,
                                     self._mam_prefs_saved)
        app.ged.remove_event_handler('mam-prefs-error', ged.GUI1,
                                     self._mam_prefs_error)
