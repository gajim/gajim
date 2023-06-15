
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

from typing import cast

import textwrap
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import quote

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import types
from gajim.common.const import URIType
from gajim.common.const import XmppUriQuery
from gajim.common.helpers import filesystem_path_from_uri
from gajim.common.helpers import is_affiliation_change_allowed
from gajim.common.helpers import is_retraction_allowed
from gajim.common.helpers import is_role_change_allowed
from gajim.common.helpers import jid_is_blocked
from gajim.common.i18n import _
from gajim.common.i18n import get_short_lang_code
from gajim.common.i18n import p_
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import can_add_to_roster
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.preview import Preview
from gajim.common.structs import URI
from gajim.common.util.text import escape_iri_path_segment

from gajim.gtk.const import MuteState
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.structs import AddChatActionParams
from gajim.gtk.structs import ChatListEntryParam
from gajim.gtk.structs import MuteContactParam
from gajim.gtk.structs import RemoveHistoryActionParams
from gajim.gtk.structs import RetractMessageParam
from gajim.gtk.util import GajimMenu
from gajim.gtk.util import MenuItemListT

UriMenuItemsT = list[tuple[str, list[str], str]]
UriMenuBuilderT = Callable[[URI, str], UriMenuItemsT]


def get_self_contact_menu(contact: types.BareContact) -> GajimMenu:
    account = contact.account
    jid = contact.jid

    menu = GajimMenu()

    menu.add_item(_('Profile'), f'app.{account}-profile', account)
    submenu = get_send_file_submenu()
    menu.append_submenu(_('Send File'), submenu)

    params = RemoveHistoryActionParams(account=account, jid=jid)
    menu.add_item(_('Remove History…'), 'app.remove-history', params)
    return menu


def get_singlechat_menu(contact: types.BareContact) -> GajimMenu:
    account = contact.account

    menu = GajimMenu()
    menu.add_item(_('Block Contact…'),
                  f'app.{account}-block-contact',
                  str(contact.jid))

    submenu = get_send_file_submenu()
    menu.append_submenu(_('Send File'), submenu)

    menu.add_item(_('Start Voice Call…'), 'win.start-voice-call')
    menu.add_item(_('Start Video Call…'), 'win.start-video-call')

    if can_add_to_roster(contact):
        params = AccountJidParam(account=account, jid=contact.jid)
        menu.add_item(_('Add to Contact List…'), 'win.add-to-roster', params)

    return menu


def get_private_chat_menu(contact: types.GroupchatParticipant) -> GajimMenu:
    menu = GajimMenu()

    value = GLib.Variant('as', [''])

    menu.add_item(_('Upload File…'), 'win.send-file-httpupload', value)

    if can_add_to_roster(contact):
        params = AccountJidParam(account=contact.account, jid=contact.jid)
        menu.add_item(_('Add to Contact List…'), 'win.add-to-roster', params)

    return menu


def get_send_file_submenu() -> GajimMenu:
    menu = GajimMenu()

    value = GLib.Variant('as', [''])

    menu.add_item(_('Upload File…'), 'win.send-file-httpupload', value)
    menu.add_item(_('Send File Directly…'), 'win.send-file-jingle', value)
    return menu


def get_groupchat_menu(contact: GroupchatContact) -> GajimMenu:
    menuitems: MenuItemListT = [
        (_('Change Nickname…'), 'win.muc-change-nickname', None),
        (_('Request Voice'), 'win.muc-request-voice', None),
        (_('Execute Command…'), 'win.muc-execute-command', ''),
    ]

    return GajimMenu.from_list(menuitems)


def get_account_menu(account: str) -> GajimMenu:

    client = app.get_client(account)
    server_jid = client.get_own_jid().domain

    menuitems: MenuItemListT = [
        (_('Profile'), f'app.{account}-profile', account),
        (_('Discover Services…'), f'app.{account}-services', account),
        (_('Execute Command…'), f'app.{account}-execute-command', server_jid),
        (_('Server Info'), f'app.{account}-server-info', account),
    ]

    menu = GajimMenu.from_list(menuitems)

    advanced_menuitems: MenuItemListT = [
        (_('Archiving Preferences'), f'app.{account}-archive', account),
        (_('Blocking List'), f'app.{account}-blocking', account),
        (_('PEP Configuration'), f'app.{account}-pep-config', account),
        (_('Synchronise History…'), f'app.{account}-sync-history', account),
    ]

    if app.settings.get('developer_modus'):
        advanced_menuitems.append(
            (_('Bookmarks'), f'app.{account}-bookmarks', account))

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
        menubar.insert_submenu(menu_position, _('_Accounts'), acc_menu)


