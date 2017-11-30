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

import sys
import os

from gi.repository import Gtk

from gajim.common import app
from gajim.common import helpers
from gajim.common.app import interface
from gajim.common.exceptions import GajimGeneralException
from gajim import config
from gajim import dialogs
from gajim import features_window
from gajim import shortcuts_window
from gajim import accounts_window
import gajim.plugins.gui
from gajim import history_window
from gajim import disco
from gajim.history_sync import HistorySyncAssistant
from gajim.server_info import ServerInfoDialog


class AppActions():
    ''' Action Callbacks '''
    def __init__(self, application: Gtk.Application):
        self.application = application

    # General Actions

    def on_add_contact_jid(self, action, param):
        dialogs.AddNewContactWindow(None, param.get_string())

    # Application Menu Actions

    def on_preferences(self, action, param):
        if 'preferences' in interface.instances:
            interface.instances['preferences'].window.present()
        else:
            interface.instances['preferences'] = \
                config.PreferencesWindow()

    def on_plugins(self, action, param):
        if 'plugins' in interface.instances:
            interface.instances['plugins'].window.present()
        else:
            interface.instances['plugins'] = gajim.plugins.gui.PluginsWindow()

    def on_accounts(self, action, param):
        if 'accounts' in app.interface.instances:
            app.interface.instances['accounts'].present()
        else:
            app.interface.instances['accounts'] = accounts_window.AccountsWindow()

    def on_history_manager(self, action, param):
        from gajim.history_manager import HistoryManager
        HistoryManager()

    def on_manage_bookmarks(self, action, param):
        config.ManageBookmarksWindow()

    def on_quit(self, action, param):
        interface.roster.on_quit_request()

    def on_new_chat(self, action, param):
        if 'start_chat' in app.interface.instances:
            app.interface.instances['start_chat'].present()
        else:
            app.interface.instances['start_chat'] = dialogs.StartChatDialog()

    # Accounts Actions

    def on_profile(self, action, param):
        interface.edit_own_details(param.get_string())

    def on_activate_bookmark(self, action, param):
        dict_ = param.unpack()
        account, jid, nick, password = \
            dict_['account'], dict_['jid'], None, None
        if 'nick' in dict_:
            nick = dict_['nick']
        if 'password' in dict_:
            password = dict_['password']
        interface.join_gc_room(account, jid, nick, password)

    def on_send_server_message(self, action, param):
        account = param.get_string()
        server = app.config.get_per('accounts', account, 'hostname')
        server += '/announce/online'
        dialogs.SingleMessageWindow(account, server, 'send')

    def on_service_disco(self, action, param):
        account = param.get_string()
        server_jid = app.config.get_per('accounts', account, 'hostname')
        if server_jid in interface.instances[account]['disco']:
            interface.instances[account]['disco'][server_jid].\
                window.present()
        else:
            try:
                # Object will add itself to the window dict
                disco.ServiceDiscoveryWindow(account, address_entry=True)
            except GajimGeneralException:
                pass

    def on_join_gc(self, action, param):
        account = param.get_string()
        invisible_show = app.SHOW_LIST.index('invisible')
        if app.connections[account].connected == invisible_show:
            dialogs.ErrorDialog(_(
                'You cannot join a group chat while you are invisible'))
            return
        if 'join_gc' in interface.instances[account]:
            interface.instances[account]['join_gc'].present()
        else:
            interface.instances[account]['join_gc'] = \
                dialogs.JoinGroupchatWindow(account, None)

    def on_add_contact(self, action, param):
        dialogs.AddNewContactWindow(param.get_string())

    def on_single_message(self, action, param):
        dialogs.SingleMessageWindow(param.get_string(), action='send')

    def on_merge_accounts(self, action, param):
        action.set_state(param)
        value = param.get_boolean()
        app.config.set('mergeaccounts', value)
        if len(app.connections) >= 2: # Do not merge accounts if only one active
            app.interface.roster.regroup = value
        else:
            app.interface.roster.regroup = False
        app.interface.roster.setup_and_draw_roster()

    def on_use_pgp_agent(self, action, param):
        action.set_state(param)
        app.config.set('use_gpg_agent', param.get_boolean())

    def on_add_account(self, action, param):
        if 'account_creation_wizard' in app.interface.instances:
            app.interface.instances['account_creation_wizard'].window.present()
        else:
            app.interface.instances['account_creation_wizard'] = \
               config.AccountCreationWizardWindow()

    def on_import_contacts(self, action, param):
        account = param.get_string()
        if 'import_contacts' in app.interface.instances:
            app.interface.instances['import_contacts'].dialog.present()
        else:
            app.interface.instances['import_contacts'] = \
                dialogs.SynchroniseSelectAccountDialog(account)

    # Advanced Actions

    def on_archiving_preferences(self, action, param):
        account = param.get_string()
        if 'archiving_preferences' in interface.instances[account]:
            interface.instances[account]['archiving_preferences'].window.\
                present()
        else:
            interface.instances[account]['archiving_preferences'] = \
                dialogs.Archiving313PreferencesWindow(account)

    def on_history_sync(self, action, param):
        account = param.get_string()
        if 'history_sync' in interface.instances[account]:
            interface.instances[account]['history_sync'].present()
        else:
            interface.instances[account]['history_sync'] = \
                    HistorySyncAssistant(account, interface.roster.window)

    def on_privacy_lists(self, action, param):
        account = param.get_string()
        if 'privacy_lists' in interface.instances[account]:
            interface.instances[account]['privacy_lists'].window.present()
        else:
            interface.instances[account]['privacy_lists'] = \
                    dialogs.PrivacyListsWindow(account)

    def on_server_info(self, action, param):
        account = param.get_string()
        if 'server_info' in interface.instances[account]:
            interface.instances[account]['server_info'].present()
        else:
            interface.instances[account]['server_info'] = \
                    ServerInfoDialog(account)

    def on_xml_console(self, action, param):
        account = param.get_string()
        if 'xml_console' in interface.instances[account]:
            interface.instances[account]['xml_console'].present()
        else:
            interface.instances[account]['xml_console'] = \
                dialogs.XMLConsoleWindow(account)

    def on_manage_proxies(self, action, param):
        if 'manage_proxies' in app.interface.instances:
            app.interface.instances['manage_proxies'].window.present()
        else:
            app.interface.instances['manage_proxies'] = \
                config.ManageProxiesWindow(interface.roster.window)

    # Admin Actions

    def on_set_motd(self, action, param):
        account = param.get_string()
        server = app.config.get_per('accounts', account, 'hostname')
        server += '/announce/motd'
        dialogs.SingleMessageWindow(account, server, 'send')

    def on_update_motd(self, action, param):
        account = param.get_string()
        server = app.config.get_per('accounts', account, 'hostname')
        server += '/announce/motd/update'
        dialogs.SingleMessageWindow(account, server, 'send')

    def on_delete_motd(self, action, param):
        account = param.get_string()
        server = app.config.get_per('accounts', account, 'hostname')
        server += '/announce/motd/delete'
        app.connections[account].send_motd(server)

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
        if interface.instances['file_transfers']. \
                window.get_property('visible'):
            interface.instances['file_transfers'].window.present()
        else:
            interface.instances['file_transfers'].window.show_all()

    def on_history(self, action, param):
        if 'logs' in interface.instances:
            interface.instances['logs'].window.present()
        else:
            interface.instances['logs'] = history_window.\
                HistoryWindow()

    def on_open_event(self, action, param):
        dict_ = param.unpack()
        app.interface.handle_event(dict_['account'], dict_['jid'],
            dict_['type_'])

