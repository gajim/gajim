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

from nbxmpp.errors import StanzaError
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import to_user_string

from .util import get_builder
from .dialogs import HigDialog

log = logging.getLogger('gajim.gui.blocking_list')


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

        self._ui = get_builder('blocking_list.ui')
        self.add(self._ui.blocking_grid)

        self._spinner = Gtk.Spinner()
        self._ui.overlay.add_overlay(self._spinner)

        self._set_grid_state(False)
        self._ui.connect_signals(self)
        self.show_all()

        self._activate_spinner()

        self._con.get_module('Blocking').request_blocking_list(
            callback=self._on_blocking_list_received)

    def _show_error(self, error):
        dialog = HigDialog(
            self, Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
            _('Error!'),
            GLib.markup_escape_text(error))
        dialog.popup()

    def _on_blocking_list_received(self, task):
        try:
            blocking_list = task.finish()
        except StanzaError as error:
            self._set_grid_state(False)
            self._show_error(to_user_string(error))
            return

        self._prev_blocked_jids = set(blocking_list)
        self._ui.blocking_store.clear()

        for jid in blocking_list:
            self._ui.blocking_store.append((str(jid),))

        self._set_grid_state(True)
        self._disable_spinner()

    def _on_save_result(self, task):
        try:
            _successful = task.finish()
        except StanzaError as error:
            self._show_error(to_user_string(error))
            self._disable_spinner()
            self._set_grid_state(True)
            return

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
        block_jids = blocked_jids - self._prev_blocked_jids

        self._con.get_module('Blocking').update_blocking_list(
            block_jids, unblock_jids, callback=self._on_save_result)

    def _activate_spinner(self):
        self._spinner.show()
        self._spinner.start()

    def _disable_spinner(self):
        self._spinner.hide()
        self._spinner.stop()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
