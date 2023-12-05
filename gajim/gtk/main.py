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

from typing import Any
from typing import TYPE_CHECKING

import logging
import os
import shutil
from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common import types
from gajim.common.client import Client
from gajim.common.const import Direction
from gajim.common.const import Display
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.helpers import open_file
from gajim.common.helpers import open_uri
from gajim.common.helpers import play_sound
from gajim.common.helpers import show_in_folder
from gajim.common.i18n import _
from gajim.common.modules.bytestream import is_transfer_active
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.plugins.manifest import PluginManifest
from gajim.plugins.repository import PluginRepository

from gajim.gtk.account_side_bar import AccountSideBar
from gajim.gtk.app_side_bar import AppSideBar
from gajim.gtk.builder import get_builder
from gajim.gtk.call_window import CallWindow
from gajim.gtk.chat_list import ChatList
from gajim.gtk.chat_list_row import ChatListRow
from gajim.gtk.chat_stack import ChatStack
from gajim.gtk.const import MAIN_WIN_ACTIONS
from gajim.gtk.dialogs import ConfirmationCheckDialog
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.filechoosers import FileSaveDialog
from gajim.gtk.main_stack import MainStack
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.structs import actionmethod
from gajim.gtk.structs import AddChatActionParams
from gajim.gtk.structs import ChatListEntryParam
from gajim.gtk.structs import RetractMessageParam
from gajim.gtk.util import get_app_window
from gajim.gtk.util import open_window
from gajim.gtk.util import resize_window
from gajim.gtk.util import restore_main_window_position
from gajim.gtk.util import save_main_window_position
from gajim.gtk.util import set_urgency_hint
from gajim.gtk.workspace_side_bar import WorkspaceSideBar

if TYPE_CHECKING:
    from gajim.gtk.control import ChatControl

log = logging.getLogger('gajim.gtk.main')


class MainWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_title('Gajim')
        self.set_default_icon_name('org.gajim.Gajim')

        app.window = self

        self._add_actions()
        self._add_stateful_actions()
        self._connect_actions()

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
        self.connect('window-state-event', self._on_window_state_changed)
        self.connect_after('key-press-event', self._on_key_press_event)

        self._ui.connect_signals(self)

        self.register_events([
            ('message-received', ged.GUI1, self._on_message_received),
            ('read-state-sync', ged.GUI1, self._on_read_state_sync),
            ('call-started', ged.GUI1, self._on_call_started),
            ('jingle-request-received', ged.GUI1, self._on_jingle_request),
            ('file-request-received', ged.GUI1, self._on_file_request),
            ('account-enabled', ged.GUI1, self._on_account_enabled),
            ('account-disabled', ged.GUI1, self._on_account_disabled),
            ('allow-gajim-update-check', ged.GUI1, self._on_allow_gajim_update),
            ('gajim-update-available', ged.GUI1,
             self._on_gajim_update_available),
            ('roster-item-exchange', ged.GUI1, self._on_roster_item_exchange),
            ('plain-connection', ged.GUI1, self._on_plain_connection),
            ('password-required', ged.GUI1, self._on_password_required),
            ('http-auth', ged.GUI1, self._on_http_auth),
            ('muc-added', ged.GUI1, self._on_muc_added),
            ('message-sent', ged.GUI1, self._on_message_sent),
            ('signed-in', ged.GUI1, self._on_signed_in),
        ])

        app.plugin_repository.connect('plugin-updates-available',
                                      self._on_plugin_updates_available)
        app.plugin_repository.connect('auto-update-finished',
                                      self._on_plugin_auto_update_finished)

        self._check_for_account()
        self._load_chats()
        self._load_unread_counts()

        self._prepare_window()

        chat_list_stack = self._chat_page.get_chat_list_stack()
        app.app.systray.connect_unread_widget(chat_list_stack,
                                              'unread-count-changed')

        for client in app.get_clients():
            client.connect_signal('state-changed',
                                  self._on_client_state_changed)

    def get_action(self, name: str) -> Gio.SimpleAction:
        action = self.lookup_action(name)
        assert isinstance(action, Gio.SimpleAction)
        return action

    def get_chat_stack(self) -> ChatStack:
        return self._chat_page.get_chat_stack()

    def is_minimized(self) -> bool:
        if app.is_display(Display.WAYLAND):
            # There is no way to discover if a window is minimized on wayland
            return False

        window = self.get_window()
        assert window is not None
        return bool(Gdk.WindowState.ICONIFIED & window.get_state())

    def is_withdrawn(self) -> bool:
        window = self.get_window()
        assert window is not None
        return bool(Gdk.WindowState.WITHDRAWN & window.get_state())

    def hide(self) -> None:
        save_main_window_position()
        Gtk.ApplicationWindow.hide(self)

    def show(self) -> None:
        restore_main_window_position()
        self.present_with_time(Gtk.get_current_event_time())

    def minimize(self) -> None:
        self.iconify()

    def unminimize(self) -> None:
        self.deiconify()
        self.present_with_time(Gtk.get_current_event_time())

    def mark_workspace_as_read(self, workspace: str) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_chatlist(workspace)
        open_chats = chat_list.get_open_chats()
        for chat in open_chats:
            self.mark_as_read(chat['account'], chat['jid'])

    def _mark_workspace_as_read(self,
                                _action: Gio.SimpleAction,
                                param: GLib.Variant
                                ) -> None:

        workspace_id = param.get_string() or None
        if workspace_id is not None:
            self.mark_workspace_as_read(workspace_id)

    def _prepare_window(self) -> None:
        window_width = app.settings.get('mainwin_width')
        window_height = app.settings.get('mainwin_height')
        resize_window(self, window_width, window_height)
        restore_main_window_position()

        self.set_skip_taskbar_hint(not app.settings.get('show_in_taskbar'))
        self.show_all()

        show_main_window = app.settings.get('show_main_window_on_startup')
        if show_main_window == 'never':
            self.hide()

        elif (show_main_window == 'last_state' and
                not app.settings.get('is_window_visible')):
            self.hide()

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        self._account_side_bar.add_account(event.account)
        self._main_stack.add_account_page(event.account)
        client = app.get_client(event.account)
        client.connect_signal('state-changed', self._on_client_state_changed)

    def _on_account_disabled(self, event: events.AccountDisabled) -> None:
        workspace_id = self._workspace_side_bar.get_first_workspace()
        self.activate_workspace(workspace_id)
        self._account_side_bar.remove_account(event.account)
        self._main_stack.remove_account_page(event.account)
        self._main_stack.remove_chats_for_account(event.account)

    def update_account_unread_count(self, account: str, count: int) -> None:
        self._account_side_bar.update_unread_count(account, count)

    def _on_key_press_event(
        self,
        _window: MainWindow,
        event: Gdk.EventKey
    ) -> bool:

        # event.get_state() behaves different on Linux and Windows.
        # On Linux its not set in the case that only a modifier key
        # is pressed.

        # Filter out modifier not used for shortcuts like Numlock (MOD2)
        modifier = event.get_state() & Gtk.accelerator_get_default_mod_mask()
        accel_name = Gtk.accelerator_name(event.keyval, modifier)

        log.info('Captured key pressed: %s', accel_name)

        if event.keyval in (
            Gdk.KEY_Control_L,
            Gdk.KEY_Control_R,
            Gdk.KEY_Alt_L,
            Gdk.KEY_Alt_R,
            Gdk.KEY_Shift_L,
            Gdk.KEY_Shift_R,
        ):
            return False

        focused_widget = self.get_focus()
        if (isinstance(focused_widget, Gtk.TextView)
            and focused_widget.props.editable):
                return False

        if isinstance(focused_widget, Gtk.Entry):
            return False

        message_input = self.get_chat_stack().get_message_input()
        if not message_input.get_mapped() or not message_input.is_sensitive():
            return False

        message_input.grab_focus()
        return self.propagate_key_event(event)

    def _on_client_state_changed(self,
                                 client: Client,
                                 _signal_name: str,
                                 state: SimpleClientState) -> None:

        app.app.set_account_actions_state(client.account, state.is_connected)
        app.app.update_app_actions_state()

    def _on_allow_gajim_update(self,
                               event: events.AllowGajimUpdateCheck) -> None:
        self.add_app_message(event.name)

    def _on_gajim_update_available(self,
                                   event: events.GajimUpdateAvailable
                                   ) -> None:

        self.add_app_message(
            event.name,
            new_version=event.version,
            new_setup_url=event.setup_url)

    @staticmethod
    def _on_roster_item_exchange(event: events.RosterItemExchangeEvent) -> None:
        open_window('RosterItemExchange',
                    account=event.client.account,
                    action=event.action,
                    exchange_list=event.exchange_items_list,
                    jid_from=event.jid)

    @staticmethod
    def _on_plain_connection(event: events.PlainConnection) -> None:
        ConfirmationDialog(
            _('Insecure Connection'),
            _('Insecure Connection'),
            _('You are about to connect to the account %(account)s '
              '(%(server)s) using an insecure connection method. This means '
              'conversations will not be encrypted. Connecting PLAIN is '
              'strongly discouraged.') % {
                  'account': event.account,
                  'server': app.get_hostname_from_account(event.account)},
            [DialogButton.make('Cancel',
                               text=_('_Abort'),
                               callback=event.abort),
             DialogButton.make('Remove',
                               text=_('_Connect Anyway'),
                               callback=event.connect)]).show()

    @staticmethod
    def _on_password_required(event: events.PasswordRequired) -> None:
        open_window('PasswordDialog', event=event)

    @staticmethod
    def _on_http_auth(event: events.HttpAuth) -> None:
        def _response(answer: str) -> None:
            event.client.get_module('HTTPAuth').build_http_auth_answer(
                event.stanza, answer)

        account = event.client.account
        message = _('HTTP (%(method)s) Authorization '
                    'for %(url)s (ID: %(id)s)') % {
                        'method': event.data.method,
                        'url': event.data.url,
                        'id': event.data.id}
        sec_msg = _('Do you accept this request?')
        if app.get_number_of_connected_accounts() > 1:
            sec_msg = _('Do you accept this request (account: %s)?') % account
        if event.data.body:
            sec_msg = event.data.body + '\n' + sec_msg
        message = message + '\n' + sec_msg

        ConfirmationDialog(
            _('Authorization Request'),
            _('HTTP Authorization Request'),
            message,
            [DialogButton.make('Cancel',
                               text=_('_No'),
                               callback=_response,
                               args=['no']),
             DialogButton.make('Accept',
                               callback=_response,
                               args=['yes'])]).show()

    def _on_muc_added(self, event: events.MucAdded) -> None:
        if self.chat_exists(event.account, event.jid):
            return

        self.add_group_chat(event.account, event.jid, select=event.select_chat)

    def _on_message_sent(self, event: events.MessageSent) -> None:
        if not event.play_sound:
            return

        enabled = app.settings.get_soundevent_settings(
            'message_sent')['enabled']
        if enabled:
            if isinstance(event.jid, list) and len(event.jid) > 1:
                return
            play_sound('message_sent', event.account)

    def _on_signed_in(self, event: events.SignedIn) -> None:
        if app.settings.get('ask_online_status'):
            self.show_account_page(event.account)

    def _add_actions(self) -> None:
        for action, variant_type, enabled in MAIN_WIN_ACTIONS:
            if variant_type is not None:
                variant_type = GLib.VariantType(variant_type)
            act = Gio.SimpleAction.new(action, variant_type)
            act.set_enabled(enabled)
            self.add_action(act)

    def _add_stateful_actions(self) -> None:
        action = Gio.SimpleAction.new_stateful(
            'show-offline',
            None,
            GLib.Variant('b', app.settings.get('showoffline')))

        action.connect('change-state', self._on_show_offline)

        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            'sort-by-show',
            None,
            GLib.Variant('b', app.settings.get('sort_by_show_in_roster')))

        action.connect('change-state', self._on_sort_by_show)

        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            'set-encryption',
            GLib.VariantType('s'),
            GLib.Variant('s', 'disabled'))

        self.add_action(action)

    def _connect_actions(self) -> None:
        actions = [
            ('change-nickname', self._on_action),
            ('change-subject', self._on_action),
            ('escape', self._on_action),
            ('close-chat', self._on_action),
            ('restore-chat', self._on_action),
            ('switch-next-chat', self._on_action),
            ('switch-prev-chat', self._on_action),
            ('switch-next-unread-chat', self._on_action),
            ('switch-prev-unread-chat', self._on_action),
            ('switch-chat-1', self._on_action),
            ('switch-chat-2', self._on_action),
            ('switch-chat-3', self._on_action),
            ('switch-chat-4', self._on_action),
            ('switch-chat-5', self._on_action),
            ('switch-chat-6', self._on_action),
            ('switch-chat-7', self._on_action),
            ('switch-chat-8', self._on_action),
            ('switch-chat-9', self._on_action),
            ('switch-workspace-1', self._on_action),
            ('switch-workspace-2', self._on_action),
            ('switch-workspace-3', self._on_action),
            ('switch-workspace-4', self._on_action),
            ('switch-workspace-5', self._on_action),
            ('switch-workspace-6', self._on_action),
            ('switch-workspace-7', self._on_action),
            ('switch-workspace-8', self._on_action),
            ('switch-workspace-9', self._on_action),
            ('increase-app-font-size', self._on_app_font_size_action),
            ('decrease-app-font-size', self._on_app_font_size_action),
            ('reset-app-font-size', self._on_app_font_size_action),
            ('toggle-chat-list', self._on_action),
            ('preview-download', self._on_preview_action),
            ('preview-open', self._on_preview_action),
            ('preview-save-as', self._on_preview_action),
            ('preview-open-folder', self._on_preview_action),
            ('preview-copy-link', self._on_preview_action),
            ('preview-open-link', self._on_preview_action),
            ('copy-message', self._on_copy_message),
            ('retract-message', self._on_retract_message),
            ('delete-message-locally', self._on_delete_message_locally),
            ('add-workspace', self._add_workspace),
            ('edit-workspace', self._edit_workspace),
            ('remove-workspace', self._remove_workspace),
            ('activate-workspace', self._activate_workspace),
            ('mark-workspace-as-read', self._mark_workspace_as_read),
            ('add-chat', self._add_chat),
            ('add-group-chat', self._add_group_chat),
            ('add-to-roster', self._add_to_roster),
        ]

        for action, func in actions:
            act = self.get_action(action)
            act.connect('activate', func)

    def _on_action(self,
                   action: Gio.SimpleAction,
                   _param: GLib.Variant | None) -> int | None:

        action_name = action.get_name()
        log.info('Activate action: %s', action_name)

        if action_name == 'escape' and self._chat_page.hide_search():
            return None

        chat_stack = self._chat_page.get_chat_stack()
        if action_name == 'escape' and chat_stack.process_escape():
            return None

        control = self.get_control()
        if control.has_active_chat():
            if action_name == 'change-nickname':
                app.window.activate_action('muc-change-nickname', None)
                return None

            if action_name == 'change-subject':
                open_window('GroupchatDetails',
                            contact=control.contact,
                            page='manage')
                return None

            if action_name == 'escape':
                if app.settings.get('escape_key_closes'):
                    self._chat_page.remove_chat(control.contact.account,
                                                control.contact.jid)
                    return None

            elif action_name == 'close-chat':
                self._chat_page.remove_chat(control.contact.account,
                                            control.contact.jid)
                return None

        if action_name == 'escape' and app.settings.get('escape_key_closes'):
            self.emit('delete-event', Gdk.Event())

        if action_name == 'restore-chat':
            self._chat_page.restore_chat()

        elif action_name == 'switch-next-chat':
            self.select_next_chat(Direction.NEXT)

        elif action_name == 'switch-prev-chat':
            self.select_next_chat(Direction.PREV)

        elif action_name == 'switch-next-unread-chat':
            self.select_next_chat(Direction.NEXT, unread_first=True)

        elif action_name == 'switch-prev-unread-chat':
            self.select_next_chat(Direction.PREV, unread_first=True)

        elif action_name.startswith('switch-chat-'):
            number = int(action_name[-1]) - 1
            self.select_chat_number(number)

        elif action_name.startswith('switch-workspace-'):
            number = int(action_name[-1]) - 1
            self._workspace_side_bar.activate_workspace_number(number)

        elif action_name == 'toggle-chat-list':
            self._toggle_chat_list()

        return None

    def _on_app_font_size_action(
            self,
            action: Gio.SimpleAction,
            _param: GLib.Variant
            ) -> None:

        action_name = action.get_name()
        if action_name == 'reset-app-font-size':
            app.settings.set_app_setting('app_font_size', None)
            app.css_config.apply_app_font_size()
            return

        app_font_size = app.settings.get('app_font_size')
        new_app_font_size = app_font_size
        if action_name == 'increase-app-font-size':
            new_app_font_size = app_font_size + 0.125
        elif action_name == 'decrease-app-font-size':
            new_app_font_size = app_font_size - 0.125

        # Clamp font size
        new_app_font_size = max(min(1.5, new_app_font_size), 1.0)

        if new_app_font_size == app_font_size:
            return

        app.settings.set_app_setting('app_font_size', new_app_font_size)
        app.css_config.apply_app_font_size()

    def _on_preview_action(self,
                           action: Gio.SimpleAction,
                           param: GLib.Variant
                           ) -> None:

        action_name = action.get_name()
        preview = app.preview_manager.get_preview(param.get_string())
        if preview is None:
            return

        if action_name == 'preview-download':
            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)

        elif action_name == 'preview-open':
            if preview.is_geo_uri:
                open_uri(preview.uri)
                return

            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)
                return

            assert preview.orig_path is not None
            open_file(preview.orig_path)

        elif action_name == 'preview-save-as':
            def _on_ok(paths: list[str]) -> None:
                if not paths:
                    ErrorDialog(
                        _('Could not save file'),
                        _('Could not save file to selected directory.'),
                        transient_for=self)
                    return

                target = paths[0]
                assert preview is not None
                assert preview.orig_path is not None

                target_path = Path(target)
                orig_ext = preview.orig_path.suffix
                new_ext = target_path.suffix
                if orig_ext != new_ext:
                    # Windows file chooser selects the full file name including
                    # extension. Starting to type will overwrite the extension
                    # as well. Restore the extension if it's lost.
                    target_path = target_path.with_suffix(orig_ext)
                dirname = target_path.parent
                if not os.access(dirname, os.W_OK):
                    ErrorDialog(
                        _('Directory "%s" is not writable') % dirname,
                        _('You do not have the proper permissions to '
                          'create files in this directory.'),
                        transient_for=self)
                    return

                shutil.copyfile(preview.orig_path, target_path)
                app.settings.set('last_save_dir', str(target_path.parent))

            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)
                return

            FileSaveDialog(_on_ok,
                           path=app.settings.get('last_save_dir'),
                           file_name=preview.filename,
                           transient_for=self)

        elif action_name == 'preview-open-folder':
            if not preview.orig_exists:
                app.preview_manager.download_content(preview, force=True)
                return

            assert preview.orig_path is not None
            show_in_folder(preview.orig_path)

        elif action_name == 'preview-copy-link':
            display = Gdk.Display.get_default()
            assert display is not None
            clipboard = Gtk.Clipboard.get_default(display)
            clipboard.set_text(preview.uri, -1)

        elif action_name == 'preview-open-link':
            if preview.is_aes_encrypted:
                if preview.is_geo_uri:
                    open_uri(preview.uri)
                    return

                assert preview.orig_path
                open_file(preview.orig_path)
            else:
                open_uri(preview.uri)

    def _on_show_offline(self,
                         action: Gio.SimpleAction,
                         value: GLib.Variant) -> None:

        action.set_state(value)
        app.settings.set('showoffline', value.get_boolean())

    def _on_sort_by_show(self,
                         action: Gio.SimpleAction,
                         value: GLib.Variant) -> None:

        action.set_state(value)
        app.settings.set('sort_by_show_in_roster', value.get_boolean())

    def _toggle_chat_list(self) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            if chat_list.is_visible():
                self._ui.toggle_chat_list_button.set_tooltip_text(
                    _('Show chat list'))
                self._ui.toggle_chat_list_icon.set_from_icon_name(
                    'go-next-symbolic', Gtk.IconSize.BUTTON)
            else:
                self._ui.toggle_chat_list_button.set_tooltip_text(
                    _('Hide chat list'))
                self._ui.toggle_chat_list_icon.set_from_icon_name(
                    'go-previous-symbolic', Gtk.IconSize.BUTTON)
        self._chat_page.toggle_chat_list()

    def _on_copy_message(self,
                         _action: Gio.SimpleAction,
                         param: GLib.Variant
                         ) -> None:

        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(param.get_string(), -1)

    @actionmethod
    def _on_retract_message(self,
                            _action: Gio.SimpleAction,
                            params: RetractMessageParam
                            ) -> None:

        def _on_retract(reason: str) -> None:
            client = app.get_client(params.account)
            client.get_module('MUC').retract_message(
                params.jid, params.stanza_id, reason or None)

        InputDialog(
            _('Retract Message'),
            _('Retract message?'),
            _('Why do you want to retract this message?'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               text=_('_Retract'),
                               callback=_on_retract)],
            input_str=_('Spam'),
            transient_for=app.window).show()

    def _on_delete_message_locally(self,
                                   _action: Gio.SimpleAction,
                                   param: GLib.Variant
                                   ) -> None:

        def _on_delete() -> None:
            log_line_id = param.get_uint32()
            app.storage.archive.delete_message_from_logs(log_line_id)
            control = self.get_control()
            control.remove_message(log_line_id)

        ConfirmationDialog(
            _('Delete Message'),
            _('Delete message locally?'),
            _('This message will be deleted from your local chat history'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Delete',
                               callback=_on_delete)],
            transient_for=app.window).show()

    def _on_window_motion_notify(self,
                                 _widget: Gtk.ApplicationWindow,
                                 _event: Gdk.EventMotion
                                 ) -> None:
        control = self.get_control()
        if not control.has_active_chat():
            return

        if self.get_property('has-toplevel-focus'):
            client = app.get_client(control.contact.account)
            chat_stack = self._chat_page.get_chat_stack()
            msg_action_box = chat_stack.get_message_action_box()
            client.get_module('Chatstate').set_mouse_activity(
                control.contact, msg_action_box.msg_textview.has_text)

    def _on_window_delete(self,
                          _widget: Gtk.ApplicationWindow,
                          _event: Gdk.Event
                          ) -> int:

        action = app.settings.get('action_on_close')
        if action == 'hide':
            self.hide()
            return Gdk.EVENT_STOP

        if action == 'minimize':
            self.minimize()
            return Gdk.EVENT_STOP

        if not app.settings.get('confirm_on_window_delete'):
            self.quit()
            return Gdk.EVENT_STOP

        def _on_ok(is_checked: bool) -> None:
            if is_checked:
                app.settings.set('confirm_on_window_delete', False)
            self.quit()

        ConfirmationCheckDialog(
            _('Quit Gajim'),
            _('You are about to quit Gajim'),
            _('Are you sure you want to quit Gajim?'),
            _('_Don’t ask again'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               text=_('_Quit'),
                               callback=_on_ok)]).show()

        return Gdk.EVENT_STOP

    def _on_window_state_changed(self,
                                 window: MainWindow,
                                 event: Gdk.EventWindowState) -> None:

        states = Gdk.WindowState.WITHDRAWN | Gdk.WindowState.ICONIFIED
        if states & event.changed_mask:
            is_withdrawn = bool(Gdk.WindowState.WITHDRAWN &
                                event.new_window_state)
            is_iconified = bool(Gdk.WindowState.ICONIFIED &
                                event.new_window_state)
            log.debug('Window state changed: ICONIFIED: %s, WITHDRAWN: %s',
                      is_iconified, is_withdrawn)

            app.settings.set('is_window_visible', not is_withdrawn)

    def _set_startup_finished(self) -> None:
        self._startup_finished = True
        self._chat_page.set_startup_finished()

    def _load_unread_counts(self) -> None:
        chats = app.storage.cache.get_unread()
        chat_list_stack = self._chat_page.get_chat_list_stack()

        for chat in chats:
            chat_list_stack.set_chat_unread_count(
                chat.account,
                chat.jid,
                chat.count)

    def show_account_page(self, account: str) -> None:
        self._app_side_bar.unselect_all()
        self._workspace_side_bar.unselect_all()
        self._account_side_bar.activate_account_page(account)
        self._main_stack.show_account(account)

    def get_active_workspace(self) -> str | None:
        return self._workspace_side_bar.get_active_workspace()

    def is_chat_active(self, account: str, jid: JID) -> bool:
        if not self.has_toplevel_focus():
            return False
        if self._main_stack.get_visible_page_name() != 'chats':
            return False
        return self._chat_page.is_chat_selected(account, jid)

    def highlight_dnd_targets(self, drag_row: Any, highlight: bool) -> None:
        if isinstance(drag_row, ChatListRow):
            chat_list_stack = self._chat_page.get_chat_list_stack()
            workspace = self.get_active_workspace()
            if workspace is None:
                return

            if drag_row.is_pinned:
                chat_list = chat_list_stack.get_chatlist(workspace)
                for row in chat_list.get_chat_list_rows():
                    if not row.is_pinned:
                        continue

                    if highlight:
                        row.get_style_context().add_class(
                            'dnd-target-chatlist')
                    else:
                        row.get_style_context().remove_class(
                            'dnd-target-chatlist')

        if highlight:
            self._workspace_side_bar.get_style_context().add_class(
                'dnd-target')
        else:
            self._workspace_side_bar.get_style_context().remove_class(
                'dnd-target')

    def _add_workspace(self,
                       _action: Gio.SimpleAction,
                       param: GLib.Variant) -> None:

        workspace_id = param.get_string()
        if workspace_id:
            self.add_workspace(workspace_id)

    def add_workspace(self,
                      workspace_id: str | None = None,
                      switch: bool = True) -> str:

        if workspace_id is None:
            workspace_id = app.settings.add_workspace(_('My Workspace'))

        self._workspace_side_bar.add_workspace(workspace_id)
        self._chat_page.add_chat_list(workspace_id)

        if self._startup_finished and switch:
            self.activate_workspace(workspace_id)
            self._workspace_side_bar.store_workspace_order()

        return workspace_id

    def _edit_workspace(self,
                        _action: Gio.SimpleAction,
                        param: GLib.Variant) -> None:
        workspace_id = param.get_string() or None
        if workspace_id is None:
            workspace_id = self.get_active_workspace()
        open_window('WorkspaceDialog', workspace_id=workspace_id)

    def _remove_workspace(self,
                          _action: Gio.SimpleAction,
                          param: GLib.Variant) -> None:

        workspace_id = param.get_string() or None
        if workspace_id is None:
            workspace_id = self.get_active_workspace()

        if workspace_id is not None:
            self.remove_workspace(workspace_id)

    def remove_workspace(self, workspace_id: str) -> None:
        if app.settings.get_workspace_count() == 1:
            log.warning('Tried to remove the only workspace')
            return

        was_active = self.get_active_workspace() == workspace_id
        chat_list = self.get_chat_list(workspace_id)
        open_chats = chat_list.get_open_chats()

        def _continue_removing_workspace():
            new_workspace_id = self._workspace_side_bar.get_other_workspace(
                workspace_id)
            if new_workspace_id is None:
                log.warning('No other workspaces found')
                return

            for open_chat in open_chats:
                params = ChatListEntryParam(
                    workspace_id=new_workspace_id,
                    source_workspace_id=workspace_id,
                    account=open_chat['account'],
                    jid=open_chat['jid'])
                self.activate_action('move-chat-to-workspace',
                                     params.to_variant())

            if was_active:
                self.activate_workspace(new_workspace_id)

            self._workspace_side_bar.remove_workspace(workspace_id)
            self._chat_page.remove_chat_list(workspace_id)
            app.settings.remove_workspace(workspace_id)

        if open_chats:
            ConfirmationDialog(
                _('Remove Workspace'),
                _('Remove Workspace'),
                _('This workspace contains chats. All chats will be moved to '
                  'the next workspace. Remove anyway?'),
                [DialogButton.make('Cancel',
                                   text=_('_No')),
                 DialogButton.make('Remove',
                                   callback=_continue_removing_workspace)]
            ).show()
            return

        # No chats in chat list, it is save to remove this workspace
        _continue_removing_workspace()

    def _activate_workspace(self,
                            _action: Gio.SimpleAction,
                            param: GLib.Variant) -> None:

        workspace_id = param.get_string()
        if workspace_id:
            self.activate_workspace(workspace_id)

    def activate_workspace(self, workspace_id: str) -> None:
        self._app_side_bar.unselect_all()
        self._account_side_bar.unselect_all()
        self._main_stack.show_chats(workspace_id)
        self._workspace_side_bar.activate_workspace(workspace_id)

        # Show chatlist if it is hidden
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.get_current_chat_list()
        if chat_list is not None:
            if not chat_list.is_visible():
                self._toggle_chat_list()

    def update_workspace(self, workspace_id: str) -> None:
        self._chat_page.update_workspace(workspace_id)
        self._workspace_side_bar.update_avatar(workspace_id)

    def get_chat_list(self, workspace_id: str) -> ChatList:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        return chat_list_stack.get_chatlist(workspace_id)

    def _get_suitable_workspace(self,
                                account: str,
                                jid: JID,
                                private_chat: bool = False
                                ) -> str:

        if private_chat:
            # Try to add private chat to the same workspace the MUC resides in
            chat_list_stack = self._chat_page.get_chat_list_stack()
            chat_list = chat_list_stack.find_chat(account, jid.new_as_bare())
            if chat_list is not None:
                return chat_list.workspace_id

        default = app.settings.get_account_setting(account, 'default_workspace')
        workspaces = app.settings.get_workspaces()
        if default in workspaces:
            return default

        workspace_id = self.get_active_workspace()
        if workspace_id is not None:
            return workspace_id
        return self._workspace_side_bar.get_first_workspace()

    def _add_group_chat(self,
                        _action: Gio.SimpleAction,
                        param: GLib.Variant) -> None:

        account, jid, select = param.unpack()
        self.add_group_chat(account, JID.from_string(jid), select)

    def add_group_chat(self,
                       account: str,
                       jid: JID,
                       select: bool = False
                       ) -> None:

        workspace_id = self._get_suitable_workspace(account, jid)
        self._chat_page.add_chat_for_workspace(workspace_id,
                                               account,
                                               jid,
                                               'groupchat',
                                               select=select)

    def _add_chat(self,
                  _action: Gio.SimpleAction,
                  param: GLib.Variant) -> None:

        params = AddChatActionParams.from_variant(param)
        self.add_chat(params.account, params.jid, params.type, params.select)

    def add_chat(self,
                 account: str,
                 jid: JID,
                 type_: str,
                 select: bool = False,
                 message: str | None = None
                 ) -> None:

        workspace_id = self._get_suitable_workspace(account, jid)
        self._chat_page.add_chat_for_workspace(workspace_id,
                                               account,
                                               jid,
                                               type_,
                                               select=select,
                                               message=message)

    def add_private_chat(self,
                         account: str,
                         jid: JID,
                         select: bool = False
                         ) -> None:

        workspace_id = self._get_suitable_workspace(account,
                                                    jid,
                                                    private_chat=True)
        self._chat_page.add_chat_for_workspace(workspace_id,
                                               account,
                                               jid,
                                               'pm',
                                               select=select)

    def clear_chat_list_row(self, account: str, jid: JID) -> None:
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list = chat_list_stack.find_chat(account, jid)
        if chat_list is not None:
            chat_list.clear_chat_list_row(account, jid)

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

    @actionmethod
    def _add_to_roster(self,
                       _action: Gio.SimpleAction,
                       params: AccountJidParam) -> None:

        open_window('AddContact', account=params.account, jid=params.jid)

    def show_app_page(self) -> None:
        self._account_side_bar.unselect_all()
        self._workspace_side_bar.unselect_all()
        self._main_stack.show_app_page()

    def add_app_message(self,
                        category: str,
                        new_version: str | None = None,
                        new_setup_url: str | None = None
                        ) -> None:

        self._app_page.add_app_message(category, new_version, new_setup_url)

    def get_control(self) -> ChatControl:
        return self._chat_page.get_control()

    def chat_exists(self, account: str, jid: JID) -> bool:
        return self._chat_page.chat_exists(account, jid)

    def is_message_correctable(self,
                               contact: types.ChatContactT,
                               message_id: str
                               ) -> bool:

        chat_stack = self._chat_page.get_chat_stack()
        last_message_id = chat_stack.get_last_message_id(contact)
        if last_message_id is None or last_message_id != message_id:
            return False

        message_row = app.storage.archive.get_last_correctable_message(
            contact.account, contact.jid, last_message_id)
        return message_row is not None

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

    def mark_as_read(self,
                     account: str,
                     jid: JID,
                     send_marker: bool = True
                     ) -> None:

        unread_count = self.get_chat_unread_count(account,
                                                  jid,
                                                  include_silent=True)

        set_urgency_hint(self, False)
        control = self.get_control()
        if control.has_active_chat():
            # Reset jump to bottom button unread counter
            control.mark_as_read()

        # Reset chat list unread counter (emits unread-count-changed)
        chat_list_stack = self._chat_page.get_chat_list_stack()
        chat_list_stack.mark_as_read(account, jid)

        if not send_marker or not unread_count:
            # Read marker must be sent only once
            return

        last_message = app.storage.archive.get_last_conversation_line(
            account, jid)
        if last_message is None:
            return

        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant)
        client.get_module('ChatMarkers').send_displayed_marker(
            contact,
            last_message.message_id,
            last_message.stanza_id)

    def _on_window_active(self,
                          window: Gtk.ApplicationWindow,
                          _param: Any
                          ) -> None:

        if not window.is_active():
            return

        set_urgency_hint(self, False)
        control = self.get_control()
        if not control.has_active_chat():
            return

        if control.get_autoscroll():
            self.mark_as_read(control.contact.account, control.contact.jid)

    def get_preferred_ft_method(self,
                                contact: types.ChatContactT
                                ) -> str | None:

        ft_pref = app.settings.get_account_setting(
            contact.account,
            'filetransfer_preference')
        httpupload_enabled = app.window.get_action_enabled(
            'send-file-httpupload')
        jingle_enabled = app.window.get_action_enabled('send-file-jingle')

        if isinstance(contact, GroupchatContact):
            if httpupload_enabled:
                return 'httpupload'
            return None

        if httpupload_enabled and jingle_enabled:
            return ft_pref

        if httpupload_enabled:
            return 'httpupload'

        if jingle_enabled:
            return 'jingle'

        return None

    def show_add_join_groupchat(self,
                                account: str,
                                jid: str,
                                nickname: str | None = None,
                                password: str | None = None
                                ) -> None:

        jid_ = JID.from_string(jid)
        if not self.chat_exists(account, jid_):
            client = app.get_client(account)
            client.get_module('MUC').join(
                jid_, nick=nickname, password=password)

        self.add_group_chat(account, jid_, select=True)

    def start_chat_from_jid(self,
                            account: str,
                            jid: str,
                            message: str | None = None
                            ) -> None:

        jid_ = JID.from_string(jid)
        if self.chat_exists(account, jid_):
            self.select_chat(account, jid_)
            if message is not None:
                message_input = self.get_chat_stack().get_message_input()
                message_input.insert_text(message)
            return

        app.app.activate_action(
            'start-chat', GLib.Variant('as', [str(jid), message or '']))

    @staticmethod
    def contact_info(account: str, jid: str) -> None:
        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        open_window('ContactInfo', account=account, contact=contact)

    @staticmethod
    def execute_command(account: str, jid: str) -> None:
        # TODO: Resource?
        open_window('AdHocCommands', account=account, jid=jid)

    def block_contact(self, account: str, jid: str) -> None:
        client = app.get_client(account)

        contact = client.get_module('Contacts').get_contact(jid)
        assert isinstance(contact, BareContact)
        if contact.is_blocked:
            client.get_module('Blocking').unblock([jid])
            return

        # TODO: Keep "confirm_block" setting?
        def _block_contact(report: str | None = None) -> None:
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
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant)
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
        if not accounts:
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

    def _on_message_received(self, event: events.MessageReceived) -> None:
        if not self.chat_exists(event.account, event.jid):
            if not event.properties.body:
                # Don’t open control on chatstate etc.
                return

            if event.properties.is_muc_pm:
                self.add_private_chat(event.account,
                                      event.properties.jid)

            else:
                jid = event.properties.jid.new_as_bare()
                self.add_chat(event.account, jid, 'contact')

    def _on_read_state_sync(self, event: events.ReadStateSync) -> None:
        last_message = app.storage.archive.get_last_conversation_line(
            event.account, event.jid)

        if last_message is None:
            return

        if event.marker_id not in (last_message.message_id,
                                   last_message.stanza_id):
            return

        self.mark_as_read(event.account, event.jid, send_marker=False)

    def _on_call_started(self, event: events.CallStarted) -> None:
        # Make sure there is only one window
        win = get_app_window('CallWindow')
        if win is not None:
            win.destroy()
        CallWindow(event.account, event.resource_jid)

    def _on_jingle_request(self, event: events.JingleRequestReceived) -> None:
        if not self.chat_exists(event.account, event.jid):
            for item in event.contents:
                if item.media not in ('audio', 'video'):
                    return
                self.add_chat(event.account, event.jid, 'contact')
                break

    def _on_file_request(self, event: events.FileRequestReceivedEvent) -> None:
        if not self.chat_exists(event.account, event.jid):
            self.add_chat(event.account, event.jid, 'contact')

    def quit(self) -> None:
        save_main_window_position()
        window_width, window_height = self.get_size()
        app.settings.set('mainwin_width', window_width)
        app.settings.set('mainwin_height', window_height)
        app.settings.save()

        def on_continue2(message: str | None) -> None:
            if 'file_transfers' not in app.interface.instances:
                app.app.start_shutdown(message=message)
                return
            # check if there is an active file transfer
            files_props = app.interface.instances['file_transfers'].files_props
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

        def on_continue(message: str | None) -> None:
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

        on_continue('')

    def _on_plugin_updates_available(self,
                                     _repository: PluginRepository,
                                     _signal_name: str,
                                     manifests: list[PluginManifest]) -> None:
        self._app_page.add_plugin_update_message(manifests)

    def _on_plugin_auto_update_finished(self,
                                        _repository: PluginRepository,
                                        _signal_name: str) -> None:
        self.add_app_message('plugin-updates-finished')
