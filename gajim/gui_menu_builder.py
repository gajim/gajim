# Copyright (C) 2009-2014 Yann Leboulanger <asterix AT lagaule.org>
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
from typing import Tuple
from typing import List
from typing import Union
from typing import Any
from typing import Optional

from urllib.parse import quote

from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib

from nbxmpp import JID

from gajim.common import app
from gajim.common import types
from gajim.common.helpers import is_affiliation_change_allowed
from gajim.common.helpers import is_role_change_allowed
from gajim.common.helpers import jid_is_blocked
from gajim.common.helpers import reduce_chars_newlines
from gajim.common.i18n import _
from gajim.common.i18n import get_short_lang_code
from gajim.common.const import URIType
from gajim.common.const import URIAction
from gajim.common.structs import URI

from gajim.gui.const import ControlType


def get_singlechat_menu(control_id: str,
                        account: str,
                        jid: JID,
                        type_: ControlType
                        ) -> Gio.Menu:
    client = app.get_client(account)
    is_self_contact = jid.bare == client.get_own_jid().bare

    singlechat_menu: List[Any] = [
        (_('Send File'), [
            ('win.send-file-httpupload-', _('Upload File…')),
            ('win.send-file-jingle-', _('Send File Directly…'))
        ])
    ]

    additional_menu = [
        ('win.send-marker-', _('Send Read Markers')),
        (_('Send Chatstate'), ['chatstate']),
        ('win.invite-contacts-', _('Invite Contacts…')),
        ('win.add-to-roster-', _('Add to Contact List…')),
        ('win.block-contact-', _('Block Contact…')),
        ('win.start-call-', _('Start Call…')),
        ('win.information-', _('Information'))
    ]

    if is_self_contact:
        singlechat_menu.append(('profile', _('Profile')))
    else:
        singlechat_menu.extend(additional_menu)

    singlechat_menu.append(('win.search-history', _('Search…')))

    def build_chatstate_menu() -> Gio.Menu:
        menu = Gio.Menu()
        entries = [
            (_('Disabled'), 'disabled'),
            (_('Composing Only'), 'composing_only'),
            (_('All Chat States'), 'all')
        ]

        for entry in entries:
            label, setting = entry
            action = f'win.send-chatstate-{control_id}::{setting}'
            menu.append(label, action)
        return menu

    def build_menu(preset):
        menu = Gio.Menu()
        for item in preset:
            if isinstance(item[1], str):
                action_name, label = item
                if action_name == 'win.send-marker-' and type_ == 'pm':
                    continue

                if action_name == 'win.search-history':
                    menuitem = Gio.MenuItem.new(label, action_name)
                    menuitem.set_action_and_target_value(action_name, None)
                    menu.append_item(menuitem)
                elif action_name == 'profile':
                    action = f'app.{account}-{action_name}'
                    menuitem = Gio.MenuItem.new(label, action)
                    variant = GLib.Variant('s', account)
                    menuitem.set_action_and_target_value(action, variant)
                    menu.append_item(menuitem)
                elif action_name == 'app.browse-history':
                    menuitem = Gio.MenuItem.new(label, action_name)
                    dict_ = {'account': GLib.Variant('s', account),
                             'jid': GLib.Variant('s', str(jid))}
                    variant_dict = GLib.Variant('a{sv}', dict_)
                    menuitem.set_action_and_target_value(action_name,
                                                         variant_dict)
                    menu.append_item(menuitem)
                else:
                    menu.append(label, action_name + control_id)
            else:
                label, sub_menu = item
                if 'chatstate' in sub_menu:
                    submenu = build_chatstate_menu()
                else:
                    submenu = build_menu(sub_menu)
                menu.append_submenu(label, submenu)
        return menu

    return build_menu(singlechat_menu)


