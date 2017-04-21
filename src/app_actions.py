# -*- coding: utf-8 -*-
## src/app_actions.py
##
## Copyright (C) 2017 Philipp Hörist <philipp AT hoerist.com>
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

from common import helpers
from common import gajim
from common.exceptions import GajimGeneralException
from gi.repository import Gtk
import sys
import os
import config
import dialogs
import features_window
import shortcuts_window
import plugins.gui
import history_window
import disco


class AppActions():
    ''' Action Callbacks '''
    def __init__(self, app: Gtk.Application):
        self.application = app

    # Application Menu Actions

    def on_preferences(self, action, param):
        if 'preferences' in gajim.interface.instances:
            gajim.interface.instances['preferences'].window.present()
        else:
            gajim.interface.instances['preferences'] = \
                config.PreferencesWindow()

    def on_plugins(self, action, param):
        if 'plugins' in gajim.interface.instances:
            gajim.interface.instances['plugins'].window.present()
        else:
            gajim.interface.instances['plugins'] = plugins.gui.PluginsWindow()

    def on_accounts(self, action, param):
        if 'accounts' in gajim.interface.instances:
            gajim.interface.instances['accounts'].window.present()
        else:
            gajim.interface.instances['accounts'] = config.AccountsWindow()

    def on_history_manager(self, action, param):
        config_path = '-c %s' % gajim.gajimpaths.config_root
        posix = os.name != 'nt'
        if os.path.exists('history_manager.exe'):  # Windows
            helpers.exec_command('history_manager.exe %s' % config_path,
                                 posix=posix)
        else:  # Linux or running from Git
            helpers.exec_command(
                '%s history_manager.py %s' % (sys.executable, config_path),
                posix=posix)

    def on_manage_bookmarks(self, action, param):
        config.ManageBookmarksWindow()

    def on_quit(self, action, param):
        gajim.interface.roster.on_quit_request()

    # Accounts Actions

    def on_profile(self, action, param):
        gajim.interface.edit_own_details(param.get_string())

    def on_activate_bookmark(self, action, param):
        dict_ = param.unpack()
        account, jid, nick, password = \
            dict_['account'], dict_['jid'], None, None
        if 'nick' in dict_:
            nick = dict_['nick']
        if 'password' in dict_:
            password = dict_['password']
        gajim.interface.join_gc_room(account, jid, nick, password)

    def on_send_server_message(self, action, param):
        account = param.get_string()
        server = gajim.config.get_per('accounts', account, 'hostname')
        server += '/announce/online'
        dialogs.SingleMessageWindow(account, server, 'send')

    def on_service_disco(self, action, param):
        account = param.get_string()
        server_jid = gajim.config.get_per('accounts', account, 'hostname')
        if server_jid in gajim.interface.instances[account]['disco']:
            gajim.interface.instances[account]['disco'][server_jid].\
                window.present()
        else:
            try:
                # Object will add itself to the window dict
                disco.ServiceDiscoveryWindow(account, address_entry=True)
            except GajimGeneralException:
                pass

    def on_join_gc(self, action, param):
        account = param.get_string()
        invisible_show = gajim.SHOW_LIST.index('invisible')
        if gajim.connections[account].connected == invisible_show:
            dialogs.ErrorDialog(_(
                'You cannot join a group chat while you are invisible'))
            return
        if 'join_gc' in gajim.interface.instances[account]:
            gajim.interface.instances[account]['join_gc'].window.present()
        else:
            try:
                gajim.interface.instances[account]['join_gc'] = \
                    dialogs.JoinGroupchatWindow(account)
            except GajimGeneralException:
                pass

    def on_add_contact(self, action, param):
        dialogs.AddNewContactWindow(param.get_string())

    def on_new_chat(self, action, param):
        dialogs.NewChatDialog(param.get_string())

    def on_single_message(self, action, param):
        dialogs.SingleMessageWindow(param.get_string(), action='send')

    # Advanced Actions

    def on_archiving_preferences(self, action, param):
        account = param.get_string()
        if 'archiving_preferences' in gajim.interface.instances[account]:
            gajim.interface.instances[account]['archiving_preferences'].window.\
                present()
        else:
            if gajim.connections[account].archiving_313_supported:
                gajim.interface.instances[account]['archiving_preferences'] = \
                    dialogs.Archiving313PreferencesWindow(account)
            else:
                gajim.interface.instances[account]['archiving_preferences'] = \
                    dialogs.ArchivingPreferencesWindow(account)

    def on_privacy_lists(self, action, param):
        account = param.get_string()
        if 'privacy_lists' in gajim.interface.instances[account]:
            gajim.interface.instances[account]['privacy_lists'].window.present()
        else:
            gajim.interface.instances[account]['privacy_lists'] = \
                    dialogs.PrivacyListsWindow(account)

    def on_xml_console(self, action, param):
        account = param.get_string()
        if 'xml_console' in gajim.interface.instances[account]:
            gajim.interface.instances[account]['xml_console'].window.present()
        else:
            gajim.interface.instances[account]['xml_console'] = \
                dialogs.XMLConsoleWindow(account)

    # Admin Actions

    def on_set_motd(self, action, param):
        account = param.get_string()
        server = gajim.config.get_per('accounts', account, 'hostname')
        server += '/announce/motd'
        dialogs.SingleMessageWindow(account, server, 'send')

    def on_update_motd(self, action, param):
        account = param.get_string()
        server = gajim.config.get_per('accounts', account, 'hostname')
        server += '/announce/motd/update'
        dialogs.SingleMessageWindow(account, server, 'send')

    def on_delete_motd(self, action, param):
        account = param.get_string()
        server = gajim.config.get_per('accounts', account, 'hostname')
        server += '/announce/motd/delete'
        gajim.connections[account].send_motd(server)

    # Help Actions

    def on_contents(self, action, param):
        helpers.launch_browser_mailer(
            'url', 'https://dev.gajim.org/gajim/gajim/wikis')

    def on_faq(self, action, param):
        helpers.launch_browser_mailer(
            'url', 'https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq')

    def on_keyboard_shortcuts(self, action, param):
        shortcuts_window.show(self.application.get_active_window())

    def on_features(self, action, param):
        features_window.FeaturesWindow()

    def on_about(self, action, param):
        dialogs.AboutDialog()

    # View Actions

    def on_file_transfers(self, action, param):
        if gajim.interface.instances['file_transfers']. \
                window.get_property('visible'):
            gajim.interface.instances['file_transfers'].window.present()
        else:
            gajim.interface.instances['file_transfers'].window.show_all()

    def on_history(self, action, param):
        if 'logs' in gajim.interface.instances:
            gajim.interface.instances['logs'].window.present()
        else:
            gajim.interface.instances['logs'] = history_window.\
                HistoryWindow()
