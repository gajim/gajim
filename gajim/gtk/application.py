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
from typing import Optional
from typing import cast

import os
import sys

from urllib.parse import unquote

from nbxmpp.namespaces import Namespace
from nbxmpp import JID
from nbxmpp.protocol import InvalidJid
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk

import gajim
from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common import idle
from gajim.common import logging_helpers
from gajim.common.application import CoreApplication
from gajim.common.const import GAJIM_FAQ_URI
from gajim.common.const import GAJIM_WIKI_URI
from gajim.common.dbus import music_track
from gajim.common.events import ApplicationEvent
from gajim.common.exceptions import GajimGeneralException
from gajim.common.helpers import load_json
from gajim.common.helpers import open_uri
from gajim.common.i18n import _

from gajim.gui import menus
from gajim.gui import structs
from gajim.gui.about import AboutDialog
from gajim.gui.avatar import AvatarStorage
from gajim.gui.builder import get_builder
from gajim.gui.dialogs import ShortcutsWindow
from gajim.gui.discovery import ServiceDiscoveryWindow
from gajim.gui.util import get_app_window
from gajim.gui.util import load_user_iconsets
from gajim.gui.util import open_window


ActionListT = list[tuple[str,
                         Optional[str],
                         Callable[[Gio.SimpleAction, GLib.Variant], Any]]]


