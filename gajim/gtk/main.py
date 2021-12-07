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

from __future__ import annotations

from typing import Optional
from typing import Generator

import logging
import os

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio

from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.const import Display
from gajim.common.const import Direction
from gajim.common.helpers import ask_for_status_message
from gajim.common.i18n import _
from gajim.common.nec import EventHelper
from gajim.common.modules.bytestream import is_transfer_active

from .adhoc import AdHocCommand
from .account_side_bar import AccountSideBar
from .app_side_bar import AppSideBar
from .workspace_side_bar import Workspace
from .workspace_side_bar import WorkspaceSideBar
from .main_stack import MainStack
from .chat_list import ChatList
from .dialogs import DialogButton
from .dialogs import ConfirmationDialog
from .dialogs import ConfirmationCheckDialog
from .types import ControlType
from .util import get_builder
from .util import resize_window
from .util import restore_main_window_position
from .util import save_main_window_position
from .util import open_window

log = logging.getLogger('gajim.gui.main')


class MainWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_title('Gajim')
        self.set_default_icon_name('org.gajim.Gajim')

        app.window = self

        self._startup_finished: bool = False

        self._ui = get_builder('main.ui')

        self.add(self._ui.main_grid)

        self._main_stack = MainStack()
        self._ui.main_grid.add(self._main_stack)

        self._chat_page = self._main_stack.get_chat_page()

        self._app_page = self._main_stack.get_app_page()
        self._app_side_bar = AppSideBar(self._app_page)
        self._ui.app_box.add(self._app_side_bar)

        self._workspace_side_bar = WorkspaceSideBar(self._chat_page)
        self._ui.workspace_scrolled.add(self._workspace_side_bar)

        self._account_side_bar = AccountSideBar()
        self._ui.account_box.add(self._account_side_bar)

        self.connect('motion-notify-event', self._on_window_motion_notify)
        self.connect('notify::is-active', self._on_window_active)
        self.connect('delete-event', self._on_window_delete)

        self._ui.connect_signals(self)

        self.register_events([
            ('presence-received', ged.GUI1, self._on_event),
            ('message-sent', ged.OUT_POSTCORE, self._on_event),
            ('message-received', ged.CORE, self._on_event),
            ('mam-message-received', ged.CORE, self._on_event),
            ('gc-message-received', ged.CORE, self._on_event),
            ('message-updated', ged.CORE, self._on_event),
            ('receipt-received', ged.GUI1, self._on_event),
            ('displayed-received', ged.GUI1, self._on_event),
            ('message-error', ged.GUI1, self._on_event),
            ('muc-creation-failed', ged.GUI1, self._on_event),
            ('muc-self-presence', ged.GUI1, self._on_event),
            ('muc-voice-request', ged.GUI1, self._on_event),
            ('muc-disco-update', ged.GUI1, self._on_event),
            ('jingle-request-received', ged.GUI1, self._on_event),
            ('jingle-connected-received', ged.GUI1, self._on_event),
            ('jingle-disconnected-received', ged.GUI1, self._on_event),
            ('jingle-error-received', ged.GUI1, self._on_event),
            ('file-request-received', ged.GUI1, self._on_event),
            ('file-request-sent', ged.GUI1, self._on_event),
            ('our-show', ged.GUI1, self._on_our_show),
            ('signed-in', ged.GUI1, self._on_signed_in),
            ('account-enabled', ged.GUI1, self._on_account_enabled),
            ('account-disabled', ged.GUI1, self._on_account_disabled),
        ])

        self._check_for_account()
        self._load_chats()
        self._add_actions()
        self._add_actions2()

        self._prepare_window()

        if not app.is_display(Display.WAYLAND):
            app.interface.systray.connect_unread_changed(
                self._chat_page.get_chat_list_stack())

    def _prepare_window(self) -> None:
        if app.settings.get('main_window_skip_taskbar'):
            self.set_property('skip-taskbar-hint', True)

        restore_main_window_position()
        window_width = app.settings.get('mainwin_width')
        window_height = app.settings.get('mainwin_height')
        resize_window(self, window_width, window_height)

        if app.settings.get('show_main_window_on_startup') == 'always':
            self.show_all()
        elif app.settings.get('show_main_window_on_startup') == 'never':
            if app.settings.get('trayicon') != 'always':
                # Without trayicon, we have to show the main window
                self.show_all()
                app.settings.set('last_main_window_visible', True)
        else:
            if (app.settings.get('last_main_window_visible') or
                    app.settings.get('trayicon') != 'always'):
                self.show_all()

    def _on_account_enabled(self, event):
        self._account_side_bar.add_account(event.account)
        self._main_stack.add_account_page(event.account)

    def _on_account_disabled(self, event):
        workspace_id = self._workspace_side_bar.get_first_workspace()
        self.activate_workspace(workspace_id)
        self._account_side_bar.remove_account(event.account)
        self._main_stack.remove_account_page(event.account)
        self._main_stack.remove_chats_for_account(event.account)

    @staticmethod
    def _on_our_show(event):
        if event.show == 'offline':
            app.app.set_account_actions_state(event.account)
            app.app.update_app_actions_state()

    @staticmethod
    def _on_signed_in(event):
        app.app.set_account_actions_state(event.account, True)
        app.app.update_app_actions_state()

    def _add_actions(self):
        actions = [
            ('add-workspace', 's', self._add_workspace),
            ('edit-workspace', 's', self._edit_workspace),
            ('remove-workspace', None, self._remove_workspace),
            ('activate-workspace', 's', self._activate_workspace),
            ('add-chat', 'a{sv}', self._add_chat),
            ('add-group-chat', 'as', self._add_group_chat),
            ('add-to-roster', 'as', self._add_to_roster),
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
            'send-file',
            'show-contact-info',
            'show-emoji-chooser',
            'clear-chat',
            'delete-line',
            'close-tab',
            'switch-next-tab',
            'switch-prev-tab',
            'switch-next-unread-tab'
            'switch-prev-unread-tab',
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

    def _on_action(self,
                   action: Gio.SimpleAction,
                   _param: Optional[GLib.Variant]) -> None:

        control = self.get_active_control()
        if control is None:
            return None
        log.info('Activate action: %s, active control: %s',
                 action.get_name(), control.contact.jid)

        action_name = action.get_name()

        res = control.delegate_action(action)
        if res != Gdk.EVENT_PROPAGATE:
            return res

        if action_name == 'escape':
            if self._chat_page.hide_search():
                return None

            if app.settings.get('escape_key_closes'):
                self._chat_page.remove_chat(control.account,
                                            control.contact.jid)
                return None

        elif action_name == 'close-tab':
            self._chat_page.remove_chat(control.account, control.contact.jid)

        elif action_name == 'switch-next-tab':
            self.select_next_chat(Direction.NEXT)

        elif action_name == 'switch-prev-tab':
            self.select_next_chat(Direction.PREV)

        elif action_name == 'switch-next-unread-tab':
            self.select_next_chat(Direction.NEXT, unread_first=True)

        elif action_name == 'switch-prev-unread-tab':
            self.select_next_chat(Direction.PREV, unread_first=True)

        elif action_name.startswith('switch-tab-'):
            number = int(action_name[-1]) - 1
            self.select_chat_number(number)

        return None

    def _on_window_motion_notify(self, _widget, _event):
        control = self.get_active_control()
        if control is None:
            return

        if self.get_property('has-toplevel-focus'):
            client = app.get_client(control.account)
            client.get_module('Chatstate').set_mouse_activity(
                control.contact, control.msg_textview.has_text())

    def _on_window_delete(self, _widget, _event):
        # Main window X button was clicked
        if app.settings.get('quit_on_main_window_x_button'):
            self.quit()
        else:
            if (app.settings.get('allow_hide_roster') or
                    (app.interface.systray_enabled and
                     app.settings.get('trayicon') != 'on_event')):
                save_main_window_position()
                if (os.name == 'nt' or
                        app.settings.get('hide_on_main_window_x_button')):
                    self.hide()
                else:
                    self.iconify()
                return True

            def _on_ok(is_checked):
                if is_checked:
                    app.settings.set('quit_on_main_window_x_button', True)
                self.quit()

            ConfirmationCheckDialog(
                _('Quit Gajim'),
                _('You are about to quit Gajim'),
                _('Are you sure you want to quit Gajim?'),
                _('_Always quit when closing Gajim'),
                [DialogButton.make('Cancel'),
                 DialogButton.make('Remove',
                                   text=_('_Quit'),
                                   callback=_on_ok)]).show()
        return True

    def _set_startup_finished(self):
        self._startup_finished = True
        self._chat_page.set_startup_finished()

    def show_account_page(self, account: str) -> None:
        self._app_side_bar.unselect_all()
        self._workspace_side_bar.unselect_all()
        self._account_side_bar.activate_account_page(account)
        self._main_stack.show_account(account)

    def get_active_workspace(self) -> Optional[Workspace]:
        return self._workspace_side_bar.get_active_workspace()

    def is_chat_active(self, account: str, jid: JID) -> bool:
        if not self.get_property('has-toplevel-focus'):
            return False
        return self._chat_page.is_chat_active(account, jid)

    def _add_workspace(self,
                       _action: Gio.SimpleAction,
                       param: Optional[GLib.Variant]) -> None:

        workspace_id = param.get_string()
        if workspace_id is not None:
            self.add_workspace(workspace_id)

    def add_workspace(self, workspace_id: str) -> None:
        self._workspace_side_bar.add_workspace(workspace_id)
        self._chat_page.add_chat_list(workspace_id)

        if self._startup_finished:
            self.activate_workspace(workspace_id)
            self._workspace_side_bar.store_workspace_order()

    def _edit_workspace(self,
                        _action: Gio.SimpleAction,
                        param: GLib.Variant) -> None:
        workspace_id = param.get_string() or None
        if workspace_id is None:
            workspace_id = self.get_active_workspace()
        open_window('WorkspaceDialog', workspace_id=workspace_id)

    def _remove_workspace(self,
                          _action: Gio.SimpleAction,
                          _param: Optional[GLib.Variant]) -> None:

        workspace_id = self.get_active_workspace()
        if workspace_id is not None:
            self.remove_workspace(workspace_id)

    def remove_workspace(self, workspace_id: str) -> None:
        was_active = self.get_active_workspace() == workspace_id

        success = self._workspace_side_bar.remove_workspace(workspace_id)
        if not success:
            return

        if was_active:
            new_active_id = self._workspace_side_bar.get_first_workspace()
            self.activate_workspace(new_active_id)

        self._chat_page.remove_chat_list(workspace_id)
        app.settings.remove_workspace(workspace_id)

    def _activate_workspace(self,
                            _action: Gio.SimpleAction,
                            param: Optional[GLib.Variant]) -> None:

        workspace_id = param.get_string()
        if workspace_id is not None:
            self.activate_workspace(workspace_id)

    def activate_workspace(self, workspace_id: str) -> None:
        self._app_side_bar.unselect_all()
        self._account_side_bar.unselect_all()
        self._main_stack.show_chats(workspace_id)
        self._workspace_side_bar.activate_workspace(workspace_id)

    def update_workspace(self, workspace_id: str) -> None:
        self._chat_page.update_workspace(workspace_id)
        self._workspace_side_bar.update_avatar(workspace_id)

    def get_chat_list(self, workspace_id: str) -> ChatList:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        return chat_list_stack.get_chatlist(workspace_id)

    def _add_group_chat(self,
                        _action: Gio.SimpleAction,
                        param: Optional[GLib.Variant]) -> None:

        account, jid, select = param.unpack()
        self.add_group_chat(account, JID.from_string(jid), select)

    def add_group_chat(self, account: str, jid: JID,
                       select: bool = False) -> None:
        workspace_id = self.get_active_workspace()
        if workspace_id is None:
            workspace_id = self._workspace_side_bar.get_first_workspace()
        self._chat_page.add_chat_for_workspace(workspace_id,
                                               account,
                                               jid,
                                               'groupchat',
                                               select=select)

    def _add_chat(self,
                  _action: Gio.SimpleAction,
                  param: Optional[GLib.Variant]) -> None:

        account, jid, type_, select = param.unpack()
        self.add_chat(account, JID.from_string(jid), type_, select)

    def add_chat(self, account: str, jid: JID, type_: str,
                 select: bool = False) -> None:
        workspace_id = self.get_active_workspace()
        if workspace_id is None:
            workspace_id = self._workspace_side_bar.get_first_workspace()
        self._chat_page.add_chat_for_workspace(workspace_id,
                                               account,
                                               jid,
                                               type_,
                                               select=select)

    def add_private_chat(self, account: str, jid: JID,
                         select: bool = False) -> None:
        workspace_id = self.get_active_workspace()
        if workspace_id is None:
            workspace_id = self._workspace_side_bar.get_first_workspace()
        self._chat_page.add_chat_for_workspace(workspace_id,
                                               account,
                                               jid,
                                               'pm',
                                               select=select)

    def select_chat(self, account: str, jid: JID) -> None:
        self._app_side_bar.unselect_all()
        self._account_side_bar.unselect_all()
        self._main_stack.show_chat_page()
        self._chat_page.select_chat(account, jid)

    def select_next_chat(self, direction: Direction,
                         unread_first: bool = False) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            chat_list.select_next_chat(direction, unread_first)

    def select_chat_number(self, number: int) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            chat_list.select_chat_number(number)

    @staticmethod
    def _add_to_roster(_action: Gio.SimpleAction,
                       param: Optional[GLib.Variant]) -> None:

        _workspace, account, jid = param.unpack()
        open_window('AddContact', account=account, jid=JID.from_string(jid))

    def show_app_page(self) -> None:
        self._account_side_bar.unselect_all()
        self._workspace_side_bar.unselect_all()
        self._main_stack.show_app_page()

    def add_app_message(self, category: str,
                        message: Optional[str] = None) -> None:
        self._app_page.add_app_message(category, message)

    def get_control(self, account: str, jid: JID) -> Optional[ControlType]:
        return self._chat_page.get_control(account, jid)

    def get_controls(self, account: Optional[str] = None
                     ) -> Generator[ControlType, None, None]:
        return self._chat_page.get_controls(account)

    def get_active_control(self) -> Optional[ControlType]:
        return self._chat_page.get_active_control()

    def get_currently_loaded_control(self) -> Optional[ControlType]:
        return self._chat_page.get_currently_loaded_control()

    def chat_exists(self, account: str, jid: JID) -> bool:
        return self._chat_page.chat_exists(account, jid)

    def get_total_unread_count(self) -> int:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        return chat_list_stack.get_total_unread_count()

    def get_chat_unread_count(self,
                              account: str,
                              jid: JID,
                              include_silent: bool = False
                              ) -> int:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        count = chat_list_stack.get_chat_unread_count(
            account, jid, include_silent)
        return count or 0

    def mark_as_read(self, account: str, jid: JID,
                     send_marker: bool = True) -> None:
        # TODO set window urgency hint, etc.
        control = self.get_control(account, jid)
        if control is not None:
            # Send displayed marker and
            # reset jump to bottom button unread counter
            control.mark_as_read(send_marker=send_marker)
        # Reset chat list unread counter (emits unread-count-changed)
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list_stack.mark_as_read(account, jid)

    def _on_window_active(self, window, _param):
        is_active = window.get_property('is-active')
        if not is_active:
            return

        control = self.get_active_control()
        if control is None:
            return

        if control.get_autoscroll():
            self.mark_as_read(control.account, control.contact.jid)

    @staticmethod
    def contact_info(account, jid):
        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        open_window('ContactInfo', account=account, contact=contact)

    @staticmethod
    def execute_command(account, jid):
        # TODO: Resource?
        AdHocCommand(account, jid)

    def block_contact(self, account, jid):
        client = app.get_client(account)

        contact = client.get_module('Contacts').get_contact(jid)
        if contact.is_blocked:
            client.get_module('Blocking').unblock([jid])
            return

        # TODO: Keep "confirm_block" setting?
        def _block_contact(report=None):
            client.get_module('Blocking').block([contact.jid], report)
            self._chat_page.remove_chat(account, contact.jid)

        ConfirmationDialog(
            _('Block Contact'),
            _('Really block this contact?'),
            _('You will appear offline for this contact and you '
              'will not receive further messages.'),
            [DialogButton.make('Cancel'),
             DialogButton.make('OK',
                               text=_('_Report Spam'),
                               callback=_block_contact,
                               kwargs={'report': 'spam'}),
             DialogButton.make('Remove',
                               text=_('_Block'),
                               callback=_block_contact)],
            modal=False).show()

    def remove_contact(self, account: str, jid: JID) -> None:
        client = app.get_client(account)

        def _remove_contact():
            self._chat_page.remove_chat(account, jid)
            client.get_module('Roster').delete_item(jid)

        contact = client.get_module('Contacts').get_contact(jid)
        sec_text = _('You are about to remove %(name)s (%(jid)s) from '
                     'your contact list.\n') % {
                         'name': contact.name,
                         'jid': jid}

        ConfirmationDialog(
            _('Remove Contact'),
            _('Remove contact from contact list'),
            sec_text,
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               callback=_remove_contact)]).show()

    @staticmethod
    def _check_for_account() -> None:
        accounts = app.settings.get_accounts()
        if (not accounts or accounts == ['Local'] and
                not app.settings.get_account_setting('Local', 'active')):
            # Either no account configured or only disabled Local account
            def _open_wizard():
                open_window('AccountWizard')

            GLib.idle_add(_open_wizard)

    def _load_chats(self) -> None:
        for workspace_id in app.settings.get_workspaces():
            self.add_workspace(workspace_id)
            self._chat_page.load_workspace_chats(workspace_id)

        workspace_id = self._workspace_side_bar.get_first_workspace()
        self.activate_workspace(workspace_id)

        self._set_startup_finished()

    def _on_event(self, event):
        if event.name == 'update-roster-avatar':
            return

        if not self.chat_exists(event.account, event.jid):
            if event.name == 'message-received':
                if not event.properties.body:
                    # Don’t open control on chatstate etc.
                    return
                if event.properties.is_muc_pm:
                    self.add_private_chat(event.account,
                                          event.properties.jid,
                                          'pm')
                else:
                    jid = event.properties.jid.new_as_bare()
                    self.add_chat(event.account, jid, 'contact')
            elif event.name == 'jingle-request-received':
                content_types = []
                for item in event.contents:
                    content_types.append(item.media)
                if 'audio' in content_types or 'video' in content_types:
                    # AV Call received, open chat control
                    self.add_chat(event.account, event.jid, 'contact')
            elif event.name == 'file-request-received':
                # Jingle file transfer, open chat control
                self.add_chat(event.account, event.jid, 'contact')
            else:
                # No chat is open, dont handle any gui events
                return

        self._main_stack.process_event(event)

    def quit(self):
        accounts = list(app.connections.keys())
        get_msg = False
        for acct in accounts:
            if app.account_is_available(acct):
                get_msg = True
                break

        save_main_window_position()
        window_width, window_height = self.get_size()
        app.settings.set('mainwin_width', window_width)
        app.settings.set('mainwin_height', window_height)
        app.settings.set(
            'last_main_window_visible', self.get_property('visible'))
        app.settings.save()

        def on_continue2(message):
            if 'file_transfers' not in app.interface.instances:
                app.app.start_shutdown(message=message)
                return
            # check if there is an active file transfer
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

            # Check for unread messages
            if self.get_total_unread_count():
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
            print('TODO: Let user choose status message')
            on_continue('')  # status message here
        else:
            on_continue('')
