import logging

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.gui.util import get_builder
from gajim.gui.util import load_icon
from gajim.gui.account_page import AccountPage
from gajim.gui.chat_list_stack import ChatListStack
from gajim.gui.chat_stack import ChatStack
from gajim.gui.account_side_bar import AccountSideBar
from gajim.gui.workspace_side_bar import WorkspaceSideBar

from gajim.common.helpers import ask_for_status_message
from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationDialog

from gajim.common.nec import EventHelper

from .util import open_window


log = logging.getLogger('gajim.gui.main')

WORKSPACE_MENU_DICT = {
    'edit': _('Edit…'),
    'remove': _('Remove'),
}


class MainWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
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
        self._chat_list_stack = ChatListStack(self, self._ui, self._chat_stack)
        self._ui.chat_list_scrolled.add(self._chat_list_stack)

        self._account_side_bar = AccountSideBar()
        self._workspace_side_bar = WorkspaceSideBar(self._chat_list_stack)

        surface = load_icon('org.gajim.Gajim', self, 40)
        self._ui.app_image.set_from_surface(surface)
        self._ui.workspace_scrolled.add(self._workspace_side_bar)

        self._ui.account_box.add(self._account_side_bar)

        self._ui.right_grid.add(self._chat_stack)

        workspace_menu = Gio.Menu()
        for action, label in WORKSPACE_MENU_DICT.items():
            workspace_menu.append(label, f'win.{action.lower()}-workspace')

        self._ui.workspace_menu_button.set_menu_model(workspace_menu)

        self._ui.start_chat_button.connect(
            'clicked', self._on_start_chat_clicked)
        self._ui.connect_signals(self)

        self._ui.paned.set_position(app.settings.get('chat_handle_position'))
        self._ui.paned.connect('button-release-event', self._on_button_release)

        self.register_events([
            ('presence-received', ged.GUI1, self._on_event),
            ('nickname-received', ged.GUI1, self._on_event),
            ('mood-received', ged.GUI1, self._on_event),
            ('activity-received', ged.GUI1, self._on_event),
            ('tune-received', ged.GUI1, self._on_event),
            ('location-received', ged.GUI1, self._on_event),
            ('chatstate-received', ged.GUI1, self._on_event),
            ('caps-update', ged.GUI1, self._on_event),
            ('message-sent', ged.OUT_POSTCORE, self._on_event),
            ('message-received', ged.CORE, self._on_event),
            ('mam-message-received', ged.CORE, self._on_event),
            ('gc-message-received', ged.CORE, self._on_event),
            ('receipt-received', ged.GUI1, self._on_event),
            ('displayed-received', ged.GUI1, self._on_event),
            ('message-error', ged.GUI1, self._on_event),
            ('update-roster-avatar', ged.GUI1, self._on_event),
            ('update-room-avatar', ged.GUI1, self._on_event),
            ('update-gc-avatar', ged.GUI1, self._on_event),
            ('muc-creation-failed', ged.GUI1, self._on_event),
            ('muc-joined', ged.GUI1, self._on_event),
            ('muc-join-failed', ged.GUI1, self._on_event),
            ('muc-user-joined', ged.GUI1, self._on_event),
            ('muc-user-left', ged.GUI1, self._on_event),
            ('muc-nickname-changed', ged.GUI1, self._on_event),
            ('muc-self-presence', ged.GUI1, self._on_event),
            ('muc-self-kicked', ged.GUI1, self._on_event),
            ('muc-user-affiliation-changed', ged.GUI1, self._on_event),
            ('muc-user-status-show-changed', ged.GUI1, self._on_event),
            ('muc-user-role-changed', ged.GUI1, self._on_event),
            ('muc-destroyed', ged.GUI1, self._on_event),
            ('muc-presence-error', ged.GUI1, self._on_event),
            ('muc-password-required', ged.GUI1, self._on_event),
            ('muc-config-changed', ged.GUI1, self._on_event),
            ('muc-subject', ged.GUI1, self._on_event),
            ('muc-captcha-challenge', ged.GUI1, self._on_event),
            ('muc-captcha-error', ged.GUI1, self._on_event),
            ('muc-voice-request', ged.GUI1, self._on_event),
            ('muc-disco-update', ged.GUI1, self._on_event),
            ('muc-configuration-finished', ged.GUI1, self._on_event),
            ('muc-configuration-failed', ged.GUI1, self._on_event),
            ('our-show', ged.GUI1, self._on_our_show),
            ('signed-in', ged.GUI1, self._on_signed_in),
        ])

        self.show_all()

        self._load_chats()
        self._add_accounts()
        self._add_actions()
        self._add_actions2()

    @staticmethod
    def _on_our_show(event):
        if event.show == 'offline':
            app.app.set_account_actions_state(event.account)
            app.app.update_app_actions_state()

    @staticmethod
    def _on_signed_in(event):
        app.app.set_account_actions_state(event.account, True)
        app.app.update_app_actions_state()

    @staticmethod
    def _on_button_release(paned, event):
        if event.window != paned.get_handle_window():
            return
        position = paned.get_position()
        app.settings.set('chat_handle_position', position)

    def _add_actions(self):
        actions = [
            ('add-workspace', 's', self._add_workspace),
            ('edit-workspace', None, self._edit_workspace),
            ('remove-workspace', None, self._remove_workspace),
            ('activate-workspace', 's', self._activate_workspace),
            ('add-chat', 'as', self._add_chat),
            ('add-group-chat', 'as', self._add_group_chat),
            ('remove-chat', 'as', self._remove_chat),
            ('toggle-chat-pinned', 'as', self._toggle_chat_pinned),
            ('move-chat-to-workspace', 'as', self._move_chat_to_workspace),
        ]

        for action in actions:
            action_name, variant, func = action
            if variant is not None:
                variant = GLib.VariantType.new(variant)
            act = Gio.SimpleAction.new(action_name, variant)
            act.connect('activate', func)
            self.add_action(act)

    def _add_actions2(self):
        actions = [
            'change-nickname',
            'change-subject',
            'escape',
            'browse-history',
            'send-file',
            'show-contact-info',
            'show-emoji-chooser',
            'clear-chat',
            'delete-line',
            'close-tab',
            'move-tab-up',
            'move-tab-down',
            'switch-next-tab',
            'switch-prev-tab',
            'switch-next-unread-tab-right'
            'switch-next-unread-tab-left',
            'switch-tab-1',
            'switch-tab-2',
            'switch-tab-3',
            'switch-tab-4',
            'switch-tab-5',
            'switch-tab-6',
            'switch-tab-7',
            'switch-tab-8',
            'switch-tab-9',
        ]

        disabled_for_emacs = (
            'browse-history',
            'send-file',
            'close-tab'
        )

        key_theme = Gtk.Settings.get_default().get_property(
            'gtk-key-theme-name')

        for action in actions:
            if key_theme == 'Emacs' and action in disabled_for_emacs:
                continue
            act = Gio.SimpleAction.new(action, None)
            act.connect('activate', self._on_action)
            self.add_action(act)

    def _on_action(self, action, _param):
        control = self.get_active_control()
        if control is None:
            return

        log.info('Activate action: %s, active control: %s',
                 action.get_name(), control.contact.jid)

        action = action.get_name()

        res = control.delegate_action(action)
        if res != Gdk.EVENT_PROPAGATE:
            return res

        # if action == 'escape' and app.settings.get('escape_key_closes'):
        #     self.remove_tab(control, self.CLOSE_ESC)
        #     return

        # if action == 'close-tab':
        #     self.remove_tab(control, self.CLOSE_CTRL_KEY)
        #     return

        # if action == 'move-tab-up':
        #     old_position = self.notebook.get_current_page()
        #     self.notebook.reorder_child(control.widget,
        #                                 old_position - 1)
        #     return

        # if action == 'move-tab-down':
        #     old_position = self.notebook.get_current_page()
        #     total_pages = self.notebook.get_n_pages()
        #     if old_position == total_pages - 1:
        #         self.notebook.reorder_child(control.widget, 0)
        #     else:
        #         self.notebook.reorder_child(control.widget,
        #                                     old_position + 1)
        #     return

        # if action == 'switch-next-tab':
        #     new = self.notebook.get_current_page() + 1
        #     if new >= self.notebook.get_n_pages():
        #         new = 0
        #     self.notebook.set_current_page(new)
        #     return

        # if action == 'switch-prev-tab':
        #     new = self.notebook.get_current_page() - 1
        #     if new < 0:
        #         new = self.notebook.get_n_pages() - 1
        #     self.notebook.set_current_page(new)
        #     return

        # if action == 'switch-next-unread-tab-right':
        #     self.move_to_next_unread_tab(True)
        #     return

        # if action == 'switch-next-unread-tab-left':
        #     self.move_to_next_unread_tab(False)
        #     return

        # if action.startswith('switch-tab-'):
        #     number = int(action[-1])
        #     self.notebook.set_current_page(number - 1)
        #     return

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

    def show_account_page(self, account):
        self._account_side_bar.activate_account_page(account)
        self._ui.main_stack.set_visible_child_name(account)

    def get_workspace_bar(self):
        return self._workspace_side_bar

    def get_active_workspace(self):
        return self._workspace_side_bar.get_active_workspace()

    def is_chat_active(self, account, jid):
        if not self.get_property('has-toplevel-focus'):
            return False
        return self._chat_list_stack.is_chat_active(account, jid)

    def _add_workspace(self, _action, param):
        workspace_id = param.get_string()
        self.add_workspace(workspace_id)

    def add_workspace(self, workspace_id):
        self._workspace_side_bar.add_workspace(workspace_id)
        self._chat_list_stack.add_chat_list(workspace_id)
        self._workspace_side_bar.activate_workspace(workspace_id)
        self._chat_list_stack.show_chat_list(workspace_id)

    def _edit_workspace(self, _action, _param):
        workspace_id = self.get_active_workspace()
        if workspace_id is not None:
            self.edit_workspace(workspace_id)

    @staticmethod
    def edit_workspace(workspace_id):
        open_window('WorkspaceDialog', workspace_id=workspace_id)

    def _remove_workspace(self, _action, _param):
        workspace_id = self.get_active_workspace()
        if workspace_id is not None:
            self.remove_workspace(workspace_id)

    def remove_workspace(self, workspace_id):
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

    def _activate_workspace(self, _action, param):
        workspace_id = param.get_string()
        self.activate_workspace(workspace_id)

    def activate_workspace(self, workspace_id):
        self._ui.main_stack.set_visible_child_name('chats')
        self._workspace_side_bar.activate_workspace(workspace_id)
        self._chat_list_stack.show_chat_list(workspace_id)

    def update_workspace(self, workspace_id):
        name = app.settings.get_workspace_setting(workspace_id, 'name')
        self._ui.workspace_label.set_text(name)
        app.interface.avatar_storage.invalidate_cache(workspace_id)
        self._workspace_side_bar.update_avatar(workspace_id)

    def _add_group_chat(self, _action, param):
        account, jid = param.unpack()
        self.add_group_chat(account, jid)

    def add_group_chat(self, account, jid, select=False):
        workspace_id = self._workspace_side_bar.get_active_workspace()
        self.add_chat_for_workspace(workspace_id,
                                    account,
                                    jid,
                                    'groupchat',
                                    select=select)

    def _add_chat(self, _action, param):
        account, jid, type_ = param.unpack()
        self.add_chat(account, jid, type_)

    def add_chat(self, account, jid, type_, select=False):
        workspace_id = self._workspace_side_bar.get_active_workspace()
        self.add_chat_for_workspace(workspace_id,
                                    account,
                                    jid,
                                    type_,
                                    select=select)

    def add_private_chat(self, account, jid, select=False):
        workspace_id = self._workspace_side_bar.get_active_workspace()
        self.add_chat_for_workspace(workspace_id,
                                    account,
                                    jid,
                                    'pm',
                                    select=select)

    def add_chat_for_workspace(self,
                               workspace_id,
                               account,
                               jid,
                               type_,
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
        self._chat_list_stack.add_chat(workspace_id, account, jid, type_)

        if self._startup_finished:
            if select:
                self._chat_list_stack.select_chat(account, jid)
            self._chat_list_stack.store_open_chats(workspace_id)

    def _toggle_chat_pinned(self, _action, param):
        workspace_id, account, jid = param.unpack()
        self.toggle_chat_pinned(workspace_id, account, jid)

    def toggle_chat_pinned(self, workspace_id, account, jid):
        self._chat_list_stack.toggle_chat_pinned(workspace_id, account, jid)

    def _move_chat_to_workspace(self, _action, param):
        new_workspace_id, account, jid = param.unpack()
        self.move_chat_to_workspace(new_workspace_id, account, jid)

    def move_chat_to_workspace(self, new_workspace_id, account, jid):
        current_chatlist = self._chat_list_stack.get_visible_child()
        type_ = current_chatlist.get_chat_type(account, jid)
        self.remove_chat(current_chatlist.workspace_id, account, jid)
        self.add_chat_for_workspace(new_workspace_id, account, jid, type_)

    def _remove_chat(self, _action, param):
        workspace_id, account, jid = param.unpack()
        self.remove_chat(workspace_id, account, jid)

    def remove_chat(self, workspace_id, account, jid):
        self._chat_list_stack.remove_chat(workspace_id, account, jid)

    def chat_exists(self, account, jid):
        return self._chat_list_stack.contains_chat(account, jid)

    def chat_exists_for_workspace(self, workspace_id, account, jid):
        return self._chat_list_stack.contains_chat(
            account, jid, workspace_id=workspace_id)

    def get_control(self, account, jid):
        return self._chat_stack.get_control(account, jid)

    def get_active_control(self):
        chat = self._chat_list_stack.get_selected_chat()
        if chat is None:
            return None
        return self.get_control(chat.account, chat.jid)

    def _add_accounts(self):
        for account in list(app.connections.keys()):
            self._ui.main_stack.add_named(
                AccountPage(account), account)

    def get_controls(self, account=None):
        return self._chat_stack.get_controls(account)

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

    def _on_event(self, event):
        if event.name == 'caps-update':
            #TODO
            return

        if not self.chat_exists(event.account, event.jid):
            if event.name == 'message-received':
                if event.properties.is_muc_pm:
                    self.add_private_chat(event.account, event.jid, 'pm')
                else:
                    self.add_chat(event.account, event.jid, 'contact')
            else:
                # No chat is open, dont handle any gui events
                return

        self._chat_stack.process_event(event)
        self._chat_list_stack.process_event(event)

    def quit(self):
        accounts = list(app.connections.keys())
        get_msg = False
        for acct in accounts:
            if app.account_is_available(acct):
                get_msg = True
                break

        def on_continue2(message):
            if 'file_transfers' not in app.interface.instances:
                app.app.start_shutdown(message=message)
                return
            # check if there is an active file transfer
            from gajim.common.modules.bytestream import is_transfer_active
            files_props = app.interface.instances['file_transfers'].\
                files_props
            transfer_active = False
            for x in files_props:
                for y in files_props[x]:
                    if is_transfer_active(files_props[x][y]):
                        transfer_active = True
                        break

            if transfer_active:
                ConfirmationDialog(
                    _('Stop File Transfers'),
                    _('You still have running file transfers'),
                    _('If you quit now, the file(s) being transferred will '
                      'be lost.\n'
                      'Do you still want to quit?'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       text=_('_Quit'),
                                       callback=app.app.start_shutdown,
                                       kwargs={'message': message})]).show()
                return
            app.app.start_shutdown(message=message)

        def on_continue(message):
            if message is None:
                # user pressed Cancel to change status message dialog
                return
            # check if we have unread messages
            unread = app.events.get_nb_events()

            for event in app.events.get_all_events(['printed_gc_msg']):
                contact = app.contacts.get_groupchat_contact(event.account,
                                                             event.jid)
                if contact is None or not contact.can_notify():
                    unread -= 1

            if unread:
                ConfirmationDialog(
                    _('Unread Messages'),
                    _('You still have unread messages'),
                    _('Messages will only be available for reading them later '
                      'if storing chat history is enabled and if the contact '
                      'is in your contact list.'),
                    [DialogButton.make('Cancel'),
                     DialogButton.make('Remove',
                                       text=_('_Quit'),
                                       callback=on_continue2,
                                       args=[message])]).show()
                return
            on_continue2(message)

        if get_msg and ask_for_status_message('offline'):
            open_window('StatusChange',
                        status='offline',
                        callback=on_continue,
                        show_pep=False)
        else:
            on_continue('')
