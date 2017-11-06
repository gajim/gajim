# -*- coding:utf-8 -*-
## src/gui_menu_builder.py
##
## Copyright (C) 2009-2014 Yann Leboulanger <asterix AT lagaule.org>
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

from gi.repository import Gtk, Gio, GLib
import os
from gajim import gtkgui_helpers
from gajim import message_control

from gajim.common import app
from gajim.common import helpers
from gajim.common import i18n
from nbxmpp.protocol import NS_COMMANDS, NS_FILE, NS_MUC, NS_ESESSION
from nbxmpp.protocol import NS_JINGLE_FILE_TRANSFER_5, NS_CONFERENCE
from gajim.gtkgui_helpers import get_action

def build_resources_submenu(contacts, account, action, room_jid=None,
                room_account=None, cap=None):
    """
    Build a submenu with contact's resources. room_jid and room_account are for
    action self.on_invite_to_room
    """
    roster = app.interface.roster
    sub_menu = Gtk.Menu()

    iconset = app.config.get('iconset')
    if not iconset:
        iconset = app.config.DEFAULT_ICONSET
    path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
    for c in contacts:
        item = Gtk.MenuItem.new_with_label(
            '%s (%s)' % (c.resource, str(c.priority)))
        sub_menu.append(item)

        if action == roster.on_invite_to_room:
            item.connect('activate', action, [(c, account)], room_jid,
                    room_account, c.resource)
        elif action == roster.on_invite_to_new_room:
            item.connect('activate', action, [(c, account)], c.resource)
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

    if contacts_transport == False:
        # they are not all from the same transport
        invite_menuitem.set_sensitive(False)
        return
    invite_to_submenu = Gtk.Menu()
    invite_menuitem.set_submenu(invite_to_submenu)
    invite_to_new_room_menuitem = Gtk.MenuItem.new_with_mnemonic(_(
        '_New Group Chat'))
    if len(contact_list) > 1: # several resources
        invite_to_new_room_menuitem.set_submenu(build_resources_submenu(
            contact_list, account, roster.on_invite_to_new_room, cap=NS_MUC))
    elif len(list_) == 1 and contact.supports(NS_MUC):
        invite_menuitem.set_sensitive(True)
        # use resource if it's self contact
        if contact.jid == app.get_jid_from_account(account) or force_resource:
            resource = contact.resource
        else:
            resource = None
        invite_to_new_room_menuitem.connect('activate',
            roster.on_invite_to_new_room, list_, resource)
    elif len(list_) > 1:
        list2 = []
        for (c, a) in list_:
            if c.supports(NS_MUC):
                list2.append((c, a))
        if len(list2) > 0:
            invite_to_new_room_menuitem.connect('activate',
                roster.on_invite_to_new_room, list2, None)
        else:
            invite_menuitem.set_sensitive(False)
    else:
        invite_menuitem.set_sensitive(False)
    # transform None in 'jabber'
    c_t = contacts_transport or 'jabber'
    muc_jid = {}
    for account in connected_accounts:
        for t in app.connections[account].muc_jid:
            muc_jid[t] = app.connections[account].muc_jid[t]
    if c_t not in muc_jid:
        invite_to_new_room_menuitem.set_sensitive(False)
    rooms = [] # a list of (room_jid, account) tuple
    invite_to_submenu.append(invite_to_new_room_menuitem)
    minimized_controls = []
    for account in connected_accounts:
        minimized_controls += \
            list(app.interface.minimized_controls[account].values())
    for gc_control in app.interface.msg_win_mgr.get_controls(
    message_control.TYPE_GC) + minimized_controls:
        acct = gc_control.account
        if acct not in connected_accounts:
            continue
        room_jid = gc_control.room_jid
        if room_jid in ignore_rooms:
            continue
        if room_jid in app.gc_connected[acct] and \
        app.gc_connected[acct][room_jid] and \
        contacts_transport in ['jabber', None]:
            rooms.append((room_jid, acct))
    if len(rooms):
        item = Gtk.SeparatorMenuItem.new() # separator
        invite_to_submenu.append(item)
        for (room_jid, account) in rooms:
            menuitem = Gtk.MenuItem.new_with_label(room_jid.split('@')[0])
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
        for room in app.connections[account].bookmarks:
            r_jid = room['jid']
            if r_jid in r_jids:
                continue
            if r_jid not in app.gc_connected[account] or not \
            app.gc_connected[account][r_jid]:
                rooms2.append((r_jid, account))
                r_jids.append(r_jid)

    if not rooms2:
        return
    item = Gtk.SeparatorMenuItem.new() # separator
    invite_to_submenu.append(item)
    for (room_jid, account) in rooms2:
        menuitem = Gtk.MenuItem.new_with_label(room_jid.split('@')[0])
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

    xml = gtkgui_helpers.get_gtk_builder('contact_context_menu.ui')
    contact_context_menu = xml.get_object('contact_context_menu')

    start_chat_menuitem = xml.get_object('start_chat_menuitem')
    execute_command_menuitem = xml.get_object('execute_command_menuitem')
    rename_menuitem = xml.get_object('rename_menuitem')
    edit_groups_menuitem = xml.get_object('edit_groups_menuitem')
    send_file_menuitem = xml.get_object('send_file_menuitem')
    assign_openpgp_key_menuitem = xml.get_object('assign_openpgp_key_menuitem')
    add_special_notification_menuitem = xml.get_object(
            'add_special_notification_menuitem')
    information_menuitem = xml.get_object('information_menuitem')
    history_menuitem = xml.get_object('history_menuitem')
    send_custom_status_menuitem = xml.get_object('send_custom_status_menuitem')
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
        start_chat_menuitem.set_submenu(build_resources_submenu(contacts,
                account, app.interface.on_open_chat_window))
        send_file_menuitem.set_submenu(build_resources_submenu(contacts,
                account, roster.on_send_file_menuitem_activate, cap=NS_FILE))
        execute_command_menuitem.set_submenu(build_resources_submenu(
                contacts, account, roster.on_execute_command, cap=NS_COMMANDS))
    else:
        start_chat_menuitem.connect('activate',
                app.interface.on_open_chat_window, contact, account)
        if contact.supports(NS_FILE) or contact.supports(NS_JINGLE_FILE_TRANSFER_5):
            send_file_menuitem.set_sensitive(True)
            send_file_menuitem.connect('activate',
                    roster.on_send_file_menuitem_activate, contact, account)
        else:
            send_file_menuitem.set_sensitive(False)

        if contact.supports(NS_COMMANDS):
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

    rename_menuitem.connect('activate', roster.on_rename, 'contact', jid,
        account)
    history_menuitem.connect('activate', roster.on_history, contact, account)

    if control:
        convert_to_gc_menuitem.connect('activate',
            control._on_convert_to_gc_menuitem_activate)
    else:
        items_to_hide.append(convert_to_gc_menuitem)

    if _('Not in Roster') not in contact.get_shown_groups():
        # contact is in normal group
        edit_groups_menuitem.connect('activate', roster.on_edit_groups, [(contact,
                account)])

        if app.connections[account].gpg:
            assign_openpgp_key_menuitem.connect('activate',
                    roster.on_assign_pgp_key, contact, account)
        else:
            assign_openpgp_key_menuitem.set_sensitive(False)
    else:
        # contact is in group 'Not in Roster'
        edit_groups_menuitem.set_sensitive(False)
        assign_openpgp_key_menuitem.set_sensitive(False)

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
    if app.config.get_per('accounts', account, 'is_zeroconf'):
        for item in (send_custom_status_menuitem, send_single_message_menuitem,
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

    # send custom status icon
    blocked = False
    if helpers.jid_is_blocked(account, jid):
        blocked = True
    else:
        for group in contact.get_shown_groups():
            if helpers.group_is_blocked(account, group):
                blocked = True
                break
    transport = app.get_transport_name_from_jid(jid, use_config_setting=False)
    if transport and transport != 'jabber':
        # Transport contact, send custom status unavailable
        send_custom_status_menuitem.set_sensitive(False)
    elif blocked:
        send_custom_status_menuitem.set_sensitive(False)

    if gc_contact:
        if not gc_contact.jid:
            # it's a pm and we don't know real JID
            invite_menuitem.set_sensitive(False)
        else:
            bookmarked = False
            c_ = app.contacts.get_contact(account, gc_contact.jid,
                gc_contact.resource)
            if c_ and c_.supports(NS_CONFERENCE):
                bookmarked=True
            build_invite_submenu(invite_menuitem, [(gc_contact, account)],
                show_bookmarked=bookmarked)
    else:
        force_resource = False
        if control and control.resource:
            force_resource = True
        build_invite_submenu(invite_menuitem, [(contact, account)],
            show_bookmarked=contact.supports(NS_CONFERENCE),
            force_resource=force_resource)

    if app.account_is_disconnected(account):
        invite_menuitem.set_sensitive(False)

    # One or several resource, we do the same for send_custom_status
    status_menuitems = Gtk.Menu()
    send_custom_status_menuitem.set_submenu(status_menuitems)
    for s in ('online', 'chat', 'away', 'xa', 'dnd', 'offline'):
        # icon MUST be different instance for every item
        status_menuitem = Gtk.MenuItem.new_with_label(helpers.get_uf_show(s))
        status_menuitem.connect('activate', roster.on_send_custom_status,
                                [(contact, account)], s)
        status_menuitems.append(status_menuitem)

    send_single_message_menuitem.connect('activate',
        roster.on_send_single_message_menuitem_activate, account, contact)

    remove_from_roster_menuitem.connect('activate', roster.on_req_usub,
        [(contact, account)])
    information_menuitem.connect('activate', roster.on_info, contact, account)

    if _('Not in Roster') not in contact.get_shown_groups():
        # contact is in normal group
        add_to_roster_menuitem.hide()
        add_to_roster_menuitem.set_no_show_all(True)

        if contact.sub in ('from', 'both'):
            send_auth_menuitem.set_sensitive(False)
        else:
            send_auth_menuitem.connect('activate', roster.authorize, jid, account)
        if contact.sub in ('to', 'both'):
            ask_auth_menuitem.set_sensitive(False)
            add_special_notification_menuitem.connect('activate',
                    roster.on_add_special_notification_menuitem_activate, jid)
        else:
            ask_auth_menuitem.connect('activate', roster.req_sub, jid,
                    _('I would like to add you to my roster'), account,
                    contact.groups, contact.name)
        transport = app.get_transport_name_from_jid(jid,
            use_config_setting=False)
        if contact.sub in ('to', 'none') or transport not in ['jabber', None]:
            revoke_auth_menuitem.set_sensitive(False)
        else:
            revoke_auth_menuitem.connect('activate', roster.revoke_auth, jid,
                    account)

    elif app.connections[account].roster_supported:
        # contact is in group 'Not in Roster'
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
        execute_command_menuitem, send_custom_status_menuitem):
            widget.set_sensitive(False)

    if app.connections[account] and (app.connections[account].\
    privacy_rules_supported or app.connections[account].blocking_supported):
        if helpers.jid_is_blocked(account, jid):
            block_menuitem.set_no_show_all(True)
            block_menuitem.hide()
            if app.get_transport_name_from_jid(jid, use_config_setting=False)\
            and transport != 'jabber':
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
            if app.get_transport_name_from_jid(jid, use_config_setting=False)\
            and transport != 'jabber':
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

    # Send Custom Status
    send_custom_status_menuitem = Gtk.MenuItem.new_with_mnemonic(
        _('Send Cus_tom Status'))
    if blocked:
        send_custom_status_menuitem.set_sensitive(False)
    else:
        status_menuitems = Gtk.Menu()
        send_custom_status_menuitem.set_submenu(status_menuitems)
        for s in ('online', 'chat', 'away', 'xa', 'dnd', 'offline'):
            status_menuitem = Gtk.MenuItem.new_with_label(helpers.get_uf_show(
                s))
            status_menuitem.connect('activate', roster.on_send_custom_status,
                [(contact, account)], s)
            status_menuitems.append(status_menuitem)
    menu.append(send_custom_status_menuitem)
    if app.account_is_disconnected(account):
        send_custom_status_menuitem.set_sensitive(False)

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

