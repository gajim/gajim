
from gi.repository import Gtk

from gajim.common import app
from gajim.gui.util import get_builder
from gajim.gui.chat_list_stack import ChatListStack
from gajim.gui.chat_stack import ChatStack
from gajim.gui.util import get_app_window


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Gajim')

        # Compatibility with ChatControl
        self.window = self
        app.window = self

        self._ui = get_builder('main.ui')

        self.add(self._ui.main_grid)

        self._chat_stack = ChatStack()
        self._chat_list_stack = ChatListStack(self._ui, self._chat_stack)

        self._ui.left_grid.add(self._chat_list_stack)
        self._ui.right_grid.add(self._chat_stack)
        self._ui.connect_signals(self)

        self._chat_list_stack.add_chat_list('default')

        self.show_all()

        self._load_chats()

    def get_widget(self, name):
        return getattr(self._ui, name)

    def redraw_tab(self, *args):
        pass

    def remove_tab(self, *args):
        pass

    def show_title(self, *args):
        pass

    def get_active_jid(self, *args):
        pass

    def add_chat(self, account, jid):
        self._chat_stack.add_chat(account, jid)
        self._chat_list_stack.add_chat('default', account, jid)
        self._chat_list_stack.select_chat('default', account, jid)

    def get_control(self, account, jid):
        return self._chat_stack.get_control(account, jid)

    def _load_chats(self):
        for account in app.settings.get_accounts():
            jids = app.settings.get_account_setting(
                account, 'opened_chat_controls')
            if not jids:
                continue

            for jid in jids.split(','):
                self.add_chat(account, jid)
