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
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.dialogs import InformationDialog

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

        self._ui = get_builder('mam_preferences.ui')
        self.add(self._ui.get_object('mam_box'))

        self._spinner = Gtk.Spinner()
        self._ui.overlay.add_overlay(self._spinner)

        app.ged.register_event_handler('mam-prefs-received', ged.GUI1,
                                       self._mam_prefs_received)
        app.ged.register_event_handler('mam-prefs-saved', ged.GUI1,
                                       self._mam_prefs_saved)
        app.ged.register_event_handler('mam-prefs-error', ged.GUI1,
                                       self._mam_prefs_error)

        self._set_mam_box_state(False)
        self._ui.connect_signals(self)
        self.show_all()

        self._activate_spinner()

        self._con.get_module('MAM').request_mam_preferences()

    def _mam_prefs_received(self, obj):
        if obj.conn.name != self.account:
            return
        self._disable_spinner()
        self._set_mam_box_state(True)

        self._ui.default_combo.set_active_id(obj.default)
        self._ui.preferences_store.clear()
        for item in obj.rules:
            self._ui.preferences_store.append(item)

    def _mam_prefs_saved(self, obj):
        if obj.conn.name != self.account:
            return

        self._disable_spinner()

        def _on_ok():
            self.destroy()

        NewConfirmationDialog(
            _('Archiving Preferences'),
            _('Archiving Preferences Saved'),
            _('Your archiving preferences have successfully been saved.'),
            [DialogButton.make('OK',
                               callback=_on_ok)]).show()

    def _mam_prefs_error(self, obj=None):
        if obj and obj.conn.name != self.account:
            return

        self._disable_spinner()

        if not obj:
            msg = _('No response from the Server')
        else:
            msg = _('Error received: {}').format(obj.error_msg)

        InformationDialog(_('Archiving Preferences Error'), msg)

        self._set_mam_box_state(True)

    def _set_mam_box_state(self, state):
        self._ui.mam_box.set_sensitive(state)

    def _jid_edited(self, renderer, path, new_text):
        iter_ = self._ui.preferences_store.get_iter(path)
        self._ui.preferences_store.set_value(iter_, 0, new_text)

    def _pref_toggled(self, renderer, path):
        iter_ = self._ui.preferences_store.get_iter(path)
        current_value = self._ui.preferences_store[iter_][1]
        self._ui.preferences_store.set_value(iter_, 1, not current_value)

    def _on_add(self, button):
        self._ui.preferences_store.append(['', False])

    def _on_remove(self, button):
        mod, paths = self._ui.pref_view.get_selection().get_selected_rows()
        for path in paths:
            iter_ = mod.get_iter(path)
            self._ui.preferences_store.remove(iter_)

    def _on_save(self, button):
        self._activate_spinner()
        self._set_mam_box_state(False)
        items = []
        default = self._ui.default_combo.get_active_id()
        for item in self._ui.preferences_store:
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
