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

from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app
from gajim.common.helpers import is_affiliation_change_allowed
from gajim.common.helpers import is_role_change_allowed
from gajim.common.helpers import jid_is_blocked
from gajim.common.i18n import _
from gajim.common.const import URIType
from gajim.common.const import URIAction


def get_singlechat_menu(control_id, account, jid, type_):
    singlechat_menu = [
        (_('Send File'), [
            ('win.send-file-httpupload-', _('Upload File…')),
            ('win.send-file-jingle-', _('Send File Directly…')),
        ]),
        ('win.send-marker-', _('Send Read Markers')),
        (_('Send Chatstate'), ['chatstate']),
        ('win.invite-contacts-', _('Invite Contacts…')),
        ('win.add-to-roster-', _('Add to Contact List…')),
        ('win.block-contact-', _('Block Contact…')),
        ('win.start-call-', _('Start Call…')),
        ('win.information-', _('Information')),
        ('win.search-history', _('Search…')),
    ]

    def build_chatstate_menu():
        menu = Gio.Menu()
        entries = [
            (_('Disabled'), 'disabled'),
            (_('Composing Only'), 'composing_only'),
            (_('All Chat States'), 'all')
        ]

        for entry in entries:
            label, setting = entry
            action = 'win.send-chatstate-%s::%s' % (control_id, setting)
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


def get_groupchat_menu(control_id, account, jid):
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

    def build_menu(preset):
        menu = Gio.Menu()
        for item in preset:
            if isinstance(item[1], str):
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
                    menuitem.set_action_and_target_value(action_name,
                                                         variant_dict)
                    menu.append_item(menuitem)

                elif action_name == 'win.execute-command-':
                    action_name = action_name + control_id
                    menuitem = Gio.MenuItem.new(label, action_name)
                    menuitem.set_action_and_target_value(action_name,
                                                         GLib.Variant('s', ''))
                    menu.append_item(menuitem)
                else:
                    menu.append(label, action_name + control_id)
            else:
                label, sub_menu = item
                submenu = build_menu(sub_menu)
                menu.append_submenu(label, submenu)
        return menu

    return build_menu(groupchat_menu)


