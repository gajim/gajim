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
import signal
import locale
from urllib.parse import unquote

import gi
gi.require_version('GLib', '2.0')
gi.require_version('Gio', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GObject', '2.0')
gi.require_version('Pango', '1.0')
from gi.repository import GLib, Gio, Gtk

from gajim.common import i18n
from gajim.common import configpaths
from gajim.common import logging_helpers

MIN_NBXMPP_VER = "0.6.4"
MIN_GTK_VER = "3.22.0"


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
        from gajim import gtkexcepthook
        gtkexcepthook.init()

        try:
            import nbxmpp
        except ImportError:
            print('Gajim needs python-nbxmpp to run. Quitting…')
            sys.exit(1)

        from distutils.version import LooseVersion as V
        if V(nbxmpp.__version__) < V(MIN_NBXMPP_VER):
            print('Gajim needs python-nbxmpp >= %s to run. '
                  'Quitting...' % MIN_NBXMPP_VER)
            sys.exit(1)

        gtk_ver = '%s.%s.%s' % (Gtk.get_major_version(),
                                Gtk.get_minor_version(),
                                Gtk.get_micro_version())
        if V(gtk_ver) < V(MIN_GTK_VER):
            print('Gajim needs GTK+ >= %s to run. '
                  'Quitting...' % MIN_GTK_VER)
            sys.exit(1)

        # Create and initialize Application Paths & Databases
        from gajim.common import app
        app.detect_dependencies()
        configpaths.create_paths()
        from gajim.common import exceptions
        from gajim.common import logger
        from gajim.common import caps_cache
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

        if os.name == 'nt':
            import gettext
            # needed for docutils
            sys.path.append('.')
            APP = 'gajim'
            DIR = '../po'
            lang = locale.getdefaultlocale()[0]
            os.environ['LANG'] = lang
            gettext.bindtextdomain(APP, DIR)
            gettext.textdomain(APP)
            gettext.install(APP, DIR)

        # This is for Windows translation which is currently not
        # working on GTK 3.18.9
        #    locale.setlocale(locale.LC_ALL, '')
        #    import ctypes
        #    import ctypes.util
        #    libintl_path = ctypes.util.find_library('intl')
        #    if libintl_path == None:
        #        local_intl = os.path.join('gtk', 'bin', 'intl.dll')
        #        if os.path.exists(local_intl):
        #            libintl_path = local_intl
        #    if libintl_path == None:
        #        raise ImportError('intl.dll library not found')
        #    libintl = ctypes.cdll.LoadLibrary(libintl_path)
        #    libintl.bindtextdomain(APP, DIR)
        #    libintl.bind_textdomain_codeset(APP, 'UTF-8')
        #    plugins_locale_dir = os.path.join(common.configpaths[
        #       'PLUGINS_USER'], 'locale').encode(locale.getpreferredencoding())
        #    libintl.bindtextdomain('gajim_plugins', plugins_locale_dir)
        #    libintl.bind_textdomain_codeset('gajim_plugins', 'UTF-8')

        if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
            i18n.direction_mark = '\u200F'

        from ctypes import CDLL, byref, create_string_buffer
        from ctypes.util import find_library
        import platform

        sysname = platform.system()
        if sysname in ('Linux', 'FreeBSD', 'OpenBSD', 'NetBSD'):
            libc = CDLL(find_library('c'))

            # The constant defined in <linux/prctl.h> which is used to set the name
            # of the process.
            PR_SET_NAME = 15

            if sysname == 'Linux':
                proc_name = b'gajim'
                buff = create_string_buffer(len(proc_name)+1)
                buff.value = proc_name
                libc.prctl(PR_SET_NAME, byref(buff), 0, 0, 0)
            elif sysname in ('FreeBSD', 'OpenBSD', 'NetBSD'):
                libc.setproctitle('gajim')

        def sigint_cb(num, stack):
            print('SIGINT/SIGTERM received')
            self.quit()
        # ^C exits the application normally
        signal.signal(signal.SIGINT, sigint_cb)
        signal.signal(signal.SIGTERM, sigint_cb)

        # Set Application Menu
        app.app = self
        path = os.path.join(configpaths.get('GUI'), 'application_menu.ui')
        builder = Gtk.Builder()
        builder.set_translation_domain(i18n.APP)
        builder.add_from_file(path)
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
        from gajim.common import app
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
        from gajim.common import app
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
        from gajim.app_actions import AppActions
        from gajim.common import app
        action = AppActions(self)

        self.account_actions = [
            ('-start-single-chat', action.on_single_message, 'online', 's'),
            ('-join-groupchat', action.on_join_gc, 'online', 's'),
            ('-add-contact', action.on_add_contact, 'online', 's'),
            ('-services', action.on_service_disco, 'online', 's'),
            ('-profile', action.on_profile, 'feature', 's'),
            ('-xml-console', action.on_xml_console, 'always', 's'),
            ('-server-info', action.on_server_info, 'online', 's'),
            ('-archive', action.on_archiving_preferences, 'feature', 's'),
            ('-sync-history', action.on_history_sync, 'online', 's'),
            ('-privacylists', action.on_privacy_lists, 'feature', 's'),
            ('-send-server-message',
                action.on_send_server_message, 'online', 's'),
            ('-set-motd', action.on_set_motd, 'online', 's'),
            ('-update-motd', action.on_update_motd, 'online', 's'),
            ('-delete-motd', action.on_delete_motd, 'online', 's'),
            ('-activate-bookmark',
                action.on_activate_bookmark, 'online', 'a{sv}'),
            ('-open-event', action.on_open_event, 'always', 'a{sv}'),
            ('-import-contacts', action.on_import_contacts, 'online', 's'),
        ]

        # General Stateful Actions

        act = Gio.SimpleAction.new_stateful(
            'merge', None,
            GLib.Variant.new_boolean(app.config.get('mergeaccounts')))
        act.connect('change-state', action.on_merge_accounts)
        self.add_action(act)

        act = Gio.SimpleAction.new_stateful(
            'agent', None,
            GLib.Variant.new_boolean(app.config.get('use_gpg_agent')))
        self.add_action(act)

        # General Actions

        self.general_actions = [
            ('quit', action.on_quit),
            ('accounts', action.on_accounts),
            ('add-account', action.on_add_account),
            ('manage-proxies', action.on_manage_proxies),
            ('start-chat', action.on_new_chat),
            ('bookmarks', action.on_manage_bookmarks),
            ('history-manager', action.on_history_manager),
            ('preferences', action.on_preferences),
            ('plugins', action.on_plugins),
            ('file-transfer', action.on_file_transfers),
            ('history', action.on_history),
            ('shortcuts', action.on_keyboard_shortcuts),
            ('features', action.on_features),
            ('content', action.on_contents),
            ('about', action.on_about),
            ('faq', action.on_faq),
            ('ipython', action.toggle_ipython),
            ('show-next-pending-event', action.show_next_pending_event),
        ]

        act = Gio.SimpleAction.new('add-contact', GLib.VariantType.new('s'))
        act.connect("activate", action.on_add_contact_jid)
        self.add_action(act)

        for action in self.general_actions:
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

    def add_account_actions(self, account):
        for action in self.account_actions:
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
        for action in self.account_actions:
            action_name = account + action[0]
            self.remove_action(action_name)

    def set_account_actions_state(self, account, new_state=False):
        for action in self.account_actions:
            action_name, _, state, _ = action
            if not new_state and state in ('online', 'feature'):
                # We go offline
                self.lookup_action(account + action_name).set_enabled(False)
            elif new_state and state == 'online':
                # We go online
                self.lookup_action(account + action_name).set_enabled(True)


def main():
    if sys.platform != 'win32':
        if os.geteuid() == 0:
            sys.exit("You must not launch gajim as root, it is insecure.")

    appli = GajimApplication()
    appli.run(sys.argv)


if __name__ == '__main__':
    main()
