#
# Copyright (C) 2017 Philipp Hörist <philipp AT hoerist.com>
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

from gajim.common import app
from gajim.common import helpers
from gajim.common.app import interface
from gajim.common.exceptions import GajimGeneralException
from gajim import config
from gajim import dialogs
from gajim.gtk import shortcuts_window
from gajim import accounts_window
import gajim.plugins.gui
from gajim import disco
from gajim.gtk.history_sync import HistorySyncAssistant
from gajim.gtk.server_info import ServerInfoDialog
from gajim.gtk.mam_preferences import MamPreferences
from gajim.gtk.preferences import Preferences
from gajim.gtk import JoinGroupchatWindow
from gajim.gtk import StartChatDialog
from gajim.gtk import AddNewContactWindow
from gajim.gtk import SingleMessageWindow
from gajim.gtk import XMLConsoleWindow
from gajim.gtk import AboutDialog
from gajim.gtk import PrivacyListsWindow
from gajim.gtk import ManageBookmarksWindow
from gajim.gtk import FeaturesDialog
from gajim.gtk import AccountCreationWizard
from gajim.gtk import HistoryWindow


# General Actions

def on_add_contact_jid(action, param):
    AddNewContactWindow(None, param.get_string())

# Application Menu Actions


def on_preferences(action, param):
    window = app.get_app_window(Preferences)
    if window is None:
        Preferences()
    else:
        window.present()


def on_plugins(action, param):
    if 'plugins' in interface.instances:
        interface.instances['plugins'].window.present()
    else:
        interface.instances['plugins'] = gajim.plugins.gui.PluginsWindow()


def on_accounts(action, param):
    if 'accounts' in app.interface.instances:
        app.interface.instances['accounts'].present()
    else:
        app.interface.instances['accounts'] = accounts_window.AccountsWindow()


def on_history_manager(action, param):
    from gajim.history_manager import HistoryManager
    HistoryManager()


def on_manage_bookmarks(action, param):
    ManageBookmarksWindow()


def on_quit(action, param):
    interface.roster.on_quit_request()


def on_new_chat(action, param):
    if 'start_chat' in app.interface.instances:
        app.interface.instances['start_chat'].present()
    else:
        app.interface.instances['start_chat'] = StartChatDialog()

# Accounts Actions


def on_profile(action, param):
    interface.edit_own_details(param.get_string())


def on_activate_bookmark(action, param):
    dict_ = param.unpack()
    account, jid, nick, password = \
        dict_['account'], dict_['jid'], None, None
    if 'nick' in dict_:
        nick = dict_['nick']
    if 'password' in dict_:
        password = dict_['password']
    interface.join_gc_room(account, jid, nick, password)


def on_send_server_message(action, param):
    account = param.get_string()
    server = app.config.get_per('accounts', account, 'hostname')
    server += '/announce/online'
    SingleMessageWindow(account, server, 'send')


def on_service_disco(action, param):
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


def on_join_gc(action, param):
    account = None
    if param is None:
        if not app.get_connected_accounts():
            return
    else:
        account = param.get_string()
    window = app.get_app_window(JoinGroupchatWindow)
    if window is None:
        JoinGroupchatWindow(account, None)
    else:
        window.present()


def on_add_contact(action, param):
    window = app.get_app_window(AddNewContactWindow)
    if window is None:
        AddNewContactWindow(param.get_string())
    else:
        window.present()


def on_single_message(action, param):
    SingleMessageWindow(param.get_string(), action='send')


def on_merge_accounts(action, param):
    action.set_state(param)
    value = param.get_boolean()
    app.config.set('mergeaccounts', value)
    # Do not merge accounts if only one active
    if len(app.connections) >= 2:
        app.interface.roster.regroup = value
    else:
        app.interface.roster.regroup = False
    app.interface.roster.setup_and_draw_roster()


def on_use_pgp_agent(action, param):
    action.set_state(param)
    app.config.set('use_gpg_agent', param.get_boolean())