def get_account_menu(account):
    '''
    [(action, label/sub_menu)]
        action: string
        label: string
        sub menu: list
    '''
    account_menu = [
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

    def build_menu(preset):
        menu = Gio.Menu()
        for item in preset:
            if isinstance(item[1], str):
                action, label = item
                action = 'app.{}{}'.format(account, action)
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


def build_accounts_menu():
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


def get_encryption_menu(control_id, control_type, zeroconf=False):
    menu = Gio.Menu()
    menu.append(
        _('Disabled'),
        'win.set-encryption-{}::{}'.format(control_id, 'disabled'))
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
        menu_action = 'win.set-encryption-{}::{}'.format(
            control_id, name)
        menu.append(name, menu_action)
    if menu.get_n_items() == 1:
        return None
    return menu


def get_conv_context_menu(account, uri):
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
            action = 'app.%s%s' % (account, action)
        else:
            action = 'app.%s' % action
        menuitem.set_action_name(action)

        data = uri.data
        if uri.type == URIType.XMPP:
            data = uri.data['jid']

        if action in ('app.open-mail', 'app.copy-text'):
            value = GLib.Variant.new_string(data)
        else:
            value = GLib.Variant.new_strv([account, data])
        menuitem.set_action_target_value(value)
        menuitem.show()
        menu.append(menuitem)
    return menu


def get_roster_menu(account, jid, transport=False):
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
    if transport:
        menu_items.insert(1, ('modify-transport', _('Modify Transport…')))

    menu = Gio.Menu()
    for item in menu_items:
        action, label = item
        action = f'win.{action}-{account}'
        menuitem = Gio.MenuItem.new(label, action)
        variant = GLib.Variant('s', str(jid))
        menuitem.set_action_and_target_value(action, variant)
        menu.append_item(menuitem)

    return menu


def get_subscription_menu(account, jid):
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


def get_chat_list_row_menu(workspace_id, account, jid, pinned):
    client = app.get_client(account)
    contact = client.get_module('Contacts').get_contact(jid)

    toggle_label = _('Unpin Chat') if pinned else _('Pin Chat')

    menu_items = [
        ('toggle-chat-pinned', toggle_label),
        (_('Move Chat'), []),
    ]

    is_self_contact = contact.jid.bare == client.get_own_jid().bare
    if (not contact.is_groupchat and not contact.is_in_roster and
            not is_self_contact):
        menu_items.append(('add-to-roster', _('Add to Contact List…')))

    menu = Gio.Menu()
    for item in menu_items:
        if isinstance(item[1], str):
            action, label = item
            action = f'win.{action}'
            menuitem = Gio.MenuItem.new(label, action)
            variant_list = GLib.Variant(
                'as', [workspace_id, account, str(jid)])
            menuitem.set_action_and_target_value(action, variant_list)
            menu.append_item(menuitem)
        else:
            # This is a submenu
            submenu = build_workspaces_submenu(workspace_id, account, str(jid))
            menu.append_submenu(item[0], submenu)

    return menu


def build_workspaces_submenu(current_workspace_id, account, jid):
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


def get_groupchat_roster_menu(account, control_id, self_contact, contact):
    menu = Gtk.Menu()

    item = Gtk.MenuItem(label=_('Information'))
    action = 'win.contact-information-%s::%s' % (control_id, contact.name)
    item.set_detailed_action_name(action)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Add to Contact List…'))
    action = 'app.{account}-add-contact(["{account}", "{jid}"])'.format(
        account=account, jid=contact.real_jid or '')
    if contact.real_jid is None:
        item.set_sensitive(False)
    else:
        item.set_detailed_action_name(action)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Execute Command…'))
    action = 'win.execute-command-%s::%s' % (control_id, contact.name)
    item.set_detailed_action_name(action)
    menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    item = Gtk.MenuItem(label=_('Kick'))
    action = 'win.kick-%s::%s' % (control_id, contact.name)
    if is_role_change_allowed(self_contact, contact):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Ban'))
    action = 'win.ban-%s::%s' % (control_id, contact.real_jid or '')
    if is_affiliation_change_allowed(self_contact, contact, 'outcast'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    item = Gtk.MenuItem(label=_('Make Owner'))
    action = 'win.change-affiliation-%s(["%s", "owner"])' % (control_id,
                                                             contact.real_jid)
    if is_affiliation_change_allowed(self_contact, contact, 'owner'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Make Admin'))
    action = 'win.change-affiliation-%s(["%s", "admin"])' % (control_id,
                                                             contact.real_jid)
    if is_affiliation_change_allowed(self_contact, contact, 'admin'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Make Member'))
    action = 'win.change-affiliation-%s(["%s", "member"])' % (control_id,
                                                              contact.real_jid)
    if is_affiliation_change_allowed(self_contact, contact, 'member'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Revoke Member'))
    action = 'win.change-affiliation-%s(["%s", "none"])' % (control_id,
                                                            contact.real_jid)
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
    action = 'win.change-role-%s(["%s", "%s"])' % (control_id,
                                                   contact.name,
                                                   role)
    if is_role_change_allowed(self_contact, contact):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    menu.show_all()
    return menu


class SearchMenu(Gtk.Menu):
    def __init__(self, treeview):
        Gtk.Menu.__init__(self)
        self._copy_item = Gtk.MenuItem(label=_('Copy'))
        self._copy_item.set_action_name('app.copy-text')
        self.set_copy_text('')
        self._copy_item.show()
        self.append(self._copy_item)
        self.attach_to_widget(treeview, None)

    def set_copy_text(self, text):
        self._copy_item.set_action_target_value(GLib.Variant('s', text))


def escape_mnemonic(label):
    if label is None:
        return
    # Underscore inside a label means the next letter is a keyboard
    # shortcut. To show an underscore we have to use double underscore
    return label.replace('_', '__')
