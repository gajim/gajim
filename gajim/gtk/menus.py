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

from typing import Any
from typing import Iterator
from typing import cast
from typing import Optional
from typing import Union

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
from gajim.common.structs import VariantMixin
from gajim.common.modules.contacts import can_add_to_roster

from gajim.gui.structs import AddChatActionParams
from gajim.gui.structs import AddToRosterParams
from gajim.gui.structs import ForgetGroupchatActionParams
from gajim.gui.structs import MoveChatToWorkspaceAP
from gajim.gui.structs import RemoveHistoryActionParams
from gajim.gui.util import GajimMenu
from gajim.gui.const import ControlType


MenuValueT = Union[None, str, GLib.Variant, VariantMixin]
MenuItemListT = list[tuple[str, str, MenuValueT]]


def get_singlechat_menu(control_id: str,
                        account: str,
                        jid: JID,
                        type_: ControlType
                        ) -> Gio.Menu:
    client = app.get_client(account)
    is_self_contact = jid.bare == client.get_own_jid().bare
    contact = client.get_module('Contacts').get_contact(jid)

    self_contact_menu: list[tuple[str, Any]] = [
        ('profile', _('Profile')),
        (_('Send File'), [
            ('win.send-file-httpupload-', _('Upload File…')),
            ('win.send-file-jingle-', _('Send File Directly…'))
        ]),
        ('app.remove-history', _('Remove History…')),
        ('win.search-history', _('Search…'))
    ]

    singlechat_menu: list[tuple[str, Any]] = [
        ('win.information-', _('Details')),
        ('win.block-contact-', _('Block Contact…')),
        (_('Send File'), [
            ('win.send-file-httpupload-', _('Upload File…')),
            ('win.send-file-jingle-', _('Send File Directly…'))
        ]),
        ('win.start-call-', _('Start Call…')),
        ('win.search-history', _('Search…'))
    ]

    if can_add_to_roster(contact):
        singlechat_menu.append(('win.add-to-roster-',
                               _('Add to Contact List…')))

    def build_menu(preset: list[tuple[str, Any]]):
        menu = Gio.Menu()
        for item in preset:
            if isinstance(item[1], str):
                action_name, label = item
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
                elif action_name == 'app.remove-history':
                    params = RemoveHistoryActionParams(account=account, jid=jid)
                    menuitem = Gio.MenuItem.new(label, action_name)
                    menuitem.set_action_and_target_value(action_name,
                                                         params.to_variant())
                    menu.append_item(menuitem)
                else:
                    menu.append(label, action_name + control_id)
            else:
                label, sub_menu = item
                submenu = build_menu(sub_menu)
                menu.append_submenu(label, submenu)
        return menu

    if is_self_contact:
        return build_menu(self_contact_menu)

    return build_menu(singlechat_menu)


def get_groupchat_menu(control_id: str, account: str, jid: JID) -> GajimMenu:
    menuitems: MenuItemListT = [
        (_('Details'), f'win.groupchat-details-{control_id}', None),
        (_('Change Nickname…'), f'win.change-nickname-{control_id}', None),
        (_('Request Voice'), f'win.request-voice-{control_id}', None),
        (_('Execute Command…'), f'win.execute-command-{control_id}', '""'),
        (_('Search…'), 'win.search-history', None)
    ]

    return GajimMenu.from_list(menuitems)


def get_account_menu(account: str) -> GajimMenu:

    val = f'"{account}"'

    menuitems: MenuItemListT = [
        (_('Profile'), f'app.{account}-profile', val),
        (_('Discover Services…'), f'app.{account}-services', val),
        (_('Server Info'), f'app.{account}-server-info', val),
    ]

    menu = GajimMenu.from_list(menuitems)

    advanced_menuitems: MenuItemListT = [
        (_('Archiving Preferences'), f'app.{account}-archive', val),
        (_('Blocking List'), f'app.{account}-blocking', val),
        (_('PEP Configuration'), f'app.{account}-pep-config', val),
        (_('Synchronise History…'), f'app.{account}-sync-history', val),
    ]

    if app.settings.get('developer_modus'):
        advanced_menuitems.append(
            (_('Bookmarks'), f'app.{account}-bookmarks', val))

    menu.append_submenu(_('Advanced'), GajimMenu.from_list(advanced_menuitems))

    return menu


def build_accounts_menu() -> None:
    menubar = app.app.get_menubar()
    assert isinstance(menubar, Gio.Menu)
    # Accounts Submenu
    menu_position = 1

    acc_menu = menubar.get_item_link(menu_position, 'submenu')
    assert isinstance(acc_menu, Gio.Menu)
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
            acc_menu.append_submenu(label, get_account_menu(acc))
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
        menu_action = f'win.set-encryption-{control_id}::{name}'
        menu.append(name, menu_action)
    if menu.get_n_items() == 1:
        return None
    return menu


def get_conv_action_context_menu(account: str,
                                 selected_text: str
                                 ) -> Gtk.MenuItem:
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

    for item in cast(list[Gtk.MenuItem], submenu):
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
                ('-open-chat', _('Start Chat')),
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
            ('-open-chat', _('Start Chat')),
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


def get_roster_menu(account: str, jid: str, gateway: bool = False) -> GajimMenu:

    block_label = _('Block…')
    if jid_is_blocked(account, jid):
        block_label = _('Unblock')

    value = f'"{jid}"'

    menuitems: MenuItemListT = [
        (_('Details'), f'win.contact-info-{account}', value),
        (_('Execute Command…'), f'win.execute-command-{account}', value),
        (block_label, f'win.block-contact-{account}', value),
        (_('Remove…'), f'win.remove-contact-{account}', value),
    ]

    if gateway:
        menuitems.insert(
            1, (_('Modify Gateway…'), f'win.modify-gateway-{account}', value))

    return GajimMenu.from_list(menuitems)


