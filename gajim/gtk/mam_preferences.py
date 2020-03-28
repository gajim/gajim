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

from nbxmpp.util import is_error_result

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.util import get_builder
from gajim.gtk.util import EventHelper
from gajim.gtk.util import ensure_not_destroyed
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.dialogs import InformationDialog

log = logging.getLogger('gajim.gtk.mam_preferences')


class MamPreferences(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Archiving Preferences for %s') % account)

        self.connect('key-press-event', self._on_key_press)

        self.account = account
        self._con = app.connections[account]
        self._destroyed = False

        self._ui = get_builder('mam_preferences.ui')
        self.add(self._ui.get_object('mam_box'))

        self._spinner = Gtk.Spinner()
        self._ui.overlay.add_overlay(self._spinner)

        self._set_mam_box_state(False)
        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)
        self.show_all()

        self._activate_spinner()

        self._con.get_module('MAM').request_preferences(
            callback=self._mam_prefs_received)

    def _on_destroy(self, *args):
        self._destroyed = True

    @ensure_not_destroyed
    def _mam_prefs_received(self, result):
        if is_error_result(result):
            self._on_error(result.get_text())
            return

        self._disable_spinner()
        self._set_mam_box_state(True)

        self._ui.default_combo.set_active_id(result.default)
        self._ui.preferences_store.clear()
        for jid in result.always:
            self._ui.preferences_store.append((str(jid), 'Always'))

        for jid in result.never:
            self._ui.preferences_store.append((str(jid), 'Never'))

    @ensure_not_destroyed
    def _mam_prefs_saved(self, result):
        if is_error_result(result):
            self._on_error(result.get_text())
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

    def _on_error(self, error):
        self._disable_spinner()

        InformationDialog(_('Archiving Preferences Error'),
                          _('Error received: {}').format(error))

        self._set_mam_box_state(True)

    def _set_mam_box_state(self, state):
        self._ui.mam_box.set_sensitive(state)

    def _jid_edited(self, _renderer, path, new_text):
        iter_ = self._ui.preferences_store.get_iter(path)
        self._ui.preferences_store.set_value(iter_, 0, new_text)

    def _pref_toggled(self, _renderer, path):
        iter_ = self._ui.preferences_store.get_iter(path)
        current_value = self._ui.preferences_store[iter_][1]
        self._ui.preferences_store.set_value(iter_, 1, not current_value)

    def _on_add(self, _button):
        self._ui.preferences_store.append(['', False])

    def _on_remove(self, _button):
        mod, paths = self._ui.pref_view.get_selection().get_selected_rows()
        for path in paths:
            iter_ = mod.get_iter(path)
            self._ui.preferences_store.remove(iter_)

    def _on_save(self, _button):
        self._activate_spinner()
        self._set_mam_box_state(False)
        always = []
        never = []
        default = self._ui.default_combo.get_active_id()
        for item in self._ui.preferences_store:
            jid, type_ = item
            if type_ == 'Always':
                always.append(jid)
            else:
                never.append(jid)
        self._con.get_module('MAM').set_preferences(
            default, always, never, callback=self._mam_prefs_saved)

    def _activate_spinner(self):
        self._spinner.show()
        self._spinner.start()

    def _disable_spinner(self):
        self._spinner.hide()
        self._spinner.stop()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