def get_encryption_menu() -> GajimMenu:

    menuitems: MenuItemListT = [
        (_('Disabled'), 'win.set-encryption', ''),
        ('OMEMO', 'win.set-encryption', 'OMEMO'),
        ('OpenPGP', 'win.set-encryption', 'OpenPGP'),
        ('PGP', 'win.set-encryption', 'PGP'),
    ]

    return GajimMenu.from_list(menuitems)


def get_conv_action_context_menu(account: str,
                                 selected_text: str
                                 ) -> Gtk.MenuItem:
    selected_text_short = textwrap.shorten(selected_text,
                                           width=10,
                                           placeholder='…')

    action_menu_item = Gtk.MenuItem.new_with_mnemonic(
        _('_Actions for "%s"') % escape_mnemonic(selected_text_short))
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
    value = GLib.Variant.new_strv([account, f'https://{uri_text}'])
    item.set_action_target_value(value)
    submenu.append(item)

    for item in cast(list[Gtk.MenuItem], submenu):
        item.set_action_name('app.open-link')

    return action_menu_item


def _xmpp_message_query_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    jid = uri.data['jid']
    # qparams = uri.query_params
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('copy-text', [jid], _('Copy XMPP Address')),
        ('open-chat', [account, jid], _('Start Chat…')),
        # ^ TODO: pass qparams ^
        (f'{account}-add-contact', [account, jid], _('Add to Contact List…')),
    ]


def _xmpp_join_query_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('copy-text', [uri.data['jid']], _('Copy XMPP Address')),
        ('open-chat', [account, uri.data['jid']],
            # ^ TODO: pass qparams ^
            _('Join Groupchat…')),
    ]


_xmpp_uri_context_menus: dict[XmppUriQuery, UriMenuBuilderT] = {
    XmppUriQuery.NONE: _xmpp_message_query_context_menu,
    XmppUriQuery.MESSAGE: _xmpp_message_query_context_menu,
    XmppUriQuery.JOIN: _xmpp_join_query_context_menu,
}


def _xmpp_uri_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return _xmpp_uri_context_menus[XmppUriQuery.from_str_or_none(uri.query_type)
                                   ](uri, account)


def _web_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('open-link', ['', uri.source], _('Open Link in Browser')),
    ]


def _mailto_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('copy-text', [uri.data['addr']], _('Copy Email Address')),
        ('open-link', ['', uri.source], _('Open Email Composer')),
    ]


def _geo_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('open-link', ['', uri.source], _('Show Location')),
    ]


def _ambiguous_addr_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    addr = uri.data['addr']
    mailto = 'mailto:' + escape_iri_path_segment(addr)
    return [
        ('copy-text', [addr], _('Copy XMPP Address/Email')),
        ('open-link', ['', mailto], _('Open Email Composer')),
        ('open-chat', [account, addr], _('Start Chat…')),
        (f'{account}-add-contact', [account, addr], _('Add to Contact List…')),
    ]


def _file_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    canopen = app.settings.get('allow_open_file_uris')
    pathobj = filesystem_path_from_uri(uri.source)
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('open-link' if canopen else '-', ['', uri.source], _('Open Path')),
        ('copy-text' if pathobj else '-', [str(pathobj)], _('Copy Path')),
    ]


def _tel_uri_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('open-link', [account, uri.source], _('Dial Number')),
        # TODO:
        # ('copy-text', [uri.data['number']], _('Copy Number')),
    ]


def _other_uri_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return [
        ('copy-text', [uri.source], _('Copy Link Location')),
        ('open-link', [account, uri.source], _('Open Link')),
    ]


_uri_context_menus: dict[URIType, UriMenuBuilderT] = {
    URIType.XMPP: _xmpp_uri_context_menu,
    URIType.MAIL: _mailto_uri_context_menu,
    URIType.GEO: _geo_uri_context_menu,
    URIType.WEB: _web_uri_context_menu,
    URIType.FILE: _file_uri_context_menu,
    URIType.AT: _ambiguous_addr_context_menu,
    URIType.TEL: _tel_uri_context_menu,
    URIType.OTHER: _other_uri_context_menu,
}


