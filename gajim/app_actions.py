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

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import helpers
from gajim.common.app import interface
from gajim.common.exceptions import GajimGeneralException
from gajim import dialogs

from gajim.gui.dialogs import ShortcutsWindow
from gajim.gui.about import AboutDialog
from gajim.gui.discovery import ServiceDiscoveryWindow
from gajim.gui.util import open_window

# General Actions


def on_add_contact_jid(_action, param):
    jid = param.get_string()
    open_window('AddContact', account=None, jid=jid)


# Application Menu Actions


def on_preferences(_action, _param):
    open_window('Preferences')


def on_plugins(_action, _param):
    open_window('PluginsWindow')


def on_accounts(_action, param):
    window = open_window('AccountsWindow')
    account = param.get_string()
    if account:
        window.select_account(account)


def on_history_manager(_action, _param):
    open_window('HistoryManager')


def on_bookmarks(_action, param):
    account = param.get_string()
    open_window('Bookmarks', account=account)


def on_quit(_action, _param):
    app.window.quit()


def on_new_chat(_action, param):
    window = open_window('StartChatDialog')
    search_text = param.get_string()
    if search_text:
        window.set_search_text(search_text)


# Accounts Actions


def on_profile(_action, param):
    account = param.get_string()
    open_window('ProfileWindow', account=account)


def on_send_server_message(_action, param):
    account = param.get_string()
    server = app.settings.get_account_setting(account, 'hostname')
    server += '/announce/online'
    open_window('SingleMessageWindow', account=account, recipients=server)


def on_service_disco(_action, param):
    account = param.get_string()
    server_jid = app.settings.get_account_setting(account, 'hostname')
    if server_jid in interface.instances[account]['disco']:
        interface.instances[account]['disco'][server_jid].\
            window.present()
    else:
        try:
            # Object will add itself to the window dict
            ServiceDiscoveryWindow(account, address_entry=True)
        except GajimGeneralException:
            pass

def on_create_gc(_action, param):
    account = param.get_string()
    open_window('CreateGroupchatWindow', account=account or None)


def on_add_contact(_action, param):
    account, jid = param.get_strv()
    open_window('AddContact', account=account, jid=jid or None)


def on_single_message(_action, param):
    account = param.get_string()
    open_window('SingleMessageWindow', account=account)


def on_merge_accounts(action, param):
    action.set_state(param)
    value = param.get_boolean()
    app.settings.set('mergeaccounts', value)
    # Do not merge accounts if only one active
    if len(app.connections) >= 2:
        app.interface.roster.regroup = value
    else:
        app.interface.roster.regroup = False
    app.interface.roster.setup_and_draw_roster()


def on_add_account(action, _param):
    open_window('AccountWizard')


def on_import_contacts(_action, param):
    account = param.get_string()
    if 'import_contacts' in app.interface.instances:
        app.interface.instances['import_contacts'].dialog.present()
    else:
        app.interface.instances['import_contacts'] = \
            dialogs.SynchroniseSelectAccountDialog(account)


# Advanced Actions

def on_pep_config(_action, param):
    account = param.get_string()
    open_window('PEPConfig', account=account)


def on_mam_preferences(_action, param):
    account = param.get_string()
    open_window('MamPreferences', account=account)


def on_blocking_list(_action, param):
    account = param.get_string()
    open_window('BlockingList', account=account)


def on_history_sync(_action, param):
    account = param.get_string()
    open_window('HistorySyncAssistant',
                account=account,
                parent=interface.roster.window)


def on_server_info(_action, param):
    account = param.get_string()
    open_window('ServerInfo', account=account)


def on_xml_console(_action, _param):
    open_window('XMLConsoleWindow')


def on_manage_proxies(_action, _param):
    open_window('ManageProxies')


# Admin Actions


def on_set_motd(_action, param):
    account = param.get_string()
    server = app.settings.get_account_setting(account, 'hostname')
    server += '/announce/motd'
    open_window('SingleMessageWindow', account=account, recipients=server)


def on_update_motd(_action, param):
    account = param.get_string()
    server = app.settings.get_account_setting(account, 'hostname')
    server += '/announce/motd/update'
    open_window('SingleMessageWindow', account=account, recipients=server)


def on_delete_motd(_action, param):
    account = param.get_string()
    app.connections[account].get_module('Announce').delete_motd()

# Help Actions


def on_contents(_action, _param):
    helpers.open_uri('https://dev.gajim.org/gajim/gajim/wikis')


def on_faq(_action, _param):
    helpers.open_uri('https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq')


def on_keyboard_shortcuts(_action, _param):
    ShortcutsWindow()


def on_features(_action, _param):
    open_window('Features')


def on_about(_action, _param):
    AboutDialog()

# View Actions


def on_file_transfers(_action, _param):
    if interface.instances['file_transfers']. \
            window.get_property('visible'):
        interface.instances['file_transfers'].window.present()
    else:
        interface.instances['file_transfers'].window.show_all()


def on_open_event(_action, param):
    dict_ = param.unpack()
    app.interface.handle_event(
        dict_['account'], dict_['jid'], dict_['type_'])


def on_remove_event(_action, param):
    dict_ = param.unpack()
    account, jid, type_ = dict_['account'], dict_['jid'], dict_['type_']
    event = app.events.get_first_event(account, jid, type_)
    app.events.remove_events(account, jid, event)
    win = app.interface.msg_win_mgr.get_window(jid, account)
    if win:
        win.redraw_tab(win.get_control(jid, account))
        win.show_title()

# Other Actions

def toggle_ipython(_action, _param):
    """
    Show/hide the ipython window
    """
    win = app.ipython_window
    if win and win.window.is_visible():
        win.present()
    else:
        app.interface.create_ipython_window()


def show_next_pending_event(_action, _param):
    """
    Show the window(s) with next pending event in tabbed/group chats
    """
    if app.events.get_nb_events():
        account, jid, event = app.events.get_first_systray_event()
        if not event:
            return
        app.interface.handle_event(account, jid, event.type_)


def open_mail(_action, param):
    uri = param.get_string()
    if not uri.startswith('mailto:'):
        uri = 'mailto:%s' % uri
    helpers.open_uri(uri)


def open_link(_action, param):
    account, uri = param.get_strv()
    helpers.open_uri(uri, account=account)


def copy_text(_action, param):
    text = param.get_string()
    clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clip.set_text(text, -1)


def start_chat(_action, param):
    account, jid = param.get_strv()
    app.interface.new_chat_from_jid(account, jid)


def on_groupchat_join(_action, param):
    account, jid = param.get_strv()
    open_window('GroupchatJoin', account=account, jid=jid)
