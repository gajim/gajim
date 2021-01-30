
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gio

from gajim.common import app
from gajim.gui.util import get_builder
from gajim.gui.util import load_icon
from gajim.gui.chat_list_stack import ChatListStack
from gajim.gui.chat_stack import ChatStack
from gajim.gui.account_side_bar import AccountSideBar
from gajim.gui.workspace_side_bar import WorkspaceSideBar

from .util import open_window


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Gajim')
        self.set_default_size(800, 500)

        # Compatibility with ChatControl
        self.window = self
        app.window = self

        self._active_workspace = None

        self._startup_finished = False

        self._ui = get_builder('main.ui')

        self.add(self._ui.main_grid)

        self._chat_stack = ChatStack()
        self._chat_list_stack = ChatListStack(self._ui, self._chat_stack)
        self._ui.chat_list_scrolled.add(self._chat_list_stack)

        self._account_side_bar = AccountSideBar()
        self._workspace_side_bar = WorkspaceSideBar()

        surface = load_icon('org.gajim.Gajim', self, 40)
        self._ui.app_image.set_from_surface(surface)
        self._ui.workspace_scrolled.add(self._workspace_side_bar)

        self._ui.account_box.add(self._account_side_bar)

        self._ui.right_grid.add(self._chat_stack)

        self._ui.edit_workspace_button.connect(
            'clicked', self._on_edit_workspace_clicked)
        self._ui.start_chat_button.connect(
            'clicked', self._on_start_chat_clicked)
        self._ui.connect_signals(self)

        self.show_all()

        self._load_chats()
        self._add_actions()

    def _add_actions(self):
        actions = [
            ('add-workspace', 's', self.add_workspace),
            ('remove-workspace', 's', self.remove_workspace),
            ('activate-workspace', 's', self.activate_workspace),
            ('add-chat', 'as', self.add_chat),
            ('remove-chat', 'as', self.remove_chat),
        ]

        for action in actions:
            action_name, variant, func = action
            variant = GLib.VariantType.new(variant)
            act = Gio.SimpleAction.new(action_name, variant)
            act.connect('activate', func)
            self.add_action(act)

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

    def get_workspace_bar(self):
        return self._workspace_side_bar

    def get_active_workspace(self):
        return self._workspace_side_bar.get_active_workspace()

    def add_workspace(self, _action, param):
        workspace_id = param.get_string()
        self._workspace_side_bar.add_workspace(workspace_id)
        self._chat_list_stack.add_chat_list(workspace_id)
        self._workspace_side_bar.activate_workspace(workspace_id)
        self._chat_list_stack.show_chat_list(workspace_id)

    def remove_workspace(self, _action, param):
        workspace_id = param.get_string()

        was_active = self.get_active_workspace() == workspace_id

        success = self._workspace_side_bar.remove_workspace(workspace_id)
        if not success:
            return

        if was_active:
            new_active_id = self._workspace_side_bar.get_first_workspace()
            self._workspace_side_bar.activate_workspace(new_active_id)
            self._chat_list_stack.show_chat_list(new_active_id)

        self._chat_list_stack.remove_chat_list(workspace_id)
        app.settings.remove_workspace(workspace_id)


    def activate_workspace(self, _action, param):
        workspace_id = param.get_string()
        self._workspace_side_bar.activate_workspace(workspace_id)
        self._chat_list_stack.show_chat_list(workspace_id)

    def add_chat(self, _action, param):
        account, jid, type_ = param.unpack()
        workspace_id = self._workspace_side_bar.get_active_workspace()
        self.add_chat_for_workspace(workspace_id, account, jid, type_)

    def add_chat_for_workspace(self, workspace_id, account, jid, type_):
        self._chat_stack.add_chat(account, jid)
        self._chat_list_stack.add_chat(workspace_id, account, jid, type_)

        if self._startup_finished:
            self._chat_list_stack.select_chat(workspace_id, account, jid)
            self._chat_list_stack.store_open_chats(workspace_id)

    def remove_chat(self, _action, param):
        workspace_id, account, jid = param.unpack()
        self._chat_list_stack.remove_chat(workspace_id, account, jid)

    def get_control(self, account, jid):
        return self._chat_stack.get_control(account, jid)

    def _load_chats(self):
        for workspace_id in app.settings.get_workspaces():
            self._workspace_side_bar.add_workspace(workspace_id)
            self._chat_list_stack.add_chat_list(workspace_id)
            open_chats = app.settings.get_workspace_setting(workspace_id,
                                                            'open_chats')
            for account, jid, type_ in open_chats:
                if account not in app.connections:
                    continue
                self.add_chat_for_workspace(workspace_id, account, jid, type_)

        for workspace_id in app.settings.get_workspaces():
            self._workspace_side_bar.activate_workspace(workspace_id)
            self._chat_list_stack.show_chat_list(workspace_id)
            break

        self._startup_finished = True

    def _on_start_chat_clicked(self, _button):
        app.app.activate_action('start-chat', GLib.Variant('s', ''))

    def _on_edit_workspace_clicked(self, _button):
        open_window('WorkspaceDialog',
                    workspace_id=self.get_active_workspace())