'''
Build dynamic Application Menus
'''


def get_singlechat_menu(control_id):
    singlechat_menu = [
        ('win.send-file-', _('Send File...')),
        ('win.invite-contacts-', _('Invite Contacts')),
        ('win.add-to-roster-', _('Add to Roster')),
        ('win.toggle-audio-', _('Audio Session')),
        ('win.toggle-video-', _('Video Session')),
        ('win.information-', _('Information')),
        ('win.browse-history-', _('History')),
        ]

    def build_menu(preset):
        menu = Gio.Menu()
        for item in preset:
            action_name, label = item
            if action_name == 'win.browse-history-':
                menu.append(label, action_name + control_id + '::none')
            else:
                menu.append(label, action_name + control_id)
        return menu

    return build_menu(singlechat_menu)


def get_groupchat_menu(control_id):
    groupchat_menu = [
        (_('Manage Room'), [
            ('win.change-subject-', _('Change Subject')),
            ('win.configure-', _('Configure Room')),
            ('win.destroy-', _('Destroy Room')),
            ]),
        ('win.change-nick-', _('Change Nick')),
        ('win.bookmark-', _('Bookmark Room')),
        ('win.request-voice-', _('Request Voice')),
        ('win.notify-on-message-', _('Notify on all messages')),
        ('win.minimize-', _('Minimize on close')),
        ('win.browse-history-', _('History')),
        ('win.disconnect-', _('Disconnect')),
        ]

    def build_menu(preset):
        menu = Gio.Menu()
        for item in preset:
            if isinstance(item[1], str):
                action_name, label = item
                if action_name == 'win.browse-history-':
                    menu.append(label, action_name + control_id + '::none')
                else:
                    menu.append(label, action_name + control_id)
            else:
                label, sub_menu = item
                # This is a submenu
                submenu = build_menu(sub_menu)
                menu.append_submenu(label, submenu)
        return menu

    return build_menu(groupchat_menu)