def get_groupchat_menu(control_id: str, account: str, jid: str) -> Gio.Menu:
    groupchat_menu = [
        ('win.information-', _('Information')),
        ('win.groupchat-settings-', _('Settings…')),
        ('win.groupchat-manage-', _('Manage…')),
        ('win.rename-groupchat-', _('Rename Chat…')),
        ('win.change-nickname-', _('Change Nickname…')),
        ('win.request-voice-', _('Request Voice')),
        ('win.execute-command-', _('Execute Command…')),
        ('win.search-history', _('Search…')),
    ]

    def build_menu(preset: list[tuple[str, str]]) -> Gio.Menu:
        menu = Gio.Menu()
        for item in preset:
            action_name, label = item
            if action_name == 'win.search-history':
                menuitem = Gio.MenuItem.new(label, action_name)
                menuitem.set_action_and_target_value(action_name, None)
                menu.append_item(menuitem)

            elif action_name == 'app.browse-history':
                menuitem = Gio.MenuItem.new(label, action_name)
                dict_ = {'account': GLib.Variant('s', account),
                            'jid': GLib.Variant('s', jid)}
                variant_dict = GLib.Variant('a{sv}', dict_)
                menuitem.set_action_and_target_value(
                    action_name, variant_dict)
                menu.append_item(menuitem)

            elif action_name == 'win.execute-command-':
                action_name = action_name + control_id
                menuitem = Gio.MenuItem.new(label, action_name)
                menuitem.set_action_and_target_value(
                    action_name, GLib.Variant('s', ''))
                menu.append_item(menuitem)
            else:
                menu.append(label, action_name + control_id)

        return menu

    return build_menu(groupchat_menu)


def get_account_menu(account: str) -> Gio.Menu:
    '''
    [(action, label/sub_menu)]
        action: string
        label: string
        sub menu: list
    '''
    account_menu: list[tuple[str, Union[str, list[tuple[str, str]]]]] = [
        ('-profile', _('Profile')),
        ('-start-single-chat', _('Send Single Message…')),
        ('-services', _('Discover Services…')),
        ('-server-info', _('Server Info')),
        (_('Advanced'), [
            ('-archive', _('Archiving Preferences')),
            ('-blocking', _('Blocking List')),
            ('-pep-config', _('PEP Configuration')),
            ('-sync-history', _('Synchronise History…')),
        ]),
        (_('Admin'), [
            ('-send-server-message', _('Send Server Message…')),
            ('-set-motd', _('Set MOTD…')),
            ('-update-motd', _('Update MOTD…')),
            ('-delete-motd', _('Delete MOTD…'))
        ]),
    ]

    if app.settings.get('developer_modus'):
        account_menu[5][1].append(('-bookmarks', _('Bookmarks')))

    def build_menu(preset: list[tuple[str, Union[str, list[tuple[str, str]]]]]):
        menu = Gio.Menu()
        for item in preset:
            if isinstance(item[1], str):
                action, label = item
                action = f'app.{account}{action}'
                menuitem = Gio.MenuItem.new(label, action)
                variant = GLib.Variant('s', account)
                menuitem.set_action_and_target_value(action, variant)
                menu.append_item(menuitem)
            else:
                label, sub_menu = item
                # This is a submenu
                submenu = build_menu(sub_menu)
                menu.append_submenu(label, submenu)
        return menu

    return build_menu(account_menu)


def build_accounts_menu() -> None:
    menubar = app.app.get_menubar()
    # Accounts Submenu
    menu_position = 1

    acc_menu = menubar.get_item_link(menu_position, 'submenu')
    acc_menu.remove_all()

    accounts_list = sorted(app.settings.get_active_accounts())
    if not accounts_list:
        add_account_item = Gio.MenuItem.new(_('_Add Account…'),
                                            'app.accounts::')
        acc_menu.append_item(add_account_item)
        return

    if len(accounts_list) > 1:
        modify_accounts_item = Gio.MenuItem.new(_('_Modify Accounts…'),
                                                'app.accounts::')
        acc_menu.append_item(modify_accounts_item)
        add_contact_item = Gio.MenuItem.new(_('Add _Contact…'),
                                            'app.add-contact::')
        acc_menu.append_item(add_contact_item)
        for acc in accounts_list:
            label = escape_mnemonic(app.get_account_label(acc))
            if acc != 'Local':
                acc_menu.append_submenu(
                    label, get_account_menu(acc))
    else:
        acc_menu = get_account_menu(accounts_list[0])
        modify_account_item = Gio.MenuItem.new(_('_Modify Account…'),
                                               'app.accounts::')
        acc_menu.insert_item(0, modify_account_item)
        add_contact_item = Gio.MenuItem.new(_('Add _Contact…'),
                                            'app.add-contact::')
        acc_menu.insert_item(1, add_contact_item)
        menubar.remove(menu_position)
        menubar.insert_submenu(menu_position, _('Accounts'), acc_menu)


