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
from gi.repository import GObject

from gajim.gui.builder import get_builder


class GroupchatState(Gtk.Box):

    __gsignals__ = {
        'join-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            ()),
        'abort-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            ()),
    }

    def __init__(self):
        Gtk.Box.__init__(self)

        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)

        self._ui = get_builder('groupchat_state.ui')
        self._ui.connect_signals(self)
        self.add(self._ui.groupchat_state)
        self.show_all()

    def set_joining(self):
        self._ui.groupchat_state.set_visible_child_name('joining')

    def set_joined(self):
        self.hide()
        self.set_no_show_all(True)

    def set_not_joined(self):
        self._ui.groupchat_state.set_visible_child_name('not-joining')
        self.show()

    def set_fetching(self):
        self._ui.groupchat_state.set_visible_child_name('fetching')

    def _on_join_clicked(self, _button: Gtk.Button) -> None:
        self.emit('join-clicked')

    def _on_abort_clicked(self, _button: Gtk.Button) -> None:
        self.emit('abort-clicked')
