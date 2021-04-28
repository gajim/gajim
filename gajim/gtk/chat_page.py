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
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import GObject

from gajim.common import app
from gajim.common.i18n import _

from .util import get_builder
from .chat_list_stack import ChatListStack
from .chat_stack import ChatStack
from .search_view import SearchView


WORKSPACE_MENU_DICT = {
    'edit': _('Edit…'),
    'remove': _('Remove'),
}


class ChatPage(Gtk.Box):

    __gsignals__ = {
        'chat-selected': (GObject.SignalFlags.RUN_LAST,
                          None,
                          (str, str, str)),
    }

    def __init__(self):
        Gtk.Box.__init__(self)
        self._ui = get_builder('chat_paned.ui')
        self.add(self._ui.paned)

        self._chat_stack = ChatStack()
        self._ui.right_grid_overlay.add(self._chat_stack)

        self._search_view = SearchView()
        self._search_view.connect('hide-search', self._on_search_hide)

        self._search_revealer = Gtk.Revealer()
        self._search_revealer.set_reveal_child(True)
        self._search_revealer.set_halign(Gtk.Align.END)
        self._search_revealer.set_no_show_all(True)
        self._search_revealer.add(self._search_view)
        self._ui.right_grid_overlay.add_overlay(self._search_revealer)

        self._chat_list_stack = ChatListStack(self._ui.search_entry)
        self._chat_list_stack.connect('chat-selected', self._on_chat_selected)
        self._chat_list_stack.connect('chat-unselected',
                                      self._on_chat_unselected)
        self._chat_list_stack.connect('chat-removed', self._on_chat_removed)
        self._chat_list_stack.connect('notify::visible-child-name',
                                      self._on_chat_list_changed)
        self._ui.chat_list_scrolled.add(self._chat_list_stack)

        self._ui.start_chat_button.connect('clicked',
                                           self._on_start_chat_clicked)

        self._ui.paned.set_position(app.settings.get('chat_handle_position'))
        self._ui.paned.connect('button-release-event', self._on_button_release)

        workspace_menu = Gio.Menu()
        for action, label in WORKSPACE_MENU_DICT.items():
            workspace_menu.append(label, f'win.{action.lower()}-workspace')

        self._ui.workspace_menu_button.set_menu_model(workspace_menu)

        self._startup_finished = False

        self._add_actions()

        self.show_all()

    def _add_actions(self):
        actions = [
            ('remove-chat', 'as', self._remove_chat),
            ('search-history', None, self._on_search_history),
        ]

        for action in actions:
            action_name, variant, func = action
            if variant is not None:
                variant = GLib.VariantType.new(variant)
            act = Gio.SimpleAction.new(action_name, variant)
            act.connect('activate', func)
            app.window.add_action(act)

    def set_startup_finished(self):
        self._startup_finished = True

    def get_chat_list_stack(self):
        return self._chat_list_stack

    def get_chat_stack(self):
        return self._chat_stack

    @staticmethod
    def _on_start_chat_clicked(_button):
        app.app.activate_action('start-chat', GLib.Variant('s', ''))

    @staticmethod
    def _on_button_release(paned, event):
        if event.window != paned.get_handle_window():
            return
        position = paned.get_position()
        app.settings.set('chat_handle_position', position)

    def _on_chat_selected(self, _chat_list_stack, workspace_id, account, jid):
        self._chat_stack.show_chat(account, jid)
        self._search_view.set_context(account, jid)

        self._ui.workspace_label.set_text(
            app.settings.get_workspace_setting(workspace_id, 'name'))

        self.emit('chat-selected', workspace_id, account, jid)

    def _on_chat_unselected(self, _chat_list_stack):
        self._chat_stack.clear()

    def _on_search_history(self, _action, _param):
        control = self.get_active_control()
        if control is not None:
            self._search_view.set_context(control.account, control.contact.jid)
        self._search_view.clear()
        self._search_revealer.show()
        self._search_view.set_focus()

    def _on_search_hide(self, *args):
        self._search_revealer.hide()

    def _on_chat_list_changed(self, *args):
        self._ui.search_entry.set_text('')

    def process_event(self, event):
        self._chat_stack.process_event(event)
        self._chat_list_stack.process_event(event)

    def add_chat_list(self, workspace_id):
        self._chat_list_stack.add_chat_list(workspace_id)

    def show_workspace_chats(self, workspace_id):
        self._chat_list_stack.show_chat_list(workspace_id)

    def update_workspace(self, workspace_id):
        name = app.settings.get_workspace_setting(workspace_id, 'name')
        self._ui.workspace_label.set_text(name)

    def remove_chat_list(self, workspace_id):
        self._chat_list_stack.remove_chat_list(workspace_id)

    def chat_exists(self, account, jid):
        return self._chat_list_stack.contains_chat(account, jid)

    def chat_exists_for_workspace(self, workspace_id, account, jid):
        return self._chat_list_stack.contains_chat(
            account, jid, workspace_id=workspace_id)

    def add_chat_for_workspace(self,
                               workspace_id,
                               account,
                               jid,
                               type_,
                               pinned=False,
                               select=False):

        if self.chat_exists(account, jid):
            if select:
                self._chat_list_stack.select_chat(account, jid)
            return

        if type_ == 'groupchat':
            self._chat_stack.add_group_chat(account, jid)
        elif type_ == 'pm':
            if not self._startup_finished:
                # TODO: Currently we cant load private chats at start
                # because the Contacts dont exist yet
                return
            self._chat_stack.add_private_chat(account, jid)
        else:
            self._chat_stack.add_chat(account, jid)
        self._chat_list_stack.add_chat(workspace_id, account, jid, type_,
                                       pinned)

        if self._startup_finished:
            if select:
                self._chat_list_stack.select_chat(account, jid)
            self._chat_list_stack.store_open_chats(workspace_id)

    def load_workspace_chats(self, workspace_id):
        open_chats = app.settings.get_workspace_setting(workspace_id,
                                                        'open_chats')

        active_accounts = app.settings.get_active_accounts()
        for account, jid, type_, pinned in open_chats:
            if account not in active_accounts:
                continue

            self.add_chat_for_workspace(workspace_id,
                                        account,
                                        jid,
                                        type_,
                                        pinned=pinned)

    def is_chat_active(self, account, jid):
        return self._chat_list_stack.is_chat_active(account, jid)

    def _remove_chat(self, _action, param):
        account, jid = param.unpack()
        self.remove_chat(account, jid)

    def remove_chat(self, account, jid):
        for workspace_id in app.settings.get_workspaces():
            if self.chat_exists_for_workspace(workspace_id, account, jid):
                self._chat_list_stack.remove_chat(workspace_id, account, jid)
                return

    def _on_chat_removed(self, _chat_list, account, jid, type_):
        self._chat_stack.remove_chat(account, jid)
        if type_ == 'groupchat':
            client = app.get_client(account)
            client.get_module('MUC').leave(jid)

    def get_control(self, account, jid):
        return self._chat_stack.get_control(account, jid)

    def get_active_control(self):
        chat = self._chat_list_stack.get_selected_chat()
        if chat is None:
            return None
        return self.get_control(chat.account, chat.jid)

    def get_controls(self, account=None):
        return self._chat_stack.get_controls(account)

    def hide_search(self):
        if self._search_revealer.get_reveal_child():
            self._search_revealer.hide()
