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

from nbxmpp.util import is_error_result
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import to_user_string

from gajim.gtk.util import get_builder
from gajim.gtk.dialogs import HigDialog

log = logging.getLogger('gajim.gtk.blocking_list')


class BlockingList(Gtk.ApplicationWindow):
    def __init__(self, account):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Blocking List for %s') % account)

        self.connect_after('key-press-event', self._on_key_press)

        self.account = account
        self._con = app.connections[account]
        self._prev_blocked_jids = set()
        self._await_results = 2
        self._received_errors = False

        self._ui = get_builder('blocking_list.ui')
        self.add(self._ui.blocking_grid)

        self._spinner = Gtk.Spinner()
        self._ui.overlay.add_overlay(self._spinner)

        self._set_grid_state(False)
        self._ui.connect_signals(self)
        self.show_all()

        self._activate_spinner()

        self._con.get_module('Blocking').get_blocking_list(
            callback=self._on_blocking_list_received)

    def _reset_after_error(self):
        self._received_errors = False
        self._await_results = 2
        self._disable_spinner()
        self._set_grid_state(True)

    def _show_error(self, error):
        dialog = HigDialog(
            self, Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
            _('Error!'),
            GLib.markup_escape_text(error))
        dialog.popup()

    def _on_blocking_list_received(self, result):
        is_error = is_error_result(result)
        self._disable_spinner()
        self._set_grid_state(not is_error)

        if is_error:
            self._show_error(to_user_string(result))

        else:
            self._prev_blocked_jids = set(result.blocking_list)
            self._ui.blocking_store.clear()
            for item in result.blocking_list:
                self._ui.blocking_store.append((item,))

    def _on_save_result(self, result):
        self._await_results -= 1
        if is_error_result(result) and not self._received_errors:
            self._show_error(to_user_string(result))
            self._received_errors = True

        if not self._await_results:
            if self._received_errors:
                self._reset_after_error()
            else:
                self.destroy()

    def _set_grid_state(self, state):
        self._ui.blocking_grid.set_sensitive(state)

    def _jid_edited(self, _renderer, path, new_text):
        iter_ = self._ui.blocking_store.get_iter(path)
        self._ui.blocking_store.set_value(iter_, 0, new_text)

    def _on_add(self, _button):
        self._ui.blocking_store.append([''])

    def _on_remove(self, _button):
        mod, paths = self._ui.block_view.get_selection().get_selected_rows()
        for path in paths:
            iter_ = mod.get_iter(path)
            self._ui.blocking_store.remove(iter_)

    def _on_save(self, _button):
        self._activate_spinner()
        self._set_grid_state(False)

        blocked_jids = set()
        for item in self._ui.blocking_store:
            blocked_jids.add(item[0].lower())

        unblock_jids = self._prev_blocked_jids - blocked_jids
        if unblock_jids:
            self._con.get_module('Blocking').unblock(
                unblock_jids, callback=self._on_save_result)
        else:
            self._await_results -= 1

        block_jids = blocked_jids - self._prev_blocked_jids
        if block_jids:
            self._con.get_module('Blocking').block(
                block_jids, callback=self._on_save_result)
        else:
            self._await_results -= 1

        if not self._await_results:
            # No changes
            self.destroy()

    def _activate_spinner(self):
        self._spinner.show()
        self._spinner.start()

    def _disable_spinner(self):
        self._spinner.hide()
        self._spinner.stop()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
