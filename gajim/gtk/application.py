# Copyright (C) 2003-2017 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
#                    Norman Rasmussen <norman AT rasmussen.co.za>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    James Newton <redshodan AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2016-2017 Emmanuel Gil Peyrot <linkmauve AT linkmauve.fr>
#                         Philipp Hörist <philipp AT hoerist.com>
#
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
from typing import Callable
from typing import cast
from typing import Optional

import os
import sys
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from urllib.parse import unquote

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import InvalidJid

import gajim
from gajim.common import app
from gajim.common import configpaths
from gajim.common import events
from gajim.common import ged
from gajim.common import idle
from gajim.common.application import CoreApplication
from gajim.common.const import GAJIM_FAQ_URI
from gajim.common.const import GAJIM_SUPPORT_JID
from gajim.common.const import GAJIM_WIKI_URI
from gajim.common.exceptions import GajimGeneralException
from gajim.common.helpers import load_json
from gajim.common.helpers import open_uri
from gajim.common.i18n import _

from gajim.gtk import menus
from gajim.gtk import structs
from gajim.gtk.about import AboutDialog
from gajim.gtk.accounts import AccountsWindow
from gajim.gtk.avatar import AvatarStorage
from gajim.gtk.builder import get_builder
from gajim.gtk.const import ACCOUNT_ACTIONS
from gajim.gtk.const import ALWAYS_ACCOUNT_ACTIONS
from gajim.gtk.const import APP_ACTIONS
from gajim.gtk.const import FEATURE_ACCOUNT_ACTIONS
from gajim.gtk.const import MuteState
from gajim.gtk.const import ONLINE_ACCOUNT_ACTIONS
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import ShortcutsWindow
from gajim.gtk.discovery import ServiceDiscoveryWindow
from gajim.gtk.start_chat import StartChatDialog
from gajim.gtk.util import get_app_window
from gajim.gtk.util import get_app_windows
from gajim.gtk.util import load_user_iconsets
from gajim.gtk.util import open_window

ActionListT = list[tuple[str,
                         Callable[[Gio.SimpleAction, GLib.Variant], Any]]]


