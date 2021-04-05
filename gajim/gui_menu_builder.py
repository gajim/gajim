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

from gi.repository import Gtk, Gio, GLib
from nbxmpp.namespaces import Namespace

from gajim import gtkgui_helpers
from gajim.common import app
from gajim.common import helpers
from gajim.common.helpers import is_affiliation_change_allowed
from gajim.common.helpers import is_role_change_allowed
from gajim.common.i18n import _
from gajim.common.const import URIType
from gajim.common.const import URIAction

from gajim.gui.util import get_builder
from gajim.gui.const import ControlType


def build_resources_submenu(contacts, account, action, room_jid=None,
                room_account=None, cap=None):
    """
    Build a submenu with contact's resources. room_jid and room_account are for
    action self.on_invite_to_room
    """
    roster = app.interface.roster
    sub_menu = Gtk.Menu()

    for c in contacts:
        item = Gtk.MenuItem.new_with_label(
            '%s (%s)' % (c.resource, str(c.priority)))
        sub_menu.append(item)
        if action == roster.on_invite_to_room:  # pylint: disable=comparison-with-callable
            item.connect('activate', action, [(c, account)], room_jid,
                    room_account, c.resource)
        else: # start_chat, execute_command, send_file
            item.connect('activate', action, c, account, c.resource)

        if cap and not c.supports(cap):
            item.set_sensitive(False)

    return sub_menu

def build_invite_submenu(invite_menuitem, list_, ignore_rooms=None,
show_bookmarked=False, force_resource=False):
    """
    list_ in a list of (contact, account)
    force_resource means we want to send invitation even if there is only one
        resource
    """
    if ignore_rooms is None:
        ignore_rooms = []
    roster = app.interface.roster
    # used if we invite only one contact with several resources
    contact_list = []
    if len(list_) == 1:
        contact, account = list_[0]
        contact_list = app.contacts.get_contacts(account, contact.jid)
    contacts_transport = -1
    connected_accounts = []
    # -1 is at start, False when not from the same, None when jabber
    for (contact, account) in list_:
        if not account in connected_accounts:
            connected_accounts.append(account)
        transport = app.get_transport_name_from_jid(contact.jid)
        if transport == 'jabber':
            transport = None
        if contacts_transport == -1:
            contacts_transport = transport
        elif contacts_transport != transport:
            contacts_transport = False

    if contacts_transport is False:
        # they are not all from the same transport
        invite_menuitem.set_sensitive(False)
        return
    invite_to_submenu = Gtk.Menu()
    invite_menuitem.set_submenu(invite_to_submenu)
    rooms = [] # a list of (room_jid, account) tuple
    minimized_controls = []
    for account in connected_accounts:
        minimized_controls += \
            list(app.interface.minimized_controls[account].values())
    for gc_control in app.interface.msg_win_mgr.get_controls(
            ControlType.GROUPCHAT) + minimized_controls:
        acct = gc_control.account
        if acct not in connected_accounts:
            continue
        room_jid = gc_control.room_jid
        room_name = gc_control.room_name
        if room_jid in ignore_rooms:
            continue
        if room_jid in app.gc_connected[acct] and \
        app.gc_connected[acct][room_jid] and \
        contacts_transport in ['jabber', None]:
            rooms.append((room_jid, room_name, acct))
    if rooms:
        item = Gtk.SeparatorMenuItem.new() # separator
        invite_to_submenu.append(item)
        for (room_jid, room_name, account) in rooms:
            menuitem = Gtk.MenuItem.new_with_label(room_name)
            if len(contact_list) > 1: # several resources
                menuitem.set_submenu(build_resources_submenu(
                    contact_list, account, roster.on_invite_to_room, room_jid,
                    account))
            else:
                # use resource if it's self contact
                if contact.jid == app.get_jid_from_account(account):
                    resource = contact.resource
                else:
                    resource = None
                menuitem.connect('activate', roster.on_invite_to_room, list_,
                    room_jid, account, resource)
            invite_to_submenu.append(menuitem)

    if not show_bookmarked:
        return
    rooms2 = [] # a list of (room_jid, account) tuple
    r_jids = [] # list of room jids
    for account in connected_accounts:
        con = app.connections[account]
        for bookmark in con.get_module('Bookmarks').bookmarks:
            if bookmark.jid in r_jids:
                continue
            if bookmark.jid not in app.gc_connected[account] or not \
            app.gc_connected[account][bookmark.jid]:
                rooms2.append((bookmark.jid, account))
                r_jids.append(bookmark.jid)

    if not rooms2:
        return
    item = Gtk.SeparatorMenuItem.new() # separator
    invite_to_submenu.append(item)
    for (room_jid, account) in rooms2:
        menuitem = Gtk.MenuItem.new_with_label(room_jid.localpart)
        if len(contact_list) > 1: # several resources
            menuitem.set_submenu(build_resources_submenu(
                contact_list, account, roster.on_invite_to_room, str(room_jid),
                account))
        else:
            # use resource if it's self contact
            if contact.jid == app.get_jid_from_account(account):
                resource = contact.resource
            else:
                resource = None
            menuitem.connect('activate', roster.on_invite_to_room, list_,
                str(room_jid), account, resource)
        invite_to_submenu.append(menuitem)