def get_encryption_menu(control_id: str,
                        control_type: ControlType,
                        zeroconf: bool = False
                        ) -> Optional[Gio.Menu]:
    menu = Gio.Menu()
    menu.append(
        _('Disabled'), f'win.set-encryption-{control_id}::disabled')
    for name, plugin in app.plugin_manager.encryption_plugins.items():
        if control_type.is_groupchat:
            if not hasattr(plugin, 'allow_groupchat'):
                continue
        if control_type.is_privatechat:
            if not hasattr(plugin, 'allow_privatechat'):
                continue
        if zeroconf:
            if not hasattr(plugin, 'allow_zeroconf'):
                continue
        menu_action = f'win.set-encryption-{control_id}::{name}'
        menu.append(name, menu_action)
    if menu.get_n_items() == 1:
        return None
    return menu


def get_conv_action_context_menu(account: str, selected_text: str) -> Gtk.MenuItem:
    selected_text_short = reduce_chars_newlines(selected_text, 10, 1)

    action_menu_item = Gtk.MenuItem.new_with_mnemonic(
        _('_Actions for "%s"') % selected_text_short)
    submenu = Gtk.Menu()
    action_menu_item.set_submenu(submenu)

    uri_text = quote(selected_text.encode('utf-8'))

    if app.settings.get('always_english_wikipedia'):
        uri = (f'https://en.wikipedia.org/wiki/'
               f'Special:Search?search={uri_text}')
    else:
        uri = (f'https://{get_short_lang_code()}.wikipedia.org/'
               f'wiki/Special:Search?search={uri_text}')
    item = Gtk.MenuItem.new_with_mnemonic(_('Read _Wikipedia Article'))
    value = GLib.Variant.new_strv([account, uri])
    item.set_action_target_value(value)
    submenu.append(item)

    item = Gtk.MenuItem.new_with_mnemonic(
        _('Look it up in _Dictionary'))
    dict_link = app.settings.get('dictionary_url')
    if dict_link == 'WIKTIONARY':
        # Default is wikitionary.org
        if app.settings.get('always_english_wiktionary'):
            uri = (f'https://en.wiktionary.org/wiki/'
                   f'Special:Search?search={uri_text}')
        else:
            uri = (f'https://{get_short_lang_code()}.wiktionary.org/'
                   f'wiki/Special:Search?search={uri_text}')
    else:
        if dict_link.find('%s') == -1:
            # There has to be a '%s' in the url if it’s not WIKTIONARY
            item = Gtk.MenuItem.new_with_label(
                _('Dictionary URL is missing a "%s"'))
            item.set_sensitive(False)
        else:
            uri = dict_link % uri_text
    value = GLib.Variant.new_strv([account, uri])
    item.set_action_target_value(value)
    submenu.append(item)

    search_link = app.settings.get('search_engine')
    if search_link.find('%s') == -1:
        # There has to be a '%s' in the url
        item = Gtk.MenuItem.new_with_label(
            _('Web Search URL is missing a "%s"'))
        item.set_sensitive(False)
    else:
        item = Gtk.MenuItem.new_with_mnemonic(_('Web _Search for it'))
        uri = search_link % uri_text
    value = GLib.Variant.new_strv([account, uri])
    item.set_action_target_value(value)
    submenu.append(item)

    item = Gtk.MenuItem.new_with_mnemonic(_('Open as _Link'))
    value = GLib.Variant.new_strv([account, uri_text])
    item.set_action_target_value(value)
    submenu.append(item)

    for item in submenu:
        item.set_action_name('app.open-link')

    return action_menu_item


def get_conv_uri_context_menu(account: str, uri: URI) -> Optional[Gtk.Menu]:
    if uri.type == URIType.XMPP:
        if uri.action == URIAction.JOIN:
            context_menu = [
                ('copy-text', _('Copy XMPP Address')),
                ('groupchat-join', _('Join Groupchat')),
            ]
        else:
            context_menu = [
                ('copy-text', _('Copy XMPP Address')),
                ('-start-chat', _('Start Chat')),
                ('-add-contact', _('Add to Contact List…')),
            ]

    elif uri.type == URIType.WEB:
        context_menu = [
            ('copy-text', _('Copy Link Location')),
            ('open-link', _('Open Link in Browser')),
        ]

    elif uri.type == URIType.MAIL:
        context_menu = [
            ('copy-text', _('Copy Email Address')),
            ('open-mail', _('Open Email Composer')),
        ]

    elif uri.type == URIType.GEO:
        context_menu = [
            ('copy-text', _('Copy Location')),
            ('open-link', _('Show Location')),
        ]

    elif uri.type == URIType.AT:
        context_menu = [
            ('copy-text', _('Copy XMPP Address/Email')),
            ('open-mail', _('Open Email Composer')),
            ('-start-chat', _('Start Chat')),
            ('groupchat-join', _('Join Groupchat')),
            ('-add-contact', _('Add to Contact List…')),
        ]
    else:
        return None

    menu = Gtk.Menu()
    for item in context_menu:
        action, label = item
        menuitem = Gtk.MenuItem()
        menuitem.set_label(label)

        if action.startswith('-'):
            action = f'app.{account}{action}'
        else:
            action = f'app.{action}'
        menuitem.set_action_name(action)

        data = uri.data
        if uri.type == URIType.XMPP:
            if isinstance(uri.data, dict):
                data = uri.data['jid']
            else:
                data = ''
        assert isinstance(data, str)

        if action in ('app.open-mail', 'app.copy-text'):
            value = GLib.Variant.new_string(data)
        else:
            value = GLib.Variant.new_strv([account, data])
        menuitem.set_action_target_value(value)
        menuitem.show()
        menu.append(menuitem)
    return menu


