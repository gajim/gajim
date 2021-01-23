
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app

from gajim.gui.chat_list import ChatList


class ChatListStack(Gtk.Stack):
    def __init__(self, ui, chat_stack):
        Gtk.Stack.__init__(self)
        self.get_style_context().add_class('chatlist-stack')

        self.set_vexpand(True)

        self._ui = ui
        self._chat_stack = chat_stack
        self._chat_lists = {}

        self.show_all()
        self._ui.start_chat_button.connect(
            'clicked', self._on_start_chat_clicked)
        self._ui.search_entry.connect(
            'search-changed', self._on_search_changed)

    def _on_start_chat_clicked(self, _button):
        app.app.activate_action('start-chat', GLib.Variant('s', ''))

    def _on_search_changed(self, search_entry):
        chat_list = self.get_visible_child()
        chat_list.set_filter_text(search_entry.get_text())

    def add_chat_list(self, workspace_id):
        chat_list = ChatList(workspace_id)
        chat_list.connect('row-selected', self._on_row_selected)

        self._chat_lists[workspace_id] = chat_list
        self.add_named(chat_list, workspace_id)
        return chat_list

    def _on_row_selected(self, _chat_list, row):
        if row is None:
            self._chat_stack.clear()
            return
        self._chat_stack.show_chat(row.account, row.jid)

    def show_chat_list(self, workspace_id):
        self.set_visible_child_name(workspace_id)

    def add_chat(self, workspace_id, *args):
        chat_list = self._chat_lists.get(workspace_id)
        if chat_list is None:
            chat_list = self.add_chat_list(workspace_id)
        chat_list.add_chat(*args)

    def select_chat(self, workspace_id, *args):
        self.show_chat_list(workspace_id)
        chat_list = self._chat_lists.get(workspace_id)
        chat_list.select_chat(*args)

    def store_open_chats(self, workspace_id):
        chat_list = self._chat_lists[workspace_id]
        open_chats = chat_list.get_open_chats()
        app.settings.set_workspace_setting(
            workspace_id, 'open_chats', open_chats)

    def remove_chat(self, workspace_id, account, jid):
        chat_list = self._chat_lists[workspace_id]
        chat_list.remove_chat(account, jid)
        self.store_open_chats(workspace_id)

        if self._find_chat(account, jid) is None:
            self._chat_stack.remove_chat(account, jid)

    def _find_chat(self, account, jid):
        for chat_list in self._chat_lists.values():
            if chat_list.contains_chat(account, jid):
                return chat_list
        return None
