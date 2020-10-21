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

import time
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from nbxmpp.namespaces import Namespace
from nbxmpp import JID
from nbxmpp.protocol import InvalidJid
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

import gajim
from gajim.common import app
from gajim.common import ged
from gajim.common import configpaths
from gajim.common import logging_helpers
from gajim.common import exceptions
from gajim.common.i18n import _
from gajim.common.contacts import LegacyContactsAPI
from gajim.common.task_manager import TaskManager
from gajim.common.storage.cache import CacheStorage
from gajim.common.storage.archive import MessageArchiveStorage
from gajim.common.settings import Settings
from gajim.common.settings import LegacyConfig


class GajimApplication(Gtk.Application):
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
            'show-next-pending-event',
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Pops up a window with the next pending event'))

        self.add_main_option(
            'start-chat', 0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _('Start a new chat'))

        self.add_main_option_entries(self._get_remaining_entry())

        self.connect('handle-local-options', self._handle_local_options)
        self.connect('command-line', self._command_line)
        self.connect('startup', self._startup)

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

    def _startup(self, _application):
        # Create and initialize Application Paths & Databases
        app.print_version()
        app.detect_dependencies()
        configpaths.create_paths()

        app.settings = Settings()
        app.settings.init()

        app.config = LegacyConfig() # type: ignore

        app.storage.cache = CacheStorage()
        app.storage.cache.init()

        app.storage.archive = MessageArchiveStorage()
        app.storage.archive.init()

        try:
            app.contacts = LegacyContactsAPI()
        except exceptions.DatabaseMalformed as error:
            dlg = Gtk.MessageDialog(
                transient_for=None,
                destroy_with_parent=True,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=_('Database Error'))
            dlg.format_secondary_text(str(error))
            dlg.run()
            dlg.destroy()
            sys.exit()

        from gajim.gtk.util import load_user_iconsets
        load_user_iconsets()

        from gajim.common.cert_store import CertificateStore
        app.cert_store = CertificateStore()
        app.task_manager = TaskManager()

        # Set Application Menu
        app.app = self
        from gajim.gtk.util import get_builder
        builder = get_builder('application_menu.ui')
        menubar = builder.get_object("menubar")
        self.set_menubar(menubar)

        from gajim.gui_interface import Interface
        self.interface = Interface()
        self.interface.run(self)
        self.add_actions()
        self._set_shortcuts()
        from gajim import gui_menu_builder
        gui_menu_builder.build_accounts_menu()
        self.update_app_actions_state()

        app.ged.register_event_handler('feature-discovered',
                                       ged.CORE,
                                       self._on_feature_discovered)

    def _open_uris(self, uris):
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

                if len(accounts) == 1:
                    app.interface.new_chat_from_jid(accounts[0], jid, message)
                else:
                    self.activate_action('start-chat', GLib.Variant('s', jid))

    def do_shutdown(self, *args):
        Gtk.Application.do_shutdown(self)
        # Shutdown GUI and save config
        if hasattr(self.interface, 'roster') and self.interface.roster:
            self.interface.roster.prepare_quit()

        # Commit any outstanding SQL transactions
        app.storage.cache.shutdown()
        app.storage.archive.shutdown()

    def _command_line(self, _application, command_line):
        options = command_line.get_options_dict()

        remote_commands = [
            ('ipython', None),
            ('show-next-pending-event', None),
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
        if options.contains('profile'):
            # Incorporate profile name into application id
            # to have a single app instance for each profile.
            profile = options.lookup_value('profile').get_string()
            app_id = '%s.%s' % (self.get_application_id(), profile)
            self.set_application_id(app_id)
            configpaths.set_profile(profile)
        if options.contains('separate'):
            configpaths.set_separation(True)
        if options.contains('config-path'):
            path = options.lookup_value('config-path').get_string()
            configpaths.set_config_root(path)

        configpaths.init()

        if app.get_debug_mode():
            # Redirect has to happen before logging init
            self._cleanup_debug_logs()
            self._redirect_output()
            logging_helpers.init()
            logging_helpers.set_verbose()
        else:
            logging_helpers.init()

        if options.contains('quiet'):
            logging_helpers.set_quiet()
        if options.contains('verbose'):
            logging_helpers.set_verbose()
        if options.contains('loglevel'):
            loglevel = options.lookup_value('loglevel').get_string()
            logging_helpers.set_loglevels(loglevel)
        if options.contains('warnings'):
            self.show_warnings()

        return -1

    @staticmethod
    def show_warnings():
        import traceback
        import warnings

        def warn_with_traceback(message, category, filename, lineno,
                                _file=None, line=None):
            traceback.print_stack(file=sys.stderr)
            sys.stderr.write(warnings.formatwarning(message, category,
                                                    filename, lineno, line))

        warnings.showwarning = warn_with_traceback
        warnings.filterwarnings(action="always")

    @staticmethod
    def _redirect_output():
        debug_folder = Path(configpaths.get('DEBUG'))
        date = datetime.today().strftime('%d%m%Y-%H%M%S')
        filename = '%s-debug.log' % date
        fd = open(debug_folder / filename, 'a')
        sys.stderr = sys.stdout = fd

    @staticmethod
    def _cleanup_debug_logs():
        debug_folder = Path(configpaths.get('DEBUG'))
        debug_files = list(debug_folder.glob('*-debug.log*'))
        now = time.time()
        for file in debug_files:
            # Delete everything older than 3 days
            if file.stat().st_ctime < now - 259200:
                file.unlink()

    def add_actions(self):
        ''' Build Application Actions '''
        from gajim import app_actions

        # General Stateful Actions

        act = Gio.SimpleAction.new_stateful(
            'merge', None,
            GLib.Variant.new_boolean(app.settings.get('mergeaccounts')))
        act.connect('change-state', app_actions.on_merge_accounts)
        self.add_action(act)

        actions = [
            ('quit', app_actions.on_quit),
            ('add-account', app_actions.on_add_account),
            ('manage-proxies', app_actions.on_manage_proxies),
            ('history-manager', app_actions.on_history_manager),
            ('preferences', app_actions.on_preferences),
            ('plugins', app_actions.on_plugins),
            ('xml-console', app_actions.on_xml_console),
            ('file-transfer', app_actions.on_file_transfers),
            ('history', app_actions.on_history),
            ('shortcuts', app_actions.on_keyboard_shortcuts),
            ('features', app_actions.on_features),
            ('content', app_actions.on_contents),
            ('about', app_actions.on_about),
            ('faq', app_actions.on_faq),
            ('ipython', app_actions.toggle_ipython),
            ('show-next-pending-event', app_actions.show_next_pending_event),
            ('start-chat', 's', app_actions.on_new_chat),
            ('accounts', 's', app_actions.on_accounts),
            ('add-contact', 's', app_actions.on_add_contact_jid),
            ('copy-text', 's', app_actions.copy_text),
            ('open-link', 'as', app_actions.open_link),
            ('open-mail', 's', app_actions.open_mail),
            ('create-groupchat', 's', app_actions.on_create_gc),
            ('browse-history', 'a{sv}', app_actions.on_browse_history),
            ('groupchat-join', 'as', app_actions.on_groupchat_join),
        ]

        for action in actions:
            if len(action) == 2:
                action_name, func = action
                variant = None
            else:
                action_name, variant, func = action
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

    @staticmethod
    def _get_account_actions(account):
        from gajim import app_actions as a

        if account == 'Local':
            return []

        return [
            ('-bookmarks', a.on_bookmarks, 'online', 's'),
            ('-start-single-chat', a.on_single_message, 'online', 's'),
            ('-start-chat', a.start_chat, 'online', 'as'),
            ('-add-contact', a.on_add_contact, 'online', 'as'),
            ('-services', a.on_service_disco, 'online', 's'),
            ('-profile', a.on_profile, 'feature', 's'),
            ('-server-info', a.on_server_info, 'online', 's'),
            ('-archive', a.on_mam_preferences, 'feature', 's'),
            ('-pep-config', a.on_pep_config, 'online', 's'),
            ('-sync-history', a.on_history_sync, 'online', 's'),
            ('-blocking', a.on_blocking_list, 'feature', 's'),
            ('-send-server-message', a.on_send_server_message, 'online', 's'),
            ('-set-motd', a.on_set_motd, 'online', 's'),
            ('-update-motd', a.on_update_motd, 'online', 's'),
            ('-delete-motd', a.on_delete_motd, 'online', 's'),
            ('-open-event', a.on_open_event, 'always', 'a{sv}'),
            ('-remove-event', a.on_remove_event, 'always', 'a{sv}'),
            ('-import-contacts', a.on_import_contacts, 'online', 's'),
        ]

    def add_account_actions(self, account):
        for action in self._get_account_actions(account):
            action_name, func, state, type_ = action
            action_name = account + action_name
            if self.lookup_action(action_name):
                # We already added this action
                continue
            act = Gio.SimpleAction.new(
                action_name, GLib.VariantType.new(type_))
            act.connect("activate", func)
            if state != 'always':
                act.set_enabled(False)
            self.add_action(act)

    def remove_account_actions(self, account):
        for action in self._get_account_actions(account):
            action_name = account + action[0]
            self.remove_action(action_name)

    def set_account_actions_state(self, account, new_state=False):
        for action in self._get_account_actions(account):
            action_name, _, state, _ = action
            if not new_state and state in ('online', 'feature'):
                # We go offline
                self.lookup_action(account + action_name).set_enabled(False)
            elif new_state and state == 'online':
                # We go online
                self.lookup_action(account + action_name).set_enabled(True)

    def update_app_actions_state(self):
        active_accounts = bool(app.get_connected_accounts(exclude_local=True))
        self.lookup_action('create-groupchat').set_enabled(active_accounts)

        enabled_accounts = app.contacts.get_accounts()
        self.lookup_action('start-chat').set_enabled(enabled_accounts)

    def _set_shortcuts(self):
        shortcuts = {
            'app.quit': ['<Primary>Q'],
            'app.shortcuts': ['<Primary>question'],
            'app.preferences': ['<Primary>P'],
            'app.plugins': ['<Primary>E'],
            'app.xml-console': ['<Primary><Shift>X'],
            'app.file-transfer': ['<Primary>T'],
            'app.ipython': ['<Primary><Alt>I'],
            'app.start-chat::': ['<Primary>N'],
            'app.create-groupchat::': ['<Primary>G'],
            'win.show-roster': ['<Primary>R'],
            'win.show-offline': ['<Primary>O'],
            'win.show-active': ['<Primary>Y'],
            'win.change-nickname': ['<Primary><Shift>N'],
            'win.change-subject': ['<Primary><Shift>S'],
            'win.escape': ['Escape'],
            'win.browse-history': ['<Primary>H'],
            'win.send-file': ['<Primary>F'],
            'win.show-contact-info': ['<Primary>I'],
            'win.show-emoji-chooser': ['<Primary><Shift>M'],
            'win.clear-chat': ['<Primary>L'],
            'win.delete-line': ['<Primary>U'],
            'win.close-tab': ['<Primary>W'],
            'win.move-tab-up': ['<Primary><Shift>Page_Up'],
            'win.move-tab-down': ['<Primary><Shift>Page_Down'],
            'win.switch-next-tab': ['<Primary>Page_Down'],
            'win.switch-prev-tab': ['<Primary>Page_Up'],
            'win.switch-next-unread-tab-right': ['<Primary>Tab'],
            'win.switch-next-unread-tab-left': ['<Primary>ISO_Left_Tab'],
            'win.switch-tab-1': ['<Alt>1', '<Alt>KP_1'],
            'win.switch-tab-2': ['<Alt>2', '<Alt>KP_2'],
            'win.switch-tab-3': ['<Alt>3', '<Alt>KP_3'],
            'win.switch-tab-4': ['<Alt>4', '<Alt>KP_4'],
            'win.switch-tab-5': ['<Alt>5', '<Alt>KP_5'],
            'win.switch-tab-6': ['<Alt>6', '<Alt>KP_6'],
            'win.switch-tab-7': ['<Alt>7', '<Alt>KP_7'],
            'win.switch-tab-8': ['<Alt>8', '<Alt>KP_8'],
            'win.switch-tab-9': ['<Alt>9', '<Alt>KP_9'],
        }

        for action, accels in shortcuts.items():
            self.set_accels_for_action(action, accels)

    def _on_feature_discovered(self, event):
        if event.feature == Namespace.VCARD:
            action = '%s-profile' % event.account
            self.lookup_action(action).set_enabled(True)
        elif event.feature == Namespace.MAM_2:
            action = '%s-archive' % event.account
            self.lookup_action(action).set_enabled(True)
        elif event.feature == Namespace.BLOCKING:
            action = '%s-blocking' % event.account
            self.lookup_action(action).set_enabled(True)