def get_roster_menu(account: str, jid: str, gateway: bool = False) -> Gio.Menu:
    if jid_is_blocked(account, jid):
        block_label = _('Unblock')
    else:
        block_label = _('Block…')
    menu_items = [
        ('contact-info', _('Information')),
        ('execute-command', _('Execute Command…')),
        ('block-contact', block_label),
        ('remove-contact', _('Remove…')),
    ]
    if gateway:
        menu_items.insert(1, ('modify-gateway', _('Modify Gateway…')))

    menu = Gio.Menu()
    for item in menu_items:
        action, label = item
        action = f'win.{action}-{account}'
        menuitem = Gio.MenuItem.new(label, action)
        variant = GLib.Variant('s', jid)
        menuitem.set_action_and_target_value(action, variant)
        menu.append_item(menuitem)

    return menu


def get_subscription_menu(account: str, jid: str) -> Gio.Menu:
    menu = Gio.Menu()

    action_name = 'win.add-chat'
    add_chat = Gio.MenuItem.new(_('Start Chat'), action_name)
    dict_ = {
        'account': GLib.Variant('s', account),
        'jid': GLib.Variant('s', str(jid)),
        'type_': GLib.Variant('s', 'contact'),
        'select': GLib.Variant.new_boolean(True),
    }
    variant_dict = GLib.Variant('a{sv}', dict_)
    add_chat.set_action_and_target_value(action_name, variant_dict)
    menu.append_item(add_chat)

    menu_items = [
        ('contact-info', _('Information')),
        ('subscription-block', _('Block')),
        ('subscription-report', _('Report')),
        ('subscription-deny', _('Deny')),
    ]
    for item in menu_items:
        action, label = item
        action = f'win.{action}-{account}'
        menuitem = Gio.MenuItem.new(label, action)
        variant = GLib.Variant('s', str(jid))
        menuitem.set_action_and_target_value(action, variant)
        menu.append_item(menuitem)

    return menu


def get_start_chat_row_menu(account: str,
                            jid: Union[JID, str]
                            ) -> Gio.Menu:
    jid = str(jid)
    menu_items: List[Tuple[str, str]] = [
        ('forget-groupchat', _('Forget this Group Chat')),
    ]
    menu = Gio.Menu()
    for item in menu_items:
        action, label = item
        action = f'app.{action}'
        menuitem = Gio.MenuItem.new(label, action)
        variant_list = GLib.Variant('as', [account, jid])
        menuitem.set_action_and_target_value(action, variant_list)
        menu.append_item(menuitem)
    return menu


def get_chat_list_row_menu(workspace_id: str,
                           account: str,
                           jid: Union[JID, str],
                           pinned: bool
                           ) -> Gio.Menu:
    jid = str(jid)
    client = app.get_client(account)
    contact = client.get_module('Contacts').get_contact(jid)

    toggle_label = _('Unpin Chat') if pinned else _('Pin Chat')

    menu_items: List[Any] = [
        ('toggle-chat-pinned', toggle_label),
    ]

    workspaces = app.settings.get_workspaces()
    if len(workspaces) > 1:
        menu_items.append((_('Move Chat'), []))

    is_self_contact = contact.jid.bare == client.get_own_jid().bare
    if (not contact.is_groupchat and not contact.is_in_roster and
            not is_self_contact):
        if contact.is_pm_contact:
            if contact.real_jid is not None:
                menu_items.append(('add-to-roster', _('Add to Contact List…')))
        else:
            menu_items.append(('add-to-roster', _('Add to Contact List…')))

    unread_count = app.window.get_chat_unread_count(
        account, jid, include_silent=True)
    if unread_count is not None and unread_count > 0:
        menu_items.append(('mark-as-read', _('Mark as read')))

    menu = Gio.Menu()
    for item in menu_items:
        if isinstance(item[1], str):
            action, label = item
            action = f'win.{action}'
            menuitem = Gio.MenuItem.new(label, action)
            variant_list = GLib.Variant(
                'as', [workspace_id, account, jid])
            menuitem.set_action_and_target_value(action, variant_list)
            menu.append_item(menuitem)
        else:
            # This is a submenu
            if len(workspaces) > 1:
                submenu = build_workspaces_submenu(
                    workspace_id, account, jid)
                menu.append_submenu(item[0], submenu)

    return menu