def get_bookmarks_menu(account, rebuild=False):
    if not app.connections[account].bookmarks:
        return None
    menu = Gio.Menu()

    # Build Join Groupchat
    action = 'app.{}-join-groupchat'.format(account)
    menuitem = Gio.MenuItem.new(_('Join Group Chat'), action)
    variant = GLib.Variant('s', account)
    menuitem.set_action_and_target_value(action, variant)
    menu.append_item(menuitem)

    # Build Bookmarks
    section = Gio.Menu()
    for bookmark in app.connections[account].bookmarks:
        name = bookmark['name']
        if not name:
            # No name was given for this bookmark.
            # Use the first part of JID instead...
            name = bookmark['jid'].split("@")[0]

        # Shorten long names
        name = (name[:42] + '..') if len(name) > 42 else name

        action = 'app.{}-activate-bookmark'.format(account)
        menuitem = Gio.MenuItem.new(name, action)

        # Create Variant Dict
        dict_ = {'account': GLib.Variant('s', account),
                 'jid': GLib.Variant('s', bookmark['jid'])}
        if bookmark['nick']:
            dict_['nick'] = GLib.Variant('s', bookmark['nick'])
        if bookmark['password']:
            dict_['password'] = GLib.Variant('s', bookmark['password'])
        variant_dict = GLib.Variant('a{sv}', dict_)

        menuitem.set_action_and_target_value(action, variant_dict)
        section.append_item(menuitem)
    menu.append_section(None, section)
    if not rebuild:
        get_action(account + '-activate-bookmark').set_enabled(True)

    return menu


