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

from typing import Iterator
from typing import cast
from typing import Optional
from typing import Union

from datetime import datetime
import textwrap
from urllib.parse import quote

from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib

from nbxmpp import JID

from gajim.common import app
from gajim.common import types
from gajim.common.helpers import from_one_line
from gajim.common.helpers import is_affiliation_change_allowed
from gajim.common.helpers import is_retraction_allowed
from gajim.common.helpers import is_role_change_allowed
from gajim.common.helpers import jid_is_blocked
from gajim.common.i18n import _
from gajim.common.i18n import Q_
from gajim.common.i18n import get_short_lang_code
from gajim.common.const import URIType
from gajim.common.const import XmppUriQuery
from gajim.common.preview import Preview
from gajim.common.structs import URI
from gajim.common.structs import VariantMixin
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import can_add_to_roster

from gajim.gui.structs import AddChatActionParams
from gajim.gui.structs import AccountJidParam
from gajim.gui.structs import ChatListEntryParam
from gajim.gui.structs import RemoveHistoryActionParams
from gajim.gui.structs import RetractMessageParam
from gajim.gui.util import GajimMenu


MenuValueT = Union[None, str, GLib.Variant, VariantMixin]
MenuItemListT = list[tuple[str, str, MenuValueT]]


def get_self_contact_menu(contact: types.BareContact) -> GajimMenu:
    account = contact.account
    jid = contact.jid

    menu = GajimMenu()

    menu.add_item(_('Profile'), f'app.{account}-profile', f'"{account}"')
    submenu = get_send_file_submenu()
    menu.append_submenu(_('Send File'), submenu)

    params = RemoveHistoryActionParams(account=account, jid=jid)
    menu.add_item(_('Remove History…'), 'app.remove-history', params)
    menu.add_item(_('Search…'), 'win.search-history', None)
    return menu


def get_singlechat_menu(contact: types.BareContact) -> GajimMenu:
    account = contact.account

    value = f'"{contact.jid}"'

    menu = GajimMenu()
    menu.add_item(_('Details'), 'win.show-contact-info')
    menu.add_item(_('Block Contact…'), f'app.{account}-block-contact', value)

    submenu = get_send_file_submenu()
    menu.append_submenu(_('Send File'), submenu)

    menu.add_item(_('Start Voice Call…'), 'win.start-voice-call')
    menu.add_item(_('Start Video Call…'), 'win.start-video-call')

    menu.add_item(_('Search…'), 'win.search-history', None)

    if can_add_to_roster(contact):
        params = AccountJidParam(account=account, jid=contact.jid)
        menu.add_item(_('Add to Contact List…'), 'win.add-to-roster', params)

    return menu


def get_private_chat_menu(contact: types.GroupchatParticipant) -> GajimMenu:
    menu = GajimMenu()
    menu.add_item(_('Details'), 'win.show-contact-info')
    menu.add_item(_('Upload File…'), 'win.send-file-httpupload([""])')
    menu.add_item(_('Search…'), 'win.search-history')

    if can_add_to_roster(contact):
        params = AccountJidParam(account=contact.account, jid=contact.jid)
        menu.add_item(_('Add to Contact List…'), 'win.add-to-roster', params)

    return menu


def get_send_file_submenu() -> GajimMenu:
    menu = GajimMenu()

    menu.add_item(_('Upload File…'), 'win.send-file-httpupload([""])')
    menu.add_item(_('Send File Directly…'), 'win.send-file-jingle([""])')
    return menu