def get_contact_menu(contact, account, use_multiple_contacts=True,
show_start_chat=True, show_encryption=False, show_buttonbar_items=True,
control=None, gc_contact=None, is_anonymous=True):
    """
    Build contact popup menu for roster and chat window. If control is not set,
    we hide invite_contacts_menuitem
    """
    if not contact:
        return

    jid = contact.jid
    our_jid = jid == app.get_jid_from_account(account)
    roster = app.interface.roster

    xml = get_builder('contact_context_menu.ui')
    contact_context_menu = xml.get_object('contact_context_menu')

    start_chat_menuitem = xml.get_object('start_chat_menuitem')
    execute_command_menuitem = xml.get_object('execute_command_menuitem')
    rename_menuitem = xml.get_object('rename_menuitem')
    edit_groups_menuitem = xml.get_object('edit_groups_menuitem')
    send_file_menuitem = xml.get_object('send_file_menuitem')
    information_menuitem = xml.get_object('information_menuitem')
    history_menuitem = xml.get_object('history_menuitem')
    send_single_message_menuitem = xml.get_object('send_single_message_menuitem')
    invite_menuitem = xml.get_object('invite_menuitem')
    block_menuitem = xml.get_object('block_menuitem')
    unblock_menuitem = xml.get_object('unblock_menuitem')
    ignore_menuitem = xml.get_object('ignore_menuitem')
    unignore_menuitem = xml.get_object('unignore_menuitem')
    # Subscription submenu
    subscription_menuitem = xml.get_object('subscription_menuitem')
    send_auth_menuitem, ask_auth_menuitem, revoke_auth_menuitem = \
            subscription_menuitem.get_submenu().get_children()
    add_to_roster_menuitem = xml.get_object('add_to_roster_menuitem')
    remove_from_roster_menuitem = xml.get_object(
            'remove_from_roster_menuitem')
    manage_contact_menuitem = xml.get_object('manage_contact')
    convert_to_gc_menuitem = xml.get_object('convert_to_groupchat_menuitem')
    last_separator = xml.get_object('last_separator')

    items_to_hide = []

    contacts = app.contacts.get_contacts(account, jid)
    if len(contacts) > 1 and use_multiple_contacts: # several resources
        send_file_menuitem.set_submenu(build_resources_submenu(
            contacts,
            account,
            roster.on_send_file_menuitem_activate,
            cap=Namespace.JINGLE_FILE_TRANSFER_5))
        execute_command_menuitem.set_submenu(build_resources_submenu(
                contacts, account, roster.on_execute_command, cap=Namespace.COMMANDS))
    else:
        if contact.supports(Namespace.JINGLE_FILE_TRANSFER_5):
            send_file_menuitem.set_sensitive(True)
            send_file_menuitem.connect('activate',
                    roster.on_send_file_menuitem_activate, contact, account)
        else:
            send_file_menuitem.set_sensitive(False)

        if contact.supports(Namespace.COMMANDS):
            execute_command_menuitem.set_sensitive(True)
            if gc_contact and gc_contact.jid and not is_anonymous:
                execute_command_menuitem.connect('activate',
                    roster.on_execute_command, gc_contact, account,
                    gc_contact.resource)
            else:
                execute_command_menuitem.connect('activate',
                    roster.on_execute_command, contact, account,
                    contact.resource)
        else:
            execute_command_menuitem.set_sensitive(False)

    start_chat_menuitem.connect(
        'activate', app.interface.on_open_chat_window, contact, account)

    rename_menuitem.connect('activate', roster.on_rename, 'contact', jid,
        account)

    history_menuitem.set_action_name('app.browse-history')
    dict_ = {'jid': GLib.Variant('s', contact.jid),
             'account': GLib.Variant('s', account)}
    variant = GLib.Variant('a{sv}', dict_)
    history_menuitem.set_action_target_value(variant)

    if control:
        convert_to_gc_menuitem.connect('activate',
            control._on_convert_to_gc_menuitem_activate)
    else:
        items_to_hide.append(convert_to_gc_menuitem)

    if _('Not in contact list') not in contact.get_shown_groups():
        # contact is in normal group
        edit_groups_menuitem.connect('activate', roster.on_edit_groups, [(contact,
                account)])
    else:
        # contact is in group 'Not in contact list'
        edit_groups_menuitem.set_sensitive(False)

    # Hide items when it's self contact row
    if our_jid:
        items_to_hide += [rename_menuitem, edit_groups_menuitem]

    # Unsensitive many items when account is offline
    if app.account_is_disconnected(account):
        for widget in (start_chat_menuitem, rename_menuitem,
        edit_groups_menuitem, send_file_menuitem, convert_to_gc_menuitem,
        information_menuitem):
            widget.set_sensitive(False)

    if not show_start_chat:
        items_to_hide.append(start_chat_menuitem)

    if not show_buttonbar_items:
        items_to_hide += [history_menuitem, send_file_menuitem,
                information_menuitem, convert_to_gc_menuitem, last_separator]

    if not control:
        items_to_hide.append(convert_to_gc_menuitem)

    # Hide items when it's a pm
    if gc_contact:
        items_to_hide += [rename_menuitem, edit_groups_menuitem,
        subscription_menuitem, remove_from_roster_menuitem]

    for item in items_to_hide:
        item.set_no_show_all(True)
        item.hide()

    # Zeroconf Account
    if app.settings.get_account_setting(account, 'is_zeroconf'):
        for item in (send_single_message_menuitem,
        invite_menuitem, block_menuitem, unblock_menuitem, ignore_menuitem,
        unignore_menuitem, subscription_menuitem,
        manage_contact_menuitem, convert_to_gc_menuitem):
            item.set_no_show_all(True)
            item.hide()

        if contact.show in ('offline', 'error'):
            information_menuitem.set_sensitive(False)
            send_file_menuitem.set_sensitive(False)
        else:
            information_menuitem.connect('activate', roster.on_info_zeroconf,
                    contact, account)

        contact_context_menu.connect('selection-done',
                gtkgui_helpers.destroy_widget)
        contact_context_menu.show_all()
        return contact_context_menu

    # normal account

    if gc_contact:
        if not gc_contact.jid:
            # it's a pm and we don't know real JID
            invite_menuitem.set_sensitive(False)
        else:
            bookmarked = False
            c_ = app.contacts.get_contact(account, gc_contact.jid,
                gc_contact.resource)
            if c_ and c_.supports(Namespace.CONFERENCE):
                bookmarked = True
            build_invite_submenu(invite_menuitem, [(gc_contact, account)],
                show_bookmarked=bookmarked)
    else:
        force_resource = False
        if control and control.resource:
            force_resource = True
        build_invite_submenu(invite_menuitem, [(contact, account)],
            show_bookmarked=contact.supports(Namespace.CONFERENCE),
            force_resource=force_resource)

    if app.account_is_disconnected(account):
        invite_menuitem.set_sensitive(False)

    send_single_message_menuitem.connect('activate',
        roster.on_send_single_message_menuitem_activate, account, contact)

    remove_from_roster_menuitem.connect('activate', roster.on_req_usub,
        [(contact, account)])
    information_menuitem.connect('activate', roster.on_info, contact, account)

    if _('Not in contact list') not in contact.get_shown_groups():
        # contact is in normal group
        add_to_roster_menuitem.hide()
        add_to_roster_menuitem.set_no_show_all(True)

        if contact.sub in ('from', 'both'):
            send_auth_menuitem.set_sensitive(False)
        else:
            send_auth_menuitem.connect('activate', roster.authorize, jid, account)
        if contact.sub in ('to', 'both'):
            ask_auth_menuitem.set_sensitive(False)
        else:
            ask_auth_menuitem.connect('activate', roster.req_sub, jid,
                    _('I would like to add you to my contact list'), account,
                    contact.groups, contact.name)
        transport = app.get_transport_name_from_jid(jid,
            use_config_setting=False)
        if contact.sub in ('to', 'none') or transport not in ['jabber', None]:
            revoke_auth_menuitem.set_sensitive(False)
        else:
            revoke_auth_menuitem.connect('activate', roster.revoke_auth, jid,
                    account)

    elif app.connections[account].roster_supported:
        # contact is in group 'Not in contact list'
        add_to_roster_menuitem.set_no_show_all(False)
        subscription_menuitem.set_sensitive(False)

        add_to_roster_menuitem.connect('activate', roster.on_add_to_roster,
                contact, account)
    else:
        add_to_roster_menuitem.hide()
        add_to_roster_menuitem.set_no_show_all(True)
        subscription_menuitem.set_sensitive(False)

    # Hide items when it's self contact row
    if our_jid:
        manage_contact_menuitem.set_sensitive(False)

    # Unsensitive items when account is offline
    if app.account_is_disconnected(account):
        for widget in (send_single_message_menuitem, subscription_menuitem,
        add_to_roster_menuitem, remove_from_roster_menuitem,
        execute_command_menuitem):
            widget.set_sensitive(False)


    con = app.connections[account]
    if con.get_module('Blocking').supported:
        transport = app.get_transport_name_from_jid(jid, use_config_setting=False)
        if helpers.jid_is_blocked(account, jid):
            block_menuitem.set_no_show_all(True)
            block_menuitem.hide()
            if transport not in ('jabber', None):
                unblock_menuitem.set_no_show_all(True)
                unblock_menuitem.hide()
                unignore_menuitem.set_no_show_all(False)
                unignore_menuitem.connect('activate', roster.on_unblock, [(contact,
                        account)])
            else:
                unblock_menuitem.connect('activate', roster.on_unblock, [(contact,
                        account)])
        else:
            unblock_menuitem.set_no_show_all(True)
            unblock_menuitem.hide()
            if transport not in ('jabber', None):
                block_menuitem.set_no_show_all(True)
                block_menuitem.hide()
                ignore_menuitem.set_no_show_all(False)
                ignore_menuitem.connect('activate', roster.on_block, [(contact,
                        account)])
            else:
                block_menuitem.connect('activate', roster.on_block, [(contact,
                        account)])
    else:
        unblock_menuitem.set_no_show_all(True)
        block_menuitem.set_sensitive(False)
        unblock_menuitem.hide()

    contact_context_menu.connect('selection-done', gtkgui_helpers.destroy_widget)
    contact_context_menu.show_all()
    return contact_context_menu

