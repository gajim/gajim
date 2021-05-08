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

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common.i18n import _


class ChatFilter(Gtk.Box):

    __gsignals__ = {
        'filter-changed': (GObject.SignalFlags.RUN_LAST,
                           None,
                           (str, )),
    }

    def __init__(self):
        Gtk.Box.__init__(self)
        self.set_halign(Gtk.Align.CENTER)

        toolbar = Gtk.Toolbar()

        all_button = Gtk.RadioToolButton.new_from_widget(None)
        all_button.set_label(_('All'))
        all_button.set_name('all')
        all_button.connect('clicked', self._on_button_clicked)
        toolbar.insert(all_button, 1)

        chats_button = Gtk.RadioToolButton.new_from_widget(all_button)
        chats_button.set_label(_('Chats'))
        chats_button.set_name('chats')
        chats_button.connect('clicked', self._on_button_clicked)
        toolbar.insert(chats_button, 2)

        group_chats_button = Gtk.RadioToolButton.new_from_widget(all_button)
        group_chats_button.set_label(_('Group Chats'))
        group_chats_button.set_name('group_chats')
        group_chats_button.connect('clicked', self._on_button_clicked)
        toolbar.insert(group_chats_button, 3)

        self.add(toolbar)
        self.show_all()

    def _on_button_clicked(self, button):
        if button.get_active():
            self.emit('filter-changed', button.get_name())