class GajimApplication(Gtk.Application, CoreApplication):
    '''Main class handling activation and command line.'''

    def __init__(self):
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
            _('Show the application\'s version'))

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
            'ipython',
            ord('i'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Open IPython shell'))

        self.add_main_option(
            'gdebug',
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Sets an environment variable so '
              'GLib debug messages are printed'))

        self.add_main_option(
            'start-chat', 0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Start a new chat'))

        self.add_main_option_entries(self._get_remaining_entry())

        self.connect('handle-local-options', self._handle_local_options)
        self.connect('command-line', self._command_line)
        self.connect('startup', self._startup)
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

    def _startup(self, _application: GajimApplication) -> None:
        self._init_core()

        icon_theme = Gtk.IconTheme.get_default()
        icon_theme.append_search_path(str(configpaths.get('ICONS')))
        load_user_iconsets()

        builder = get_builder('application_menu.ui')
        self.set_menubar(cast(Gio.Menu, builder.get_object('menubar')))

        from gajim.gui import notification
        notification.init()

        self.avatar_storage = AvatarStorage()

        app.load_css_config()

        idle.Monitor.set_interval(app.settings.get('autoawaytime') * 60,
                                  app.settings.get('autoxatime') * 60)

        if sys.platform in ('win32', 'darwin'):
            from gajim.gui.emoji_chooser import emoji_chooser
            emoji_chooser.load()

        from gajim.gui_interface import Interface

        self.interface = Interface()
        self.interface.run(self)

        from gajim.gui.status_icon import StatusIcon
        self.systray = StatusIcon()

        if sys.platform not in ('win32', 'darwin'):
            music_track.enable()

        self.add_actions()
        self._load_shortcuts()
        menus.build_accounts_menu()
        self.update_app_actions_state()

        app.ged.register_event_handler('feature-discovered',
                                       ged.CORE,
                                       self._on_feature_discovered)

        from gajim.gui.main import MainWindow
        MainWindow()

    def _open_uris(self, uris: list[str]) -> None:
        accounts = list(app.connections.keys())
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
                        'groupchat-join',
                        GLib.Variant('as', [accounts[0], jid]))
                else:
                    self.activate_action('start-chat', GLib.Variant('s', jid))

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

                app.interface.start_chat_from_jid(accounts[0], jid, message)

    def _shutdown(self, _application: GajimApplication) -> None:
        self._shutdown_core()

    def _quit_app(self) -> None:
        self.quit()

    def _command_line(self,
                      _application: GajimApplication,
                      command_line: Gio.ApplicationCommandLine) -> int:
        options = command_line.get_options_dict()

        remote_commands = [
            ('ipython', None),
            ('start-chat', GLib.Variant('s', '')),
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
        # Parse all options that have to be executed before ::startup
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

        if options.contains('separate'):
            configpaths.set_separation(True)

        config_path = options.lookup_value('config-path')
        if config_path is not None:
            config_path = config_path.get_string()
            configpaths.set_config_root(config_path)

        configpaths.init()

        if options.contains('gdebug'):
            os.environ['G_MESSAGES_DEBUG'] = 'all'

        logging_helpers.init()

        if options.contains('quiet'):
            logging_helpers.set_quiet()

        if options.contains('verbose'):
            logging_helpers.set_verbose()

        loglevel = options.lookup_value('loglevel')
        if loglevel is not None:
            loglevel = loglevel.get_string()
            logging_helpers.set_loglevels(loglevel)

        if options.contains('warnings'):
            self._show_warnings()

        return -1

    def add_actions(self) -> None:
        actions: ActionListT = [
            ('quit', None, self._on_quit_action),
            ('add-account', None,  self._on_add_account_action),
            ('manage-proxies', None,  self._on_manage_proxies_action),
            ('preferences', None,  self._on_preferences_action),
            ('plugins', None,  self._on_plugins_action),
            ('xml-console', None,  self._on_xml_console_action),
            ('file-transfer', None,  self._on_file_transfer_action),
            ('shortcuts', None,  self._on_shortcuts_action),
            ('features', None,  self._on_features_action),
            ('content', None,  self._on_content_action),
            ('about', None,  self._on_about_action),
            ('faq', None,  self._on_faq_action),
            ('ipython', None,  self._on_ipython_action),
            ('start-chat', 's', self._on_new_chat_action),
            ('accounts', 's', self._on_accounts_action),
            ('add-contact', 's', self._on_add_contact_action),
            ('copy-text', 's', self._on_copy_text_action),
            ('open-link', 'as', self._on_open_link_action),
            ('open-mail', 's', self._on_open_mail_action),
            ('remove-history', 'a{sv}', self._on_remove_history_action),
            ('create-groupchat', 's', self._on_create_groupchat_action),
            ('forget-groupchat', 'a{sv}', self._on_forget_groupchat_action),
            ('groupchat-join', 'as', self._on_groupchat_join_action),
        ]

        for action in actions:
            action_name, variant, func = action
            if variant is not None:
                variant = GLib.VariantType.new(variant)

            act = Gio.SimpleAction.new(action_name, variant)
            act.connect('activate', func)
            self.add_action(act)

        accounts_list = sorted(app.settings.get_accounts())
        if not accounts_list:
            return
        if len(accounts_list) > 1:
            for acc in accounts_list:
                self.add_account_actions(acc)
        else:
            self.add_account_actions(accounts_list[0])

    def _get_account_actions(self,
                             account: str) -> list[tuple[str, Any, str, str]]:
        # pylint: disable=line-too-long
        return [
            ('-bookmarks', self._on_bookmarks_action, 'online', 's'),
            ('-start-single-chat', self._on_start_single_message_action, 'online', 's'),
            ('-open-chat', self._on_open_chat_action, 'online', 'as'),
            ('-add-contact', self._on_add_contact_account_action, 'online', 'as'),
            ('-services', self._on_services_action, 'online', 's'),
            ('-profile', self._on_profile_action, 'online', 's'),
            ('-server-info', self._on_server_info_action, 'online', 's'),
            ('-archive', self._on_archive_action, 'feature', 's'),
            ('-pep-config', self._on_pep_config_action, 'online', 's'),
            ('-sync-history', self._on_sync_history_action, 'online', 's'),
            ('-blocking', self._on_blocking_action, 'feature', 's'),
            ('-send-server-message', self._on_send_server_message_action, 'online', 's'),
            ('-set-motd', self._on_set_motd_action, 'online', 's'),
            ('-update-motd', self._on_update_motd_action, 'online', 's'),
            ('-delete-motd', self._on_delete_motd_action, 'online', 's'),
            ('-open-event', self._on_open_event_action, 'always', 'a{sv}'),
            ('-mark-as-read', self._on_mark_as_read_action, 'always', 'a{sv}'),
            ('-import-contacts', self._on_import_contacts_action, 'online', 's'),
            ('-export-history', self._on_export_history, 'always', 's'),
        ]
        # pylint: enable=line-too-long

    def add_account_actions(self, account: str) -> None:
        for action in self._get_account_actions(account):
            action_name, func, state, type_ = action
            action_name = account + action_name
            if self.lookup_action(action_name) is not None:
                # We already added this action
                continue
            act = Gio.SimpleAction.new(
                action_name, GLib.VariantType.new(type_))
            act.connect("activate", func)
            if state != 'always':
                act.set_enabled(False)
            self.add_action(act)

    def remove_account_actions(self, account: str) -> None:
        for action in self._get_account_actions(account):
            action_name = account + action[0]
            self.remove_action(action_name)

    def set_action_state(self, action_name: str, state: bool) -> None:
        action = self.lookup_action(action_name)
        if action is None:
            raise ValueError('Action %s does not exist' % action_name)
        action.set_enabled(state)

    def set_account_actions_state(self,
                                  account: str,
                                  new_state: bool = False) -> None:
        for action in self._get_account_actions(account):
            action_name, _, state, _ = action
            if not new_state and state in ('online', 'feature'):
                # We go offline
                self.set_action_state(account + action_name, False)
            elif new_state and state == 'online':
                # We go online
                self.set_action_state(account + action_name, True)

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

    def _on_feature_discovered(self, event: ApplicationEvent) -> None:
        if event.feature == Namespace.MAM_2:
            action = '%s-archive' % event.account
            self.set_action_state(action, True)
        elif event.feature == Namespace.BLOCKING:
            action = '%s-blocking' % event.account
            self.set_action_state(action, True)

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
        window = open_window('StartChatDialog')
        search_text = param.get_string()
        if search_text:
            window.set_search_text(search_text)

    @staticmethod
    def _on_profile_action(_action: Gio.SimpleAction,
                           param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('ProfileWindow', account=account)

    @staticmethod
    def _on_send_server_message_action(_action: Gio.SimpleAction,
                                       param: GLib.Variant) -> None:
        account = param.get_string()
        server = app.settings.get_account_setting(account, 'hostname')
        server += '/announce/online'
        open_window('SingleMessageWindow', account=account, recipients=server)

    @staticmethod
    def _on_services_action(_action: Gio.SimpleAction,
                            param: GLib.Variant) -> None:
        account = param.get_string()
        server_jid = app.settings.get_account_setting(account, 'hostname')
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
        if jid is not None:
            jid = JID.from_string(jid)
        open_window('AddContact', account=account or None, jid=jid or None)

    @staticmethod
    def _on_start_single_message_action(_action: Gio.SimpleAction,
                                        param: GLib.Variant) -> None:
        account = param.get_string()
        open_window('SingleMessageWindow', account=account)

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
    def _on_set_motd_action(_action: Gio.SimpleAction,
                            param: GLib.Variant) -> None:
        account = param.get_string()
        server = app.settings.get_account_setting(account, 'hostname')
        server += '/announce/motd'
        open_window('SingleMessageWindow', account=account, recipients=server)

    @staticmethod
    def _on_update_motd_action(_action: Gio.SimpleAction,
                               param: GLib.Variant) -> None:
        account = param.get_string()
        server = app.settings.get_account_setting(account, 'hostname')
        server += '/announce/motd/update'
        open_window('SingleMessageWindow', account=account, recipients=server)

    @staticmethod
    def _on_delete_motd_action(_action: Gio.SimpleAction,
                               param: GLib.Variant) -> None:
        account = param.get_string()
        app.connections[account].get_module('Announce').delete_motd()

    @staticmethod
    def _on_content_action(_action: Gio.SimpleAction,
                           _param: Optional[GLib.Variant]) -> None:
        open_uri(GAJIM_WIKI_URI)

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

            assert params.jid is not None
            app.window.select_chat(params.account, params.jid)

        app.window.present_with_time(Gtk.get_current_event_time())

    @staticmethod
    def _on_mark_as_read_action(_action: Gio.SimpleAction,
                                param: GLib.Variant) -> None:
        dict_ = param.unpack()
        account, jid = dict_['account'], dict_['jid']
        app.window.mark_as_read(account, JID.from_string(jid))

    @staticmethod
    def _on_ipython_action(_action: Gio.SimpleAction,
                           _param: Optional[GLib.Variant]) -> None:
        """
        Show/hide the ipython window
        """
        win = app.ipython_window
        if win and win.window.is_visible():
            win.present()
        else:
            app.interface.create_ipython_window()

    @staticmethod
    def _on_open_mail_action(_action: Gio.SimpleAction,
                             param: GLib.Variant) -> None:
        uri = param.get_string()
        if not uri.startswith('mailto:'):
            uri = 'mailto:%s' % uri
        open_uri(uri)

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
        app.interface.start_chat_from_jid(account, jid)

    @staticmethod
    @structs.actionfunction
    def _on_remove_history_action(_action: Gio.SimpleAction,
                                  params: structs.RemoveHistoryActionParams
                                  ) -> None:

        if params.jid is not None:
            app.storage.archive.remove_history(params.account, params.jid)
            control = app.window.get_control(params.account, params.jid)
            if control is not None:
                control.reset_view()
        else:
            for control in app.window.get_controls(params.account):
                control.reset_view()

    @staticmethod
    @structs.actionfunction
    def _on_forget_groupchat_action(_action: Gio.SimpleAction,
                                    params: structs.ForgetGroupchatActionParams
                                    ) -> None:

        window = get_app_window('StartChatDialog')
        window.remove_row(params.account, str(params.jid))

        client = app.get_client(params.account)
        client.get_module('MUC').leave(params.jid)
        client.get_module('Bookmarks').remove(params.jid)

        app.storage.archive.remove_history(params.account, params.jid)
        app.storage.archive.forget_jid_data(params.account, params.jid)

    @staticmethod
    def _on_groupchat_join_action(_action: Gio.SimpleAction,
                                  param: GLib.Variant) -> None:
        account, jid = param.get_strv()
        open_window('GroupchatJoin', account=account, jid=jid)