def get_transport_menu(contact, account):
    roster = app.interface.roster
    jid = contact.jid

    menu = Gtk.Menu()

    # Send single message
    item = Gtk.MenuItem.new_with_mnemonic(_('Send Single _Message…'))
    item.connect('activate', roster.on_send_single_message_menuitem_activate,
        account, contact)
    menu.append(item)
    if app.account_is_disconnected(account):
        item.set_sensitive(False)

    blocked = False
    if helpers.jid_is_blocked(account, jid):
        blocked = True

    item = Gtk.SeparatorMenuItem.new() # separator
    menu.append(item)

    # Execute Command
    item = Gtk.MenuItem.new_with_mnemonic(_('E_xecute Command…'))
    menu.append(item)
    item.connect('activate', roster.on_execute_command, contact, account,
        contact.resource)
    if app.account_is_disconnected(account):
        item.set_sensitive(False)

    # Manage Transport submenu
    item = Gtk.MenuItem.new_with_mnemonic(_('_Manage Transport'))
    manage_transport_submenu = Gtk.Menu()
    item.set_submenu(manage_transport_submenu)
    menu.append(item)

    # Modify Transport
    item = Gtk.MenuItem.new_with_mnemonic(_('_Modify Transport'))
    manage_transport_submenu.append(item)
    item.connect('activate', roster.on_edit_agent, contact, account)
    if app.account_is_disconnected(account):
        item.set_sensitive(False)

    # Rename
    item = Gtk.MenuItem.new_with_mnemonic(_('_Rename…'))
    manage_transport_submenu.append(item)
    item.connect('activate', roster.on_rename, 'agent', jid, account)
    if app.account_is_disconnected(account):
        item.set_sensitive(False)

    item = Gtk.SeparatorMenuItem.new() # separator
    manage_transport_submenu.append(item)

    # Block
    if blocked:
        item = Gtk.MenuItem.new_with_mnemonic(_('_Unblock'))
        item.connect('activate', roster.on_unblock, [(contact, account)])
    else:
        item = Gtk.MenuItem.new_with_mnemonic(_('_Block'))
        item.connect('activate', roster.on_block, [(contact, account)])

    manage_transport_submenu.append(item)
    if app.account_is_disconnected(account):
        item.set_sensitive(False)

    # Remove
    item = Gtk.MenuItem.new_with_mnemonic(_('Remo_ve'))
    manage_transport_submenu.append(item)
    item.connect('activate', roster.on_remove_agent, [(contact, account)])
    if app.account_is_disconnected(account):
        item.set_sensitive(False)

    item = Gtk.SeparatorMenuItem.new() # separator
    menu.append(item)

    # Information
    information_menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Information'))
    menu.append(information_menuitem)
    information_menuitem.connect('activate', roster.on_info, contact, account)
    if app.account_is_disconnected(account):
        information_menuitem.set_sensitive(False)

    menu.connect('selection-done', gtkgui_helpers.destroy_widget)
    menu.show_all()
    return menu


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
        ('app.browse-history', _('History')),
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
        ('app.browse-history', _('History')),
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
        ('-add-contact', _('Add Contact…')),
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
                if 'add-contact' in action:
                    variant = GLib.Variant('as', [account, ''])
                else:
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
        modify_account_item = Gio.MenuItem.new(_('_Add Account…'),
                                               'app.accounts::')
        acc_menu.append_item(modify_account_item)
        return

    if len(accounts_list) > 1:
        modify_account_item = Gio.MenuItem.new(_('_Modify Accounts…'),
                                               'app.accounts::')
        acc_menu.append_item(modify_account_item)
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
        return

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


