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

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

from .groupchat_info import GroupChatInfoScrolled
from .sidebar_switcher import SideBarSwitcher


class GroupchatDetails(Gtk.ApplicationWindow):
    def __init__(self, contact: GroupchatContact) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(-1, 600)
        self.set_title(_('Groupchat Details'))

        self.account = contact.account
        self._contact = contact

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._stack = Gtk.Stack()
        self._side_bar_switcher = SideBarSwitcher()

        main_box.add(self._side_bar_switcher)
        main_box.add(self._stack)

        self._add_groupchat_info()

        self._side_bar_switcher.set_stack(self._stack)

        self.add(main_box)

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _add_groupchat_info(self) -> None:
        groupchat_info = GroupChatInfoScrolled(self._contact.account, width=600)
        groupchat_info.set_halign(Gtk.Align.FILL)
        disco_info = self._contact.get_disco()
        assert disco_info is not None
        groupchat_info.set_from_disco_info(disco_info)
        groupchat_info.set_subject(self._contact.subject)

        self._stack.add_titled(groupchat_info, 'info', _('Information'))

    def _on_key_press(self,
                      _widget: GroupchatDetails,
                      event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_destroy(self, _widget: GroupchatDetails) -> None:
        app.check_finalize(self)