class GajimApplication(Gtk.Application, CoreApplication):
    '''Main class handling activation and command line.'''

    def __init__(self):
        CoreApplication.__init__(self)
        flags = (Gio.ApplicationFlags.HANDLES_COMMAND_LINE |
                 Gio.ApplicationFlags.CAN_OVERRIDE_APP_ID)
        Gtk.Application.__init__(self,
                                 application_id='org.gajim.Gajim',
                                 flags=flags)

        # required to track screensaver state
        self.props.register_session = True

        self.add_main_option(
            'version',
            ord('V'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Show the application's version"))

        self.add_main_option(
            'quiet',
            ord('q'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Show only critical errors'))

        self.add_main_option(
            'separate',
            ord('s'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Separate profile files completely '
              '(even history database and plugins)'))

        self.add_main_option(
            'verbose',
            ord('v'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Print XML stanzas and other debug information'))

        self.add_main_option(
            'profile',
            ord('p'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _('Use defined profile in configuration directory'),
            'NAME')

        self.add_main_option(
            'config-path',
            ord('c'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _('Set configuration directory'),
            'PATH')

        self.add_main_option(
            'loglevel',
            ord('l'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _('Configure logging system'),
            'LEVEL')

        self.add_main_option(
            'warnings',
            ord('w'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Show all warnings'))

        self.add_main_option(
            'gdebug',
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Sets an environment variable so '
              'GLib debug messages are printed'))

        self.add_main_option(
            'cprofile',
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Profile application with cprofile'))

        self.add_main_option(
            'start-chat', 0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Start a new chat'))

        self.add_main_option(
            'show', 0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Show Gajim'))

        self.add_main_option_entries(self._get_remaining_entry())

        self.connect('handle-local-options', self._handle_local_options)
        self.connect('command-line', self._command_line)
        self.connect('shutdown', self._shutdown)

        self.interface = None

        GLib.set_prgname('org.gajim.Gajim')
        if GLib.get_application_name() != 'Gajim':
            GLib.set_application_name('Gajim')

    @staticmethod
    def _get_remaining_entry():
        option = GLib.OptionEntry()
        option.arg = GLib.OptionArg.STRING_ARRAY
        option.arg_data = None
        option.arg_description = ('[URI …]')
        option.flags = GLib.OptionFlags.NONE
        option.long_name = GLib.OPTION_REMAINING
        option.short_name = 0
        return [option]

    def _startup(self) -> None:
        if sys.platform in ('win32', 'darwin'):
            # Changing the PANGOCAIRO_BACKEND is necessary on Windows/MacOS
            # to render colored emoji glyphs
            os.environ['PANGOCAIRO_BACKEND'] = 'fontconfig'

        self._init_core()

        icon_theme = Gtk.IconTheme.get_default()
        icon_theme.append_search_path(str(configpaths.get('ICONS')))
        load_user_iconsets()

        builder = get_builder('application_menu.ui')
        self.set_menubar(cast(Gio.Menu, builder.get_object('menubar')))

        from gajim.gtk import notification
        notification.init()

        self.avatar_storage = AvatarStorage()

        app.load_css_config()

        idle.Monitor.set_interval(app.settings.get('autoawaytime') * 60,
                                  app.settings.get('autoxatime') * 60)

        from gajim.gui_interface import Interface

        self.interface = Interface()
        self.interface.run(self)

        from gajim.gtk.status_icon import StatusIcon
        self.systray = StatusIcon()

        self._add_app_actions()
        accounts = app.settings.get_accounts()
        for account in accounts:
            self.add_account_actions(account)

        self._load_shortcuts()
        menus.build_accounts_menu()
        self.update_app_actions_state()

        self.register_event('feature-discovered',
                            ged.CORE,
                            self._on_feature_discovered)

        from gajim.gtk.main import MainWindow
        MainWindow()

        GLib.timeout_add(100, self._auto_connect)

    def _open_uris(self, uris: list[str]) -> None:
        accounts = app.settings.get_active_accounts()
        if not accounts:
            return

        for uri in uris:
            app.log('uri_handler').info('open %s', uri)
            if not uri.startswith('xmpp:'):
                continue
            # remove xmpp:
            uri = uri[5:]
            try:
                jid, cmd = uri.split('?')
            except ValueError:
                # No query argument
                jid, cmd = uri, 'message'

            try:
                jid = JID.from_string(jid)
            except InvalidJid as error:
                app.log('uri_handler').warning('Invalid JID %s: %s', uri, error)
                continue

            if cmd == 'join' and jid.resource:
                app.log('uri_handler').warning('Invalid MUC JID %s', uri)
                continue

            jid = str(jid)

            if cmd == 'join':
                if len(accounts) == 1:
                    self.activate_action(
                        'open-chat',
                        GLib.Variant('as', [accounts[0], jid]))
                else:
                    self.activate_action(
                        'start-chat', GLib.Variant('as', [jid, '']))

            elif cmd == 'roster':
                self.activate_action('add-contact', GLib.Variant('s', jid))

            elif cmd.startswith('message'):
                attributes = cmd.split(';')
                message = None
                for key in attributes:
                    if not key.startswith('body'):
                        continue
                    try:
                        message = unquote(key.split('=')[1])
                    except Exception:
                        app.log('uri_handler').error('Invalid URI: %s', cmd)

                app.window.start_chat_from_jid(accounts[0], jid, message)

    def _shutdown(self, _application: GajimApplication) -> None:
        self._shutdown_core()

    def _quit_app(self) -> None:
        self.quit()

    def _command_line(self,
                      _application: GajimApplication,
                      command_line: Gio.ApplicationCommandLine) -> int:
        '''Handles command line options not related to the startup of Gajim.
        '''

        options = command_line.get_options_dict()

        remote_commands = [
            ('start-chat', GLib.Variant('as', ['', ''])),
            ('show', None)
        ]

        remaining = options.lookup_value(GLib.OPTION_REMAINING,
                                         GLib.VariantType.new('as'))

        for cmd, parameter in remote_commands:
            if options.contains(cmd):
                self.activate_action(cmd, parameter)
                return 0

        if remaining is not None:
            self._open_uris(remaining.unpack())
            return 0

        return 0

    def _handle_local_options(self,
                              _application: Gtk.Application,
                              options: GLib.VariantDict) -> int:

        if options.contains('version'):
            print(gajim.__version__)
            return 0

        profile = options.lookup_value('profile')
        if profile is not None:
            # Incorporate profile name into application id
            # to have a single app instance for each profile.
            profile = profile.get_string()
            app_id = '%s.%s' % (self.get_application_id(), profile)
            self.set_application_id(app_id)
            configpaths.set_profile(profile)

        self.register()
        if self.get_is_remote():
            print('Gajim is already running. '
                  'The primary instance will handle remote commands')
            return -1

        self._core_command_line(options)
        self._startup()
        return -1

    def _add_app_actions(self) -> None:
        for action in APP_ACTIONS:
            action_name, variant = action
            if variant is not None:
                variant = GLib.VariantType.new(variant)

            act = Gio.SimpleAction.new(action_name, variant)
            self.add_action(act)

        self._connect_app_actions()

    def _connect_app_actions(self) -> None:
        actions: ActionListT = [
            ('quit', self._on_quit_action),
            ('add-account', self._on_add_account_action),
            ('manage-proxies', self._on_manage_proxies_action),
            ('preferences', self._on_preferences_action),
            ('plugins', self._on_plugins_action),
            ('xml-console', self._on_xml_console_action),
            ('file-transfer', self._on_file_transfer_action),
            ('shortcuts', self._on_shortcuts_action),
            ('features', self._on_features_action),
            ('content', self._on_content_action),
            ('join-support-chat', self._on_join_support_chat),
            ('about', self._on_about_action),
            ('faq', self._on_faq_action),
            ('start-chat', self._on_new_chat_action),
            ('accounts', self._on_accounts_action),
            ('add-contact', self._on_add_contact_action),
            ('copy-text', self._on_copy_text_action),
            ('open-link', self._on_open_link_action),
            ('remove-history', self._on_remove_history_action),
            ('create-groupchat', self._on_create_groupchat_action),
            ('forget-groupchat', self._on_forget_groupchat_action),
            ('open-chat', self._on_open_chat_action),
            ('mute-chat', self._on_mute_chat_action),
            ('show', self._on_show),
        ]

        for action in actions:
            action_name, func = action
            act = self.lookup_action(action_name)
            assert act is not None
            act.connect('activate', func)
            self.add_action(act)

    def add_account_actions(self, account: str) -> None:
        for action_name, type_ in ACCOUNT_ACTIONS:
            account_action_name = f'{account}-{action_name}'
            if self.has_action(account_action_name):
                raise ValueError('Trying to add action more than once')

            act = Gio.SimpleAction.new(account_action_name,
                                       GLib.VariantType.new(type_))
            act.set_enabled(action_name in ALWAYS_ACCOUNT_ACTIONS)
            self.add_action(act)

        self._connect_account_actions(account)

    def _connect_account_actions(self, account: str) -> None:
        actions = [
            ('bookmarks', self._on_bookmarks_action),
            ('add-contact', self._on_add_contact_account_action),
            ('services', self._on_services_action),
            ('profile', self._on_profile_action),
            ('server-info', self._on_server_info_action),
            ('archive', self._on_archive_action),
            ('pep-config', self._on_pep_config_action),
            ('sync-history', self._on_sync_history_action),
            ('blocking', self._on_blocking_action),
            ('open-event', self._on_open_event_action),
            ('mark-as-read', self._on_mark_as_read_action),
            ('import-contacts', self._on_import_contacts_action),
            ('export-history', self._on_export_history),
        ]

        for action_name, func in actions:
            account_action_name = f'{account}-{action_name}'
            act = self.lookup_action(account_action_name)
            assert act is not None
            act.connect('activate', func)

    def remove_account_actions(self, account: str) -> None:
        for action_name in self.list_actions():
            if action_name.startswith(f'{account}-'):
                self.remove_action(action_name)

    def set_action_state(self, action_name: str, state: bool) -> None:
        action = self.lookup_action(action_name)
        assert isinstance(action, Gio.SimpleAction)
        action.set_enabled(state)

    def set_account_actions_state(self,
                                  account: str,
                                  new_state: bool = False) -> None:

        for action_name in ONLINE_ACCOUNT_ACTIONS:
            self.set_action_state(f'{account}-{action_name}', new_state)

        if not new_state:
            for action_name in FEATURE_ACCOUNT_ACTIONS:
                self.set_action_state(f'{account}-{action_name}', new_state)

    def update_app_actions_state(self) -> None:
        active_accounts = bool(app.get_connected_accounts(exclude_local=True))
        self.set_action_state('create-groupchat', active_accounts)

        enabled_accounts = bool(app.settings.get_active_accounts())
        self.set_action_state('start-chat', enabled_accounts)

    def _load_shortcuts(self) -> None:
        default_path = configpaths.get('DATA') / 'other' / 'shortcuts.json'
        shortcuts = load_json(default_path)
        assert shortcuts is not None

        user_path = configpaths.get('MY_SHORTCUTS')
        user_shortcuts = {}
        if user_path.exists():
            app.log('app').info('Load user shortcuts')
            user_shortcuts = load_json(user_path, default={})

        shortcuts.update(user_shortcuts)

        for action, accels in shortcuts.items():
            self.set_accels_for_action(action, accels)

    def _on_feature_discovered(self, event: events.FeatureDiscovered) -> None:
        if event.feature == Namespace.MAM_2:
            action = '%s-archive' % event.account
            self.set_action_state(action, True)
        elif event.feature == Namespace.BLOCKING:
            action = '%s-blocking' % event.account
            self.set_action_state(action, True)
            action = '%s-block-contact' % event.account
            self.set_action_state(action, True)

    def create_account(self,
                       account: str,
                       username: str,
                       domain: str,
                       password: str,
                       proxy_name: str | None,
                       custom_host: tuple[str,
                                          ConnectionProtocol,
                                          ConnectionType] | None,
                       anonymous: bool = False
                       ) -> None:

        CoreApplication.create_account(self,
                                       account,
                                       username,
                                       domain,
                                       password,
                                       proxy_name,
                                       custom_host,
                                       anonymous)

        app.css_config.refresh()

        # Action must be added before account window is updated
        self.add_account_actions(account)

        window = cast(AccountsWindow | None, get_app_window('AccountsWindow'))
        if window is not None:
            window.add_account(account)

    def enable_account(self, account: str) -> None:
        CoreApplication.enable_account(self, account)
        menus.build_accounts_menu()
        self.update_app_actions_state()
        window = cast(AccountsWindow | None, get_app_window('AccountsWindow'))
        if window is not None:
            window.enable_account(account, True)

    def disable_account(self, account: str) -> None:
        for win in get_app_windows(account):
            # Close all account specific windows, except the RemoveAccount
            # dialog. It shows if the removal was successful.
            if type(win).__name__ == 'RemoveAccount':
                continue
            win.destroy()

        CoreApplication.disable_account(self, account)

        menus.build_accounts_menu()
        self.update_app_actions_state()

    def remove_account(self, account: str) -> None:
        CoreApplication.remove_account(self, account)

        self.remove_account_actions(account)

        window = cast(AccountsWindow | None, get_app_window('AccountsWindow'))
        if window is not None:
            window.remove_account(account)

    # Action Callbacks

    @staticmethod
    def _on_add_contact_action(_action: Gio.SimpleAction,
                               param: GLib.Variant) -> None:
        jid = param.get_string() or None
        if jid is not None:
            jid = JID.from_string(jid)
        open_window('AddContact', account=None, jid=jid)

    @staticmethod
    def _on_preferences_action(_action: Gio.SimpleAction,
                               _param: Optional[GLib.Variant]) -> None:
        open_window('Preferences')

    @staticmethod
    def _on_plugins_action(_action: Gio.SimpleAction,
                           _param: Optional[GLib.Variant]) -> None:
        open_window('PluginsWindow')

    @staticmethod
    def _on_accounts_action(_action: Gio.SimpleAction,
                            param: GLib.Variant) -> None:
        window = open_window('AccountsWindow')
        account = param.get_string()
        if account:
            window.select_account(account)

    @staticmethod
    def _on_bookmarks_action(_action: Gio.SimpleAction,
                             param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('Bookmarks', account=account)

    @staticmethod
    def _on_quit_action(_action: Gio.SimpleAction,
                        _param: Optional[GLib.Variant]) -> None:
        app.window.quit()

    @staticmethod
    def _on_new_chat_action(_action: Gio.SimpleAction,
                            param: GLib.Variant) -> None:

        jid, initial_message = param.get_strv()
        open_window('StartChatDialog',
                    initial_jid=jid or None,
                    initial_message=initial_message or None)

    @staticmethod
    def _on_profile_action(_action: Gio.SimpleAction,
                           param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('ProfileWindow', account=account)

    @staticmethod
    def _on_services_action(_action: Gio.SimpleAction,
                            param: GLib.Variant) -> None:
        account = param.get_string()
        server_jid = app.settings.get_account_setting(account, 'hostname')
        if account not in app.interface.instances:
            app.interface.instances[account] = {'disco': {}}

        disco = app.interface.instances[account]['disco']
        if server_jid in disco:
            disco[server_jid].window.present()
        else:
            try:
                # Object will add itself to the window dict
                ServiceDiscoveryWindow(account, address_entry=True)
            except GajimGeneralException:
                pass

    @staticmethod
    def _on_create_groupchat_action(_action: Gio.SimpleAction,
                                    param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('CreateGroupchatWindow', account=account or None)

    @staticmethod
    def _on_add_contact_account_action(_action: Gio.SimpleAction,
                                       param: GLib.Variant) -> None:
        account, jid = param.get_strv()
        if jid:
            jid = JID.from_string(jid)
        open_window('AddContact', account=account or None, jid=jid or None)

    @staticmethod
    def _on_add_account_action(_action: Gio.SimpleAction,
                               _param: Optional[GLib.Variant]) -> None:
        open_window('AccountWizard')

    @staticmethod
    def _on_import_contacts_action(_action: Gio.SimpleAction,
                                   param: GLib.Variant) -> None:
        open_window('SynchronizeAccounts', account=param.get_string())

    @staticmethod
    def _on_export_history(_action: Gio.SimpleAction,
                           param: GLib.Variant) -> None:
        open_window('HistoryExport', account=param.get_string())

    @staticmethod
    def _on_pep_config_action(_action: Gio.SimpleAction,
                              param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('PEPConfig', account=account)

    @staticmethod
    def _on_archive_action(_action: Gio.SimpleAction,
                           param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('MamPreferences', account=account)

    @staticmethod
    def _on_blocking_action(_action: Gio.SimpleAction,
                            param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('BlockingList', account=account)

    @staticmethod
    def _on_sync_history_action(_action: Gio.SimpleAction,
                                param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('HistorySyncAssistant',
                    account=account)

    @staticmethod
    def _on_server_info_action(_action: Gio.SimpleAction,
                               param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('ServerInfo', account=account)

    @staticmethod
    def _on_xml_console_action(_action: Gio.SimpleAction,
                               _param: Optional[GLib.Variant]) -> None:
        open_window('XMLConsoleWindow')

    @staticmethod
    def _on_manage_proxies_action(_action: Gio.SimpleAction,
                                  _param: Optional[GLib.Variant]) -> None:
        open_window('ManageProxies')

    @staticmethod
    def _on_content_action(_action: Gio.SimpleAction,
                           _param: Optional[GLib.Variant]) -> None:
        open_uri(GAJIM_WIKI_URI)

    @staticmethod
    def _on_join_support_chat(_action: Gio.SimpleAction,
                              _param: Optional[GLib.Variant]) -> None:
        accounts = app.settings.get_active_accounts()
        if len(accounts) == 1:
            app.window.show_add_join_groupchat(
                accounts[0], GAJIM_SUPPORT_JID)
            return
        open_window('StartChatDialog', initial_jid=GAJIM_SUPPORT_JID)

    @staticmethod
    def _on_faq_action(_action: Gio.SimpleAction,
                       _param: Optional[GLib.Variant]) -> None:
        open_uri(GAJIM_FAQ_URI)

    @staticmethod
    def _on_shortcuts_action(_action: Gio.SimpleAction,
                             _param: Optional[GLib.Variant]) -> None:
        ShortcutsWindow()

    @staticmethod
    def _on_features_action(_action: Gio.SimpleAction,
                            _param: Optional[GLib.Variant]) -> None:
        open_window('Features')

    @staticmethod
    def _on_about_action(_action: Gio.SimpleAction,
                         _param: Optional[GLib.Variant]) -> None:
        AboutDialog()

    @staticmethod
    def _on_file_transfer_action(_action: Gio.SimpleAction,
                                 _param: Optional[GLib.Variant]) -> None:

        ft = app.interface.instances['file_transfers']
        if ft.window.get_property('visible'):
            ft.window.present()
        else:
            ft.window.show_all()

    @staticmethod
    @structs.actionfunction
    def _on_open_event_action(_action: Gio.SimpleAction,
                              params: structs.OpenEventActionParams) -> None:

        if params.type in ('connection-failed',
                           'subscription-request',
                           'unsubscribed',
                           'group-chat-invitation',
                           'server-shutdown'):

            app.window.show_account_page(params.account)

        elif params.type in ('incoming-message',
                             'incoming-call',
                             'file-transfer'):

            assert params.jid
            jid = JID.from_string(params.jid)
            app.window.select_chat(params.account, jid)

        app.window.present_with_time(Gtk.get_current_event_time())

    @structs.actionmethod
    def _on_mark_as_read_action(self,
                                _action: Gio.SimpleAction,
                                params: structs.AccountJidParam) -> None:

        app.window.mark_as_read(params.account, params.jid)

    @staticmethod
    def _on_open_link_action(_action: Gio.SimpleAction,
                             param: GLib.Variant) -> None:
        account, uri = param.get_strv()
        open_uri(uri, account=account)

    @staticmethod
    def _on_copy_text_action(_action: Gio.SimpleAction,
                             param: GLib.Variant) -> None:
        text = param.get_string()
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(text, -1)

    @staticmethod
    def _on_open_chat_action(_action: Gio.SimpleAction,
                             param: GLib.Variant) -> None:
        account, jid = param.get_strv()
        app.window.start_chat_from_jid(account, jid)

    @staticmethod
    @structs.actionfunction
    def _on_mute_chat_action(_action: Gio.SimpleAction,
                             params: structs.MuteContactParam
                             ) -> None:

        client = app.get_client(params.account)
        contact = client.get_module('Contacts').get_contact(params.jid)

        if params.state == MuteState.UNMUTE:
            contact.settings.set('mute_until', None)
            return

        until = datetime.now(timezone.utc) + timedelta(minutes=params.state)
        contact.settings.set('mute_until', until.isoformat())

    @staticmethod
    @structs.actionfunction
    def _on_remove_history_action(_action: Gio.SimpleAction,
                                  params: structs.RemoveHistoryActionParams
                                  ) -> None:
        def _remove() -> None:
            app.storage.archive.remove_history(params.account, params.jid)
            control = app.window.get_control()

            if not control.is_loaded(params.account, params.jid):
                return

            control.reset_view()

        ConfirmationDialog(
            _('Remove Chat History'),
            _('Remove Chat History?'),
            _('Do you really want to remove your chat history for this chat?'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               callback=_remove)],
            transient_for=app.window).show()

    @staticmethod
    @structs.actionfunction
    def _on_forget_groupchat_action(_action: Gio.SimpleAction,
                                    params: structs.AccountJidParam
                                    ) -> None:

        window = cast(StartChatDialog, get_app_window('StartChatDialog'))
        window.remove_row(params.account, str(params.jid))

        client = app.get_client(params.account)
        client.get_module('MUC').leave(params.jid)
        client.get_module('Bookmarks').remove(params.jid)

        app.storage.archive.remove_history(params.account, params.jid)

    @staticmethod
    def _on_show(_action: Gio.SimpleAction, param: GLib.Variant) -> None:
        app.window.show()