def get_roster_menu(account, jid):
    if helpers.jid_is_blocked(account, jid):
        block_label = _('Unblock')
    else:
        block_label = _('Block…')
    menu_items = [
        ('contact-info', _('Information')),
        ('execute-command', _('Execute Command…')),
        ('block-contact', block_label),
        ('remove-contact', _('Remove…')),
    ]

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

    if not contact.is_groupchat and not contact.is_in_roster:
        menu_items.append(('add-to-roster', _('Add to contact list')))

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
        account=account, jid=contact.jid or '')
    if contact.jid is None:
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
    action = 'win.ban-%s::%s' % (control_id, contact.jid or '')
    if is_affiliation_change_allowed(self_contact, contact, 'outcast'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    item = Gtk.MenuItem(label=_('Make Owner'))
    action = 'win.change-affiliation-%s(["%s", "owner"])' % (control_id,
                                                             contact.jid)
    if is_affiliation_change_allowed(self_contact, contact, 'owner'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Make Admin'))
    action = 'win.change-affiliation-%s(["%s", "admin"])' % (control_id,
                                                             contact.jid)
    if is_affiliation_change_allowed(self_contact, contact, 'admin'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Make Member'))
    action = 'win.change-affiliation-%s(["%s", "member"])' % (control_id,
                                                              contact.jid)
    if is_affiliation_change_allowed(self_contact, contact, 'member'):
        item.set_detailed_action_name(action)
    else:
        item.set_sensitive(False)
    menu.append(item)

    item = Gtk.MenuItem(label=_('Revoke Member'))
    action = 'win.change-affiliation-%s(["%s", "none"])' % (control_id,
                                                            contact.jid)
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