def populate_uri_context_menu(menu: Gtk.Menu, account: str, uri: URI) -> None:
    assert uri.type != URIType.INVALID  # it really begs to be a separate class
    for action, args, label in _uri_context_menus[uri.type](uri, account):
        menuitem = Gtk.MenuItem()
        menuitem.set_label(label)
        menuitem.set_action_name(f'app.{action}')
        if len(args) == 1:
            value = GLib.Variant.new_string(args[0])
        else:
            value = GLib.Variant.new_strv(args)
        menuitem.set_action_target_value(value)
        menuitem.show()
        menu.append(menuitem)


def get_roster_menu(account: str, jid: str, gateway: bool = False) -> GajimMenu:

    block_label = _('Block…')
    if jid_is_blocked(account, jid):
        block_label = _('Unblock')

    value = str(jid)

    menuitems: MenuItemListT = [
        (_('Details'), f'app.{account}-contact-info', value),
        (_('Execute Command…'), f'app.{account}-execute-command', value),
        (block_label, f'app.{account}-block-contact', value),
        (_('Remove…'), f'app.{account}-remove-contact', value),
    ]

    if gateway:
        menuitems.insert(
            1, (_('Modify Gateway…'), f'app.{account}-modify-gateway', value))

    return GajimMenu.from_list(menuitems)


def get_roster_view_menu() -> GajimMenu:
    menuitems: MenuItemListT = [
        (_('Show Offline Contacts'), 'win.show-offline', None),
        (_('Sort by Status'), 'win.sort-by-show', None),
        (_('Add Contact…'), 'app.add-contact', ''),
    ]

    return GajimMenu.from_list(menuitems)


def get_account_notifications_menu(account: str) -> GajimMenu:
    menuitems: MenuItemListT = [
        (_('Deny all subscription requests'),
         f'win.subscription-deny-all-{account}',
         None),
    ]
    return GajimMenu.from_list(menuitems)


def get_subscription_menu(account: str, jid: JID) -> GajimMenu:
    params = AddChatActionParams(account=account,
                                 jid=jid,
                                 type='contact',
                                 select=True)
    value = str(jid)
    menuitems: MenuItemListT = [
        (_('Start Chat'), 'win.add-chat', params),
        (_('Details'), f'win.contact-info-{account}', value),
        (_('Block'), f'win.subscription-block-{account}', value),
        (_('Report'), f'win.subscription-report-{account}', value),
        (_('Deny'), f'win.subscription-deny-{account}', value),
    ]

    return GajimMenu.from_list(menuitems)


def get_start_chat_button_menu() -> GajimMenu:

    value = GLib.Variant('as', ['', ''])

    menuitems: MenuItemListT = [
        (_('Start Chat…'), 'app.start-chat', value),
        (_('Create Group Chat…'), 'app.create-groupchat', ''),
        (_('Add Contact…'), 'app.add-contact', ''),
    ]

    return GajimMenu.from_list(menuitems)


def get_start_chat_row_menu(account: str, jid: JID) -> GajimMenu:
    params = AccountJidParam(account=account, jid=jid)
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
    assert isinstance(
        contact, BareContact | GroupchatContact | GroupchatParticipant)

    menu = GajimMenu()

    params = ChatListEntryParam(workspace_id=workspace_id,
                                source_workspace_id=workspace_id,
                                account=account,
                                jid=jid)

    toggle_label = _('Unpin Chat') if pinned else _('Pin Chat')
    menu.add_item(toggle_label, 'win.toggle-chat-pinned', params)

    submenu = menu.add_submenu(_('Move Chat'))
    if app.settings.get_workspace_count() > 1:
        for name, params in get_workspace_params(workspace_id, account, jid):
            submenu.add_item(name, 'win.move-chat-to-workspace', params)

    params = ChatListEntryParam(workspace_id='',
                                source_workspace_id=workspace_id,
                                account=account,
                                jid=jid)

    submenu.add_item(
        _('New Workspace'), 'win.move-chat-to-workspace', params)

    if can_add_to_roster(contact):
        params = AccountJidParam(account=account, jid=jid)
        menu.add_item(_('Add to Contact List…'), 'win.add-to-roster', params)

    if app.window.get_chat_unread_count(account, jid, include_silent=True):
        params = AccountJidParam(account=account, jid=jid)
        menu.add_item(_('Mark as read'), 'win.mark-as-read', params)

    if contact.is_muted:
        menu.add_item(
            _('Unmute Chat'),
            'app.mute-chat',
            MuteContactParam(account=account,
                             jid=jid,
                             state=MuteState.UNMUTE))
    else:
        submenu = menu.add_submenu(_('Mute Chat'))
        for state, label in MuteState.iter():
            submenu.add_item(
                label,
                'app.mute-chat',
                MuteContactParam(account=account, jid=jid, state=state))

    return menu


