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
from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app

from gajim.gui.chat_list import ChatList


HANDLED_EVENTS = [
    'message-received',
    'mam-message-received',
    'gc-message-received',
    'presence-received',
    'message-sent',
    'chatstate-received',
]


class ChatListStack(Gtk.Stack):

    __gsignals__ = {
        'unread-count-changed': (GObject.SignalFlags.RUN_LAST,
                                 None,
                                 (str, int)),
        'chat-selected': (GObject.SignalFlags.RUN_LAST,
                          None,
                          (str, str, str)),
        'chat-unselected': (GObject.SignalFlags.RUN_LAST,
                            None,
                            ()),
        'chat-removed': (GObject.SignalFlags.RUN_LAST,
                         None,
                         (str, str, str)),
    }

    def __init__(self, chat_filter, search_entry):
        Gtk.Stack.__init__(self)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_vhomogeneous(False)

        self._chat_lists = {}

        self._last_visible_child_name = 'default'

        self.add_named(Gtk.Box(), 'default')

        self.connect('notify::visible-child-name', self._on_visible_child_name)
        search_entry.connect('search-changed', self._on_search_changed)
        chat_filter.connect('filter-changed', self._on_filter_changed)
        app.window.connect('notify::is-active', self._on_window_active)

        self._add_actions()
        self.show_all()

    def _add_actions(self):
        actions = [
            ('toggle-chat-pinned', 'as', self._toggle_chat_pinned),
            ('move-chat-to-workspace', 'as', self._move_chat_to_workspace),
        ]

        for action in actions:
            action_name, variant, func = action
            if variant is not None:
                variant = GLib.VariantType.new(variant)
            act = Gio.SimpleAction.new(action_name, variant)
            act.connect('activate', func)
            app.window.add_action(act)

    def _on_window_active(self, window, _param):
        is_active = window.get_property('is-active')
        if is_active:
            chat = self.get_selected_chat()
            if chat is not None:
                chat.reset_unread()

    def _on_visible_child_name(self, _stack, _param):
        if self._last_visible_child_name == self.get_visible_child_name():
            return

        if self._last_visible_child_name != 'default':
            child = self.get_child_by_name(self._last_visible_child_name)
            child.set_filter_text('')
        self._last_visible_child_name = self.get_visible_child_name()

    def get_chatlist(self, workspace_id):
        return self._chat_lists[workspace_id]

    def get_selected_chat(self):
        chat_list = self.get_current_chat_list()
        if chat_list is None:
            return None
        return chat_list.get_selected_chat()

    def get_current_chat_list(self):
        workspace_id = self.get_visible_child_name()
        if workspace_id == 'empty':
            return None

        return self._chat_lists[workspace_id]

    def is_chat_active(self, account, jid):
        chat = self.get_selected_chat()
        if chat is None:
            return False
        if chat.account != account or chat.jid != jid:
            return False
        return chat.is_active

    def _on_filter_changed(self, _filter, name):
        chat_list = self.get_visible_child()
        chat_list.set_filter(name)

    def _on_search_changed(self, search_entry):
        chat_list = self.get_visible_child()
        chat_list.set_filter_text(search_entry.get_text())

    def add_chat_list(self, workspace_id):
        chat_list = ChatList(workspace_id)
        chat_list.connect('row-selected', self._on_row_selected)

        self._chat_lists[workspace_id] = chat_list
        self.add_named(chat_list, workspace_id)
        return chat_list

    def remove_chat_list(self, workspace_id):
        chat_list = self._chat_lists[workspace_id]
        self.remove(chat_list)
        for account, jid, _, _ in chat_list.get_open_chats():
            self.remove_chat(workspace_id, account, jid)

        self._chat_lists.pop(workspace_id)
        chat_list.destroy()

    def _on_row_selected(self, _chat_list, row):
        if row is None:
            self.emit('chat-unselected')
            return

        if row.is_active:
            row.reset_unread()
        self.emit('chat-selected', row.workspace_id, row.account, row.jid)

    def show_chat_list(self, workspace_id):
        current_workspace_id = self.get_visible_child_name()
        if current_workspace_id == workspace_id:
            return

        if current_workspace_id != 'default':
            self._chat_lists[current_workspace_id].unselect_all()

        self.set_visible_child_name(workspace_id)

    def add_chat(self, workspace_id, account, jid, type_, pinned=False):
        chat_list = self._chat_lists.get(workspace_id)
        if chat_list is None:
            chat_list = self.add_chat_list(workspace_id)
        chat_list.add_chat(account, jid, type_, pinned)

    def select_chat(self, account, jid):
        chat_list = self._find_chat(account, jid)
        if chat_list is None:
            return

        self.show_chat_list(chat_list.workspace_id)
        chat_list.select_chat(account, jid)

    def store_open_chats(self, workspace_id):
        chat_list = self._chat_lists[workspace_id]
        open_chats = chat_list.get_open_chats()
        app.settings.set_workspace_setting(
            workspace_id, 'open_chats', open_chats)

    def _toggle_chat_pinned(self, _action, param):
        workspace_id, account, jid = param.unpack()
        chat_list = self._chat_lists[workspace_id]
        chat_list.toggle_chat_pinned(account, jid)
        self.store_open_chats(workspace_id)

    def _move_chat_to_workspace(self, _action, param):
        new_workspace_id, account, jid = param.unpack()

        current_chatlist = self.get_visible_child()
        type_ = current_chatlist.get_chat_type(account, jid)
        current_chatlist.remove_chat(account, jid)

        new_chatlist = self.get_chatlist(new_workspace_id)
        new_chatlist.add_chat(account, jid, type_)
        self.store_open_chats(current_chatlist.workspace_id)
        self.store_open_chats(new_workspace_id)

    def remove_chat(self, workspace_id, account, jid):
        chat_list = self._chat_lists[workspace_id]
        type_ = chat_list.get_chat_type(account, jid)
        chat_list.remove_chat(account, jid)
        self.store_open_chats(workspace_id)
        self.emit('chat-removed', account, jid, type_)

    def remove_chats_for_account(self, account):
        for workspace_id, chat_list in self._chat_lists.items():
            chat_list.remove_chats_for_account(account)
            self.store_open_chats(workspace_id)

    def _find_chat(self, account, jid):
        for chat_list in self._chat_lists.values():
            if chat_list.contains_chat(account, jid):
                return chat_list
        return None

    def contains_chat(self, account, jid, workspace_id=None):
        if workspace_id is None:
            for chat_list in self._chat_lists.values():
                if chat_list.contains_chat(account, jid):
                    return True
            return False

        chat_list = self._chat_lists[workspace_id]
        return chat_list.contains_chat(account, jid)

    def get_total_unread_count(self):
        count = 0
        for chat_list in self._chat_lists.values():
            count += chat_list.get_unread_count()
        return count

    def process_event(self, event):
        if event.name not in HANDLED_EVENTS:
            return

        chat_list = self._find_chat(event.account, event.jid)
        if chat_list is None:
            return
        chat_list.process_event(event)