def get_account_menu(account):
    '''
    [(action, label/sub_menu)]
        action: string
        label: string
        sub menu: list
    '''
    account_menu = [
            ('-add-contact', _('Add Contact...')),
            ('-join-groupchat', _('Join Group Chat')),
            ('-profile', _('Profile')),
            ('-services', _('Discover Services')),
            ('-start-chat', _('Start Chat...')),
            ('-start-single-chat', _('Send Single Message...')),
            ('Advanced', [
                ('-archive', _('Archiving Preferences')),
                ('-sync-history', _('Synchronise History')),
                ('-privacylists', _('Privacy Lists')),
                ('-server-info', _('Server Info')),
                ('-xml-console', _('XML Console'))
                ]),
            ('Admin', [
                ('-send-server-message', _('Send Server Message...')),
                ('-set-motd', _('Set MOTD...')),
                ('-update-motd', _('Update MOTD...')),
                ('-delete-motd', _('Delete MOTD...'))
                ]),
            ]

    def build_menu(preset):
        menu = Gio.Menu()
        for item in preset:
            if isinstance(item[1], str):
                action, label = item
                if action == '-join-groupchat':
                    bookmark_menu = get_bookmarks_menu(account, True)
                    if bookmark_menu:
                        menu.append_submenu(label, bookmark_menu)
                        continue
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
    menu_position = 0
    if os.name == 'nt':
        menu_position = 1

    acc_menu = menubar.get_item_link(menu_position, 'submenu')
    acc_menu.remove_all()
    accounts_list = sorted(app.contacts.get_accounts())
    if not accounts_list:
        no_accounts = _('No Accounts available')
        acc_menu.append_item(Gio.MenuItem.new(no_accounts, None))
        return
    if len(accounts_list) > 1:
        for acc in accounts_list:
            label = app.config.get_per('accounts', acc, 'account_label')
            acc_menu.append_submenu(
                label or acc, get_account_menu(acc))
    else:
        acc_menu = get_account_menu(accounts_list[0])
        menubar.remove(menu_position)
        menubar.insert_submenu(menu_position, 'Accounts', acc_menu)