def build_workspaces_submenu(current_workspace_id: str,
                             account: str,
                             jid: str
                             ) -> Gio.Menu:
    submenu = Gio.Menu()
    for workspace_id in app.settings.get_workspaces():
        if workspace_id == current_workspace_id:
            continue
        name = app.settings.get_workspace_setting(workspace_id, 'name')
        action = 'win.move-chat-to-workspace'
        menuitem = Gio.MenuItem.new(name, action)
        variant_list = GLib.Variant('as', [workspace_id, account, jid])
        menuitem.set_action_and_target_value(action, variant_list)
        submenu.append_item(menuitem)
    return submenu


def get_groupchat_roster_menu(account: str,
                              control_id: str,
                              self_contact: types.GroupchatParticipant,
                              contact: types.GroupchatParticipant
                              ) -> Gtk.Menu:
    menu = Gtk.Menu()
    real_jid = ''
    if contact.real_jid is not None:
        real_jid = contact.real_jid.bare

    item = Gtk.MenuItem(label=_('Information'))
    action = f'win.contact-information-{control_id}::{contact.name}'
    item.set_detailed_action_name(action)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Add to Contact List…'))
    action = f'app.{account}-add-contact(["{account}", "{real_jid}"])'
    if contact.real_jid is None:
        item.set_sensitive(False)
    else:
        item.set_detailed_action_name(action)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Execute Command…'))
    action = f'win.execute-command-{control_id}::{contact.name}'
    item.set_detailed_action_name(action)
    menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    item = Gtk.MenuItem(label=_('Kick'))
    action = f'win.kick-{control_id}::{contact.name}'
    if is_role_change_allowed(self_contact, contact):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Ban'))
    action = f'win.ban-{control_id}::{real_jid}'
    if is_affiliation_change_allowed(self_contact, contact, 'outcast'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    item = Gtk.MenuItem(label=_('Make Owner'))
    action = (f'win.change-affiliation-{control_id}'
              f'(["{contact.real_jid}", "owner"])')
    if is_affiliation_change_allowed(self_contact, contact, 'owner'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Make Admin'))
    action = (f'win.change-affiliation-{control_id}'
              f'(["{contact.real_jid}", "admin"])')
    if is_affiliation_change_allowed(self_contact, contact, 'admin'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Make Member'))
    action = (f'win.change-affiliation-{control_id}'
              f'(["{contact.real_jid}", "member"])')
    if is_affiliation_change_allowed(self_contact, contact, 'member'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Revoke Member'))
    action = (f'win.change-affiliation-{control_id}'
              f'(["{contact.real_jid}", "none"])')
    if is_affiliation_change_allowed(self_contact, contact, 'none'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    if contact.role.is_visitor:
        label = _('Grant Voice')
        role = 'participant'
    else:
        label = _('Revoke Voice')
        role = 'visitor'

    item = Gtk.MenuItem(label=label)
    action = (f'win.change-role-{control_id}'
              f'(["{contact.name}", "{role}"])')
    if is_role_change_allowed(self_contact, contact):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    menu.show_all()
    return menu


class SearchMenu(Gtk.Menu):
    def __init__(self, treeview: Gtk.TreeView) -> None:
        Gtk.Menu.__init__(self)
        self._copy_item = Gtk.MenuItem(label=_('Copy'))
        self._copy_item.set_action_name('app.copy-text')
        self.set_copy_text('')
        self._copy_item.show()
        self.append(self._copy_item)
        self.attach_to_widget(treeview, None)

    def set_copy_text(self, text: str) -> None:
        self._copy_item.set_action_target_value(GLib.Variant('s', text))


def escape_mnemonic(label: Optional[str]) -> Optional[str]:
    if label is None:
        return None
    # Underscore inside a label means the next letter is a keyboard
    # shortcut. To show an underscore we have to use double underscore
    return label.replace('_', '__')
