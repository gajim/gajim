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

from gajim.common import app

from .chat_page import ChatPage
from .account_page import AccountPage


class MainStack(Gtk.Stack):
    def __init__(self):
        Gtk.Stack.__init__(self)

        self._chat_page = ChatPage()
        self._chat_page.connect('chat-selected', self._on_chat_selected)
        self.add_named(self._chat_page, 'chats')

        for account in list(app.connections.keys()):
            account_page = AccountPage(account)
            self.add_named(account_page, account)

    def show_chats(self, workspace_id):
        self._chat_page.show_workspace_chats(workspace_id)
        self.set_visible_child_name('chats')

    def show_account(self, account):
        self.set_visible_child_name(account)

    def get_account_page(self, account):
        return self.get_child_by_name(account)

    def get_chat_page(self):
        return self.get_child_by_name('chats')

    def process_event(self, event):
        for page in self.get_children():
            page.process_event(event)

    def _on_chat_selected(self, *args):
        self.set_visible_child_name('chats')