def build_bookmark_menu(account):
    menubar = app.app.get_menubar()
    bookmark_menu = get_bookmarks_menu(account)
    if not bookmark_menu:
        return

    menu_position = 0
    if os.name == 'nt':
        menu_position = 1

    # Accounts Submenu
    acc_menu = menubar.get_item_link(menu_position, 'submenu')

    # We have more than one Account active
    if acc_menu.get_item_link(0, 'submenu'):
        for i in range(acc_menu.get_n_items()):
            label = acc_menu.get_item_attribute_value(i, 'label')
            account_label = app.config.get_per('accounts', account,
                                               'account_label')
            if label.get_string() in (account_label, account):
                menu = acc_menu.get_item_link(i, 'submenu')
    else:
        # We have only one Account active
        menu = acc_menu
    label = menu.get_item_attribute_value(1, 'label').get_string()
    menu.remove(1)
    menu.insert_submenu(1, label, bookmark_menu)


def get_encryption_menu(control_id, type_id):
    menu = Gio.Menu()
    menu.append(
        'Disabled', 'win.set-encryption-{}::{}'.format(control_id, 'disabled'))
    for name, plugin in app.plugin_manager.encryption_plugins.items():
        if type_id == 'gc':
            if not hasattr(plugin, 'allow_groupchat'):
                continue
        if type_id == 'pm':
            if not hasattr(plugin, 'allow_privatchat'):
                continue
        menu_action = 'win.set-encryption-{}::{}'.format(
            control_id, name)
        menu.append(name, menu_action)
    if menu.get_n_items() == 1:
        return None
    return menu