def get_groupchat_menu(contact: GroupchatContact) -> GajimMenu:
    menuitems: MenuItemListT = [
        (_('Details'), 'win.show-contact-info', None),
        (_('Change Nickname…'), 'win.muc-change-nickname', None),
        (_('Request Voice'), 'win.muc-request-voice', None),
        (_('Execute Command…'), 'win.muc-execute-command', '""'),
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


def get_encryption_menu() -> GajimMenu:

    menuitems: MenuItemListT = [
        (_('Disabled'), 'win.set-encryption', '""'),
        ('OMEMO', 'win.set-encryption', '"OMEMO"'),
        ('OpenPGP', 'win.set-encryption', '"OpenPGP"'),
        ('PGP', 'win.set-encryption', '"PGP"'),
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


def get_conv_uri_context_menu(account: str, uri: URI) -> Optional[Gtk.Menu]:
    if uri.type == URIType.XMPP:
        if XmppUriQuery.from_str(uri.query_type) == XmppUriQuery.JOIN:
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
    ]

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


def get_start_chat_button_menu() -> GajimMenu:
    menuitems: MenuItemListT = [
        (_('Start Chat…'), 'app.start-chat(["", ""])', None),
        (_('Create Group Chat…'), 'app.create-groupchat::', None),
        (_('Add Contact…'), 'app.add-contact::', None),
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
        menu.add_item(_('Ban…'), 'win.muc-ban', value)

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

    if is_role_change_allowed(self_contact, contact):
        value = f'"{contact.name}"'
        menu.add_item(_('Kick…'), 'win.muc-kick', value)

    action = 'win.muc-change-role'

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


def get_groupchat_participant_menu(account: str,
                                   self_contact: types.GroupchatParticipant,
                                   contact: types.GroupchatParticipant
                                   ) -> GajimMenu:

    value = f'"{contact.name}"'

    general_items: MenuItemListT = [
        (_('Details'), 'win.muc-contact-info', value),
        (_('Execute Command…'), 'win.muc-execute-command', value),
    ]

    real_contact = contact.get_real_contact()
    if real_contact is not None and can_add_to_roster(real_contact):
        value = f'["{account}", "{real_contact.jid}"]'
        action = f'app.{account}-add-contact'
        general_items.insert(1, (_('Add to Contact List…'), action, value))

    mod_menu = get_groupchat_mod_menu(self_contact, contact)
    admin_menu = get_groupchat_admin_menu(self_contact, contact)

    menu = GajimMenu.from_list(general_items)
    menu.append_section(_('Moderation'), mod_menu)
    menu.append_section(_('Administration'), admin_menu)
    return menu


def get_component_search_menu(jid: Optional[str], copy_text: str) -> Gio.Menu:
    menu_items: list[tuple[str, str]] = [
        ('app.copy-text', _('Copy')),
    ]
    if jid is not None:
        menu_items.append(
            ('app.start-chat', _('Start Chat…')))

    menu = Gio.Menu()
    for item in menu_items:
        action, label = item
        menuitem = Gio.MenuItem.new(label, action)
        if action == 'app.copy-text':
            data = copy_text
        else:
            data = jid
        variant = GLib.Variant('s', data)
        menuitem.set_action_and_target_value(action, variant)
        menu.append_item(menuitem)
    return menu


def get_chat_row_menu(contact: types.ChatContactT,
                      name: str,
                      text: str,
                      timestamp: datetime,
                      message_id: Optional[str],
                      stanza_id: Optional[str],
                      log_line_id: Optional[int]
                      ) -> GajimMenu:

    menu_items: MenuItemListT = []

    text = text.replace('"', '\\"')

    time_format = from_one_line(app.settings.get('time_format'))
    timestamp_formatted = timestamp.strftime(time_format)
    copy_text = f'{timestamp_formatted} - {name}: {text}'
    menu_items.append(
        (Q_('?Message row action:Copy'), 'win.copy-message', f'"{copy_text}"'))

    menu_items.append(
        (Q_('?Message row action:Select Messages…'),
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
            Q_('?Message row action:Quote…'),
            'win.quote',
            f'"{text}"'))

    show_correction = False
    if message_id is not None:
        show_correction = app.window.is_message_correctable(
            contact, message_id)
    if show_correction:
        menu_items.append((
            Q_('?Message row action:Correct…'), 'win.correct-message', None))

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
    if show_retract:
        assert stanza_id is not None
        param = RetractMessageParam(
            account=contact.account,
            jid=contact.jid,
            stanza_id=stanza_id)
        menu_items.append((
            Q_('?Message row action:Retract…'), 'win.retract-message', param))

    menu = GajimMenu.from_list(menu_items)
    return menu


def get_preview_menu(preview: Preview) -> GajimMenu:
    menu_items: MenuItemListT = []

    variant = GLib.Variant('s', preview.id)

    download = (_('_Download'), 'win.preview-download', variant)
    open_file = (_('_Open'), 'win.preview-open', variant)
    save_as = (_('_Save as…'), 'win.preview-save-as', variant)
    open_folder = (_('Open _Folder'), 'win.preview-open-folder', variant)
    copy_link = (_('_Copy Link'), 'win.preview-copy-link', variant)
    open_link = (_('Open Link in _Browser'), 'win.preview-open-link', variant)

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


def get_workspace_menu(workspace_id: str, has_unread: bool) -> GajimMenu:
    remove_action = 'win.dummy'
    if app.settings.get_workspace_count() > 1:
        remove_action = 'win.remove-workspace'

    menuitems: MenuItemListT = [
        (_('Edit…'), 'win.edit-workspace', f'"{workspace_id}"'),
        (_('Remove'), remove_action, f'"{workspace_id}"'),
    ]

    if has_unread:
        menuitems.insert(
            0,
            (_('Mark as read'),
             'win.mark-workspace-as-read',
             f'"{workspace_id}"'))

    return GajimMenu.from_list(menuitems)


def escape_mnemonic(label: Optional[str]) -> Optional[str]:
    if label is None:
        return None
    # Underscore inside a label means the next letter is a keyboard
    # shortcut. To show an underscore we have to use double underscore
    return label.replace('_', '__')
