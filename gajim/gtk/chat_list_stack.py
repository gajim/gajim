
from gi.repository import Gtk

from gajim.gui.chat_list import ChatList


class ChatListStack(Gtk.Stack):
    def __init__(self, ui, chat_stack):
        Gtk.Stack.__init__(self)

        self.set_vexpand(True)

        self._ui = ui
        self._chat_stack = chat_stack
        self._chat_lists = {}

        self.show_all()
        self._ui.search_entry.connect('search-changed', self._on_search_changed)

    def _on_search_changed(self, search_entry):
        chat_list = self.get_visible_child()
        chat_list.set_filter_text(search_entry.get_text())

    def add_chat_list(self, name):
        chat_list = ChatList(self._ui, self._chat_stack)
        self._chat_lists[name] = chat_list
        self.add_named(chat_list, name)

    def show_chat_list(self, name):
        self.set_visible_child_name(name)

    def add_chat(self, name, *args):
        chat_list = self._chat_lists.get(name)
        chat_list.add_chat(*args)

    def select_chat(self, name, *args):
        self.show_chat_list(name)
        chat_list = self._chat_lists.get(name)
        chat_list.select_chat(*args)