def get_workspace_params(current_workspace_id: str,
                         account: str,
                         jid: JID
                         ) -> Iterator[tuple[str, ChatListEntryParam]]:

    for workspace_id in app.settings.get_workspaces():
        if workspace_id == current_workspace_id:
            continue
        name = app.settings.get_workspace_setting(workspace_id, 'name')
        params = ChatListEntryParam(workspace_id=workspace_id,
                                    source_workspace_id=current_workspace_id,
                                    account=account,
                                    jid=jid)
        yield name, params


def get_groupchat_admin_menu(self_contact: types.GroupchatParticipant,
                             contact: types.GroupchatParticipant) -> GajimMenu:

    menu = GajimMenu()

    if contact.real_jid is None:
        menu.add_item(_('Not Available'), 'dummy', None)
        return menu

    action = 'win.muc-change-affiliation'
    real_jid = str(contact.real_jid)

    if is_affiliation_change_allowed(self_contact, contact, 'owner'):
        value = GLib.Variant('as', [real_jid, 'owner'])
        menu.add_item(_('Make Owner'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'admin'):
        value = GLib.Variant('as', [real_jid, 'admin'])
        menu.add_item(_('Make Admin'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'member'):
        value = GLib.Variant('as', [real_jid, 'member'])
        menu.add_item(_('Make Member'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'none'):
        value = GLib.Variant('as', [real_jid, 'none'])
        menu.add_item(_('Revoke Member'), action, value)

    if is_affiliation_change_allowed(self_contact, contact, 'outcast'):
        menu.add_item(_('Ban…'), 'win.muc-ban', real_jid)

    if not menu.get_n_items():
        menu.add_item(_('Not Available'), 'dummy', None)

    return menu


def get_groupchat_mod_menu(self_contact: types.GroupchatParticipant,
                           contact: types.GroupchatParticipant
                           ) -> GajimMenu:

    menu = GajimMenu()

    if not contact.is_available:
        menu.add_item(_('Not Available'), 'dummy', None)
        return menu

    contact_name = str(contact.name)

    if is_role_change_allowed(self_contact, contact):
        menu.add_item(_('Kick…'), 'win.muc-kick', contact_name)

    action = 'win.muc-change-role'

    if is_role_change_allowed(self_contact, contact):
        if contact.role.is_visitor:
            value = GLib.Variant('as', [contact_name, 'participant'])
            menu.add_item(_('Grant Voice'), action, value)
        else:
            value = GLib.Variant('as', [contact_name, 'visitor'])
            menu.add_item(_('Revoke Voice'), action, value)

    if not menu.get_n_items():
        menu.add_item(_('Not Available'), 'dummy', None)

    return menu


def get_groupchat_participant_menu(account: str,
                                   self_contact: types.GroupchatParticipant,
                                   contact: types.GroupchatParticipant
                                   ) -> GajimMenu:

    value = str(contact.name)

    general_items: MenuItemListT = [
        (_('Details'), 'win.muc-contact-info', value),
        (_('Execute Command…'), 'win.muc-execute-command', value),
    ]

    real_contact = contact.get_real_contact()
    if real_contact is not None and can_add_to_roster(real_contact):
        value = GLib.Variant('as', [account, str(real_contact.jid)])
        action = f'app.{account}-add-contact'
        general_items.insert(1, (_('Add to Contact List…'), action, value))

    mod_menu = get_groupchat_mod_menu(self_contact, contact)
    admin_menu = get_groupchat_admin_menu(self_contact, contact)

    menu = GajimMenu.from_list(general_items)
    menu.append_section(_('Moderation'), mod_menu)
    menu.append_section(_('Administration'), admin_menu)
    return menu


def get_component_search_menu(jid: str | None, copy_text: str) -> GajimMenu:
    menuitems: MenuItemListT = [
        (_('Copy'), 'app.copy-text', copy_text),
    ]

    if jid is not None:
        menuitems.append(
            (_('Start Chat…'), 'app.start-chat', jid)
        )

    return GajimMenu.from_list(menuitems)


def get_chat_row_menu(contact: types.ChatContactT,
                      name: str,
                      text: str,
                      timestamp: datetime,
                      message_id: str | None,
                      stanza_id: str | None,
                      log_line_id: int | None
                      ) -> GajimMenu:

    menu_items: MenuItemListT = []

    format_string = app.settings.get('date_time_format')
    timestamp_formatted = timestamp.strftime(format_string)

    copy_text = f'{timestamp_formatted} - {name}: '
    if text.startswith(('```', '> ')):
        # Prepend a line break in order to keep code block/quotes rendering
        copy_text += '\n'
    copy_text += text

    menu_items.append(
        (p_('Message row action', 'Copy'),
         'win.copy-message',
         copy_text))

    menu_items.append(
        (p_('Message row action', 'Select Messages…'),
         'win.activate-message-selection',
         GLib.Variant('u', log_line_id or 0)))

    show_quote = True
    if isinstance(contact, GroupchatContact):
        if contact.is_joined:
            self_contact = contact.get_self()
            assert self_contact is not None
            show_quote = not self_contact.role.is_visitor
        else:
            show_quote = False
    if show_quote:
        menu_items.append((
            p_('Message row action', 'Quote…'), 'win.quote', text))

    show_correction = False
    if message_id is not None:
        show_correction = app.window.is_message_correctable(
            contact, message_id)
    if show_correction:
        menu_items.append((
            p_('Message row action', 'Correct…'), 'win.correct-message', None))

    show_retract = False
    if isinstance(contact, GroupchatContact) and contact.is_joined:
        resource_contact = contact.get_resource(name)
        self_contact = contact.get_self()
        assert self_contact is not None
        is_allowed = is_retraction_allowed(self_contact, resource_contact)

        disco_info = app.storage.cache.get_last_disco_info(contact.jid)
        assert disco_info is not None

        if disco_info.has_message_moderation and is_allowed:
            show_retract = True
    if show_retract and stanza_id is not None:
        param = RetractMessageParam(
            account=contact.account,
            jid=contact.jid,
            stanza_id=stanza_id)
        menu_items.append((
            p_('Message row action', 'Retract…'),
            'win.retract-message',
            param))

    if log_line_id is not None:
        menu_items.append(
            (p_('Message row action', 'Delete Message Locally…'),
            'win.delete-message-locally',
            GLib.Variant('u', log_line_id or 0)))

    return GajimMenu.from_list(menu_items)


def get_preview_menu(preview: Preview) -> GajimMenu:
    menu_items: MenuItemListT = []

    download = (_('_Download'), 'win.preview-download', preview.id)
    open_file = (_('_Open'), 'win.preview-open', preview.id)
    save_as = (_('_Save as…'), 'win.preview-save-as', preview.id)
    open_folder = (_('Open _Folder'), 'win.preview-open-folder', preview.id)
    copy_link = (_('_Copy Link'), 'win.preview-copy-link', preview.id)
    open_link = (_('Open Link in _Browser'), 'win.preview-open-link',
                 preview.id)

    if preview.is_geo_uri:
        menu_items.append(open_file)
        menu_items.append(copy_link)
        return GajimMenu.from_list(menu_items)

    if preview.orig_exists:
        menu_items.append(open_file)
        menu_items.append(save_as)
        menu_items.append(open_folder)
    else:
        if not preview.download_in_progress:
            menu_items.append(download)

    menu_items.append(copy_link)

    if not preview.is_aes_encrypted:
        menu_items.append(open_link)

    return GajimMenu.from_list(menu_items)


def get_format_menu() -> GajimMenu:

    menuitems: MenuItemListT = [
        (_('bold'), 'win.input-bold', None),
        (_('italic'), 'win.input-italic', None),
        (_('strike'), 'win.input-strike', None),
    ]

    return GajimMenu.from_list(menuitems)


def get_workspace_menu(workspace_id: str) -> GajimMenu:
    remove_action = 'win.dummy'
    if app.settings.get_workspace_count() > 1:
        remove_action = 'win.remove-workspace'

    menuitems: MenuItemListT = [
        (_('Mark as read'), 'win.mark-workspace-as-read', workspace_id),
        (_('Edit…'), 'win.edit-workspace', workspace_id),
        (_('Remove'), remove_action, workspace_id),
    ]

    return GajimMenu.from_list(menuitems)


def escape_mnemonic(label: str | None) -> str | None:
    if label is None:
        return None
    # Underscore inside a label means the next letter is a keyboard
    # shortcut. To show an underscore we have to use double underscore
    return label.replace('_', '__')
