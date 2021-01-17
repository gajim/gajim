
from collections import defaultdict

from gi.repository import Gtk

from gajim.common import app
from gajim.chat_control import ChatControl


class ChatStack(Gtk.Stack):
    def __init__(self):
        Gtk.Stack.__init__(self)

        self.set_vexpand(True)
        self.set_hexpand(True)

        self.add_named(Gtk.Box(), 'empty')

        self.show_all()
        self._controls = defaultdict(dict)

    def get_control(self, account, jid):
        try:
            return self._controls[account][jid]
        except KeyError:
            return None

    def add_chat(self, account, jid):
        mw = self.get_toplevel()
        contact = app.contacts.create_contact(jid, account)
        chat_control = ChatControl(mw, contact, account, None, None)
        self._controls[account][jid] = chat_control
        self.add_named(chat_control.widget, f'{account}:{jid}')
        chat_control.widget.show_all()

    def remove_chat(self, account, jid):
        control = self._controls[account].pop(jid)
        control.shutdown()
        self.remove(control)

    def show_chat(self, account, jid):
        self.set_visible_child_name(f'{account}:{jid}')

    def clear(self):
        self.set_visible_child_name('empty')