def on_add_account(action, param):
    if 'account_creation_wizard' in app.interface.instances:
        app.interface.instances['account_creation_wizard'].window.present()
    else:
        app.interface.instances['account_creation_wizard'] = \
            AccountCreationWizard()


def on_import_contacts(action, param):
    account = param.get_string()
    if 'import_contacts' in app.interface.instances:
        app.interface.instances['import_contacts'].dialog.present()
    else:
        app.interface.instances['import_contacts'] = \
            dialogs.SynchroniseSelectAccountDialog(account)

# Advanced Actions


def on_mam_preferences(action, param):
    account = param.get_string()
    window = app.get_app_window(MamPreferences, account)
    if window is None:
        MamPreferences(account)
    else:
        window.present()


def on_history_sync(action, param):
    account = param.get_string()
    if 'history_sync' in interface.instances[account]:
        interface.instances[account]['history_sync'].present()
    else:
        interface.instances[account]['history_sync'] = \
            HistorySyncAssistant(account, interface.roster.window)


def on_privacy_lists(action, param):
    account = param.get_string()
    if 'privacy_lists' in interface.instances[account]:
        interface.instances[account]['privacy_lists'].window.present()
    else:
        interface.instances[account]['privacy_lists'] = \
            PrivacyListsWindow(account)


def on_server_info(action, param):
    account = param.get_string()
    if 'server_info' in interface.instances[account]:
        interface.instances[account]['server_info'].present()
    else:
        interface.instances[account]['server_info'] = \
            ServerInfoDialog(account)


def on_xml_console(action, param):
    account = param.get_string()
    if 'xml_console' in interface.instances[account]:
        interface.instances[account]['xml_console'].present()
    else:
        interface.instances[account]['xml_console'] = \
            XMLConsoleWindow(account)


def on_manage_proxies(action, param):
    if 'manage_proxies' in app.interface.instances:
        app.interface.instances['manage_proxies'].window.present()
    else:
        app.interface.instances['manage_proxies'] = \
            config.ManageProxiesWindow(interface.roster.window)

# Admin Actions


def on_set_motd(action, param):
    account = param.get_string()
    server = app.config.get_per('accounts', account, 'hostname')
    server += '/announce/motd'
    SingleMessageWindow(account, server, 'send')


def on_update_motd(action, param):
    account = param.get_string()
    server = app.config.get_per('accounts', account, 'hostname')
    server += '/announce/motd/update'
    SingleMessageWindow(account, server, 'send')


def on_delete_motd(action, param):
    account = param.get_string()
    server = app.config.get_per('accounts', account, 'hostname')
    server += '/announce/motd/delete'
    app.connections[account].send_motd(server)

# Help Actions


def on_contents(action, param):
    helpers.launch_browser_mailer(
        'url', 'https://dev.gajim.org/gajim/gajim/wikis')


def on_faq(action, param):
    helpers.launch_browser_mailer(
        'url', 'https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq')


def on_keyboard_shortcuts(action, param):
    shortcuts_window.show(app.app.get_active_window())


def on_features(action, param):
    FeaturesDialog()


def on_about(action, param):
    AboutDialog()

# View Actions


def on_file_transfers(action, param):
    if interface.instances['file_transfers']. \
            window.get_property('visible'):
        interface.instances['file_transfers'].window.present()
    else:
        interface.instances['file_transfers'].window.show_all()


def on_history(action, param):
    if 'logs' in interface.instances:
        interface.instances['logs'].window.present()
    else:
        interface.instances['logs'] = HistoryWindow()


def on_open_event(action, param):
    dict_ = param.unpack()
    app.interface.handle_event(
        dict_['account'], dict_['jid'], dict_['type_'])


# Other Actions

def toggle_ipython(action, param):
    """
    Show/hide the ipython window
    """
    win = app.ipython_window
    if win and win.window.is_visible():
        win.present()
    else:
        app.interface.create_ipython_window()


def show_next_pending_event(action, param):
    """
    Show the window(s) with next pending event in tabbed/group chats
    """
    if app.events.get_nb_events():
        account, jid, event = app.events.get_first_systray_event()
        if not event:
            return
        app.interface.handle_event(account, jid, event.type_)