def get_subscription_menu(account: str, jid: JID) -> GajimMenu:
    params = AddChatActionParams(account=account,
                                 jid=jid,
                                 type='contact',
                                 select=True)
    value = f'"{jid}"'
    menuitems: MenuItemListT = [
        (_('Start Chat'), 'win.add-chat', params),
        (_('Details'), f'win.contact-info-{account}', value),
        (_('Block'), f'win.subscription-block-{account}', value),
        (_('Report'), f'win.subscription-report-{account}', value),
        (_('Deny'), f'win.subscription-deny-{account}', value),
    ]

    return GajimMenu.from_list(menuitems)


def get_start_chat_row_menu(account: str, jid: JID) -> GajimMenu:
    params = ForgetGroupchatActionParams(account=account, jid=jid)
    menuitems: MenuItemListT = [
        (_('Forget this Group Chat'), 'app.forget-groupchat', params),
    ]

    return GajimMenu.from_list(menuitems)


def get_chat_list_row_menu(workspace_id: str,
                           account: str,
                           jid: JID,
                           pinned: bool
                           ) -> GajimMenu:

    client = app.get_client(account)
    contact = client.get_module('Contacts').get_contact(jid)

    menu = GajimMenu()

    toggle_label = _('Unpin Chat') if pinned else _('Pin Chat')
    menu.add_item(toggle_label, 'win.toggle-chat-pinned', None)

    workspaces = app.settings.get_workspaces()
    if len(workspaces) > 1:
        submenu = menu.add_submenu(_('Move Chat'))

        params = MoveChatToWorkspaceAP(workspace_id=workspace_id,
                                       account=account,
                                       jid=jid)

        for name in get_workspace_names(workspace_id, account, jid):
            submenu.add_item(name, 'win.move-chat-to-workspace', params)

    if can_add_to_roster(contact):
        params = AddToRosterParams(account=account, jid=jid)
        menu.add_item(_('Add to Contact List…'), 'win.add-to-roster', params)

    if app.window.get_chat_unread_count(account, jid, include_silent=True):
        menu.add_item(_('Mark as read'), 'win.mark-as-read', None)

    return menu


def get_workspace_names(current_workspace_id: str,
                        account: str,
                        jid: JID
                        ) -> Iterator[str]:

    for workspace_id in app.settings.get_workspaces():
        if workspace_id == current_workspace_id:
            continue
        yield app.settings.get_workspace_setting(workspace_id, 'name')


def get_groupchat_admin_menu(control_id: str,
                             self_contact: types.GroupchatParticipant,
                             contact: types.GroupchatParticipant) -> GajimMenu:

    menu = GajimMenu()

    action = f'win.change-affiliation-{control_id}'

    if is_affiliation_change_allowed(self_contact, contact, 'owner'):
        value = f'["{contact.real_jid}", "owner"]'
        menu.add_item(_('Make Owner'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'admin'):
        value = f'["{contact.real_jid}", "admin"]'
        menu.add_item(_('Make Admin'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'member'):
        value = f'["{contact.real_jid}", "member"]'
        menu.add_item(_('Make Member'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'none'):
        value = f'["{contact.real_jid}", "none"]'
        menu.add_item(_('Revoke Member'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'outcast'):
        value = f'"{contact.real_jid}"'
        menu.add_item(_('Ban…'), f'win.ban-{control_id}', value)

    if not menu.get_n_items():
        menu.add_item(_('Not Available'), 'dummy', None)

    return menu


def get_groupchat_mod_menu(control_id: str,
                           self_contact: types.GroupchatParticipant,
                           contact: types.GroupchatParticipant
                           ) -> GajimMenu:

    menu = GajimMenu()

    if is_role_change_allowed(self_contact, contact):
        value = f'"{contact.name}"'
        menu.add_item(_('Kick…'), f'win.kick-{control_id}', value)

    action = f'win.change-role-{control_id}'

    if is_role_change_allowed(self_contact, contact):
        if contact.role.is_visitor:
            value = f'["{contact.name}", "participant"]'
            menu.add_item(_('Grant Voice'), action, value)
        else:
            value = f'["{contact.name}", "visitor"]'
            menu.add_item(_('Revoke Voice'), action, value)

    if not menu.get_n_items():
        menu.add_item(_('Not Available'), 'dummy', None)

    return menu


def get_groupchat_roster_menu(account: str,
                              control_id: str,
                              self_contact: types.GroupchatParticipant,
                              contact: types.GroupchatParticipant
                              ) -> GajimMenu:

    value = f'"{contact.name}"'

    general_items: MenuItemListT = [
        (_('Details'), f'win.contact-information-{control_id}', value),
        (_('Execute Command…'), f'win.execute-command-{control_id}', value),
    ]

    real_contact = contact.get_real_contact()
    if real_contact is not None and can_add_to_roster(real_contact):
        value = f'["{account}", "{real_contact.jid}"]'
        action = f'app.{account}-add-contact'
        general_items.insert(1, (_('Add to Contact List…'), action, value))

    mod_menu = get_groupchat_mod_menu(control_id, self_contact, contact)
    admin_menu = get_groupchat_admin_menu(control_id, self_contact, contact)

    menu = GajimMenu.from_list(general_items)
    menu.append_section(_('Moderation'), mod_menu)
    menu.append_section(_('Administration'), admin_menu)
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
