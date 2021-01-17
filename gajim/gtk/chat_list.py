
from gi.repository import Gtk



class ChatList(Gtk.ListBox):
    def __init__(self, ui, chat_stack):
        Gtk.ListBox.__init__(self)

        self._ui = ui
        self._chat_stack = chat_stack
        self._chats = {}
        self._current_filter_text = ''

        self.show_all()

        self.set_filter_func(self._filter_func)
        self.connect('row-selected', self._on_row_selected)

    def _filter_func(self, row):
        if not self._current_filter_text:
            return True
        return self._current_filter_text in row.jid

    def set_filter_text(self, text):
        self._current_filter_text = text
        self.invalidate_filter()

    def add_chat(self, account, jid):
        row = ChatRow(account, jid)
        self._chats[(account, jid)] = row
        self.add(row)

    def select_chat(self, account, jid):
        row = self._chats[(account, jid)]
        self.select_row(row)

    def remove_chat(self, account, jid):
        row = self._chats.pop((account, jid))
        self.remove(row)
        row.destroy()

    def _on_row_selected(self, _listbox, row):
        if row is None:
            self._chat_stack.clear()
            return
        self._chat_stack.show_chat(row.account, row.jid)

    def get_open_chats(self):
        return list(self._chats.keys())


class ChatRow(Gtk.ListBoxRow):
    def __init__(self, account, jid):
        Gtk.ListBoxRow.__init__(self)

        self.account = account
        self.jid = jid

        label = Gtk.Label(jid)
        self.add(label)
        self.show_all()
