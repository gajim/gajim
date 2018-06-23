# -*- coding:utf-8 -*-
## src/gajim.py
##
## Copyright (C) 2003-2017 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
##                    Norman Rasmussen <norman AT rasmussen.co.za>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
## Copyright (C) 2016-2017 Emmanuel Gil Peyrot <linkmauve AT linkmauve.fr>
##                         Philipp Hörist <philipp AT hoerist.com>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import sys
import os
from urllib.parse import unquote

from gi.repository import GLib, Gio, Gtk

from gajim.common import app
from gajim.common import i18n
from gajim.common import configpaths
from gajim.common import logging_helpers
from gajim.common import exceptions
from gajim.common import caps_cache
from gajim.common import logger


class GajimApplication(Gtk.Application):
    '''Main class handling activation and command line.'''

    def __init__(self):
        Gtk.Application.__init__(self, application_id='org.gajim.Gajim',
                                 flags=(
                                    Gio.ApplicationFlags.HANDLES_COMMAND_LINE |
                                    Gio.ApplicationFlags.HANDLES_OPEN))

        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Show the application\'s version'))
        self.add_main_option('quiet', ord('q'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Show only critical errors'))
        self.add_main_option('separate', ord('s'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Separate profile files completely (even '
                               'history database and plugins)'))
        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Print XML stanzas and other debug '
                               'information'))
        self.add_main_option('profile', ord('p'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Use defined profile in configuration '
                               'directory'), 'NAME')
        self.add_main_option('config-path', ord('c'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Set configuration directory'), 'PATH')
        self.add_main_option('loglevel', ord('l'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Configure logging system'), 'LEVEL')
        self.add_main_option('warnings', ord('w'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Show all warnings'))
        self.add_main_option('ipython', ord('i'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Open IPython shell'))
        self.add_main_option('show-next-pending-event', 0, GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Pops up a window with the next pending event'))
        self.add_main_option('start-chat', 0, GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Start a new chat'))

        self.add_main_option_entries(self._get_remaining_entry())

        self.connect('handle-local-options', self._handle_local_options)
        self.connect('command-line', self._handle_remote_options)
        self.connect('startup', self._startup)
        self.connect('activate', self._activate)

        self.interface = None

        GLib.set_prgname('gajim')
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

    def _startup(self, application):

        # Create and initialize Application Paths & Databases
        app.detect_dependencies()
        configpaths.create_paths()
        try:
            app.logger = logger.Logger()
            caps_cache.initialize(app.logger)
        except exceptions.DatabaseMalformed as error:
            dlg = Gtk.MessageDialog(
                None,
                Gtk.DialogFlags.DESTROY_WITH_PARENT | Gtk.DialogFlags.MODAL,
                Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK,
                _('Database Error'))
            dlg.format_secondary_text(str(error))
            dlg.run()
            dlg.destroy()
            sys.exit()

        # Set Application Menu
        app.app = self
        from gajim import gtkgui_helpers
        builder = gtkgui_helpers.get_gtk_builder('application_menu.ui')
        menubar = builder.get_object("menubar")
        appmenu = builder.get_object("appmenu")
        if app.prefers_app_menu():
            self.set_app_menu(appmenu)
        else:
            # Add it to the menubar instead
            menubar.prepend_submenu('Gajim', appmenu)
        self.set_menubar(menubar)

    def _activate(self, application):
        if self.interface is not None:
            self.interface.roster.window.present()
            return
        from gajim.gui_interface import Interface
        from gajim import gtkgui_helpers
        self.interface = Interface()
        gtkgui_helpers.load_css()
        self.interface.run(self)
        self.add_actions()
        from gajim import gui_menu_builder
        gui_menu_builder.build_accounts_menu()

    def _open_uris(self, uris):
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
            if cmd == 'join':
                self.interface.join_gc_minimal(None, jid)
            elif cmd == 'roster':
                self.activate_action('add-contact', GLib.Variant('s', jid))
            elif cmd.startswith('message'):
                attributes = cmd.split(';')
                message = None
                for key in attributes:
                    if key.startswith('body'):
                        try:
                            message = unquote(key.split('=')[1])
                        except Exception:
                            app.log('uri_handler').error('Invalid URI: %s', cmd)
                accounts = list(app.connections.keys())
                if not accounts:
                    continue
                if len(accounts) == 1:
                    app.interface.new_chat_from_jid(accounts[0], jid, message)
                else:
                    self.activate_action('start-chat')
                    start_chat_window = app.interface.instances['start_chat']
                    start_chat_window.search_entry.set_text(jid)

    def do_shutdown(self, *args):
        Gtk.Application.do_shutdown(self)
        # Shutdown GUI and save config
        if hasattr(self.interface, 'roster') and self.interface.roster:
            self.interface.roster.prepare_quit()

        # Commit any outstanding SQL transactions
        app.logger.commit()

    def _handle_remote_options(self, application, command_line):
        # Parse all options that should be executed on a remote instance
        options = command_line.get_options_dict()

        remote_commands = ['ipython',
                           'show-next-pending-event',
                           'start-chat',
                           ]

        remaining = options.lookup_value(GLib.OPTION_REMAINING,
                                         GLib.VariantType.new('as'))

        for cmd in remote_commands:
            if options.contains(cmd):
                self.activate_action(cmd)
                return 0

        if remaining is not None:
            self._open_uris(remaining.unpack())
            return 0

        self.activate()
        return 0

    def _handle_local_options(self, application,
                              options: GLib.VariantDict) -> int:
        # Parse all options that have to be executed before ::startup
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

    def show_warnings(self):
        import traceback
        import warnings

        def warn_with_traceback(message, category, filename, lineno,
                                file=None, line=None):
            traceback.print_stack(file=sys.stderr)
            sys.stderr.write(warnings.formatwarning(message, category,
                                                    filename, lineno, line))

        warnings.showwarning = warn_with_traceback
        warnings.filterwarnings(action="always")

    def add_actions(self):
        ''' Build Application Actions '''
        from gajim import app_actions

        # General Stateful Actions

        act = Gio.SimpleAction.new_stateful(
            'merge', None,
            GLib.Variant.new_boolean(app.config.get('mergeaccounts')))
        act.connect('change-state', app_actions.on_merge_accounts)
        self.add_action(act)

        act = Gio.SimpleAction.new_stateful(
            'agent', None,
            GLib.Variant.new_boolean(app.config.get('use_gpg_agent')))
        self.add_action(act)

        # General Actions

        general_actions = [
            ('quit', app_actions.on_quit),
            ('accounts', app_actions.on_accounts),
            ('add-account', app_actions.on_add_account),
            ('manage-proxies', app_actions.on_manage_proxies),
            ('start-chat', app_actions.on_new_chat),
            ('bookmarks', app_actions.on_manage_bookmarks),
            ('history-manager', app_actions.on_history_manager),
            ('preferences', app_actions.on_preferences),
            ('plugins', app_actions.on_plugins),
            ('file-transfer', app_actions.on_file_transfers),
            ('history', app_actions.on_history),
            ('shortcuts', app_actions.on_keyboard_shortcuts),
            ('features', app_actions.on_features),
            ('content', app_actions.on_contents),
            ('about', app_actions.on_about),
            ('faq', app_actions.on_faq),
            ('ipython', app_actions.toggle_ipython),
            ('show-next-pending-event', app_actions.show_next_pending_event),
        ]

        act = Gio.SimpleAction.new('add-contact', GLib.VariantType.new('s'))
        act.connect("activate", app_actions.on_add_contact_jid)
        self.add_action(act)

        for action in general_actions:
            action_name, func = action
            act = Gio.SimpleAction.new(action_name, None)
            act.connect("activate", func)
            self.add_action(act)

        accounts_list = sorted(app.config.get_per('accounts'))
        if not accounts_list:
            return
        if len(accounts_list) > 1:
            for acc in accounts_list:
                self.add_account_actions(acc)
        else:
            self.add_account_actions(accounts_list[0])

    def _get_account_actions(self, account):
        from gajim import app_actions

        if account == 'Local':
            return [
                ('-xml-console', app_actions.on_xml_console, 'always', 's')
            ]

        return [
            ('-start-single-chat', app_actions.on_single_message, 'online', 's'),
            ('-join-groupchat', app_actions.on_join_gc, 'online', 's'),
            ('-add-contact', app_actions.on_add_contact, 'online', 's'),
            ('-services', app_actions.on_service_disco, 'online', 's'),
            ('-profile', app_actions.on_profile, 'feature', 's'),
            ('-xml-console', app_actions.on_xml_console, 'always', 's'),
            ('-server-info', app_actions.on_server_info, 'online', 's'),
            ('-archive', app_actions.on_archiving_preferences, 'feature', 's'),
            ('-sync-history', app_actions.on_history_sync, 'online', 's'),
            ('-privacylists', app_actions.on_privacy_lists, 'feature', 's'),
            ('-send-server-message',
                app_actions.on_send_server_message, 'online', 's'),
            ('-set-motd', app_actions.on_set_motd, 'online', 's'),
            ('-update-motd', app_actions.on_update_motd, 'online', 's'),
            ('-delete-motd', app_actions.on_delete_motd, 'online', 's'),
            ('-activate-bookmark',
                app_actions.on_activate_bookmark, 'online', 'a{sv}'),
            ('-open-event', app_actions.on_open_event, 'always', 'a{sv}'),
            ('-import-contacts', app_actions.on_import_contacts, 'online', 's'),
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
